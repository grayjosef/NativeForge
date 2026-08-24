"""Tests: Gate 79B contract wiring and vocabulary drift guards.

Gate 79 built the canonical funding-lane and exclusion-evidence contracts beside
the services that needed them. Gate 79B wires them in, and these tests keep the
wiring from rotting.

The property that matters most: **a canonical federal lane must never project
onto a state lane in any older vocabulary.** Everything else can be lossy; that
cannot, because it is the exact error Gate 79 existed to correct.

The second property: **exclusion is per applicant class.** The same opportunity
is eligible coverage for a federally recognized tribe and negative intelligence
for a state-recognized one, and neither view may overwrite the other.
"""

from __future__ import annotations

import pathlib

import pytest

from nativeforge.services.eligibility_exclusion_evidence_service import (
    APPLICANT_CLASSES,
    RESULT_STATES,
    evaluate_all_applicant_classes,
    evaluate_applicant_class,
)
from nativeforge.services.native_opportunity_discovery_service import (
    LANES as DISCOVERY_LANES,
)
from nativeforge.services.native_opportunity_discovery_service import (
    build_native_opportunity_record,
    opportunity_record_invariant_failures,
)
from nativeforge.services.opportunity_discovery_quality_service import (
    build_discovery_quality_score,
    discovery_quality_invariant_failures,
)
from nativeforge.services.opportunity_funding_lane_service import (
    FEDERALLY_FUNDED_LANES,
    FUNDING_LANES,
    STATE_FUNDED_LANES,
    classify_opportunity_funding_lane,
    discovery_lane,
    sc_routing_lane,
)
from nativeforge.services.sc_native_routing_service import (
    FUNDING_LANES as SC_ROUTING_LANES,
)
from nativeforge.services.sc_native_routing_service import (
    route_sc_opportunity,
    sc_routing_invariant_failures,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]

NACTEP_TEXT = (
    "Eligibility is limited to Federally recognized Indian tribes, tribal "
    "organizations, Alaska Native entities, and eligible BIE-funded schools"
)
NACTEP_CITE = "https://advance.sc.gov/grants-state-tribes"


# ── the property that must never break ──────────────────────────────────────


@pytest.mark.parametrize("lane", sorted(FEDERALLY_FUNDED_LANES))
def test_no_federal_lane_ever_projects_onto_a_state_value(lane: str) -> None:
    """The exact error Gate 79 corrected. Both older vocabularies."""
    assert sc_routing_lane(lane) not in STATE_FUNDED_LANES
    assert sc_routing_lane(lane) != "sc_state"
    assert discovery_lane(lane) != "state"


def test_federal_pass_through_specifically_never_becomes_sc_state() -> None:
    assert sc_routing_lane("federal_pass_through") == "federal_sc_relevant"
    assert discovery_lane("federal_pass_through") == "federal"


@pytest.mark.parametrize("lane", sorted(FUNDING_LANES))
def test_projections_land_inside_the_older_vocabularies(lane: str) -> None:
    """No fourth vocabulary: every canonical lane maps into both existing sets."""
    assert sc_routing_lane(lane) in SC_ROUTING_LANES
    assert discovery_lane(lane) in DISCOVERY_LANES


def test_only_sc_state_projects_to_a_state_value() -> None:
    """Inverse direction: nothing else may reach a state lane."""
    to_sc_state = {
        lane for lane in FUNDING_LANES if sc_routing_lane(lane) == "sc_state"
    }
    to_state = {lane for lane in FUNDING_LANES if discovery_lane(lane) == "state"}
    assert to_sc_state == {"sc_state"}
    assert to_state == {"sc_state"}


# ── routing wiring ──────────────────────────────────────────────────────────


def _route(**over: object) -> dict:
    kwargs: dict = {"opportunity_id": "opp-1", "state": "SC"}
    kwargs.update(over)
    return route_sc_opportunity(**kwargs)


