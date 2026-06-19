"""Sprint 217: never mutate a profile to make a match fit."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_matching_readiness_no_profile_mutation_guard_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def apply_no_profile_mutation_guard(
    *,
    profile_mutation_requested: bool,
    mutation_reason: str = "improve_match_fit",
    operator_approved: bool = False,
) -> dict[str, Any]:
    """Fail-closed: block profile mutations intended to improve match fit."""
    if not profile_mutation_requested:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "profile_mutation_requested": False,
                "mutation_blocked": False,
                "profile_mutated": False,
            }
        )

    if operator_approved:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "profile_mutation_requested": True,
                "mutation_blocked": False,
                "profile_mutated": True,
                "mutation_reason": mutation_reason,
                "operator_approved": True,
            }
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "profile_mutation_requested": True,
            "mutation_blocked": True,
            "profile_mutated": False,
            "mutation_reason": mutation_reason,
            "guard_reason": "never mutate profile to make a match fit without approval",
        }
    )


def build_no_profile_mutation_guard_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "forbidden_mutation_reasons": ["improve_match_fit", "force_eligibility_fit"],
            "preview_only": True,
            "no_runtime_db_mutation": True,
        }
    )
