"""Authority source registry for live/read-only verification spike (Block 33)."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_authority_source_registry_v1"

SOURCE_TYPES = frozenset(
    {
        "sam_gov_uei_entity_registration",
        "grants_gov_organization_profile",
        "ebiz_poc_evidence",
        "aor_or_expanded_aor_role",
        "tribal_authorization_resolution_delegation",
        "state_portal_account_vendor_registration",
        "state_authorized_signer",
        "fiscal_sponsor_delegation",
        "nonprofit_board_officer_authorization",
        "unknown_manual_review",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_authority_source_registry() -> dict[str, Any]:
    sources = [
        {
            "source_type": "sam_gov_uei_entity_registration",
            "live_check_availability": "not_configured",
            "credentials_required": ["SAM_API_KEY_or_login_not_present"],
            "api_or_manual_evidence_path": "manual_evidence_upload_or_future_read_only_SAM_API",
            "verification_confidence": "unknown_until_live_or_evidence",
            "staleness_expiration_behavior": "recheck_if_registration_expired_or_stale",
            "human_review_required": True,
            "authority_claims_allowed": ["none_without_evidence"],
            "authority_claims_forbidden": [
                "sam_verified",
                "uei_verified",
                "federal_submission_authority",
            ],
        },
        {
            "source_type": "grants_gov_organization_profile",
            "live_check_availability": "not_configured",
            "credentials_required": ["Grants.gov_org_admin_not_present"],
            "api_or_manual_evidence_path": "manual_org_profile_screenshot_or_export",
            "verification_confidence": "unknown_until_evidence",
            "staleness_expiration_behavior": "recheck_on_role_change",
            "human_review_required": True,
            "authority_claims_allowed": ["none_without_evidence"],
            "authority_claims_forbidden": ["grants_gov_profile_verified"],
        },
        {
            "source_type": "ebiz_poc_evidence",
            "live_check_availability": "not_configured",
            "credentials_required": ["SAM_EBiz_POC_access_not_present"],
            "api_or_manual_evidence_path": "manual_EBiz_POC_evidence",
            "verification_confidence": "unknown_until_evidence",
            "staleness_expiration_behavior": "recheck_on_POC_change",
            "human_review_required": True,
            "authority_claims_allowed": ["none_without_evidence"],
            "authority_claims_forbidden": ["ebiz_poc_verified"],
        },
        {
            "source_type": "aor_or_expanded_aor_role",
            "live_check_availability": "not_configured",
            "credentials_required": ["Grants.gov_workspace_role_access_not_present"],
            "api_or_manual_evidence_path": "manual_AOR_role_evidence",
            "verification_confidence": "unknown_until_evidence",
            "staleness_expiration_behavior": "recheck_on_role_revoke_or_expiry",
            "human_review_required": True,
            "authority_claims_allowed": ["none_without_evidence"],
            "authority_claims_forbidden": ["aor_verified", "expanded_aor_verified"],
        },
        {
            "source_type": "tribal_authorization_resolution_delegation",
            "live_check_availability": "manual_evidence_only",
            "credentials_required": [],
            "api_or_manual_evidence_path": "tribal_resolution_or_delegation_letter_upload",
            "verification_confidence": "medium_with_reviewed_evidence",
            "staleness_expiration_behavior": "resolution_may_expire_or_be_purpose_limited",
            "human_review_required": True,
            "authority_claims_allowed": ["draft_with_reviewed_evidence_possible"],
            "authority_claims_forbidden": [
                "tribal_authorization_verified_without_evidence",
                "submission_authority_without_full_packet",
            ],
        },
        {
            "source_type": "state_portal_account_vendor_registration",
            "live_check_availability": "not_configured_varies_by_state",
            "credentials_required": ["state_portal_credentials_not_present"],
            "api_or_manual_evidence_path": "manual_state_portal_account_evidence",
            "verification_confidence": "unknown_until_evidence",
            "staleness_expiration_behavior": "recheck_per_state_rules",
            "human_review_required": True,
            "authority_claims_allowed": ["none_without_evidence"],
            "authority_claims_forbidden": ["state_portal_authority_verified"],
        },
        {
            "source_type": "state_authorized_signer",
            "live_check_availability": "manual_evidence_only",
            "credentials_required": [],
            "api_or_manual_evidence_path": "authorized_signer_letter_or_portal_role_evidence",
            "verification_confidence": "unknown_until_evidence",
            "staleness_expiration_behavior": "recheck_on_signer_change",
            "human_review_required": True,
            "authority_claims_allowed": ["none_without_evidence"],
            "authority_claims_forbidden": ["state_authorized_signer_verified"],
        },
        {
            "source_type": "fiscal_sponsor_delegation",
            "live_check_availability": "manual_evidence_only",
            "credentials_required": [],
            "api_or_manual_evidence_path": "fiscal_sponsor_MOU_or_delegation",
            "verification_confidence": "unknown_until_evidence",
            "staleness_expiration_behavior": "recheck_on_MOU_expiry",
            "human_review_required": True,
            "authority_claims_allowed": ["none_without_evidence"],
            "authority_claims_forbidden": [
                "fiscal_sponsor_authority_verified_without_evidence"
            ],
        },
        {
            "source_type": "nonprofit_board_officer_authorization",
            "live_check_availability": "manual_evidence_only",
            "credentials_required": [],
            "api_or_manual_evidence_path": "board_resolution_or_officer_authorization",
            "verification_confidence": "unknown_until_evidence",
            "staleness_expiration_behavior": "recheck_on_board_change",
            "human_review_required": True,
            "authority_claims_allowed": ["none_without_evidence"],
            "authority_claims_forbidden": [
                "board_authorization_verified_without_evidence"
            ],
        },
        {
            "source_type": "unknown_manual_review",
            "live_check_availability": "not_supported",
            "credentials_required": [],
            "api_or_manual_evidence_path": "operator_manual_review",
            "verification_confidence": "unknown",
            "staleness_expiration_behavior": "n/a",
            "human_review_required": True,
            "authority_claims_allowed": ["none"],
            "authority_claims_forbidden": ["any_live_verified_claim"],
        },
    ]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_count": len(sources),
            "sources": sources,
            "any_live_check_configured": False,
            "live_verification_credentials_present": False,
        }
    )


def authority_source_registry_invariant_failures(reg: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if reg.get("any_live_check_configured") is True:
        fails.append("live_check_configured_unexpected")
    if reg.get("live_verification_credentials_present") is True:
        fails.append("credentials_present_unexpected")
    if not (reg.get("sources") or []):
        fails.append("no_sources")
    for s in reg.get("sources") or []:
        if s.get("source_type") not in SOURCE_TYPES:
            fails.append(f"bad_source:{s.get('source_type')}")
        if s.get("human_review_required") is not True:
            fails.append(f"no_human_review:{s.get('source_type')}")
    return fails
