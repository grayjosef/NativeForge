"""Gate 92 - v2 source registry + Phase 1 collector spine contracts.

These tests pin the things that would be cheapest to lose later: that nothing
here collects, that the v2 registry's UNKNOWNs and negative rows survive intact,
that the recall set stays five codes wide, and that a geography gate denies by
default.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

from nativeforge.services.external_source_registry_import_service import (
    import_external_source_registry,
    import_invariant_failures,
    resolve_tristate,
    summarise_import,
)
from nativeforge.services.external_source_registry_seed_service import (
    build_registry_seed_set,
    seed_invariant_failures,
)
from nativeforge.services.external_source_registry_v2_reconciliation_service import (
    reconcile_registries,
    reconciliation_invariant_failures,
)
from nativeforge.services.native_eligibility_code_classification_service import (
    DIRECT_TRIBAL_CODES,
    ELIGIBILITY_CLASSES,
    NATIVE_RECALL_CODES,
    REQUIRES_READING_CODES,
    SAM_TO_GRANTS_GOV_CROSSWALK,
    classification_invariant_failures,
    classify_native_eligibility,
    summarise_classification,
)
from nativeforge.services.opportunity_deadline_and_amendment_model_service import (
    AMENDMENT_CATEGORIES,
    DEADLINE_PATTERNS,
    MATERIAL_CATEGORIES,
    amendment_invariant_failures,
    build_deadline_model,
    categorize_modified_field,
    classify_amendment,
    deadline_model_invariant_failures,
)
from nativeforge.services.opportunity_identity_versioning_service import (
    DOC_TYPES,
    build_fuzzy_fallback_key,
    build_opportunity_identity,
    build_version_key,
    identity_invariant_failures,
    normalize_opportunity_number,
)
from nativeforge.services.sc_native_recognition_and_geography_service import (
    CATAWBA_NATION_NAME,
    FEDERALLY_RECOGNIZED_RESIDENT_IN_SC_COUNT,
    GEOGRAPHY_TEST_CASES,
    RECLAMATION_WESTERN_STATE_COUNT,
    RECOGNITION_SETS,
    apply_geography_gate,
    build_recognition_record,
    evaluate_program_access,
    geography_invariant_failures,
    recognition_invariant_failures,
)
from nativeforge.services.source_crawler_governance_service import (
    BLACKLISTED_HOSTS,
    CIRCUIT_BREAKER_CONSECUTIVE_FAILURES,
    FORBIDDEN_USER_AGENT_TOKENS,
    MIN_REQUEST_INTERVAL_SECONDS,
    NATIVEFORGE_USER_AGENT,
    PER_HOST_CONCURRENCY,
    build_circuit_breaker_state,
    classify_page_liveness,
    evaluate_fetch_permission,
    governance_invariant_failures,
    user_agent_violations,
)
from nativeforge.services.source_spine_build_plan_service import (
    GRANTS_GOV_ATTRIBUTION,
    GRANTS_GOV_EXTRACT_RETENTION_DAYS,
    SAM_RATE_LIMIT_NO_ROLE_PER_DAY,
    SAM_RATE_LIMIT_WITH_ROLE_PER_DAY,
    build_phase1_spine_plan,
    spine_invariant_failures,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
V1_CSV = REPO_ROOT / "fixtures/external_source_registry/nativeforge-source-registry.csv"
V2_CSV = (
    REPO_ROOT / "fixtures/external_source_registry/nativeforge-source-registry-v2.csv"
)
RESEARCH_DIR = REPO_ROOT / "docs/research"

GATE92_SERVICES = (
    "source_spine_build_plan_service",
    "opportunity_identity_versioning_service",
    "native_eligibility_code_classification_service",
    "opportunity_deadline_and_amendment_model_service",
    "source_crawler_governance_service",
    "sc_native_recognition_and_geography_service",
    "external_source_registry_v2_reconciliation_service",
)


@pytest.fixture(scope="module")
def v2_imported() -> dict:
    return import_external_source_registry(
        csv_text=V2_CSV.read_text(encoding="utf-8-sig"), source_label="registry_v2"
    )


@pytest.fixture(scope="module")
def v1_imported() -> dict:
    return import_external_source_registry(csv_text=V1_CSV.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# 92A/B/C - the v2 registry itself
# --------------------------------------------------------------------------


def test_v2_registry_imports_with_no_invariant_failures(v2_imported: dict) -> None:
    assert v2_imported["imported_count"] == 381
    assert import_invariant_failures(v2_imported) == []


def test_v2_import_fetches_nothing(v2_imported: dict) -> None:
    assert v2_imported["urls_fetched"] == 0
    assert v2_imported["network_access_performed"] is False
    assert v2_imported["monitoring_started"] is False
    assert v2_imported["live_coverage_claimed"] is False


def test_v2_preserves_unknown_cells_verbatim(v2_imported: dict) -> None:
    summary = summarise_import(v2_imported)
    # An unknown capability is not an absent one. If this number ever drops,
    # something resolved an UNKNOWN it had no evidence to resolve.
    assert summary["unknown_cells_preserved"] == 570


def test_v2_preserves_negative_rows(v2_imported: dict) -> None:
    """Dead pages, traps, 404s, shells, blacklist and absence findings stay."""
    signals = ("blacklist", "dead", "trap", "absence", "404", "shell", "prohibited")
    found = {sig: 0 for sig in signals}
    for row in v2_imported["sources"]:
        note = (row.get("notes") or "").lower()
        for sig in signals:
            if sig in note:
                found[sig] += 1
    for sig, count in found.items():
        assert count > 0, f"negative row signal {sig!r} was pruned"


def test_v2_preserves_research_lane_tags(v2_imported: dict) -> None:
    tagged = [
        r for r in v2_imported["sources"] if "research lane:" in (r.get("notes") or "")
    ]
    assert len(tagged) == 381


def test_v1_registry_still_imports_unchanged(v1_imported: dict) -> None:
    """The importer was extended additively; v1's readings must not move."""
    summary = summarise_import(v1_imported)
    assert v1_imported["imported_count"] == 55
    assert summary["terms_review_required_count"] == 13
    assert summary["state_scoped_count"] == 10
    assert summary["api_capable_count"] == 5
    assert summary["unknown_cells_preserved"] == 23
    assert import_invariant_failures(v1_imported) == []


