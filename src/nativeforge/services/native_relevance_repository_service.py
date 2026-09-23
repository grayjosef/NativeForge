"""Gate 173N/P: writing relevance down, and reading it back by the paths that
matter.

Every query in `CRITICAL_QUERIES` is one an operator or a downstream gate
actually issues, and each is written here once so the access-path audit can
EXPLAIN the real statement rather than an invented one. Gate 172 lost a phase
to an audit that measured queries the service never runs - it omitted the
organization scope every index is prefixed by, reported five scans, and the
finding was about the audit.

Relevance is GLOBAL, so unlike the source fleet these tables carry no
organization column and the indexes are not org-prefixed. That difference is
deliberate and is the reason the audit here looks different from Gate 172's.

Writes are batched. Gate 170 shipped a corroboration path that issued one
UPDATE per event - 4,291 statements for a 1,500-observation chunk - and the
back-to-back battery caught it. `executemany` is the default here rather than
an optimisation applied later.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import sqlalchemy as sa

from nativeforge.services.native_relevance_ontology_service import (
    ONTOLOGY_VERSION,
    UNCERTAIN,
)

SCHEMA_VERSION = "nf_native_relevance_repository_v1"

ASSESSMENTS = "nf_opportunity_relevance_assessments"
EVIDENCE = "nf_opportunity_relevance_evidence"
UNIVERSE = "nf_source_coverage_universe"
GAPS = "nf_source_coverage_gap_signals"


#: name -> (sql, params_factory). The queries the service issues, so the audit
#: can EXPLAIN what actually runs.
def critical_queries(
    *,
    canonical_id: str,
    relevance_class: str = "NATIVE_ELIGIBLE",
    source_id: str = "",
    family: str = "FEDERAL",
) -> dict[str, tuple[str, tuple[Any, ...]]]:
    return {
        # "show me everything in this class" - the operator's main list
        "opportunities_by_relevance_class": (
            f"SELECT canonical_id FROM {ASSESSMENTS} "
            "WHERE relevance_class = ? AND is_current = 1",
            (relevance_class,),
        ),
        # "what needs a human"
        "opportunities_needing_review": (
            f"SELECT canonical_id FROM {ASSESSMENTS} "
            "WHERE review_required = 1 AND is_current = 1",
            (),
        ),
        # "what have we not settled"
        "opportunities_unknown": (
            f"SELECT canonical_id FROM {ASSESSMENTS} "
            "WHERE relevance_class = ? AND is_current = 1",
            (UNCERTAIN,),
        ),
        # one opportunity's current answer
        "latest_relevance_result": (
            f"SELECT relevance_class, confidence FROM {ASSESSMENTS} "
            "WHERE canonical_id = ? AND is_current = 1",
            (canonical_id,),
        ),
        # the evidence behind that answer
        "evidence_by_opportunity": (
            f"SELECT evidence_id, evidence_type FROM {EVIDENCE} WHERE canonical_id = ?",
            (canonical_id,),
        ),
        # candidate-stage inputs for one opportunity
        "candidate_generation_inputs": (
            f"SELECT evidence_value_json FROM {EVIDENCE} "
            "WHERE canonical_id = ? AND evidence_type = ?",
            (canonical_id, "APPLICANT_ELIGIBILITY"),
        ),
        # coverage
        "sources_by_coverage_state": (
            f"SELECT publisher_key FROM {UNIVERSE} WHERE coverage_state = ?",
            ("DISCOVERED_PENDING_REVIEW",),
        ),
        "source_family_coverage_summary": (
            f"SELECT coverage_state, count(*) FROM {UNIVERSE} "
            "WHERE family = ? GROUP BY coverage_state",
            (family,),
        ),
        "coverage_gaps_by_source": (
            f"SELECT gap_id FROM {GAPS} WHERE source_id = ?",
            (source_id,),
        ),
    }


#: Queries that return most of the population and are CORRECTLY scans. Named
#: so the exemption is visible rather than assumed, per Gate 172's rule.
EXPECTED_AGGREGATES: frozenset[str] = frozenset({"source_family_coverage_summary"})


def _json(value: Any) -> str:
    return json.dumps(value, default=str, sort_keys=True)


def _now(value: Any = None) -> dt.datetime:
    return value if isinstance(value, dt.datetime) else dt.datetime.now(dt.UTC)


def assessment_id(*, canonical_id: Any, ontology_version: Any, computed_at: Any) -> str:
    import hashlib

    parts = [str(canonical_id), str(ontology_version), str(computed_at)]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def write_evidence(
    connection: sa.engine.Connection,
    *,
    items: list[dict[str, Any]],
    now: Any = None,
) -> int:
    """Batched. One statement, however many rows."""
    if not items:
        return 0
    stamp = _now(now)
    rows = [
        {
            "evidence_id": item["evidence_id"],
            "canonical_id": item["canonical_id"],
            "evidence_type": item["evidence_type"],
            "source_id": item.get("source_id"),
            "raw_payload_sha256": item.get("raw_payload_sha256"),
            "observation_id": item.get("observation_id"),
            "version_id": item.get("version_id"),
            "field_name": item.get("field_name"),
            "section_ref": item.get("section_ref"),
            "page_ref": item.get("page_ref"),
            "document_ref": item.get("document_ref"),
            "evidence_value_json": _json(item.get("evidence_value")),
            "confidence_class": item["confidence_class"],
            "ambiguity_class": item["ambiguity_class"],
            "supports_classes_json": _json(item.get("supports_classes") or []),
            "ontology_version": item.get("ontology_version") or ONTOLOGY_VERSION,
            "observed_at": item.get("observed_at"),
            "created_at": stamp,
        }
        for item in items
    ]
    connection.execute(
        sa.text(
            f"INSERT OR REPLACE INTO {EVIDENCE} ("
            "evidence_id, canonical_id, evidence_type, source_id, "
            "raw_payload_sha256, observation_id, version_id, field_name, "
            "section_ref, page_ref, document_ref, evidence_value_json, "
            "confidence_class, ambiguity_class, supports_classes_json, "
            "ontology_version, observed_at, created_at) VALUES ("
            ":evidence_id, :canonical_id, :evidence_type, :source_id, "
            ":raw_payload_sha256, :observation_id, :version_id, :field_name, "
            ":section_ref, :page_ref, :document_ref, :evidence_value_json, "
            ":confidence_class, :ambiguity_class, :supports_classes_json, "
            ":ontology_version, :observed_at, :created_at)"
        ),
        rows,
    )
    return len(rows)


def write_assessments(
    connection: sa.engine.Connection,
    *,
    assessments: list[dict[str, Any]],
    now: Any = None,
) -> int:
    """Batched, and it supersedes rather than overwrites.

    173R: the prior classification survives. "This became relevant when the
    amendment landed" is the fact an operator acts on, and an UPDATE in place
    would destroy it.
    """
    if not assessments:
        return 0
    stamp = _now(now)

    canonical_ids = sorted({str(a["canonical_id"]) for a in assessments})
    # One statement, not one per opportunity.
    connection.execute(
        sa.text(
            f"UPDATE {ASSESSMENTS} SET is_current = 0, superseded_at = :stamp "
            f"WHERE is_current = 1 AND canonical_id IN "
            f"({', '.join(':c' + str(i) for i in range(len(canonical_ids)))})"
        ),
        {
            "stamp": stamp,
            **{f"c{i}": value for i, value in enumerate(canonical_ids)},
        },
    )

    rows = [
        {
            "assessment_id": assessment_id(
                canonical_id=a["canonical_id"],
                ontology_version=a.get("ontology_version") or ONTOLOGY_VERSION,
                computed_at=a.get("computed_at") or stamp,
            ),
            "canonical_id": a["canonical_id"],
            "ontology_version": a.get("ontology_version") or ONTOLOGY_VERSION,
            "relevance_class": a["relevance_class"],
            "candidate_state": a["candidate_state"],
            "confidence": a["confidence"],
            "review_required": 1 if a.get("review_required") else 0,
            "review_reasons_json": _json(a.get("review_reasons") or []),
            "reasons_json": _json(a.get("reasons") or []),
            "entity_classes_json": _json(a.get("entity_classes") or []),
            "sectors_json": _json(a.get("sectors") or []),
            "evidence_count": len(a.get("evidence_ids") or []),
            "ranking_score": int(a.get("ranking_score") or 0),
            "scope": a.get("scope") or "GLOBAL",
            "computed_at": a.get("computed_at") or stamp,
            "superseded_at": None,
            "is_current": 1,
            "created_at": stamp,
        }
        for a in assessments
    ]
    connection.execute(
        sa.text(
            f"INSERT OR REPLACE INTO {ASSESSMENTS} ("
            "assessment_id, canonical_id, ontology_version, relevance_class, "
            "candidate_state, confidence, review_required, review_reasons_json, "
            "reasons_json, entity_classes_json, sectors_json, evidence_count, "
            "ranking_score, scope, computed_at, superseded_at, is_current, "
            "created_at) VALUES ("
            ":assessment_id, :canonical_id, :ontology_version, :relevance_class, "
            ":candidate_state, :confidence, :review_required, :review_reasons_json, "
            ":reasons_json, :entity_classes_json, :sectors_json, :evidence_count, "
            ":ranking_score, :scope, :computed_at, :superseded_at, :is_current, "
            ":created_at)"
        ),
        rows,
    )
    return len(rows)


def write_coverage_entries(
    connection: sa.engine.Connection,
    *,
    entries: list[dict[str, Any]],
    now: Any = None,
) -> int:
    if not entries:
        return 0
    stamp = _now(now)
    rows = [
        {
            "publisher_key": e["publisher_key"],
            "family": e["family"],
            "publisher_name": e.get("publisher_name"),
            "coverage_state": e["coverage_state"],
            "source_ids_json": _json(e.get("source_ids") or []),
            "source_count": len(e.get("source_ids") or []),
            "decided_by": e.get("decided_by"),
            "decided_at": e.get("decided_at"),
            "why_json": _json(e.get("why") or []),
            "first_seen_at": e.get("first_seen_at") or stamp,
            "updated_at": stamp,
        }
        for e in entries
    ]
    connection.execute(
        sa.text(
            f"INSERT OR REPLACE INTO {UNIVERSE} ("
            "publisher_key, family, publisher_name, coverage_state, "
            "source_ids_json, source_count, decided_by, decided_at, why_json, "
            "first_seen_at, updated_at) VALUES ("
            ":publisher_key, :family, :publisher_name, :coverage_state, "
            ":source_ids_json, :source_count, :decided_by, :decided_at, :why_json, "
            ":first_seen_at, :updated_at)"
        ),
        rows,
    )
    return len(rows)


def record_gap_signals(
    connection: sa.engine.Connection,
    *,
    gaps: list[dict[str, Any]],
    now: Any = None,
) -> dict[str, int]:
    """Idempotent. The same blind spot seen twice is one row and a counter."""
    if not gaps:
        return {"inserted": 0, "advanced": 0, "statements": 0}
    stamp = _now(now)
    statements = 0

    existing = {
        row[0]
        for row in connection.execute(sa.text(f"SELECT gap_id FROM {GAPS}")).fetchall()
    }
    statements += 1

    fresh = [g for g in gaps if g["gap_id"] not in existing]
    seen_again = [g for g in gaps if g["gap_id"] in existing]

    if fresh:
        connection.execute(
            sa.text(
                f"INSERT INTO {GAPS} ("
                "gap_id, signal_type, family, publisher_key, source_id, "
                "canonical_id, evidence_ref, evidence_payload_sha256, "
                "detail_json, recommended_action, gap_state, first_detected_at, "
                "latest_detected_at, detection_count, created_at) VALUES ("
                ":gap_id, :signal_type, :family, :publisher_key, :source_id, "
                ":canonical_id, :evidence_ref, :evidence_payload_sha256, "
                ":detail_json, :recommended_action, :gap_state, :first_detected_at, "
                ":latest_detected_at, 1, :created_at)"
            ),
            [
                {
                    "gap_id": g["gap_id"],
                    "signal_type": g["signal_type"],
                    "family": g.get("family"),
                    "publisher_key": g.get("publisher_key"),
                    "source_id": g.get("source_id"),
                    "canonical_id": g.get("canonical_id"),
                    "evidence_ref": g.get("evidence_ref"),
                    "evidence_payload_sha256": g.get("evidence_payload_sha256"),
                    "detail_json": _json(g.get("detail")),
                    "recommended_action": g["recommended_action"],
                    "gap_state": g.get("gap_state") or "open",
                    "first_detected_at": g.get("first_detected_at") or stamp,
                    "latest_detected_at": g.get("latest_detected_at") or stamp,
                    "created_at": stamp,
                }
                for g in fresh
            ],
        )
        statements += 1

    if seen_again:
        # first_detected_at is never rewritten. That is the whole value.
        connection.execute(
            sa.text(
                f"UPDATE {GAPS} SET latest_detected_at = :stamp, "
                "detection_count = detection_count + 1 WHERE gap_id = :gap_id"
            ),
            [{"stamp": stamp, "gap_id": g["gap_id"]} for g in seen_again],
        )
        statements += 1

    return {
        "inserted": len(fresh),
        "advanced": len(seen_again),
        "statements": statements,
    }


def relevance_history(
    connection: sa.engine.Connection, *, canonical_id: str
) -> list[dict[str, Any]]:
    """173R: every answer this opportunity has had, oldest first."""
    rows = connection.execute(
        sa.text(
            f"SELECT relevance_class, confidence, is_current, computed_at, "
            f"superseded_at, evidence_count FROM {ASSESSMENTS} "
            "WHERE canonical_id = :canonical_id ORDER BY computed_at"
        ),
        {"canonical_id": canonical_id},
    ).fetchall()
    return [
        {
            "relevance_class": row[0],
            "confidence": row[1],
            "is_current": bool(row[2]),
            "computed_at": row[3],
            "superseded_at": row[4],
            "evidence_count": row[5],
        }
        for row in rows
    ]


def describe_repository() -> dict[str, Any]:
    names = sorted(critical_queries(canonical_id="x"))
    return json.loads(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "tables": [ASSESSMENTS, EVIDENCE, UNIVERSE, GAPS],
                "critical_query_names": names,
                "critical_query_count": len(names),
                "expected_aggregates": sorted(EXPECTED_AGGREGATES),
                "writes_are_batched": True,
                "assessments_supersede_rather_than_overwrite": True,
                "gap_signals_are_idempotent": True,
                "relevance_is_global_so_tables_carry_no_tenant": True,
            },
            default=str,
        )
    )
