"""Deterministic connector run manifest payloads (offline diagnostics spine)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any


def build_connector_run_manifest_v1(
    *,
    source_registry_id: uuid.UUID,
    intake_run_id: uuid.UUID | None,
    dry_run: bool,
    connector_run_id: str | None,
    fixture_row_count: int | None = None,
    source_row_count: int | None = None,
    normalized_candidate_count: int = 0,
    intake_candidate_count: int | None = None,
    accepted: int | None = None,
    duplicate: int | None = None,
    rejected: int | None = None,
    error: int | None = None,
    review_required: int | None = None,
    normalization_errors: int | None = None,
    source_check_run_id: uuid.UUID | None = None,
    evidence_pack_subject_hints: dict[str, Any] | None = None,
    connector_id: str | None = None,
    connector_version: str | None = None,
    connector_schema_version: str | None = None,
    health_status: str | None = None,
    warning_codes: list[str] | tuple[str, ...] | None = None,
    source_identifiers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Versioned additive metadata for offline connector → intake runs.

    Populates manifest v1 fields; callers merge alongside intake responses.
    """
    now = datetime.now(UTC)
    ts_block: dict[str, str] = {"manifest_generated_at": now.isoformat()}

    counts_body: dict[str, Any] = {
        "normalized_candidates": int(normalized_candidate_count),
    }
    if fixture_row_count is not None:
        counts_body["fixture_rows"] = int(fixture_row_count)
    if source_row_count is not None:
        counts_body["source_rows"] = int(source_row_count)
    if intake_candidate_count is not None:
        counts_body["intake_candidates"] = int(intake_candidate_count)
    if accepted is not None:
        counts_body["accepted"] = int(accepted)
    if duplicate is not None:
        counts_body["duplicate"] = int(duplicate)
    if rejected is not None:
        counts_body["rejected"] = int(rejected)
    if error is not None:
        counts_body["error"] = int(error)
    if review_required is not None:
        counts_body["review_required"] = int(review_required)
    if normalization_errors is not None:
        counts_body["normalization_errors"] = int(normalization_errors)

    warnings_list: list[str] = list(warning_codes) if warning_codes is not None else []

    hints: dict[str, Any]
    if evidence_pack_subject_hints is not None:
        hints = dict(evidence_pack_subject_hints)
    else:
        hints = {
            "opportunity_source": {
                "subject_path": "sources",
                "subject_id": str(source_registry_id),
            },
        }
        if intake_run_id is not None:
            hints["intake_run"] = {
                "subject_path": "intake-runs",
                "subject_id": str(intake_run_id),
            }
    if source_check_run_id is not None:
        hints["source_check_run"] = {
            "subject_path": "source-check-runs",
            "subject_id": str(source_check_run_id),
        }

    ids_block: dict[str, Any] = {
        "source_registry_id": str(source_registry_id),
        "intake_run_id": str(intake_run_id) if intake_run_id else None,
        "source_check_run_id": str(source_check_run_id)
        if source_check_run_id
        else None,
        "connector_run_id": connector_run_id,
    }

    src_ids = dict(source_identifiers) if source_identifiers else {}

    out: dict[str, Any] = {
        "schema_version": "nf_connector_run_manifest_v1",
        "generated_at": now.isoformat(),
        "connector_id": connector_id,
        "connector_version": connector_version,
        "connector_schema_version": connector_schema_version,
        "connector_run_id": connector_run_id,
        "dry_run": dry_run,
        "source_registry_id": str(source_registry_id),
        "timestamps": ts_block,
        "ids": ids_block,
        "counts": counts_body,
        "warning_codes": warnings_list,
        "health_status": health_status,
        "evidence_pack_subject_hints": hints,
    }
    if src_ids:
        out["source_identifiers"] = src_ids

    return out