def test_v1_registry_fixture_is_not_deleted() -> None:
    assert V1_CSV.exists()


def test_tristate_denies_by_default() -> None:
    """An unrecognised value is `conditional`, never a bare `no`."""
    assert resolve_tristate("Yes") == "yes"
    assert resolve_tristate("no") == "no"
    assert resolve_tristate("no - not login-gated") == "no"
    assert resolve_tristate("UNKNOWN") == "unknown"
    assert resolve_tristate("") == "unknown"
    for qualified in (
        "yes - API key and paid contract",
        "yes to apply",
        "only for the applicant portal",
        "sort of",
    ):
        assert resolve_tristate(qualified) in {"yes", "conditional"}
        assert resolve_tristate(qualified) != "no"


def test_v2_seed_set_is_inert(v2_imported: dict) -> None:
    seed = build_registry_seed_set(imported=v2_imported)
    assert seed["seed_count"] == 381
    assert seed["monitored_count"] == 0
    assert seed["api_approved_count"] == 0
    assert seed["monitoring_started"] is False
    assert seed_invariant_failures(seed) == []


def test_human_review_only_sources_are_inert_by_flag(v2_imported: dict) -> None:
    """Enforced by a flag, not by convention."""
    seed = build_registry_seed_set(imported=v2_imported)
    for s in seed["seeds"]:
        if s["human_review_only"]:
            assert s["legal_terms_review_required"] is True
            assert "human_review_only" in s["activation_blocked_reasons"]
        if s["terms_status"] in {"TERMS_REVIEW_REQUIRED", "HUMAN_REVIEW_ONLY"}:
            assert s["monitoring_status"] == "not_started"
            assert s["api_approved"] is False


def test_reconciliation_supersedes_without_deleting(
    v1_imported: dict, v2_imported: dict
) -> None:
    rec = reconcile_registries(
        v1_rows=v1_imported["sources"], v2_rows=v2_imported["sources"]
    )
    assert rec["v1_row_count"] == 55
    assert rec["v2_row_count"] == 381
    assert rec["supersession_status"] == "v2_supersedes_v1"
    assert rec["v1_deleted"] is False
    assert rec["negative_rows_pruned"] == 0
    assert rec["unknown_backfilled"] == 0
    assert reconciliation_invariant_failures(rec) == []


# --------------------------------------------------------------------------
# 92D - Phase 1 spine
# --------------------------------------------------------------------------


def test_spine_plan_has_no_invariant_failures() -> None:
    assert spine_invariant_failures(build_phase1_spine_plan()) == []


def test_spine_builds_nothing_and_collects_nothing() -> None:
    plan = build_phase1_spine_plan()
    assert plan["collectors_built"] == 0
    assert plan["collectors_active"] == 0
    assert plan["urls_fetched"] == 0
    assert plan["monitoring_started"] is False
    assert plan["live_coverage_claimed"] is False
    for source in plan["sources"]:
        assert source["collector_status"] == "not_built"
        assert source["activation_blocked_reasons"]


def test_extract_is_corpus_of_record_and_search2_is_not() -> None:
    plan = build_phase1_spine_plan()
    by_id = {s["source_id"]: s for s in plan["sources"]}
    assert by_id["GRANTS-GOV-EXTRACT"]["source_role"] == "corpus_of_record"
    assert by_id["GRANTS-GOV-SEARCH2"]["source_role"] == "delta_accelerator"
    assert plan["corpus_of_record_id"] == "GRANTS-GOV-EXTRACT"
    assert (
        sum(1 for s in plan["sources"] if s["source_role"] == "corpus_of_record") == 1
    )


