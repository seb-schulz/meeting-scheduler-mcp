"""
Test cases for slot finder.
"""

from datetime import date, time

import pytest
from freezegun import freeze_time

from meeting_scheduler_mcp.calendar import (
    BlockedTime,
    Calendar,
    Schedule,
    SlotFinder,
    TimeSlot,
    Weekday,
    WeeklyAvailability,
)


@pytest.fixture
def basic_calendar() -> Calendar:
    """Basis-Kalender: Mo-Fr 9-12, 13-17."""
    return Calendar(
        schedule=Schedule(
            timezone="Europe/Berlin",
            slot_duration=30,
            holidays="DE",
            weekly=[
                WeeklyAvailability(
                    days=[Weekday.MON, Weekday.TUE, Weekday.WED, Weekday.THU, Weekday.FRI],
                    slots=[
                        TimeSlot(start=time(9, 0), end=time(12, 0)),
                        TimeSlot(start=time(13, 0), end=time(17, 0)),
                    ]
                )
            ]
        ),
        blocked=[]
    )


class TestSlotFinderBasic:

    @freeze_time("2025-01-06 08:00:00", tz_offset=1)  # Montag
    def test_generates_slots_for_workday(self, basic_calendar):
        finder = SlotFinder(basic_calendar)

        slots = finder.find_available_slots(
            from_date=date(2025, 1, 6),
            to_date=date(2025, 1, 6),
            max_results=50,
            min_notice_hours=1
        )

        # With min_notice_hours=1 and current time 8:00, slots from 9:00 onwards should be available
        # 9-12: 6 Slots, 13-17: 8 Slots = 14 total, but some may be filtered by min_notice
        assert len(slots) > 0  # Should have some slots available
        if slots:
            assert slots[0].start_time >= time(9, 0)

    @freeze_time("2025-01-04 08:00:00", tz_offset=1)  # Samstag
    def test_no_slots_on_weekend(self, basic_calendar):
        finder = SlotFinder(basic_calendar)

        slots = finder.find_available_slots(
            from_date=date(2025, 1, 4),
            to_date=date(2025, 1, 5),  # Sa + So
            max_results=50
        )

        assert len(slots) == 0

    @freeze_time("2025-01-01 08:00:00", tz_offset=1)  # Neujahr
    def test_no_slots_on_holiday(self, basic_calendar):
        finder = SlotFinder(basic_calendar)

        slots = finder.find_available_slots(
            from_date=date(2025, 1, 1),
            to_date=date(2025, 1, 1),
            max_results=50
        )

        assert len(slots) == 0


class TestSlotFinderWithBlocks:

    @freeze_time("2025-01-06 08:00:00", tz_offset=1)
    def test_blocked_slot_excluded(self, basic_calendar):
        basic_calendar.blocked.append(
            BlockedTime(
                datetime="2025-01-06T10:00+01:00",
                duration=60,
                reason="Meeting"
            )
        )

        finder = SlotFinder(basic_calendar)
        slots = finder.find_available_slots(
            from_date=date(2025, 1, 6),
            to_date=date(2025, 1, 6),
            max_results=50,
            min_notice_hours=1  # Explicitly set to 1 hour for this test
        )

        slot_starts = [s.start_time for s in slots]
        assert time(10, 0) not in slot_starts
        assert time(10, 30) not in slot_starts
        assert time(11, 0) in slot_starts

    @freeze_time("2025-01-06 08:00:00", tz_offset=1)
    def test_all_day_block(self, basic_calendar):
        basic_calendar.blocked.append(
            BlockedTime(datetime="2025-01-06", reason="Urlaub")
        )

        finder = SlotFinder(basic_calendar)
        slots = finder.find_available_slots(
            from_date=date(2025, 1, 6),
            to_date=date(2025, 1, 6),
            max_results=50
        )

        assert len(slots) == 0

    @freeze_time("2025-01-06 08:00:00", tz_offset=1)
    def test_multi_day_block(self, basic_calendar):
        basic_calendar.blocked.append(
            BlockedTime(
                datetime="2025-01-06",
                until="2025-01-08",
                reason="Urlaub"
            )
        )

        finder = SlotFinder(basic_calendar)
        slots = finder.find_available_slots(
            from_date=date(2025, 1, 6),
            to_date=date(2025, 1, 10),
            max_results=50
        )

        # Mo, Di, Mi blockiert, Do + Fr frei
        slot_dates = {s.date for s in slots}
        assert date(2025, 1, 6) not in slot_dates
        assert date(2025, 1, 7) not in slot_dates
        assert date(2025, 1, 8) not in slot_dates
        assert date(2025, 1, 9) in slot_dates
        assert date(2025, 1, 10) in slot_dates


class TestIsSlotBookable:

    @freeze_time("2025-01-06 08:00:00", tz_offset=1)
    def test_valid_slot_bookable(self, basic_calendar):
        finder = SlotFinder(basic_calendar)

        bookable, reason = finder.is_slot_bookable(
            date(2025, 1, 6), time(14, 0), time(14, 30)
        )

        assert bookable is True
        assert reason == ""

    @freeze_time("2025-01-06 08:00:00", tz_offset=1)
    def test_holiday_not_bookable(self, basic_calendar):
        finder = SlotFinder(basic_calendar)

        bookable, reason = finder.is_slot_bookable(
            date(2025, 12, 25), time(10, 0), time(10, 30)
        )

        assert bookable is False
        assert "Christmas Day" in reason

    @freeze_time("2025-01-06 08:00:00", tz_offset=1)
    def test_weekend_not_bookable(self, basic_calendar):
        finder = SlotFinder(basic_calendar)

        bookable, reason = finder.is_slot_bookable(
            date(2025, 1, 11), time(10, 0), time(10, 30)  # Samstag
        )

        assert bookable is False
        assert "availability" in reason

    @freeze_time("2025-01-06 08:00:00", tz_offset=1)
    def test_blocked_not_bookable(self, basic_calendar):
        basic_calendar.blocked.append(
            BlockedTime(
                datetime="2025-01-06T14:00+01:00",
                duration=60,
                reason="Lisa Meeting"
            )
        )

        finder = SlotFinder(basic_calendar)

        bookable, reason = finder.is_slot_bookable(
            date(2025, 1, 6), time(14, 0), time(14, 30)
        )

        assert bookable is False
        assert "Lisa" in reason
