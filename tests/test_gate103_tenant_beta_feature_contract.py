"""Gate 103 - tenant beta feature contract.

Hermetic. Nothing here activates a collector, fetches a URL, sends a message, or
invents a fact about any real Tribe.
"""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from nativeforge.services.nativeforge_software_allowability_source_service import (
    ALLOWABILITY_CLASSES as SOURCE_ALLOWABILITY_CLASSES,
)
from nativeforge.services.software_capacity_allowability_review_service import (
    AFFIRMATIVE_LABELS,
    ALLOWABILITY_LABELS,
    COST_TYPES,
    PROHIBITED_CLAIMS,
    SELF_ASSESSMENT_CAP,
    SOURCE_CLASS_TO_REVIEW_LABEL,
    allowability_review_invariant_failures,
    build_allowability_review,
    review_label_for_source_class,
    summarise_reviews,
)
from nativeforge.services.tenant_beta_contract_artifact_service import (
    ARTIFACT_DIR,
    ARTIFACT_NAMES,
    DECLARATION_KEYS,
    FALSE_DECLARATION_KEYS,
    TenantBetaArtifactError,
    artifact_claim_failures,
    build_tenant_beta_bundle,
    render_summary,
    write_tenant_beta_artifacts,
)
from nativeforge.services.tenant_beta_demo_fixture_service import (
    DEMO_TENANT_COUNT,
    FIXTURE_PERMITTED_STATUSES,
    REAL_TRIBE_NAME_TOKENS,
    build_demo_tenant_fixture_set,
    demo_fixture_invariant_failures,
)
from nativeforge.services.tenant_beta_feature_entitlement_service import (
    BETA_FEATURES,
    DEFAULT_ENABLED_FEATURES,
    build_tenant_feature_entitlement,
    detect_feature_implementation,
    entitlement_invariant_failures,
)
from nativeforge.services.tenant_beta_profile_service import (
    ACTIONABLE_FACT_STATUSES,
    FACT_STATUSES,
    INFERENCE_PROHIBITED,
    RECOGNITION_STATUSES,
    TRACKED_FACT_FIELDS,
    build_tenant_beta_profile,
    profile_invariant_failures,
    summarise_profiles,
)
from nativeforge.services.tenant_beta_readiness_service import (
    DEMO_SCOPE,
    ONBOARDING_COMPONENT_KEYS,
    build_tenant_beta_readiness,
    readiness_invariant_failures,
)
from nativeforge.services.tenant_source_priority_service import (
    PRIORITY_TIERS,
    SOURCE_ACTIVATION_STATUSES,
    build_tenant_source_priority,
    load_registry_rows,
    source_priority_invariant_failures,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

GATE103_SERVICES = (
    "tenant_beta_profile_service",
    "tenant_beta_feature_entitlement_service",
    "tenant_source_priority_service",
    "tenant_beta_demo_fixture_service",
    "software_capacity_allowability_review_service",
    "tenant_beta_readiness_service",
    "tenant_beta_contract_artifact_service",
)


# --------------------------------------------------------------------------
# 103B - tenant profile
# --------------------------------------------------------------------------


def test_a_bare_profile_keeps_every_fact_unknown() -> None:
    profile = build_tenant_beta_profile(tenant_id="t1")
    assert profile["profile_fact_status"] == "unknown"
    for field in TRACKED_FACT_FIELDS:
        assert profile[field]["status"] == "unknown"
        assert profile[field]["value"] is None
    assert profile["blocked_reasons"]
    assert not profile_invariant_failures(profile)


def test_recognition_status_is_never_inferred() -> None:
    """Not from name, not from state, not from anything."""
    profile = build_tenant_beta_profile(
        tenant_id="t1",
        tenant_name="Some Tribe of South Carolina",
        tenant_name_status="tenant_supplied",
        operating_states=["SC"],
        operating_states_status="tenant_supplied",
    )
    assert profile["recognition_status"]["value"] is None
    assert profile["recognition_status"]["status"] == "unknown"


def test_recognition_verified_requires_a_source() -> None:
    without = build_tenant_beta_profile(
        tenant_id="t1",
        recognition_status="federally_recognized",
        recognition_status_status="verified",
    )
    assert without["recognition_status"]["status"] == "needs_human_review"
    assert "recognition_verified_without_a_source" in without["blocked_reasons"]

    with_source = build_tenant_beta_profile(
        tenant_id="t1",
        recognition_status="federally_recognized",
        recognition_status_status="verified",
        recognition_source="BIA federally recognised tribe list",
    )
    assert with_source["recognition_status"]["status"] == "verified"
    assert not profile_invariant_failures(with_source)


def test_an_unrecognised_recognition_value_is_not_coerced() -> None:
    profile = build_tenant_beta_profile(
        tenant_id="t1",
        recognition_status="probably federal",
        recognition_status_status="tenant_supplied",
    )
    assert profile["recognition_status"]["value"] is None
    assert profile["recognition_status"]["status"] == "needs_human_review"


def test_federal_eligibility_is_not_inferred_from_state_recognition() -> None:
    """Recorded as a refusal on every profile, so it stays inspectable."""
    profile = build_tenant_beta_profile(
        tenant_id="t1",
        recognition_status="state_recognized",
        recognition_status_status="tenant_supplied",
    )
    assert profile["eligibility_determined"] is False
    listed = {item["inference"] for item in profile["inference_prohibited"]}
    assert "federal_eligibility_from_state_recognition" in listed
    assert listed == {name for name, _ in INFERENCE_PROHIBITED}


def test_operating_state_is_not_mailing_address() -> None:
    profile = build_tenant_beta_profile(tenant_id="t1", mailing_state="SC")
    assert profile["operating_states"]["value"] is None
    assert profile["sc_priority"] is False
    assert (
        "mailing_state_supplied_without_operating_states" in profile["blocked_reasons"]
    )


@pytest.mark.parametrize(
    ("states", "expected"),
    [(["SC"], True), (["NC", "GA"], False), ([], False)],
)
def test_sc_priority_is_tenant_specific(states: list[str], expected: bool) -> None:
    profile = build_tenant_beta_profile(
        tenant_id="t1",
        operating_states=states,
        operating_states_status="tenant_supplied",
    )
    assert profile["sc_priority"] is expected


def test_demo_fixture_facts_are_labelled_demo_fixture() -> None:
    profile = build_tenant_beta_profile(
        tenant_id="t1",
        tenant_name="Demo Tenant One",
        tenant_name_status="demo_fixture",
    )
    assert profile["tenant_name"]["status"] == "demo_fixture"
    assert "demo_fixture" not in ACTIONABLE_FACT_STATUSES


def test_a_value_without_provenance_is_not_actionable() -> None:
    profile = build_tenant_beta_profile(tenant_id="t1", service_area="Statewide")
    assert profile["service_area"]["status"] == "needs_human_review"


def test_a_profile_does_not_imply_coverage() -> None:
    profile = build_tenant_beta_profile(
        tenant_id="t1", source_watchlist=["grants_gov", "sc_source"]
    )
    assert profile["source_watchlist"] == ["grants_gov", "sc_source"]
    assert profile["source_monitoring_live"] is False
    assert profile["live_source_coverage"] is False
    assert profile["collectors_active"] == 0


def test_the_overall_status_is_the_weakest_fact() -> None:
    profile = build_tenant_beta_profile(
        tenant_id="t1",
        tenant_name="X",
        tenant_name_status="verified",
        tenant_kind="tribal_government",
        tenant_kind_status="verified",
    )
    # recognition, operating states, service area and classes are still unknown
    assert profile["profile_fact_status"] == "unknown"


def test_fact_status_vocabulary_is_closed() -> None:
    assert FACT_STATUSES == frozenset(
        {
            "verified",
            "tenant_supplied",
            "demo_fixture",
            "unknown",
            "needs_human_review",
        }
    )


@pytest.mark.parametrize(
    "key", ["source_monitoring_live", "live_source_coverage", "eligibility_determined"]
)
def test_profile_invariants_reject_a_coverage_claim(key: str) -> None:
    profile = build_tenant_beta_profile(tenant_id="t1")
    fails = profile_invariant_failures(dict(profile, **{key: True}))
    assert f"profile_claimed:{key}" in fails


def test_profile_invariants_reject_sc_priority_without_sc() -> None:
    profile = build_tenant_beta_profile(tenant_id="t1")
    fails = profile_invariant_failures(dict(profile, sc_priority=True))
    assert "sc_priority_without_sc_in_operating_states" in fails


def test_profile_invariants_reject_an_upgraded_status() -> None:
    profile = build_tenant_beta_profile(tenant_id="t1")
    fails = profile_invariant_failures(dict(profile, profile_fact_status="verified"))
    assert "profile_status_stronger_than_its_weakest_fact" in fails


def test_profile_summary_reports_no_coverage() -> None:
    summary = summarise_profiles([build_tenant_beta_profile(tenant_id="t1")])
    assert summary["source_monitoring_live"] is False
    assert summary["collectors_active"] == 0
    assert summary["verified_profile_count"] == 0


# --------------------------------------------------------------------------
# 103C - feature entitlement
# --------------------------------------------------------------------------


def test_entitlement_covers_every_beta_feature() -> None:
    result = build_tenant_feature_entitlement(tenant_id="t1")
    assert set(result["enabled_features"]) | set(result["disabled_features"]) == set(
        BETA_FEATURES
    )
    assert len(BETA_FEATURES) == 11
    assert not entitlement_invariant_failures(result)


def test_daily_alerts_are_off_by_default() -> None:
    """Weekly is the default; daily is an opt-in for grants/admin users."""
    assert "optional_daily_alerts" not in DEFAULT_ENABLED_FEATURES
    result = build_tenant_feature_entitlement(tenant_id="t1")
    assert "optional_daily_alerts" in result["disabled_features"]


def test_enabling_digest_does_not_imply_email_is_live() -> None:
    result = build_tenant_feature_entitlement(
        tenant_id="t1", requested_features=["weekly_nofo_digest"]
    )
    assert "weekly_nofo_digest" in result["enabled_features"]
    assert result["digest_email_delivery_live"] is False


def test_enabling_the_watchlist_does_not_imply_monitoring() -> None:
    result = build_tenant_feature_entitlement(
        tenant_id="t1", requested_features=["sc_federal_source_watchlist"]
    )
    assert "sc_federal_source_watchlist" in result["enabled_features"]
    assert result["source_monitoring_live"] is False
    assert result["collectors_active"] == 0


def test_enabling_awarded_grants_does_not_verify_requirements() -> None:
    result = build_tenant_feature_entitlement(
        tenant_id="t1", requested_features=["awarded_grants_workspace"]
    )
    assert "awarded_grants_workspace" in result["enabled_features"]
    assert result["extracted_requirements_verified"] is False


def test_enabling_a_feature_does_not_implement_it() -> None:
    """The digest has no service. The entitlement says so rather than pretending."""
    result = build_tenant_feature_entitlement(
        tenant_id="t1", requested_features=["weekly_nofo_digest"]
    )
    assert result["features_implemented_by_enabling"] is False
    assert result["feature_implementation"]["weekly_nofo_digest"] is False
    assert "feature_not_implemented:weekly_nofo_digest" in result["blocked_reasons"]


def test_implementation_is_detected_not_declared() -> None:
    detected = detect_feature_implementation()
    assert detected["detection_method"] == "importlib.util.find_spec"
    # Backed by a real service.
    assert detected["implemented"]["tenant_eligibility_profile"] is True
    # Gate 104's, and genuinely absent.
    assert detected["implemented"]["weekly_nofo_digest"] is False
    assert detected["implemented"]["pursuit_suppression"] is False


def test_an_unrecognised_feature_is_reported_not_honoured() -> None:
    result = build_tenant_feature_entitlement(
        tenant_id="t1", requested_features=["weekly_nofo_digest", "mind_reading"]
    )
    assert "mind_reading" not in result["enabled_features"]
    assert result["unrecognised_features"] == ["mind_reading"]


def test_configuration_gaps_name_what_is_missing() -> None:
    result = build_tenant_feature_entitlement(
        tenant_id="t1", requested_features=["sc_federal_source_watchlist"]
    )
    entries = {c["feature"]: c["missing"] for c in result["configuration_required"]}
    assert "operating_states" in entries["sc_federal_source_watchlist"]


@pytest.mark.parametrize(
    ("feature", "downstream"),
    [
        ("weekly_nofo_digest", "digest_email_delivery_live"),
        ("sc_federal_source_watchlist", "source_monitoring_live"),
        ("awarded_grants_workspace", "extracted_requirements_verified"),
    ],
)
def test_entitlement_invariants_reject_a_downstream_claim(
    feature: str, downstream: str
) -> None:
    result = build_tenant_feature_entitlement(
        tenant_id="t1", requested_features=[feature]
    )
    fails = entitlement_invariant_failures(dict(result, **{downstream: True}))
    assert f"{feature}_read_as:{downstream}" in fails


# --------------------------------------------------------------------------
# 103D - source priority
# --------------------------------------------------------------------------


def _sc_profile():
    return build_tenant_beta_profile(
        tenant_id="sc-tenant",
        operating_states=["SC"],
        operating_states_status="tenant_supplied",
    )


def test_the_registry_fixture_loads() -> None:
    rows = load_registry_rows()
    assert len(rows) == 381


def test_an_sc_tenant_gets_sc_sources_first() -> None:
    result = build_tenant_source_priority(tenant_id="sc-tenant", profile=_sc_profile())
    assert result["sc_source_count"] == 57
    assert result["federal_source_count"] == 303
    assert result["sc_priority_applied"] is True
    assert result["source_priority_rows"][0]["priority_tier"] == "tenant_state_priority"
    assert not source_priority_invariant_failures(result)


def test_a_non_sc_tenant_gets_no_sc_tier() -> None:
    """SC priority is a property of these tenants, not of NativeForge."""
    profile = build_tenant_beta_profile(
        tenant_id="nc-tenant",
        operating_states=["NC"],
        operating_states_status="tenant_supplied",
    )
    result = build_tenant_source_priority(tenant_id="nc-tenant", profile=profile)
    assert result["sc_source_count"] == 0
    assert result["sc_priority_applied"] is False
    assert result["federal_source_count"] == 303


def test_a_tenant_with_no_state_gets_no_state_tier() -> None:
    result = build_tenant_source_priority(
        tenant_id="t1", profile=build_tenant_beta_profile(tenant_id="t1")
    )
    assert result["sc_source_count"] == 0
    assert "tenant_operating_states_unknown" in result["blocked_reasons"]


def test_source_priority_reports_zero_active_and_monitored() -> None:
    result = build_tenant_source_priority(tenant_id="sc-tenant", profile=_sc_profile())
    assert result["sources_active"] == 0
    assert result["sources_monitored"] == 0
    assert result["live_coverage"] is False
    assert result["collectors_activated"] == 0
    assert "no_active_collectors" in result["blocked_reasons"]


def test_no_source_row_claims_to_be_running() -> None:
    result = build_tenant_source_priority(tenant_id="sc-tenant", profile=_sc_profile())
    for row in result["source_priority_rows"]:
        assert row["active"] is False
        assert row["monitored"] is False
        assert row["fetch_performed"] is False
        assert row["activation_status"] in SOURCE_ACTIVATION_STATUSES
        assert row["priority_tier"] in PRIORITY_TIERS


def test_ranking_is_order_independent_and_stable() -> None:
    first = build_tenant_source_priority(tenant_id="sc-tenant", profile=_sc_profile())
    second = build_tenant_source_priority(tenant_id="sc-tenant", profile=_sc_profile())
    assert [r["source_id"] for r in first["source_priority_rows"]] == [
        r["source_id"] for r in second["source_priority_rows"]
    ]


def test_priority_invariants_reject_a_coverage_claim() -> None:
    result = build_tenant_source_priority(tenant_id="sc-tenant", profile=_sc_profile())
    fails = source_priority_invariant_failures(dict(result, live_coverage=True))
    assert "priority_claimed:live_coverage" in fails


def test_priority_invariants_reject_sc_sources_for_a_non_sc_tenant() -> None:
    profile = build_tenant_beta_profile(
        tenant_id="nc",
        operating_states=["NC"],
        operating_states_status="tenant_supplied",
    )
    result = build_tenant_source_priority(tenant_id="nc", profile=profile)
    fails = source_priority_invariant_failures(dict(result, sc_source_count=57))
    assert "sc_sources_counted_for_a_non_sc_tenant" in fails


# --------------------------------------------------------------------------
# 103E - demo fixtures
# --------------------------------------------------------------------------


def test_four_demo_tenants_are_produced() -> None:
    fixtures = build_demo_tenant_fixture_set()
    assert fixtures["tenant_count"] == DEMO_TENANT_COUNT == 4
    assert fixtures["fixture_status"] == "demo_fixture"
    assert not demo_fixture_invariant_failures(fixtures)


def test_no_demo_fixture_names_a_real_tribe() -> None:
    fixtures = build_demo_tenant_fixture_set()
    assert fixtures["real_tribe_named"] is False
    blob = json.dumps(fixtures).lower()
    for token in REAL_TRIBE_NAME_TOKENS:
        assert token not in blob, token


def test_no_demo_fixture_produces_a_verified_fact() -> None:
    fixtures = build_demo_tenant_fixture_set()
    assert fixtures["facts_verified_count"] == 0
    for profile in fixtures["tenant_profiles"]:
        for field in TRACKED_FACT_FIELDS:
            status = profile[field]["status"]
            assert status in FIXTURE_PERMITTED_STATUSES | {"needs_human_review"}


@pytest.mark.parametrize(
    "field", ["recognition_status", "applicant_classes", "service_area"]
)
def test_the_consequential_facts_are_never_fabricated(field: str) -> None:
    fixtures = build_demo_tenant_fixture_set()
    for profile in fixtures["tenant_profiles"]:
        assert profile[field]["value"] is None, profile["tenant_id"]


def test_the_fixture_set_shows_tenant_specific_sc_priority() -> None:
    """Two SC tenants, one elsewhere, one unknown - so the demo can show both."""
    fixtures = build_demo_tenant_fixture_set()
    assert fixtures["sc_priority_count"] == 2


def test_the_real_path_is_a_separate_function() -> None:
    """Nobody reaches the fabricating path by passing a flag."""
    from nativeforge.services.tenant_beta_demo_fixture_service import (
        build_supplied_tenant_profile,
    )

    supplied = build_supplied_tenant_profile(
        tenant_id="real-1",
        tenant_name="Supplied Name",
        tenant_name_status="tenant_supplied",
    )
    assert supplied["tenant_name"]["status"] == "tenant_supplied"


def test_fixture_invariants_reject_a_verified_claim() -> None:
    fixtures = build_demo_tenant_fixture_set()
    fails = demo_fixture_invariant_failures(dict(fixtures, facts_verified_count=3))
    assert "fixture_reported_a_verified_fact" in fails


def test_fixture_invariants_reject_a_real_tribe_name() -> None:
    fixtures = build_demo_tenant_fixture_set()
    profiles = list(fixtures["tenant_profiles"])
    profiles[0] = dict(
        profiles[0],
        tenant_name={"value": "Catawba Nation", "status": "demo_fixture"},
    )
    fails = demo_fixture_invariant_failures(dict(fixtures, tenant_profiles=profiles))
    assert any("named_a_real_tribe" in f for f in fails)


# --------------------------------------------------------------------------
# 103F - allowability review
# --------------------------------------------------------------------------


def test_the_six_labels_are_the_required_ones() -> None:
    assert ALLOWABILITY_LABELS == frozenset(
        {
            "clearly_allowable",
            "likely_allowable",
            "possibly_allowable",
            "not_indicated",
            "likely_not_allowable",
            "requires_human_review",
        }
    )


@pytest.mark.parametrize("label", sorted(AFFIRMATIVE_LABELS))
def test_no_affirmative_label_without_evidence(label: str) -> None:
    review = build_allowability_review(
        opportunity_id="opp-1", assessed_cost_type="grant_administration",
        proposed_label=label,
    )
    assert review["allowability_label"] == "not_indicated"
    assert "no_evidence_supplied" in review["blocked_reasons"]
    assert not allowability_review_invariant_failures(review)


def test_an_affirmative_label_with_evidence_is_kept() -> None:
    """Not vacuous: if nothing could ever be allowable, the refusals prove nothing."""
    review = build_allowability_review(
        opportunity_id="opp-1",
        assessed_cost_type="grant_administration",
        proposed_label="clearly_allowable",
        evidence_quotes=["Allowable costs include grant administration."],
    )
    assert review["allowability_label"] == "clearly_allowable"
    assert review["evidence_present"] is True
    assert not allowability_review_invariant_failures(review)


def test_nativeforge_self_assessment_is_capped_at_human_review() -> None:
    """The one place this gate removes a capability rather than adding one."""
    review = build_allowability_review(
        opportunity_id="opp-1",
        assessed_cost_type="software_license",
        proposed_label="clearly_allowable",
        evidence_quotes=["Allowable costs include grant management software."],
        is_nativeforge_itself=True,
    )
    assert review["allowability_label"] == SELF_ASSESSMENT_CAP
    assert SELF_ASSESSMENT_CAP == "requires_human_review"
    # Nothing is hidden - the pre-cap label is retained.
    assert review["uncapped_label"] == "clearly_allowable"
    assert review["self_assessment_capped"] is True
    assert review["human_review_required"] is True
    assert not allowability_review_invariant_failures(review)


@pytest.mark.parametrize("label", sorted(ALLOWABILITY_LABELS))
def test_the_cap_holds_for_every_starting_label(label: str) -> None:
    review = build_allowability_review(
        opportunity_id="opp-1",
        assessed_cost_type="software_license",
        proposed_label=label,
        evidence_quotes=["some supporting text"],
        is_nativeforge_itself=True,
    )
    assert review["allowability_label"] == SELF_ASSESSMENT_CAP


def test_another_vendors_software_is_not_capped() -> None:
    """Capping every software assessment would make the feature useless."""
    review = build_allowability_review(
        opportunity_id="opp-1",
        assessed_cost_type="software_license",
        proposed_label="likely_allowable",
        evidence_quotes=["Software licences are permitted."],
        is_nativeforge_itself=False,
    )
    assert review["allowability_label"] == "likely_allowable"
    assert any("confirm_vendor" in r for r in review["blocked_reasons"])


def test_the_source_class_bridge_covers_every_gate_92_class() -> None:
    assert set(SOURCE_CLASS_TO_REVIEW_LABEL) == set(SOURCE_ALLOWABILITY_CLASSES)
    for label in SOURCE_CLASS_TO_REVIEW_LABEL.values():
        assert label in ALLOWABILITY_LABELS


def test_an_unknown_source_class_bridges_to_human_review() -> None:
    assert review_label_for_source_class("something_else") == "requires_human_review"


def test_no_review_renders_a_prohibited_claim() -> None:
    review = build_allowability_review(
        opportunity_id="opp-1",
        assessed_cost_type="grant_administration",
        proposed_label="clearly_allowable",
        evidence_quotes=["Allowable costs include grant administration."],
    )
    wording = review["label_wording"].lower()
    for claim in PROHIBITED_CLAIMS:
        assert claim not in wording, claim
    assert review["funding_guaranteed"] is False
    assert review["allowability_determined"] is False


def test_review_invariants_reject_an_escaped_cap() -> None:
    review = build_allowability_review(
        opportunity_id="opp-1",
        assessed_cost_type="software_license",
        proposed_label="clearly_allowable",
        evidence_quotes=["text"],
        is_nativeforge_itself=True,
    )
    forged = dict(review, allowability_label="clearly_allowable")
    fails = allowability_review_invariant_failures(forged)
    assert "self_assessment_escaped_the_human_review_cap" in fails


def test_review_invariants_reject_an_unevidenced_affirmative() -> None:
    review = build_allowability_review(
        opportunity_id="opp-1", assessed_cost_type="grant_administration"
    )
    forged = dict(review, allowability_label="clearly_allowable")
    fails = allowability_review_invariant_failures(forged)
    assert "affirmative_label_without_evidence" in fails


def test_cost_type_vocabulary_is_closed() -> None:
    review = build_allowability_review(
        opportunity_id="opp-1", assessed_cost_type="nonsense"
    )
    assert review["assessed_cost_type"] == "unknown"
    assert "unknown" in COST_TYPES


def test_review_summary_reports_the_cap_count() -> None:
    reviews = [
        build_allowability_review(
            opportunity_id="o1",
            assessed_cost_type="software_license",
            proposed_label="clearly_allowable",
            evidence_quotes=["text"],
            is_nativeforge_itself=True,
        ),
        build_allowability_review(
            opportunity_id="o2",
            assessed_cost_type="grant_administration",
            proposed_label="likely_allowable",
            evidence_quotes=["text"],
        ),
    ]
    summary = summarise_reviews(reviews)
    assert summary["self_assessed_count"] == 1
    assert summary["self_assessment_capped_count"] == 1
    assert summary["funding_guaranteed"] is False


# --------------------------------------------------------------------------
# 103G - readiness
# --------------------------------------------------------------------------


def test_the_contract_demo_is_ready_and_scoped() -> None:
    readiness = build_tenant_beta_readiness()
    assert readiness["ready_for_demo"] is True
    assert readiness["demo_scope"] == DEMO_SCOPE
    assert "fixture" in DEMO_SCOPE
    assert not readiness_invariant_failures(readiness)


def test_beta_onboarding_is_not_ready() -> None:
    readiness = build_tenant_beta_readiness()
    assert readiness["ready_for_beta_onboarding"] is False
    assert set(readiness["onboarding_components_missing"]) == set(
        ONBOARDING_COMPONENT_KEYS
    )


@pytest.mark.parametrize("key", list(ONBOARDING_COMPONENT_KEYS))
def test_each_onboarding_component_is_absent(key: str) -> None:
    assert build_tenant_beta_readiness()[key] is False


def test_readiness_does_not_claim_live_source_collection() -> None:
    readiness = build_tenant_beta_readiness()
    assert readiness["live_source_collection_available"] is False
    assert readiness["source_monitoring_live"] is False
    assert readiness["live_source_coverage"] is False
    assert readiness["collectors_active"] == 0


def test_readiness_does_not_claim_customer_auth() -> None:
    readiness = build_tenant_beta_readiness()
    assert readiness["customer_auth_live"] is False
    assert readiness["customer_persistence_live"] is False


def test_the_digest_contract_is_absent_and_says_so() -> None:
    readiness = build_tenant_beta_readiness()
    assert readiness["digest_contract_available"] is False
    assert readiness["pursuit_suppression_contract_available"] is False
    assert any("gate_104" in r for r in readiness["blocked_reasons"])


def test_readiness_invariants_reject_forged_onboarding() -> None:
    readiness = build_tenant_beta_readiness()
    fails = readiness_invariant_failures(
        dict(readiness, ready_for_beta_onboarding=True)
    )
    assert "onboarding_readiness_disagrees_with_its_components" in fails


def test_readiness_invariants_reject_live_collection_without_collectors() -> None:
    readiness = build_tenant_beta_readiness()
    fails = readiness_invariant_failures(
        dict(readiness, live_source_collection_available=True)
    )
    assert "live_collection_claimed_without_active_collectors" in fails


# --------------------------------------------------------------------------
# 103 - the services do not fetch
# --------------------------------------------------------------------------


def _service_source(name: str) -> str:
    return (REPO_ROOT / "src" / "nativeforge" / "services" / f"{name}.py").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize("name", GATE103_SERVICES)
def test_no_gate103_service_imports_an_http_client(name: str) -> None:
    banned = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib.request",
        "urllib3",
        "http.client",
        "socket",
    }
    tree = ast.parse(_service_source(name))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not imported & banned, f"{name} imports {imported & banned}"


