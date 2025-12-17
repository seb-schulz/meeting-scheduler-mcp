"""
Integration tests for the complete workflow.
"""

import pytest
from freezegun import freeze_time

from meeting_scheduler_mcp.tools import _save_draft_and_block_slot_internal as save_draft_func
from tests.conftest import MockEmailClient


class TestIntegration:
    """Integration tests for the complete workflow."""

    def test_save_draft_and_block_slot_integration(
        self, mock_email_client: MockEmailClient
    ):
        """Test the complete workflow of blocking a slot and saving a draft."""
        # Test the new API with mock email client
        result = save_draft_func(
            datetime="2025-12-15T14:00:00+01:00",
            duration=60,
            reason="Meeting",
            subject="Test Meeting",
            body="Test body",
            to="test@example.com",
            email_client=mock_email_client,
        )

        # Verify the result
        assert result["success"] is True

        # Verify that save_draft was called with correct parameters using mock assertions
        assert mock_email_client._get_draft_count() == 1
        draft = mock_email_client._get_drafts()[0]
        assert draft["subject"] == "Test Meeting"
        assert draft["body"] == "Test body"
        assert draft["to"] == "test@example.com"
        assert draft["in_reply_to"] == ""

    def test_save_draft_and_block_slot_invalid_datetime(self):
        """Test error handling for invalid datetime format."""
        result = save_draft_func(
            datetime="invalid-datetime",
            duration=60,
            reason="Meeting",
            subject="Test Meeting",
            body="Test body",
            to="test@example.com",
        )

        # Should return success=False due to invalid datetime
        assert result["success"] is False

    def test_save_draft_and_block_slot_invalid_duration(self):
        """Test error handling for invalid duration."""
        result = save_draft_func(
            datetime="2025-12-15T14:00:00+01:00",
            duration=0,  # Invalid duration
            reason="Meeting",
            subject="Test Meeting",
            body="Test body",
            to="test@example.com",
        )

        # Should return success=False due to invalid duration
        assert result["success"] is False

    def test_save_draft_and_block_slot_with_threading(
        self, mock_email_client: MockEmailClient
    ):
        """Test the workflow with email threading."""
        # Test with email threading
        result = save_draft_func(
            datetime="2025-12-15T14:00:00+01:00",
            duration=60,
            reason="Meeting",
            subject="Re: Meeting Request",
            body="Meeting confirmed",
            to="test@example.com",
            in_reply_to="<original-request@example.com>",
            email_client=mock_email_client,
        )

        # Verify the result
        assert result["success"] is True

        # Verify that save_draft was called with threading headers
        assert mock_email_client._get_draft_count() == 1
        draft = mock_email_client._get_drafts()[0]
        assert draft["in_reply_to"] == "<original-request@example.com>"

    @freeze_time("2025-12-15 08:00:00", tz_offset=1)
    def test_calendar_blocking_integration(self, temp_calendar):
        """Test that the calendar blocking works correctly."""
        # Get the calendar manager from the fixture
        _, calendar_manager = temp_calendar

        # Test the API directly with a mock email client
        mock_email_client = MockEmailClient()
        success = calendar_manager.save_draft_and_block_slot(
            datetime_str="2025-12-15T14:00:00+01:00",
            duration=60,
            reason="Integration Test",
            subject="Test Meeting",
            body="Test body",
            to="test@example.com",
            email_client=mock_email_client,
        )

        # Verify the function returns a boolean
        assert isinstance(success, bool)
        assert success is True

        # Verify the email was saved
        assert mock_email_client._get_draft_count() == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