@pytest.mark.parametrize(
    "state_agency,federal_agency,program",
    [
        ("SCEMD", "FEMA", "Hazard Mitigation Grant Program"),
        ("SCOR", "HUD", "Community Development Block Grant - Mitigation"),
        ("SCDES", "EPA", "Section 319 Nonpoint Source"),
    ],
)
def test_sc_administered_federal_money_does_not_become_sc_state(
    state_agency: str, federal_agency: str, program: str
) -> None:
    """The five Gate 78R sources, routed end to end through both contracts."""
    lane = classify_opportunity_funding_lane(
        opportunity_id="opp-1",
        state_agency=state_agency,
        federal_agency=federal_agency,
        program_name=program,
        funding_origin="federal_pass_through_to_state",
        administering_agency=state_agency,
        source_lane="sc_state",
        source_url="https://example.sc.gov/page",
        state="SC",
        evidence_text=f"{program} administered by {state_agency}",
        evidence_url="https://example.sc.gov/page",
    )
    assert lane["funding_lane"] == "federal_pass_through"

    routed = _route(
        canonical_funding_lane=lane["funding_lane"],
        state_agency=state_agency,
        federal_agency=federal_agency,
    )
    assert routed["funding_lane"] != "sc_state"
    assert routed["is_state_lane"] is False
    assert routed["is_federal_lane"] is True
    assert not sc_routing_invariant_failures(routed)


def test_pass_through_projection_is_marked_lossy() -> None:
    r = _route(canonical_funding_lane="federal_pass_through", federal_agency="FEMA")
    assert r["lane_projection_lossy"] is True
    assert r["lane_projection"]["canonical_funding_lane"] == "federal_pass_through"
    assert r["lane_projection"]["projected_lane"] == "federal_sc_relevant"
    assert any("lossy_lane_projection" in x for x in r["review_reasons"])


def test_source_lane_alone_cannot_override_opportunity_lane_evidence() -> None:
    """A source that says sc_state does not make the money state money."""
    lane = classify_opportunity_funding_lane(
        opportunity_id="opp-2",
        source_lane="sc_state",
        source_url="https://ria.sc.gov/grants/",
        state_agency="RIA",
        state="SC",
    )
    assert lane["funding_lane"] == "unknown"
    routed = _route(canonical_funding_lane=lane["funding_lane"])
    assert routed["funding_lane"] == "unknown"
    assert routed["is_state_lane"] is False


def test_mixed_funding_carries_human_review_through_routing() -> None:
    lane = classify_opportunity_funding_lane(
        opportunity_id="opp-3",
        state_agency="SCDE",
        funding_origin="mixed",
        state="SC",
        evidence_text="federal, state, and privately funded",
        evidence_url="https://ed.sc.gov/finance/grants/",
    )
    assert lane["human_review_required"] is True
    routed = _route(canonical_funding_lane=lane["funding_lane"])
    assert routed["human_review_required"] is True


def test_sc_state_survives_projection_when_evidenced() -> None:
    lane = classify_opportunity_funding_lane(
        opportunity_id="opp-4",
        state_agency="SC Housing",
        funding_origin="state_trust_fund",
        state="SC",
        evidence_text="state trust fund providing state funds",
        evidence_url="https://schousing.sc.gov/development",
    )
    assert lane["funding_lane"] == "sc_state"
    routed = _route(canonical_funding_lane="sc_state", state_agency="SC Housing")
    assert routed["funding_lane"] == "sc_state"
    assert routed["is_state_lane"] is True
    assert routed["lane_projection_lossy"] is False


def test_unrecognised_canonical_lane_is_refused_not_guessed() -> None:
    r = _route(canonical_funding_lane="sc_state_probably")
    assert r["funding_lane"] == "unknown"
    assert any("unrecognised_canonical_funding_lane" in x for x in r["review_reasons"])


def test_routing_invariant_catches_a_forged_state_projection() -> None:
    r = _route(canonical_funding_lane="federal_pass_through", federal_agency="FEMA")
    r["funding_lane"] = "sc_state"
    r["is_state_lane"] = True
    r["is_federal_lane"] = False
    fails = sc_routing_invariant_failures(r)
    assert "federal_canonical_lane_projected_onto_a_state_lane" in fails
    assert "federal_pass_through_projected_to_sc_state" in fails


def test_routing_without_a_canonical_lane_is_unchanged() -> None:
    """Backward compatibility: existing callers keep working."""
    r = _route(funding_lane="sc_state", state_agency="SC Housing")
    assert r["funding_lane"] == "sc_state"
    assert r["canonical_funding_lane"] is None
    assert r["lane_projection"] is None


# ── discovery wiring ────────────────────────────────────────────────────────


def _discovery(**over: object) -> dict:
    kwargs: dict = {
        "opportunity_id": "opp-1",
        "source_id": "src-1",
        "provenance_url": "https://example.gov/nofo",
    }
    kwargs.update(over)
    return build_native_opportunity_record(**kwargs)