@pytest.mark.parametrize("name", GATE103_SERVICES)
def test_no_gate103_service_imports_a_collector(name: str) -> None:
    tree = ast.parse(_service_source(name))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    offending = {
        m
        for m in modules
        if any(
            token in m
            for token in (
                "polite_http",
                "live_network_guard",
                "real_url_resolver",
                "live_fetch",
                "source_connectors",
                "source_check_bridge",
            )
        )
    }
    assert not offending, f"{name} imports {offending}"


@pytest.mark.parametrize("name", GATE103_SERVICES)
def test_every_gate103_service_declares_a_schema_version(name: str) -> None:
    module = __import__(f"nativeforge.services.{name}", fromlist=["SCHEMA_VERSION"])
    assert module.SCHEMA_VERSION.startswith("nf_")


def test_gate_92s_allowability_service_is_unmodified() -> None:
    """55 registry rows and Gate 92's tests depend on its vocabulary."""
    assert SOURCE_ALLOWABILITY_CLASSES == frozenset(
        {
            "clearly_allowable",
            "likely_allowable",
            "sometimes_allowable",
            "unclear",
            "unlikely_allowable",
            "unknown",
        }
    )


# --------------------------------------------------------------------------
# 103H - artifacts
# --------------------------------------------------------------------------


def test_artifacts_regenerate_deterministically(tmp_path: Path) -> None:
    first = tmp_path / "a"
    second = tmp_path / "b"
    write_tenant_beta_artifacts(repo_root=first)
    write_tenant_beta_artifacts(repo_root=second)
    for name in ARTIFACT_NAMES:
        a = (first / ARTIFACT_DIR / name).read_bytes()
        b = (second / ARTIFACT_DIR / name).read_bytes()
        assert hashlib.sha256(a).hexdigest() == hashlib.sha256(b).hexdigest(), name


