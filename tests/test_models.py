"""
Test cases for calendar models.
"""

from datetime import date, time
from zoneinfo import ZoneInfo

import pytest

from meeting_scheduler_mcp.calendar import (
    BlockedTime,
    TimeSlot,
    Weekday,
    WeeklyAvailability,
)


class TestTimeSlot:
    def test_valid_slot(self):
        slot = TimeSlot(start=time(9, 0), end=time(12, 0))
        assert slot.duration_minutes() == 180

    def test_invalid_end_before_start(self):
        with pytest.raises(ValueError, match="must be after start"):
            TimeSlot(start=time(12, 0), end=time(9, 0))

    def test_invalid_same_time(self):
        with pytest.raises(ValueError):
            TimeSlot(start=time(9, 0), end=time(9, 0))


class TestWeeklyAvailability:
    def test_valid_weekly(self):
        weekly = WeeklyAvailability(
            days=[Weekday.MON, Weekday.TUE],
            slots=[TimeSlot(start=time(9, 0), end=time(17, 0))],
        )
        assert len(weekly.days) == 2

    def test_empty_days_rejected(self):
        with pytest.raises(ValueError, match="must not be empty"):
            WeeklyAvailability(days=[], slots=[])


class TestBlockedTime:
    def test_datetime_with_duration(self):
        blocked = BlockedTime(
            datetime="2024-12-23T10:00+01:00", duration=60, reason="Test"
        )
        tz = ZoneInfo("Europe/Berlin")

        assert not blocked.is_all_day()
        end = blocked.get_end(tz)
        assert end.hour == 11

    def test_date_only_is_all_day(self):
        blocked = BlockedTime(datetime="2024-12-24", reason="Feiertag")

        assert blocked.is_all_day()

        tz = ZoneInfo("Europe/Berlin")
        start = blocked.get_start(tz)
        end = blocked.get_end(tz)

        assert start.hour == 0
        assert end.hour == 23

    def test_date_range_with_until(self):
        blocked = BlockedTime(
            datetime="2024-12-27", until="2024-12-31", reason="Urlaub"
        )
        tz = ZoneInfo("Europe/Berlin")

        start = blocked.get_start(tz)
        end = blocked.get_end(tz)

        assert start.date() == date(2024, 12, 27)
        assert end.date() == date(2024, 12, 31)
        assert end.hour == 23

    def test_duration_and_until_rejected(self):
        with pytest.raises(ValueError, match="not both"):
            BlockedTime(
                datetime="2024-12-23T10:00+01:00",
                duration=60,
                until="2024-12-23T12:00+01:00",
            )
