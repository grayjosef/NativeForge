"""Tests: Gate 79 SC contract corrections.

Two corrections, both driven by the Gate 78R research pass.

**Funding lane follows the money, not the masthead.** Five SC agency sources
administer federal money. Under Gate 78's source-level rule every one files as
pure `sc_state`, which would show a customer federal money — with federal strings
and often federal-recognition eligibility — labelled as a state programme, and
would corrupt both coverage counts.

**Exclusion evidence is expressible and per-class.** NACTEP's cited eligibility
is an enumerated exclusive list that SC's ten state-recognized tribes are not on.
The product could previously only say `unknown`. Saying "we don't know" when the
notice plainly excludes them wastes the scarcest thing a tribal grant office has.

Neither correction weakens the Gate 77 boundary: universal `not_eligible` stays
unassertable.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from nativeforge.services.eligibility_exclusion_evidence_service import (
    APPLICANT_CLASSES,
    RESULT_STATES,
    all_classes_invariant_failures,
    analyse_eligibility_text,
    evaluate_all_applicant_classes,
    evaluate_applicant_class,
    exclusion_invariant_failures,
    federal_tier_for,
)
from nativeforge.services.opportunity_funding_lane_service import (
    DISCOVERY_LANE_MAP,
    FEDERALLY_FUNDED_LANES,
    FUNDING_LANES,
    PRIVATE_FUNDED_LANES,
    SC_ROUTING_LANE_MAP,
    STATE_FUNDED_LANES,
    classify_opportunity_funding_lane,
    discovery_lane,
    funding_lane_invariant_failures,
    sc_routing_lane,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "sc_research"
    / "gate78r_grants_for_state_tribes_model.json"
)

# The real quoted eligibility from advance.sc.gov/grants-state-tribes.
NACTEP_TEXT = (
    "Eligibility is limited to Federally recognized Indian tribes, tribal "
    "organizations, Alaska Native entities, and eligible BIE-funded schools"
)
NACTEP_CITE = "https://advance.sc.gov/grants-state-tribes"


def _lane(**over: object) -> dict:
    kwargs: dict = {"opportunity_id": "opp-1"}
    kwargs.update(over)
    return classify_opportunity_funding_lane(**kwargs)


# ── correction 1: lane follows the money ────────────────────────────────────


def test_sc_agency_can_produce_a_federal_pass_through_opportunity() -> None:
    """The FEMA HMGP case. Every signal looks state; the money is federal."""
    r = _lane(
        state_agency="SCEMD",
        federal_agency="FEMA",
        program_name="Hazard Mitigation Grant Program",
        funding_origin="federal_pass_through_to_state",
        administering_agency="SCEMD",
        source_url="https://www.scemd.org/recover/mitigation/",
        source_lane="sc_state",
        state="SC",
        evidence_text="funded on a 75% federal, 25% non-federal cost share basis",
        evidence_url="https://www.scemd.org/recover/mitigation/",
    )
    assert r["funding_lane"] == "federal_pass_through"
    assert r["federally_funded"] is True
    assert r["state_funded"] is False
    assert r["is_pass_through"] is True
    assert not funding_lane_invariant_failures(r)


def test_sc_gov_url_alone_does_not_create_an_sc_state_lane() -> None:
    r = _lane(source_url="https://ria.sc.gov/grants/", state="SC")
    assert r["funding_lane"] == "unknown"
    assert "sc_gov_source_url_does_not_determine_funding_lane" in r["notes"]


def test_sc_agency_administration_alone_does_not_create_an_sc_state_lane() -> None:
    r = _lane(state_agency="SC Housing", administering_agency="SC Housing", state="SC")
    assert r["funding_lane"] == "unknown"
    assert "sc_agency_administration_does_not_determine_funding_lane" in r["notes"]


def test_source_lane_does_not_determine_opportunity_lane() -> None:
    """The core of the correction."""
    r = _lane(source_lane="sc_state", state="SC")
    assert r["funding_lane"] == "unknown"
    assert "source_lane_does_not_determine_opportunity_funding_lane" in r["notes"]


@pytest.mark.parametrize(
    "funder", ["FEMA", "HUD", "EPA", "USDA", "HHS", "DOI", "DOL", "Treasury"]
)
def test_federal_funder_evidence_prevents_pure_sc_state(funder: str) -> None:
    r = _lane(
        state_agency="Some SC Agency",
        federal_agency=funder,
        state="SC",
        source_lane="sc_state",
        evidence_text=f"awarded by {funder}",
        evidence_url="https://example.gov/notice",
    )
    assert r["funding_lane"] != "sc_state"
    assert r["funding_lane"] in FEDERALLY_FUNDED_LANES
    assert r["state_funded"] is False


def test_federal_evidence_in_text_alone_prevents_sc_state() -> None:
    """No federal_agency field, but the evidence text names CDBG."""
    r = _lane(
        state_agency="SCOR",
        state="SC",
        funding_origin="unknown",
        evidence_text=(
            "Community Development Block Grant - Mitigation, a Federal HUD grant"
        ),
        evidence_url="https://scor.sc.gov/",
    )
    assert r["funding_lane"] == "federal_pass_through"
    assert r["federal_funder_evidence"]


def test_state_appropriation_evidence_supports_sc_state_only_with_citation() -> None:
    base = {
        "state_agency": "SC Housing",
        "state": "SC",
        "funding_origin": "state_trust_fund",
        "program_name": "South Carolina Housing Trust Fund",
        "evidence_text": (
            "state trust fund providing state funds for affordable housing"
        ),
    }
    uncited = _lane(**base)
    assert uncited["funding_lane"] == "unknown"
    assert "state_funding_claimed_without_cited_evidence" in uncited["reasons"]

    cited = _lane(
        **base,
        evidence_url="https://schousing.sc.gov/development/south-carolina-housing-trust-fund-htf",
    )
    assert cited["funding_lane"] == "sc_state"
    assert cited["state_funded"] is True
    assert cited["federally_funded"] is False
    assert not funding_lane_invariant_failures(cited)


def test_mixed_funding_origin_requires_human_review_and_stays_unknown() -> None:
    r = _lane(
        state_agency="SCDE",
        state="SC",
        funding_origin="mixed",
        program_name="SCDE grant opportunities",
        evidence_text="federal, state, and privately funded",
        evidence_url="https://ed.sc.gov/finance/grants/",
    )
    assert r["funding_lane"] == "unknown"
    assert r["human_review_required"] is True
    assert "mixed_funding_origin" in r["review_reasons"]
    assert not funding_lane_invariant_failures(r)


def test_both_federal_and_state_signals_also_go_to_review() -> None:
    r = _lane(
        state_agency="SCDES",
        federal_agency="EPA",
        state="SC",
        evidence_text="EPA 319 funds plus a state appropriation match",
        evidence_url="https://des.sc.gov/",
    )
    assert r["funding_lane"] == "unknown"
    assert "mixed_funding_origin_requires_human_review" in r["reasons"]


def test_unknown_funding_evidence_remains_unknown() -> None:
    """Never a default to sc_state."""
    r = _lane(program_name="A Programme", state="SC")
    assert r["funding_lane"] == "unknown"
    assert "no_funding_origin_evidence" in r["reasons"]
    assert r["human_review_required"] is True


def test_federal_sc_relevant_stays_federal_not_state() -> None:
    r = _lane(
        federal_agency="ED",
        funding_origin="federal_appropriation",
        state="SC",
        sc_relevant=True,
        evidence_text="Department of Education discretionary grant",
        evidence_url="https://example.gov/notice",
    )
    assert r["funding_lane"] == "federal_sc_relevant"
    assert r["federally_funded"] is True
    assert r["state_funded"] is False


def test_plain_federal_when_not_sc_relevant() -> None:
    r = _lane(
        federal_agency="ED",
        funding_origin="federal_appropriation",
        sc_relevant=False,
        evidence_text="Department of Education discretionary grant",
        evidence_url="https://example.gov/notice",
    )
    assert r["funding_lane"] == "federal"


@pytest.mark.parametrize(
    "origin,expected",
    [
        ("local_government", "local_regional"),
        ("private_foundation", "foundation"),
        ("corporate_giving", "corporate"),
    ],
)
def test_non_government_origins_resolve(origin: str, expected: str) -> None:
    r = _lane(
        funding_origin=origin,
        evidence_url="https://example.org/x",
        evidence_text="award",
    )
    assert r["funding_lane"] == expected


def test_lane_groups_partition_correctly() -> None:
    assert not (FEDERALLY_FUNDED_LANES & STATE_FUNDED_LANES)
    assert not (FEDERALLY_FUNDED_LANES & PRIVATE_FUNDED_LANES)
    assert (
        FEDERALLY_FUNDED_LANES
        | STATE_FUNDED_LANES
        | PRIVATE_FUNDED_LANES
        | {"local_regional", "unknown"}
    ) == FUNDING_LANES


def test_no_fourth_lane_vocabulary_was_created() -> None:
    """Doc 440 found three. Gate 79 bridges them; it must not add a fourth."""
    from nativeforge.services.native_opportunity_discovery_service import LANES
    from nativeforge.services.sc_native_routing_service import (
        FUNDING_LANES as SC_ROUTING_LANES,
    )

    for lane in FUNDING_LANES:
        assert sc_routing_lane(lane) in SC_ROUTING_LANES
        assert discovery_lane(lane) in LANES


def test_projections_are_total_over_the_canonical_set() -> None:
    for lane in FUNDING_LANES:
        assert lane in SC_ROUTING_LANE_MAP
        assert lane in DISCOVERY_LANE_MAP


def test_pass_through_projects_to_federal_in_both_older_vocabularies() -> None:
    """A lossy projection, but it must never land on a state value."""
    assert sc_routing_lane("federal_pass_through") == "federal_sc_relevant"
    assert discovery_lane("federal_pass_through") == "federal"


def test_invariants_reject_federal_money_marked_state_funded() -> None:
    r = _lane(
        state_agency="SCEMD",
        federal_agency="FEMA",
        funding_origin="federal_pass_through_to_state",
        state="SC",
        evidence_text="FEMA",
        evidence_url="https://example.gov",
    )
    r["state_funded"] = True
    assert "federal_money_marked_state_funded" in funding_lane_invariant_failures(r)


def test_invariants_reject_sc_state_with_a_federal_agency() -> None:
    r = _lane(
        state_agency="SC Housing",
        funding_origin="state_trust_fund",
        state="SC",
        evidence_text="state trust fund",
        evidence_url="https://example.sc.gov",
    )
    assert r["funding_lane"] == "sc_state"
    r["federal_agency"] = "HUD"
    assert "sc_state_lane_carries_a_federal_agency" in (
        funding_lane_invariant_failures(r)
    )


def test_invariants_reject_uncited_sc_state() -> None:
    r = _lane(
        state_agency="SC Housing",
        funding_origin="state_trust_fund",
        state="SC",
        evidence_text="state trust fund",
        evidence_url="https://example.sc.gov",
    )
    r["has_cited_evidence"] = False
    assert "sc_state_lane_without_cited_evidence" in funding_lane_invariant_failures(r)


def test_no_funding_lane_result_claims_coverage() -> None:
    r = _lane()
    assert r["coverage_claimed"] is False
    assert r["live_ingestion_claimed"] is False


# ── correction 2: exclusion evidence ────────────────────────────────────────


def test_federally_recognized_only_excludes_state_recognized_tribe() -> None:
    """The NACTEP case. The finding that motivated this gate."""
    r = evaluate_applicant_class(
        opportunity_id="nactep",
        applicant_class="state_recognized_tribe",
        eligibility_text=NACTEP_TEXT,
        evidence_reference=NACTEP_CITE,
    )
    assert r["result_state"] == "excluded_by_evidence"
    assert r["excluded"] is True
    assert r["is_exclusive_list"] is True
    assert not exclusion_invariant_failures(r)


def test_federally_recognized_only_does_not_exclude_federally_recognized() -> None:
    r = evaluate_applicant_class(
        opportunity_id="nactep",
        applicant_class="federally_recognized_tribe",
        eligibility_text=NACTEP_TEXT,
        evidence_reference=NACTEP_CITE,
    )
    assert r["result_state"] == "eligible"
    assert r["excluded"] is False
    assert not exclusion_invariant_failures(r)


def test_absence_of_state_recognized_language_alone_is_not_exclusion() -> None:
    """Silence is not exclusion. Only an exclusive list excludes."""
    r = evaluate_applicant_class(
        opportunity_id="opp-2",
        applicant_class="state_recognized_tribe",
        eligibility_text=(
            "Nonprofit organizations and units of local government may apply."
        ),
        evidence_reference="https://example.gov/notice",
    )
    assert r["result_state"] == "not_supported_by_evidence"
    assert r["excluded"] is False
    assert r["human_review_required"] is True


def test_bie_funded_school_eligibility_does_not_imply_tribal_government() -> None:
    """A narrow grant is not a broad one."""
    text = "Eligibility is limited to eligible BIE-funded schools"
    school = evaluate_applicant_class(
        opportunity_id="opp-3",
        applicant_class="bie_funded_school",
        eligibility_text=text,
        evidence_reference="https://example.gov/notice",
    )
    tribe = evaluate_applicant_class(
        opportunity_id="opp-3",
        applicant_class="federally_recognized_tribe",
        eligibility_text=text,
        evidence_reference="https://example.gov/notice",
    )
    assert school["result_state"] == "eligible"
    assert tribe["result_state"] == "excluded_by_evidence"
    assert tribe["result_state"] != "eligible"


def test_federal_trust_land_restriction_is_preserved_not_turned_into_exclusion() -> (
    None
):
    """A restriction narrows use; it does not remove a class."""
    text = (
        "Eligible Native American Veterans who wish to purchase, construct, or "
        "improve a home on Federal Trust land"
    )
    r = evaluate_applicant_class(
        opportunity_id="opp-4",
        applicant_class="native_individual",
        eligibility_text=text,
        evidence_reference="https://example.gov/notice",
    )
    assert "federal_trust_land" in r["restrictions"]
    assert r["result_state"] != "excluded_by_evidence"


def test_restrictions_survive_into_the_all_classes_result() -> None:
    r = evaluate_all_applicant_classes(
        opportunity_id="opp-4",
        eligibility_text="improve a home on Federal Trust land",
        evidence_reference="https://example.gov/notice",
    )
    assert "federal_trust_land" in r["restrictions"]


def test_exclusion_requires_a_citation() -> None:
    """An exclusion without a citation is an accusation."""
    r = evaluate_applicant_class(
        opportunity_id="nactep",
        applicant_class="state_recognized_tribe",
        eligibility_text=NACTEP_TEXT,
        evidence_reference=None,
    )
    assert r["result_state"] == "human_review_required"
    assert r["excluded"] is False
    assert "exclusion_indicated_but_no_citation_supplied" in r["reasons"]


def test_invariants_reject_an_uncited_exclusion() -> None:
    r = evaluate_applicant_class(
        opportunity_id="nactep",
        applicant_class="state_recognized_tribe",
        eligibility_text=NACTEP_TEXT,
        evidence_reference=NACTEP_CITE,
    )
    r["has_citation"] = False
    assert "exclusion_without_citation" in exclusion_invariant_failures(r)


def test_invariants_reject_exclusion_without_an_exclusive_list() -> None:
    r = evaluate_applicant_class(
        opportunity_id="opp-5",
        applicant_class="state_recognized_tribe",
        eligibility_text="Nonprofits may apply.",
        evidence_reference="https://example.gov/notice",
    )
    r["result_state"] = "excluded_by_evidence"
    r["excluded"] = True
    fails = exclusion_invariant_failures(r)
    assert "exclusion_without_an_exclusive_eligibility_list" in fails


def test_exclusion_is_applicant_class_specific() -> None:
    """Excluding one class says nothing about another."""
    text = "Eligibility is limited to Native American tribal organizations"
    per = evaluate_all_applicant_classes(
        opportunity_id="opp-6",
        eligibility_text=text,
        evidence_reference="https://example.gov/notice",
    )
    assert "tribal_organization" in per["eligible_classes"]
    assert "state_recognized_tribe" in per["excluded_classes"]
    # A class cannot be both.
    assert not set(per["eligible_classes"]) & set(per["excluded_classes"])
    assert not all_classes_invariant_failures(per)


def test_additional_evidence_can_widen_an_exclusive_list() -> None:
    r = evaluate_applicant_class(
        opportunity_id="nactep",
        applicant_class="state_recognized_tribe",
        eligibility_text=NACTEP_TEXT,
        evidence_reference=NACTEP_CITE,
        additional_expanding_evidence=[
            {
                "reference": "https://example.gov/amendment",
                "expands_classes": ["state_recognized_tribe"],
            }
        ],
    )
    assert r["result_state"] == "possibly_eligible"
    assert r["excluded"] is False


def test_widening_evidence_without_a_reference_does_not_reopen_the_list() -> None:
    r = evaluate_applicant_class(
        opportunity_id="nactep",
        applicant_class="state_recognized_tribe",
        eligibility_text=NACTEP_TEXT,
        evidence_reference=NACTEP_CITE,
        additional_expanding_evidence=[
            {"reference": "", "expands_classes": ["state_recognized_tribe"]}
        ],
    )
    assert r["result_state"] == "excluded_by_evidence"


def test_no_eligibility_text_is_unknown_not_exclusion() -> None:
    r = evaluate_applicant_class(
        opportunity_id="opp-7",
        applicant_class="state_recognized_tribe",
        eligibility_text=None,
        evidence_reference=NACTEP_CITE,
    )
    assert r["result_state"] == "unknown"
    assert r["excluded"] is False


def test_unknown_applicant_class_stays_unknown() -> None:
    r = evaluate_applicant_class(
        opportunity_id="opp-8",
        applicant_class="badgers",
        eligibility_text=NACTEP_TEXT,
        evidence_reference=NACTEP_CITE,
    )
    assert r["applicant_class"] == "unknown"
    assert r["result_state"] == "unknown"


def test_universal_ineligibility_stays_unassertable() -> None:
    """Gate 77's boundary is untouched. excluded_by_evidence is narrower."""
    r = evaluate_applicant_class(
        opportunity_id="nactep",
        applicant_class="state_recognized_tribe",
        eligibility_text=NACTEP_TEXT,
        evidence_reference=NACTEP_CITE,
    )
    assert r["result_state"] == "excluded_by_evidence"
    assert r["not_eligible_asserted"] is False
    r["not_eligible_asserted"] = True
    assert "forbidden_claim:not_eligible_asserted" in exclusion_invariant_failures(r)


