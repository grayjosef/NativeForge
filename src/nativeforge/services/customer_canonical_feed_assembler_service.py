"""Assemble Gate 179 feed items from canonical graph + Gates 173–175 intelligence."""

from __future__ import annotations

import json
import uuid
from typing import Any

import sqlalchemy as sa

from nativeforge.repositories.opportunity_identity_repository import (
    resolve_logical_canonical_ids,
)
from nativeforge.services.customer_decision_service import NEW
from nativeforge.services.customer_opportunity_feed_service import (
    ELIGIBILITY_APPEARS_ELIGIBLE,
    ELIGIBILITY_APPEARS_INELIGIBLE,
    ELIGIBILITY_CONDITIONAL,
    ELIGIBILITY_NOT_ASSESSED,
    ELIGIBILITY_UNCERTAIN,
    RELEVANCE_BROADLY_ELIGIBLE,
    RELEVANCE_NATIVE_ELIGIBLE,
    RELEVANCE_NATIVE_SPECIFIC,
    RELEVANCE_NOT_RELEVANT,
    RELEVANCE_UNCERTAIN,
    build_feed,
    build_recommendation,
    recommendation_invariant_failures,
)
from nativeforge.services.customer_repository_service import (
    DECISIONS,
    q_my_dismissed,
)
from nativeforge.services.intelligence_sql_dialect_service import is_current_active_sql
from nativeforge.services.eligibility_intelligence_repository_service import (
    load_current_match,
    load_current_requirements,
)
from nativeforge.services.native_relevance_ontology_service import (
    BROADLY_ELIGIBLE_NATIVE_RELEVANT,
    INDIRECTLY_RELEVANT,
    NATIVE_BENEFICIARY_RELEVANT,
    NATIVE_ELIGIBLE,
    NATIVE_PRIORITY,
    NATIVE_SPECIFIC,
    NOT_RELEVANT,
)
from nativeforge.services.native_relevance_ontology_service import (
    UNCERTAIN as REL_UNCERTAIN,
)
from nativeforge.services.native_relevance_repository_service import (
    ASSESSMENTS,
    EVIDENCE,
)
from nativeforge.services.opportunity_change_read_model_service import (
    build_customer_change_feed,
)

SCHEMA_VERSION = "nf_customer_canonical_feed_assembler_v1"
CANONICAL = "nf_canonical_opportunities"
AUTHORITATIVE_LAYER = "gate173_174_175_persisted"

_RELEVANCE_TO_FEED: dict[str, str] = {
    NATIVE_SPECIFIC: RELEVANCE_NATIVE_SPECIFIC,
    NATIVE_PRIORITY: RELEVANCE_NATIVE_SPECIFIC,
    NATIVE_ELIGIBLE: RELEVANCE_NATIVE_ELIGIBLE,
    BROADLY_ELIGIBLE_NATIVE_RELEVANT: RELEVANCE_BROADLY_ELIGIBLE,
    NATIVE_BENEFICIARY_RELEVANT: RELEVANCE_BROADLY_ELIGIBLE,
    INDIRECTLY_RELEVANT: RELEVANCE_BROADLY_ELIGIBLE,
    REL_UNCERTAIN: RELEVANCE_UNCERTAIN,
    NOT_RELEVANT: RELEVANCE_NOT_RELEVANT,
}

_ELIGIBILITY_TO_FEED: dict[str, str] = {
    "ELIGIBLE": ELIGIBILITY_APPEARS_ELIGIBLE,
    "LIKELY_ELIGIBLE": ELIGIBILITY_APPEARS_ELIGIBLE,
    "CONDITIONALLY_ELIGIBLE": ELIGIBILITY_CONDITIONAL,
    "INELIGIBLE": ELIGIBILITY_APPEARS_INELIGIBLE,
    "UNKNOWN": ELIGIBILITY_UNCERTAIN,
    "REVIEW_REQUIRED": ELIGIBILITY_UNCERTAIN,
}


