"""
Test cases for calendar_manager.py
"""

import pytest
from freezegun import freeze_time

from tests.conftest import MockEmailClient


class TestCalendarManager:
    """Test suite for CalendarManager class."""

    def test_initialization(self, temp_calendar):
        """Test that CalendarManager initializes correctly."""
        calendar_path, cm = temp_calendar
        assert cm is not None
        assert cm.file_path.name == "test_calendar.yaml"

    def test_get_free_slots(self, temp_calendar):
        """Test getting free (unblocked) slots using PRD system."""
        calendar_path, cm = temp_calendar

        # Get free slots - should use weekly patterns from calendar.yaml
        free_slots = cm.get_free_slots()
        assert isinstance(free_slots, list)

        # Should have slots for weekdays 9-12 and 13-17
        if free_slots:
            slot = free_slots[0]
            assert hasattr(slot, "date")
            assert hasattr(slot, "start_time")
            assert hasattr(slot, "end_time")
            assert hasattr(slot, "timezone")

    def test_save_draft_and_block_slot(
        self, temp_calendar, mock_email_client: MockEmailClient
    ):
        """Test blocking a slot and saving email draft."""
        from datetime import datetime
        from zoneinfo import ZoneInfo

        calendar_path, cm = temp_calendar

        # Get free slots first
        free_slots = cm.get_free_slots()
        if not free_slots:
            pytest.skip("No free slots available for testing")

        # Block the first slot using the new API with mock email client
        slot = free_slots[0]
        # Create a datetime for the slot
        slot_start = datetime.combine(
            slot.date, slot.start_time, tzinfo=ZoneInfo(slot.timezone)
        )
        slot_end = datetime.combine(
            slot.date, slot.end_time, tzinfo=ZoneInfo(slot.timezone)
        )
        duration = int((slot_end - slot_start).total_seconds() / 60)

        success = cm.save_draft_and_block_slot(
            datetime_str=slot_start.isoformat(),
            duration=duration,
            reason="Test Meeting",
            subject="Test Meeting",
            body="Test body",
            to="test@example.com",
            email_client=mock_email_client,
        )

        # Verify the function returns a boolean
        assert isinstance(success, bool)
        assert success is True

        # Verify the email was saved via mock (using private helper methods)
        assert mock_email_client._get_draft_count() == 1
        drafts = mock_email_client._get_drafts()
        draft = drafts[0]
        assert draft["subject"] == "Test Meeting"
        assert draft["body"] == "Test body"
        assert draft["to"] == "test@example.com"

    @freeze_time("2023-12-15 08:00:00", tz_offset=1)
    def test_free_slots_with_weekly_pattern(self, temp_calendar):
        """Test that free slots respect weekly availability patterns."""
        calendar_path, cm = temp_calendar

        # Friday should have slots (9-12, 13-17)
        free_slots = cm.get_free_slots()

        # Filter for Friday slots
        friday_slots = [s for s in free_slots if s.date.weekday() == 4]  # Friday = 4

        if friday_slots:
            # Should have slots in the configured time ranges
            for slot in friday_slots:
                # Should be within 9-12 or 13-17
                slot_hour = slot.start_time.hour
                assert 9 <= slot_hour <= 12 or 13 <= slot_hour <= 17, (
                    f"Slot at {slot_hour}:00 outside configured hours"
                )

    @freeze_time("2023-12-16 08:00:00", tz_offset=1)  # Saturday
    def test_no_slots_on_weekend(self, temp_calendar):
        """Test that no slots are available on weekends."""
        calendar_path, cm = temp_calendar

        free_slots = cm.get_free_slots()

        # Filter for Saturday slots
        saturday_slots = [
            s for s in free_slots if s.date.weekday() == 5
        ]  # Saturday = 5

        # Should be no slots on Saturday (not in weekly pattern)
        assert len(saturday_slots) == 0, "Should not have slots on weekends"
