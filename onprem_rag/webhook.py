"""Parse index-update webhooks.

Two formats are accepted: a plain JSON object ``{"action": ..., "ref": ...}`` and
the chat-notification text MediaWiki's notification extensions post, e.g.
``user) edited [Page](<https://wiki/Page>)``, from which the action and page URL
are recovered.
"""

from __future__ import annotations

import re

_PATTERNS = {
    "edit": re.compile(r"\) edited \[.*?\]\(<(.*?)>\)"),
    "create": re.compile(r"\) created \[.*?\]\(<(.*?)>\)"),
    "delete": re.compile(r"\) deleted \[.*?\]\(<(.*?)>\)"),
}


def parse_notification_text(content: str) -> tuple[str, str]:
    for action, pattern in _PATTERNS.items():
        match = pattern.search(content or "")
        if match:
            return action, match.group(1)
    return "", ""


def parse_webhook(payload: dict) -> tuple[str, str]:
    action = str(payload.get("action", "")).lower()
    ref = payload.get("ref") or payload.get("url") or ""
    if action in ("edit", "create", "delete") and ref:
        return action, str(ref)
    return parse_notification_text(str(payload.get("content", "")))
