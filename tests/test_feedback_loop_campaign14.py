"""Tests: Campaign Block 14 feedback loop + Slack + collaboration dark flag."""

from __future__ import annotations

from nativeforge.services.collaboration_dark_flag_service import (
    build_collaboration_dark_flag_contract,
    collaboration_dark_flag_invariant_failures,
)
from nativeforge.services.feedback_loop_assembler_service import (
    build_feedback_loop_demo_surface,
    feedback_loop_demo_surface_invariant_failures,
)
from nativeforge.services.feedback_report_contract_service import (
    build_feedback_report,
    feedback_report_invariant_failures,
)
from nativeforge.services.feedback_slack_alert_service import (
    send_feedback_slack_alert,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_feedback_report_contract() -> None:
    report = build_feedback_report(
        route="/?view=sc_customer_demo",
        page_id="sc_customer_demo",
        surface_id="draft_workspace",
        report_type="draft_quality_concern",
        severity="high",
        user_message="Draft looks wrong",
    )
    assert report["persistence_claimed"] is False
    assert report["slack_alert_status"] != "sent"
    assert feedback_report_invariant_failures(report) == []


def test_slack_cannot_claim_sent_on_dry_run() -> None:
    report = build_feedback_report(
        route="/?view=sc_customer_demo",
        page_id="sc_customer_demo",
        surface_id="ai_governance",
        report_type="bug",
        severity="critical",
        user_message="Panel broken",
    )
    result = send_feedback_slack_alert(report, force_dry_run=True)
    assert result["sent"] is False
    assert result["slack_alert_status"] in {"dry_run", "not_configured"}


def test_collaboration_dark_flags_off() -> None:
    contract = build_collaboration_dark_flag_contract()
    assert collaboration_dark_flag_invariant_failures(contract) == []
    assert contract["collaboration_feature_enabled"] is False
    assert contract["partner_matching_live_claimed"] is False
    assert contract["global_rollout_claimed"] is False


def test_demo_surface_and_bridge() -> None:
    surface = build_feedback_loop_demo_surface()
    assert feedback_loop_demo_surface_invariant_failures(surface) == []
    assert surface["report_hook_count"] >= 10
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["feedback_loop"]["persistence_claimed"] is False
    assert (
        payload["feedback_loop"]["collaboration"]["collaboration_feature_enabled"]
        is False
    )
