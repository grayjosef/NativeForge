"""Slack alert plumbing for feedback reports.

Default mode is dry_run. Never logs webhook URLs. Never claims sent without
a successful live POST.
"""

from __future__ import annotations

import json
import logging
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
ENV_MODE = "NATIVEFORGE_FEEDBACK_ALERT_MODE"
ENV_CHANNEL = "NATIVEFORGE_FEEDBACK_ALERT_CHANNEL_LABEL"
ALERT_MODES = frozenset({"off", "dry_run", "live"})
LOGGER = logging.getLogger("nativeforge.feedback_alert")


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def resolve_alert_mode(*, force_dry_run: bool | None = None) -> str:
    if force_dry_run is True:
        return "dry_run"
    if force_dry_run is False:
        return "live"
    raw = os.environ.get(ENV_MODE, "dry_run").strip().lower()
    if raw not in ALERT_MODES:
        return "dry_run"
    return raw


def _safe_ctx(report: dict[str, Any], key: str) -> str:
    ctx = report.get("client_context") or {}
    if not isinstance(ctx, dict):
        return "n/a"
    val = ctx.get(key)
    if val is None or val == "":
        return "n/a"
    text = escape_slack_mrkdwn_fragment(str(val)[:200])
    lowered = text.lower()
    if "webhook" in lowered or "token" in lowered or "secret" in lowered:
        return "[redacted]"
    return text


def format_slack_message(report: dict[str, Any]) -> dict[str, Any]:
    sev = report.get("severity") or "medium"
    safe_msg = escape_slack_mrkdwn_fragment(str(report.get("user_message") or ""))
    env = escape_slack_mrkdwn_fragment(os.environ.get("NF_APP_ENV", "local"))
    channel = escape_slack_mrkdwn_fragment(
        os.environ.get(ENV_CHANNEL, "unset") or "unset"
    )
    org_name = _safe_ctx(report, "org_display_name")
    if org_name == "n/a":
        org_name = escape_slack_mrkdwn_fragment(
            str(report.get("organization_profile_id") or "n/a")
        )
    email = _safe_ctx(report, "contact_email")
    return _json_safe(
        {
            "text": (
                f"[NativeForge feedback/{sev}] "
                f"{report.get('report_type')} on {report.get('route')}"
            ),
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*NativeForge customer feedback*\n"
                            f"Timestamp: `{report.get('reported_at')}` | "
                            f"Env: `{env}` | Channel: `{channel}`\n"
                            f"Type: `{report.get('report_type')}` | "
                            f"Severity: `{sev}`\n"
                            f"Org: `{org_name}` | Contact: `{email}`\n"
                            f"Route: `{report.get('route')}` | "
                            f"Source: `{report.get('surface_id')}`\n"
                            f"Ref: `{report.get('feedback_report_id')}`\n"
                            f"Summary: {safe_msg}"
                        ),
                    },
                }
            ],
        }
    )


def _audit(
    *,
    status: str,
    sent: bool,
    report: dict[str, Any],
    mode: str,
    webhook_configured: bool,
) -> None:
    LOGGER.info(
        "feedback_alert id=%s mode=%s status=%s sent=%s webhook_configured=%s",
        report.get("feedback_report_id"),
        mode,
        status,
        sent,
        webhook_configured,
    )


def send_feedback_slack_alert(
    report: dict[str, Any],
    *,
    force_dry_run: bool | None = True,
) -> dict[str, Any]:
    """Return alert result. Default dry-run; never fake sent."""
    fails = feedback_report_invariant_failures(report)
    webhook = os.environ.get(ENV_WEBHOOK, "").strip()
    payload = format_slack_message(report)
    mode = resolve_alert_mode(force_dry_run=force_dry_run)
    configured = bool(webhook)

    def _result(status: str, sent: bool, extra: dict[str, Any] | None = None) -> dict:
        body = {
            "schema_version": SCHEMA_VERSION,
            "feedback_report_id": report.get("feedback_report_id"),
            "slack_alert_status": status,
            "sent": sent,
            "webhook_configured": configured,
            "alert_mode": mode,
            "force_dry_run": force_dry_run,
            "message_preview": payload,
            "invariant_failures": fails,
        }
        if extra:
            body.update(extra)
        dumped_meta = json.dumps(
            {k: v for k, v in body.items() if k != "message_preview"}
        )
        if webhook and webhook in dumped_meta:
            raise RuntimeError("webhook leaked into alert result")
        _audit(
            status=status,
            sent=sent,
            report=report,
            mode=mode,
            webhook_configured=configured,
        )
        return _json_safe(body)

    if mode == "off":
        return _result(
            "off",
            False,
            {"note": "Alert mode off. Slack not sent."},
        )

    if mode == "dry_run":
        return _result(
            "dry_run",
            False,
            {
                "note": (
                    "Slack not sent — dry_run. Payload preview is local only. "
                    "Do not claim live delivery."
                ),
            },
        )

    # live
    if not webhook:
        return _result(
            "config_error",
            False,
            {
                "note": (
                    "Live mode requires NATIVEFORGE_FEEDBACK_SLACK_WEBHOOK_URL "
                    "out of repo. Slack not sent."
                ),
            },
        )

    # Gate 94B: the global choke point. `mode == "live"` and a configured
    # webhook already gate this, but every egress decision belongs in one place.
    from nativeforge.services.live_network_guard_service import (
        build_live_network_decision,
    )

    decision = build_live_network_decision(
        purpose="operational_alert",
        target_url=webhook,
        caller="feedback_slack_alert_service.send_feedback_slack_alert",
        method="POST",
        allow_live_fetch=True,
        endpoint_configured=bool(webhook),
    )
    if not decision["allowed"]:
        return _result(
            "failed",
            False,
            {"error": "live_network_refused"},
        )

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
        return _result("sent" if ok else "failed", bool(ok))
    except Exception as exc:  # noqa: BLE001
        return _result(
            "failed",
            False,
            {"error": str(exc)[:200]},
        )


def attach_slack_status_to_report(
    report: dict[str, Any],
    *,
    force_dry_run: bool | None = True,
) -> dict[str, Any]:
    result = send_feedback_slack_alert(report, force_dry_run=force_dry_run)
    out = dict(report)
    out["slack_alert_status"] = result.get("slack_alert_status")
    out["slack_alert_result"] = result
    if out.get("slack_alert_status") == "sent" and not result.get("sent"):
        out["slack_alert_status"] = "failed"
    return _json_safe(out)
