"""Deterministic connector run manifest payloads (offline diagnostics spine)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any


def build_connector_run_manifest_v1(
    *,
    source_registry_id: uuid.UUID,
    intake_run_id: uuid.UUID,
    dry_run: bool,
    connector_run_id: str | None,
    fixture_row_count: int,
    normalized_candidate_count: int,
    source_check_run_id: uuid.UUID | None = None,
    evidence_pack_subject_hints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Non-breaking additive metadata for static connector → intake runs.

    Shapes are versioned; callers merge alongside existing intake responses.
    """
    now = datetime.now(UTC)
    hints = evidence_pack_subject_hints or {
        "intake_run": {"subject_path": "intake-runs", "subject_id": str(intake_run_id)},
        "opportunity_source": {
            "subject_path": "sources",
            "subject_id": str(source_registry_id),
        },
    }
    return {
        "schema_version": "nf_connector_run_manifest_v1",
        "generated_at": now.isoformat(),
        "dry_run": dry_run,
        "timestamps": {"manifest_generated_at": now.isoformat()},
        "ids": {
            "source_registry_id": str(source_registry_id),
            "intake_run_id": str(intake_run_id),
            "source_check_run_id": str(source_check_run_id)
            if source_check_run_id
            else None,
            "connector_run_id": connector_run_id,
        },
        "counts": {
            "fixture_rows": fixture_row_count,
            "normalized_candidates": normalized_candidate_count,
        },
        "evidence_pack_subject_hints": hints,
        "review_signals": {
            "source_registry_registered": True,
            "intake_persisted": True,
        },
    }
