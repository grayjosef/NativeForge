"""Map offline connector outcomes to coarse health labels (Sprint 28 spine)."""

from __future__ import annotations

from typing import Literal

ConnectorHealthLabel = Literal["healthy", "empty", "degraded", "failed", "stale"]


def intake_bridge_outcome_health(
    *,
    normalization_errors: int,
    accepted_count: int,
    rejected_count: int,
    duplicate_count: int,
    error_count: int,
    review_required_count: int = 0,
    source_overdue_for_check: bool = False,
) -> ConnectorHealthLabel:
    """
    Pure heuristic aligned with intake counters (no DB reads).

    Ordering: normalization/intake hard failures first, then empty, degraded
    dominance (zero accepts, duplicate/rejection load, review-heavy), then
    healthy vs stale when the registry was overdue for a check at run start.
    """
    if normalization_errors > 0:
        return "failed"
    if error_count > 0:
        return "failed"

    total = accepted_count + rejected_count + duplicate_count + error_count
    if total == 0:
        return "empty"

    # No successful accepts — duplicates and/or rejections only (errors ruled out).
    if accepted_count == 0:
        return "degraded"

    if duplicate_count > accepted_count:
        return "degraded"
    if rejected_count > accepted_count:
        return "degraded"
    # Review-heavy: most/all accepts still need human review (deterministic saturation).
    if (
        accepted_count > 0
        and review_required_count >= 2
        and review_required_count >= accepted_count
    ):
        return "degraded"

    if source_overdue_for_check:
        return "stale"
    return "healthy"


def connector_outcome_warning_codes(
    *,
    health: ConnectorHealthLabel,
    accepted_count: int,
    rejected_count: int,
    duplicate_count: int,
    error_count: int,
    review_required_count: int,
    normalization_errors: int,
) -> list[str]:
    """Stable warning codes for manifests / source-check summaries (deterministic)."""
    codes: set[str] = set()
    if health == "stale":
        codes.add("source_check_overdue")
    if health == "empty":
        codes.add("connector_run_empty")
    if health == "failed" and normalization_errors == 0 and error_count > 0:
        codes.add("intake_candidate_errors")
    if duplicate_count > accepted_count and accepted_count > 0:
        codes.add("duplicate_load_dominant")
    if accepted_count == 0 and duplicate_count > 0:
        codes.add("duplicate_only_intake")
    if accepted_count == 0 and rejected_count > 0:
        codes.add("rejected_only_intake")
    if (
        accepted_count > 0
        and review_required_count >= 2
        and review_required_count >= accepted_count
    ):
        codes.add("review_required_heavy")
    elif (
        review_required_count >= 1
        and accepted_count > 0
        and review_required_count < accepted_count
    ):
        codes.add("review_required_elevated")
    return sorted(codes)


def connector_dry_run_operator_diagnostic_message(
    *,
    health: ConnectorHealthLabel,
    accepted_count: int,
    rejected_count: int,
    duplicate_count: int,
    error_count: int,
    review_required_count: int,
    normalization_errors: int,
    fixture_row_count: int | None,
    source_row_count: int | None,
) -> str:
    """Single operator-facing sentence for source-check result_summary."""
    row_hint = ""
    if source_row_count is not None:
        row_hint = f" ({source_row_count} source row(s))"
    elif fixture_row_count is not None:
        row_hint = f" ({fixture_row_count} fixture row(s))"

    if health == "failed" and normalization_errors > 0:
        return (
            "Fixture normalization failed before intake; no candidates were processed."
        )
    if health == "failed":
        return "Intake completed with candidate processing errors; no reliable accepts."
    if health == "empty":
        return f"Dry run produced zero intake candidates{row_hint}."
    if health == "degraded":
        return (
            "Dry run finished with no accepts or with duplicates, rejections, or "
            "review-required load dominating outcomes."
        )
    if health == "stale":
        return (
            f"Dry run accepted {accepted_count} candidate(s){row_hint}, but this "
            "source was overdue for its scheduled check when the run started."
        )
    if health == "healthy":
        return (
            f"Dry run accepted {accepted_count} candidate(s){row_hint}; intake "
            "completed without blocking errors."
        )
    return "Connector dry run completed."
