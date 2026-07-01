"""Static extraction-gap re-ingest for no_live_nofo pages with HTML present."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.tier2_state_batch_live_fetch_service import (
    run_tier2_state_batch_live_fetch,
)
from nativeforge.services.tier2_state_corpus_persist_service import (
    persist_tier2_batch_to_corpus,
)
from nativeforge.services.tier3_foundation_batch_live_fetch_service import (
    run_tier3_foundation_batch_live_fetch,
)
from nativeforge.services.tier3_foundation_corpus_persist_service import (
    persist_tier3_batch_to_corpus,
)

SCHEMA_VERSION = "nf_static_extraction_gap_v1"

EXTRACTION_GAP_TIER2_SEED_IDS: tuple[str, ...] = (
    "nf-seed-2026-st-035",
)

EXTRACTION_GAP_TIER3_SEED_IDS: tuple[str, ...] = (
    "nf-seed-2026-t3-012",
    "nf-seed-2026-t3-034",
    "nf-seed-2026-t3-019",
    "nf-seed-2026-t3-036",
    "nf-seed-2026-t3-053",
    "nf-seed-2026-t3-063",
    "nf-seed-2026-t3-065",
)

EXTRACTION_GAP_SEED_IDS: tuple[str, ...] = (
    EXTRACTION_GAP_TIER2_SEED_IDS + EXTRACTION_GAP_TIER3_SEED_IDS
)

# Genuinely empty — must remain honest no_live_nofo.
GENUINELY_EMPTY_DEFERRED_SEED_IDS: tuple[str, ...] = (
    "nf-seed-2026-t3-024",
    "nf-seed-2026-t3-027",
    "nf-seed-2026-t3-030",
    "nf-seed-2026-t3-035",
    "nf-seed-2026-t3-044",
    "nf-seed-2026-t3-055",
    "nf-seed-2026-t3-059",
    "nf-seed-2026-t3-062",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def audit_extraction_gap_page(
    *,
    seed_id: str,
    included: list[dict[str, Any]],
    excluded: list[dict[str, Any]],
) -> dict[str, Any]:
    nav_leaked = [
        i
        for i in included
        if str(i.get("listing_title", "")).lower().startswith(
            ("skip to", "resources", "learn more", "grantmaking")
        )
    ]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "seed_id": seed_id,
            "included_count": len(included),
            "excluded_count": len(excluded),
            "generic_nav_leaked": len(nav_leaked),
            "accuracy_ok": len(nav_leaked) == 0,
            "sample_included": [
                str(i.get("listing_title") or i.get("opportunity_title") or "")[:70]
                for i in included[:5]
            ],
            "sample_excluded": [
                str(e.get("listing_title") or "")[:70] for e in excluded[:5]
            ],
        }
    )


def run_extraction_gap_reingest_block(
    *,
    fetch_mode: str = "live",
) -> dict[str, Any]:
    """Re-fetch and persist extraction-gap targets only."""
    t2_batch = run_tier2_state_batch_live_fetch(
        list(EXTRACTION_GAP_TIER2_SEED_IDS),
        fetch_mode=fetch_mode,  # type: ignore[arg-type]
    )
    t3_batch = run_tier3_foundation_batch_live_fetch(
        list(EXTRACTION_GAP_TIER3_SEED_IDS),
        fetch_mode=fetch_mode,  # type: ignore[arg-type]
    )
    t2_persist = persist_tier2_batch_to_corpus(t2_batch)
    t3_persist = persist_tier3_batch_to_corpus(t3_batch)

    per_page: list[dict[str, Any]] = []
    for row in t2_batch["per_source"]:
        sid = str(row["seed_id"])
        payloads = [
            p
            for p in t2_batch["raw_payloads"]
            if str(p.get("source_seed_id")) == sid
        ]
        excluded = list(row.get("excluded_listings_audit") or [])
        per_page.append(
            audit_extraction_gap_page(
                seed_id=sid,
                included=payloads,
                excluded=excluded,
            )
        )
    for row in t3_batch["per_source"]:
        sid = str(row["seed_id"])
        payloads = [
            p
            for p in t3_batch["raw_payloads"]
            if str(p.get("source_seed_id")) == sid
        ]
        per_page.append(
            audit_extraction_gap_page(
                seed_id=sid,
                included=payloads,
                excluded=[],
            )
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "target_seed_count": len(EXTRACTION_GAP_SEED_IDS),
            "tier2_persist": t2_persist,
            "tier3_persist": t3_persist,
            "per_page_audit": per_page,
            "tier2_recovered": sum(
                1 for r in t2_batch["per_source"] if r["opportunity_count"] > 0
            ),
            "tier3_recovered": sum(
                1 for r in t3_batch["per_source"] if r["opportunity_count"] > 0
            ),
        }
    )
