"""Sprint 266-267: tier-3 foundation adapter."""

from __future__ import annotations

from nativeforge.services.source_ingestion_tier3_foundation_adapter_service import (
    discover_sources_from_directory_orgs,
)


def test_directory_dedupe() -> None:
    rows = [
        {"canonical_source_id": "nf:org:1", "org_name": "Org A", "grants_page_url": "https://a.org/g"},
        {"canonical_source_id": "nf:org:1", "org_name": "Org A dup", "grants_page_url": "https://a.org/g"},
        {"canonical_source_id": "nf:org:2", "org_name": "Org B", "grants_page_url": "https://b.org/g"},
    ]
    result = discover_sources_from_directory_orgs(rows)
    assert result["discovered_count"] == 2
    assert result["dedupe_skipped_count"] == 1
