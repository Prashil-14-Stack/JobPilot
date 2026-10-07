from __future__ import annotations

import sys

from app.networking.gmail_sender import GmailSender
from app.networking.outreach_tracker import OutreachTracker


def send_outreach(
    run_id: str,
    dry_run: bool = False,
) -> dict:

    tracker = OutreachTracker()

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

    sender = GmailSender()

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

    encoded_message = (
        sender.build_raw_message(
            message
        )
    )

    result = (
        sender.service
        .users()
        .messages()
        .send(
            userId="me",
            body={
                "raw": encoded_message
            },
        )
        .execute()
    )

    tracker.update_status(
        run_id,
        "SENT",
    )

    return {
        "run_id": run_id,
        "status": "SENT",
        "gmail_message_id": result.get(
            "id"
        ),
    }


if __name__ == "__main__":

    if len(sys.argv) not in (2, 3):

        raise SystemExit(
            "Usage: "
            "python -m app.networking.send_outreach "
            "<run_id> [--dry-run]"
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