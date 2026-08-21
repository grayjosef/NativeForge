"""Slack alert plumbing for feedback reports (Campaign Block 14).

Dry-run safe. Never claims sent without configured webhook + successful send.
"""

from __future__ import annotations

import json
import os
from typing import Any

from nativeforge.services.feedback_report_contract_service import (
    feedback_report_invariant_failures,
)
from nativeforge.services.payload_safety_hardening_service import (
    escape_slack_mrkdwn_fragment,
)

SCHEMA_VERSION = "nf_feedback_slack_alert_service_v1"
ENV_WEBHOOK = "NATIVEFORGE_FEEDBACK_SLACK_WEBHOOK_URL"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def format_slack_message(report: dict[str, Any]) -> dict[str, Any]:
    sev = report.get("severity") or "medium"
    safe_msg = escape_slack_mrkdwn_fragment(str(report.get("user_message") or ""))
    safe_blockers = ", ".join(
        escape_slack_mrkdwn_fragment(str(b))
        for b in (report.get("current_blockers") or [])
    ) or "none"
    return _json_safe(
        {
            "text": (
                f"[NativeForge feedback/{sev}] "
                f"{report.get('report_type')} on {report.get('route')} "
                f"surface={report.get('surface_id')}"
            ),
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*NativeForge customer feedback*\n"
                            f"Type: `{report.get('report_type')}` | "
                            f"Severity: `{sev}`\n"
                            f"Route: `{report.get('route')}` | "
                            f"Surface: `{report.get('surface_id')}` | "
                            f"Dialog: `{report.get('dialog_id') or 'n/a'}`\n"
                            f"Org: `{report.get('organization_profile_id') or 'n/a'}` | "
                            f"Opp: `{report.get('opportunity_id') or 'n/a'}`\n"
                            f"Data mode: `{report.get('data_mode')}`\n"
                            f"Message: {safe_msg}\n"
                            f"Blockers: {safe_blockers}\n"
                            f"Claim flags: `{json.dumps(report.get('current_claim_flags') or {})}`"
                        ),
                    },
                }
            ],
        }
    )


def send_feedback_slack_alert(
    report: dict[str, Any],
    *,
    force_dry_run: bool = True,
) -> dict[str, Any]:
    """Return alert result. Default dry-run; never fake sent."""
    fails = feedback_report_invariant_failures(report)
    webhook = os.environ.get(ENV_WEBHOOK, "").strip()
    payload = format_slack_message(report)

    if force_dry_run or not webhook:
        status = "dry_run" if force_dry_run else "not_configured"
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "feedback_report_id": report.get("feedback_report_id"),
                "slack_alert_status": status,
                "sent": False,
                "webhook_configured": bool(webhook),
                "force_dry_run": force_dry_run,
                "message_preview": payload,
                "invariant_failures": fails,
                "note": (
                    "Slack not sent — dry-run or webhook not configured. "
                    "Do not claim live delivery."
                ),
            }
        )

    # Live send path exists only when webhook set AND force_dry_run=False.
    # Gate 04 default remains dry-run; network send is opt-in and still honest.
    try:
        import urllib.request

        req = urllib.request.Request(
            webhook,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
            ok = 200 <= getattr(resp, "status", 0) < 300
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "feedback_report_id": report.get("feedback_report_id"),
                "slack_alert_status": "sent" if ok else "failed",
                "sent": bool(ok),
                "webhook_configured": True,
                "force_dry_run": False,
                "message_preview": payload,
                "invariant_failures": fails,
            }
        )
    except Exception as exc:  # noqa: BLE001 — capture send failure honestly
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "feedback_report_id": report.get("feedback_report_id"),
                "slack_alert_status": "failed",
                "sent": False,
                "webhook_configured": True,
                "force_dry_run": False,
                "message_preview": payload,
                "error": str(exc)[:200],
                "invariant_failures": fails,
            }
        )


def attach_slack_status_to_report(
    report: dict[str, Any],
    *,
    force_dry_run: bool = True,
) -> dict[str, Any]:
    result = send_feedback_slack_alert(report, force_dry_run=force_dry_run)
    out = dict(report)
    out["slack_alert_status"] = result.get("slack_alert_status")
    out["slack_alert_result"] = result
    # Contract still forbids claiming sent in persistence-less demos unless truly sent
    if out.get("slack_alert_status") == "sent" and not result.get("sent"):
        out["slack_alert_status"] = "failed"
    return _json_safe(out)
