"""Sprint 207: org/applicant profile evaluator with hard invariants."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.org_applicant_profile_no_mutation_without_approval_guard_service import (
    apply_no_mutation_without_approval_guard,
)
from nativeforge.services.org_applicant_profile_record_builder_service import (
    build_provenance_first_profile_record,
)
from nativeforge.services.org_applicant_profile_review_status_service import (
    STATUS_DRAFT,
    STATUS_INCOMPLETE,
    STATUS_NEEDS_REVIEW,
)
from nativeforge.services.org_applicant_profile_schema_service import (
    FIELD_ENTITY_TYPE,
    FIELD_LEGAL_NAME,
)
from nativeforge.services.org_applicant_profile_unknown_value_policy_service import (
    is_unknown_value,
)
from nativeforge.services.org_applicant_profile_verified_by_user_guard_service import (
    apply_verified_by_user_guard,
)

SCHEMA_VERSION = "nf_org_applicant_profile_evaluator_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _propose_review_status(raw: dict[str, Any], profile_fields: dict[str, Any]) -> str:
    proposed = str(raw.get("review_status") or STATUS_DRAFT)
    if is_unknown_value(profile_fields.get(FIELD_LEGAL_NAME)) or is_unknown_value(
        profile_fields.get(FIELD_ENTITY_TYPE)
    ):
        return STATUS_INCOMPLETE
    return proposed


def evaluate_org_applicant_profile(raw: dict[str, Any]) -> dict[str, Any]:
    record = build_provenance_first_profile_record(raw)
    profile_fields = record["profile_fields"]

    proposed_status = _propose_review_status(raw, profile_fields)
    verify_guard = apply_verified_by_user_guard(
        proposed_review_status=proposed_status,
        human_confirmation_present=bool(raw.get("human_confirmation_present")),
        customer_confirmation_present=bool(raw.get("customer_confirmation_present")),
    )

    mutation_guard = apply_no_mutation_without_approval_guard(
        mutation_requested=bool(raw.get("mutation_requested")),
        operator_approved=bool(raw.get("operator_approved")),
        operator_note=str(raw.get("operator_note") or ""),
    )

    unknown_field_count = sum(1 for v in profile_fields.values() if is_unknown_value(v))
    human_review_required = (
        verify_guard["verification_blocked"]
        or unknown_field_count > 0
        or verify_guard["final_review_status"] in {STATUS_NEEDS_REVIEW, STATUS_INCOMPLETE}
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixture_key": record["fixture_key"],
            "profile_record": record,
            "review_status": verify_guard["final_review_status"],
            "human_review_required": human_review_required,
            "unknown_field_count": unknown_field_count,
            "verified_by_user_guard": verify_guard,
            "mutation_guard": mutation_guard,
            "discoverable": True,
            "preview_only": True,
            "no_runtime_db_mutation": not mutation_guard["mutation_applied"],
        }
    )