def test_committed_artifacts_match_a_fresh_generation(tmp_path: Path) -> None:
    committed = REPO_ROOT / ARTIFACT_DIR
    if not (committed / ARTIFACT_NAMES[0]).exists():
        pytest.skip("tenant beta artifacts not generated in this tree")
    write_tenant_beta_artifacts(repo_root=tmp_path)
    for name in ARTIFACT_NAMES:
        fresh = (tmp_path / ARTIFACT_DIR / name).read_bytes()
        on_disk = (committed / name).read_bytes()
        assert (
            hashlib.sha256(on_disk).hexdigest() == hashlib.sha256(fresh).hexdigest()
        ), name


def test_all_six_artifacts_are_written(tmp_path: Path) -> None:
    result = write_tenant_beta_artifacts(repo_root=tmp_path)
    assert len(ARTIFACT_NAMES) == 6
    for name in ARTIFACT_NAMES:
        assert (tmp_path / ARTIFACT_DIR / name).exists(), name
    assert result["files"] == list(ARTIFACT_NAMES)


@pytest.mark.parametrize("name", ARTIFACT_NAMES)
def test_every_artifact_states_the_declarations(name: str) -> None:
    path = REPO_ROOT / ARTIFACT_DIR / name
    if not path.exists():
        pytest.skip("tenant beta artifacts not generated in this tree")
    text = path.read_text(encoding="utf-8")
    for key in DECLARATION_KEYS:
        assert key in text, f"{name} omits {key}"


