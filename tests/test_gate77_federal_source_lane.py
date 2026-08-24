"""Tests: Gate 77 federal source lane and Native eligibility evidence.

The central assertion is the one Gate 77's corpus triage proved is load-bearing:
**IHS and SAMHSA are not interchangeable because both sit under HHS.** A live
Grants.gov search for a SAMHSA seed currently returns an IHS opportunity, and a
system that treated the shared department as alignment would have attributed one
agency's grant to another agency's source without anyone noticing.

Everything else here is a refusal: keyword-only matching, parent-agency mission,
unbound applicant codes, and recognition tiers inferred from each other.
"""

from __future__ import annotations

import pathlib

import pytest

from nativeforge.services.federal_native_eligibility_service import (
    RECOGNITION_TIERS,
    eligibility_invariant_failures,
    evaluate_evidence_item,
    evaluate_federal_native_eligibility,
)
from nativeforge.services.federal_source_lane_service import (
    CROSS_AGENCY_FAMILIES,
    FEDERAL_SOURCE_FAMILIES,
    SUBAGENCY_REQUIRED_FAMILIES,
    build_federal_source,
    federal_agencies_align,
    federal_source_invariant_failures,
    split_agency_identifier,
)
from nativeforge.services.federal_source_seed_catalog import (
    FEDERAL_SEED_LANES,
    build_federal_seed_catalog,
    federal_seed_catalog_invariant_failures,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]

# A complete, cleared agency-specific federal source.
GOOD_SOURCE = {
    "source_id": "fed-1",
    "source_family": "agency_nofo_page",
    "agency": "HHS",
    "subagency": "SAMHSA",
    "program_name": "AI/AN Zero Suicide",
    "source_url": "https://example.gov/samhsa/nofo",
    "access_method": "html_page_scheduled_check",
    "robots_terms_status": "reviewed_allowed",
    "refresh_cadence": "weekly",
    "federal_program_scope": "operating_division",
    "provenance_url": "https://example.gov/samhsa/nofo",
    "promotion_status": "monitoring",
}


# ── the finding that motivated this gate ────────────────────────────────────


def test_ihs_and_samhsa_do_not_align_despite_sharing_hhs() -> None:
    """The exact real-world case from Gate 77's triage."""
    r = federal_agencies_align("SAMHSA / HHS", "HHS-IHS")
    assert r["aligned"] is False
    assert r["reason"] == "different_subagency_same_department"


def test_the_two_identifier_shapes_in_the_repo_both_parse() -> None:
    assert split_agency_identifier("SAMHSA / HHS") == {
        "department": "HHS",
        "subagency": "SAMHSA",
        "raw": "SAMHSA / HHS",
    }
    assert split_agency_identifier("HHS-IHS") == {
        "department": "HHS",
        "subagency": "IHS",
        "raw": "HHS-IHS",
    }


def test_same_subagency_aligns_across_identifier_shapes() -> None:
    assert federal_agencies_align("SAMHSA / HHS", "HHS-SAMHSA")["aligned"] is True


def test_parent_agency_alone_does_not_satisfy_a_subagency_claim() -> None:
    """A department-level identifier cannot confirm a program-level one."""
    r = federal_agencies_align("HHS", "HHS-IHS")
    assert r["aligned"] is False
    assert r["reason"] == "subagency_required_but_only_department_supplied"


def test_department_only_identifiers_align_with_each_other() -> None:
    assert federal_agencies_align("HHS", "HHS")["aligned"] is True


def test_different_departments_do_not_align() -> None:
    assert federal_agencies_align("EPA", "HHS")["aligned"] is False


def test_missing_identifier_never_aligns() -> None:
    """Absent is not a match. Aligning on absence is how proxies slip in."""
    for left, right in (("", "HHS-IHS"), ("HHS-IHS", ""), (None, None)):
        r = federal_agencies_align(left, right)
        assert r["aligned"] is False
        assert r["reason"] == "missing_agency_identifier"


