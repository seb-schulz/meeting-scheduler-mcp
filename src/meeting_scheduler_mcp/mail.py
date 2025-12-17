"""
IMAP client for the meeting scheduler.
Uses .env for configuration and provides email operation functions.
"""

import email
import email.message
import imaplib
import logging
import os
import ssl
import time
from ssl import SSLError
from typing import Dict, List, Protocol, Tuple, Union

from dotenv import load_dotenv

# Load .env file (only relevant in production)
load_dotenv()

logger = logging.getLogger(__name__)


class EmailClientProtocol(Protocol):
    """Protocol defining the interface for email client operations."""

    def __enter__(self) -> "EmailClientProtocol": ...

    """Context manager entry."""

    def __exit__(self, exc_type, exc_val, exc_tb) -> None: ...

    """Context manager exit."""

    def connect(self) -> None: ...

    """Connect to the email server."""

    def save_draft(
        self, subject: str, body: str, to: str, in_reply_to: str = ""
    ) -> bool: ...

    """Save an email as a draft."""

    def search_emails(
        self, mailbox: str = "INBOX", criteria: str = "UNSEEN"
    ) -> List[int]: ...

    """Search emails in a mailbox."""

    def get_email_content(
        self, email_id: int, mailbox: str = "INBOX"
    ) -> Tuple[str, str]: ...

    """Get email subject and body."""

    def get_email_metadata(
        self, email_id: int, mailbox: str = "INBOX"
    ) -> Dict[str, str]: ...

    """Get email metadata including threading headers."""

    def close(self) -> None: ...

    """Close the connection to the email server."""