def test_the_artifacts_claim_no_live_coverage() -> None:
    path = REPO_ROOT / ARTIFACT_DIR / "tenant_beta_feature_contract.json"
    if not path.exists():
        pytest.skip("tenant beta artifacts not generated in this tree")
    payload = json.loads(path.read_text(encoding="utf-8"))
    for key in FALSE_DECLARATION_KEYS:
        assert payload[key] is False, key
    assert payload["tenant_beta_contract_available"] is True
    assert payload["ready_for_demo_contract"] is True


def test_the_committed_profiles_name_no_real_tribe() -> None:
    path = REPO_ROOT / ARTIFACT_DIR / "tenant_beta_demo_profiles.json"
    if not path.exists():
        pytest.skip("tenant beta artifacts not generated in this tree")
    lowered = path.read_text(encoding="utf-8").lower()
    for token in REAL_TRIBE_NAME_TOKENS:
        assert token not in lowered, token


def test_the_allowability_artifact_keeps_the_cap() -> None:
    path = REPO_ROOT / ARTIFACT_DIR / "software_capacity_allowability_contract.json"
    if not path.exists():
        pytest.skip("tenant beta artifacts not generated in this tree")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["self_assessment_cap"] == SELF_ASSESSMENT_CAP
    example = payload["examples"]["nativeforge_self_assessed"]
    assert example["allowability_label"] == SELF_ASSESSMENT_CAP
    assert example["uncapped_label"] == "clearly_allowable"


