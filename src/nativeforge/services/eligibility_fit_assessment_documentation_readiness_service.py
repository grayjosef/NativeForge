"""Sprint 198: documentation readiness assessment for eligibility fit."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_eligibility_fit_assessment_documentation_readiness_v1"

READINESS_COMPLETE = "complete"
READINESS_PARTIAL = "partial"
READINESS_INCOMPLETE = "incomplete"
READINESS_UNKNOWN = "unknown"

DOCUMENTATION_READINESS_LEVELS: tuple[str, ...] = (
    READINESS_COMPLETE,
    READINESS_PARTIAL,
    READINESS_INCOMPLETE,
    READINESS_UNKNOWN,
)

_REQUIRED_DOC_FIELDS: tuple[str, ...] = (
    "organizational_profile_complete",
    "tribal_resolution_on_file",
    "financial_statements_on_file",
    "authorized_signer_confirmed",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def assess_documentation_readiness(profile: dict[str, Any]) -> dict[str, Any]:
    inventory = profile.get("documentation_inventory") or {}
    if not isinstance(inventory, dict) or not inventory:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "documentation_readiness": READINESS_UNKNOWN,
                "missing_documentation_fields": list(_REQUIRED_DOC_FIELDS),
                "human_review_required": True,
            }
        )
    missing = [f for f in _REQUIRED_DOC_FIELDS if not inventory.get(f)]
    if not missing:
        readiness = READINESS_COMPLETE
    elif len(missing) < len(_REQUIRED_DOC_FIELDS):
        readiness = READINESS_PARTIAL
    else:
        readiness = READINESS_INCOMPLETE
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "documentation_readiness": readiness,
            "missing_documentation_fields": missing,
            "human_review_required": readiness != READINESS_COMPLETE,
        }
    )