def test_discovery_uses_the_canonical_lane() -> None:
    r = _discovery(canonical_funding_lane="federal_pass_through")
    assert r["lane"] == "federal"
    assert r["canonical_funding_lane"] == "federal_pass_through"
    assert r["lane_projection_lossy"] is True


def test_discovery_never_puts_federal_money_in_the_state_lane() -> None:
    for lane in sorted(FEDERALLY_FUNDED_LANES):
        r = _discovery(canonical_funding_lane=lane)
        assert r["lane"] != "state"


def test_discovery_invariant_catches_a_forged_state_lane() -> None:
    r = _discovery(canonical_funding_lane="federal_pass_through")
    r["lane"] = "state"
    assert "federal_canonical_lane_projected_onto_state" in (
        opportunity_record_invariant_failures(r)
    )


def test_exclusion_is_carried_into_the_discovery_record() -> None:
    exclusion = evaluate_all_applicant_classes(
        opportunity_id="nactep",
        eligibility_text=NACTEP_TEXT,
        evidence_reference=NACTEP_CITE,
    )
    r = _discovery(exclusion_result=exclusion)
    assert "state_recognized_tribe" in r["excluded_classes"]
    assert "federally_recognized_tribe" in r["eligible_classes"]
    assert r["has_exclusion_evidence"] is True


def test_state_recognized_exclusion_does_not_exclude_federally_recognized() -> None:
    """The single most important applicant-class property."""
    exclusion = evaluate_all_applicant_classes(
        opportunity_id="nactep",
        eligibility_text=NACTEP_TEXT,
        evidence_reference=NACTEP_CITE,
    )
    r = _discovery(exclusion_result=exclusion)
    assert "federally_recognized_tribe" not in r["excluded_classes"]
    assert "federally_recognized_tribe" in r["eligible_classes"]


def test_excluded_opportunity_stays_visible() -> None:
    """Excluded is negative intelligence, not noise. It must not disappear."""
    exclusion = evaluate_all_applicant_classes(
        opportunity_id="nactep",
        eligibility_text=NACTEP_TEXT,
        evidence_reference=NACTEP_CITE,
    )
    r = _discovery(exclusion_result=exclusion)
    assert r["visible"] is True
    assert any("excluded_by_evidence_for" in x for x in r["review_reasons"])


def test_discovery_invariant_catches_a_hidden_excluded_opportunity() -> None:
    exclusion = evaluate_all_applicant_classes(
        opportunity_id="nactep", eligibility_text=NACTEP_TEXT,
        evidence_reference=NACTEP_CITE,
    )
    r = _discovery(exclusion_result=exclusion)
    r["visible"] = False
    assert "excluded_opportunity_hidden_instead_of_marked" in (
        opportunity_record_invariant_failures(r)
    )


def test_discovery_invariant_catches_a_class_both_eligible_and_excluded() -> None:
    r = _discovery(
        exclusion_result={
            "excluded_classes": ["state_recognized_tribe"],
            "eligible_classes": ["state_recognized_tribe"],
        }
    )
    fails = opportunity_record_invariant_failures(r)
    assert any(f.startswith("class_both_eligible_and_excluded") for f in fails)


def test_missing_citation_cannot_create_exclusion_in_the_record() -> None:
    exclusion = evaluate_all_applicant_classes(
        opportunity_id="nactep", eligibility_text=NACTEP_TEXT,
        evidence_reference=None,
    )
    r = _discovery(exclusion_result=exclusion)
    assert r["excluded_classes"] == []
    assert r["has_exclusion_evidence"] is False


def test_native_relevance_still_does_not_imply_eligibility() -> None:
    """Gate 76's rule survives the wiring."""
    r = _discovery(
        native_relevance_classification={
            "label": "native_specific", "structured_signal": True, "keyword_hit": False
        },
        native_relevance_evidence=[
            {"kind": "explicit_tribal_eligibility_text",
             "reference": "https://example.gov/nofo#elig"}
        ],
        eligibility_evidence=[],
    )
    assert r["native_relevance_credited"] is True
    assert r["eligibility_state"] != "eligible"


