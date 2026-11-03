"""Optional Slack-compatible webhook notifications for index updates."""

from __future__ import annotations

import time

import requests

from .logging_setup import logger


class Notifier:
    def __init__(self, webhook_url: str | None) -> None:
        self.webhook_url = webhook_url
        if webhook_url:
            logger.info("Update notifications enabled")

    def send(
        self,
        action: str,
        ref: str,
        success: bool,
        chunks_before: int | None = None,
        chunks_after: int | None = None,
        error: str | None = None,
    ) -> None:
        if not self.webhook_url:
            return
        title = "Index updated" if success else "Index update failed"
        text = f"{action} on {ref}" + (f": {error}" if error else "")
        fields = []
        if chunks_before is not None:
            fields.append({"title": "Chunks before", "value": str(chunks_before), "short": True})
        if chunks_after is not None:
            fields.append({"title": "Chunks after", "value": str(chunks_after), "short": True})
        message = {
            "text": title,
            "attachments": [{"color": "good" if success else "danger", "title": title, "text": text, "fields": fields, "ts": int(time.time())}],
        }
        try:
            requests.post(self.webhook_url, json=message, timeout=10).raise_for_status()
        except requests.RequestException as exc:
            logger.error("Notification failed: %s", exc)
