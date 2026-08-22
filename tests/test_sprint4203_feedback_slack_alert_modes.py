"""Gate 37: feedback Slack alert modes (dry_run, missing webhook, mocked live)."""

from __future__ import annotations

import urllib.request
from unittest.mock import MagicMock

import pytest

from nativeforge.services.feedback_report_contract_service import (
    build_feedback_report,
)
from nativeforge.services.feedback_slack_alert_service import (
    ENV_MODE,
    ENV_WEBHOOK,
    format_slack_message,
    send_feedback_slack_alert,
)


def _report(**kwargs):
    base = dict(
        route="/?view=sc_customer_demo",
        page_id="sc_customer_demo",
        surface_id="operator_readiness",
        report_type="customer_feedback",
        severity="high",
        user_message="Need a follow-up from Mayhem",
        client_context={
            "org_display_name": "Example Nation",
            "contact_email": "buyer@example.invalid",
        },
    )
    base.update(kwargs)
    return build_feedback_report(**base)


def test_dry_run_does_not_send(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_MODE, "dry_run")
    monkeypatch.setenv(ENV_WEBHOOK, "https://hooks.example.invalid/TEST_HOOK")
    result = send_feedback_slack_alert(_report(), force_dry_run=True)
    assert result["sent"] is False
    assert result["slack_alert_status"] == "dry_run"
    assert result["alert_mode"] == "dry_run"
    assert "TEST_HOOK" not in str(result.get("note"))
    preview = format_slack_message(_report())
    text = preview["blocks"][0]["text"]["text"]
    assert "Example Nation" in text
    assert "buyer@example.invalid" in text
    assert "/?view=sc_customer_demo" in text


def test_live_missing_webhook_is_config_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ENV_MODE, "live")
    monkeypatch.delenv(ENV_WEBHOOK, raising=False)
    result = send_feedback_slack_alert(_report(), force_dry_run=False)
    assert result["sent"] is False
    assert result["slack_alert_status"] == "config_error"
    assert result["webhook_configured"] is False


def test_live_mode_mocked_http_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_MODE, "live")
    monkeypatch.setenv(ENV_WEBHOOK, "https://hooks.example.invalid/TEST_HOOK")
    resp = MagicMock()
    resp.status = 200
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: resp)
    result = send_feedback_slack_alert(_report(), force_dry_run=False)
    assert result["sent"] is True
    assert result["slack_alert_status"] == "sent"
    assert "TEST_HOOK" not in str(result)
