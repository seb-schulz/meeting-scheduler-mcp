"""
MCP tool implementations for the meeting scheduler.
This module contains the business logic for all MCP tools.
"""

import logging
from typing import Annotated, Dict, List

from pydantic import Field

from .calendar import CalendarManager
from .mail import IMAPEmailClient

logger = logging.getLogger(__name__)

# Initialize Calendar Manager
calendar_manager = CalendarManager()


def search_emails(
    mailbox: Annotated[
        str,
        Field(
            description="Mailbox name to search in. Defaults to INBOX. Can be any valid IMAP mailbox name such as INBOX, INBOX.Sent, INBOX.Drafts, or custom folders. The mailbox must exist in your email account."
        ),
    ] = "INBOX",
    criteria: Annotated[
        str,
        Field(
            description='Search criteria using IMAP search syntax. Defaults to UNSEEN. Supports various search options: UNSEN for unseen emails, FROM "sender@example.com" for emails from specific sender, SUBJECT "meeting" for emails with specific subject, BEFORE 01-Jan-2024 or SINCE 01-Jan-2024 for date ranges, TEXT "urgent" for emails containing specific text. Multiple criteria can be combined with spaces.'
        ),
    ] = "UNSEEN",
) -> List[Dict[str, str]] | Dict[str, str]:
    """Search emails with full metadata including Message-ID, In-Reply-To, and References headers for email threading. Find meeting requests, track conversations, and maintain context across email exchanges. Supports custom mailboxes and flexible IMAP search criteria. Returns comprehensive email data with subject, sender, recipient, date, and body content."""
    try:
        with IMAPEmailClient() as client:
            email_ids = client.search_emails(mailbox, criteria)

            result = []
            for email_id in email_ids:
                # Get full email metadata including threading information
                metadata = client.get_email_metadata(int(email_id), mailbox)

                # Convert email_id to string for consistent return format
                email_id_str = (
                    email_id.decode() if isinstance(email_id, bytes) else str(email_id)
                )

                result.append(
                    {
                        "id": email_id_str,
                        "subject": metadata.get("subject", ""),
                        "from": metadata.get("from", ""),
                        "to": metadata.get("to", ""),
                        "date": metadata.get("date", ""),
                        "message_id": metadata.get("message_id", ""),
                        "in_reply_to": metadata.get("in_reply_to", ""),
                        "references": metadata.get("references", ""),
                        "body": metadata.get("body", ""),
                    }
                )

        return result

    except (ConnectionError, OSError) as e:
        logger.error("Failed to search emails: %s", e)
        return {"error": f"Email search failed: {e}"}
    except Exception as e:
        logger.error("Unexpected error searching emails: %s", e)
        return {"error": f"Unexpected error: {e}"}


def get_free_slots() -> List[Dict[str, str]] | Dict[str, str]:
    """Get up to 50 available time slots from your calendar with timezone information. Uses intelligent slot finding with holiday awareness, minimum notice period validation (2 hours), and automatic filtering of blocked/past slots. Perfect for finding meeting times and managing your schedule. Returns slots in ISO 8601 format with date, start, end, and timezone."""
    try:
        free_slots = calendar_manager.get_free_slots()
        return [slot.to_dict() for slot in free_slots]
    except FileNotFoundError as e:
        logger.error("Calendar file not found: %s", e)
        return {"error": f"Calendar file not found: {e}"}
    except Exception as e:
        logger.error("Error getting free slots: %s", e)
        return {"error": f"Error getting free slots: {e}"}


def _save_draft_and_block_slot_internal(
    datetime: str,
    duration: int,
    reason: str,
    subject: str,
    body: str,
    to: str,
    in_reply_to: str = "",
    email_client=None,
) -> Dict[str, str | bool]:
    """Internal function for testing with dependency injection support.

    Args:
        datetime: ISO 8601 formatted datetime
        duration: Duration in minutes
        reason: Reason for blocking
        subject: Email subject
        body: Email body
        to: Recipient email
        in_reply_to: Message-ID for threading
        email_client: Optional email client for testing (internal use only)

    Returns:
        Dict with success status
    """
    try:
        success = calendar_manager.save_draft_and_block_slot(
            datetime,
            duration,
            reason,
            subject,
            body,
            to,
            in_reply_to=in_reply_to,
            email_client=email_client,
        )
        return {"success": success}
    except (ValueError, FileNotFoundError) as e:
        logger.error("Failed to save draft and block slot: %s", e)
        return {"error": f"Failed to save draft and block slot: {e}", "success": False}
    except Exception as e:
        logger.error("Unexpected error in save_draft_and_block_slot: %s", e)
        return {"error": f"Unexpected error: {e}", "success": False}


def save_draft_and_block_slot(
    datetime: Annotated[
        str,
        Field(
            description="ISO 8601 formatted datetime string representing the start time of the meeting. Must include timezone information. Format: YYYY-MM-DDTHH:MM:SS±HH:MM. Examples: 2025-12-15T14:00:00+01:00, 2025-12-15T14:00:00-05:00"
        ),
    ],
    duration: Annotated[
        int,
        Field(
            description="Duration of the meeting in minutes. Must be a positive integer. Minimum: 1, Maximum: 1440 (24 hours)",
            ge=1,
            le=1440,
        ),
    ],
    reason: Annotated[
        str,
        Field(
            description="Reason or description for blocking the calendar slot. This will be visible in your calendar entry. Should be descriptive (e.g., Meeting with Lisa about project update)"
        ),
    ],
    subject: Annotated[
        str,
        Field(
            description="Subject line of the confirmation email. Should be clear and descriptive (e.g., Meeting Confirmed - Project Update or Re: Meeting Request)"
        ),
    ],
    body: Annotated[
        str,
        Field(
            description="Content/body of the confirmation email. Should include meeting details, confirmation, and any additional information for the recipient"
        ),
    ],
    to: Annotated[
        str,
        Field(
            description="Email address of the recipient. Must be a valid email format (e.g., lisa@example.com, client@company.com)"
        ),
    ],
    in_reply_to: Annotated[
        str,
        Field(
            description="Optional Message-ID of the email this is replying to, for maintaining email conversation threads. Format: <original-message-id@example.com>. Examples: <CA+123456789@example.com>, <meeting-request-123@mail.server.com>. When provided, this creates a proper email thread by setting In-Reply-To and References headers",
            default="",
        ),
    ] = "",
) -> Dict[str, str | bool]:
    """Complete meeting scheduling workflow: atomically block a calendar slot AND save a confirmation email as a draft. Supports email threading with In-Reply-To headers for maintaining conversation context. Requires ISO 8601 datetime with timezone, duration in minutes, and email content. Returns success status with error handling. Perfect for confirming meetings naturally while maintaining proper email threading."""
    return _save_draft_and_block_slot_internal(
        datetime, duration, reason, subject, body, to, in_reply_to=in_reply_to
    )


__all__ = [
    "search_emails",
    "get_free_slots",
    "save_draft_and_block_slot",
    "_save_draft_and_block_slot_internal",
]