def _load_assessment(
    connection: sa.engine.Connection, *, canonical_id: str
) -> dict[str, Any] | None:
    row = connection.execute(
        sa.text(
            f"SELECT relevance_class, confidence, review_required, reasons_json, "
            f"candidate_state, evidence_count, computed_at "
            f"FROM {ASSESSMENTS} WHERE canonical_id = :cid AND "
            f"{is_current_active_sql(connection)}"
        ),
        {"cid": canonical_id},
    ).fetchone()
    if not row:
        return None
    reasons_raw = row[3]
    try:
        reasons = json.loads(reasons_raw) if reasons_raw else {}
    except json.JSONDecodeError:
        reasons = {"items": [str(reasons_raw)]}
    return {
        "relevance_class": row[0],
        "confidence": row[1],
        "review_required": bool(row[2]),
        "reasons": reasons,
        "candidate_state": row[4],
        "evidence_count": row[5],
        "computed_at": row[6],
    }


def _load_evidence_ids(
    connection: sa.engine.Connection, *, canonical_id: str
) -> list[str]:
    rows = connection.execute(
        sa.text(f"SELECT evidence_id FROM {EVIDENCE} WHERE canonical_id = :cid"),
        {"cid": canonical_id},
    ).fetchall()
    return [str(r[0]) for r in rows]


def _map_relevance(
    assessment: dict[str, Any] | None,
) -> dict[str, Any]:
    if not assessment:
        return {
            "relevance_class": RELEVANCE_UNCERTAIN,
            "why": "authoritative Native relevance has not been projected yet",
            "evidence_ids": [],
            "unknowns": ["native_relevance_not_assessed"],
        }
    raw = str(assessment.get("relevance_class") or REL_UNCERTAIN)
    feed_class = _RELEVANCE_TO_FEED.get(raw, RELEVANCE_UNCERTAIN)
    reasons = assessment.get("reasons") or {}
    why = None
    if isinstance(reasons, dict):
        items = reasons.get("items") or []
        if items:
            why = str(items[0])
    return {
        "relevance_class": feed_class,
        "why": why or f"classified as {raw} from persisted Gate 173 evidence",
        "evidence_ids": [],
        "unknowns": ["native_relevance_undecided"]
        if feed_class == RELEVANCE_UNCERTAIN
        else [],
        "authoritative_classification": raw,
        "confidence": assessment.get("confidence"),
        "review_required": assessment.get("review_required"),
    }


def _map_eligibility(
    connection: sa.engine.Connection,
    *,
    canonical_id: str,
    tenant_id: str | None,
) -> dict[str, Any]:
    requirements = load_current_requirements(connection, canonical_id=canonical_id)
    match = (
        load_current_match(connection, canonical_id=canonical_id, tenant_id=tenant_id)
        if tenant_id
        else None
    )
    if match:
        result = str(match.get("eligibility_result") or "UNKNOWN")
        view = _ELIGIBILITY_TO_FEED.get(result, ELIGIBILITY_UNCERTAIN)
        conditions = list(match.get("conditions_to_obtain") or [])
        blockers: list[str] = []
        if view == ELIGIBILITY_APPEARS_INELIGIBLE:
            blockers = [str(match.get("reason") or "disqualifying requirement")]
        payload: dict[str, Any] = {
            "eligibility_view": view,
            "why": str(match.get("reason") or ""),
            "evidence_ids": [],
            "conditions": conditions,
            "blockers": blockers,
            "unknowns": [],
        }
        if view == ELIGIBILITY_UNCERTAIN:
            payload["unknowns"] = ["tenant_eligibility_undecided"]
        return payload
    if requirements:
        return {
            "eligibility_view": ELIGIBILITY_NOT_ASSESSED,
            "why": "requirements exist but no tenant match has been computed",
            "evidence_ids": [],
            "conditions": [],
            "blockers": [],
            "unknowns": ["tenant_match_pending"],
        }
    return {
        "eligibility_view": ELIGIBILITY_NOT_ASSESSED,
        "why": "no normalized eligibility requirements on file",
        "evidence_ids": [],
        "conditions": [],
        "blockers": [],
        "unknowns": ["eligibility_evidence_missing"],
    }


