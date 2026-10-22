from __future__ import annotations

from app.networking.gmail_sender import GmailSender
from app.networking.outreach_tracker import OutreachTracker


class ApprovalProcessor:
    """
    Processes manually approved outreach records.

    Workflow:

    APPROVED
        ↓
    SENDING
        ↓
    Gmail send
        ↓
    SENT

    If Gmail fails:

    SENDING
        ↓
    SEND_FAILED
    """

    def __init__(
        self,
        tracker: OutreachTracker | None = None,
        sender: GmailSender | None = None,
        user_id: str | None = None,
    ) -> None:

        if not user_id or "@" not in user_id.strip():
            raise ValueError(
                "A valid authenticated user_id is required for outreach processing."
            )

        self.user_id = user_id.strip().lower()
        self.tracker = (
            tracker
            if tracker is not None
            else OutreachTracker(user_id=self.user_id)
        )
        self.sender = sender

    @staticmethod
    def sender_user_context_missing(sender, user_id):
        # A preconfigured sender is allowed only when the trusted caller
        # has already supplied the authenticated user identity.
        return not user_id

    def process(
        self,
        run_id: str,
    ) -> dict:

        outreach = self.tracker.get_outreach(
            run_id
        )

        if not outreach:
            raise ValueError(
                f"Outreach record not found: {run_id}"
            )

        status = (
            outreach.get("Status")
            or ""
        ).upper()

        if status != "APPROVED":

            return {
                "run_id": run_id,
                "status": status,
                "action": "SKIPPED",
                "reason": (
                    "Only APPROVED "
                    "outreach can be processed."
                ),
            }

        if status == "APPROVED":

            self.tracker.mark_sending(
                run_id
            )

        gmail_message_id = None

        try:

            if self.sender is None:
                self.sender = GmailSender(user_id=self.user_id)

            result = self.sender.send(
                recipient=outreach["Contact Email"],
                subject=outreach["Subject"],
                body=outreach["Email Body"],
                status="APPROVED",
                attachment_path=outreach["CV Path"],
            )

            gmail_message_id = result.get(
                "id"
            )

            if not gmail_message_id:
                raise RuntimeError(
                    "Gmail API returned success "
                    "without a message ID."
                )

            sent_result = (
                self.tracker.mark_sent(
                    run_id,
                    gmail_message_id,
                )
            )

            return {
                "run_id": run_id,
                "status": "SENT",
                "action": "SENT",
                "gmail_message_id": (
                    gmail_message_id
                ),
                "sent_at": sent_result[
                    "sent_at"
                ],
            }

        except Exception as exc:

            # Gmail has confirmed acceptance if a message ID was returned.
            # A later tracker error must not turn that delivery into a
            # retryable SEND_FAILED record.
            if gmail_message_id:
                return {
                    "run_id": run_id,
                    "status": "SENT_TRACKING_FAILED",
                    "action": "TRACKING_FAILED",
                    "gmail_message_id": gmail_message_id,
                    "error_message": (
                        "Gmail accepted the message, but JobPilot could "
                        "not confirm the tracker update: "
                        f"{exc}"
                    ),
                }

            failed_result = (
                self.tracker.mark_send_failed(
                    run_id,
                    str(exc),
                )
            )

            return {
                "run_id": run_id,
                "status": "SEND_FAILED",
                "action": "FAILED",
                "error_message": str(exc),
                "retry_count": (
                    failed_result[
                        "retry_count"
                    ]
                ),
            }

def process_approval(
    run_id: str,
) -> dict:
    raise RuntimeError(
        "Unauthenticated approval processing is disabled. "
        "Use an authenticated workflow with a user-specific "
        "ApprovalProcessor and OutreachTracker."
    )