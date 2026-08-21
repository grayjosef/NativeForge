"""Tests: Campaign Block 09 controlled NOFO extraction pilot."""

from __future__ import annotations

from nativeforge.services.nofo_extraction_pilot_assembler_service import (
    build_nofo_extraction_demo_surface,
    nofo_extraction_demo_surface_invariant_failures,
)
from nativeforge.services.nofo_extraction_pilot_contract_service import (
    build_nofo_extraction_contract,
    nofo_extraction_invariant_failures,
)
from nativeforge.services.nofo_extraction_pilot_extractor_service import (
    PILOT_OPPORTUNITY_ID,
    run_controlled_nofo_extraction,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_broad_full_pdf_claims_remain_false() -> None:
    packet = build_nofo_extraction_contract(
        opportunity_id="x",
        source_document_id="y",
        source_document_label="z",
        source_document_type="text",
        source_layer="federal",
        document_url_or_fixture_reference="fixtures/x",
        data_mode="fixture_controlled",
        extraction_mode="controlled_text_extraction",
        extraction_scope="one_showcase_opportunity",
        extraction_status="partial",
        extracted_at=None,
        extractor_version="t",
    )
    assert packet["full_pdf_extraction_claimed"] is False
    assert packet["broad_pdf_support_claimed"] is False
    assert packet["pdf_bytes_parsed"] is False
    assert nofo_extraction_invariant_failures(packet) == []


def test_missing_requirements_do_not_become_requirements() -> None:
    nx = run_controlled_nofo_extraction()
    assert nx["opportunity_id"] == PILOT_OPPORTUNITY_ID
    assert nx["full_pdf_extraction_claimed"] is False
    assert nx["pdf_bytes_parsed"] is False
    for req in nx["requirements_map"]:
        if req["status"] in {"not_in_source", "missing", "not_supported"}:
            assert req.get("value") in (None, "", [])
            assert req.get("fabricated") is False
    # narrative/scoring should be not_in_source from synopsis-only fixture
    by_id = {r["requirement_id"]: r for r in nx["requirements_map"]}
    assert by_id["narrative_section_requirements"]["status"] == "not_in_source"
    assert by_id["evaluation_scoring_criteria"]["status"] == "not_in_source"
    assert by_id["deadline"]["status"] in {"extracted", "partial"}
    assert by_id["applicant_eligibility_language"]["status"] in {"extracted", "partial"}
    assert nofo_extraction_invariant_failures(nx) == []


def test_sections_and_demo_surface() -> None:
    nx = run_controlled_nofo_extraction()
    assert len(nx["sections"]) >= 10
    surface = build_nofo_extraction_demo_surface()
    assert nofo_extraction_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["nofo_extraction_pilot"]["full_pdf_extraction_claimed"] is False
    assert payload["nofo_extraction_pilot"]["broad_pdf_support_claimed"] is False
