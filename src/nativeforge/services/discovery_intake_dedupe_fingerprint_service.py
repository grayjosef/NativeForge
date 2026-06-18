"""Sprint 164: offline intake batch dedupe fingerprint report (advisory only)."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from nativeforge.domain.enums import OpportunitySourceType
from nativeforge.services.opportunity_discovery_service import (
    compute_duplicate_key,
    compute_structural_duplicate_fingerprint,
)

SCHEMA_VERSION = "nf_discovery_dedupe_fingerprint_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _parse_source_type(raw: dict[str, Any]) -> OpportunitySourceType | None:
    st = raw.get("opportunity_source_type") or raw.get("source_type")
    if st is None:
        return None
    try:
        return OpportunitySourceType(str(st))
    except ValueError:
        return None


def candidate_dedupe_fingerprints_from_raw(raw: dict[str, Any]) -> dict[str, str]:
    """Deterministic duplicate and structural fingerprints for one raw candidate dict."""
    title = str(raw.get("opportunity_title") or raw.get("title") or "")
    agency = str(raw.get("agency") or raw.get("publisher_name") or "")
    publisher = str(raw.get("publisher_name") or raw.get("agency") or "")
    opp_num = str(raw.get("opportunity_number") or raw.get("opportunity_id") or "")
    url = raw.get("source_url") or raw.get("url")
    source_url = str(url) if url is not None else None
    source_type = _parse_source_type(raw)
    duplicate_key = compute_duplicate_key(
        source_url=source_url,
        publisher_name=publisher or None,
        opportunity_number=opp_num or None,
        opportunity_title=title or None,
        opportunity_source_type=source_type,
    )
    structural = compute_structural_duplicate_fingerprint(
        agency=agency or None,
        publisher_name=publisher or None,
        opportunity_number=opp_num or None,
        opportunity_title=title or None,
    )
    return {
        "duplicate_key": duplicate_key,
        "structural_fingerprint": structural,
    }


def build_intake_batch_dedupe_fingerprint_report(
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    """Advisory collision report for a structured intake batch (no auto-reject)."""
    duplicate_groups: dict[str, list[int]] = defaultdict(list)
    structural_groups: dict[str, list[int]] = defaultdict(list)
    rows: list[dict[str, Any]] = []

    for idx, cand in enumerate(candidates):
        raw = dict(cand) if isinstance(cand, dict) else {"value": cand}
        fps = candidate_dedupe_fingerprints_from_raw(raw)
        duplicate_groups[fps["duplicate_key"]].append(idx)
        structural_groups[fps["structural_fingerprint"]].append(idx)
        rows.append(
            {
                "batch_index": idx,
                "duplicate_key": fps["duplicate_key"],
                "structural_fingerprint": fps["structural_fingerprint"],
                "opportunity_title": str(
                    raw.get("opportunity_title") or raw.get("title") or ""
                )[:120],
            }
        )

    dup_collisions = [
        {"fingerprint_type": "duplicate_key", "fingerprint": k, "batch_indices": v}
        for k, v in sorted(duplicate_groups.items())
        if len(v) > 1
    ]
    struct_collisions = [
        {
            "fingerprint_type": "structural_fingerprint",
            "fingerprint": k,
            "batch_indices": v,
        }
        for k, v in sorted(structural_groups.items())
        if len(v) > 1
    ]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "batch_candidate_count": len(candidates),
            "unique_duplicate_key_count": len(duplicate_groups),
            "unique_structural_fingerprint_count": len(structural_groups),
            "duplicate_key_collision_count": len(dup_collisions),
            "structural_fingerprint_collision_count": len(struct_collisions),
            "collision_groups": dup_collisions + struct_collisions,
            "candidate_fingerprints": rows,
            "advisory_only": True,
            "notes": (
                "Fingerprint collisions are advisory metadata only; intake acceptance "
                "logic is unchanged and existing duplicate_key matching still governs "
                "Grant Spark deduplication."
            ),
        }
    )


def attach_dedupe_fingerprint_report_to_intake_summary(
    summary: dict[str, Any],
    report: dict[str, Any],
) -> dict[str, Any]:
    """Merge dedupe report into intake run summary JSON."""
    merged = dict(summary)
    merged["dedupe_fingerprint_report"] = report
    return _json_safe(merged)
