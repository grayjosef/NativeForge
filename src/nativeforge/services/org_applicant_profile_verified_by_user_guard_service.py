"""Sprint 203: verified_by_user requires explicit human/customer confirmation."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.org_applicant_profile_review_status_service import (
    STATUS_NEEDS_REVIEW,
    STATUS_VERIFIED_BY_USER,
    is_valid_review_status,
)

SCHEMA_VERSION = "nf_org_applicant_profile_verified_by_user_guard_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def apply_verified_by_user_guard(
    *,
    proposed_review_status: str,
    human_confirmation_present: bool,
    customer_confirmation_present: bool = False,
) -> dict[str, Any]:
    """Fail-closed: verified_by_user only with explicit human or customer confirmation."""
    if not is_valid_review_status(proposed_review_status):
        raise ValueError(f"invalid review status: {proposed_review_status!r}")

    if proposed_review_status != STATUS_VERIFIED_BY_USER:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "proposed_review_status": proposed_review_status,
                "final_review_status": proposed_review_status,
                "verification_blocked": False,
                "human_confirmation_present": human_confirmation_present,
            }
        )

    confirmed = human_confirmation_present or customer_confirmation_present
    if confirmed:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "proposed_review_status": proposed_review_status,
                "final_review_status": STATUS_VERIFIED_BY_USER,
                "verification_blocked": False,
                "human_confirmation_present": human_confirmation_present,
                "customer_confirmation_present": customer_confirmation_present,
            }
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "proposed_review_status": proposed_review_status,
            "final_review_status": STATUS_NEEDS_REVIEW,
            "verification_blocked": True,
            "human_confirmation_present": False,
            "guard_reason": (
                "verified_by_user requires explicit human or customer confirmation"
            ),
        }
    )


def build_verified_by_user_guard_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "protected_status": STATUS_VERIFIED_BY_USER,
            "fallback_status": STATUS_NEEDS_REVIEW,
            "preview_only": True,
        }
    )
