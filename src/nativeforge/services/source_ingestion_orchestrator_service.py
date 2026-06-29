"""Sprint 268: live source ingestion orchestrator (seed → quality → tier routing)."""

from __future__ import annotations

import json
import uuid
from typing import Any

from nativeforge.domain.enums import (
    OpportunitySourceType,
    OpportunityVerificationStatus,
    SourceCheckMethod,
    SourcePriorityLevel,
    SourceReliabilityRating,
)
from nativeforge.services import opportunity_discovery_service as ods
from nativeforge.services.source_ingestion_plan_gate_service import (
    build_plan_gate_contract,
)
from nativeforge.services.source_ingestion_seed_loader_service import (
    build_source_seed_candidate_bundle,
)
from nativeforge.services.source_ingestion_tier2_state_adapter_service import (
    build_tier2_registry_from_seed,
)
from nativeforge.services.source_ingestion_url_quality_service import (
    verify_seed_candidate_batch,
)

SCHEMA_VERSION = "nf_source_ingestion_orchestrator_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _candidate_to_source_payload(
    candidate: dict[str, Any],
) -> ods.OpportunitySourcePayload:
    st = str(candidate.get("source_type") or "federal")
    try:
        source_type = OpportunitySourceType(st)
    except ValueError:
        source_type = OpportunitySourceType.other
    notes = str(candidate.get("native_relevance_notes") or "") or None
    return ods.OpportunitySourcePayload(
        source_name=str(candidate["source_name"]),
        source_type=source_type,
        source_url=str(candidate.get("source_url") or ""),
        publisher_name=str(candidate.get("publisher_name") or "") or None,
        description=notes,
        native_relevance_notes=notes,
        reliability_rating=SourceReliabilityRating.unknown,
        verification_status=OpportunityVerificationStatus.unverified,
        is_active=False,
        check_method=SourceCheckMethod.web_page,
        priority_level=SourcePriorityLevel.medium,
    )


def run_source_seed_ingestion_preview(
    *,
    org_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Load seed, verify quality, build tier registries — no activation, no scrape."""
    bundle = build_source_seed_candidate_bundle()
    candidates = bundle["candidates"]
    quality = verify_seed_candidate_batch(candidates)
    tier2 = build_tier2_registry_from_seed(candidates)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "org_id": str(org_id) if org_id else None,
            "plan_gate": build_plan_gate_contract(),
            "seed_bundle": {
                "seed_row_count": bundle["seed_row_count"],
                "tier_counts": bundle["tier_counts"],
            },
            "quality_summary": {
                "result_count": quality["result_count"],
                "public_count": quality["public_count"],
                "blocked_posture_count": quality["blocked_posture_count"],
            },
            "tier2_registry": tier2,
            "all_candidates_inactive": True,
            "human_activation_required": True,
            "no_opportunity_scrape_without_activation": True,
        }
    )


def persist_seed_candidates_to_registry(
    session: Any,
    *,
    org: Any,
    candidates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Upsert inactive registry rows from seed candidates (idempotent by url)."""
    from nativeforge.repositories import opportunity_sources as os_repo

    rows_in = candidates or build_source_seed_candidate_bundle()["candidates"]
    existing_rows = os_repo.list_opportunity_sources_for_org(
        session=session,
        org_id=org.id,
        org_type=org.org_type,
    )
    known_urls = {r.source_url for r in existing_rows if r.source_url}
    inserted = 0
    skipped = 0
    for cand in rows_in:
        payload = _candidate_to_source_payload(cand)
        url = payload.source_url
        if url in known_urls:
            skipped += 1
            continue
        ods.create_opportunity_source(session, org=org, body=payload)
        known_urls.add(url)
        inserted += 1
    return {
        "inserted": inserted,
        "skipped": skipped,
        "all_inactive": True,
    }