def test_grants_gov_attribution_is_verbatim() -> None:
    expected = (
        "This product uses the Grants.gov API but is not endorsed or certified "
        "by the U.S. Department of Health and Human Services."
    )
    assert GRANTS_GOV_ATTRIBUTION == expected
    plan = build_phase1_spine_plan()
    assert plan["grants_gov_attribution"] == expected
    for source in plan["sources"]:
        if source["source_id"].startswith("GRANTS-GOV"):
            assert source["attribution_text"] == expected
            assert source["must_store_attribution"] is True


def test_extract_retention_is_seven_days_and_a_miss_is_unrecoverable() -> None:
    assert GRANTS_GOV_EXTRACT_RETENTION_DAYS == 7
    plan = build_phase1_spine_plan()
    assert plan["grants_gov_extract_retention_days"] == 7
    assert plan["grants_gov_missed_day_is_unrecoverable"] is True


def test_sam_is_api_only_with_its_documented_rate_limits() -> None:
    assert SAM_RATE_LIMIT_NO_ROLE_PER_DAY == 10
    assert SAM_RATE_LIMIT_WITH_ROLE_PER_DAY == 1000
    plan = build_phase1_spine_plan()
    assert plan["sam_scraping_prohibited"] is True
    sam = next(s for s in plan["sources"] if s["source_id"].startswith("SAM-GOV"))
    assert sam["collection_method"] == "public_api_with_key"
    assert sam["auth_required"] is True
    assert any(
        "scraping_prohibited" in r for r in sam["activation_blocked_reasons"]
    )


def test_every_spine_source_must_retain_its_evidence() -> None:
    for source in build_phase1_spine_plan()["sources"]:
        assert source["must_store_raw_payload"] is True
        assert source["must_store_retrieved_at"] is True
        assert source["must_store_source_hash"] is True


# --------------------------------------------------------------------------
# 92E - identity and versioning
# --------------------------------------------------------------------------


def test_opportunity_number_normalization() -> None:
    assert normalize_opportunity_number("hhs-2026-ihs-01") == "HHS2026IHS01"
    assert normalize_opportunity_number("  HHS 2026 ") == "HHS2026"
    assert normalize_opportunity_number(None) == ""


def test_forecast_and_synopsis_do_not_collide() -> None:
    """They share an opportunity number; only doc_type separates them."""
    forecast = build_opportunity_identity(
        opportunity_number="HHS-2026-IHS-01", doc_type="forecast"
    )
    synopsis = build_opportunity_identity(
        opportunity_number="HHS-2026-IHS-01", doc_type="synopsis"
    )
    assert (
        forecast["normalized_opportunity_number"]
        == synopsis["normalized_opportunity_number"]
    )
    assert forecast["composite_key"] != synopsis["composite_key"]
    assert identity_invariant_failures(forecast) == []
    assert identity_invariant_failures(synopsis) == []


def test_a_key_without_doc_type_is_rejected() -> None:
    broken = build_opportunity_identity(
        opportunity_number="HHS-2026-IHS-01", doc_type="forecast"
    )
    broken["composite_key"] = broken["normalized_opportunity_number"]
    assert "l1_key_is_not_composite" in identity_invariant_failures(broken)


def test_title_is_never_a_key_field() -> None:
    identity = build_opportunity_identity(
        opportunity_number="HHS-2026-IHS-01", doc_type="synopsis"
    )
    identity["opportunity_title"] = "Tribal Tourism Cooperative Agreement"
    fails = identity_invariant_failures(identity)
    assert "forbidden_key_field_present:opportunity_title" in fails


def test_aln_is_many_to_many_and_malformed_values_are_reported_not_fixed() -> None:
    identity = build_opportunity_identity(
        opportunity_number="X-1",
        doc_type="synopsis",
        aln_list=["93.210", "15.022", "93210", "bad"],
    )
    assert identity["aln_list"] == ["93.210", "15.022"]
    assert sorted(identity["aln_malformed"]) == ["93210", "BAD"]
    assert identity["aln_relation_is_many_to_many"] is True
    assert identity_invariant_failures(identity) == []


def test_agency_is_never_matched_by_name() -> None:
    identity = build_opportunity_identity(
        opportunity_number="X-1", doc_type="synopsis", agency_code="BIA"
    )
    assert identity["agency_crosswalk_required"] is True
    assert identity["agency_matched_by_name"] is False


def test_versions_are_immutable_rows() -> None:
    v1 = build_version_key(opportunity_id=1, doc_type="synopsis", revision=1)
    v2 = build_version_key(opportunity_id=1, doc_type="synopsis", revision=2)
    assert v1["version_key"] != v2["version_key"]
    assert v1["is_immutable"] is True
    assert v1["updates_in_place"] is False
    assert identity_invariant_failures(v1) == []


