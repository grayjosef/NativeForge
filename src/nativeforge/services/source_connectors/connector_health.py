"""Map offline connector outcomes to coarse health labels (Sprint 28 spine)."""

from __future__ import annotations

from typing import Literal

ConnectorHealthLabel = Literal["healthy", "empty", "degraded", "failed"]


def intake_bridge_outcome_health(
    *,
    normalization_errors: int,
    accepted_count: int,
    rejected_count: int,
    duplicate_count: int,
    error_count: int,
) -> ConnectorHealthLabel:
    """Pure heuristic aligned with existing intake counters (no DB reads)."""
    if normalization_errors > 0:
        return "failed"
    if error_count > 0:
        return "failed"
    total = accepted_count + rejected_count + duplicate_count
    if total == 0:
        return "empty"
    if rejected_count >= accepted_count and accepted_count == 0:
        return "degraded"
    return "healthy"