def test_the_ownership_guard_was_not_weakened() -> None:
    """Gate 77 must not have touched the NF-16 guard."""
    guard = (
        ROOT
        / "src"
        / "nativeforge"
        / "services"
        / "source_program_ownership_guard_service.py"
    ).read_text(encoding="utf-8")
    assert "class CrossProgramProxyError" in guard
    assert "raise CrossProgramProxyError" in guard
    assert "def assert_source_program_ownership" in guard


# ── federal source completeness ─────────────────────────────────────────────


def test_complete_cleared_source_may_monitor() -> None:
    """The gate must be passable, or it is theatre rather than a gate."""
    r = build_federal_source(**GOOD_SOURCE)
    assert r["incomplete_reasons"] == [], r["incomplete_reasons"]
    assert r["blocked_reasons"] == [], r["blocked_reasons"]
    assert r["monitoring_allowed"] is True
    assert not federal_source_invariant_failures(r)


def test_federal_source_without_agency_is_incomplete() -> None:
    r = build_federal_source(**{**GOOD_SOURCE, "agency": None, "subagency": None})
    assert r["complete"] is False
    assert "no_agency" in r["incomplete_reasons"]
    assert r["monitoring_allowed"] is False


@pytest.mark.parametrize("family", sorted(SUBAGENCY_REQUIRED_FAMILIES))
def test_agency_specific_families_require_a_subagency(family: str) -> None:
    """HHS does not identify whose NOFO page this is."""
    r = build_federal_source(
        **{**GOOD_SOURCE, "source_family": family, "subagency": None}
    )
    assert r["complete"] is False
    assert "subagency_required_for_agency_specific_source" in r["incomplete_reasons"]
    assert r["monitoring_allowed"] is False


@pytest.mark.parametrize("family", sorted(CROSS_AGENCY_FAMILIES))
def test_government_wide_families_do_not_require_a_subagency(family: str) -> None:
    """Grants.gov spans every department; demanding one would be wrong."""
    r = build_federal_source(
        **{
            **GOOD_SOURCE,
            "source_family": family,
            "agency": None,
            "subagency": None,
            "federal_program_scope": "government_wide",
        }
    )
    assert (
        "subagency_required_for_agency_specific_source" not in r["incomplete_reasons"]
    )


def test_unknown_source_family_is_blocked() -> None:
    r = build_federal_source(**{**GOOD_SOURCE, "source_family": "carrier_pigeon"})
    assert r["source_family"] == "unknown"
    assert "source_family_unknown" in r["blocked_reasons"]
    assert r["monitoring_allowed"] is False


def test_federal_source_stays_in_the_federal_lane() -> None:
    r = build_federal_source(**GOOD_SOURCE)
    assert r["lane"] == "federal"
    r["lane"] = "state"
    assert "federal_source_left_the_federal_lane" in federal_source_invariant_failures(
        r
    )


# ── monitoring, provenance, freshness ───────────────────────────────────────


@pytest.mark.parametrize(
    "status",
    ["unreviewed", "unknown", "reviewed_disallowed", "reviewed_requires_agreement"],
)
def test_unresolved_or_negative_terms_block_monitoring(status: str) -> None:
    r = build_federal_source(**{**GOOD_SOURCE, "robots_terms_status": status})
    assert r["monitoring_allowed"] is False
    assert any(b.startswith("robots_terms_not_cleared") for b in r["blocked_reasons"])


def test_marked_monitoring_but_ineligible_is_named() -> None:
    r = build_federal_source(**{**GOOD_SOURCE, "robots_terms_status": "unreviewed"})
    assert "marked_monitoring_but_not_eligible" in r["blocked_reasons"]


def test_source_without_provenance_cannot_count_coverage() -> None:
    r = build_federal_source(**{**GOOD_SOURCE, "provenance_url": None})
    assert r["counts_toward_coverage"] is False
    assert "no_provenance_url" in r["incomplete_reasons"]


