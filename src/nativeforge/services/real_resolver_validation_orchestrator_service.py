"""Sprint 294: real-resolver validation + first tier-1 activation orchestrator."""

from __future__ import annotations

import json
import uuid
from typing import Any

from nativeforge.services.real_resolver_seed_preview_report_service import (
    build_real_resolver_seed_preview_report,
)
from nativeforge.services.real_resolver_validation_gate_service import (
    build_real_resolver_validation_gate_contract,
    require_real_resolver_validation_gate,
)
from nativeforge.services.real_tier1_live_fetch_service import (
    Tier1LiveFetcher,
    fixture_tier1_live_fetch,
    run_real_tier1_fetch_and_upsert,
)
from nativeforge.services.real_url_resolver_service import HttpFetcher
from nativeforge.services.seed_source_human_activation_service import (
    NF9_AUTHORIZED_SEED_ID,
    activate_single_seed_source_human_gate,
)

SCHEMA_VERSION = "nf_real_resolver_validation_orchestrator_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def run_real_resolver_validation_block(
    session: Any,
    *,
    org: Any,
    org_id: uuid.UUID | None = None,
    operator_confirmation: dict[str, Any],
    nf_live_source_ingestion: bool = True,
    nf_real_resolver_validation: bool = True,
    url_fetcher: HttpFetcher | None = None,
    tier1_fetcher: Tier1LiveFetcher | None = None,
) -> dict[str, Any]:
    require_real_resolver_validation_gate(
        nf_live_source_ingestion=nf_live_source_ingestion,
        nf_real_resolver_validation=nf_real_resolver_validation,
    )
    seed_preview = build_real_resolver_seed_preview_report(fetcher=url_fetcher)
    activation = activate_single_seed_source_human_gate(
        session,
        org=org,
        seed_id=NF9_AUTHORIZED_SEED_ID,
        operator_confirmation=operator_confirmation,
    )
    tier1_live = run_real_tier1_fetch_and_upsert(
        fetcher=tier1_fetcher or fixture_tier1_live_fetch,
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "org_id": str(org_id or org.id),
            "gate": build_real_resolver_validation_gate_contract(
                nf_live_source_ingestion=nf_live_source_ingestion,
                nf_real_resolver_validation=nf_real_resolver_validation,
            ),
            "real_seed_preview_report": seed_preview,
            "baseline_comparison": seed_preview["baseline_comparison"],
            "fed001_activation": activation,
            "fed001_tier1_live_fetch": tier1_live,
            "stop_after_fed001": True,
            "no_other_sources_activated": True,
        }
    )
