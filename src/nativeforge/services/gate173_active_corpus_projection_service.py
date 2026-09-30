"""Bounded Gate 173 relevance projection for the active canonical corpus.

Root cause (production 2026): assessments are written only by
``project_canonical_opportunity``; ingest and OVI enrichment persisted canonical
rows without invoking that path, so no *current* rows existed in
``nf_opportunity_relevance_assessments`` for live active opportunities.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import sqlalchemy as sa

from nativeforge.services.canonical_intelligence_projection_service import (
    project_canonical_opportunity,
)
from nativeforge.services.intelligence_sql_dialect_service import is_current_active_sql
from nativeforge.services.native_relevance_ontology_service import ONTOLOGY_VERSION
from nativeforge.services.native_relevance_repository_service import ASSESSMENTS
from nativeforge.services.opportunity_value_funnel_service import (
    invalidate_funnel_cache,
)
from nativeforge.services.opportunity_value_intelligence_service import (
    ACTIVE_LIFECYCLE_STATES,
    CANONICAL,
    invalidate_public_cache,
)

SCHEMA_VERSION = "nf_gate173_active_corpus_projection_v1"
ROOT_CAUSE_CLASS = "projection_never_run_on_active_corpus"
DEFAULT_BOUND = 250


def gate173_root_cause() -> dict[str, Any]:
    return {
        "root_cause_class": ROOT_CAUSE_CLASS,
        "evidence": (
            "Gate 173 assessments are persisted exclusively via "
            "canonical_intelligence_projection_service.project_canonical_opportunity; "
            "production corpus ingest and Grants.gov funding enrichment did not call "
            "that path before V3 continuity wiring."
        ),
        "remediation": "run_bounded_active_relevance_projection (bounded, idempotent)",
        "ontology_version": ONTOLOGY_VERSION,
    }


def list_active_canonical_ids_missing_current_assessment(
    connection: sa.engine.Connection,
    *,
    limit: int = DEFAULT_BOUND,
) -> list[str]:
    active_list = ", ".join(f"'{s}'" for s in sorted(ACTIVE_LIFECYCLE_STATES))
    current_a = is_current_active_sql(connection, column="a.is_current")
    rows = connection.execute(
        sa.text(
            f"""
            SELECT c.canonical_id
            FROM {CANONICAL} c
            WHERE c.lifecycle_state IN ({active_list})
              AND NOT EXISTS (
                SELECT 1 FROM {ASSESSMENTS} a
                WHERE a.canonical_id = c.canonical_id
                  AND {current_a}
              )
            ORDER BY c.last_seen_at DESC
            LIMIT :lim
            """
        ),
        {"lim": int(limit)},
    ).fetchall()
    return [str(r[0]) for r in rows if str(r[0]) and str(r[0]) != "L1:"]


def project_intelligence_for_canonical_ids(
    connection: sa.engine.Connection,
    *,
    canonical_ids: list[str],
    dry_run: bool = False,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    """Idempotent Gate 173 projection for explicit canonical ids."""
    stamp = now or dt.datetime.now(dt.UTC)
    unique = []
    seen: set[str] = set()
    for cid in canonical_ids:
        key = str(cid or "").strip()
        if not key or key in seen or key == "L1:":
            continue
        seen.add(key)
        unique.append(key)
    results = [
        project_canonical_opportunity(
            connection, canonical_id=cid, now=stamp, dry_run=dry_run
        )
        for cid in unique
    ]
    if not dry_run and results:
        invalidate_public_cache()
        invalidate_funnel_cache()
    return {
        "schema_version": SCHEMA_VERSION,
        "requested": len(unique),
        "projected": len(results),
        "skipped_unchanged": sum(1 for r in results if r.get("skipped_unchanged")),
        "dry_run": dry_run,
        "sample": results[:5],
    }


def list_active_canonical_ids(
    connection: sa.engine.Connection,
    *,
    limit: int = DEFAULT_BOUND,
) -> list[str]:
    active_list = ", ".join(f"'{s}'" for s in sorted(ACTIVE_LIFECYCLE_STATES))
    rows = connection.execute(
        sa.text(
            f"""
            SELECT canonical_id FROM {CANONICAL}
            WHERE lifecycle_state IN ({active_list})
            ORDER BY last_seen_at DESC
            LIMIT :lim
            """
        ),
        {"lim": int(limit)},
    ).fetchall()
    return [str(r[0]) for r in rows if str(r[0]) and str(r[0]) != "L1:"]


def run_bounded_active_relevance_reassessment(
    connection: sa.engine.Connection,
    *,
    limit: int = DEFAULT_BOUND,
    dry_run: bool = True,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    """Reproject Gate 173 for the active corpus (input-fingerprint idempotent)."""
    cohort = list_active_canonical_ids(connection, limit=limit)
    stats: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "dry_run": dry_run,
        "active_reassessment_count": len(cohort),
        "limit": int(limit),
    }
    if dry_run:
        stats["cohort_sample"] = cohort[:10]
        return stats
    batch = project_intelligence_for_canonical_ids(
        connection, canonical_ids=cohort, dry_run=False, now=now
    )
    stats.update(batch)
    return stats


def run_bounded_active_relevance_projection(
    connection: sa.engine.Connection,
    *,
    limit: int = DEFAULT_BOUND,
    dry_run: bool = True,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    """Project Gate 173 for active opportunities missing a current assessment."""
    cohort = list_active_canonical_ids_missing_current_assessment(
        connection, limit=limit
    )
    stats: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "root_cause": gate173_root_cause(),
        "dry_run": dry_run,
        "active_missing_current_assessment_count": len(cohort),
        "limit": int(limit),
    }
    if dry_run:
        stats["cohort_sample"] = cohort[:10]
        return stats

    batch = project_intelligence_for_canonical_ids(
        connection, canonical_ids=cohort, dry_run=False, now=now
    )
    remaining = list_active_canonical_ids_missing_current_assessment(
        connection, limit=1
    )
    stats.update(batch)
    stats["remaining_active_without_current_assessment"] = len(remaining)
    return stats
