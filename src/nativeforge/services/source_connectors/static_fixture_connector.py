"""Offline connector that ingests in-memory dict rows (tests / operators)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from nativeforge.services.source_connectors.base import (
    ConnectorDryRunResult,
    ConnectorRunContext,
    ConnectorSourceConfig,
    NormalizedOpportunityCandidate,
)
from nativeforge.services.source_connectors.normalization import normalize_raw_dict


def dry_run_fixture_rows(
    rows: list[dict[str, Any]],
    *,
    config: ConnectorSourceConfig,
    ctx: ConnectorRunContext | None = None,
) -> ConnectorDryRunResult:
    """
    Turn static fixture dicts into normalized candidates.

    No network I/O — suitable for unit tests and operator dry-runs.
    """
    run_ctx = ctx or ConnectorRunContext()
    now = run_ctx.now or datetime.now(UTC)
    ctx_filled = ConnectorRunContext(
        dry_run=run_ctx.dry_run,
        run_id=run_ctx.run_id,
        now=now,
        normalization_schema_version=run_ctx.normalization_schema_version,
    )

    candidates: list[NormalizedOpportunityCandidate] = []
    errors: list[dict[str, Any]] = []

    for idx, row in enumerate(rows):
        local_key = str(row.get("fixture_key", idx))
        extra = {
            "fixture_index": idx,
            "fixture_connector": "static_fixture",
        }
        try:
            cand = normalize_raw_dict(
                dict(row),
                local_key=local_key,
                config=config,
                ctx=ctx_filled,
                extra_provenance=extra,
            )
            candidates.append(cand)
        except Exception as ex:  # noqa: BLE001 — capture per-row normalization failures
            errors.append(
                {"fixture_index": idx, "local_key": local_key, "message": str(ex)}
            )

    return ConnectorDryRunResult(
        candidates=tuple(candidates),
        errors=tuple(errors),
    )