def test_the_gate_77_guard_was_not_weakened() -> None:
    src = (
        ROOT
        / "src"
        / "nativeforge"
        / "services"
        / "federal_native_eligibility_service.py"
    ).read_text(encoding="utf-8")
    assert '"not_eligible_asserted": False' in src
    assert "forbidden_claim:not_eligible_asserted" in src


def test_applicant_classes_project_onto_the_gate_77_tiers() -> None:
    from nativeforge.services.federal_native_eligibility_service import (
        RECOGNITION_TIERS,
    )

    for cls in APPLICANT_CLASSES:
        tier = federal_tier_for(cls)
        assert tier is None or tier in RECOGNITION_TIERS


def test_result_states_are_the_declared_set() -> None:
    assert RESULT_STATES == {
        "eligible",
        "possibly_eligible",
        "excluded_by_evidence",
        "not_supported_by_evidence",
        "unknown",
        "human_review_required",
    }


def test_exclusivity_detection_requires_both_a_marker_and_a_named_class() -> None:
    only_marker = analyse_eligibility_text("Eligibility is limited to certain parties")
    assert only_marker["is_exclusive_list"] is False
    both = analyse_eligibility_text(NACTEP_TEXT)
    assert both["is_exclusive_list"] is True


def test_native_relevance_is_not_eligibility() -> None:
    """A programme about Native communities may still exclude Native applicants."""
    r = evaluate_applicant_class(
        opportunity_id="opp-9",
        applicant_class="state_recognized_tribe",
        eligibility_text=(
            "This program serves American Indian communities. Eligibility is "
            "limited to Federally recognized Indian tribes."
        ),
        evidence_reference="https://example.gov/notice",
    )
    assert r["result_state"] == "excluded_by_evidence"


