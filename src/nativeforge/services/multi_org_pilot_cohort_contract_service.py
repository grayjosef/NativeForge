"""Multi-organization pilot / cohort contract (Campaign Block 19)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_multi_org_pilot_cohort_contract_v1"

COHORT_DATA_MODES = frozenset({"curated_demo", "fixture_backed_pilot", "not_supported"})


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_pilot_cohort_id(cohort_label: str) -> str:
    raw = f"cohort::{cohort_label}".encode()
    return f"pc_{hashlib.sha256(raw).hexdigest()[:16]}"


def build_multi_org_pilot_cohort_contract(
    *,
    cohort_label: str,
    cohort_data_mode: str = "fixture_backed_pilot",
    organization_profile_ids: list[str] | None = None,
    opportunity_scope: str = "sc_plus_federal_relevant",
    state_scope: str = "South Carolina",
    federal_scope_enabled: bool = True,
    package_workspace_ids: list[str] | None = None,
    readiness_rollup_ids: list[str] | None = None,
    feedback_context_ids: list[str] | None = None,
) -> dict[str, Any]:
    mode = (
        cohort_data_mode
        if cohort_data_mode in COHORT_DATA_MODES
        else "fixture_backed_pilot"
    )
    org_ids = list(organization_profile_ids or [])
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "pilot_cohort_id": make_pilot_cohort_id(cohort_label),
            "cohort_label": cohort_label,
            "cohort_data_mode": mode,
            "organization_profile_ids": org_ids,
            "organization_count": len(org_ids),
            "opportunity_scope": opportunity_scope,
            "state_scope": state_scope,
            "federal_scope_enabled": federal_scope_enabled,
            "package_workspace_ids": list(package_workspace_ids or []),
            "readiness_rollup_ids": list(readiness_rollup_ids or []),
            "feedback_context_ids": list(feedback_context_ids or []),
            "collaboration_enabled": False,
            "customer_data_persistence_claimed": False,
            "production_multi_tenant_claimed": False,
            "live_customer_login_claimed": False,
            "live_ingest_claimed": False,
            "submission_ready_claimed": False,
            "final_export_claimed": False,
            "final_eligibility_claimed": False,
        }
    )


def multi_org_pilot_cohort_invariant_failures(contract: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "collaboration_enabled",
        "customer_data_persistence_claimed",
        "production_multi_tenant_claimed",
        "live_customer_login_claimed",
        "live_ingest_claimed",
        "submission_ready_claimed",
        "final_export_claimed",
        "final_eligibility_claimed",
    ):
        if contract.get(key) is True:
            fails.append(key)
    if contract.get("cohort_data_mode") not in COHORT_DATA_MODES:
        fails.append("bad_cohort_data_mode")
    if (contract.get("organization_count") or 0) < 1:
        fails.append("no_orgs")
    return fails
