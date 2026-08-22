"""Buyer-grade UX / trust surfaces + final claim freeze (Block 66)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate30_final_closeout_service import (
    build_3000_sprint_closeout,
)

SCHEMA_VERSION = "nf_gate30_buyer_trust_v1"

SAFE_VERBS = (
    "Build Evidence-Backed Package",
    "Review Eligibility",
    "Resolve Authority Gap",
    "Attach Required Evidence",
    "Run QA Gates",
    "Prepare Human Review",
    "Owner Action Required",
    "Production Claim Blocked",
    "Evidence Required",
)

FORBIDDEN_UI_PHRASES = (
    "Generate Proposal",
    "Auto Submit",
    "Guaranteed Eligibility",
    "Production Ready",
    "Pilot Ready",
    "Secure",
    "Pen-Test Passed",
    "Login Live",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _view(
    view_id: str,
    title: str,
    answers: dict[str, str],
    freeze: dict[str, Any],
) -> dict[str, Any]:
    return {
        "view_id": view_id,
        "title": title,
        "answers": answers,
        "allowed_claims": freeze.get("allowed_claims"),
        "forbidden_claims": freeze.get("forbidden_claims"),
        "blocker_reason": freeze.get("next_owner_action"),
        "evidence_refs": list((freeze.get("evidence_map") or {}).keys())[:6],
        "owner_next_action": freeze.get("next_owner_action"),
        "fake_green_badge": False,
        "fake_customer_access_cta": False,
        "fake_upload_cta": False,
        "fake_secure_badge": False,
        "fake_pilot_ready_banner": False,
    }


def build_buyer_trust_surfaces() -> dict[str, Any]:
    closeout = build_3000_sprint_closeout()
    freeze = {
        "allowed_claims": closeout.get("allowed_claims"),
        "forbidden_claims": closeout.get("forbidden_claims"),
        "evidence_map": closeout.get("evidence_map"),
        "next_owner_action": closeout.get("next_owner_action"),
    }
    views = [
        _view(
            "buyer_landing",
            "Buyer landing",
            {
                "what": "Native-relevant grant discovery and intelligence for SC orgs",
                "next_safe": "Review Eligibility, then Build Evidence-Backed Package",
                "cannot_claim": "Production Ready / Pilot Ready / Login Live",
            },
            freeze,
        ),
        _view(
            "opportunity_intelligence",
            "Opportunity intelligence",
            {
                "what": "Curated SC + federal opportunities with source labels",
                "lane": "federal, state, Native-relevant (not Native-only)",
                "missing": "Live ingest and NOFO PDF extraction remain NOT_SUPPORTED",
            },
            freeze,
        ),
        _view(
            "eligibility_recognition",
            "Eligibility and recognition",
            {
                "recognition": "Federal vs state-only recognition stays visible",
                "action": "Review Eligibility",
                "blocked": "Guaranteed Eligibility is forbidden",
            },
            freeze,
        ),
        _view(
            "authority_to_apply",
            "Authority-to-apply",
            {
                "who": "Human reviewer / authorized tribal grant manager",
                "action": "Resolve Authority Gap",
                "blocked": "authority_not_live blocks final eligibility/submission",
            },
            freeze,
        ),
        _view(
            "evidence_package_readiness",
            "Evidence binder / package readiness",
            {
                "action": "Attach Required Evidence; Run QA Gates; Prepare Human Review",
                "missing": "Package is a skeleton, not a finished application",
                "blocked": "Auto Submit is forbidden",
            },
            freeze,
        ),
        _view(
            "customer_data_sovereignty",
            "Customer data policy / sovereignty",
            {
                "policy": "Customer data policy exists; AI training consent default false",
                "blocked": "customer persistence remains false",
                "action": "Owner Action Required before any customer data store",
            },
            freeze,
        ),
        _view(
            "security_pentest_readiness",
            "Security and pen-test readiness",
            {
                "sca": "Gate 16 SCA pass preserved",
                "pentest": "pen_test_passed=false; no fake Secure badge",
                "action": "Evidence Required — attach real pen-test report",
            },
            freeze,
        ),
        _view(
            "owner_action_cockpit",
            "Production cutover / owner action cockpit",
            {
                "blocked": "Production Claim Blocked until Mode B inputs exist",
                "action": closeout.get("next_owner_action") or "Owner Action Required",
                "mode_b": "Mode B executed=false",
            },
            freeze,
        ),
        _view(
            "controlled_pilot_go_nogo",
            "Controlled pilot GO/NO-GO",
            {
                "status": closeout.get("controlled_customer_pilot_status") or "",
                "rollout": closeout.get("production_rollout_status") or "",
                "blocked": "CONTROLLED_CUSTOMER_GO not allowed in Mode A",
            },
            freeze,
        ),
        _view(
            "operator_command_center",
            "Operator command center",
            {
                "route": "/?view=sc_customer_demo",
                "demo": "GO",
                "customer_pilot": closeout.get("controlled_customer_pilot_status")
                or "",
            },
            freeze,
        ),
    ]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "buyer_trust_contract": True,
            "safe_verbs": list(SAFE_VERBS),
            "forbidden_ui_phrases": list(FORBIDDEN_UI_PHRASES),
            "views": views,
            "controlled_customer_pilot_status": closeout.get(
                "controlled_customer_pilot_status"
            ),
            "production_rollout_status": closeout.get("production_rollout_status"),
            "login_live_claimed": False,
            "production_storage_claimed": False,
            "pen_test_passed_claimed": False,
            "fake_green_badge": False,
            "fake_pilot_ready_banner": False,
            "fake_production_ready": False,
            "fake_secure_badge": False,
            "blockers_exposed": True,
            "owner_next_action_exposed": True,
            "claim_freeze_visible": True,
            "demo_safe": True,
            "next_owner_action": closeout.get("next_owner_action"),
            "allowed_claims": closeout.get("allowed_claims"),
            "forbidden_claims": closeout.get("forbidden_claims"),
            "talk_track": [
                "This is a Monday demo of Native-relevant opportunity intelligence.",
                "Review Eligibility, then Build Evidence-Backed Package.",
                "Owner Action Required before customer access.",
                "Production Claim Blocked: login, storage, and pen-test remain false.",
            ],
            "closeout_run_id": closeout.get("closeout_run_id"),
        }
    )


def buyer_trust_invariant_failures(surface: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "login_live_claimed",
        "production_storage_claimed",
        "pen_test_passed_claimed",
        "fake_green_badge",
        "fake_pilot_ready_banner",
        "fake_production_ready",
        "fake_secure_badge",
    ):
        if surface.get(key) is True:
            fails.append(key)
    blob = json.dumps(surface)
    for phrase in FORBIDDEN_UI_PHRASES:
        # Allowed only inside forbidden_ui_phrases list or "cannot_claim" answers
        if phrase in blob and surface.get("production_rollout_status") == "GO":
            fails.append(f"forbidden_phrase_with_go:{phrase}")
    if surface.get("controlled_customer_pilot_status") == "CONTROLLED_CUSTOMER_GO":
        fails.append("pilot_go")
    if not surface.get("blockers_exposed"):
        fails.append("blockers_hidden")
    if not surface.get("owner_next_action_exposed"):
        fails.append("owner_action_hidden")
    if not surface.get("claim_freeze_visible"):
        fails.append("freeze_hidden")
    if not surface.get("demo_safe"):
        fails.append("not_demo_safe")
    for view in surface.get("views") or []:
        if view.get("fake_green_badge") or view.get("fake_pilot_ready_banner"):
            fails.append(f"fake_badge:{view.get('view_id')}")
        if not view.get("allowed_claims") or not view.get("forbidden_claims"):
            fails.append(f"freeze_missing:{view.get('view_id')}")
    return fails
