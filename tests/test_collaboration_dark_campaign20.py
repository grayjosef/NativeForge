"""Tests: Campaign Block 20 collaboration dark-launch expansion."""

from __future__ import annotations

from nativeforge.services.collaboration_dark_launch_assembler_service import (
    build_collaboration_dark_launch_demo_surface,
    collaboration_dark_launch_demo_surface_invariant_failures,
)
from nativeforge.services.collaboration_dark_launch_expansion_service import (
    build_collaboration_consent_contract,
    build_collaboration_rollout_controls,
    build_future_collaboration_fit_model_dark,
    collaboration_consent_invariant_failures,
    collaboration_fit_model_invariant_failures,
    collaboration_rollout_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_consent_defaults_all_live_false() -> None:
    c = build_collaboration_consent_contract()
    assert c["collaboration_feature_enabled"] is False
    assert c["data_sharing_allowed"] is False
    assert c["organization_opt_in_required"] is True
    assert collaboration_consent_invariant_failures(c) == []


def test_fit_model_dark_no_recommendations() -> None:
    m = build_future_collaboration_fit_model_dark()
    assert m["feature_enabled"] is False
    assert m["fit_score_claimed"] is False
    assert m["partner_recommendation_claimed"] is False
    assert m["partner_names_surfaced"] is False
    assert len(m["dimensions"]) >= 10
    assert collaboration_fit_model_invariant_failures(m) == []


def test_rollout_controls_reject_live_stages() -> None:
    r = build_collaboration_rollout_controls(rollout_stage="global_enabled")
    assert r["rollout_stage"] == "dark"
    assert r["collaboration_global_enabled"] is False
    assert collaboration_rollout_invariant_failures(r) == []


def test_demo_surface_and_bridge() -> None:
    surface = build_collaboration_dark_launch_demo_surface()
    assert collaboration_dark_launch_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    cd = payload["collaboration_dark_launch"]
    assert cd["collaboration_feature_enabled"] is False
    assert cd["partner_matching_live_claimed"] is False
    assert cd["partner_recommendations_claimed"] is False
    assert cd["data_sharing_allowed"] is False