def test_keyword_only_still_gets_no_credit_after_wiring() -> None:
    r = _discovery(
        native_relevance_classification={
            "label": "native_specific", "structured_signal": False, "keyword_hit": True
        },
        native_relevance_evidence=[
            {"kind": "explicit_tribal_eligibility_text",
             "reference": "https://example.gov/nofo#elig"}
        ],
    )
    assert r["native_relevance_credited"] is False


def test_discovery_without_wiring_params_is_unchanged() -> None:
    """Backward compatibility."""
    r = _discovery(lane="federal", federal_agency="ED")
    assert r["lane"] == "federal"
    assert r["canonical_funding_lane"] is None
    assert r["excluded_classes"] == []


# ── scoring ─────────────────────────────────────────────────────────────────

_OPP = {
    "source_id": "s1",
    "source_url": "https://example.gov/nofo",
    "extraction_timestamp": "2026-08-24T00:00:00Z",
    "eligibility_evidence": [{"kind": "explicit_eligible_applicant_list"}],
    "eligibility_state": "eligible",
    "recognition_tier": "federally_recognized",
    "native_relevance_evidence": [{"kind": "explicit_tribal_eligibility_text"}],
    "authority_requirements": ["tribal_council_resolution"],
    "excluded_classes": ["state_recognized_tribe"],
}


def _score(applicant_class: str | None) -> dict:
    return build_discovery_quality_score(
        opportunities=[dict(_OPP)], coverage={}, applicant_class=applicant_class
    )


def test_excluded_opportunity_is_not_eligible_coverage_for_that_class() -> None:
    s = _score("state_recognized_tribe")
    assert s["eligibility_evidence_score"] == 0.0
    assert s["excluded_for_class_count"] == 1
    assert not discovery_quality_invariant_failures(s)


def test_the_same_opportunity_remains_eligible_coverage_for_another_class() -> None:
    """State-recognized exclusion must not suppress the federally recognized path."""
    s = _score("federally_recognized_tribe")
    assert s["eligibility_evidence_score"] == 1.0
    assert s["excluded_for_class_count"] == 0


def test_excluded_opportunity_counts_as_negative_intelligence() -> None:
    s = _score("state_recognized_tribe")
    assert s["negative_intelligence_count"] == 1
    # And it is still in the corpus: the raw and unique counts are unchanged.
    assert s["opportunity_count_raw"] == 1
    assert s["opportunity_count_unique"] == 1


def test_excluded_is_never_counted_as_eligible_coverage() -> None:
    for cls in (None, "state_recognized_tribe", "federally_recognized_tribe"):
        assert _score(cls)["excluded_counted_as_eligible_coverage"] is False


def test_unknown_eligibility_does_not_count_as_eligible() -> None:
    unknown = dict(_OPP)
    unknown["eligibility_state"] = "unknown"
    unknown["excluded_classes"] = []
    s = build_discovery_quality_score(
        opportunities=[unknown], coverage={}, applicant_class="state_recognized_tribe"
    )
    assert s["eligibility_evidence_score"] == 0.0
    assert s["unknown_eligibility_counted_as_eligible"] is False


def test_possibly_eligible_still_counts_as_uncertain_coverage() -> None:
    maybe = dict(_OPP)
    maybe["eligibility_state"] = "possibly_eligible"
    maybe["excluded_classes"] = []
    s = build_discovery_quality_score(
        opportunities=[maybe], coverage={}, applicant_class="native_nonprofit"
    )
    assert s["eligibility_evidence_score"] == 1.0


def test_scoring_without_an_applicant_class_is_unchanged() -> None:
    """Backward compatibility: the previous behaviour exactly."""
    s = _score(None)
    assert s["scored_for_applicant_class"] is None
    assert s["excluded_for_class_count"] == 0
    assert s["eligibility_evidence_score"] == 1.0
    assert not discovery_quality_invariant_failures(s)


def test_scoring_invariant_catches_exclusions_without_a_class() -> None:
    s = _score(None)
    s["excluded_for_class_count"] = 2
    assert "exclusions_counted_without_an_applicant_class" in (
        discovery_quality_invariant_failures(s)
    )


def test_scoring_invariant_catches_a_negative_intelligence_mismatch() -> None:
    s = _score("state_recognized_tribe")
    s["negative_intelligence_count"] = 99
    assert "negative_intelligence_count_disagrees_with_exclusions" in (
        discovery_quality_invariant_failures(s)
    )


# ── drift guards ────────────────────────────────────────────────────────────