def test_fuzzy_key_is_provisional_and_deterministic() -> None:
    kwargs = dict(
        agency="Bureau of Indian Affairs",
        title="Tribal Tourism Cooperative Agreement",
        earliest_deadline_date="2026-10-15",
    )
    a = build_fuzzy_fallback_key(**kwargs)
    b = build_fuzzy_fallback_key(**kwargs)
    assert a["fuzzy_key"] == b["fuzzy_key"]
    assert a["is_provisional"] is True
    assert a["must_promote_to_l1_when_number_found"] is True
    assert a["near_match_auto_merges"] is False
    assert identity_invariant_failures(a) == []
    expected = hashlib.sha256(
        "|".join(a["key_inputs"]).encode("utf-8")
    ).hexdigest()
    assert a["fuzzy_key"] == expected


def test_doc_types_are_exactly_forecast_and_synopsis() -> None:
    assert DOC_TYPES == frozenset({"forecast", "synopsis"})


# --------------------------------------------------------------------------
# 92F - graded eligibility
# --------------------------------------------------------------------------


def test_recall_set_is_five_codes() -> None:
    assert NATIVE_RECALL_CODES == frozenset({"07", "11", "08", "99", "25"})
    assert set(DIRECT_TRIBAL_CODES) == {"07", "11", "08"}
    assert set(REQUIRES_READING_CODES) == {"99", "25"}


def test_unrestricted_and_others_stay_in_the_recall_set() -> None:
    """A filter on 07|11 alone looks clean and misses money. Not here."""
    for code in ("99", "25"):
        result = classify_native_eligibility(eligible_applicant_codes=code)
        assert result["in_recall_set"] is True
        assert result["confidence"] == "requires_reading"
        assert result["free_text_screening_required"] is True
        assert classification_invariant_failures(result) == []


def test_requires_reading_is_neither_positive_nor_negative() -> None:
    result = classify_native_eligibility(eligible_applicant_codes="25")
    assert result["confidence"] not in {"direct", "negative"}
    promoted = dict(result, confidence="direct")
    assert "requires_reading_promoted_to_direct" in (
        classification_invariant_failures(promoted)
    )
    demoted = dict(result, confidence="negative")
    assert "requires_reading_collapsed_to_negative" in (
        classification_invariant_failures(demoted)
    )


def test_absent_codes_are_unknown_not_negative() -> None:
    result = classify_native_eligibility()
    assert result["confidence"] == "unknown"
    assert classification_invariant_failures(result) == []


def test_classification_never_reads_the_free_text() -> None:
    result = classify_native_eligibility(
        eligible_applicant_codes="25",
        additional_eligibility_text="Federally recognized tribes may apply.",
    )
    assert result["free_text_present"] is True
    assert result["free_text_screened"] is False
    assert result["free_text_read_by_this_service"] is False
    assert result["confidence"] == "requires_reading"


def test_classification_is_graded_not_boolean() -> None:
    result = classify_native_eligibility(eligible_applicant_codes="07")
    assert result["is_boolean_filter"] is False
    assert result["customer_eligibility_determined"] is False
    assert "customer_eligibility_determined" in result


def test_sam_crosswalk_is_labelled_inferred() -> None:
    assert SAM_TO_GRANTS_GOV_CROSSWALK == {
        "ET23010": "07",
        "ET23020": "11",
        "ET23030": "08",
    }
    result = classify_native_eligibility(sam_applicant_type_codes="ET23010")
    assert result["crosswalk_is_inferred"] is True
    assert result["sam_crosswalked_to_grants_gov"] == ["07"]
    claimed = dict(result, crosswalk_is_inferred=False)
    assert "sam_crosswalk_claimed_as_documented" in (
        classification_invariant_failures(claimed)
    )


def test_et12010_defers_to_the_nofo() -> None:
    result = classify_native_eligibility(sam_applicant_type_codes="ET12010")
    assert result["nofo_text_is_authoritative"] is True
    assert result["confidence"] == "requires_reading"


def test_eligibility_class_vocabulary_has_twelve_members() -> None:
    assert len(ELIGIBILITY_CLASSES) == 12
    assert "UNKNOWN" in ELIGIBILITY_CLASSES
    assert "state-recognized-tribe" in ELIGIBILITY_CLASSES


def test_classification_summary_counts_the_screening_backlog() -> None:
    results = [
        classify_native_eligibility(eligible_applicant_codes=c)
        for c in ("07", "25", "99", "12", "")
    ]
    summary = summarise_classification(results)
    assert summary["free_text_screening_backlog"] == 2
    assert summary["free_text_screened_count"] == 0
    assert summary["customers_matched"] == 0