def test_eligibility_proven_requires_both_eligible_and_a_citation() -> None:
    cited = evaluate_applicant_class(
        opportunity_id="nactep",
        applicant_class="federally_recognized_tribe",
        eligibility_text=NACTEP_TEXT,
        evidence_reference=NACTEP_CITE,
    )
    assert cited["eligibility_proven"] is True
    uncited = evaluate_applicant_class(
        opportunity_id="nactep",
        applicant_class="federally_recognized_tribe",
        eligibility_text=NACTEP_TEXT,
        evidence_reference=None,
    )
    assert uncited["eligibility_proven"] is False


# ── the research fixture ────────────────────────────────────────────────────


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_research_fixture_exists_and_claims_nothing() -> None:
    meta = _fixture()["_meta"]
    assert meta["monitoring_allowed"] is False
    assert meta["coverage_claimed"] is False
    assert meta["freshness_claimed"] is False
    assert meta["eligibility_proven"] is False
    assert meta["provenance"].startswith("research-derived model")


def test_research_fixture_invents_no_opportunity_records() -> None:
    """No dates, numbers, amounts or application URLs — none were captured."""
    body = FIXTURE.read_text(encoding="utf-8")
    for invented in (
        "close_date",
        "posted_date",
        "opportunity_number",
        "award_amount",
        "application_url",
        "deadline",
    ):
        assert invented not in body, f"fixture invented {invented}"