def test_the_source_matrix_reports_zero_active_everywhere() -> None:
    path = REPO_ROOT / ARTIFACT_DIR / "tenant_source_priority_matrix.csv"
    if not path.exists():
        pytest.skip("tenant beta artifacts not generated in this tree")
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == (DEMO_TENANT_COUNT * len(PRIORITY_TIERS)) + 1
    for line in lines[1:]:
        assert line.endswith("True,True,False,False,False,False,False"), line


def test_a_clean_bundle_has_no_claim_failures() -> None:
    bundle = build_tenant_beta_bundle(repo_root=REPO_ROOT)
    assert artifact_claim_failures(bundle, render_summary(bundle)) == []


def test_the_writer_refuses_a_forged_declaration(tmp_path: Path, monkeypatch) -> None:
    import nativeforge.services.tenant_beta_contract_artifact_service as mod

    real = mod.build_tenant_beta_bundle

    def lying(*, repo_root=None):
        bundle = real(repo_root=repo_root)
        bundle["declarations"]["live_source_collection_available"] = True
        return bundle

    monkeypatch.setattr(mod, "build_tenant_beta_bundle", lying)
    with pytest.raises(TenantBetaArtifactError):
        mod.write_tenant_beta_artifacts(repo_root=tmp_path)
    assert not (tmp_path / ARTIFACT_DIR).exists()