# --------------------------------------------------------------------------
# 92G - deadlines and amendments
# --------------------------------------------------------------------------


def test_deadline_pattern_defaults_to_unknown() -> None:
    model = build_deadline_model()
    assert model["deadline_pattern"] == "unknown"
    assert model["pattern_verified"] is False
    assert model["dates_synthesized"] == 0
    assert model["dates_inferred_from_pattern"] == 0
    assert deadline_model_invariant_failures(model) == []


@pytest.mark.parametrize("pattern", sorted(DEADLINE_PATTERNS))
def test_every_deadline_pattern_is_representable(pattern: str) -> None:
    needed = 2 if pattern in {"dual", "per_region", "phased"} else 1
    deadlines = [{"n": i} for i in range(needed)]
    model = build_deadline_model(
        pattern=pattern,
        deadlines=deadlines,
        superseded_deadlines=[{"old": True}] if pattern == "revised" else None,
        amendment_number="Amendment No. 2" if pattern == "multi_year" else None,
    )
    assert deadline_model_invariant_failures(model) == []


def test_dual_deadlines_cannot_collapse_to_one() -> None:
    """DOJ publishes a Grants.gov deadline and a JustGrants deadline."""
    collapsed = build_deadline_model(
        pattern="dual", deadlines=[{"portal": "grants.gov"}]
    )
    assert "multi_valued_pattern_collapsed_to_scalar:dual" in (
        deadline_model_invariant_failures(collapsed)
    )


def test_per_region_deadlines_survive() -> None:
    """EPA GAP publishes ten regional deadlines in one national NOFA."""
    model = build_deadline_model(
        pattern="per_region",
        deadlines=[{"region": f"R{i}", "date": None} for i in range(1, 11)],
    )
    assert model["deadline_count"] == 10
    assert deadline_model_invariant_failures(model) == []


def test_a_revised_deadline_keeps_the_superseded_one() -> None:
    without = build_deadline_model(pattern="revised", deadlines=[{"d": "new"}])
    assert "revised_pattern_without_superseded_deadline" in (
        deadline_model_invariant_failures(without)
    )
    with_history = build_deadline_model(
        pattern="revised",
        deadlines=[{"d": "new"}],
        superseded_deadlines=[{"d": "old"}],
    )
    assert deadline_model_invariant_failures(with_history) == []
    assert with_history["deadlines_are_versioned"] is True


def test_multi_year_nofo_watches_the_amendment_number() -> None:
    """FHWA TTPSF spans 2022-2026; the amendments change, not the NOFO."""
    model = build_deadline_model(
        pattern="multi_year", deadlines=[{"d": "x"}], amendment_number="Amendment No. 2"
    )
    assert model["watch_amendment_number"] is True


def test_forecast_lapsed_is_an_explicit_state() -> None:
    model = build_deadline_model(
        pattern="single", deadlines=[{"d": "x"}], lifecycle_state="forecast_lapsed"
    )
    assert model["forecast_lapsed"] is True
    assert deadline_model_invariant_failures(model) == []
    silent = dict(model, lifecycle_state="open")
    assert "forecast_lapsed_flag_without_state" in (
        deadline_model_invariant_failures(silent)
    )


def test_amendment_categories_number_seven_and_four_notify() -> None:
    assert len(AMENDMENT_CATEGORIES) == 7
    assert len(MATERIAL_CATEGORIES) == 4
    assert MATERIAL_CATEGORIES < AMENDMENT_CATEGORIES


@pytest.mark.parametrize(
    "field,expected",
    [
        ("closeDate", "deadline_change"),
        ("estimatedSynopsisCloseDate", "deadline_change"),
        ("applicantTypes", "eligibility_change"),
        ("awardCeiling", "funding_amount_change"),
        ("synAttChangeComments", "attachment_change"),
        ("agencyContactEmail", "contact_change"),
        ("description", "descriptive_text_change"),
        ("somethingNobodyDocumented", "uncategorized_change"),
    ],
)
def test_modified_field_categorization(field: str, expected: str) -> None:
    assert categorize_modified_field(field) == expected


def test_deadline_and_eligibility_changes_notify_but_contact_churn_does_not() -> None:
    material = classify_amendment(modified_fields=["closeDate", "applicantTypes"])
    assert material["should_notify"] is True
    assert amendment_invariant_failures(material) == []

    noise = classify_amendment(modified_fields=["agencyContactName", "description"])
    assert noise["should_notify"] is False
    # Suppressed, not discarded - the categories are still recorded.
    assert noise["suppressed_categories"]
    assert amendment_invariant_failures(noise) == []


def test_no_amendment_category_is_silently_dropped() -> None:
    amendment = classify_amendment(
        modified_fields=["closeDate", "agencyContactName", "mysteryField"]
    )
    assert set(amendment["material_categories"]) | set(
        amendment["suppressed_categories"]
    ) == set(amendment["categories"])
    assert amendment_invariant_failures(amendment) == []