def test_research_fixture_marks_every_eligibility_as_unverified() -> None:
    for programme in _fixture()["programmes"]:
        assert programme["eligibility_verified"] is False


def test_research_fixture_has_no_checked_timestamp() -> None:
    assert _fixture()["source"]["last_checked_at"] is None
    assert _fixture()["source"]["robots_terms_status"] == "unresolved"


def test_research_fixture_records_the_host_state_lane_mismatch() -> None:
    source = _fixture()["source"]
    assert source["source_lane"] == "sc_state"
    assert source["opportunity_funding_lane_default"] == "federal_sc_relevant"


def test_every_fixture_programme_is_federally_funded_or_unknown() -> None:
    """The finding: a page for state tribes listing only federal programmes."""
    for programme in _fixture()["programmes"]:
        assert programme["funding_lane"] in FEDERALLY_FUNDED_LANES | {"unknown"}
        assert programme["funding_lane"] != "sc_state"


def test_fixture_pass_through_examples_classify_as_pass_through() -> None:
    for example in _fixture()["pass_through_examples"]:
        r = _lane(
            state_agency=example["state_agency"],
            federal_agency=example["federal_agency"],
            funding_origin=example["funding_origin"],
            administering_agency=example["state_agency"],
            source_url=example["source_url"],
            source_lane="sc_state",
            state="SC",
            evidence_text=example["evidence_as_captured"],
            evidence_url=example["source_url"],
        )
        assert r["funding_lane"] == example["expected_funding_lane"]
        assert r["federally_funded"] is True
        assert r["state_funded"] is False
        assert not funding_lane_invariant_failures(r)


