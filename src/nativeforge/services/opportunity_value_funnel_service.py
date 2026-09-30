"""Opportunity value funnel slices (V2) — HABEAS DATA stage + value provenance."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import sqlalchemy as sa

from nativeforge.services.canonical_intelligence_projection_service import (
    GRANTS_GOV_SOURCE,
    resolve_canonical_id_for_spark,
)
from nativeforge.services.eligibility_requirement_model_service import (
    CONDITIONALLY_ELIGIBLE,
    ELIGIBLE,
    INELIGIBLE,
    LIKELY_ELIGIBLE,
    REVIEW_REQUIRED,
)
from nativeforge.services.eligibility_requirement_model_service import (
    UNKNOWN as ELIG_UNKNOWN,
)
from nativeforge.services.intelligence_sql_dialect_service import is_current_active_sql
from nativeforge.services.native_relevance_ontology_service import APPLICANT_RELEVANT
from nativeforge.services.opportunity_value_intelligence_service import (
    DEFAULT_CURRENCY,
    VALUE_CONFLICTING,
    VALUE_KNOWN,
    compute_active_opportunity_value_aggregate,
    enumerate_active_opportunity_values,
)
from nativeforge.services.opportunity_value_intelligence_service import (
    METHODOLOGY_VERSION as VALUE_METHODOLOGY_VERSION,
)

FUNNEL_METHODOLOGY_VERSION = "nativeforge.opportunity_value_funnel.v1"
SCHEMA_VERSION = "nf_opportunity_value_funnel_v1"

ASSESSMENTS = "nf_opportunity_relevance_assessments"
MATCHES = "nf_tenant_eligibility_matches"

_ELIGIBLE = frozenset({ELIGIBLE, LIKELY_ELIGIBLE})
_CONDITIONAL = frozenset({CONDITIONALLY_ELIGIBLE})
_INELIGIBLE = frozenset({INELIGIBLE})
_UNKNOWN_ELIG = frozenset({ELIG_UNKNOWN, REVIEW_REQUIRED})

_PURSUING_STATUSES = frozenset({"active", "paused"})
_SUBMITTED_STATUS = "submitted"

_corpus_cache: dict[str, Any] = {"expires_at": None, "payload": None}
_org_cache: dict[str, Any] = {}
_CACHE_TTL_SECONDS = 120


def funnel_stage_definitions() -> dict[str, Any]:
    return {
        "funnel_methodology_version": FUNNEL_METHODOLOGY_VERSION,
        "value_methodology_version": VALUE_METHODOLOGY_VERSION,
        "stages_are_additive": False,
        "note": "Stages are slices/segments; overlapping membership is legitimate.",
        "active": {
            "scope": "corpus",
            "rule": "nf_canonical_opportunities lifecycle in posted|amended|forecasted",
        },
        "native_relevant": {
            "scope": "corpus",
            "rule": "current Gate 173 assessment relevance_class in APPLICANT_RELEVANT",
            "source": ASSESSMENTS,
        },
        "eligibility": {
            "scope": "organization",
            "rule": "current Gate 174 nf_tenant_eligibility_matches.eligibility_result",
            "source": MATCHES,
            "visibility": "eligibility does not gate discovery feed",
        },
        "pursuing": {
            "scope": "organization",
            "rule": "nf_grant_pursuits.status in active|paused, linked via grant_spark",
        },
        "submitted": {
            "scope": "organization",
            "rule": "nf_grant_pursuits.status = submitted (workflow, not funder confirmation)",
        },
    }


def _metrics_from_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    totals: dict[str, Decimal] = {}
    known = unknown = conflicting = 0
    for rec in records:
        status = rec["value_status"]
        if status == VALUE_KNOWN and rec.get("selected_amount") is not None:
            known += 1
            cur = str(rec.get("currency") or DEFAULT_CURRENCY)
            totals[cur] = totals.get(cur, Decimal(0)) + rec["selected_amount"]
        elif status == VALUE_CONFLICTING:
            conflicting += 1
        else:
            unknown += 1
    count = len(records)
    coverage = round(100.0 * known / count, 2) if count else 0.0
    totals_by_currency = {
        cur: str(amt.quantize(Decimal("0.01"))) for cur, amt in sorted(totals.items())
    }
    usd = totals.get(DEFAULT_CURRENCY)
    return {
        "count": count,
        "known_count": known,
        "unknown_count": unknown,
        "conflicting_count": conflicting,
        "known_value_coverage_pct": coverage,
        "totals_by_currency": totals_by_currency,
        "known_value_total_usd": str(usd.quantize(Decimal("0.01"))) if usd is not None else None,
    }


def _load_current_relevance_map(
    connection: sa.engine.Connection,
) -> dict[str, str]:
    current = is_current_active_sql(connection)
    rows = connection.execute(
        sa.text(
            f"SELECT canonical_id, relevance_class FROM {ASSESSMENTS} WHERE {current}"
        )
    ).fetchall()
    return {str(r[0]): str(r[1]) for r in rows}


def _load_current_eligibility_map(
    connection: sa.engine.Connection, *, tenant_id: str
) -> dict[str, str]:
    current = is_current_active_sql(connection)
    rows = connection.execute(
        sa.text(
            f"SELECT canonical_id, eligibility_result FROM {MATCHES} "
            f"WHERE tenant_id = :tid AND {current}"
        ),
        {"tid": tenant_id},
    ).fetchall()
    return {str(r[0]): str(r[1]) for r in rows}


def _filter_relevance(
    records: list[dict[str, Any]], relevance: dict[str, str]
) -> list[dict[str, Any]]:
    classes = set(APPLICANT_RELEVANT)
    return [
        r
        for r in records
        if relevance.get(str(r["canonical_id"])) in classes
    ]


def _filter_eligibility(
    records: list[dict[str, Any]], elig: dict[str, str], bucket: frozenset[str]
) -> list[dict[str, Any]]:
    return [
        r
        for r in records
        if elig.get(str(r["canonical_id"])) in bucket
    ]


def _value_by_canonical(
    records: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {str(r["canonical_id"]): r for r in records}


def _pursuit_canonical_ids(
    connection: sa.engine.Connection,
    *,
    organization_id: str,
    statuses: frozenset[str],
) -> list[str]:
    rows = connection.execute(
        sa.text(
            """
            SELECT s.source_id, s.opportunity_number, p.status
            FROM nf_grant_pursuits p
            JOIN nf_grant_sparks s ON s.id = p.grant_spark_id
            WHERE p.organization_id = :org
            """
        ),
        {"org": organization_id},
    ).fetchall()
    out: list[str] = []
    for source_id, opp_num, status in rows:
        if str(status) not in statuses:
            continue
        cid = resolve_canonical_id_for_spark(
            connection,
            source_record_id=str(source_id or ""),
            opportunity_number=str(opp_num or "") or None,
            source_id=GRANTS_GOV_SOURCE,
        )
        if cid:
            out.append(str(cid))
    return out


def compute_corpus_funnel_aggregate(
    connection: sa.engine.Connection,
    *,
    use_cache: bool = True,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    stamp = now or dt.datetime.now(dt.UTC)
    if use_cache and _corpus_cache.get("payload") and _corpus_cache.get("expires_at"):
        if stamp < _corpus_cache["expires_at"]:
            return dict(_corpus_cache["payload"])

    active_agg = compute_active_opportunity_value_aggregate(
        connection, use_cache=use_cache, now=stamp
    )
    records = enumerate_active_opportunity_values(connection)
    relevance = _load_current_relevance_map(connection)
    native_records = _filter_relevance(records, relevance)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "funnel_methodology_version": FUNNEL_METHODOLOGY_VERSION,
        "value_methodology_version": VALUE_METHODOLOGY_VERSION,
        "calculated_at": stamp.isoformat(),
        "stages_are_additive": False,
        "habeas_data": "no material intelligence claim without retrievable evidence",
        "stage_definitions": funnel_stage_definitions(),
        "stages": {
            "active": {
                "scope": "corpus",
                "count": active_agg["active_opportunity_count"],
                "known_count": active_agg["known_value_count"],
                "unknown_count": active_agg["unknown_value_count"],
                "conflicting_count": active_agg["conflicting_value_count"],
                "known_value_coverage_pct": active_agg["known_value_coverage_pct"],
                "totals_by_currency": active_agg.get("totals_by_currency") or {},
                "known_value_total_usd": active_agg.get("active_known_value_total_usd"),
                "stage_provenance": "nf_canonical_opportunities.lifecycle_state",
                "value_provenance": "nf_opportunity_field_provenance",
            },
            "native_relevant": {
                "scope": "corpus",
                "supported": bool(relevance),
                "relevance_source": ASSESSMENTS,
                **_metrics_from_records(native_records),
                "stage_provenance": f"current {ASSESSMENTS}.relevance_class in APPLICANT_RELEVANT",
                "value_provenance": "nf_opportunity_field_provenance",
            },
        },
        "support": {
            "blocked_value": False,
            "blocked_value_reason": "no persisted deterministic block-reason dimension in V2",
            "submitted": False,
            "submitted_reason": "exposed on org funnel only when pursuits exist",
            "awarded": False,
            "awarded_reason": "nf_awarded_grants not linked to canonical value observations",
        },
    }

    if use_cache:
        _corpus_cache["payload"] = payload
        _corpus_cache["expires_at"] = stamp + dt.timedelta(seconds=_CACHE_TTL_SECONDS)
    return payload


def compute_org_funnel_aggregate(
    connection: sa.engine.Connection,
    *,
    organization_id: str,
    tenant_id: str | None = None,
    use_cache: bool = True,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    tid = tenant_id or organization_id
    stamp = now or dt.datetime.now(dt.UTC)
    cache_key = f"{organization_id}:{tid}"
    if use_cache and cache_key in _org_cache:
        entry = _org_cache[cache_key]
        if stamp < entry.get("expires_at"):
            return dict(entry["payload"])

    corpus = compute_corpus_funnel_aggregate(connection, use_cache=use_cache, now=stamp)
    records = enumerate_active_opportunity_values(connection)
    by_id = _value_by_canonical(records)
    elig = _load_current_eligibility_map(connection, tenant_id=tid)

    def elig_stage(name: str, bucket: frozenset[str]) -> dict[str, Any]:
        slice_recs = _filter_eligibility(records, elig, bucket)
        return {
            "scope": "organization",
            "supported": True,
            "eligibility_source": MATCHES,
            "membership_rule": f"current eligibility_result in {sorted(bucket)}",
            **_metrics_from_records(slice_recs),
            "stage_provenance": f"current {MATCHES} for tenant_id",
            "value_provenance": "nf_opportunity_field_provenance",
        }

    pursuing_ids = _pursuit_canonical_ids(
        connection, organization_id=organization_id, statuses=_PURSUING_STATUSES
    )
    submitted_ids = _pursuit_canonical_ids(
        connection, organization_id=organization_id, statuses=frozenset({_SUBMITTED_STATUS})
    )
    pursuing_recs = [by_id[cid] for cid in pursuing_ids if cid in by_id]
    submitted_recs = [by_id[cid] for cid in submitted_ids if cid in by_id]

    payload = {
        **corpus,
        "organization_id": organization_id,
        "tenant_id": tid,
        "stages": {
            **corpus["stages"],
            "eligibility": {
                "scope": "organization",
                "supported": True,
                "partitions_are_exclusive_within_matched": True,
                "note": "Only active opportunities with a current tenant match are classified",
                "eligible": elig_stage("eligible", _ELIGIBLE),
                "conditionally_eligible": elig_stage("conditionally_eligible", _CONDITIONAL),
                "ineligible": elig_stage("ineligible", _INELIGIBLE),
                "unknown_eligibility": elig_stage("unknown_eligibility", _UNKNOWN_ELIG),
                "unmatched_active_count": sum(
                    1 for r in records if str(r["canonical_id"]) not in elig
                ),
            },
            "pursuing": {
                "scope": "organization",
                "supported": True,
                "membership_rule": f"nf_grant_pursuits.status in {sorted(_PURSUING_STATUSES)}",
                **_metrics_from_records(pursuing_recs),
                "stage_provenance": "nf_grant_pursuits + canonical resolution",
                "value_provenance": "nf_opportunity_field_provenance",
            },
            "submitted": {
                "scope": "organization",
                "supported": True,
                "membership_rule": f"nf_grant_pursuits.status = {_SUBMITTED_STATUS}",
                **_metrics_from_records(submitted_recs),
                "stage_provenance": "nf_grant_pursuits workflow status",
                "value_provenance": "nf_opportunity_field_provenance",
                "caution": "workflow submitted, not funder award confirmation",
            },
            "awarded": {
                "scope": "organization",
                "supported": False,
                "reason": "award dollars not joined to canonical opportunity value observations",
            },
        },
        "support": {
            **corpus["support"],
            "submitted": True,
            "submitted_scope": "organization",
            "pursuing": True,
        },
    }

    if use_cache:
        _org_cache[cache_key] = {
            "payload": payload,
            "expires_at": stamp + dt.timedelta(seconds=_CACHE_TTL_SECONDS),
        }
    return payload


def public_corpus_funnel_view(full: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": full["schema_version"],
        "funnel_methodology_version": full["funnel_methodology_version"],
        "value_methodology_version": full["value_methodology_version"],
        "calculated_at": full["calculated_at"],
        "stages_are_additive": False,
        "label": "known funding value by corpus stage",
        "stages": {
            "active": full["stages"]["active"],
            "native_relevant": full["stages"]["native_relevant"],
        },
        "support": full.get("support"),
        "habeas_data": full.get("habeas_data"),
    }


def invalidate_funnel_cache() -> None:
    _corpus_cache["expires_at"] = None
    _corpus_cache["payload"] = None
    _org_cache.clear()