def _services_declaring(pattern: str) -> list[str]:
    import re

    services = ROOT / "src" / "nativeforge" / "services"
    return sorted(
        p.name
        for p in services.glob("*.py")
        if re.search(pattern, p.read_text(encoding="utf-8"), re.M)
    )


def test_no_service_added_a_fourth_funding_lane_vocabulary() -> None:
    """Doc 445 counted the funding-lane vocabularies. This pins the count."""
    assert _services_declaring(r"^FUNDING_LANES\s*=") == [
        "opportunity_funding_lane_service.py",
        "sc_native_routing_service.py",
    ], "a new FUNDING_LANES vocabulary appeared"


def test_the_bare_lanes_name_is_used_by_exactly_two_unrelated_concepts() -> None:
    """`LANES` is declared twice for two different things, which is a naming
    collision rather than lane drift:

      native_opportunity_discovery_service.LANES  — opportunity funding lanes
      source_seed_catalog.LANES                   — seed catalog GROUPINGS
                                                    (federal / south_carolina /
                                                     expansion)

    The second is not a funding classification and must never be projected onto
    or from the canonical funding lanes. Pinned here so a future reader does not
    mistake one for the other, and so a genuinely new declaration still fails.
    """
    assert _services_declaring(r"^LANES\s*=") == [
        "native_opportunity_discovery_service.py",
        "source_seed_catalog.py",
    ], "a new bare LANES vocabulary appeared"

    from nativeforge.services.source_seed_catalog import LANES as SEED_LANES

    # Disjoint from the funding vocabulary apart from the shared word "federal",
    # which is why the collision is worth pinning rather than ignoring.
    assert set(SEED_LANES) == {"federal", "south_carolina", "expansion"}
    assert "south_carolina" not in FUNDING_LANES
    assert "expansion" not in FUNDING_LANES


def test_exclusion_result_states_are_the_single_declared_set() -> None:
    assert RESULT_STATES == {
        "eligible", "possibly_eligible", "excluded_by_evidence",
        "not_supported_by_evidence", "unknown", "human_review_required",
    }


def test_not_eligible_remains_unassertable() -> None:
    """Unchanged by the wiring, in both services that guard it."""
    for name in (
        "federal_native_eligibility_service.py",
        "eligibility_exclusion_evidence_service.py",
    ):
        src = (ROOT / "src" / "nativeforge" / "services" / name).read_text(
            encoding="utf-8"
        )
        assert '"not_eligible_asserted": False' in src
        assert "forbidden_claim:not_eligible_asserted" in src


def test_excluded_by_evidence_remains_citation_required() -> None:
    cited = evaluate_applicant_class(
        opportunity_id="nactep", applicant_class="state_recognized_tribe",
        eligibility_text=NACTEP_TEXT, evidence_reference=NACTEP_CITE,
    )
    uncited = evaluate_applicant_class(
        opportunity_id="nactep", applicant_class="state_recognized_tribe",
        eligibility_text=NACTEP_TEXT, evidence_reference=None,
    )
    assert cited["result_state"] == "excluded_by_evidence"
    assert uncited["result_state"] == "human_review_required"


def test_applicant_classes_are_the_single_declared_set() -> None:
    assert len(APPLICANT_CLASSES) == 8
    assert "state_recognized_tribe" in APPLICANT_CLASSES
    assert "federally_recognized_tribe" in APPLICANT_CLASSES


def test_hermetic_and_corpus_guards_untouched() -> None:
    """Gate 79B must not have weakened Gate 77B or Gate 78E."""
    guard = (
        ROOT / "src" / "nativeforge" / "services" / "hermetic_test_guard_service.py"
    ).read_text(encoding="utf-8")
    assert "assert_live_network_allowed" in guard
    assert "resolve_writeback_path" in guard
    adapter = (
        ROOT / "src" / "nativeforge" / "services"
        / "grants_gov_search_api_adapter_service.py"
    ).read_text(encoding="utf-8")
    assert "assert_live_network_allowed(url=url" in adapter


# ── claims ──────────────────────────────────────────────────────────────────


def test_readiness_doc_claims_no_coverage() -> None:
    doc = (
        ROOT / "docs" / "operations" / "448_GATE79B_PRODUCTION_READINESS_DELTA.md"
    ).read_text(encoding="utf-8")
    assert "Live SC source coverage:   NONE" in doc
    assert "65% improvement:           NOT CLAIMED" in doc
    assert "Controlled customer pilot: NO_GO" in doc
