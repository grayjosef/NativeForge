"""Sprint 208: hardened org/applicant profile record assembler."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.org_applicant_profile_evaluator_service import (
    evaluate_org_applicant_profile,
)
from nativeforge.services.org_applicant_profile_review_status_service import (
    STATUS_INCOMPLETE,
)
from nativeforge.services.readiness_terminology_reconciliation_service import (
    build_readiness_terminology_reconciliation,
    canonical_readiness_label,
)

SCHEMA_VERSION = "nf_org_applicant_profile_hardened_record_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_hardened_org_applicant_profile_record(
    raw: dict[str, Any],
    *,
    fixture_key: str | None = None,
) -> dict[str, Any]:
    fk = fixture_key or str(raw.get("fixture_key") or "unspecified_fixture")
    merged = dict(raw)
    merged["fixture_key"] = fk
    evaluation = evaluate_org_applicant_profile(merged)
    application_readiness = (
        "incomplete"
        if evaluation["review_status"] == STATUS_INCOMPLETE
        else "needs_operator_review"
        if evaluation["human_review_required"]
        else "ready_for_review"
    )
    readiness_reconciliation = build_readiness_terminology_reconciliation(
        application_readiness=application_readiness,
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixture_key": fk,
            "evaluation": evaluation,
            "profile_record": evaluation["profile_record"],
            "review_status": evaluation["review_status"],
            "human_review_required": evaluation["human_review_required"],
            "discoverable": evaluation["discoverable"],
            "application_readiness": application_readiness,
            "readiness_label": canonical_readiness_label(application_readiness),
            "readiness_terminology_reconciliation": readiness_reconciliation,
            "preview_only": True,
            "no_live_ingestion": True,
            "synthetic_fixture": True,
            "no_runtime_db_mutation": True,
        }
    )