class IMAPEmailClient:
    """Production implementation of EmailClientProtocol using IMAP."""

    def __init__(self):
        self._imap: Union[imaplib.IMAP4, imaplib.IMAP4_SSL, None] = None

    def __enter__(self) -> "IMAPEmailClient":
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()

    def connect(self) -> None:
        """Connect to the IMAP server."""
        host = os.getenv("IMAP_HOST")
        user = os.getenv("IMAP_USER")
        password = os.getenv("IMAP_PASSWORD")
        port = os.getenv("IMAP_PORT", "993")
        use_ssl = os.getenv("IMAP_USE_SSL", "true")
        use_starttls = os.getenv("IMAP_USE_STARTTLS", "false")
        verify_ssl = os.getenv("IMAP_VERIFY_SSL", "true")

        # Handle None values and convert to boolean
        use_ssl = use_ssl.lower() == "true" if use_ssl else True
        use_starttls = use_starttls.lower() == "true" if use_starttls else False
        verify_ssl = verify_ssl.lower() == "true" if verify_ssl else True

        if host is None or user is None or password is None:
            raise ValueError("IMAP configuration in .env incomplete")

        try:
            # Convert port to integer
            port_int = int(port)

            # Create SSL context if needed
            ssl_context = None
            if use_ssl or use_starttls:
                ssl_context = ssl.create_default_context()
                if not verify_ssl:
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE

            # Connect using appropriate method
            if use_starttls:
                # Use IMAP4 with STARTTLS
                imap = imaplib.IMAP4(host, port_int)
                imap.starttls(ssl_context=ssl_context)
            else:
                # Use IMAP4_SSL (direct SSL/TLS)
                imap = imaplib.IMAP4_SSL(host, port_int, ssl_context=ssl_context)

            imap.login(user, password)
            self._imap = imap
        except imaplib.IMAP4.error as e:
            raise ConnectionError(f"IMAP connection failed: {e}") from e
        except ValueError as e:
            raise ValueError(f"Invalid IMAP port: {e}") from e
        except (OSError, SSLError) as e:
            raise ConnectionError(f"Network error: {e}") from e
        except Exception as e:
            raise ConnectionError(f"IMAP connection failed: {e}") from e

    def save_draft(
        self, subject: str, body: str, to: str, in_reply_to: str = ""
    ) -> bool:
        """Save an email as a draft using IMAP."""
        if self._imap is None:
            raise ConnectionError("Not connected to email server")

        try:
            # Get drafts folder from environment variable
            drafts_folder = os.getenv("IMAP_DRAFT_FOLDER", "INBOX.Drafts")

            # Ensure the folder exists
            try:
                status, _ = self._imap.select(drafts_folder)
                if status != "OK":
                    # Folder doesn't exist, try to create it
                    status, _ = self._imap.create(drafts_folder)
                    if status != "OK":
                        logger.error(
                            "Failed to create or access folder: %s", drafts_folder
                        )
                        return False
                    # Successfully created, select it
                    self._imap.select(drafts_folder)
            except (ConnectionError, OSError) as e:
                logger.error("Error ensuring folder exists: %s", e)
                return False
            except Exception as e:
                logger.error("Unexpected error ensuring folder exists: %s", e)
                return False

            # Create the email
            message = email.message.EmailMessage()
            from_address = os.getenv("IMAP_FROM", os.getenv("IMAP_USER"))
            message["From"] = from_address
            message["To"] = to
            message["Subject"] = subject

            # Add email threading headers if provided
            if in_reply_to:
                message["In-Reply-To"] = in_reply_to
                # Generate References header for proper email threading
                message["References"] = in_reply_to

            message.set_content(body)

            # Save the email
            status, _ = self._imap.append(
                drafts_folder,
                "",
                imaplib.Time2Internaldate(time.time()),
                message.as_bytes(),
            )
            return status == "OK"

        except (ConnectionError, OSError) as e:
            logger.error("Error saving draft: %s", e)
            return False
        except Exception as e:
            logger.error("Unexpected error saving draft: %s", e)
            return False

    def search_emails(
        self, mailbox: str = "INBOX", criteria: str = "UNSEEN"
    ) -> List[int]:
        """Search emails in a mailbox."""
        if self._imap is None:
            raise ConnectionError("Not connected to email server")

        status, messages = self._imap.select(mailbox)
        if status != "OK":
            raise ConnectionError(f"Cannot select mailbox {mailbox}")

        status, email_ids = self._imap.search(None, criteria)
        if status != "OK":
            raise ConnectionError("Email search failed")

        return email_ids[0].split()

    def get_email_content(
        self, email_id: int, mailbox: str = "INBOX"
    ) -> Tuple[str, str]:
        """Get email subject and body."""
        if self._imap is None:
            raise ConnectionError("Not connected to email server")

        status, data = self._imap.fetch(str(email_id), "(RFC822)")
        if status != "OK":
            raise ConnectionError(f"Cannot retrieve email {email_id}")

        # Type safety: Ensure data has the expected structure
        if not data or not data[0] or len(data[0]) < 2:
            raise ConnectionError(f"Invalid email data structure for email {email_id}")

        raw_email = data[0][1]
        if not isinstance(raw_email, bytes):
            raise ConnectionError(
                f"Expected bytes for email data, got {type(raw_email)}"
            )

        email_message = email.message_from_bytes(raw_email)

        subject = email_message.get("subject", "")
        body = ""

        if email_message.is_multipart():
            for part in email_message.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    payload = part.get_payload(decode=True)
                    body = (
                        payload.decode() if isinstance(payload, bytes) else str(payload)
                    )
                    break
        else:
            payload = email_message.get_payload(decode=True)
            body = payload.decode() if isinstance(payload, bytes) else str(payload)

        return subject, body

    def get_email_metadata(
        self, email_id: int, mailbox: str = "INBOX"
    ) -> Dict[str, str]:
        """Get email metadata including threading headers."""
        if self._imap is None:
            raise ConnectionError("Not connected to email server")

        status, data = self._imap.fetch(str(email_id), "(RFC822)")
        if status != "OK":
            raise ConnectionError(f"Cannot retrieve email {email_id}")

        # Type safety: Ensure data has the expected structure
        if not data or not data[0] or len(data[0]) < 2:
            raise ConnectionError(f"Invalid email data structure for email {email_id}")

        raw_email = data[0][1]
        if not isinstance(raw_email, bytes):
            raise ConnectionError(
                f"Expected bytes for email data, got {type(raw_email)}"
            )

        email_message = email.message_from_bytes(raw_email)

        # Extract metadata
        metadata = {
            "subject": email_message.get("subject", ""),
            "from": email_message.get("from", ""),
            "to": email_message.get("to", ""),
            "date": email_message.get("date", ""),
            "message_id": email_message.get("Message-ID", ""),
            "in_reply_to": email_message.get("In-Reply-To", ""),
            "references": email_message.get("References", ""),
        }

        # Extract body content
        body = ""
        if email_message.is_multipart():
            for part in email_message.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    payload = part.get_payload(decode=True)
                    body = (
                        payload.decode() if isinstance(payload, bytes) else str(payload)
                    )
                    break
        else:
            payload = email_message.get_payload(decode=True)
            body = payload.decode() if isinstance(payload, bytes) else str(payload)

        metadata["body"] = body

        return metadata

    def close(self) -> None:
        """Close the IMAP connection."""
        if self._imap is not None:
            try:
                self._imap.close()
                self._imap.logout()
            except (ConnectionError, OSError):
                pass
            self._imap = None
