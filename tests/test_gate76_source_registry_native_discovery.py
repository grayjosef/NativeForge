"""Tests: Gate 76 source registry and Native opportunity discovery.

Almost every assertion here is a refusal, because the failure modes in funding
intelligence are all forms of overclaim: a keyword read as eligibility, a stale
grant shown as current, a duplicate counted as coverage, a source monitored
before anyone read its terms.

The one that would hurt a real customer most is showing an expired grant as
current — a tribal grant office that misses a deadline because of this product
has been actively harmed, not merely underserved. That is why the expiry and
supersession rules get the most coverage.
"""

from __future__ import annotations

import pathlib

import pytest

from nativeforge.services.native_opportunity_discovery_service import (
    APPLICANT_ROUTING,
    RECOGNITION_ROUTING,
    SECTOR_ROUTING,
    build_native_opportunity_record,
    derive_recognition_routing,
    opportunity_record_invariant_failures,
)
from nativeforge.services.opportunity_discovery_quality_service import (
    RECOGNITION_TIERS,
)
from nativeforge.services.opportunity_freshness_service import (
    CURRENT_STATES,
    FRESHNESS_STATES,
    NON_CURRENT_STATES,
    evaluate_opportunity_freshness,
    evaluate_supersession,
    freshness_invariant_failures,
    supersession_invariant_failures,
)
from nativeforge.services.source_registry_service import (
    MONITORING_STATUSES,
    NON_MONITORING_STATUSES,
    PROMOTION_STATUSES,
    ROBOTS_TERMS_CLEARED,
    build_source_record,
    quality_source_type,
    score_source_quality,
    source_record_invariant_failures,
)
from nativeforge.services.source_seed_catalog import (
    LANES,
    build_seed_catalog,
    seed_catalog_invariant_failures,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
NOW = "2026-08-24"

# A source cleared for monitoring, so individual fields can be broken.
GOOD_SOURCE = {
    "source_id": "src-1",
    "source_name": "Grants.gov",
    "source_url": "https://www.grants.gov/",
    "source_type": "grants_gov",
    "jurisdiction": "federal",
    "access_method": "public_api",
    "refresh_cadence": "daily",
    "robots_terms_status": "reviewed_allowed",
    "promotion_status": "monitoring",
    "last_checked_at": "2026-08-23",
    "staleness_status": "fresh",
    "provenance_url": "https://www.grants.gov/",
    "native_relevance_rationale": "explicit tribal applicant codes",
}


# ── source registry: monitoring gate ────────────────────────────────────────


def test_cleared_source_can_monitor() -> None:
    """The gate must be passable, or it is theatre rather than a gate."""
    r = build_source_record(**GOOD_SOURCE)
    assert r["blocked_reasons"] == [], r["blocked_reasons"]
    assert r["can_monitor"] is True
    assert not source_record_invariant_failures(r)


def test_unknown_source_type_cannot_monitor() -> None:
    r = build_source_record(**{**GOOD_SOURCE, "source_type": "unknown"})
    assert r["can_monitor"] is False
    assert "source_type_unknown" in r["blocked_reasons"]


def test_unrecognised_source_type_normalises_to_unknown_and_denies() -> None:
    r = build_source_record(**{**GOOD_SOURCE, "source_type": "some_new_portal"})
    assert r["source_type"] == "unknown"
    assert r["can_monitor"] is False


def test_blocked_terms_source_cannot_monitor() -> None:
    r = build_source_record(**{**GOOD_SOURCE, "promotion_status": "blocked_terms"})
    assert r["can_monitor"] is False
    assert "promotion_status_blocked_terms" in r["blocked_reasons"]


@pytest.mark.parametrize(
    "status",
    ["unreviewed", "unknown", "reviewed_disallowed", "reviewed_requires_agreement"],
)
def test_unresolved_or_negative_terms_cannot_monitor(status: str) -> None:
    """A source monitored before anyone read its terms is a scraping incident."""
    r = build_source_record(**{**GOOD_SOURCE, "robots_terms_status": status})
    assert r["can_monitor"] is False
    assert any(b.startswith("robots_terms_not_cleared") for b in r["blocked_reasons"])


@pytest.mark.parametrize("status", sorted(ROBOTS_TERMS_CLEARED))
def test_cleared_terms_permit_monitoring(status: str) -> None:
    r = build_source_record(**{**GOOD_SOURCE, "robots_terms_status": status})
    assert r["can_monitor"] is True


@pytest.mark.parametrize("status", sorted(NON_MONITORING_STATUSES))
def test_non_monitoring_statuses_cannot_monitor(status: str) -> None:
    r = build_source_record(**{**GOOD_SOURCE, "promotion_status": status})
    assert r["can_monitor"] is False


def test_monitoring_status_set_is_derived_not_listed() -> None:
    """A status added later must deny until someone deliberately permits it."""
    assert MONITORING_STATUSES | NON_MONITORING_STATUSES == PROMOTION_STATUSES
    assert not (MONITORING_STATUSES & NON_MONITORING_STATUSES)


def test_source_without_url_cannot_monitor() -> None:
    r = build_source_record(**{**GOOD_SOURCE, "source_url": None})
    assert r["can_monitor"] is False
    assert "no_source_url" in r["blocked_reasons"]


def test_retirement_overrides_the_promotion_column() -> None:
    r = build_source_record(**{**GOOD_SOURCE, "retirement_status": "retired"})
    assert r["promotion_status"] == "retired"
    assert r["can_monitor"] is False


def test_marked_monitoring_but_ineligible_is_named_not_hidden() -> None:
    r = build_source_record(**{**GOOD_SOURCE, "robots_terms_status": "unreviewed"})
    assert r["can_monitor"] is False
    assert "marked_monitoring_but_not_eligible" in r["blocked_reasons"]


# ── source registry: provenance, duplicates, staleness ──────────────────────


def test_source_without_provenance_gets_no_quality_credit() -> None:
    r = build_source_record(**{**GOOD_SOURCE, "provenance_url": None})
    assert r["has_provenance"] is False
    assert r["quality_credit_eligible"] is False
    assert score_source_quality(r)["quality_score"] == 0.0
    assert score_source_quality(r)["counts_toward_coverage"] is False


def test_duplicate_source_earns_no_quality_credit() -> None:
    """Raw source count must not be inflatable by re-listing the same portal."""
    r = build_source_record(
        **{**GOOD_SOURCE, "is_duplicate": True, "duplicate_group_id": "grp-1"}
    )
    assert r["quality_credit_eligible"] is False
    scored = score_source_quality(r)
    assert scored["quality_score"] == 0.0
    assert "duplicate_scores_zero" in scored["notes"]


def test_duplicate_does_not_raise_a_registry_score() -> None:
    unique = score_source_quality(build_source_record(**GOOD_SOURCE))
    dupe = score_source_quality(
        build_source_record(**{**GOOD_SOURCE, "is_duplicate": True})
    )
    assert unique["quality_score"] > dupe["quality_score"]
    assert dupe["quality_score"] == 0.0


@pytest.mark.parametrize("status", ["stale", "retired"])
def test_stale_and_retired_sources_remain_visible(status: str) -> None:
    """A stale source that disappears looks like one we never had."""
    r = build_source_record(**{**GOOD_SOURCE, "promotion_status": status})
    assert r["visible"] is True
    assert r["can_monitor"] is False
    scored = score_source_quality(r)
    assert scored["counts_toward_coverage"] is False
    assert scored["quality_score"] == 0.0


def test_no_check_timestamp_means_unknown_staleness_not_fresh() -> None:
    """Absence of evidence is not freshness."""
    r = build_source_record(
        **{**GOOD_SOURCE, "last_checked_at": None, "staleness_status": "fresh"}
    )
    assert r["staleness_status"] == "unknown"
    assert not source_record_invariant_failures(r)


def test_invariants_catch_a_forged_monitoring_claim() -> None:
    r = build_source_record(**{**GOOD_SOURCE, "robots_terms_status": "unreviewed"})
    r["can_monitor"] = True
    r["blocked_reasons"] = []
    fails = source_record_invariant_failures(r)
    assert "monitoring_without_cleared_terms" in fails


def test_invariants_catch_freshness_without_a_check() -> None:
    r = build_source_record(**GOOD_SOURCE)
    r["last_checked_at"] = None
    assert "staleness_claimed_without_a_check_timestamp" in (
        source_record_invariant_failures(r)
    )


def test_source_types_map_onto_the_existing_quality_vocabulary() -> None:
    """Two vocabularies for one concept would drift. The bridge is explicit."""
    from nativeforge.services.opportunity_discovery_quality_service import SOURCE_TYPES
    from nativeforge.services.source_registry_service import SOURCE_TYPES as REG_TYPES

    for t in REG_TYPES:
        assert quality_source_type(t) in SOURCE_TYPES
    assert quality_source_type("not_a_type") == "unknown"


# ── opportunity freshness ───────────────────────────────────────────────────


def test_open_recently_checked_opportunity_is_fresh() -> None:
    f = evaluate_opportunity_freshness(
        opportunity_id="o1",
        close_date="2026-12-01",
        last_checked_at="2026-08-23",
        now=NOW,
    )
    assert f["freshness_state"] == "fresh"
    assert f["counts_as_current"] is True
    assert not freshness_invariant_failures(f)


def test_past_close_date_is_expired_not_fresh() -> None:
    """The failure that would cost a customer a deadline."""
    f = evaluate_opportunity_freshness(
        opportunity_id="o2",
        close_date="2026-01-15",
        last_checked_at="2026-08-23",
        now=NOW,
    )
    assert f["freshness_state"] == "expired"
    assert f["counts_as_current"] is False
    assert f["counts_toward_quality"] is False
    assert f["visible"] is True
    assert not freshness_invariant_failures(f)


def test_expired_with_extension_evidence_becomes_amended() -> None:
    f = evaluate_opportunity_freshness(
        opportunity_id="o3",
        close_date="2026-01-15",
        last_checked_at="2026-08-23",
        now=NOW,
        extension_evidence=[
            {
                "kind": "federal_register_notice_url",
                "reference": "https://www.federalregister.gov/documents/example",
            }
        ],
    )
    assert f["freshness_state"] == "amended"
    assert f["counts_as_current"] is True


def test_extension_claimed_without_a_reference_does_not_move_the_state() -> None:
    """A kind with nothing behind it is an assertion wearing the word evidence."""
    f = evaluate_opportunity_freshness(
        opportunity_id="o4",
        close_date="2026-01-15",
        last_checked_at="2026-08-23",
        now=NOW,
        extension_evidence=[{"kind": "federal_register_notice_url", "reference": ""}],
    )
    assert f["freshness_state"] == "expired"


def test_unrecognised_extension_evidence_kind_is_ignored() -> None:
    f = evaluate_opportunity_freshness(
        opportunity_id="o5",
        close_date="2026-01-15",
        last_checked_at="2026-08-23",
        now=NOW,
        extension_evidence=[{"kind": "someone_told_me", "reference": "trust me"}],
    )
    assert f["freshness_state"] == "expired"


def test_missing_close_date_is_unknown_not_fresh() -> None:
    f = evaluate_opportunity_freshness(
        opportunity_id="o6", close_date=None, last_checked_at="2026-08-23", now=NOW
    )
    assert f["freshness_state"] == "unknown"
    assert f["counts_as_current"] is False
    assert f["human_review_required"] is True


def test_missing_check_timestamp_is_unknown() -> None:
    """We cannot vouch for what we have not looked at."""
    f = evaluate_opportunity_freshness(
        opportunity_id="o7", close_date="2026-12-01", last_checked_at=None, now=NOW
    )
    assert f["freshness_state"] == "unknown"
    assert "never_checked" in f["reasons"]


def test_long_unchecked_open_opportunity_is_stale() -> None:
    f = evaluate_opportunity_freshness(
        opportunity_id="o8",
        close_date="2026-12-01",
        last_checked_at="2026-06-01",
        now=NOW,
    )
    assert f["freshness_state"] == "stale"
    assert f["counts_as_current"] is False
    assert f["visible"] is True


def test_amendment_newer_than_posted_marks_amended() -> None:
    f = evaluate_opportunity_freshness(
        opportunity_id="o9",
        close_date="2026-12-01",
        posted_date="2026-05-01",
        amendment_date="2026-08-01",
        last_checked_at="2026-08-23",
        now=NOW,
    )
    assert f["freshness_state"] == "amended"


def test_current_state_set_is_derived_not_listed() -> None:
    assert CURRENT_STATES | NON_CURRENT_STATES == FRESHNESS_STATES
    assert not (CURRENT_STATES & NON_CURRENT_STATES)


@pytest.mark.parametrize("state", sorted(NON_CURRENT_STATES))
def test_no_non_current_state_counts_toward_quality(state: str) -> None:
    forged = {
        "schema_version": "nf_opportunity_freshness_v1",
        "freshness_state": state,
        "counts_as_current": True,
        "counts_toward_quality": True,
        "visible": True,
    }
    fails = freshness_invariant_failures(forged)
    assert any("non_current_state_counted" in f for f in fails)


# ── supersession ────────────────────────────────────────────────────────────

OLDER = {
    "opportunity_id": "old-1",
    "source_id": "src-1",
    "title": "Tribal Housing Improvement Program",
    "agency_or_funder": "Example Agency",
    "posted_date": "2025-05-01",
}
NEWER = {
    "opportunity_id": "new-1",
    "source_id": "src-1",
    "title": "Tribal Housing Improvement Program",
    "agency_or_funder": "Example Agency",
    "amendment_date": "2026-05-01",
}


def test_supersession_requires_evidence() -> None:
    """Same title and funder is a coincidence generator, not a proof."""
    s = evaluate_supersession(older=OLDER, newer=NEWER)
    assert s["supersedes"] is False
    assert "no_supersession_evidence" in s["blocked_reasons"]
    assert s["older_remains_visible"] is True


def test_supersession_with_evidence_is_allowed() -> None:
    s = evaluate_supersession(
        older=OLDER,
        newer=NEWER,
        evidence=[{"kind": "same_opportunity_number", "reference": "EX-2026-001"}],
    )
    assert s["supersedes"] is True
    assert s["blocked_reasons"] == []
    assert not supersession_invariant_failures(s)


def test_different_lineage_cannot_supersede_even_with_evidence() -> None:
    s = evaluate_supersession(
        older=OLDER,
        newer={**NEWER, "agency_or_funder": "A Different Agency"},
        evidence=[{"kind": "operator_verified_supersession", "reference": "ticket-9"}],
    )
    assert s["supersedes"] is False
    assert "not_the_same_opportunity_lineage" in s["blocked_reasons"]


def test_a_newer_version_that_is_not_newer_cannot_supersede() -> None:
    s = evaluate_supersession(
        older={**OLDER, "amendment_date": "2026-06-01"},
        newer={**NEWER, "amendment_date": "2026-05-01"},
        evidence=[{"kind": "same_opportunity_number", "reference": "EX-2026-001"}],
    )
    assert s["supersedes"] is False
    assert "newer_version_is_not_actually_newer" in s["blocked_reasons"]


def test_superseded_state_requires_evidence_in_the_freshness_path() -> None:
    without = evaluate_opportunity_freshness(
        opportunity_id="o10",
        close_date="2026-12-01",
        last_checked_at="2026-08-23",
        now=NOW,
        superseded_by="new-1",
    )
    assert without["freshness_state"] != "superseded"
    assert "supersession_claimed_without_evidence" in without["reasons"]
    assert without["human_review_required"] is True

    with_ev = evaluate_opportunity_freshness(
        opportunity_id="o11",
        close_date="2026-12-01",
        last_checked_at="2026-08-23",
        now=NOW,
        superseded_by="new-1",
        supersession_evidence=[
            {"kind": "same_opportunity_number", "reference": "EX-2026-001"}
        ],
    )
    assert with_ev["freshness_state"] == "superseded"
    assert with_ev["counts_as_current"] is False
    assert with_ev["visible"] is True


# ── Native relevance and eligibility ────────────────────────────────────────

FRESH = {
    "schema_version": "nf_opportunity_freshness_v1",
    "freshness_state": "fresh",
}

STRONG_CLASSIFICATION = {
    "label": "native_specific",
    "structured_signal": True,
    "keyword_hit": True,
}

RELEVANCE_EVIDENCE = [
    {
        "kind": "explicit_tribal_eligibility_text",
        "reference": "https://example.gov/nofo#eligibility",
    }
]


def _opportunity(**over: object) -> dict:
    kwargs: dict = {
        "opportunity_id": "opp-1",
        "source_id": "src-1",
        "title": "Tribal Housing Improvement Program",
        "agency_or_funder": "Example Agency",
        "lane": "federal",
        "federal_agency": "Example Agency",
        "funding_geography": "federal",
        "close_date": "2026-12-01",
        "eligibility_text": "Federally recognized tribes are eligible applicants.",
        "eligibility_evidence": [
            {
                "kind": "explicit_eligible_applicant_list",
                "reference": "https://example.gov/nofo#applicants",
            }
        ],
        "native_relevance_classification": STRONG_CLASSIFICATION,
        "native_relevance_evidence": RELEVANCE_EVIDENCE,
        "recognition_routing_tags": ["federally_recognized", "native_housing"],
        "authority_to_apply_requirements": ["tribal_council_resolution"],
        "freshness": FRESH,
        "provenance_url": "https://example.gov/nofo",
    }
    kwargs.update(over)
    return build_native_opportunity_record(**kwargs)


def test_evidenced_native_relevance_gets_credit() -> None:
    r = _opportunity()
    assert r["blocked_reasons"] == [], r["blocked_reasons"]
    assert r["native_relevance_credited"] is True
    assert r["counts_toward_quality"] is True
    assert not opportunity_record_invariant_failures(r)


def test_keyword_only_match_gets_no_relevance_credit() -> None:
    """The rule the gate cares about most."""
    r = _opportunity(
        native_relevance_classification={
            "label": "native_specific",
            "structured_signal": False,
            "keyword_hit": True,
        }
    )
    assert r["native_relevance_credited"] is False
    assert "native_relevance_from_keyword_match_only" in r["blocked_reasons"]
    assert r["counts_toward_quality"] is False


def test_relevance_without_evidence_gets_no_credit() -> None:
    r = _opportunity(native_relevance_evidence=[])
    assert r["native_relevance_credited"] is False
    assert "native_relevance_without_evidence" in r["blocked_reasons"]


def test_evidence_kind_without_a_reference_is_not_evidence() -> None:
    r = _opportunity(
        native_relevance_evidence=[
            {"kind": "explicit_tribal_eligibility_text", "reference": "  "}
        ]
    )
    assert r["native_relevance_credited"] is False


@pytest.mark.parametrize(
    "label",
    [
        "broadly_eligible_potentially_relevant",
        "weak_native_relevance",
        "uncertain_relevance",
        "irrelevant",
    ],
)
def test_weak_labels_get_no_relevance_credit(label: str) -> None:
    r = _opportunity(
        native_relevance_classification={
            "label": label,
            "structured_signal": True,
            "keyword_hit": False,
        }
    )
    assert r["native_relevance_credited"] is False
    assert any(
        b.startswith("native_relevance_label_too_weak") for b in r["blocked_reasons"]
    )


def test_eligibility_is_not_inferred_from_relevance() -> None:
    """Relevance is about the program; eligibility is about the applicant."""
    r = _opportunity(eligibility_evidence=[])
    assert r["native_relevance_credited"] is True
    assert r["eligibility_state"] != "eligible"
    assert r["human_review_required"] is True


def test_unknown_eligibility_stays_unknown() -> None:
    r = _opportunity(
        eligibility_evidence=[],
        eligibility_text=None,
        recognition_routing_tags=[],
    )
    assert r["eligibility_state"] == "unknown"


def test_eligibility_text_without_citation_is_possibly_eligible_at_most() -> None:
    r = _opportunity(eligibility_evidence=[])
    assert r["eligibility_state"] == "possibly_eligible"
    assert "eligibility_inferred_from_text_needs_review" in r["review_reasons"]


def test_invariants_reject_eligible_without_eligibility_evidence() -> None:
    r = _opportunity(eligibility_evidence=[])
    r["eligibility_state"] = "eligible"
    assert "eligible_without_eligibility_evidence" in (
        opportunity_record_invariant_failures(r)
    )


# ── recognition routing: two orthogonal axes ────────────────────────────────


def test_routing_carries_both_applicant_and_sector_axes() -> None:
    """A federally recognized tribe can pursue a housing grant."""
    d = derive_recognition_routing(["federally_recognized", "native_housing"])
    assert d["applicant_routing"] == ["federally_recognized"]
    assert d["native_sectors"] == ["native_housing"]
    assert d["recognition_tier"] == "federally_recognized"
    assert d["routing_known"] is True


def test_the_two_axes_partition_the_routing_vocabulary() -> None:
    assert APPLICANT_ROUTING | SECTOR_ROUTING | {"unknown"} == RECOGNITION_ROUTING
    assert not (APPLICANT_ROUTING & SECTOR_ROUTING)


def test_tier_projection_uses_the_existing_vocabulary() -> None:
    for tag in sorted(APPLICANT_ROUTING):
        d = derive_recognition_routing([tag])
        assert d["recognition_tier"] in RECOGNITION_TIERS


def test_state_recognized_is_not_federally_recognized() -> None:
    """Different status, different eligibility consequences."""
    d = derive_recognition_routing(["state_recognized"])
    assert d["recognition_tier"] == "state_recognized"
    assert "federally_recognized" not in d["applicant_routing"]


def test_unknown_routing_stays_unknown() -> None:
    d = derive_recognition_routing([])
    assert d["recognition_routing"] == ["unknown"]
    assert d["recognition_tier"] == "unknown"
    assert d["routing_known"] is False


def test_unrecognised_routing_tags_are_surfaced_for_review() -> None:
    r = _opportunity(
        recognition_routing_tags=["federally_recognized", "native_fishing"]
    )
    assert "native_fishing" in r["unrecognised_tags"]
    assert any(x.startswith("unrecognised_routing_tags") for x in r["review_reasons"])


def test_sector_only_routing_leaves_tier_unknown() -> None:
    """Knowing the money is for housing says nothing about who may apply."""
    d = derive_recognition_routing(["native_housing"])
    assert d["recognition_tier"] == "unknown"
    assert d["routing_known"] is True


# ── state / federal lane discipline ─────────────────────────────────────────


def test_state_lane_requires_a_state() -> None:
    r = _opportunity(lane="state", state=None, federal_agency=None)
    assert "state_lane_without_a_state" in r["blocked_reasons"]


def test_state_lane_cannot_carry_a_federal_agency() -> None:
    """Lanes must not be collapsed; it would corrupt both coverage counts."""
    r = _opportunity(lane="state", state="SC", federal_agency="Example Agency")
    assert "state_lane_with_a_federal_agency" in r["blocked_reasons"]
    r["blocked_reasons"] = []
    assert "state_lane_carries_a_federal_agency" in (
        opportunity_record_invariant_failures(r)
    )


def test_sc_specific_does_not_exclude_federal_opportunities() -> None:
    """An SC organization's federal opportunity stays in the federal lane."""
    r = _opportunity(
        lane="federal",
        state="SC",
        federal_agency="Example Agency",
        funding_geography="federal",
    )
    assert r["lane"] == "federal"
    assert r["state"] == "SC"
    assert r["funding_geography"] == "federal"
    assert r["counts_toward_quality"] is True


def test_state_and_federal_lanes_produce_distinct_records() -> None:
    fed = _opportunity(lane="federal", funding_geography="federal")
    st = _opportunity(
        lane="state",
        state="SC",
        federal_agency=None,
        funding_geography="south_carolina",
    )
    assert fed["lane"] != st["lane"]
    assert fed["funding_geography"] != st["funding_geography"]


# ── duplicates, freshness, provenance at opportunity level ──────────────────


def test_duplicate_opportunity_does_not_count_toward_quality() -> None:
    r = _opportunity(duplicate_status="duplicate_of", duplicate_group_id="grp-1")
    assert r["is_duplicate"] is True
    assert r["counts_toward_quality"] is False


def test_expired_opportunity_does_not_count_as_current() -> None:
    r = _opportunity(freshness={"schema_version": "x", "freshness_state": "expired"})
    assert r["counts_as_current"] is False
    assert r["counts_toward_quality"] is False
    assert r["visible"] is True


def test_opportunity_without_provenance_is_blocked() -> None:
    r = _opportunity(provenance_url=None)
    assert "no_provenance_url" in r["blocked_reasons"]
    assert r["counts_toward_quality"] is False


def test_authority_requirements_default_to_unknown_and_flag_review() -> None:
    r = _opportunity(authority_to_apply_requirements=[])
    assert r["authority_to_apply_requirements"] == ["unknown"]
    assert "authority_requirements_not_determined" in r["review_reasons"]


# ── seed catalog: categories, not coverage ──────────────────────────────────


def test_seed_catalog_builds_all_three_lanes() -> None:
    c = build_seed_catalog()
    assert set(c["lanes"]) == set(LANES)
    assert c["record_count"] >= 12
    assert not seed_catalog_invariant_failures(c)


def test_no_seed_is_monitorable() -> None:
    """The central guarantee of the seed catalog."""
    c = build_seed_catalog()
    assert c["monitorable_count"] == 0
    for r in c["records"]:
        assert r["can_monitor"] is False


def test_no_seed_claims_a_check_timestamp_or_freshness() -> None:
    """A seed with a check timestamp would claim we looked at something we did not."""
    for r in build_seed_catalog()["records"]:
        assert r["last_checked_at"] is None
        assert r["staleness_status"] == "unknown"


def test_every_seed_is_discovered_and_unreviewed() -> None:
    for r in build_seed_catalog()["records"]:
        assert r["promotion_status"] == "discovered"
        assert r["robots_terms_status"] == "unreviewed"


def test_seed_catalog_claims_no_live_or_complete_coverage() -> None:
    c = build_seed_catalog()
    assert c["live_coverage_claimed"] is False
    assert c["coverage_complete_claimed"] is False
    assert c["any_source_monitored"] is False


def test_most_seeds_have_no_url_because_inventing_one_would_fabricate_a_source() -> (
    None
):
    c = build_seed_catalog()
    assert c["with_url_count"] < c["record_count"]
    assert (
        c["with_url_count"] >= 1
    )  # grants.gov and the Federal Register are public record


@pytest.mark.parametrize("lane", sorted(LANES))
def test_each_lane_can_be_built_alone(lane: str) -> None:
    c = build_seed_catalog(lane)
    assert c["lanes"] == [lane]
    assert c["record_count"] >= 1
    assert not seed_catalog_invariant_failures(c)


def test_federal_lane_names_grants_gov_and_the_federal_register() -> None:
    keys = {r["source_id"] for r in build_seed_catalog("federal")["records"]}
    assert "federal.grants_gov" in keys
    assert "federal.federal_register" in keys


def test_sc_lane_is_present_and_state_scoped() -> None:
    records = build_seed_catalog("south_carolina")["records"]
    assert records
    assert all(r["state"] == "SC" for r in records)


# ── claims that must stay false ─────────────────────────────────────────────


def test_no_service_claims_live_coverage() -> None:
    assert build_source_record(**GOOD_SOURCE)["live_coverage_claimed"] is False
    assert build_source_record(**GOOD_SOURCE)["monitoring_active"] is False
    assert _opportunity()["live_coverage_claimed"] is False
    assert build_seed_catalog()["live_coverage_claimed"] is False


def test_no_service_claims_the_improvement_target() -> None:
    """The 65% target belongs to Gate 86 and needs a measured baseline first."""
    assert _opportunity()["improvement_target_claimed"] is False


def test_readiness_doc_does_not_claim_coverage_or_improvement() -> None:
    doc = (
        ROOT / "docs" / "operations" / "422_GATE76_PRODUCTION_READINESS_DELTA.md"
    ).read_text(encoding="utf-8")
    assert "Live source coverage:      NONE" in doc
    assert "65% improvement:           NOT CLAIMED" in doc
    assert "Controlled customer pilot: NO_GO" in doc
