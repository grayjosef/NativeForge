"""Pure helpers for connector run manifests and offline dry-run diagnostics."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


# Intake candidate models / row dicts with raw_candidate_json
def count_review_required_from_intake_candidates(
    candidates: Sequence[Any],
) -> int:
    """
    Count intake rows whose connector native relevance marked review_required.

    Uses the same `connector_native_relevance_v1` blob written by the static connector
    bridge (see :func:`normalization.to_discovery_intake_candidate_payload`).
    """
    n = 0
    for c in candidates:
        raw = getattr(c, "raw_candidate_json", None)
        if raw is None and isinstance(c, dict):
            raw = c.get("raw_candidate_json")
        if not isinstance(raw, dict):
            continue
        nr = raw.get("connector_native_relevance_v1")
        if isinstance(nr, dict) and nr.get("review_required") is True:
            n += 1
    return n


def warning_codes_from_connector_normalization_errors(
    errors: tuple[dict[str, Any], ...] | list[dict[str, Any]],
) -> list[str]:
    """Derive stable warning codes from per-row fixture normalization errors."""
    codes: list[str] = ["fixture_normalization_failed"]
    for e in errors:
        if not isinstance(e, dict):
            continue
        msg = str(e.get("message", "")).strip()
        if msg:
            codes.append(f"row_error:{msg[:200]}")
    return codes


def source_labels_from_fixture_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Best-effort corpus / shape hints from raw fixture dicts (pre-intake).

    Deterministic: stable sorted unique categories, first non-empty schema version.
    """
    categories: set[str] = set()
    corpus_schema: str | None = None
    shapes: set[str] = set()
    for r in rows:
        if not isinstance(r, dict):
            continue
        cat = r.get("fixture_category")
        if cat is not None and str(cat).strip():
            categories.add(str(cat).strip())
        cs = r.get("corpus_schema_version")
        if cs is not None and str(cs).strip() and corpus_schema is None:
            corpus_schema = str(cs).strip()
        for k in ("connector_shape", "fixture_format"):
            v = r.get(k)
            if v is not None and str(v).strip():
                shapes.add(f"{k}:{str(v).strip()}")
    out: dict[str, Any] = {
        "fixture_categories": sorted(categories),
        "corpus_schema_version": corpus_schema,
        "row_shape_hints": sorted(shapes),
    }
    return {k: v for k, v in out.items() if v not in (None, [], ())}


def connector_shape_label(
    *,
    grants_gov_shaped_dry_run: bool,
    provenance: dict[str, Any],
) -> str | None:
    """Resolve offline connector shape from dry-run provenance."""
    if grants_gov_shaped_dry_run:
        alt = provenance.get("fixture_connector") or provenance.get("connector_shape")
        return str(alt or "grants_gov_shaped")
    fc = provenance.get("fixture_connector")
    if fc is not None:
        return str(fc)
    return "static_fixture"


def manifest_counts_intake_consistent(
    *,
    summary_counts: dict[str, Any],
    accepted: int,
    duplicate: int,
    rejected: int,
    error: int,
) -> bool:
    """Return True if manifest path counters match the intake summary block."""
    try:
        c = int(summary_counts.get("candidate_count", 0))
        a = int(summary_counts.get("accepted_count", 0))
        d = int(summary_counts.get("duplicate_count", 0))
        r = int(summary_counts.get("rejected_count", 0))
        e = int(summary_counts.get("error_count", 0))
    except (TypeError, ValueError):
        return False
    return (
        c == a + d + r + e
        and a == accepted
        and d == duplicate
        and r == rejected
        and e == error
    )


def flatten_manifest_for_json(obj: Any) -> Any:
    """JSON-serializable view (UUIDs should already be strings in manifests)."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): flatten_manifest_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [flatten_manifest_for_json(x) for x in obj]
    return str(obj)