def test_source_without_a_check_timestamp_cannot_claim_freshness() -> None:
    r = build_federal_source(**GOOD_SOURCE)
    assert r["last_checked_at"] is None
    assert r["freshness_claimable"] is False
    r["freshness_claimable"] = True
    assert "freshness_claimable_without_a_check_timestamp" in (
        federal_source_invariant_failures(r)
    )


def test_no_federal_source_claims_coverage_or_live_ingestion() -> None:
    r = build_federal_source(**GOOD_SOURCE)
    assert r["coverage_claimed"] is False
    assert r["live_ingestion_claimed"] is False


# ── Native eligibility evidence ─────────────────────────────────────────────

TRIBAL_GOV_EVIDENCE = {
    "evidence_type": "explicit_tribal_government_eligibility",
    "reference": "https://example.gov/nofo#eligible-applicants",
    "quote": "Federally recognized Indian tribal governments are eligible.",
}


def _elig(**over: object) -> dict:
    kwargs: dict = {
        "opportunity_id": "opp-1",
        "agency": "HHS",
        "subagency": "SAMHSA",
        "evidence": [TRIBAL_GOV_EVIDENCE],
    }
    kwargs.update(over)
    return evaluate_federal_native_eligibility(**kwargs)


def test_explicit_tribal_government_evidence_gives_credit() -> None:
    r = _elig()
    tier = r["tiers"]["federally_recognized_tribal_government"]
    assert tier["eligibility_state"] == "eligible"
    assert tier["explicit"] is True
    assert not eligibility_invariant_failures(r)


def test_keyword_only_reference_gives_no_credit() -> None:
    """The word tribal in a title is not eligibility."""
    r = _elig(
        evidence=[{**TRIBAL_GOV_EVIDENCE, "keyword_match_only": True}],
        title_mentions_tribal=True,
    )
    assert r["tiers"]["federally_recognized_tribal_government"][
        "eligibility_state"
    ] == ("unknown")
    assert "title_keyword_is_not_eligibility" in r["notes"]
    assert any("keyword_match_only" in n for n in r["notes"])


def test_parent_agency_native_mission_is_not_eligibility() -> None:
    """IHS serving Native people does not open every IHS opportunity."""
    r = _elig(evidence=[], agency_serves_native_communities=True, subagency="IHS")
    for tier in RECOGNITION_TIERS:
        assert r["tiers"][tier]["eligibility_state"] == "unknown"
    assert "agency_native_mission_is_not_opportunity_eligibility" in r["notes"]


def test_evidence_without_a_reference_is_rejected() -> None:
    r = _elig(evidence=[{**TRIBAL_GOV_EVIDENCE, "reference": "   "}])
    assert r["tiers"]["federally_recognized_tribal_government"][
        "eligibility_state"
    ] == ("unknown")
    assert r["rejected_evidence_count"] == 1


@pytest.mark.parametrize(
    "etype",
    ["cfda_assistance_listing_applicant_type", "grants_gov_applicant_eligibility_code"],
)
def test_applicant_codes_must_bind_to_an_opportunity_or_listing(etype: str) -> None:
    """A code recalled from a program page describes the program, not this NOFO."""
    unbound = evaluate_evidence_item(
        {"evidence_type": etype, "reference": "https://example.gov/x"}
    )
    assert unbound["counts"] is False
    assert "applicant_code_not_bound_to_an_opportunity_or_listing" in unbound["reasons"]

    bound = evaluate_evidence_item(
        {
            "evidence_type": etype,
            "reference": "https://example.gov/x",
            "opportunity_id": "361976",
        }
    )
    assert bound["counts"] is True


def test_bound_applicant_code_supports_possibly_eligible_not_eligible() -> None:
    """Strong, but it does not name a tier. A human decides."""
    r = _elig(
        evidence=[
            {
                "evidence_type": "grants_gov_applicant_eligibility_code",
                "reference": "https://example.gov/opp",
                "opportunity_id": "361976",
            }
        ]
    )
    for tier in RECOGNITION_TIERS:
        assert r["tiers"][tier]["eligibility_state"] == "possibly_eligible"
    assert r["human_review_required"] is True
    assert not eligibility_invariant_failures(r)


