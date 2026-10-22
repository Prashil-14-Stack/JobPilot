from __future__ import annotations

import sys

from app.networking.gmail_sender import GmailSender
from app.networking.outreach_tracker import OutreachTracker
from app.networking.approval_processor import ApprovalProcessor


def send_outreach(
    run_id: str,
    dry_run: bool = False,
    user_id: str | None = None,
) -> dict:

    if not user_id:
        raise ValueError(
            "A verified user_id is required to send outreach. "
            "Use the authenticated JobPilot UI or provide the "
            "verified account identity from a trusted caller."
        )

    tracker = OutreachTracker(user_id=user_id)

    outreach = tracker.get_outreach(
        run_id
    )

    if not outreach:
        raise ValueError(
            f"Outreach record not found: {run_id}"
        )

    status = outreach.get(
        "Status"
    )

    GmailSender.validate_send_status(
        status
    )

    sender = GmailSender(user_id=user_id)

    message = sender.build_message(
        recipient=outreach["Contact Email"],
        subject=outreach["Subject"],
        body=outreach["Email Body"],
        attachment_path=outreach["CV Path"],
    )

    if dry_run:

        attachment = (
            list(
                message.iter_attachments()
            )[0]
            if list(
                message.iter_attachments()
            )
            else None
        )

        return {
            "run_id": run_id,
            "status": status,
            "dry_run": True,
            "recipient": message["To"],
            "subject": message["Subject"],
            "content_type": message.get_content_type(),
            "attachment": (
                attachment.get_filename()
                if attachment
                else None
            ),
        }

    processor = ApprovalProcessor(
        tracker=tracker,
        sender=sender,
        user_id=user_id,
    )

    return processor.process(run_id)


if __name__ == "__main__":

    if len(sys.argv) not in (2, 3):

        raise SystemExit(
            "Usage: "
            "python -m app.networking.send_outreach "
            "<run_id> [--dry-run]"
        )

    raise SystemExit(
        "Direct CLI sending is disabled because it has no authenticated "
        "JobPilot user context. Use the authenticated UI instead."
    )

    run_id = sys.argv[1]

    dry_run = (
        len(sys.argv) == 3
        and sys.argv[2] == "--dry-run"
    )

    if len(sys.argv) == 3 and not dry_run:

        raise SystemExit(
            "Unknown argument. "
            "Use --dry-run if a dry run is intended."
        )

    result = send_outreach(
        run_id,
        dry_run=dry_run,
    )

    print(result)