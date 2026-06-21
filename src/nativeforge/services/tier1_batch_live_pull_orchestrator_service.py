"""Sprint 318: NF-12 tier-1 batch live pull orchestrator — STOP at checkpoint."""

from __future__ import annotations

import json
import uuid
from typing import Any

from nativeforge.services.corrected_catalog_posture_report_service import (
    build_corrected_catalog_posture_report,
)
from nativeforge.services.grants_gov_search_api_adapter_service import HttpPostJson
from nativeforge.services.real_resolver_validation_gate_service import (
    build_real_resolver_validation_gate_contract,
    require_real_resolver_validation_gate,
)
from nativeforge.services.real_url_resolver_service import HttpFetcher
from nativeforge.services.tier1_batch_federal_activation_service import (
    activate_tier1_public_batch_human_gate,
    select_tier1_public_batch_seed_ids,
)
from nativeforge.services.tier1_batch_live_fetch_service import (
    run_tier1_batch_live_fetch_and_upsert,
)

SCHEMA_VERSION = "nf_tier1_batch_live_pull_orchestrator_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def run_tier1_batch_live_pull_block(
    session: Any,
    *,
    org: Any,
    org_id: uuid.UUID | None = None,
    operator_confirmation: dict[str, Any],
    nf_live_source_ingestion: bool = True,
    nf_real_resolver_validation: bool = True,
    url_fetcher: HttpFetcher | None = None,
    http_post: HttpPostJson | None = None,
    max_batch_size: int | None = None,
) -> dict[str, Any]:
    """
    Corrected posture report → batch activate public tier-1 → live Grants.gov fetch.
    Surfaces empty honestly; counts REAL grants (real_fetch proven live).
    """
    require_real_resolver_validation_gate(
        nf_live_source_ingestion=nf_live_source_ingestion,
        nf_real_resolver_validation=nf_real_resolver_validation,
    )
    posture = build_corrected_catalog_posture_report(fetcher=url_fetcher)
    seed_ids = select_tier1_public_batch_seed_ids(
        posture["candidates"],
        max_batch_size=max_batch_size,
    )
    activation = activate_tier1_public_batch_human_gate(
        session,
        org=org,
        seed_ids=seed_ids,
        operator_confirmation=operator_confirmation,
    )
    batch_fetch = run_tier1_batch_live_fetch_and_upsert(
        seed_ids,
        http_post=http_post,
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "org_id": str(org_id or org.id),
            "gate": build_real_resolver_validation_gate_contract(
                nf_live_source_ingestion=nf_live_source_ingestion,
                nf_real_resolver_validation=nf_real_resolver_validation,
            ),
            "corrected_posture_report": posture,
            "batch_activation": activation,
            "batch_live_fetch": batch_fetch,
            "sources_activated": activation["activated_count"],
            "real_grants_ingested": batch_fetch["real_grant_count"],
            "real_fetch_proven_live": batch_fetch["real_fetch_proven_live"],
            "empty_nofo_sources": batch_fetch["empty_seed_ids"],
            "stop_at_checkpoint": True,
            "honest_labeling_locked": True,
        }
    )
