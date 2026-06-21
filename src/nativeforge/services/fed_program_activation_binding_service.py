"""Sprint 309: bind fed activation to real ALN program with live-NOFO fallback."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.grants_gov_search_api_adapter_service import (
    HttpPostJson,
    extract_assistance_listing_number,
    probe_grants_gov_live_hits,
)
from nativeforge.services.source_ingestion_seed_loader_service import (
    load_source_seed_rows,
    seed_row_to_discovery_candidate,
)

SCHEMA_VERSION = "nf_fed_program_activation_binding_v1"

NF11_PRIMARY_SEED_ID = "nf-seed-2026-fed-001"
NF11_FALLBACK_SEED_ID = "nf-seed-2026-fed-006"
NF11_PRIMARY_ALN = "15.020"
NF11_FALLBACK_ALN = "15.148"
SEED_ALN_BINDINGS: dict[str, str] = {
    NF11_PRIMARY_SEED_ID: NF11_PRIMARY_ALN,
    NF11_FALLBACK_SEED_ID: NF11_FALLBACK_ALN,
}
NF11_ALLOWED_ACTIVATION_SEEDS = frozenset(
    {NF11_PRIMARY_SEED_ID, NF11_FALLBACK_SEED_ID}
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def load_seed_candidate(seed_id: str) -> dict[str, Any]:
    for row in load_source_seed_rows():
        if row["seed_id"] == seed_id:
            return seed_row_to_discovery_candidate(row)
    raise ValueError(f"unknown seed_id: {seed_id!r}")


def resolve_live_activation_seed(
    *,
    http_post: HttpPostJson | None = None,
) -> dict[str, Any]:
    """
    Prefer fed-001 (ALN 15.020). If no live NOFO, fall back to TEDC fed-006 (15.148).
    """
    primary = load_seed_candidate(NF11_PRIMARY_SEED_ID)
    primary_hits = probe_grants_gov_live_hits(primary, http_post=http_post)
    if primary_hits.get("hit_count", 0) > 0:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "seed_id": NF11_PRIMARY_SEED_ID,
                "assistance_listing_number": NF11_PRIMARY_ALN,
                "binding": "primary_program",
                "primary_empty": False,
                "fallback_used": False,
                "live_search": primary_hits,
            }
        )
    fallback = load_seed_candidate(NF11_FALLBACK_SEED_ID)
    fallback_hits = probe_grants_gov_live_hits(fallback, http_post=http_post)
    if fallback_hits.get("hit_count", 0) > 0:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "seed_id": NF11_FALLBACK_SEED_ID,
                "assistance_listing_number": NF11_FALLBACK_ALN,
                "binding": "fallback_live_nofo",
                "primary_empty": True,
                "fallback_used": True,
                "primary_aln": NF11_PRIMARY_ALN,
                "live_search": fallback_hits,
            }
        )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "seed_id": None,
            "binding": "no_live_nofo",
            "primary_empty": True,
            "fallback_used": False,
            "primary_aln": NF11_PRIMARY_ALN,
            "fallback_aln": NF11_FALLBACK_ALN,
            "live_search_primary": primary_hits,
            "live_search_fallback": fallback_hits,
        }
    )


def assert_seed_aln_binding(seed_id: str, source_name: str) -> None:
    aln = SEED_ALN_BINDINGS.get(seed_id) or extract_assistance_listing_number(
        source_name
    )
    if seed_id == NF11_PRIMARY_SEED_ID and aln != NF11_PRIMARY_ALN:
        raise ValueError(f"fed-001 must bind to ALN {NF11_PRIMARY_ALN}, got {aln!r}")
    if seed_id == NF11_FALLBACK_SEED_ID and aln != NF11_FALLBACK_ALN:
        raise ValueError(
            f"fed-006 fallback must bind to ALN {NF11_FALLBACK_ALN}, got {aln!r}"
        )
