"""Unified customer intelligence read model (Gates 173–175 authoritative)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa

from nativeforge.db.models import NfGrantSpark
from nativeforge.services.canonical_intelligence_projection_service import (
    GRANTS_GOV_SOURCE,
    resolve_canonical_id_for_spark,
)
from nativeforge.services.eligibility_intelligence_repository_service import (
    load_current_match,
    load_current_requirements,
)
from nativeforge.services.native_relevance_repository_service import (
    ASSESSMENTS,
    EVIDENCE,
)

SCHEMA_VERSION = "nf_customer_intelligence_read_model_v1"
AUTHORITATIVE_LAYER = "gate173_174_175_persisted"
STAGE6_7_NON_AUTHORITATIVE = (
    "native_relevance_classification_* and eligibility_fit_assessment_* are "
    "preview/readiness only; persisted Gate 173–175 rows are customer truth."
)


def _load_current_assessment(
    connection: sa.engine.Connection, *, canonical_id: str
) -> dict[str, Any] | None:
    row = connection.execute(
        sa.text(
            f"SELECT relevance_class, confidence, review_required, reasons_json, "
            f"candidate_state, evidence_count, computed_at "
            f"FROM {ASSESSMENTS} WHERE canonical_id = :cid AND is_current = 1"
        ),
        {"cid": canonical_id},
    ).fetchone()
    if not row:
        return None
    reasons_raw = row[3]
    reasons: Any = {}
    if reasons_raw:
        try:
            reasons = json.loads(reasons_raw)
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
        "authoritative": True,
    }


def _load_evidence(
    connection: sa.engine.Connection, *, canonical_id: str
) -> list[dict[str, Any]]:
    rows = connection.execute(
        sa.text(
            f"SELECT evidence_id, evidence_type, field_name, confidence_class, "
            f"evidence_value_json, raw_payload_sha256 "
            f"FROM {EVIDENCE} WHERE canonical_id = :cid"
        ),
        {"cid": canonical_id},
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        try:
            value = json.loads(r[4]) if r[4] else None
        except json.JSONDecodeError:
            value = r[4]
        out.append(
            {
                "evidence_id": r[0],
                "evidence_type": r[1],
                "field_name": r[2],
                "confidence_class": r[3],
                "evidence_value": value,
                "raw_payload_sha256": r[5],
            }
        )
    return out


def build_customer_intelligence_payload(
    connection: sa.engine.Connection,
    *,
    spark: NfGrantSpark,
    organization_id: uuid.UUID | None = None,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    canonical_id = resolve_canonical_id_for_spark(
        connection,
        source_record_id=str(spark.source_id or ""),
        opportunity_number=str(spark.opportunity_number or "") or None,
        source_id=GRANTS_GOV_SOURCE,
    )
    assessment = (
        _load_current_assessment(connection, canonical_id=canonical_id)
        if canonical_id
        else None
    )
    evidence = (
        _load_evidence(connection, canonical_id=canonical_id) if canonical_id else []
    )
    requirements = (
        load_current_requirements(connection, canonical_id=canonical_id)
        if canonical_id
        else []
    )
    match = None
    if canonical_id and tenant_id:
        match = load_current_match(
            connection, canonical_id=canonical_id, tenant_id=tenant_id
        )

    def _dt(dt: datetime | None) -> str | None:
        return dt.isoformat() if dt else None

    legacy_score = spark.native_relevance_score
    native_relevance: dict[str, Any]
    if assessment:
        native_relevance = {
            "source": AUTHORITATIVE_LAYER,
            "classification": assessment["relevance_class"],
            "confidence": assessment["confidence"],
            "review_required": assessment["review_required"],
            "candidate_state": assessment["candidate_state"],
            "reasons": assessment["reasons"],
            "evidence": evidence,
            "unknowns": []
            if assessment["relevance_class"] not in ("UNCERTAIN",)
            else ["native_relevance_undecided"],
        }
    elif canonical_id:
        native_relevance = {
            "source": AUTHORITATIVE_LAYER,
            "classification": "NOT_ASSESSED",
            "confidence": "NONE",
            "review_required": True,
            "reasons": {"items": ["intelligence_not_projected_yet"]},
            "evidence": [],
            "unknowns": ["projection_pending"],
        }
    else:
        native_relevance = {
            "source": "unlinked_spark",
            "classification": "NOT_ASSESSED",
            "confidence": "NONE",
            "legacy_keyword_score": legacy_score,
            "legacy_reasons": spark.native_relevance_reasons_json,
            "unknowns": ["no_canonical_graph_link"],
        }

    eligibility: dict[str, Any]
    if match:
        eligibility = {
            "source": AUTHORITATIVE_LAYER,
            "result": match["eligibility_result"],
            "reason": match["reason"],
            "conditions_to_obtain": match.get("conditions_to_obtain") or [],
            "review_required": match.get("review_required"),
            "unknown_count": match.get("unknown_count"),
        }
    elif requirements:
        eligibility = {
            "source": AUTHORITATIVE_LAYER,
            "result": "NOT_MATCHED",
            "reason": "requirements exist but no tenant match computed",
            "requirement_count": len(requirements),
            "unknowns": ["tenant_match_pending"],
        }
    else:
        eligibility = {
            "source": AUTHORITATIVE_LAYER,
            "result": "UNKNOWN",
            "reason": "no normalized requirements on file",
            "unknowns": ["eligibility_evidence_missing"],
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "authoritative_layer": AUTHORITATIVE_LAYER,
        "stage6_7_disposition": STAGE6_7_NON_AUTHORITATIVE,
        "identity": {
            "grant_spark_id": str(spark.id),
            "canonical_id": canonical_id,
            "source": spark.source,
            "freshness_status": spark.freshness_status,
            "application_deadline": _dt(spark.application_deadline),
            "last_verified_at": _dt(spark.last_verified_at),
        },
        "native_relevance": native_relevance,
        "eligibility": eligibility,
        "requirements": [
            {
                "requirement_id": r["requirement_id"],
                "kind": r["requirement_kind"],
                "polarity": r["polarity"],
                "original_text": r["original_text"][:500],
            }
            for r in requirements
        ],
        "documents": {
            "items": [],
            "note": "Gate 175 documents appear when authorized fetch ingests bytes",
        },
        "conflicts": [],
        "legacy_keyword_score": legacy_score if canonical_id and assessment else None,
    }
