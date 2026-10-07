from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CREDENTIALS_PATH = (
    PROJECT_ROOT / "credentials.json"
)

TOKEN_PATH = (
    PROJECT_ROOT / "token.json"
)


# ============================================================
# GMAIL PERMISSION
# ============================================================

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send"
]


class GmailSender:

    def __init__(self):

        self.service = self._authenticate()

    # ========================================================
    # AUTHENTICATION
    # ========================================================

    def _authenticate(self):

        credentials = None

        if TOKEN_PATH.exists():

            credentials = Credentials.from_authorized_user_file(
                TOKEN_PATH,
                SCOPES
            )

        if credentials and credentials.expired:

            if credentials.refresh_token:

                credentials.refresh(
                    Request()
                )

            else:

                credentials = None

        if not credentials:

            if not CREDENTIALS_PATH.exists():

                raise FileNotFoundError(
                    f"Google OAuth credentials not found: "
                    f"{CREDENTIALS_PATH}"
                )

            flow = (
                InstalledAppFlow
                .from_client_secrets_file(
                    CREDENTIALS_PATH,
                    SCOPES
                )
            )

            credentials = flow.run_local_server(
                port=0
            )

            TOKEN_PATH.write_text(
                credentials.to_json(),
                encoding="utf-8"
            )

        return build(
            "gmail",
            "v1",
            credentials=credentials
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