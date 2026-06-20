"""Sprint 261-263: tier-1 federal adapter."""

from __future__ import annotations

from nativeforge.services.source_ingestion_tier1_federal_adapter_service import (
    build_canonical_opportunity_id,
    parse_tier1_federal_opportunity,
    upsert_tier1_opportunities,
)


def test_canonical_opportunity_id_stable() -> None:
    raw = {"opportunity_number": "ABC-123", "opportunity_title": "Test"}
    assert build_canonical_opportunity_id(raw) == "ABC-123"


def test_parse_tier1_federal() -> None:
    parsed = parse_tier1_federal_opportunity(
        {
            "opportunity_title": "Tribal Language Grant",
            "agency": "Demo Agency",
            "opportunity_number": "DEMO-001",
            "source_url": "https://grants.gov/opportunity/demo-001",
        },
        adapter_key="grants_gov_federal",
    )
    assert parsed["canonical_opportunity_id"] == "DEMO-001"


def test_idempotent_upsert() -> None:
    payloads = [
        {
            "adapter_key": "grants_gov_federal",
            "opportunity_number": "X-1",
            "opportunity_title": "A",
            "agency": "Ag",
        },
        {
            "adapter_key": "grants_gov_federal",
            "opportunity_number": "X-1",
            "opportunity_title": "A",
            "agency": "Ag",
        },
    ]
    result = upsert_tier1_opportunities(payloads)
    assert result["inserted_count"] == 1
    assert result["updated_count"] == 1