def test_fixture_state_funded_example_classifies_as_sc_state_with_citation() -> None:
    example = _fixture()["state_funded_example"]
    r = _lane(
        state_agency=example["state_agency"],
        federal_agency=example["federal_agency"],
        funding_origin=example["funding_origin"],
        program_name=example["source_name"],
        source_url=example["source_url"],
        state="SC",
        evidence_text=example["evidence_as_captured"],
        evidence_url=example["source_url"],
    )
    assert r["funding_lane"] == example["expected_funding_lane"] == "sc_state"
    assert r["state_funded"] is True
    assert not funding_lane_invariant_failures(r)


def test_fixture_nactep_programme_excludes_state_recognized_tribes() -> None:
    nactep = next(
        p for p in _fixture()["programmes"] if "NACTEP" in p["programme_name"]
    )
    assert nactep["expected_exclusion_signal"] == "state_recognized_tribe"
    r = evaluate_applicant_class(
        opportunity_id="nactep",
        applicant_class="state_recognized_tribe",
        eligibility_text="Eligibility is limited to "
        + nactep["eligibility_text_as_captured"],
        evidence_reference=NACTEP_CITE,
    )
    assert r["result_state"] == "excluded_by_evidence"


def test_fixture_records_the_recognition_count_discrepancy() -> None:
    ctx = _fixture()["source"]["recognition_context"]
    assert ctx["sc_federally_recognized_tribes"] == 1
    assert ctx["sc_state_recognized_tribes"] == 10
    assert "discrepancy" in ctx["note"]


