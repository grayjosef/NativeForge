"""Bounded Grants.gov detail enrichment for active canonical funding provenance (OVI V1.1)."""

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
from nativeforge.services.grants_gov_search_api_adapter_service import (
    HttpPostJson,
    fetch_grants_gov_opportunity_detail,
)
from nativeforge.services.grants_gov_synopsis_funding_service import (
    ADAPTER_KEY,
    ENRICHMENT_VERSION,
    build_fetch_opportunity_funding_record,
    funding_record_has_aggregate_signal,
    map_synopsis_funding_to_canonical,
)
from nativeforge.services.intelligence_sql_dialect_service import sql_bool_literal
from nativeforge.services.gate173_active_corpus_projection_service import (
    project_intelligence_for_canonical_ids,
)
from nativeforge.services.opportunity_value_funnel_service import invalidate_funnel_cache
from nativeforge.services.opportunity_value_intelligence_service import (
    ACTIVE_LIFECYCLE_STATES,
    CANONICAL,
    FUNDING_MAX,
    FUNDING_MIN,
    PROVENANCE,
    VALUE_KNOWN,
    _select_monetary_value,
    compute_active_opportunity_value_aggregate,
    invalidate_public_cache,
)
from nativeforge.services.source_adapter_contract_service import identity_for_normalized

SCHEMA_VERSION = "nf_grants_gov_active_funding_enrichment_v1"
DEFAULT_BOUND = 75


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _lifecycle_to_status(state: str) -> str:
    if state == "forecasted":
        return "forecasted"
    if state in ("posted", "amended"):
        return "posted"
    return str(state or "unknown")


def list_active_canonical_missing_known_funding(
    connection: sa.engine.Connection,
    *,
    limit: int = DEFAULT_BOUND,
) -> list[dict[str, Any]]:
    """Active opportunities where V1 selector is not KNOWN."""
    active_list = ", ".join(f"'{s}'" for s in sorted(ACTIVE_LIFECYCLE_STATES))
    current = sql_bool_literal(connection, value=True)
    rows = connection.execute(
        sa.text(
            f"""
            SELECT c.canonical_id, c.lifecycle_state, c.doc_type,
                   pmin.field_value AS min_val, pmax.field_value AS max_val,
                   c.has_field_conflicts,
                   pmin.conflict_group AS min_conflict,
                   pmax.conflict_group AS max_conflict,
                   rid.field_value AS source_record_id,
                   num.field_value AS opportunity_number
            FROM {CANONICAL} c
            LEFT JOIN {PROVENANCE} pmin
              ON pmin.canonical_id = c.canonical_id
             AND pmin.field_name = :fmin AND pmin.is_current_canonical = {current}
            LEFT JOIN {PROVENANCE} pmax
              ON pmax.canonical_id = c.canonical_id
             AND pmax.field_name = :fmax AND pmax.is_current_canonical = {current}
            LEFT JOIN {PROVENANCE} rid
              ON rid.canonical_id = c.canonical_id
             AND rid.field_name = 'source_record_id'
             AND rid.is_current_canonical = {current}
            LEFT JOIN {PROVENANCE} num
              ON num.canonical_id = c.canonical_id
             AND num.field_name = 'opportunity_number'
             AND num.is_current_canonical = {current}
            WHERE c.lifecycle_state IN ({active_list})
            ORDER BY c.last_seen_at DESC
            """
        ),
        {"fmin": FUNDING_MIN, "fmax": FUNDING_MAX},
    ).mappings()
    missing: list[dict[str, Any]] = []
    for row in rows:
        sel = _select_monetary_value(
            min_raw=row.get("min_val"),
            max_raw=row.get("max_val"),
            has_field_conflicts=bool(row.get("has_field_conflicts")),
            min_conflict=row.get("min_conflict"),
            max_conflict=row.get("max_conflict"),
        )
        if sel["value_status"] == VALUE_KNOWN:
            continue
        grants_id = str(row.get("source_record_id") or "").strip()
        if not grants_id:
            continue
        missing.append(dict(row))
        if len(missing) >= limit:
            break
    return missing


def _build_observation(
    *,
    detail: dict[str, Any],
    row: dict[str, Any],
    payload_sha256: str,
    attempt_id: str,
    stamp: dt.datetime,
) -> NormalizedSourceObservation | None:
    opp_num = str(row.get("opportunity_number") or detail.get("opportunityNumber") or "")
    grants_id = str(row.get("source_record_id") or detail.get("id") or "")
    doc_type = str(row.get("doc_type") or detail.get("docType") or "synopsis")
    status = _lifecycle_to_status(str(row.get("lifecycle_state") or "posted"))
    flat = build_fetch_opportunity_funding_record(
        detail=detail,
        opportunity_number=opp_num,
        source_record_id=grants_id,
        doc_type=doc_type,
        lifecycle_status=status,
    )
    if not funding_record_has_aggregate_signal(flat):
        return None
    normalized = normalize_record(record=flat, adapter_key=ADAPTER_KEY)
    normalized["parser_version"] = ENRICHMENT_VERSION
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


