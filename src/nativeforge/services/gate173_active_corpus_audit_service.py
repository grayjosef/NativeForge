"""Audit active production corpus for Native-relevant source signals vs Gate 173."""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa

from nativeforge.services.intelligence_sql_dialect_service import (
    is_current_active_sql,
    sql_bool_literal,
)
from nativeforge.services.native_eligibility_code_classification_service import (
    DIRECT_TRIBAL_CODES,
    NATIVE_RECALL_CODES,
    classify_native_eligibility,
)
from nativeforge.services.native_relevance_ontology_service import APPLICANT_RELEVANT
from nativeforge.services.native_relevance_repository_service import ASSESSMENTS
from nativeforge.services.opportunity_value_intelligence_service import (
    ACTIVE_LIFECYCLE_STATES,
    CANONICAL,
    PROVENANCE,
)

SCHEMA_VERSION = "nf_gate173_active_corpus_audit_v1"


def _parse_codes(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(v).strip() for v in raw if str(v).strip()]
    text = str(raw).strip()
    if not text:
        return []
    if "," in text:
        return [p.strip() for p in text.split(",") if p.strip()]
    return [text]


def production_relevance_class_distribution(
    connection: sa.engine.Connection,
) -> dict[str, Any]:
    current_a = is_current_active_sql(connection, column="a.is_current")
    active_list = ", ".join(f"'{s}'" for s in sorted(ACTIVE_LIFECYCLE_STATES))
    rows = connection.execute(
        sa.text(
            f"""
            SELECT a.relevance_class, COUNT(*) AS n
            FROM {ASSESSMENTS} a
            JOIN {CANONICAL} c ON c.canonical_id = a.canonical_id
            WHERE {current_a}
              AND c.lifecycle_state IN ({active_list})
            GROUP BY a.relevance_class
            ORDER BY n DESC
            """
        )
    ).fetchall()
    dist = {str(r[0]): int(r[1]) for r in rows}
    applicant = sum(dist.get(c, 0) for c in APPLICANT_RELEVANT)
    return {
        "active_assessment_count": sum(dist.values()),
        "by_class": dist,
        "applicant_relevant_count": applicant,
    }


def audit_active_corpus_native_signals(
    connection: sa.engine.Connection,
    *,
    sample_limit: int = 25,
) -> dict[str, Any]:
    """Compare authoritative applicant-code signals to current Gate 173 classes."""
    active_list = ", ".join(f"'{s}'" for s in sorted(ACTIVE_LIFECYCLE_STATES))
    current_p = sql_bool_literal(connection, value=True)
    current_a = is_current_active_sql(connection, column="a.is_current")
    rows = connection.execute(
        sa.text(
            f"""
            SELECT c.canonical_id,
                   pcodes.field_value AS codes,
                   a.relevance_class
            FROM {CANONICAL} c
            LEFT JOIN {PROVENANCE} pcodes
              ON pcodes.canonical_id = c.canonical_id
             AND pcodes.field_name = 'eligible_applicant_codes'
             AND pcodes.is_current_canonical = {current_p}
            LEFT JOIN {ASSESSMENTS} a
              ON a.canonical_id = c.canonical_id
             AND {current_a}
            WHERE c.lifecycle_state IN ({active_list})
            """
        )
    ).mappings()

    direct_examples: list[dict[str, Any]] = []
    recall_examples: list[dict[str, Any]] = []
    mismatch: list[dict[str, Any]] = []
    with_codes = 0
    without_codes = 0

    for row in rows:
        codes = _parse_codes(row.get("codes"))
        if not codes:
            without_codes += 1
            continue
        with_codes += 1
        band = classify_native_eligibility(eligible_applicant_codes=codes)
        conf = str(band.get("confidence") or "unknown")
        rel = str(row.get("relevance_class") or "")
        entry = {
            "canonical_id": row["canonical_id"],
            "codes": codes,
            "code_confidence": conf,
            "relevance_class": rel or None,
            "direct_tribal_codes": [c for c in codes if c in DIRECT_TRIBAL_CODES],
            "recall_codes": [c for c in codes if c in NATIVE_RECALL_CODES],
        }
        if conf == "direct":
            direct_examples.append(entry)
            if rel and rel not in APPLICANT_RELEVANT:
                mismatch.append(
                    {**entry, "issue": "direct_code_not_applicant_relevant"}
                )
        elif conf == "requires_reading":
            recall_examples.append(entry)

    direct_examples = direct_examples[:sample_limit]
    recall_examples = recall_examples[:sample_limit]

    if direct_examples and mismatch:
        corpus_verdict = "true"
        zero_explanation = "CLASSIFIER_OR_PROJECTION_RECALL_GAP"
    elif direct_examples and not mismatch:
        corpus_verdict = "true"
        zero_explanation = "APPLICANT_RELEVANT_PRESENT_IN_ASSESSMENTS"
    elif recall_examples and not direct_examples:
        corpus_verdict = "unknown"
        zero_explanation = "CORPUS_REQUIRES_TEXT_READING_NO_DIRECT_CODES"
    else:
        corpus_verdict = "false"
        zero_explanation = "CORRECT_ZERO_NO_PROVEN_NATIVE_APPLICANT_CODES"

    return {
        "schema_version": SCHEMA_VERSION,
        "corpus_has_proven_native_relevant_examples": corpus_verdict,
        "production_zero_explanation": zero_explanation,
        "active_with_applicant_codes": with_codes,
        "active_without_applicant_codes": without_codes,
        "direct_tribal_code_example_count": len(direct_examples),
        "requires_reading_code_example_count": len(recall_examples),
        "direct_code_assessment_mismatches": mismatch[:sample_limit],
        "sample_direct_code_examples": direct_examples,
        "sample_requires_reading_examples": recall_examples,
        "note": (
            "Proven Native-relevant means direct tribal applicant codes or "
            "assessments in APPLICANT_RELEVANT; code 99/25 alone is not proof."
        ),
    }