# ── the cleanliness filter, corrected in Gate 79 ────────────────────────────

CLEANLINESS_SCRIPT = ROOT / "scripts" / "verify_nativeforge_fixture_cleanliness.sh"


def _filter_porcelain(lines: list[str]) -> list[str]:
    """Run the script's own filter over synthetic porcelain lines.

    Behavioural rather than textual, and it touches no real fixture.
    """
    import subprocess

    result = subprocess.run(
        ["grep", "-vE", r"^(\?\?|A )"],
        input="\n".join(lines),
        capture_output=True,
        text=True,
        check=False,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def test_cleanliness_filter_ignores_untracked_and_staged_additions() -> None:
    """Gate 78F flagged a deliberately added new fixture as a mutation.

    A suite run cannot `git add`; anything it creates shows as `??`. So
    excluding `A ` opens no hole and removes a false positive.
    """
    assert _filter_porcelain(["?? fixtures/scratch.json"]) == []
    assert _filter_porcelain(["A  tests/fixtures/sc_research/new.json"]) == []


@pytest.mark.parametrize(
    "line",
    [
        " M fixtures/real_grants_corpus/nf15_eligibility_reingest_pulls.json",
        "M  fixtures/real_grants_corpus/nf14_mixed_corpus.json",
        "MM fixtures/real_grants_corpus/la_scaled_federal_grants.json",
        " D fixtures/real_grants_corpus/ta_tier2_state_grants.json",
        "D  fixtures/real_grants_corpus/ta_tier3_foundation_grants.json",
        "R  fixtures/real_grants_corpus/renamed.json",
    ],
)
def test_cleanliness_filter_still_catches_mutation(line: str) -> None:
    """The case that matters: a tracked evidence file changed underneath us."""
    assert _filter_porcelain([line]) == [line]


def test_cleanliness_script_documents_why_additions_are_excluded() -> None:
    body = CLEANLINESS_SCRIPT.read_text(encoding="utf-8")
    assert "test run cannot `git add`" in body
    assert "opens no hole" in body


# ── claims ──────────────────────────────────────────────────────────────────


def test_readiness_doc_claims_no_coverage_or_improvement() -> None:
    doc = (
        ROOT / "docs" / "operations" / "444_GATE79_PRODUCTION_READINESS_DELTA.md"
    ).read_text(encoding="utf-8")
    assert "Live SC source coverage:   NONE" in doc
    assert "65% improvement:           NOT CLAIMED" in doc
    assert "Controlled customer pilot: NO_GO" in doc
