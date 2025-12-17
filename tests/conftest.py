"""
Pytest fixtures for integration tests.
"""

from datetime import datetime, time
from pathlib import Path
from typing import Dict, List, Tuple

import pytest

from meeting_scheduler_mcp.calendar import (
    BlockedTime,
    Calendar,
    CalendarManager,
    Schedule,
    TimeSlot,
    Weekday,
    WeeklyAvailability,
)


class MockEmailClient:
    """Mock implementation of EmailClientProtocol for testing with realistic behavior."""

    def __init__(self):
        self._connected = False
        self._emails: Dict[int, Dict[str, str]] = {}  # email_id -> email data
        self._next_email_id = 1

    def __enter__(self) -> "MockEmailClient":
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()

    def connect(self) -> None:
        """Connect to the email server (mock)."""
        self._connected = True

    def save_draft(
        self, subject: str, body: str, to: str, in_reply_to: str = ""
    ) -> bool:
        """Save an email as a draft (mock)."""
        if not self._connected:
            raise ConnectionError("Not connected to email server")

        email_id = self._next_email_id
        self._next_email_id += 1

        self._emails[email_id] = {
            "subject": subject,
            "body": body,
            "to": to,
            "from": "mock@example.com",
            "date": "Mon, 15 Dec 2025 10:00:00 +0100",
            "message_id": f"<{email_id}.mock@example.com>",
            "in_reply_to": in_reply_to,
            "references": in_reply_to,
        }
        return True

    def search_emails(
        self, mailbox: str = "INBOX", criteria: str = "UNSEEN"
    ) -> list[bytes]:
        """Search emails in a mailbox (mock)."""
        if not self._connected:
            raise ConnectionError("Not connected to email server")

        # For mock: return all email IDs as bytes (matching IMAP behavior)
        return [str(email_id).encode() for email_id in self._emails.keys()]

    def get_email_content(
        self, email_id: int, mailbox: str = "INBOX"
    ) -> Tuple[str, str]:
        """Get email subject and body (mock)."""
        if not self._connected:
            raise ConnectionError("Not connected to email server")

        if email_id not in self._emails:
            raise ConnectionError(f"Email {email_id} not found")

        email = self._emails[email_id]
        return email["subject"], email["body"]

    def get_email_metadata(
        self, email_id: int, mailbox: str = "INBOX"
    ) -> Dict[str, str]:
        """Get email metadata including threading headers (mock)."""
        if not self._connected:
            raise ConnectionError("Not connected to email server")

        if email_id not in self._emails:
            raise ConnectionError(f"Email {email_id} not found")

        return self._emails[email_id].copy()

    def close(self) -> None:
        """Close the connection to the email server (mock)."""
        self._connected = False

    # Private assertion helpers for testing
    def _get_drafts(self) -> List[Dict[str, str]]:
        """Get all saved emails for test assertions."""
        return list(self._emails.values())

    def _get_draft_count(self) -> int:
        """Get the number of saved emails for test assertions."""
        return len(self._emails)

    def _get_email_by_id(self, email_id: int) -> Dict[str, str] | None:
        """Get a specific email by ID for test assertions."""
        return self._emails.get(email_id)

    def _find_drafts_to(self, recipient: str) -> List[Dict[str, str]]:
        """Find all drafts to a specific recipient for test assertions."""
        return [e for e in self._emails.values() if e["to"] == recipient]

    def _find_drafts_with_subject(self, subject: str) -> List[Dict[str, str]]:
        """Find all drafts with a specific subject for test assertions."""
        return [e for e in self._emails.values() if subject in e["subject"]]

    def _clear(self) -> None:
        """Clear all emails for test cleanup."""
        self._emails.clear()
        self._next_email_id = 1


@pytest.fixture
def mock_email_client() -> MockEmailClient:
    """Fixture providing a mock email client for testing.

    Returns:
        MockEmailClient: A fresh mock email client instance
    """
    return MockEmailClient()


@pytest.fixture
def temp_calendar(tmp_path: Path) -> Tuple[Path, CalendarManager]:
    """Fixture providing a temporary calendar YAML file and CalendarManager instance.

    Args:
        tmp_path: pytest's built-in tmp_path fixture

    Returns:
        Tuple[Path, CalendarManager]: Tuple containing the path to the temporary
        calendar file and a configured CalendarManager instance
    """
    # Create a temporary calendar file
    calendar_path = tmp_path / "test_calendar.yaml"

    # Create CalendarManager with the temporary file
    calendar_manager = CalendarManager(str(calendar_path))

    return calendar_path, calendar_manager


class InMemoryCalendarStore:
    """In-memory calendar store for testing without file I/O.

    Implements the same interface as CalendarStore but stores calendar state
    entirely in memory. Useful for unit tests that don't need file persistence.
    """

    def __init__(self, calendar: Calendar | None = None):
        """Initialize in-memory store with optional calendar.

        Args:
            calendar: Optional Calendar instance. If not provided, creates
                a default calendar with Mon-Fri 09:00-17:00 availability
                in Europe/Berlin timezone with German holidays.
        """
        self._calendar = calendar or Calendar(
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
                        slots=[TimeSlot(start=time(9, 0), end=time(17, 0))],
                    )
                ],
            ),
            blocked=[],
        )

    def load(self) -> Calendar:
        """Load calendar from memory.

        Returns:
            Calendar: The currently stored calendar instance.
        """
        return self._calendar

    def save(self, calendar: Calendar) -> None:
        """Save calendar to memory.

        Args:
            calendar: Calendar instance to store.
        """
        self._calendar = calendar

    def add_blocked(
        self,
        dt: datetime,
        duration: int | None = None,
        until: datetime | None = None,
        reason: str | None = None,
    ) -> None:
        """Add a blocked time to the calendar.

        Args:
            dt: Start datetime of the blocked period.
            duration: Duration in minutes (mutually exclusive with until).
            until: End datetime (mutually exclusive with duration).
            reason: Optional reason for the block.
        """
        blocked = BlockedTime(
            datetime=dt.isoformat(),
            duration=duration,
            until=until.isoformat() if until else None,
            reason=reason,
        )
        self._calendar.blocked.append(blocked)


@pytest.fixture
def in_memory_calendar_store() -> InMemoryCalendarStore:
    """Fixture providing an in-memory calendar store for testing.

    Use this fixture for unit tests that need calendar state isolation
    without file I/O overhead. Each test gets a fresh store with a default
    calendar configuration.

    Returns:
        InMemoryCalendarStore: A fresh in-memory calendar store instance
            with default calendar configuration (Mon-Fri 09:00-17:00,
            Europe/Berlin timezone, German holidays).

    Example:
        def test_add_blocked_slot(in_memory_calendar_store):
            from datetime import datetime, timedelta
            store = in_memory_calendar_store
            start = datetime.now()
            store.add_blocked(start, duration=60, reason="Meeting")
            calendar = store.load()
            assert len(calendar.blocked) == 1
    """
    return InMemoryCalendarStore()