def test_the_writer_refuses_a_named_tribe(tmp_path: Path, monkeypatch) -> None:
    import nativeforge.services.tenant_beta_contract_artifact_service as mod

    real = mod.build_tenant_beta_bundle

    def named(*, repo_root=None):
        bundle = real(repo_root=repo_root)
        bundle["fixtures"] = dict(bundle["fixtures"], real_tribe_named=True)
        return bundle

    monkeypatch.setattr(mod, "build_tenant_beta_bundle", named)
    with pytest.raises(TenantBetaArtifactError):
        mod.write_tenant_beta_artifacts(repo_root=tmp_path)
    assert not (tmp_path / ARTIFACT_DIR).exists()


def test_no_artifact_contains_a_secret() -> None:
    directory = REPO_ROOT / ARTIFACT_DIR
    if not directory.exists():
        pytest.skip("tenant beta artifacts not generated in this tree")
    for path in sorted(directory.glob("*")):
        text = path.read_text(encoding="utf-8")
        assert "-----BEGIN" not in text
        assert "eyJ" not in text
        for marker in ("Bearer ", "api_key=", "postgresql://", "password="):
            assert marker not in text, f"{path.name} contains {marker!r}"


def test_the_artifact_dir_is_not_gitignored() -> None:
    proc = subprocess.run(
        ["git", "check-ignore", "-q", f"{ARTIFACT_DIR}/{ARTIFACT_NAMES[0]}"],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    assert proc.returncode != 0, "tenant beta artifacts are gitignored"


# --------------------------------------------------------------------------
# 103 - cross-cutting
# --------------------------------------------------------------------------


def test_the_gate_activates_nothing() -> None:
    readiness = build_tenant_beta_readiness()
    priority = build_tenant_source_priority(
        tenant_id="sc-tenant", profile=_sc_profile()
    )
    assert readiness["collectors_active"] == 0
    assert readiness["production_rollout"] is False
    assert readiness["controlled_customer_pilot"] is False
    assert priority["collectors_activated"] == 0
    assert priority["fetch_performed"] is False


def test_no_environment_variable_can_claim_coverage(monkeypatch) -> None:
    for name in (
        "NF_LIVE_SOURCE_COVERAGE",
        "NF_SOURCE_MONITORING_LIVE",
        "NF_CUSTOMER_AUTH_LIVE",
        "NF_BETA_ONBOARDING_READY",
    ):
        monkeypatch.setenv(name, "true")
    readiness = build_tenant_beta_readiness()
    assert readiness["live_source_coverage"] is False
    assert readiness["customer_auth_live"] is False
    assert readiness["ready_for_beta_onboarding"] is False


def test_recognition_statuses_stay_distinct() -> None:
    """Gate 92's rule, carried into the tenant model."""
    assert RECOGNITION_STATUSES == frozenset(
        {
            "federally_recognized",
            "state_recognized",
            "historic_affiliation",
            "unrecognized",
            "unknown",
        }
    )