@pytest.mark.parametrize(
    "etype", ["federal_register_notice_text", "agency_nofo_text", "program_page_text"]
)
def test_narrative_evidence_needs_a_quoted_statement(etype: str) -> None:
    """The document existing proves nothing; the sentence has to be quoted."""
    r = evaluate_evidence_item(
        {"evidence_type": etype, "reference": "https://example.gov/doc"}
    )
    assert r["counts"] is False
    assert "narrative_evidence_without_a_quoted_statement" in r["reasons"]


def test_unknown_evidence_type_is_rejected() -> None:
    r = evaluate_evidence_item(
        {"evidence_type": "a_colleague_said_so", "reference": "https://example.gov/x"}
    )
    assert r["counts"] is False
    assert "evidence_type_unknown" in r["reasons"]


# ── recognition tiers stay independent ──────────────────────────────────────


def test_tribal_government_evidence_does_not_credit_other_tiers() -> None:
    """Three different applicant types. Naming one says nothing about the others."""
    r = _elig()
    assert r["tiers"]["federally_recognized_tribal_government"][
        "eligibility_state"
    ] == ("eligible")
    assert r["tiers"]["state_recognized_tribe"]["eligibility_state"] == "unknown"
    assert r["tiers"]["native_nonprofit"]["eligibility_state"] == "unknown"


def test_state_recognized_eligibility_stays_unknown_unless_explicit() -> None:
    r = _elig(evidence=[])
    assert r["tiers"]["state_recognized_tribe"]["eligibility_state"] == "unknown"
    r2 = _elig(
        evidence=[
            {
                "evidence_type": "explicit_native_organization_eligibility",
                "reference": "https://example.gov/nofo#applicants",
            }
        ]
    )
    assert r2["tiers"]["state_recognized_tribe"]["eligibility_state"] == "eligible"


def test_native_nonprofit_eligibility_stays_unknown_unless_explicit() -> None:
    r = _elig(evidence=[])
    assert r["tiers"]["native_nonprofit"]["eligibility_state"] == "unknown"
    r2 = _elig(
        evidence=[
            {
                "evidence_type": "explicit_native_nonprofit_eligibility",
                "reference": "https://example.gov/nofo#applicants",
            }
        ]
    )
    assert r2["tiers"]["native_nonprofit"]["eligibility_state"] == "eligible"


def test_federally_recognized_eligibility_stays_unknown_unless_explicit() -> None:
    r = _elig(evidence=[])
    assert r["tiers"]["federally_recognized_tribal_government"][
        "eligibility_state"
    ] == ("unknown")


def test_no_evidence_means_unknown_not_ineligible() -> None:
    """Asserting ineligibility on no grounds would discourage a real applicant."""
    r = _elig(evidence=[])
    assert r["not_eligible_asserted"] is False
    for tier in RECOGNITION_TIERS:
        assert r["tiers"][tier]["eligibility_state"] == "unknown"


def test_invariants_reject_credit_from_unmapped_evidence() -> None:
    r = _elig()
    r["tiers"]["native_nonprofit"]["eligibility_state"] = "eligible"
    r["tiers"]["native_nonprofit"]["supporting_evidence_types"] = [
        "explicit_tribal_government_eligibility"
    ]
    assert "eligible_from_unmapped_evidence:native_nonprofit" in (
        eligibility_invariant_failures(r)
    )


def test_invariants_reject_credit_from_rejected_evidence() -> None:
    r = _elig(evidence=[{**TRIBAL_GOV_EVIDENCE, "reference": ""}])
    r["tiers"]["federally_recognized_tribal_government"].update(
        {
            "eligibility_state": "eligible",
            "supporting_evidence_types": ["explicit_tribal_government_eligibility"],
        }
    )
    fails = eligibility_invariant_failures(r)
    assert "credited_rejected_evidence:explicit_tribal_government_eligibility" in fails


