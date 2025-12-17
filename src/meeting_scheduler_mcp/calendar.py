"""
Calendar management for the meeting scheduler.
Manages free and blocked time slots in a YAML file.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import Enum
from pathlib import Path
from typing import List, Optional
from zoneinfo import ZoneInfo

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from .holidays import HolidayChecker
from .mail import EmailClientProtocol, IMAPEmailClient

logger = logging.getLogger(__name__)


class Weekday(str, Enum):
    """Weekdays."""
    MON = "mon"
    TUE = "tue"
    WED = "wed"
    THU = "thu"
    FRI = "fri"
    SAT = "sat"
    SUN = "sun"

    @property
    def iso_weekday(self) -> int:
        """ISO weekday (1=Monday, 7=Sunday)."""
        return {
            self.MON: 1, self.TUE: 2, self.WED: 3, self.THU: 4,
            self.FRI: 5, self.SAT: 6, self.SUN: 7,
        }[self]


class TimeSlot(BaseModel):
    """A time window within a day."""
    start: time
    end: time

    @model_validator(mode="after")
    def validate_order(self) -> "TimeSlot":
        if self.end <= self.start:
            raise ValueError(f"end ({self.end}) must be after start ({self.start})")
        return self

    def duration_minutes(self) -> int:
        """Duration in minutes."""
        return (self.end.hour * 60 + self.end.minute) - (self.start.hour * 60 + self.start.minute)


class WeeklyAvailability(BaseModel):
    """Availability for specific weekdays."""
    days: list[Weekday]
    slots: list[TimeSlot]

    @field_validator("days")
    @classmethod
    def validate_days_not_empty(cls, v: list[Weekday]) -> list[Weekday]:
        if not v:
            raise ValueError("days must not be empty")
        return v


class BlockedTime(BaseModel):
    """A blocked time."""
    datetime: str  # ISO 8601: "2024-12-23" or "2024-12-23T10:00+01:00"
    duration: Optional[int] = None  # minutes
    until: Optional[str] = None  # ISO 8601
    reason: Optional[str] = None

    @model_validator(mode="after")
    def validate_duration_or_until(self) -> "BlockedTime":
        if self.duration is not None and self.until is not None:
            raise ValueError("Either duration or until must be specified, not both")
        return self

    def is_all_day(self) -> bool:
        """Checks if this is an all-day block."""
        return "T" not in self.datetime

    def get_start(self, default_tz: ZoneInfo) -> datetime:
        """Parses datetime and returns start."""
        if self.is_all_day():
            d = date.fromisoformat(self.datetime)
            return datetime.combine(d, time(0, 0), tzinfo=default_tz)
        return datetime.fromisoformat(self.datetime)

    def get_end(self, default_tz: ZoneInfo) -> datetime:
        """Calculates end timepoint."""
        start = self.get_start(default_tz)

        if self.until:
            if "T" in self.until:
                return datetime.fromisoformat(self.until)
            else:
                # All day until end of until date
                d = date.fromisoformat(self.until)
                return datetime.combine(d, time(23, 59, 59), tzinfo=default_tz)

        if self.duration:
            return start + timedelta(minutes=self.duration)

        # All day
        if self.is_all_day():
            return datetime.combine(start.date(), time(23, 59, 59), tzinfo=default_tz)

        raise ValueError("Either duration, until, or all-day date required")


class Schedule(BaseModel):
    """Complete schedule configuration."""
    timezone: str
    slot_duration: int = Field(ge=5, le=480)
    holidays: Optional[str] = None  # e.g. "DE"
    weekly: list[WeeklyAvailability]

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except KeyError:
            raise ValueError(f"Invalid timezone: {v}")
        return v

    def get_tz(self) -> ZoneInfo:
        """Returns ZoneInfo."""
        return ZoneInfo(self.timezone)


class Calendar(BaseModel):
    """Root model for calendar.yaml."""
    schedule: Schedule
    blocked: list[BlockedTime] = Field(default_factory=list)


@dataclass(slots=True)
class AvailableSlot:
    """An available time slot."""

    date: date
    start_time: time
    end_time: time
    timezone: str

    def __str__(self) -> str:
        weekdays = {
            1: "Mon",
            2: "Tue",
            3: "Wed",
            4: "Thu",
            5: "Fri",
            6: "Sat",
            7: "Sun",
        }
        return f"{weekdays[self.date.isoweekday()]} {self.date.strftime('%d.%m.')}, {self.start_time.strftime('%H:%M')}"

    def to_dict(self) -> dict[str, str]:
        """Serialize to dictionary for API responses."""
        return {
            "date": self.date.isoformat(),
            "start": self.start_time.isoformat(),
            "end": self.end_time.isoformat(),
            "timezone": self.timezone,
        }


class CalendarStore:
    """Loads and saves calendar.yaml."""

    def __init__(self, path: Path | str):
        self.path = Path(path)

    def load(self) -> Calendar:
        """Load calendar from YAML."""
        with open(self.path) as f:
            data = yaml.safe_load(f)
        return Calendar.model_validate(data)

    def save(self, calendar: Calendar) -> None:
        """Save calendar as YAML."""
        data = calendar.model_dump(mode="json")
        with open(self.path, "w") as f:
            yaml.dump(
                data, f, default_flow_style=False, allow_unicode=True, sort_keys=False
            )

    def add_blocked(
        self,
        dt: datetime,
        duration: int | None = None,
        until: datetime | None = None,
        reason: str | None = None,
    ) -> None:
        """Add a blocked time."""
        calendar = self.load()

        blocked = BlockedTime(
            datetime=dt.isoformat(),
            duration=duration,
            until=until.isoformat() if until else None,
            reason=reason,
        )

        calendar.blocked.append(blocked)
        self.save(calendar)


class SlotFinder:
    """Finds available slots."""

    def __init__(self, calendar: Calendar):
        self.calendar = calendar
        self.tz = calendar.schedule.get_tz()
        self.holiday_checker = HolidayChecker(calendar.schedule.holidays)

    def find_available_slots(
        self,
        from_date: date | None = None,
        to_date: date | None = None,
        max_results: int = 10,
        min_notice_hours: int = 2,
    ) -> list[AvailableSlot]:
        """Find available slots."""

        now = datetime.now(self.tz)
        from_date = from_date or now.date()
        to_date = to_date or (from_date + timedelta(days=30))
        min_bookable = now + timedelta(hours=min_notice_hours)

        available: list[AvailableSlot] = []
        current = from_date

        while current <= to_date and len(available) < max_results:
            day_slots = self._get_slots_for_date(current, min_bookable)
            available.extend(day_slots)
            current += timedelta(days=1)

        return available[:max_results]

    def _get_slots_for_date(
        self, d: date, min_bookable: datetime
    ) -> list[AvailableSlot]:
        """Generate slots for a date."""

        # Holiday?
        if self.holiday_checker.is_holiday(d):
            return []

        # Find weekday
        iso_weekday = d.isoweekday()
        weekly_slots: list[TimeSlot] = []

        for weekly in self.calendar.schedule.weekly:
            if any(day.iso_weekday == iso_weekday for day in weekly.days):
                weekly_slots.extend(weekly.slots)

        if not weekly_slots:
            return []

        # Generate slots
        slot_duration = timedelta(minutes=self.calendar.schedule.slot_duration)
        available: list[AvailableSlot] = []

        for time_slot in weekly_slots:
            current = datetime.combine(d, time_slot.start, tzinfo=self.tz)
            end = datetime.combine(d, time_slot.end, tzinfo=self.tz)

            while current + slot_duration <= end:
                slot_start = current.time()
                slot_end = (current + slot_duration).time()

                if current >= min_bookable and not self._is_blocked(
                    d, slot_start, slot_end
                ):
                    available.append(
                        AvailableSlot(
                            date=d,
                            start_time=slot_start,
                            end_time=slot_end,
                            timezone=self.calendar.schedule.timezone,
                        )
                    )

                current += slot_duration

        return available

    def _is_blocked(self, d: date, start: time, end: time) -> bool:
        """Check if slot is blocked."""

        slot_start = datetime.combine(d, start, tzinfo=self.tz)
        slot_end = datetime.combine(d, end, tzinfo=self.tz)

        for blocked in self.calendar.blocked:
            block_start = blocked.get_start(self.tz)
            block_end = blocked.get_end(self.tz)

            # Check overlap
            if slot_start < block_end and block_start < slot_end:
                return True

        return False

    def is_slot_bookable(self, d: date, start: time, end: time) -> tuple[bool, str]:
        """Check if a slot is bookable."""

        now = datetime.now(self.tz)
        slot_dt = datetime.combine(d, start, tzinfo=self.tz)

        # Past?
        if slot_dt < now:
            return False, "Timepoint is in the past"

        # Holiday?
        if self.holiday_checker.is_holiday(d):
            name = self.holiday_checker.get_holiday_name(d) or "Holiday"
            return False, f"{name}"

        # Weekday available?
        iso_weekday = d.isoweekday()
        day_available = False

        for weekly in self.calendar.schedule.weekly:
            if any(day.iso_weekday == iso_weekday for day in weekly.days):
                for slot in weekly.slots:
                    if slot.start <= start and end <= slot.end:
                        day_available = True
                        break

        if not day_available:
            return False, "Outside of availability"

        # Blocked?
        if self._is_blocked(d, start, end):
            for blocked in self.calendar.blocked:
                block_start = blocked.get_start(self.tz)
                block_end = blocked.get_end(self.tz)
                slot_start = datetime.combine(d, start, tzinfo=self.tz)
                slot_end = datetime.combine(d, end, tzinfo=self.tz)

                if slot_start < block_end and block_start < slot_end:
                    return False, blocked.reason or "Blocked"

        return True, ""


class CalendarManager:
    """Manages the calendar in a YAML file."""

    def __init__(self, file_path: str = "calendar.yaml"):
        self.file_path = Path(file_path)
        self.calendar_store = CalendarStore(file_path)
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        """Ensures that the calendar file exists."""
        if not self.file_path.exists():
            # Create default calendar with reasonable settings
            default_calendar = Calendar(
                schedule=Schedule(
                    timezone="Europe/Berlin",
                    slot_duration=30,
                    holidays="DE",
                    weekly=[
                        WeeklyAvailability(
                            days=[
                                Weekday.MON,
                                Weekday.TUE,
                                Weekday.WED,
                                Weekday.THU,
                                Weekday.FRI,
                            ],
                            slots=[
                                TimeSlot(start=time(9, 0), end=time(12, 0)),
                                TimeSlot(start=time(13, 0), end=time(17, 0)),
                            ],
                        )
                    ],
                ),
                blocked=[],
            )
            self.calendar_store.save(default_calendar)

    def get_free_slots(self) -> List[AvailableSlot]:
        """Gets all free (unblocked) time slots using the PRD slot finder.

        Returns:
            List[AvailableSlot]: List of free time slots
        """
        try:
            calendar = self.calendar_store.load()
            finder = SlotFinder(calendar)
            return finder.find_available_slots(max_results=50)
        except FileNotFoundError as e:
            logger.error("Calendar file not found: %s", e)
            return []
        except Exception as e:
            logger.error("Error finding free slots: %s", e)
            return []

    def save_draft_and_block_slot(
        self,
        datetime_str: str,
        duration: int,
        reason: str,
        subject: str,
        body: str,
        to: str,
        in_reply_to: str = "",
        email_client: EmailClientProtocol | None = None,
    ) -> bool:
        """Blocks a time slot and saves a confirmation email as a draft.

        Args:
            datetime_str: ISO 8601 formatted datetime (e.g., "2025-12-15T14:00:00+01:00")
            duration: Duration in minutes
            reason: Reason for blocking the slot
            subject: Subject of the confirmation email
            body: Content of the confirmation email
            to: Recipient of the confirmation email
            in_reply_to: Message-ID of the email this is replying to (for email threading)
            email_client: Optional email client implementation (for dependency injection)

        Returns:
            bool: True on success, False on failure
        """
        try:
            # Parse the datetime string
            try:
                slot_start = datetime.fromisoformat(datetime_str)
            except ValueError as e:
                logger.error("Invalid datetime format: %s", e)
                return False

            # Validate duration
            if duration <= 0:
                logger.error("Invalid duration: %d (must be positive)", duration)
                return False

            # Add blocked time using CalendarStore
            self.calendar_store.add_blocked(
                dt=slot_start, duration=duration, reason=reason
            )

            # Save email as draft with threading support
            # Use injected email client or create default
            if email_client is None:
                email_client = IMAPEmailClient()

            with email_client:
                success = email_client.save_draft(
                    subject, body, to, in_reply_to=in_reply_to
                )
            return success

        except ValueError as e:
            logger.error("Invalid datetime format: %s", e)
            return False
        except FileNotFoundError as e:
            logger.error("Calendar file not found: %s", e)
            return False
        except (ConnectionError, OSError) as e:
            logger.error("Failed to save draft: %s", e)
            return False
        except Exception as e:
            logger.error("Error in save_draft_and_block_slot: %s", e)
            return False
