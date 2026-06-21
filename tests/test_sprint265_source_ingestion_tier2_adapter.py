"""Sprint 264-265: tier-2 state adapter."""

from __future__ import annotations

from nativeforge.services.source_ingestion_seed_loader_service import (
    build_source_seed_candidate_bundle,
)
from nativeforge.services.source_ingestion_tier2_state_adapter_service import (
    build_tier2_registry_from_seed,
    parse_tier2_state_listing,
)


def test_tier2_registry() -> None:
    cands = build_source_seed_candidate_bundle()["candidates"]
    reg = build_tier2_registry_from_seed(cands)
    assert reg["state_portal_count"] == 51


def test_tier2_public_listings_only() -> None:
    cands = build_source_seed_candidate_bundle()["candidates"]
    tier2 = next(c for c in cands if c["tier"] == 2)
    parsed = parse_tier2_state_listing(tier2, listing_rows=[{"title": "Grant A"}])
    assert parsed["public_listings_only"] is True