def test_polymorphic_update_field_alone_does_not_confirm_an_amendment() -> None:
    """The extract field holds the CREATED date when nothing was updated."""
    amendment = classify_amendment(last_updated_or_created_only=True)
    assert amendment["evidence_is_only_polymorphic_field"] is True
    assert amendment["amendment_confirmed"] is False
    assert amendment_invariant_failures(amendment) == []
    lying = dict(amendment, amendment_confirmed=True)
    assert "amendment_confirmed_from_polymorphic_field_alone" in (
        amendment_invariant_failures(lying)
    )


def test_amendment_sends_no_notifications() -> None:
    amendment = classify_amendment(modified_fields=["closeDate"])
    assert amendment["notifications_sent"] == 0


# --------------------------------------------------------------------------
# 92H - crawler governance
# --------------------------------------------------------------------------


def test_nativeforge_user_agent_is_descriptive_and_contactable() -> None:
    assert user_agent_violations(NATIVEFORGE_USER_AGENT) == []
    assert "nativeforge" in NATIVEFORGE_USER_AGENT.lower()
    assert "http" in NATIVEFORGE_USER_AGENT.lower()


@pytest.mark.parametrize("token", sorted(FORBIDDEN_USER_AGENT_TOKENS))
def test_ai_crawler_user_agents_are_refused(token: str) -> None:
    """hud.gov names these with Disallow: / and asserts ai-train=no."""
    fails = user_agent_violations(f"Mozilla/5.0 ({token}/1.0)")
    assert any(f.startswith("ai_crawler_user_agent:") for f in fails)


def test_empty_user_agent_is_a_violation() -> None:
    assert "user_agent_empty" in user_agent_violations("")
    assert "user_agent_empty" in user_agent_violations(None)


def test_site_search_paths_are_disallowed() -> None:
    """Disallow: /search/ is near-universal across agency hosts."""
    result = evaluate_fetch_permission(
        url="https://sam.gov/search/opportunities", user_agent=NATIVEFORGE_USER_AGENT
    )
    assert result["permitted"] is False
    assert any("robots_disallowed_path" in r for r in result["denial_reasons"])


@pytest.mark.parametrize("host", sorted(BLACKLISTED_HOSTS))
def test_blacklisted_hosts_are_never_permitted(host: str) -> None:
    result = evaluate_fetch_permission(
        url=f"https://{host}/anything", user_agent=NATIVEFORGE_USER_AGENT
    )
    assert result["permitted"] is False
    assert any(r.startswith("host_blacklisted:") for r in result["denial_reasons"])


def test_hijacked_domain_is_blocked_with_its_reason() -> None:
    assert "casino" in BLACKLISTED_HOSTS["scdmh.net"]


def test_cdc_tribal_namespace_is_blocked_but_healthy_tribes_is_not() -> None:
    blocked = evaluate_fetch_permission(
        url="https://www.cdc.gov/tribal/index.html", user_agent=NATIVEFORGE_USER_AGENT
    )
    assert blocked["permitted"] is False
    allowed = evaluate_fetch_permission(
        url="https://www.cdc.gov/healthy-tribes/about/index.html",
        user_agent=NATIVEFORGE_USER_AGENT,
    )
    assert allowed["permitted"] is True


def test_governance_never_fetches() -> None:
    result = evaluate_fetch_permission(
        url="https://www.grants.gov/", user_agent=NATIVEFORGE_USER_AGENT
    )
    assert result["fetch_performed"] is False
    assert governance_invariant_failures(result) == []


def test_pacing_floors_hold() -> None:
    assert PER_HOST_CONCURRENCY == 1
    assert MIN_REQUEST_INTERVAL_SECONDS >= 5.0
    result = evaluate_fetch_permission(
        url="https://www.grants.gov/", user_agent=NATIVEFORGE_USER_AGENT
    )
    relaxed = dict(result, min_request_interval_seconds=0.5)
    assert "request_interval_below_floor" in governance_invariant_failures(relaxed)


def test_hud_dead_shell_is_flagged_stale_not_unchanged() -> None:
    """HTTP 200, valid HTML, zero body, titled 25red-Indian Housing."""
    result = classify_page_liveness(
        http_status=200,
        body_bytes=180,
        body_hash="same",
        previous_body_hash="same",
        page_title="25red-Indian Housing",
    )
    assert result["verdict"] == "stale_redesign_artifact"
    assert result["eligible_for_diff"] is False
    assert result["content_changed"] is False
    assert governance_invariant_failures(result) == []


def test_an_empty_body_on_a_200_is_a_dead_shell() -> None:
    result = classify_page_liveness(http_status=200, body_bytes=42, page_title="ONAP")
    assert result["verdict"] == "dead_shell"
    assert result["eligible_for_diff"] is False


