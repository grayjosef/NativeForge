"""Applicant authority demo assembler (Campaign Block 28)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.authority_verification_service import (
    authority_verification_invariant_failures,
    verify_federal_authority,
    verify_state_authority,
)

SCHEMA_VERSION = "nf_applicant_authority_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_applicant_authority_demo_surface() -> dict[str, Any]:
    # Demo placeholder person — not a real verified user
    federal = verify_federal_authority(
        person_id="demo_operator_placeholder",
        person_name="Demo Operator (placeholder)",
        organization_profile_id="sc_pilot_catawba_indian_nation",
        organization_type="federally_recognized_tribe",
        opportunity_id="fed_ana_seds_example",
        evidence_present={},
        self_attested_only=False,
    )
    federal_self = verify_federal_authority(
        person_id="self_attested_user",
        person_name="Self-attested User",
        organization_profile_id="sc_pilot_catawba_indian_nation",
        organization_type="federally_recognized_tribe",
        evidence_present={"aor_or_expanded_aor_or_delegated_role_evidence": True},
        self_attested_only=True,
    )
    state = verify_state_authority(
        person_id="demo_operator_placeholder",
        person_name="Demo Operator (placeholder)",
        organization_profile_id="sc_pilot_catawba_indian_nation",
        organization_type="federally_recognized_tribe",
        state_code="SC",
        opportunity_id="sc_state_community_dev_example",
        evidence_present={},
    )

    allowed_actions = ["view_demo_surfaces", "prepare_draft_workspace_with_review"]
    blocked_actions = [
        "submit_federal_application",
        "submit_state_application",
        "claim_aor_verified",
        "claim_sam_verified",
        "claim_submission_ready",
        "final_export",
    ]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 28,
            "title": "Applicant authority verification",
            "selected_person": {
                "person_id": "demo_operator_placeholder",
                "person_name": "Demo Operator (placeholder)",
                "role_placeholder": True,
            },
            "organization_profile_id": "sc_pilot_catawba_indian_nation",
            "federal_authority": federal,
            "federal_self_attestation_example": federal_self,
            "state_authority": state,
            "draft_authority_claimed": False,
            "manage_authority_claimed": False,
            "submit_authority_claimed": False,
            "submission_authority_claimed": False,
            "federal_authority_claimed": False,
            "state_authority_claimed": False,
            "required_evidence": list(federal.get("required_evidence") or [])
            + list(state.get("required_evidence") or []),
            "missing_evidence": list(
                dict.fromkeys(
                    list(federal.get("missing_evidence") or [])
                    + list(state.get("missing_evidence") or [])
                )
            ),
            "verification_confidence": "low",
            "human_review_required": True,
            "allowed_actions": allowed_actions,
            "blocked_actions": blocked_actions,
            "buyer_summary": [
                "Authority to draft, manage, and submit are separate",
                "Submission authority is not claimed without evidence",
                "Self-attestation alone never verifies AOR/EBiz POC/SAM",
                "State portal authorization varies by state and is not live-verified",
                "Package export / submission-ready remain blocked on authority gaps",
            ],
            "ties_into": [
                "package_export_preview",
                "final_export_guard",
                "submission_ready_guard",
                "operator_readiness",
                "customer_pilot_readiness",
            ],
            "submission_ready_claimed": False,
            "final_export_claimed": False,
            "login_live_claimed": False,
            "live_ingest_claimed": False,
        }
    )


def applicant_authority_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "submission_authority_claimed",
        "submit_authority_claimed",
        "federal_authority_claimed",
        "state_authority_claimed",
        "submission_ready_claimed",
        "final_export_claimed",
        "login_live_claimed",
        "live_ingest_claimed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    fails.extend(
        authority_verification_invariant_failures(surface.get("federal_authority") or {})
    )
    fails.extend(
        authority_verification_invariant_failures(surface.get("state_authority") or {})
    )
    fed_self = surface.get("federal_self_attestation_example") or {}
    if fed_self.get("submission_authority_claimed") is True:
        fails.append("self_attestation_submission")
    if fed_self.get("federal_authority_claimed") is True:
        fails.append("self_attestation_federal")
    return fails
