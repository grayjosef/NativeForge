"""Sprint 258: load NF_SOURCE_SEED_2026.csv into source-discovery candidate rows."""

from __future__ import annotations

import csv
import json
from typing import Any

from nativeforge.services.source_ingestion_seed_schema_service import (
    EXPECTED_ROW_COUNT,
    REQUIRED_COLUMNS,
    SCHEMA_VERSION,
    seed_csv_path,
)

ACCESS_PUBLIC = "public"
ACCESS_MEMBERS = "members"
ACCESS_LOGIN = "login"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _validate_row(row: dict[str, str]) -> None:
    for col in REQUIRED_COLUMNS:
        if col not in row:
            raise ValueError(f"seed row missing column {col!r}")
    if row["tier"] not in {"1", "2", "3"}:
        raise ValueError(f"invalid tier: {row['tier']!r}")
    if row["access_posture_hint"] not in {
        ACCESS_PUBLIC,
        ACCESS_MEMBERS,
        ACCESS_LOGIN,
    }:
        raise ValueError(f"invalid access_posture_hint: {row['access_posture_hint']!r}")


def load_source_seed_rows(*, limit: int | None = None) -> list[dict[str, str]]:
    path = seed_csv_path()
    if not path.is_file():
        raise FileNotFoundError(f"seed CSV not found: {path}")
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = [dict(r) for r in reader]
    for row in rows:
        _validate_row(row)
    if len(rows) != EXPECTED_ROW_COUNT:
        raise ValueError(f"expected {EXPECTED_ROW_COUNT} seed rows, got {len(rows)}")
    if limit is not None:
        return rows[:limit]
    return rows


def seed_row_to_discovery_candidate(row: dict[str, str]) -> dict[str, Any]:
    """Map CSV row to a source-discovery candidate (not active)."""
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "seed_id": row["seed_id"],
            "canonical_source_id": row["canonical_source_id"],
            "source_name": row["source_name"],
            "source_url": row["source_url"],
            "tier": int(row["tier"]),
            "adapter_key": row["adapter_key"],
            "source_type": row["source_type"],
            "publisher_name": row["publisher_name"],
            "state_code": row["state_code"] or None,
            "access_posture_hint": row["access_posture_hint"],
            "program_family": row["program_family"],
            "native_relevance_notes": row["native_relevance_notes"],
            "is_active": False,
            "candidate_not_active": True,
            "human_activation_required": True,
            "verification_status": "unverified",
        }
    )


def build_source_seed_candidate_bundle() -> dict[str, Any]:
    rows = load_source_seed_rows()
    candidates = [seed_row_to_discovery_candidate(r) for r in rows]
    tier_counts = {1: 0, 2: 0, 3: 0}
    for c in candidates:
        tier_counts[c["tier"]] += 1
    return _json_safe(
        {
            "schema_version": "nf_source_seed_candidate_bundle_v1",
            "seed_row_count": len(rows),
            "candidate_count": len(candidates),
            "tier_counts": tier_counts,
            "candidates": candidates,
            "all_candidates_inactive": all(not c["is_active"] for c in candidates),
            "human_activation_required": True,
        }
    )