# ── federal seed catalog ────────────────────────────────────────────────────


def test_federal_seed_catalog_builds() -> None:
    c = build_federal_seed_catalog()
    assert c["record_count"] >= 6
    assert not federal_seed_catalog_invariant_failures(c)


def test_no_federal_seed_is_monitorable() -> None:
    c = build_federal_seed_catalog()
    assert c["monitoring_allowed_count"] == 0
    for r in c["records"]:
        assert r["monitoring_allowed"] is False


def test_no_federal_seed_claims_a_check_timestamp_or_freshness() -> None:
    for r in build_federal_seed_catalog()["records"]:
        assert r["last_checked_at"] is None
        assert r["freshness_claimable"] is False


def test_every_federal_seed_is_discovered_and_unreviewed() -> None:
    for r in build_federal_seed_catalog()["records"]:
        assert r["promotion_status"] == "discovered"
        assert r["robots_terms_status"] == "unreviewed"


def test_federal_seed_catalog_claims_no_coverage_or_ingestion() -> None:
    c = build_federal_seed_catalog()
    assert c["coverage_claimed"] is False
    assert c["live_ingestion_claimed"] is False
    assert c["federal_coverage_complete_claimed"] is False


def test_only_public_record_entry_points_carry_urls() -> None:
    c = build_federal_seed_catalog()
    assert c["with_url_count"] < c["record_count"]
    urls = {r["source_url"] for r in c["records"] if r["source_url"]}
    assert urls == {
        "https://www.grants.gov/",
        "https://www.federalregister.gov/",
        "https://sam.gov/",
    }


def test_no_specific_native_program_page_is_named() -> None:
    """Naming one would assert a factual claim about a real federal program."""
    native = [
        r
        for r in build_federal_seed_catalog()["records"]
        if r["source_family"] == "native_specific_federal_program_page"
    ]
    assert native
    for r in native:
        assert r["source_url"] is None


@pytest.mark.parametrize("lane", sorted(FEDERAL_SEED_LANES))
def test_each_federal_lane_builds_alone(lane: str) -> None:
    c = build_federal_seed_catalog(lane)
    assert c["record_count"] >= 1
    assert not federal_seed_catalog_invariant_failures(c)


def test_all_seed_families_are_recognised() -> None:
    for r in build_federal_seed_catalog()["records"]:
        assert r["source_family"] in FEDERAL_SOURCE_FAMILIES
        assert r["source_family"] != "unknown"


# ── corpus test hermeticity and claim boundaries ────────────────────────────


def test_the_corpus_tests_are_hermetic_and_unquarantined() -> None:
    """Gate 77 quarantined these two; Gate 77B fixed the cause and freed them.

    This assertion moved rather than disappeared. It used to require that the
    quarantine be visible and explained; it now requires the replacement — a
    recorded transport and no live call — because that is what makes the tests
    trustworthy. Re-introduce a live fetch here and this fails.
    """
    src = (ROOT / "tests" / "test_sprint345_nf15_corrected_corpus.py").read_text(
        encoding="utf-8"
    )
    assert "@pytest.mark.skip" not in src
    assert "load_recorded_transport" in src
    assert src.count("http_post=recorded_transport") == 2
    # The recorded agency is asserted in-test, so a live leak fails loudly.
    assert '"SAMHSA / HHS"' in src


def test_readiness_doc_states_the_boundaries() -> None:
    doc = (
        ROOT / "docs" / "operations" / "427_GATE77_PRODUCTION_READINESS_DELTA.md"
    ).read_text(encoding="utf-8")
    assert "Live federal source coverage: NONE" in doc
    assert "Federal coverage complete:    NOT CLAIMED" in doc
    assert "65% improvement:              NOT CLAIMED" in doc
    assert "Controlled customer pilot:    NO_GO" in doc
