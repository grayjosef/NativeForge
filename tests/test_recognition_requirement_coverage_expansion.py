"""Recognition-requirement coverage expansion: GG applicant types + derivation regression."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nativeforge.services.grants_gov_applicant_type_recognition_service import (
    TYPE_FED_TRIBAL_GOV,
    TYPE_NONFED_TRIBAL_ORG,
    TYPE_NONPROFIT_501C3,
    TYPE_NONPROFIT_NO_501C3,
    derive_recognition_from_applicant_type_ids,
    derive_recognition_from_grant_applicant_types,
    infer_applicant_type_ids_from_labels,
    resolve_grant_applicant_type_ids,
)
from nativeforge.services.grant_eligibility_conditions_service import (
    enrich_grant_with_eligibility_metadata,
)
from nativeforge.services.matching_profile_provenance_service import (
    CAPTURE_PUBLIC_INFERRED,
    build_matching_profile_with_provenance,
)
from nativeforge.services.recognition_requirement_derivation_service import (
    derive_recognition_requirement_bundle,
    derive_recognition_requirement_from_grant,
)
from nativeforge.services.recognition_tier_eligibility_gate_service import (
    OUTCOME_BLOCKED,
    OUTCOME_ELIGIBLE,
    apply_recognition_tier_eligibility_gate,
)
from nativeforge.services.sc_pilot_fixture_loader_service import load_sc_eligibility_rules
from nativeforge.services.tier3_foundation_corpus_persist_service import load_mixed_tier13_corpus

_SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "recognition_requirement_regression_snapshot.json"
)


def _state_only_profile(**extra: object) -> dict:
    base = {
        "fixture_key": "sc_test_state_only",
        "organization_name": "Test State-Recognized Tribe",
        "recognition_type": "state_only",
        "applicant_type": "tribal_government",
        "service_geography": "south_carolina",
        "capture_method": CAPTURE_PUBLIC_INFERRED,
    }
    base.update(extra)
    return build_matching_profile_with_provenance(base)


def test_applicant_type_07_only_federal_required() -> None:
    result = derive_recognition_from_applicant_type_ids([TYPE_FED_TRIBAL_GOV])
    assert result is not None
    assert result["recognition_requirement"] == "federal_required"
    assert result["recognition_requirement_source"] == "applicant_types"


def test_applicant_type_11_only_state_ok() -> None:
    result = derive_recognition_from_applicant_type_ids([TYPE_NONFED_TRIBAL_ORG])
    assert result is not None
    assert result["recognition_requirement"] == "state_ok"


def test_applicant_type_07_and_11_state_ok_ac2d() -> None:
    """AC-2d: 07 + 11 → state_ok; state-only tribe eligible."""
    result = derive_recognition_from_applicant_type_ids(
        [TYPE_FED_TRIBAL_GOV, TYPE_NONFED_TRIBAL_ORG]
    )
    assert result is not None
    assert result["recognition_requirement"] == "state_ok"

    grant = {
        "grant_id": "test-07-11",
        "eligibility_text": (
            "Applicant types: Native American tribal governments (Federally recognized); "
            "Native American tribal organizations (other than Federally recognized tribal governments)"
        ),
        "tribal_eligible": True,
    }
    enriched = enrich_grant_with_eligibility_metadata(grant)
    assert enriched["recognition_requirement"] == "state_ok"
    assert enriched["recognition_requirement_source"] == "applicant_types"

    profile = _state_only_profile()
    gate = apply_recognition_tier_eligibility_gate(
        opportunity=enriched,
        profile=profile,
    )
    assert gate["recognition_tier_mismatch"] is False
    assert gate["excluded_from_match_set"] is False
    assert gate["outcome"] == OUTCOME_ELIGIBLE


def test_applicant_type_07_and_12_dual_pathway_ac2e() -> None:
    """AC-2e: 07 + 12 (no 11) → dual pathway; tribal blocked, nonprofit eligible w/ 501c3."""
    result = derive_recognition_from_applicant_type_ids(
        [TYPE_FED_TRIBAL_GOV, TYPE_NONPROFIT_501C3]
    )
    assert result is not None
    assert result["recognition_requirement"] == "federal_required_for_tribal_pathway"
    assert result["requires_501c3_from_applicant_types"] is True
    assert result["dual_pathway_from_applicant_types"]["nonprofit_alternative"] is True

    grant = {
        "grant_id": "test-07-12",
        "eligibility_text": (
            "Applicant types: Native American tribal governments (Federally recognized); "
            "Nonprofits having a 501(c)(3) status with the IRS, other than institutions of higher education"
        ),
        "tribal_eligible": True,
    }
    enriched = enrich_grant_with_eligibility_metadata(grant)
    assert enriched["recognition_requirement"] == "federal_required_for_tribal_pathway"
    assert enriched["requires_501c3"] is True
    assert enriched["dual_pathway"]["nonprofit_alternative"] is True

    profile = _state_only_profile(has_501c3=True)
    gate = apply_recognition_tier_eligibility_gate(opportunity=enriched, profile=profile)
    assert gate["recognition_tier_mismatch"] is True
    assert gate["tribal_pathway"]["outcome"] == OUTCOME_BLOCKED
    assert gate["nonprofit_pathway"]["outcome"] == OUTCOME_ELIGIBLE
    assert gate["outcome"] == OUTCOME_ELIGIBLE
    assert gate["excluded_from_match_set"] is False


def test_applicant_type_12_open_nonprofit_requires_501c3() -> None:
    result = derive_recognition_from_applicant_type_ids([TYPE_NONPROFIT_501C3])
    assert result is not None
    assert result["recognition_requirement"] == "open_nonprofit"
    assert result["requires_501c3_from_applicant_types"] is True


def test_applicant_type_13_open_nonprofit_no_501c3_requirement() -> None:
    result = derive_recognition_from_applicant_type_ids([TYPE_NONPROFIT_NO_501C3])
    assert result is not None
    assert result["recognition_requirement"] == "open_nonprofit"
    assert result.get("requires_501c3_from_applicant_types") is False


def test_applicant_type_gov_only_unknown() -> None:
    result = derive_recognition_from_applicant_type_ids(["01"])
    assert result is not None
    assert result["recognition_requirement"] == "unknown"


def test_backfill_applicant_type_ids_from_eligibility_text() -> None:
    grant = {
        "eligibility_text": (
            "Applicant types: Native American tribal governments (Federally recognized)\n\n"
            "Only Indian tribes."
        )
    }
    ids = resolve_grant_applicant_type_ids(grant)
    assert ids == [TYPE_FED_TRIBAL_GOV]
    assert derive_recognition_requirement_from_grant(grant) == "federal_required"


def test_tier3_title_only_stays_unknown_ac3() -> None:
    grant = {
        "grant_id": "ta3-title-only",
        "tier": 3,
        "opportunity_title": "Environmental Justice Grants",
        "eligibility_text": "",
        "synopsis": "Environmental Justice Grants program overview.",
    }
    bundle = derive_recognition_requirement_bundle(grant)
    assert bundle["recognition_requirement"] == "unknown"
    assert bundle["recognition_requirement_source"] == "unknown"


def test_conflict_gg_vs_rules_surfaces_unknown() -> None:
    grant = {
        "grant_id": "conflict-test",
        "opportunity_title": "USDA Community Facilities 10.766 Tribal",
        "opportunity_number": "10.766",
        "agency": "USDA Rural Development",
        "eligibility_text": (
            "Applicant types: Native American tribal governments (Federally recognized)"
        ),
        "sc_rule_category_id": "USDA_CF_TRIBAL",
    }
    rules = load_sc_eligibility_rules(require_files=False)
    bundle = derive_recognition_requirement_bundle(grant, rules=rules)
    assert bundle["recognition_requirement"] == "unknown"
    assert bundle["recognition_requirement_source"] == "conflict"
    assert bundle["recognition_requirement_conflict"] is True
    assert bundle["recognition_requirement_candidates"]["applicant_types"] == "federal_required"
    assert (
        bundle["recognition_requirement_candidates"]["rules"]
        == "federal_required_for_tribal_pathway"
    )


def test_no_applicant_types_prefix_regression_snapshot() -> None:
    snapshot = json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    baseline = snapshot["no_applicant_types_prefix_unchanged"]
    rules = load_sc_eligibility_rules(require_files=False)
    corpus = {g["grant_id"]: g for g in load_mixed_tier13_corpus()}
    for grant_id, expected in baseline.items():
        grant = corpus[grant_id]
        enriched = enrich_grant_with_eligibility_metadata(grant, rules=rules)
        assert enriched["recognition_requirement"] == expected, grant_id


def test_unknown_count_drops_ac1() -> None:
    rules = load_sc_eligibility_rules(require_files=False)
    corpus = load_mixed_tier13_corpus()
    enriched = [enrich_grant_with_eligibility_metadata(g, rules=rules) for g in corpus]
    unknowns = [g for g in enriched if g["recognition_requirement"] == "unknown"]
    assert len(unknowns) <= 45
    assert len(unknowns) < 57


def test_corpus_derived_regression_snapshot() -> None:
    """Regression: previously derived grants must not change (49-grant baseline)."""
    snapshot = json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    baseline = snapshot["all_derived_unchanged"]
    rules = load_sc_eligibility_rules(require_files=False)
    corpus = {g["grant_id"]: g for g in load_mixed_tier13_corpus()}
    mismatches = []
    for grant_id, expected in baseline.items():
        enriched = enrich_grant_with_eligibility_metadata(corpus[grant_id], rules=rules)
        actual = enriched["recognition_requirement"]
        if actual != expected:
            mismatches.append((grant_id, expected, actual, enriched.get("recognition_requirement_source")))
    assert not mismatches, mismatches


def test_infer_labels_from_tedc_fixture_style() -> None:
    labels = [
        "Native American tribal governments (Federally recognized)",
        "Native American tribal organizations (other than Federally recognized tribal governments)",
    ]
    assert infer_applicant_type_ids_from_labels(labels) == [TYPE_FED_TRIBAL_GOV, TYPE_NONFED_TRIBAL_ORG]