def _list_canonical_rows(
    connection: sa.engine.Connection, *, limit: int, offset: int
) -> list[dict[str, Any]]:
    rows = (
        connection.execute(
            sa.text(
                f"SELECT canonical_id, title, funder_agency_name, current_close_date, "
                f"normalized_opportunity_number, lifecycle_state, last_seen_at "
                f"FROM {CANONICAL} ORDER BY (current_close_date IS NULL), "
                f"current_close_date, canonical_id "
                f"LIMIT :lim OFFSET :off"
            ),
            {"lim": int(limit), "off": int(offset)},
        )
        .mappings()
        .all()
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "canonical_id": row["canonical_id"],
                "title": row["title"],
                "funder_name": row["funder_agency_name"],
                "close_date": row["current_close_date"],
                "opportunity_number": row["normalized_opportunity_number"],
                "status": row["lifecycle_state"],
                "freshness_updated_at": row["last_seen_at"],
            }
        )
    return out


def _load_decision_map(
    connection: sa.engine.Connection, *, organization_id: str
) -> dict[str, dict[str, Any]]:
    rows = (
        connection.execute(
            sa.text(
                f"SELECT canonical_id, decision_state, actor_id, decided_at, reason "
                f"FROM {DECISIONS} WHERE organization_id = :org"
            ),
            {"org": organization_id},
        )
        .mappings()
        .all()
    )
    return {str(r["canonical_id"]): dict(r) for r in rows}


def _dismissed_set(
    connection: sa.engine.Connection, *, organization_id: str
) -> frozenset[str]:
    sql, params = q_my_dismissed(organization_id=organization_id)
    rows = connection.execute(sa.text(sql), params).fetchall()
    return frozenset(str(r[0]) for r in rows)


def assemble_customer_opportunity_feed(
    connection: sa.engine.Connection,
    *,
    organization_id: str,
    tenant_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    ordering: str = "DEADLINE_SOONEST",
    include_dismissed: bool = False,
    as_of: Any = None,
) -> dict[str, Any]:
    """Build a canonical-backed buyer feed for one organisation."""
    canonical_rows = _list_canonical_rows(connection, limit=limit, offset=offset)
    canonical_ids = [str(r["canonical_id"]) for r in canonical_rows]
    resolutions = resolve_logical_canonical_ids(
        connection=connection, canonical_ids=canonical_ids
    )
    decisions = _load_decision_map(connection, organization_id=organization_id)
    dismissed = _dismissed_set(connection, organization_id=organization_id)

    recommendations: list[dict[str, Any]] = []
    skipped_invariants: list[dict[str, Any]] = []

    for record in canonical_rows:
        cid = str(record["canonical_id"])
        if not include_dismissed and cid in dismissed:
            continue

        assessment = _load_assessment(connection, canonical_id=cid)
        evidence_ids = _load_evidence_ids(connection, canonical_id=cid)
        relevance = _map_relevance(assessment)
        relevance["evidence_ids"] = evidence_ids

        eligibility = _map_eligibility(
            connection, canonical_id=cid, tenant_id=tenant_id
        )

        changes_payload = build_customer_change_feed(
            connection=connection, canonical_id=cid, limit=5
        )
        changes = [
            {
                "change_type": c.get("what_changed"),
                "observed_at": c.get("detected_at"),
                "summary": c.get("explanation"),
            }
            for c in (changes_payload.get("changes") or [])
        ]

        decision_row = decisions.get(cid)
        decision = (
            {"decision_state": decision_row.get("decision_state")}
            if decision_row
            else {"decision_state": NEW}
        )

        rec = build_recommendation(
            organization_id=organization_id,
            canonical_record=record,
            relevance=relevance,
            eligibility=eligibility,
            documents=[],
            changes=changes,
            decision=decision,
        )
        failures = recommendation_invariant_failures(rec)
        if failures:
            skipped_invariants.append({"canonical_id": cid, "failures": failures})
            continue
        recommendations.append(rec)

    feed = build_feed(
        organization_id=organization_id,
        recommendations=recommendations,
        ordering=ordering,
        include_dismissed=include_dismissed,
        as_of=as_of,
        limit=limit,
        logical_resolutions=resolutions,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "authoritative_layer": AUTHORITATIVE_LAYER,
        "organization_id": organization_id,
        "tenant_id": tenant_id,
        "feed": feed,
        "canonical_row_count": len(canonical_rows),
        "skipped_invariant_count": len(skipped_invariants),
        "sourced_from_canonical_graph": True,
        "fixture_feed": False,
        "intelligence_disposition": {
            "uses_persisted_gate173_assessments": True,
            "legacy_keyword_spark_scores": False,
        },
    }


def organization_id_str(org_id: uuid.UUID | str) -> str:
    return str(org_id)
