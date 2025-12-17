"""
Test cases for IMAP email client
"""

import pytest

from meeting_scheduler_mcp.calendar import BlockedTime


class TestBlockedTimeValidation:
    """Test suite for BlockedTime model validation."""

    def test_valid_blocked_time_with_duration(self):
        """Test valid BlockedTime with duration."""
        blocked = BlockedTime(
            datetime="2025-12-15T14:00:00+01:00", duration=60, reason="Meeting"
        )
        assert blocked.datetime == "2025-12-15T14:00:00+01:00"
        assert blocked.duration == 60
        assert blocked.reason == "Meeting"
        assert blocked.until is None

    def test_valid_blocked_time_with_until(self):
        """Test valid BlockedTime with until."""
        blocked = BlockedTime(
            datetime="2025-12-15", until="2025-12-16", reason="Vacation"
        )
        assert blocked.datetime == "2025-12-15"
        assert blocked.until == "2025-12-16"
        assert blocked.reason == "Vacation"
        assert blocked.duration is None

    def test_invalid_blocked_time_both_duration_and_until(self):
        """Test that BlockedTime rejects both duration and until."""
        with pytest.raises(ValueError):
            BlockedTime(
                datetime="2025-12-15T14:00:00+01:00",
                duration=60,
                until="2025-12-15T15:00:00+01:00",
                reason="Meeting",
            )

    def test_valid_blocked_time_neither_duration_nor_until(self):
        """Test that BlockedTime allows neither duration nor until (will be handled at runtime)."""
        # This is actually valid according to the current validation logic
        # The validation only prevents both being set, not neither
        blocked = BlockedTime(datetime="2025-12-15T14:00:00+01:00", reason="Meeting")
        assert blocked.datetime == "2025-12-15T14:00:00+01:00"
        assert blocked.duration is None
        assert blocked.until is None
        assert blocked.reason == "Meeting"

    def test_valid_blocked_time_all_day(self):
        """Test valid all-day BlockedTime."""
        blocked = BlockedTime(datetime="2025-12-15", reason="Vacation")
        assert blocked.datetime == "2025-12-15"
        assert blocked.duration is None
        assert blocked.until is None
        assert blocked.reason == "Vacation"

    def test_blocked_time_is_all_day(self):
        """Test is_all_day method."""
        all_day = BlockedTime(datetime="2025-12-15", reason="Vacation")
        assert all_day.is_all_day() is True

        timed = BlockedTime(
            datetime="2025-12-15T14:00:00+01:00", duration=60, reason="Meeting"
        )
        assert timed.is_all_day() is False

    def test_blocked_time_get_start(self):
        """Test get_start method."""
        from zoneinfo import ZoneInfo

        blocked = BlockedTime(
            datetime="2025-12-15T14:00:00+01:00", duration=60, reason="Meeting"
        )
        start = blocked.get_start(ZoneInfo("Europe/Berlin"))
        assert start.year == 2025
        assert start.month == 12
        assert start.day == 15
        assert start.hour == 14
        assert start.minute == 0

    def test_blocked_time_get_end(self):
        """Test get_end method."""
        from zoneinfo import ZoneInfo

        blocked = BlockedTime(
            datetime="2025-12-15T14:00:00+01:00", duration=60, reason="Meeting"
        )
        end = blocked.get_end(ZoneInfo("Europe/Berlin"))
        assert end.year == 2025
        assert end.month == 12
        assert end.day == 15
        assert end.hour == 15
        assert end.minute == 0

    def test_blocked_time_get_end_with_until(self):
        """Test get_end method with until."""
        from zoneinfo import ZoneInfo

        blocked = BlockedTime(
            datetime="2025-12-15", until="2025-12-16", reason="Vacation"
        )
        end = blocked.get_end(ZoneInfo("Europe/Berlin"))
        assert end.year == 2025
        assert end.month == 12
        assert end.day == 16
        assert end.hour == 23
        assert end.minute == 59
        assert end.second == 59


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
