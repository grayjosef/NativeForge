"""Operator-safe applicant eligibility provenance coverage."""

from __future__ import annotations

import sqlalchemy as sa

from nativeforge.services.gate173_active_corpus_audit_service import (
    production_relevance_class_distribution,
)
from nativeforge.services.grants_gov_detail_enrichment_service import (
    DETAIL_ENRICHMENT_VERSION,
    list_active_canonical_applicant_evidence_gaps,
)
from nativeforge.services.intelligence_sql_dialect_service import sql_bool_literal
from nativeforge.services.opportunity_value_intelligence_service import (
    ACTIVE_LIFECYCLE_STATES,
    CANONICAL,
    PROVENANCE,
)

SCHEMA_VERSION = "nf_applicant_enrichment_diagnostics_v1"


def compute_applicant_enrichment_diagnostics(
    connection: sa.engine.Connection,
) -> dict[str, object]:
    active_list = ", ".join(f"'{s}'" for s in sorted(ACTIVE_LIFECYCLE_STATES))
    current = sql_bool_literal(connection, value=True)
    active_count = connection.execute(
        sa.text(
            f"SELECT COUNT(*) FROM {CANONICAL} WHERE lifecycle_state IN ({active_list})"
        )
    ).scalar()
    structured = connection.execute(
        sa.text(
            f"""
            SELECT COUNT(DISTINCT c.canonical_id)
            FROM {CANONICAL} c
            JOIN {PROVENANCE} p
              ON p.canonical_id = c.canonical_id
             AND p.field_name = 'eligible_applicant_codes'
             AND p.is_current_canonical = {current}
             AND TRIM(p.field_value) != ''
            WHERE c.lifecycle_state IN ({active_list})
            """
        )
    ).scalar()
    text_count = connection.execute(
        sa.text(
            f"""
            SELECT COUNT(DISTINCT c.canonical_id)
            FROM {CANONICAL} c
            JOIN {PROVENANCE} p
              ON p.canonical_id = c.canonical_id
             AND p.field_name = 'eligibility_text'
             AND p.is_current_canonical = {current}
             AND TRIM(p.field_value) != ''
            WHERE c.lifecycle_state IN ({active_list})
            """
        )
    ).scalar()
    terminal = connection.execute(
        sa.text(
            f"""
            SELECT COUNT(DISTINCT c.canonical_id)
            FROM {CANONICAL} c
            JOIN {PROVENANCE} p
              ON p.canonical_id = c.canonical_id
             AND p.field_name = 'applicant_enrichment_terminal'
             AND p.is_current_canonical = {current}
             AND p.field_value IN (
               'no_applicant_fields',
               'detail_unavailable_no_source_record_id'
             )
            WHERE c.lifecycle_state IN ({active_list})
            """
        )
    ).scalar()
    active_n = int(active_count or 0)
    structured_n = int(structured or 0)
    coverage = round(100.0 * structured_n / active_n, 2) if active_n else 0.0
    dist = production_relevance_class_distribution(connection)
    gap_sample = list_active_canonical_applicant_evidence_gaps(connection, limit=5)
    return {
        "schema_version": SCHEMA_VERSION,
        "enrichment_version": DETAIL_ENRICHMENT_VERSION,
        "active_count": active_n,
        "structured_code_count": structured_n,
        "eligibility_text_count": int(text_count or 0),
        "no_applicant_fields_count": int(terminal or 0),
        "active_without_applicant_evidence": max(
            0, active_n - structured_n - int(terminal or 0)
        ),
        "applicant_evidence_coverage_pct": coverage,
        "gate173_distribution": dist,
        "applicant_relevant_count": dist.get("applicant_relevant_count"),
        "applicant_evidence_gap_sample": [
            {
                "canonical_id": row.get("canonical_id"),
                "source_record_id": row.get("source_record_id"),
                "opportunity_number": row.get("opportunity_number"),
            }
            for row in gap_sample
        ],
    }
