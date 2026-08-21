"""Federal and state applicant authority verification (Campaign Block 28)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.applicant_authority_contract_service import (
    applicant_authority_invariant_failures,
    build_applicant_authority_record,
)

SCHEMA_VERSION = "nf_authority_verification_service_v1"

FEDERAL_REQUIRED = [
    "uei_sam_registration_evidence",
    "organization_applicant_profile_evidence",
    "ebiz_poc_evidence",
    "aor_or_expanded_aor_or_delegated_role_evidence",
    "tribal_authorization_or_delegation_evidence",
]

# Configurable per-state profiles (incomplete by design)
STATE_PROFILES: dict[str, dict[str, Any]] = {
    "SC": {
        "portal_label": "SC state grant portal / vendor systems (varies by program)",
        "required_evidence": [
            "state_portal_or_vendor_account_evidence",
            "authorized_signer_evidence",
            "tribal_resolution_or_delegation_evidence",
            "state_specific_required_attachments",
        ],
        "notes": "State portals vary; SC demo does not live-verify portal roles",
    },
    "DEFAULT": {
        "portal_label": "state_portal_unknown",
        "required_evidence": [
            "state_portal_or_vendor_account_evidence",
            "authorized_signer_evidence",
            "tribal_resolution_or_delegation_evidence",
            "state_specific_role_evidence",
        ],
        "notes": "State-specific profile needed before any authorization claim",
    },
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def verify_federal_authority(
    *,
    person_id: str,
    person_name: str,
    organization_profile_id: str,
    organization_type: str,
    opportunity_id: str | None = None,
    evidence_present: dict[str, bool] | None = None,
    self_attested_only: bool = False,
) -> dict[str, Any]:
    present = dict(evidence_present or {})
    missing = [k for k in FEDERAL_REQUIRED if not present.get(k)]
    refs = [k for k, v in present.items() if v]

    if self_attested_only or not refs:
        status = "needs_verification"
        verification_source = (
            "self_attestation" if self_attested_only else "not_live_verified"
        )
        draft = False
        manage = False
    elif missing:
        status = "partially_verified"
        verification_source = "evidence_packet_incomplete"
        # May allow draft only if org profile + role claim evidence exist — still conservative
        draft = bool(present.get("organization_applicant_profile_evidence"))
        manage = False
    else:
        # Complete packet still not live SAM/Grants.gov verified in Gate 11
        status = "partially_verified"
        verification_source = "evidence_packet_not_live_verified"
        draft = True
        manage = True

    record = build_applicant_authority_record(
        person_id=person_id,
        person_name=person_name,
        organization_profile_id=organization_profile_id,
        organization_type=organization_type,
        grant_context="federal",
        jurisdiction_scope="federal",
        opportunity_id=opportunity_id,
        authority_type="AOR"
        if present.get("aor_or_expanded_aor_or_delegated_role_evidence")
        else "unknown",
        authority_status=status,
        authority_evidence_refs=refs,
        required_evidence=list(FEDERAL_REQUIRED),
        missing_evidence=missing,
        verification_source=verification_source,
        verification_confidence="low",
        human_review_required=True,
        draft_authority_claimed=draft
        and status
        in {
            "verified_for_drafting",
            "partially_verified",
            "verified_for_management",
        },
        manage_workspace_authority_claimed=manage
        and status
        in {
            "verified_for_management",
            "partially_verified",
        },
    )
    # Force honesty flags
    record["submission_authority_claimed"] = False
    record["federal_authority_claimed"] = False
    record["aor_verified_claimed"] = False
    record["ebiz_poc_verified_claimed"] = False
    record["sam_verified_claimed"] = False
    record["not_live_verified"] = True
    record["evidence_required"] = True
    record["schema_version_service"] = SCHEMA_VERSION
    return _json_safe(record)


def verify_state_authority(
    *,
    person_id: str,
    person_name: str,
    organization_profile_id: str,
    organization_type: str,
    state_code: str,
    opportunity_id: str | None = None,
    evidence_present: dict[str, bool] | None = None,
    self_attested_only: bool = False,
) -> dict[str, Any]:
    code = (state_code or "DEFAULT").upper()
    profile = STATE_PROFILES.get(code) or STATE_PROFILES["DEFAULT"]
    required = list(profile["required_evidence"])
    present = dict(evidence_present or {})
    missing = [k for k in required if not present.get(k)]
    refs = [k for k, v in present.items() if v]

    if self_attested_only or not refs:
        status = "needs_verification"
        verification_source = (
            "self_attestation" if self_attested_only else "not_live_verified"
        )
        draft = False
    elif missing:
        status = "partially_verified"
        verification_source = "evidence_packet_incomplete"
        draft = bool(present.get("state_portal_or_vendor_account_evidence"))
    else:
        status = "partially_verified"
        verification_source = "evidence_packet_not_live_verified"
        draft = True

    record = build_applicant_authority_record(
        person_id=person_id,
        person_name=person_name,
        organization_profile_id=organization_profile_id,
        organization_type=organization_type,
        grant_context=f"state:{code}",
        jurisdiction_scope="state",
        opportunity_id=opportunity_id,
        authority_type="authorized_signer"
        if present.get("authorized_signer_evidence")
        else "unknown",
        authority_status=status,
        authority_evidence_refs=refs,
        required_evidence=required,
        missing_evidence=missing,
        verification_source=verification_source,
        verification_confidence="low",
        human_review_required=True,
        draft_authority_claimed=draft,
        manage_workspace_authority_claimed=False,
    )
    record["submission_authority_claimed"] = False
    record["state_authority_claimed"] = False
    record["state_portal_status"] = profile["portal_label"]
    record["state_profile_notes"] = profile["notes"]
    record["not_live_verified"] = True
    record["evidence_required"] = True
    record["schema_version_service"] = SCHEMA_VERSION
    return _json_safe(record)


def authority_verification_invariant_failures(record: dict[str, Any]) -> list[str]:
    fails = applicant_authority_invariant_failures(record)
    if record.get("not_live_verified") is not True:
        # Gate 11: no live SAM/Grants.gov/state portal verification claimed
        fails.append("live_verified_without_integration")
    return fails
