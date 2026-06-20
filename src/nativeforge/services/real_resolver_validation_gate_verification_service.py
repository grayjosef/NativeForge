"""Sprint 295: real-resolver validation gate verification."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.db.models import Organization
from nativeforge.services.real_resolver_validation_orchestrator_service import (
    run_real_resolver_validation_block,
)
from nativeforge.services.real_tier1_live_fetch_service import (
    fixture_tier1_live_fetch,
    reset_real_tier1_fetch_rate_limit,
)
from nativeforge.services.real_url_resolver_service import (
    reset_real_url_resolver_rate_limit,
)
from nativeforge.services.seed_source_human_activation_service import (
    NF9_AUTHORIZED_SEED_ID,
)

SCHEMA_VERSION = "nf_real_resolver_validation_gate_verification_v1"

_CONFIRMATION = {
    "operator_handle": "staging-operator",
    "human_activation_acknowledged": True,
    "public_only_acknowledged": True,
    "single_source_only_acknowledged": True,
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _test_url_fetcher(url: str, method: str) -> dict[str, Any]:
    return {
        "http_status": 200,
        "body_snippet": "public grants listing",
        "final_url": url,
    }


def verify_real_resolver_validation_gates(
    session: Any,
    *,
    org: Organization,
) -> dict[str, Any]:
    reset_real_url_resolver_rate_limit()
    reset_real_tier1_fetch_rate_limit()
    result = run_real_resolver_validation_block(
        session,
        org=org,
        operator_confirmation=_CONFIRMATION,
        url_fetcher=_test_url_fetcher,
        tier1_fetcher=fixture_tier1_live_fetch,
    )
    preview = result["real_seed_preview_report"]
    activation = result["fed001_activation"]
    tier1 = result["fed001_tier1_live_fetch"]
    checks = {
        "seed_row_count_177": preview["seed_row_count"] == 177,
        "baseline_comparison_present": "deltas" in result["baseline_comparison"],
        "fed001_activated": activation["seed_id"] == NF9_AUTHORIZED_SEED_ID,
        "exactly_one_active": activation["exactly_one_active"] is True,
        "tier1_idempotent": tier1["second_run_zero_new"] is True,
        "stop_after_fed001": result["stop_after_fed001"] is True,
    }
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "verification_passed": all(checks.values()),
            "checks": checks,
        }
    )