def test_liveness_is_never_decided_on_status_alone() -> None:
    result = classify_page_liveness(http_status=200, body_bytes=90_000, page_title="Ok")
    assert result["decided_on_status_alone"] is False
    lying = dict(result, decided_on_status_alone=True)
    assert "liveness_decided_on_status_alone" in governance_invariant_failures(lying)


def test_circuit_breaker_halts_and_pages_rather_than_retrying() -> None:
    open_state = build_circuit_breaker_state(
        source_id="X", consecutive_failures=CIRCUIT_BREAKER_CONSECUTIVE_FAILURES
    )
    assert open_state["tripped"] is True
    assert open_state["halts_source"] is True
    assert open_state["pages_human"] is True
    assert open_state["auto_retries_after_trip"] is False
    assert governance_invariant_failures(open_state) == []


# --------------------------------------------------------------------------
# 92I - SC recognition and geography
# --------------------------------------------------------------------------


def test_three_recognition_sets_are_kept_apart() -> None:
    assert len(RECOGNITION_SETS) == 3


def test_catawba_is_the_only_resident_federally_recognized_tribe() -> None:
    assert FEDERALLY_RECOGNIZED_RESIDENT_IN_SC_COUNT == 1
    record = build_recognition_record(
        entity_name=CATAWBA_NATION_NAME,
        recognition_set="federally_recognized_resident_in_sc",
        resident_state="SC",
    )
    assert record["federally_recognized"] is True
    assert recognition_invariant_failures(record) == []

    impostor = build_recognition_record(
        entity_name="Some Other Nation",
        recognition_set="federally_recognized_resident_in_sc",
    )
    assert "more_than_the_one_resident_federally_recognized_tribe" in (
        recognition_invariant_failures(impostor)
    )


def test_section_106_consultation_listing_is_not_recognition() -> None:
    record = build_recognition_record(
        entity_name="Muscogee (Creek) Nation",
        recognition_set="federally_recognized_with_sc_consultation_interest",
    )
    assert record["is_consultation_listing"] is True
    assert record["consultation_listing_implies_recognition_in_sc"] is False
    conflated = dict(record, consultation_listing_implies_recognition_in_sc=True)
    assert "consultation_listing_treated_as_recognition" in (
        recognition_invariant_failures(conflated)
    )


def test_state_recognized_entity_is_withheld_from_federally_gated_programs() -> None:
    entity = build_recognition_record(
        entity_name="A State-Recognized Tribe",
        recognition_set="sc_state_recognized",
        sc_category="native_american_indian_tribe",
    )
    assert entity["federally_recognized"] is False
    for program in ("GAP", "CTAS", "TTPSF", "SS4A"):
        access = evaluate_program_access(entity=entity, program_id=program)
        assert access["access_status"] == "excluded_federal_recognition_required"
        assert recognition_invariant_failures(access) == []


def test_fta_state_subrecipient_pathway_is_offered_only_where_documented() -> None:
    state_only = build_recognition_record(
        entity_name="A State-Recognized Tribe",
        recognition_set="sc_state_recognized",
        sc_category="native_american_indian_tribe",
    )
    fta = evaluate_program_access(entity=state_only, program_id="FTA_5311")
    assert fta["state_subrecipient_pathway_available"] is True
    assert fta["state_subrecipient_pathway_is_documented"] is True

    gap = evaluate_program_access(entity=state_only, program_id="GAP")
    assert gap["state_subrecipient_pathway_available"] is False


def test_program_access_never_decides_applicant_eligibility() -> None:
    entity = build_recognition_record(
        entity_name=CATAWBA_NATION_NAME,
        recognition_set="federally_recognized_resident_in_sc",
    )
    access = evaluate_program_access(entity=entity, program_id="GAP")
    assert access["applicant_eligibility_determined"] is False
    assert access["customer_advised"] is False


@pytest.mark.parametrize("source_name", sorted(GEOGRAPHY_TEST_CASES))
def test_an_sc_customer_never_sees_an_out_of_region_funder(source_name: str) -> None:
    result = apply_geography_gate(
        customer_states=["SC"],
        source_states=list(GEOGRAPHY_TEST_CASES[source_name]),
        source_name=source_name,
    )
    assert result["verdict"] == "out_of_scope"
    assert result["surfaced_to_customer"] is False
    assert geography_invariant_failures(result) == []


def test_reclamation_covers_seventeen_western_states() -> None:
    states = GEOGRAPHY_TEST_CASES["Bureau of Reclamation Native American Affairs"]
    assert len(states) == RECLAMATION_WESTERN_STATE_COUNT == 17
    assert "SC" not in states


def test_geography_gate_denies_by_default() -> None:
    unknown_source = apply_geography_gate(customer_states=["SC"], source_states=[])
    assert unknown_source["verdict"] == "withheld_unknown"
    assert unknown_source["surfaced_to_customer"] is False

    unknown_customer = apply_geography_gate(customer_states=[], source_states=["SC"])
    assert unknown_customer["verdict"] == "withheld_unknown"
    assert unknown_customer["surfaced_to_customer"] is False


