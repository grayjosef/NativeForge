"""Single fetchOpportunity enrichment: funding + applicant provenance (one network call)."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from typing import Any

import sqlalchemy as sa

from nativeforge.repositories.canonical_opportunity_batch_repository import (
    NormalizedSourceObservation,
    persist_observations,
)
from nativeforge.services.canonical_intelligence_projection_service import (
    GRANTS_GOV_SOURCE,
)
from nativeforge.services.canonical_opportunity_normalizer_service import (
    normalize_record,
)
from nativeforge.services.gate173_active_corpus_projection_service import (
    project_intelligence_for_canonical_ids,
)
from nativeforge.services.grants_gov_search_api_adapter_service import (
    HttpPostJson,
    fetch_grants_gov_opportunity_detail,
)
from nativeforge.services.grants_gov_synopsis_applicant_service import (
    APPLICANT_ENRICHMENT_VERSION,
    applicant_record_has_signal,
    map_detail_applicant_to_canonical,
)
from nativeforge.services.grants_gov_synopsis_funding_service import (
    ENRICHMENT_VERSION as FUNDING_ENRICHMENT_VERSION,
)
from nativeforge.services.grants_gov_synopsis_funding_service import (
    build_fetch_opportunity_funding_record,
    funding_record_has_aggregate_signal,
    map_synopsis_funding_to_canonical,
)
from nativeforge.services.intelligence_sql_dialect_service import sql_bool_literal
from nativeforge.services.opportunity_value_funnel_service import (
    invalidate_funnel_cache,
)
from nativeforge.services.opportunity_value_intelligence_service import (
    ACTIVE_LIFECYCLE_STATES,
    CANONICAL,
    PROVENANCE,
    invalidate_public_cache,
)
from nativeforge.services.source_adapter_contract_service import identity_for_normalized

DETAIL_ENRICHMENT_VERSION = "nf_grants_gov_fetch_opportunity_detail_v1"
ADAPTER_KEY = "grants_gov_fetch_opportunity_detail"
SCHEMA_VERSION = "nf_grants_gov_detail_enrichment_v1"
DEFAULT_BOUND = 75

TERMINAL_NO_APPLICANT = "no_applicant_fields"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _lifecycle_to_status(state: str) -> str:
    if state == "forecasted":
        return "forecasted"
    if state in ("posted", "amended"):
        return "posted"
    return str(state or "unknown")


def build_fetch_opportunity_detail_record(
    *,
    detail: dict[str, Any],
    opportunity_number: str,
    source_record_id: str,
    doc_type: str,
    lifecycle_status: str,
) -> dict[str, Any]:
    base = build_fetch_opportunity_funding_record(
        detail=detail,
        opportunity_number=opportunity_number,
        source_record_id=source_record_id,
        doc_type=doc_type,
        lifecycle_status=lifecycle_status,
    )
    applicant = map_detail_applicant_to_canonical(detail)
    record: dict[str, Any] = {
        **base,
        "detail_enrichment_meta": {
            "enrichment_version": DETAIL_ENRICHMENT_VERSION,
            "funding_enrichment_version": FUNDING_ENRICHMENT_VERSION,
            "applicant_enrichment_version": APPLICANT_ENRICHMENT_VERSION,
            "grants_gov_opportunity_id": detail.get("id"),
        },
    }
    if applicant.get("eligible_applicant_codes"):
        record["eligible_applicant_codes"] = applicant["eligible_applicant_codes"]
    if applicant.get("eligibility_text"):
        record["eligibility_text"] = applicant["eligibility_text"]
    if not applicant_record_has_signal(record):
        record["applicant_enrichment_terminal"] = TERMINAL_NO_APPLICANT
        record["detail_enrichment_meta"]["applicant_outcome"] = TERMINAL_NO_APPLICANT
    else:
        record["detail_enrichment_meta"]["applicant_outcome"] = (
            "applicant_evidence_found"
        )
    return record


def detail_record_should_persist(record: dict[str, Any]) -> bool:
    return (
        funding_record_has_aggregate_signal(record)
        or applicant_record_has_signal(record)
        or record.get("applicant_enrichment_terminal") == TERMINAL_NO_APPLICANT
    )


def list_active_canonical_missing_applicant_provenance(
    connection: sa.engine.Connection,
    *,
    limit: int = DEFAULT_BOUND,
) -> list[dict[str, Any]]:
    active_list = ", ".join(f"'{s}'" for s in sorted(ACTIVE_LIFECYCLE_STATES))
    current = sql_bool_literal(connection, value=True)
    rows = connection.execute(
        sa.text(
            f"""
            SELECT c.canonical_id, c.lifecycle_state, c.doc_type,
                   rid.field_value AS source_record_id,
                   num.field_value AS opportunity_number
            FROM {CANONICAL} c
            LEFT JOIN {PROVENANCE} pcodes
              ON pcodes.canonical_id = c.canonical_id
             AND pcodes.field_name = 'eligible_applicant_codes'
             AND pcodes.is_current_canonical = {current}
            LEFT JOIN {PROVENANCE} pterm
              ON pterm.canonical_id = c.canonical_id
             AND pterm.field_name = 'applicant_enrichment_terminal'
             AND pterm.is_current_canonical = {current}
            LEFT JOIN {PROVENANCE} rid
              ON rid.canonical_id = c.canonical_id
             AND rid.field_name = 'source_record_id'
             AND rid.is_current_canonical = {current}
            LEFT JOIN {PROVENANCE} num
              ON num.canonical_id = c.canonical_id
             AND num.field_name = 'opportunity_number'
             AND num.is_current_canonical = {current}
            WHERE c.lifecycle_state IN ({active_list})
              AND (pcodes.field_value IS NULL OR TRIM(pcodes.field_value) = '')
              AND (pterm.field_value IS NULL OR pterm.field_value != :terminal)
            ORDER BY c.last_seen_at DESC
            """
        ),
        {"terminal": TERMINAL_NO_APPLICANT},
    ).mappings()
    out: list[dict[str, Any]] = []
    for row in rows:
        grants_id = str(row.get("source_record_id") or "").strip()
        if not grants_id:
            continue
        out.append(dict(row))
        if len(out) >= limit:
            break
    return out


def _canonical_binding(
    connection: sa.engine.Connection, *, canonical_id: str
) -> tuple[str, str] | None:
    row = connection.execute(
        sa.text(
            f"""
            SELECT normalized_opportunity_number, doc_type
            FROM {CANONICAL}
            WHERE canonical_id = :cid
            """
        ),
        {"cid": canonical_id},
    ).fetchone()
    if not row:
        return None
    num = str(row[0] or "").strip()
    doc = str(row[1] or "synopsis").strip() or "synopsis"
    if not num:
        return None
    return num, doc


def _build_observation(
    connection: sa.engine.Connection,
    *,
    detail: dict[str, Any],
    row: dict[str, Any],
    payload_sha256: str,
    attempt_id: str,
    stamp: dt.datetime,
) -> NormalizedSourceObservation | None:
    cid = str(row.get("canonical_id") or "").strip()
    binding = _canonical_binding(connection, canonical_id=cid) if cid else None
    grants_id = str(row.get("source_record_id") or detail.get("id") or "")
    if binding:
        opp_num, doc_type = binding
    else:
        opp_num = str(
            row.get("opportunity_number") or detail.get("opportunityNumber") or ""
        )
        doc_type = str(row.get("doc_type") or detail.get("docType") or "synopsis")
    status = _lifecycle_to_status(str(row.get("lifecycle_state") or "posted"))
    flat = build_fetch_opportunity_detail_record(
        detail=detail,
        opportunity_number=opp_num,
        source_record_id=grants_id,
        doc_type=doc_type,
        lifecycle_status=status,
    )
    if not detail_record_should_persist(flat):
        return None
    normalized = normalize_record(record=flat, adapter_key=ADAPTER_KEY)
    normalized["parser_version"] = DETAIL_ENRICHMENT_VERSION
    if not normalized.get("parseable"):
        return None
    identity = identity_for_normalized(normalized, source_id=GRANTS_GOV_SOURCE)
    return NormalizedSourceObservation(
        source_id=GRANTS_GOV_SOURCE,
        normalized=normalized,
        raw_payload_sha256=payload_sha256,
        identity=identity,
        raw_payload_attempt_id=attempt_id,
        source_authority_host="api.grants.gov",
        observed_at=stamp,
    )


def enrich_one_active_detail(
    connection: sa.engine.Connection,
    *,
    row: dict[str, Any],
    http_post: HttpPostJson | None = None,
    stamp: dt.datetime | None = None,
) -> dict[str, Any]:
    now = stamp or dt.datetime.now(dt.UTC)
    grants_id = str(row.get("source_record_id") or "")
    detail, ok = fetch_grants_gov_opportunity_detail(grants_id, http_post=http_post)
    outcome: dict[str, Any] = {
        "canonical_id": row.get("canonical_id"),
        "grants_gov_id": grants_id,
        "detail_fetch_ok": ok,
        "observation_persisted": False,
        "enrichment_version": DETAIL_ENRICHMENT_VERSION,
        "applicant_outcome": None,
        "funding_semantic": "NONE",
    }
    if not ok or not detail:
        outcome["error"] = "detail_fetch_failed"
        return outcome

    synopsis = detail.get("synopsis") or {}
    funding = map_synopsis_funding_to_canonical(synopsis)
    outcome["funding_semantic"] = funding.get("funding_semantic")
    applicant = map_detail_applicant_to_canonical(detail)
    outcome["applicant_outcome"] = (
        "applicant_evidence_found"
        if applicant_record_has_signal(
            {
                "eligible_applicant_codes": applicant.get("eligible_applicant_codes"),
                "eligibility_text": applicant.get("eligibility_text"),
            }
        )
        else TERMINAL_NO_APPLICANT
    )

    body = json.dumps(detail, sort_keys=True, default=str)
    payload_sha = _sha256(body)
    attempt_id = _sha256(f"fetch-opp-detail:{grants_id}:{payload_sha[:16]}")
    obs = _build_observation(
        connection,
        detail=detail,
        row=row,
        payload_sha256=payload_sha,
        attempt_id=attempt_id,
        stamp=now,
    )
    if obs is None:
        outcome["error"] = "parse_failed"
        return outcome

    metrics = persist_observations(connection=connection, observations=[obs])
    outcome["observation_persisted"] = True
    outcome["canonical_metrics"] = metrics
    cid = str(row.get("canonical_id") or "").strip()
    if not cid and metrics:
        cid = str(metrics[0].get("canonical_id") or "").strip()
    if cid:
        proj = project_intelligence_for_canonical_ids(
            connection, canonical_ids=[cid], dry_run=False, now=now
        )
        outcome["gate173_projection"] = {
            "projected": proj.get("projected"),
            "skipped_unchanged": proj.get("skipped_unchanged"),
        }
    return outcome


def run_bounded_active_applicant_enrichment(
    connection: sa.engine.Connection,
    *,
    limit: int = DEFAULT_BOUND,
    http_post: HttpPostJson | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    cohort = list_active_canonical_missing_applicant_provenance(connection, limit=limit)
    stats: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "enrichment_version": DETAIL_ENRICHMENT_VERSION,
        "applicant_enrichment_version": APPLICANT_ENRICHMENT_VERSION,
        "funding_enrichment_version": FUNDING_ENRICHMENT_VERSION,
        "dry_run": dry_run,
        "active_missing_applicant_provenance_count": len(cohort),
        "detail_fetch_attempted": 0,
        "detail_fetch_succeeded": 0,
        "applicant_evidence_found": 0,
        "no_applicant_fields": 0,
        "detail_fetch_failed": 0,
        "parse_failed": 0,
        "observations_persisted": 0,
        "gate173_reprojected": 0,
    }
    if dry_run:
        stats["cohort_sample"] = [
            {
                "canonical_id": r.get("canonical_id"),
                "grants_gov_id": r.get("source_record_id"),
            }
            for r in cohort[:5]
        ]
        return stats

    for row in cohort:
        stats["detail_fetch_attempted"] += 1
        result = enrich_one_active_detail(connection, row=row, http_post=http_post)
        if result.get("detail_fetch_ok"):
            stats["detail_fetch_succeeded"] += 1
        else:
            stats["detail_fetch_failed"] += 1
        if result.get("observation_persisted"):
            stats["observations_persisted"] += 1
        ao = result.get("applicant_outcome")
        if ao == "applicant_evidence_found":
            stats["applicant_evidence_found"] += 1
        elif ao == TERMINAL_NO_APPLICANT:
            stats["no_applicant_fields"] += 1
        elif result.get("error") == "parse_failed":
            stats["parse_failed"] += 1
        if result.get("gate173_projection", {}).get("projected"):
            stats["gate173_reprojected"] += 1

    invalidate_public_cache()
    invalidate_funnel_cache()
    return stats


def enrich_canonical_ids_missing_applicant(
    connection: sa.engine.Connection,
    *,
    canonical_ids: list[str],
    http_post: HttpPostJson | None = None,
    dry_run: bool = False,
    limit: int = 10,
) -> dict[str, Any]:
    """Continuity hook: bounded applicant detail enrich for explicit canonical ids."""
    if dry_run or not canonical_ids:
        return {"dry_run": dry_run, "requested": len(canonical_ids), "processed": 0}
    active_list = ", ".join(f"'{s}'" for s in sorted(ACTIVE_LIFECYCLE_STATES))
    current = sql_bool_literal(connection, value=True)
    ids = [str(c) for c in canonical_ids[:limit] if str(c).strip()]
    if not ids:
        return {"processed": 0}
    placeholders = ", ".join(f":id{i}" for i in range(len(ids)))
    params = {f"id{i}": cid for i, cid in enumerate(ids)}
    rows = connection.execute(
        sa.text(
            f"""
            SELECT c.canonical_id, c.lifecycle_state, c.doc_type,
                   rid.field_value AS source_record_id,
                   num.field_value AS opportunity_number
            FROM {CANONICAL} c
            LEFT JOIN {PROVENANCE} rid
              ON rid.canonical_id = c.canonical_id
             AND rid.field_name = 'source_record_id'
             AND rid.is_current_canonical = {current}
            LEFT JOIN {PROVENANCE} num
              ON num.canonical_id = c.canonical_id
             AND num.field_name = 'opportunity_number'
             AND num.is_current_canonical = {current}
            WHERE c.canonical_id IN ({placeholders})
              AND c.lifecycle_state IN ({active_list})
            """
        ),
        params,
    ).mappings()
    processed = 0
    for row in rows:
        enrich_one_active_detail(connection, row=dict(row), http_post=http_post)
        processed += 1
    return {"processed": processed, "limit": limit}
