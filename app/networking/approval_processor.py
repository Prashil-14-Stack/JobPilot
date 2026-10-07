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
    ) -> None:

        self.tracker = (
            tracker
            or OutreachTracker()
        )

        self.sender = sender

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

        if status not in (
            "APPROVED",
            "SEND_FAILED",
        ):

            return {
                "run_id": run_id,
                "status": status,
                "action": "SKIPPED",
                "reason": (
                    "Only APPROVED or SEND_FAILED "
                    "outreach can be processed."
                ),
            }

        if status == "APPROVED":

            self.tracker.mark_sending(
                run_id
            )

        elif status == "SEND_FAILED":

            self.tracker.mark_retrying(
                run_id
            )

        try:

            if self.sender is None:
                self.sender = GmailSender()

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

    processor = ApprovalProcessor()

    return processor.process(
        run_id
    )