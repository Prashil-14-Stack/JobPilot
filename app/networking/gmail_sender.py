from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from googleapiclient.discovery import build

# ============================================================
# GMAIL PERMISSION
# ============================================================

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send"
]



class GmailSender:

    def __init__(self, user_id: str | None = None):
        if not user_id or "@" not in user_id:
            raise ValueError(
                "A verified authenticated user_id is required for Gmail access."
            )

        self.user_id = user_id.strip().lower()

        from app.networking.gmail_oauth import gmail_token_path

        self.token_path = gmail_token_path(self.user_id)
        self.service = self._authenticate()

    # ========================================================
    # AUTHENTICATION
    # ========================================================

    def _authenticate(self):
        if not self.token_path.exists():
            raise FileNotFoundError(
                "Gmail is not connected for this account. "
                "Use Connect Gmail in the JobPilot sidebar first."
            )

        credentials = Credentials.from_authorized_user_file(
            str(self.token_path),
            SCOPES,
        )

        if not credentials.valid:
            if credentials.expired and credentials.refresh_token:
                try:
                    credentials.refresh(Request())
                except Exception as exc:
                    from google.auth.exceptions import RefreshError

                    if isinstance(exc, RefreshError):
                        raise PermissionError(
                            "Gmail authorization has expired or been revoked. "
                            "Reconnect Gmail from the JobPilot sidebar."
                        ) from exc
                    raise

                # Persist refreshed credentials for this user.
                self.token_path.write_text(
                    credentials.to_json(),
                    encoding="utf-8",
                )
            else:
                raise PermissionError(
                    "Gmail credentials are invalid or cannot be refreshed. "
                    "Reconnect Gmail from the JobPilot sidebar."
                )

        return build(
            "gmail",
            "v1",
            credentials=credentials,
        )

    # ========================================================
    # APPROVAL + DUPLICATE-SEND GATE
    # ========================================================

    @staticmethod
    def validate_send_status(
        status: str
    ):

        if status == "SENT":

            raise PermissionError(
                "This outreach has already been sent."
            )

        if status != "APPROVED":

            raise PermissionError(
                "Only APPROVED outreach can be sent."
            )
    @staticmethod
    def build_message(
        *,
        recipient: str,
        subject: str,
        body: str,
        attachment_path: str | Path | None = None,
    ) -> EmailMessage:

        message = EmailMessage()

        message["To"] = recipient
        message["Subject"] = subject

        message.set_content(
            body
        )

        if attachment_path:

            attachment = Path(
                attachment_path
            )

            if not attachment.exists():

                raise FileNotFoundError(
                    f"Attachment not found: "
                    f"{attachment}"
                )

            file_data = attachment.read_bytes()

            message.add_attachment(
                file_data,
                maintype="application",
                subtype="pdf",
                filename=attachment.name,
            )

        return message

    @staticmethod
    def build_raw_message(
        message: EmailMessage,
    ) -> str:

        return (
            __import__("base64")
            .urlsafe_b64encode(
                message.as_bytes()
            )
            .decode()
        )
    # ========================================================
    # SEND
    # ========================================================

    def send(
        self,
        *,
        recipient: str,
        subject: str,
        body: str,
        status: str,
        attachment_path: str | Path | None = None,
    ):

        self.validate_send_status(
            status
        )

        message = self.build_message(
            recipient=recipient,
            subject=subject,
            body=body,
            attachment_path=attachment_path,
        )

        encoded_message = (
            self.build_raw_message(
                message
            )
        )

        result = (
            self.service
            .users()
            .messages()
            .send(
                userId="me",
                body={
                    "raw": encoded_message
                }
            )
            .execute()
        )

        return result