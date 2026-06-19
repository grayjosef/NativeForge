"""Sprint 204: no profile mutation without operator approval."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_org_applicant_profile_no_mutation_without_approval_guard_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def apply_no_mutation_without_approval_guard(
    *,
    mutation_requested: bool,
    operator_approved: bool,
    operator_note: str = "",
) -> dict[str, Any]:
    """Fail-closed: block profile mutations unless operator explicitly approves."""
    if not mutation_requested:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "mutation_requested": False,
                "mutation_allowed": False,
                "mutation_applied": False,
                "operator_approved": operator_approved,
            }
        )

    if operator_approved:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "mutation_requested": True,
                "mutation_allowed": True,
                "mutation_applied": True,
                "operator_approved": True,
                "operator_note": operator_note,
            }
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "mutation_requested": True,
            "mutation_allowed": False,
            "mutation_applied": False,
            "operator_approved": False,
            "guard_reason": "profile mutation requires explicit operator approval",
        }
    )


def build_no_mutation_guard_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "requires_operator_approval": True,
            "preview_only": True,
            "no_runtime_db_mutation": True,
        }
    )
