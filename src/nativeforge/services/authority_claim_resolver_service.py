"""Authority claim resolver distinguishing view/draft/manage/submit (Block 33)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.federal_live_authority_spike_service import (
    run_federal_live_authority_spike,
)
from nativeforge.services.state_authority_spike_service import run_state_authority_spike

SCHEMA_VERSION = "nf_authority_claim_resolver_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def resolve_authority_claims(
    *,
    organization_type: str = "federally_recognized_tribe",
    jurisdiction: str = "federal",
    opportunity_type: str = "federal_grant",
    evidence_present: dict[str, bool] | None = None,
    human_review_complete: bool = False,
    self_attested_only: bool = False,
) -> dict[str, Any]:
    present = dict(evidence_present or {})
    federal = run_federal_live_authority_spike(
        evidence_present=present,
        self_attested_only=self_attested_only,
    )
    state = (
        run_state_authority_spike(state_code="SC", evidence_present=present)
        if jurisdiction in {"state", "both"}
        else None
    )

    view_authority = True  # demo view always
    # Draft only with some org evidence + not self-attestation-only
    draft_authority = bool(
        not self_attested_only
        and present.get("organization_applicant_profile_evidence")
        and human_review_complete
    )
    manage_workspace_authority = False  # Gate 14: still conservative
    upload_evidence_authority = bool(not self_attested_only and human_review_complete)
    approve_package_authority = False
    submit_authority = False

    # Hard: submit never without full federal packet AND live/manual verified claims
    # which remain false in this gate
    if (
        federal.get("sam_uei_verified_claimed")
        and federal.get("ebiz_poc_verified_claimed")
        and federal.get("aor_verified_claimed")
        and present.get("tribal_authorization_or_delegation_evidence")
        and human_review_complete
        and not self_attested_only
    ):
        # Still keep false — no live verification in Gate 14
        submit_authority = False

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "organization_type": organization_type,
            "jurisdiction": jurisdiction,
            "opportunity_type": opportunity_type,
            "view_authority": view_authority,
            "draft_authority": draft_authority,
            "manage_workspace_authority": manage_workspace_authority,
            "upload_evidence_authority": upload_evidence_authority,
            "approve_package_authority": approve_package_authority,
            "submit_authority": submit_authority,
            "submission_authority_claimed": False,
            "federal_spike": federal,
            "state_spike": state,
            "ties_into": [
                "package_export_preview",
                "submission_ready_guard",
                "operator_readiness",
                "controlled_pilot_invite_design",
            ],
            "human_review_required": True,
            "login_live_claimed": False,
            "sam_uei_verified_claimed": False,
            "ebiz_poc_verified_claimed": False,
            "aor_verified_claimed": False,
            "state_authority_verified_claimed": False,
            "submission_ready_claimed": False,
            "final_export_claimed": False,
        }
    )


def authority_claim_resolver_invariant_failures(report: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "submit_authority",
        "submission_authority_claimed",
        "sam_uei_verified_claimed",
        "ebiz_poc_verified_claimed",
        "aor_verified_claimed",
        "state_authority_verified_claimed",
        "submission_ready_claimed",
        "final_export_claimed",
        "login_live_claimed",
        "approve_package_authority",
    ):
        if report.get(key) is True:
            fails.append(key)
    return fails