def enrich_one_active_opportunity(
    connection: sa.engine.Connection,
    *,
    row: dict[str, Any],
    http_post: HttpPostJson | None = None,
    stamp: dt.datetime | None = None,
) -> dict[str, Any]:
    """Fetch detail for one canonical row; persist funding provenance if defensible."""
    now = stamp or dt.datetime.now(dt.UTC)
    grants_id = str(row.get("source_record_id") or "")
    detail, ok = fetch_grants_gov_opportunity_detail(grants_id, http_post=http_post)
    outcome: dict[str, Any] = {
        "canonical_id": row.get("canonical_id"),
        "grants_gov_id": grants_id,
        "detail_fetch_ok": ok,
        "observation_persisted": False,
        "funding_semantic": "NONE",
    }
    if not ok or not detail:
        outcome["error"] = "detail_fetch_failed"
        return outcome

    synopsis = detail.get("synopsis") or {}
    funding = map_synopsis_funding_to_canonical(synopsis)
    outcome["funding_semantic"] = funding.get("funding_semantic")

    body = json.dumps(detail, sort_keys=True, default=str)
    payload_sha = _sha256(body)
    attempt_id = _sha256(f"fetch-opp-funding:{grants_id}:{payload_sha[:16]}")
    obs = _build_observation(
        detail=detail,
        row=row,
        payload_sha256=payload_sha,
        attempt_id=attempt_id,
        stamp=now,
    )
    if obs is None:
        outcome["error"] = "no_aggregate_signal"
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


def run_bounded_active_funding_enrichment(
    connection: sa.engine.Connection,
    *,
    limit: int = DEFAULT_BOUND,
    http_post: HttpPostJson | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Enrich up to ``limit`` active opportunities missing known funding value."""
    before = compute_active_opportunity_value_aggregate(connection, use_cache=False)
    cohort = list_active_canonical_missing_known_funding(connection, limit=limit)
    stats = {
        "schema_version": SCHEMA_VERSION,
        "enrichment_version": ENRICHMENT_VERSION,
        "methodology_version": before.get("methodology_version"),
        "dry_run": dry_run,
        "active_missing_value_count": len(cohort),
        "detail_fetch_attempted": 0,
        "detail_fetch_succeeded": 0,
        "value_observations_created": 0,
        "parse_failures": 0,
        "source_errors": 0,
        "conflicts_created": 0,
        "before": {
            "known_value_count": before.get("known_value_count"),
            "unknown_value_count": before.get("unknown_value_count"),
            "known_value_coverage_pct": before.get("known_value_coverage_pct"),
        },
    }
    if dry_run:
        stats["cohort_sample"] = [
            {"canonical_id": r.get("canonical_id"), "grants_gov_id": r.get("source_record_id")}
            for r in cohort[:5]
        ]
        return stats

    for row in cohort:
        stats["detail_fetch_attempted"] += 1
        result = enrich_one_active_opportunity(connection, row=row, http_post=http_post)
        if result.get("detail_fetch_ok"):
            stats["detail_fetch_succeeded"] += 1
        else:
            stats["source_errors"] += 1
        if result.get("observation_persisted"):
            stats["value_observations_created"] += 1
        elif result.get("error") == "no_aggregate_signal":
            stats["parse_failures"] += 1

    invalidate_public_cache()
    invalidate_funnel_cache()
    after = compute_active_opportunity_value_aggregate(connection, use_cache=False)
    stats["after"] = {
        "known_value_count": after.get("known_value_count"),
        "unknown_value_count": after.get("unknown_value_count"),
        "known_value_coverage_pct": after.get("known_value_coverage_pct"),
        "active_known_value_total_usd": after.get("active_known_value_total_usd"),
        "totals_by_currency": after.get("totals_by_currency"),
    }
    return stats


def source_priority_policy() -> dict[str, Any]:
    return {
        "enrichment_version": ENRICHMENT_VERSION,
        "precedence": [
            "grants_gov_fetch_opportunity synopsis structured fields (detail)",
            "search2 hit funding fields (not supported by search2 normalizer today)",
            "NOFO/document extraction (not wired in V1.1 — Gate 175 pilot only)",
        ],
        "conflict": "canonical batch repository marks disagreeing current provenance",
    }
