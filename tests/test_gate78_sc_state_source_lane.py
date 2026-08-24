"""Tests: Gate 78 South Carolina state source lane.

Two boundaries carry this gate.

**SC-specific is not SC-only.** A federal opportunity an SC organization can
pursue stays federal. Collapsing it into the state lane would undercount federal
and overcount state coverage, telling a customer their funding landscape is
smaller and more local than it is — for a tribal organization in a state with
few state-administered Native programs, that is actively misleading.

**State recognition is not federal recognition.** South Carolina has
state-recognized tribes, so this is the local case rather than an abstraction.
Neither tier ever implies the other.

Plus the carry-forward: three latent persist services could rewrite committed
corpus evidence by default. All three are now guarded, proved here without
touching the network or a committed file.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from nativeforge.services.hermetic_test_guard_service import (
    ENV_ALLOW_CORPUS_WRITEBACK,
    ENV_ALLOW_LIVE_NETWORK,
    ENV_ALLOW_SOURCE_FIXTURE_OVERWRITE,
    is_source_controlled,
    resolve_writeback_path,
)
from nativeforge.services.sc_federal_discovery_improvement_service import (
    RECOGNITION_ROUTES,
    SC_CATEGORIES,
)
from nativeforge.services.sc_native_routing_service import (
    FEDERAL_LANES,
    FUNDING_LANES,
    RECOGNITION_TIERS,
    SECTORS,
    STATE_LANES,
    recognition_tier_route,
    route_sc_opportunity,
    sc_routing_invariant_failures,
    sector_category,
)
from nativeforge.services.sc_source_seed_catalog import (
    SC_SEED_LANES,
    build_sc_seed_catalog,
    sc_seed_catalog_invariant_failures,
)
from nativeforge.services.sc_state_source_lane_service import (
    NON_STATE_AGENCY_FAMILIES,
    RECOGNITION_RELEVANCE,
    SC_SOURCE_FAMILIES,
    STATE_AGENCY_REQUIRED_FAMILIES,
    build_sc_source,
    normalize_recognition_relevance,
    recognition_route,
    sc_source_invariant_failures,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]

GOOD_SC_SOURCE = {
    "source_id": "sc-1",
    "source_family": "sc_agency_grant_page",
    "state": "SC",
    "state_agency": "Example SC Department",
    "program_name": "Example Program",
    "source_url": "https://example.sc.gov/grants",
    "access_method": "html_page_scheduled_check",
    "robots_terms_status": "reviewed_allowed",
    "refresh_cadence": "weekly",
    "state_program_scope": "agency_wide",
    "provenance_url": "https://example.sc.gov/grants",
    "promotion_status": "monitoring",
}


@pytest.fixture(autouse=True)
def _clear_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    for flag in (
        ENV_ALLOW_LIVE_NETWORK,
        ENV_ALLOW_CORPUS_WRITEBACK,
        ENV_ALLOW_SOURCE_FIXTURE_OVERWRITE,
    ):
        monkeypatch.delenv(flag, raising=False)


# ── SC ownership and the federal boundary ───────────────────────────────────


def test_complete_cleared_sc_source_may_monitor() -> None:
    """The gate must be passable, or it is theatre rather than a gate."""
    r = build_sc_source(**GOOD_SC_SOURCE)
    assert r["incomplete_reasons"] == [], r["incomplete_reasons"]
    assert r["blocked_reasons"] == [], r["blocked_reasons"]
    assert r["monitoring_allowed"] is True
    assert not sc_source_invariant_failures(r)


def test_sc_source_must_have_state_sc() -> None:
    for state in ("NC", "GA", None, ""):
        r = build_sc_source(**{**GOOD_SC_SOURCE, "state": state})
        assert r["monitoring_allowed"] is False
        assert any(
            b.startswith("not_a_south_carolina_source") for b in r["blocked_reasons"]
        )


def test_sc_source_cannot_be_federally_owned() -> None:
    """A federal opportunity relevant to SC belongs in the federal lane."""
    r = build_sc_source(**{**GOOD_SC_SOURCE, "federal_agency": "HHS"})
    assert r["monitoring_allowed"] is False
    assert "federally_owned_source_not_sc_state:HHS" in r["blocked_reasons"]
    # The field is recorded as rejected, never carried.
    assert r["federal_agency"] is None
    assert r["rejected_federal_agency"] == "HHS"


def test_invariants_reject_an_sc_source_carrying_a_federal_agency() -> None:
    r = build_sc_source(**GOOD_SC_SOURCE)
    r["federal_agency"] = "HHS"
    assert "sc_state_source_carries_a_federal_agency" in sc_source_invariant_failures(r)


def test_sc_source_stays_in_the_sc_state_lane() -> None:
    r = build_sc_source(**GOOD_SC_SOURCE)
    assert r["lane"] == "sc_state"
    r["lane"] = "federal"
    assert "sc_source_left_the_sc_state_lane" in sc_source_invariant_failures(r)


@pytest.mark.parametrize("family", sorted(STATE_AGENCY_REQUIRED_FAMILIES))
def test_agency_specific_families_require_a_state_agency(family: str) -> None:
    """ "South Carolina" does not identify whose grant page this is."""
    r = build_sc_source(
        **{**GOOD_SC_SOURCE, "source_family": family, "state_agency": None}
    )
    assert r["complete"] is False
    assert "state_agency_required_for_agency_specific_source" in r["incomplete_reasons"]
    assert r["monitoring_allowed"] is False


@pytest.mark.parametrize("family", sorted(NON_STATE_AGENCY_FAMILIES))
def test_private_and_local_families_need_no_state_agency(family: str) -> None:
    """A community foundation has no state agency; demanding one would be wrong."""
    r = build_sc_source(
        **{**GOOD_SC_SOURCE, "source_family": family, "state_agency": None}
    )
    assert (
        "state_agency_required_for_agency_specific_source"
        not in r["incomplete_reasons"]
    )


def test_unknown_source_family_is_blocked() -> None:
    r = build_sc_source(**{**GOOD_SC_SOURCE, "source_family": "sc_carrier_pigeon"})
    assert r["source_family"] == "unknown"
    assert "source_family_unknown" in r["blocked_reasons"]


# ── monitoring, provenance, freshness ───────────────────────────────────────


@pytest.mark.parametrize(
    "status",
    ["unreviewed", "unknown", "reviewed_disallowed", "reviewed_requires_agreement"],
)
def test_unresolved_terms_block_monitoring(status: str) -> None:
    r = build_sc_source(**{**GOOD_SC_SOURCE, "robots_terms_status": status})
    assert r["monitoring_allowed"] is False
    assert any(b.startswith("robots_terms_not_cleared") for b in r["blocked_reasons"])


def test_source_without_provenance_cannot_count_coverage() -> None:
    r = build_sc_source(**{**GOOD_SC_SOURCE, "provenance_url": None})
    assert r["counts_toward_coverage"] is False
    assert "no_provenance_url" in r["incomplete_reasons"]


def test_source_without_a_check_timestamp_cannot_claim_freshness() -> None:
    r = build_sc_source(**GOOD_SC_SOURCE)
    assert r["freshness_claimable"] is False
    r["freshness_claimable"] = True
    assert "freshness_claimable_without_a_check_timestamp" in (
        sc_source_invariant_failures(r)
    )


def test_no_sc_source_claims_coverage_or_ingestion() -> None:
    r = build_sc_source(**GOOD_SC_SOURCE)
    assert r["coverage_claimed"] is False
    assert r["live_ingestion_claimed"] is False
    # Source-level relevance is never opportunity-level eligibility.
    assert r["eligibility_determined"] is False


# ── recognition relevance stays independent ─────────────────────────────────


def test_state_recognized_does_not_imply_federally_recognized() -> None:
    d = normalize_recognition_relevance(["state_recognized_relevant"])
    assert d["state_recognized_relevant"] is True
    assert d["federally_recognized_relevant"] is False
    assert "federally_recognized" not in d["recognition_routes"]


def test_federally_recognized_does_not_imply_state_recognized() -> None:
    d = normalize_recognition_relevance(["federally_recognized_relevant"])
    assert d["federally_recognized_relevant"] is True
    assert d["state_recognized_relevant"] is False
    assert "state_recognized" not in d["recognition_routes"]


def test_both_tiers_can_be_held_together_when_both_are_supplied() -> None:
    d = normalize_recognition_relevance(
        ["state_recognized_relevant", "federally_recognized_relevant"]
    )
    assert d["state_recognized_relevant"] is True
    assert d["federally_recognized_relevant"] is True
    assert set(d["recognition_routes"]) == {"state_recognized", "federally_recognized"}


def test_unknown_recognition_remains_unknown() -> None:
    for tags in (None, [], ["unknown"]):
        d = normalize_recognition_relevance(tags)
        assert d["recognition_relevance"] == ["unknown"]
        assert d["recognition_known"] is False


def test_unrecognised_relevance_tags_are_surfaced() -> None:
    r = build_sc_source(**{**GOOD_SC_SOURCE, "recognition_relevance": ["made_up_tier"]})
    assert "made_up_tier" in r["unrecognised_relevance_tags"]
    assert "unrecognised_recognition_relevance_tags" in r["incomplete_reasons"]


@pytest.mark.parametrize("tag", sorted(RECOGNITION_RELEVANCE))
def test_every_relevance_tag_projects_into_the_existing_vocabulary(tag: str) -> None:
    """No second recognition vocabulary may appear."""
    assert recognition_route(tag) in RECOGNITION_ROUTES


# ── routing: lanes stay distinct, joinable ──────────────────────────────────


def _route(**over: object) -> dict:
    kwargs: dict = {
        "opportunity_id": "opp-1",
        "funding_lane": "sc_state",
        "state": "SC",
        "state_agency": "Example SC Department",
        "sectors": ["housing"],
        "recognition_tiers": ["state_recognized"],
    }
    kwargs.update(over)
    return route_sc_opportunity(**kwargs)


def test_sc_state_and_federal_lanes_are_distinct() -> None:
    state = _route(funding_lane="sc_state")
    federal = _route(
        funding_lane="federal_sc_relevant",
        state_agency=None,
        federal_agency="HHS",
        sc_location_relevant=True,
    )
    assert state["is_state_lane"] is True and state["is_federal_lane"] is False
    assert federal["is_federal_lane"] is True and federal["is_state_lane"] is False


def test_federal_opportunity_relevant_to_sc_stays_federal() -> None:
    """SC-specific is not SC-only."""
    r = _route(
        funding_lane="federal_sc_relevant",
        state="SC",
        state_agency=None,
        federal_agency="HHS",
        sc_location_relevant=True,
    )
    assert r["funding_lane"] == "federal_sc_relevant"
    assert r["is_federal_lane"] is True
    assert r["federal_agency"] == "HHS"
    # It still joins the customer's SC view.
    assert r["sc_relevant"] is True
    assert not sc_routing_invariant_failures(r)


def test_sc_state_lane_cannot_carry_a_federal_agency() -> None:
    r = _route(funding_lane="sc_state", federal_agency="HHS")
    assert "sc_state_lane_cannot_carry_a_federal_agency" in r["blocked_reasons"]


def test_invariants_reject_an_opportunity_in_both_lanes() -> None:
    r = _route()
    r["is_federal_lane"] = True
    assert "opportunity_in_both_state_and_federal_lanes" in (
        sc_routing_invariant_failures(r)
    )


def test_lane_sets_are_disjoint() -> None:
    assert not (FEDERAL_LANES & STATE_LANES)
    assert (FEDERAL_LANES | STATE_LANES) <= FUNDING_LANES


def test_sc_state_lane_rejects_a_non_sc_state() -> None:
    r = _route(funding_lane="sc_state", state="NC")
    assert any(
        b.startswith("sc_state_lane_with_a_non_sc_state") for b in r["blocked_reasons"]
    )


# ── sectors and tiers ───────────────────────────────────────────────────────


def test_multiple_sectors_are_preserved() -> None:
    r = _route(sectors=["housing", "health", "economic_development"])
    assert r["sectors"] == ["economic_development", "health", "housing"]
    assert len(r["sector_categories"]) == 3


def test_sectors_project_into_the_existing_category_vocabulary() -> None:
    for sector in SECTORS:
        assert sector_category(sector) in SC_CATEGORIES


def test_recognition_tiers_project_into_the_existing_route_vocabulary() -> None:
    for tier in RECOGNITION_TIERS:
        assert recognition_tier_route(tier) in RECOGNITION_ROUTES


def test_unrecognised_sectors_surface_for_review() -> None:
    r = _route(sectors=["housing", "underwater_basket_weaving"])
    assert "underwater_basket_weaving" in r["unrecognised_sectors"]
    assert r["human_review_required"] is True


def test_multiple_recognition_tiers_are_preserved() -> None:
    r = _route(recognition_tiers=["state_recognized", "native_nonprofit"])
    assert r["recognition_tiers"] == ["native_nonprofit", "state_recognized"]


def test_unknown_sectors_and_tiers_stay_unknown() -> None:
    r = _route(sectors=[], recognition_tiers=[])
    assert r["sectors"] == ["unknown"]
    assert r["recognition_tiers"] == ["unknown"]


# ── eligibility is neither location nor relevance ───────────────────────────


def test_sc_location_relevance_is_not_eligibility() -> None:
    r = _route(sc_location_relevant=True, eligibility_evidence=[])
    assert r["eligibility_state"] == "unknown"
    assert "sc_location_relevance_is_not_eligibility" in r["notes"]


def test_native_relevance_evidence_is_not_eligibility_by_itself() -> None:
    """A grant can be unmistakably Native-relevant and closed to Native applicants."""
    r = _route(native_relevance_evidenced=True, eligibility_evidence=[])
    assert r["eligibility_state"] == "unknown"
    assert "native_relevance_evidence_is_not_eligibility_by_itself" in r["notes"]


def test_both_together_still_are_not_eligibility() -> None:
    r = _route(
        sc_location_relevant=True,
        native_relevance_evidenced=True,
        eligibility_evidence=[],
    )
    assert r["eligibility_state"] == "unknown"
    assert r["human_review_required"] is True


def test_explicit_tier_evidence_gives_that_tier_eligibility() -> None:
    r = _route(
        eligibility_evidence=[
            {
                "kind": "explicit_state_recognized_tribe_eligibility",
                "reference": "https://example.sc.gov/nofo#applicants",
            }
        ]
    )
    assert r["tier_eligibility"]["state_recognized"] == "eligible"
    # And only that tier.
    assert r["tier_eligibility"]["federally_recognized"] == "unknown"
    assert not sc_routing_invariant_failures(r)


def test_general_applicant_list_yields_possibly_eligible() -> None:
    r = _route(
        eligibility_evidence=[
            {
                "kind": "explicit_eligible_applicant_list",
                "reference": "https://example.sc.gov/nofo#applicants",
            }
        ]
    )
    for tier in ("federally_recognized", "state_recognized", "native_nonprofit"):
        assert r["tier_eligibility"][tier] == "possibly_eligible"
    assert r["human_review_required"] is True


def test_evidence_without_a_reference_is_not_evidence() -> None:
    r = _route(
        eligibility_evidence=[
            {"kind": "explicit_state_recognized_tribe_eligibility", "reference": "  "}
        ]
    )
    assert r["eligibility_state"] == "unknown"


def test_invariants_reject_eligibility_without_evidence() -> None:
    r = _route(eligibility_evidence=[])
    r["eligibility_state"] = "eligible"
    fails = sc_routing_invariant_failures(r)
    assert "eligible_without_any_evidence" in fails


# ── seed catalog ────────────────────────────────────────────────────────────


def test_sc_seed_catalog_builds() -> None:
    c = build_sc_seed_catalog()
    assert c["record_count"] >= 7
    assert c["state"] == "SC"
    assert not sc_seed_catalog_invariant_failures(c)


def test_no_sc_seed_is_monitorable() -> None:
    c = build_sc_seed_catalog()
    assert c["monitoring_allowed_count"] == 0
    for r in c["records"]:
        assert r["monitoring_allowed"] is False


def test_no_sc_seed_claims_a_check_timestamp_or_freshness() -> None:
    for r in build_sc_seed_catalog()["records"]:
        assert r["last_checked_at"] is None
        assert r["freshness_claimable"] is False


def test_no_sc_seed_carries_a_url() -> None:
    """Unlike the federal lane there is no canonical SC entry point to assert."""
    c = build_sc_seed_catalog()
    assert c["with_url_count"] == 0
    for r in c["records"]:
        assert r["source_url"] is None


def test_every_sc_seed_is_discovered_and_unreviewed() -> None:
    for r in build_sc_seed_catalog()["records"]:
        assert r["promotion_status"] == "discovered"
        assert r["robots_terms_status"] == "unreviewed"


def test_no_sc_seed_expects_native_relevance_without_examination() -> None:
    """Whether a source carries Native-relevant work is a finding, not a guess."""
    for r in build_sc_seed_catalog()["records"]:
        assert r["native_relevance_expected"] is False


def test_sc_seed_catalog_claims_no_coverage() -> None:
    c = build_sc_seed_catalog()
    assert c["coverage_claimed"] is False
    assert c["live_ingestion_claimed"] is False
    assert c["sc_coverage_complete_claimed"] is False


@pytest.mark.parametrize("lane", sorted(SC_SEED_LANES))
def test_each_sc_lane_builds_alone(lane: str) -> None:
    c = build_sc_seed_catalog(lane)
    assert c["record_count"] >= 1
    assert not sc_seed_catalog_invariant_failures(c)


def test_all_sc_seed_families_are_recognised() -> None:
    for r in build_sc_seed_catalog()["records"]:
        assert r["source_family"] in SC_SOURCE_FAMILIES
        assert r["source_family"] != "unknown"


# ── carry-forward: latent writeback defaults ────────────────────────────────

LATENT_TARGETS = {
    "scaled_federal_corpus_persist_service": ["la_scaled_federal_grants.json"],
    "tier2_state_corpus_persist_service": [
        "ta_tier2_state_grants.json",
        "ta_mixed_tier13_grants.json",
    ],
    "tier3_foundation_corpus_persist_service": [
        "ta_tier3_foundation_grants.json",
        "ta_mixed_tier13_grants.json",
    ],
}


@pytest.mark.parametrize("service", sorted(LATENT_TARGETS))
def test_latent_persist_services_route_through_the_writeback_guard(
    service: str,
) -> None:
    """All three, not the two Gate 77B reported."""
    src = (ROOT / "src" / "nativeforge" / "services" / f"{service}.py").read_text(
        encoding="utf-8"
    )
    assert "guarded_write_text" in src, f"{service} still writes unguarded"
    # And no raw write to a committed target remains.
    assert "target.write_text(" not in src
    assert "mixed_target.write_text(" not in src


@pytest.mark.parametrize(
    "fixture_name",
    sorted({n for names in LATENT_TARGETS.values() for n in names}),
)
def test_every_latent_target_is_recognised_as_committed_evidence(
    fixture_name: str,
) -> None:
    path = ROOT / "fixtures" / "real_grants_corpus" / fixture_name
    assert is_source_controlled(path) is True
    decision = resolve_writeback_path(path)
    assert decision["redirected"] is True
    assert "artifacts" in decision["path"]


def test_the_mixed_corpus_is_written_by_two_services() -> None:
    """It also carries the SAMHSA record, so it had two unguarded write paths."""
    writers = [
        s
        for s, names in LATENT_TARGETS.items()
        if "ta_mixed_tier13_grants.json" in names
    ]
    assert len(writers) == 2


def test_committed_corpus_fixtures_are_all_source_controlled() -> None:
    corpus = ROOT / "fixtures" / "real_grants_corpus"
    files = sorted(corpus.glob("*.json"))
    assert files
    for path in files:
        assert is_source_controlled(path) is True


# ── fixture cleanliness guard ───────────────────────────────────────────────


def test_the_cleanliness_script_exists_and_is_executable() -> None:
    script = ROOT / "scripts" / "verify_nativeforge_fixture_cleanliness.sh"
    assert script.is_file()
    assert script.stat().st_mode & 0o111, "script must be executable"


def test_the_cleanliness_script_watches_the_guarded_directories() -> None:
    """The script and the guard must not disagree about what is protected."""
    from nativeforge.services.hermetic_test_guard_service import (
        SOURCE_CONTROLLED_DIRS,
    )

    body = (ROOT / "scripts" / "verify_nativeforge_fixture_cleanliness.sh").read_text(
        encoding="utf-8"
    )
    for directory in SOURCE_CONTROLLED_DIRS:
        rel = str(directory).replace(str(ROOT) + "/", "")
        assert rel in body, f"{rel} not watched by the cleanliness script"


def test_the_cleanliness_script_checks_the_samhsa_record_by_content() -> None:
    body = (ROOT / "scripts" / "verify_nativeforge_fixture_cleanliness.sh").read_text(
        encoding="utf-8"
    )
    assert "SAMHSA / HHS" in body
    assert "SM-26-024" in body
    assert "HHS-IHS" in body
    assert "Connection refused" in body


def test_the_samhsa_record_is_still_intact() -> None:
    fixture = (
        ROOT
        / "fixtures"
        / "real_grants_corpus"
        / "nf15_eligibility_reingest_pulls.json"
    )
    body = fixture.read_text(encoding="utf-8")
    assert "SAMHSA / HHS" in body
    assert "SM-26-024" in body
    assert "HHS-IHS" not in body
    assert "Connection refused" not in body
    row = next(
        r
        for r in json.loads(body)["results"]
        if r.get("grant_id") == "nf13-real-fed-021"
    )
    assert row["chosen_opportunity_id"] == "361976"


# ── claims ──────────────────────────────────────────────────────────────────


def test_no_live_sc_coverage_or_improvement_is_claimed() -> None:
    doc = (
        ROOT / "docs" / "operations" / "438_GATE78_PRODUCTION_READINESS_DELTA.md"
    ).read_text(encoding="utf-8")
    assert "Live SC source coverage:   NONE" in doc
    assert "SC coverage complete:      NOT CLAIMED" in doc
    assert "65% improvement:           NOT CLAIMED" in doc
    assert "Controlled customer pilot: NO_GO" in doc
