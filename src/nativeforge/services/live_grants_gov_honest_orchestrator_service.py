"""Sprint 310: NF-11 live Grants.gov honest labeling + program-bound activation."""

from __future__ import annotations

import json
import uuid
from typing import Any

from nativeforge.services.fed_program_activation_binding_service import (
    NF11_ALLOWED_ACTIVATION_SEEDS,
    load_seed_candidate,
    resolve_live_activation_seed,
)
from nativeforge.services.grants_gov_search_api_adapter_service import HttpPostJson
from nativeforge.services.real_resolver_validation_gate_service import (
    build_real_resolver_validation_gate_contract,
    require_real_resolver_validation_gate,
)
from nativeforge.services.real_tier1_live_fetch_service import (
    Tier1LiveFetcher,
    default_real_tier1_grants_gov_fetch,
    fixture_tier1_live_fetch,
    run_real_tier1_fetch_and_upsert,
)
from nativeforge.services.seed_source_human_activation_service import (
    activate_single_seed_source_human_gate,
)

SCHEMA_VERSION = "nf_live_grants_gov_honest_orchestrator_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def run_live_grants_gov_honest_block(
    session: Any,
    *,
    org: Any,
    org_id: uuid.UUID | None = None,
    operator_confirmation: dict[str, Any],
    nf_live_source_ingestion: bool = True,
    nf_real_resolver_validation: bool = True,
    http_post: HttpPostJson | None = None,
    tier1_fetcher: Tier1LiveFetcher | None = None,
) -> dict[str, Any]:
    """
    Resolve fed-001 (15.020) vs fed-006 TEDC fallback, activate one source,
    execute search2/fetchOpportunity with honest fetch_mode labels.
    """
    require_real_resolver_validation_gate(
        nf_live_source_ingestion=nf_live_source_ingestion,
        nf_real_resolver_validation=nf_real_resolver_validation,
    )
    binding = resolve_live_activation_seed(http_post=http_post)
    chosen_seed = binding.get("seed_id")
    if not chosen_seed:
        raise ValueError(
            "no live NOFO for fed-001 (15.020) or TEDC fallback (15.148)"
        )
    activation = activate_single_seed_source_human_gate(
        session,
        org=org,
        seed_id=chosen_seed,
        operator_confirmation=operator_confirmation,
        authorized_seeds=NF11_ALLOWED_ACTIVATION_SEEDS,
    )
    source = load_seed_candidate(chosen_seed)
    if tier1_fetcher is not None:
        tier1_live = run_real_tier1_fetch_and_upsert(
            source=source,
            fetcher=tier1_fetcher,
        )
    else:

        def _live_fetch(src: dict[str, Any]) -> list[dict[str, Any]]:
            return default_real_tier1_grants_gov_fetch(src, http_post=http_post)

        tier1_live = run_real_tier1_fetch_and_upsert(
            source=source,
            fetcher=_live_fetch,
        )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "org_id": str(org_id or org.id),
            "gate": build_real_resolver_validation_gate_contract(
                nf_live_source_ingestion=nf_live_source_ingestion,
                nf_real_resolver_validation=nf_real_resolver_validation,
            ),
            "program_binding": binding,
            "activation": activation,
            "tier1_live_fetch": tier1_live,
            "exactly_one_active": activation.get("exactly_one_active") is True,
            "honest_labeling": True,
            "stop_after_one_activation": True,
        }
    )


def run_live_grants_gov_honest_block_ci(
    session: Any,
    *,
    org: Any,
    org_id: uuid.UUID | None = None,
    operator_confirmation: dict[str, Any],
    http_post: HttpPostJson | None = None,
) -> dict[str, Any]:
    """CI path: resolver uses injected http_post; tier-1 uses recorded fixture."""
    return run_live_grants_gov_honest_block(
        session,
        org=org,
        org_id=org_id,
        operator_confirmation=operator_confirmation,
        http_post=http_post,
        tier1_fetcher=fixture_tier1_live_fetch,
    )
