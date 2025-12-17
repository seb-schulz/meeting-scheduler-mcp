"""
Integration tests for MCP tools.
Tests the email search and draft functionality with threading support.
"""

from unittest.mock import MagicMock, patch

# Import the underlying function from tools module
from meeting_scheduler_mcp.tools import search_emails

# The function is now plain, no wrapper needed
search_emails_func = search_emails


class TestMCPEmailTools:
    """Test suite for MCP email tools."""

    @patch("meeting_scheduler_mcp.tools.IMAPEmailClient")
    def test_search_emails_with_metadata(self, mock_imap_client_class):
        """Test that search_emails_tool returns full email metadata including threading info."""
        # Setup mock instance
        mock_client = MagicMock()
        mock_imap_client_class.return_value = mock_client

        # Configure context manager behavior
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)

        # Mock email IDs
        mock_client.search_emails.return_value = [b"1", b"2"]

        # Mock email metadata with threading information
        mock_client.get_email_metadata.side_effect = [
            {
                "subject": "Meeting Request",
                "from": "client@example.com",
                "to": "me@example.com",
                "date": "Mon, 1 Jan 2024 10:00:00 +0000",
                "message_id": "<abc123@example.com>",
                "in_reply_to": "",
                "references": "",
                "body": "Can we schedule a meeting?",
            },
            {
                "subject": "Re: Meeting Request",
                "from": "me@example.com",
                "to": "client@example.com",
                "date": "Mon, 1 Jan 2024 11:00:00 +0000",
                "message_id": "<def456@example.com>",
                "in_reply_to": "<abc123@example.com>",
                "references": "<abc123@example.com>",
                "body": "Yes, let's schedule it.",
            },
        ]

        # Call the tool
        result = search_emails_func(mailbox="INBOX", criteria="UNSEEN")

        # Verify results
        assert isinstance(result, list)
        assert len(result) == 2

        # Verify first email metadata
        email1 = result[0]
        assert email1["id"] == "1"
        assert email1["subject"] == "Meeting Request"
        assert email1["from"] == "client@example.com"
        assert email1["to"] == "me@example.com"
        assert email1["message_id"] == "<abc123@example.com>"
        assert email1["in_reply_to"] == ""
        assert email1["references"] == ""

        # Verify second email metadata (reply)
        email2 = result[1]
        assert email2["id"] == "2"
        assert email2["subject"] == "Re: Meeting Request"
        assert email2["message_id"] == "<def456@example.com>"
        assert email2["in_reply_to"] == "<abc123@example.com>"
        assert email2["references"] == "<abc123@example.com>"

        # Verify threading relationship
        original_message_id = email1["message_id"]
        reply = email2
        assert reply["in_reply_to"] == original_message_id
        assert original_message_id in reply["references"]

        # Verify mock calls
        mock_client.search_emails.assert_called_once_with("INBOX", "UNSEEN")
        assert mock_client.get_email_metadata.call_count == 2

    def test_email_threading_relationships(self):
        """Test logic for identifying email threading relationships."""
        # Sample email data
        emails = [
            {
                "id": "1",
                "message_id": "<msg1@example.com>",
                "in_reply_to": "",
                "references": "",
            },
            {
                "id": "2",
                "message_id": "<msg2@example.com>",
                "in_reply_to": "<msg1@example.com>",
                "references": "<msg1@example.com>",
            },
            {
                "id": "3",
                "message_id": "<msg3@example.com>",
                "in_reply_to": "<msg2@example.com>",
                "references": "<msg1@example.com> <msg2@example.com>",
            },
        ]

        # Test finding replies
        original_msg_id = "<msg1@example.com>"
        replies = [email for email in emails if email["in_reply_to"] == original_msg_id]

        assert len(replies) == 1
        assert replies[0]["id"] == "2"

        # Test finding entire thread
        thread = [emails[0]]  # Start with original
        for email in emails[1:]:  # Add replies
            if email["in_reply_to"] in [e["message_id"] for e in thread]:
                thread.append(email)

        assert len(thread) == 3
        assert thread[0]["id"] == "1"  # Original
        assert thread[1]["id"] == "2"  # First reply
        assert thread[2]["id"] == "3"  # Second reply

    def test_message_id_validation(self):
        """Test validation of Message-ID format."""
        valid_message_ids = [
            "<abc123@example.com>",
            "<12345.67890@example.org>",
            "<unique-id-12345@mail.server.com>",
        ]

        invalid_message_ids = [
            "abc123@example.com",  # Missing angle brackets
            "<>",  # Empty
            "not-a-message-id",  # No format
            "",  # Empty string
        ]

        # Test valid formats
        for msg_id in valid_message_ids:
            assert msg_id.startswith("<") and msg_id.endswith(">")
            assert len(msg_id) > 2  # Not just <>
            content = msg_id[1:-1]  # Remove angle brackets
            assert "@" in content  # Should contain @
            assert "." in content or content.count("@") > 1  # Should have domain

        # Test invalid formats
        for msg_id in invalid_message_ids:
            is_valid = (
                msg_id.startswith("<") and msg_id.endswith(">") and len(msg_id) > 2
            )
            assert not is_valid
