"""Sprint 318 / LA: NF-12 tier-1 batch live pull orchestrator."""

from __future__ import annotations

import json
import uuid
from typing import Any

from nativeforge.db.models import is_demo_for_org_type
from nativeforge.repositories import activation_state as activation_repo
from nativeforge.services.activation_publish_gate_service import (
    assert_live_publish_permitted,
)
from nativeforge.services.corrected_catalog_posture_report_service import (
    build_corrected_catalog_posture_report,
)
from nativeforge.services.grants_gov_search_api_adapter_service import HttpPostJson
from nativeforge.services.real_resolver_validation_gate_service import (
    build_real_resolver_validation_gate_contract,
    require_real_resolver_validation_gate,
)
from nativeforge.services.real_url_resolver_service import HttpFetcher
from nativeforge.services.scaled_federal_corpus_persist_service import (
    persist_batch_fetch_to_scaled_corpus,
)
from nativeforge.services.tier1_batch_federal_activation_service import (
    Tier1BatchConfirmationBody,
    activate_tier1_public_batch_human_gate,
    parse_batch_confirmation,
    select_tier1_public_batch_seed_ids,
)
from nativeforge.services.tier1_batch_live_fetch_service import (
    run_tier1_batch_live_fetch_and_upsert,
    update_source_freshness_after_batch,
)

SCHEMA_VERSION = "nf_tier1_batch_live_pull_orchestrator_v1"
DEFAULT_BATCH_SIZE = 20


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def assert_batch_activation_publish_permitted(session: Any, *, org: Any) -> None:
    """M8 publish gate — kill switch + live_publish must permit before batch runs."""
    row = activation_repo.get_or_create_activation_state(
        session,
        organization_id=org.id,
        is_demo=is_demo_for_org_type(org.org_type),
    )
    assert_live_publish_permitted(row)


def run_tier1_batch_live_pull_block(
    session: Any,
    *,
    org: Any,
    org_id: uuid.UUID | None = None,
    operator_confirmation: dict[str, Any] | Tier1BatchConfirmationBody,
    nf_live_source_ingestion: bool = True,
    nf_real_resolver_validation: bool = True,
    url_fetcher: HttpFetcher | None = None,
    http_post: HttpPostJson | None = None,
    max_batch_size: int | None = DEFAULT_BATCH_SIZE,
    batch_offset: int = 0,
    persist_corpus: bool = True,
) -> dict[str, Any]:
    """
    Corrected posture report → M8 publish gate → batch activate public tier-1
    → live Grants.gov fetch → optional corpus persist with dedup.
    """
    require_real_resolver_validation_gate(
        nf_live_source_ingestion=nf_live_source_ingestion,
        nf_real_resolver_validation=nf_real_resolver_validation,
    )
    confirmation = parse_batch_confirmation(operator_confirmation)
    assert_batch_activation_publish_permitted(session, org=org)
    posture = build_corrected_catalog_posture_report(fetcher=url_fetcher)
    seed_ids = select_tier1_public_batch_seed_ids(
        posture["candidates"],
        max_batch_size=max_batch_size,
        batch_offset=batch_offset,
    )
    activation = activate_tier1_public_batch_human_gate(
        session,
        org=org,
        seed_ids=seed_ids,
        operator_confirmation=confirmation.model_dump(),
    )
    batch_fetch = run_tier1_batch_live_fetch_and_upsert(
        seed_ids,
        http_post=http_post,
    )
    freshness = update_source_freshness_after_batch(
        session,
        org=org,
        per_source=list(batch_fetch.get("per_source") or []),
    )
    corpus_persist = None
    if persist_corpus:
        corpus_persist = persist_batch_fetch_to_scaled_corpus(batch_fetch)
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
            "source_freshness": freshness,
            "corpus_persist": corpus_persist,
            "batch_offset": batch_offset,
            "batch_size": len(seed_ids),
            "sources_activated": activation["activated_count"],
            "real_grants_ingested": batch_fetch["real_grant_count"],
            "real_fetch_proven_live": batch_fetch["real_fetch_proven_live"],
            "empty_nofo_sources": batch_fetch["empty_seed_ids"],
            "stop_at_checkpoint": True,
            "honest_labeling_locked": True,
        }
    )
