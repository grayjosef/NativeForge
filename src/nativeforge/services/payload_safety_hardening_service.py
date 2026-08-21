"""Payload / rendering safety hardening helpers (Gate 06 / Block 18)."""

from __future__ import annotations

import re
from typing import Any

SCHEMA_VERSION = "nf_payload_safety_hardening_v1"

MAX_USER_MESSAGE_CHARS = 4000
MAX_REPORT_BLOCKERS = 50

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def sanitize_user_visible_text(text: str, *, max_chars: int = MAX_USER_MESSAGE_CHARS) -> str:
    """Neutralize HTML/script-like content for safe display / Slack preview.

    Does not claim XSS-proof for all browsers; React text nodes remain primary UI defense.
    """
    raw = text if isinstance(text, str) else str(text)
    raw = _CONTROL_RE.sub("", raw)
    # Escape angle brackets and backticks commonly used in injection / Slack mrkdwn
    escaped = (
        raw.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("`", "'")
    )
    if len(escaped) > max_chars:
        escaped = escaped[: max_chars - 1] + "…"
    return escaped


def escape_slack_mrkdwn_fragment(text: str) -> str:
    """Reduce Slack mrkdwn injection surface in free-text fragments."""
    t = sanitize_user_visible_text(text, max_chars=2000)
    # Break user/channel mention patterns
    t = t.replace("<@", "< @").replace("<!", "< !")
    return t


def harden_feedback_report_fields(report: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with sanitized message and bounded lists; never claim sent/persisted."""
    out = dict(report)
    out["user_message"] = sanitize_user_visible_text(str(out.get("user_message") or ""))
    blockers = list(out.get("current_blockers") or [])[:MAX_REPORT_BLOCKERS]
    out["current_blockers"] = [sanitize_user_visible_text(str(b), max_chars=200) for b in blockers]
    if out.get("slack_alert_status") == "sent":
        out["slack_alert_status"] = "not_run"
    out["persistence_claimed"] = False
    out["live_ingest_claimed"] = False
    out["payload_safety_schema"] = SCHEMA_VERSION
    return out


def assert_no_raw_script_payload(serialized: str) -> list[str]:
    fails: list[str] = []
    low = serialized.lower()
    if "<script" in low:
        fails.append("raw_script_tag")
    if "javascript:" in low:
        fails.append("javascript_uri")
    return fails


def payload_safety_demo() -> dict[str, Any]:
    sample = sanitize_user_visible_text("<script>alert(1)</script> hello `code`")
    return {
        "schema_version": SCHEMA_VERSION,
        "sample_sanitized": sample,
        "max_user_message_chars": MAX_USER_MESSAGE_CHARS,
        "contains_raw_script": "<script" in sample.lower(),
        "pen_test_passed_claimed": False,
    }
