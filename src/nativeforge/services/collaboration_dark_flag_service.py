"""Collaboration dark-flag foundation (Campaign Block 14). Feature OFF by default."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_collaboration_dark_flag_contract_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_collaboration_dark_flag_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 14,
            "title": "Collaboration dark foundation (disabled)",
            "collaboration_feature_enabled": False,
            "collaboration_global_enabled": False,
            "collaboration_cohort_enabled": False,
            "organization_opt_in_required": True,
            "partner_matching_live_claimed": False,
            "cohort_rollout_claimed": False,
            "global_rollout_claimed": False,
            "live_introductions_claimed": False,
            "customer_data_sharing_claimed": False,
            "future_concepts": [
                "opportunity-based collaboration fit",
                "geography/service-area compatibility",
                "eligibility compatibility",
                "fiscal sponsor/partner pathway",
                "consortium opportunities",
                "shared service goals",
                "customer opt-in",
                "data sovereignty boundaries",
                "cohort rollout before global",
                "operator review before introductions",
            ],
            "buyer_summary": [
                "Collaboration / partner discovery is architected but dark and OFF",
                "No live matching, introductions, or partner recommendations",
                "Org opt-in and sovereignty boundaries required before any future enablement",
                "Cohort and global rollout claims remain false",
            ],
        }
    )


def collaboration_dark_flag_invariant_failures(contract: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "collaboration_feature_enabled",
        "collaboration_global_enabled",
        "collaboration_cohort_enabled",
        "partner_matching_live_claimed",
        "cohort_rollout_claimed",
        "global_rollout_claimed",
        "live_introductions_claimed",
        "customer_data_sharing_claimed",
    ):
        if contract.get(key) is True:
            fails.append(key)
    if contract.get("organization_opt_in_required") is not True:
        fails.append("opt_in_not_required")
    return fails