def test_geography_gate_runs_before_ranking() -> None:
    result = apply_geography_gate(customer_states=["SC"], source_states=["SC"])
    assert result["verdict"] == "in_scope"
    assert result["runs_before_ranking"] is True
    demoted = dict(result, runs_before_ranking=False)
    assert "geography_gate_demoted_to_a_post_filter" in (
        geography_invariant_failures(demoted)
    )


def test_enumerated_set_eligibility_beats_a_state_match() -> None:
    """Reclamation's drought opportunity names 30 specific Tribes."""
    result = apply_geography_gate(
        customer_states=["AZ"],
        source_states=["AZ"],
        source_name="Colorado River Basin Tribal Drought Resiliency",
        eligible_entity_set=["Navajo Nation", "Hopi Tribe"],
        customer_entity_name="Some Other Tribe",
    )
    assert result["verdict"] == "out_of_scope"
    assert result["reason"] == "not_in_enumerated_eligible_set"
    assert result["enumerated_set_applied"] is True


def test_enumerated_set_with_an_unnamed_customer_is_withheld() -> None:
    result = apply_geography_gate(
        customer_states=["AZ"],
        source_states=["AZ"],
        eligible_entity_set=["Navajo Nation"],
    )
    assert result["verdict"] == "withheld_unknown"


# --------------------------------------------------------------------------
# Cross-cutting guards
# --------------------------------------------------------------------------


@pytest.mark.parametrize("module_name", GATE92_SERVICES)
def test_gate92_services_import_no_network_library(module_name: str) -> None:
    """Parsed, not grepped - a docstring mentioning `requests` is not a call."""
    path = REPO_ROOT / f"src/nativeforge/services/{module_name}.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
    forbidden = {
        "requests", "httpx", "aiohttp", "socket", "urllib3", "http", "ftplib",
        "telnetlib", "smtplib", "selenium", "playwright",
    }
    assert not (imported & forbidden), sorted(imported & forbidden)


@pytest.mark.parametrize("module_name", GATE92_SERVICES)
def test_gate92_services_use_no_ai_extraction(module_name: str) -> None:
    path = REPO_ROOT / f"src/nativeforge/services/{module_name}.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
    forbidden = {
        "openai", "anthropic", "transformers", "torch", "sentence_transformers",
        "langchain", "llama_index", "tiktoken",
    }
    assert not (imported & forbidden), sorted(imported & forbidden)


@pytest.mark.parametrize("module_name", GATE92_SERVICES)
def test_gate92_service_outputs_are_json_serialisable(module_name: str) -> None:
    builders = {
        "source_spine_build_plan_service": lambda: build_phase1_spine_plan(),
        "opportunity_identity_versioning_service": lambda: build_opportunity_identity(
            opportunity_number="X-1", doc_type="synopsis"
        ),
        "native_eligibility_code_classification_service": (
            lambda: classify_native_eligibility(eligible_applicant_codes="07")
        ),
        "opportunity_deadline_and_amendment_model_service": (
            lambda: build_deadline_model()
        ),
        "source_crawler_governance_service": lambda: evaluate_fetch_permission(
            url="https://www.grants.gov/", user_agent=NATIVEFORGE_USER_AGENT
        ),
        "sc_native_recognition_and_geography_service": lambda: apply_geography_gate(
            customer_states=["SC"], source_states=["SC"]
        ),
        "external_source_registry_v2_reconciliation_service": lambda: (
            reconcile_registries(v1_rows=[], v2_rows=[])
        ),
    }
    json.dumps(builders[module_name]())


def test_research_docs_are_present() -> None:
    """If a file is missing, say so rather than reasoning from memory."""
    required = [
        "nativeforge-funding-source-dossier-v2.md",
        "nativeforge-research-funding-and-cost-allowability.md",
        "ext-apis-monitoring.md",
        "ext-usda-hud-commerce.md",
        "ext-doj-dhs-ed-dol-sba.md",
        "ext-doe-epa-dot.md",
        "ext-extra-tables.md",
        "nativeforge-source-registry-v2.csv",
    ]
    missing = [name for name in required if not (RESEARCH_DIR / name).exists()]
    assert missing == [], f"missing research files: {missing}"


def test_no_gate92_service_claims_live_coverage() -> None:
    banned = (
        "monitoring is active",
        "live source coverage",
        "65% improvement",
        "collection is live",
        "scraper activated",
    )
    for module_name in GATE92_SERVICES:
        text = (
            REPO_ROOT / f"src/nativeforge/services/{module_name}.py"
        ).read_text(encoding="utf-8").lower()
        for phrase in banned:
            assert phrase not in text, f"{module_name}: {phrase}"
