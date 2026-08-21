"""Block 51 assembler: customer data policy surface."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.customer_data_policy_service import (
    build_customer_data_policy_contract,
    classify_data_item,
    customer_data_policy_invariant_failures,
    resolve_customer_persistence,
)

SCHEMA_VERSION = "nf_customer_data_policy_assembler_v1"
DOC = "docs/operations/247_CUSTOMER_DATA_POLICY_GATE23.md"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_customer_data_policy_demo_surface() -> dict[str, Any]:
    policy = build_customer_data_policy_contract()
    persistence = resolve_customer_persistence(policy=policy)
    sample = classify_data_item(
        classification="legal_or_governance_document",
        proposed_storage_mode="production_object_storage",
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 51,
            "title": "Customer data policy enforcement",
            "docs": [DOC],
            "customer_data_policy_contract": True,
            "data_classifications": policy.get("data_classifications"),
            "storage_modes": policy.get("storage_modes"),
            "ai_training_consent_default": False,
            "ai_training_consent": False,
            "organization_policy_status": policy.get("policy_status"),
            "customer_persistence_resolver": True,
            "customer_data_persistence_claimed": False,
            "customer_data_policy_production_claimed": False,
            "legal_compliance_claimed": False,
            "policy_violation_audit": True,
            "sample_classification_blocked": sample.get("blocked"),
            "production_storage_claimed": False,
            "login_live_claimed": False,
            "controlled_customer_pilot_status": "NO_GO",
            "production_rollout_status": "NO_GO",
            "missing_gates": persistence.get("missing_gates"),
            "buyer_summary": [
                "Customer data policy contract classifies org/evidence/sensitive data",
                "AI training consent defaults to false",
                "Unknown or production modes without approval block persistence",
                "Customer persistence remains false until policy + auth + storage + tenant + audit pass",
            ],
            "next_safe_actions": [
                persistence.get("next_safe_action"),
                "Do not claim legal compliance or production policy validation",
            ],
            "human_review_required": True,
            "policy": policy,
            "persistence": persistence,
        }
    )


def customer_data_policy_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "customer_data_persistence_claimed",
        "customer_data_policy_production_claimed",
        "legal_compliance_claimed",
        "production_storage_claimed",
        "login_live_claimed",
        "ai_training_consent",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if surface.get("ai_training_consent_default") is not False:
        fails.append("ai_training_default")
    fails.extend(
        customer_data_policy_invariant_failures(surface.get("persistence") or {})
    )
    fails.extend(customer_data_policy_invariant_failures(surface.get("policy") or {}))
    return fails
