"""Gate 174: eligibility intelligence.

Hermetic. No socket, no writes to the real database.

The four ways an eligibility layer hurts somebody, and the regressions that
keep each one out:

```text
yes when a disqualifier applies  -> three weeks wasted, then rejected
no when the block is obtainable  -> a fundable cycle abandoned
yes on an unanswered question    -> a claim nobody can defend
eligibility transferred between  -> a Tribe told to apply as something it
Native entity classes               is not
```

The last is the most specific to this product and the least likely to be
caught by a generic suite, so it has its own block.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

from nativeforge.services.eligibility_gold_corpus_service import (
    corpus,
    describe_corpus,
    run_corpus,
)
from nativeforge.services.eligibility_match_engine_service import (
    describe_match_engine,
    match_eligibility,
    match_invariant_failures,
)
from nativeforge.services.eligibility_requirement_model_service import (
    ADDRESSABLE_KINDS,
    APPLICANT_TYPE,
    CONDITIONALLY_ELIGIBLE,
    ELIGIBILITY_RESULTS,
    ELIGIBLE,
    EXCLUSION,
    INCLUSION,
    INELIGIBLE,
    LIKELY_ELIGIBLE,
    MATCHING_FUNDS,
    PURSUABLE,
    REGISTRATION,
    REVIEW_REQUIRED,
    STRUCTURAL_KINDS,
    UNKNOWN,
    build_requirement,
    describe_requirement_model,
    eligibility_transfers_between,
    expand_class_group,
    requirement_invariant_failures,
)
from nativeforge.services.organization_capability_profile_service import (
    ANSWERED,
    DOCUMENT_PROVIDED,
    PROFILE_FIELDS,
    SELF_DECLARED,
    UNANSWERED,
    VERIFIED_BY_AUTHORITY,
    blank_profile,
    build_profile,
    describe_profile_contract,
    field_is_answered,
    field_value,
    profile_invariant_failures,
)

REPO = pathlib.Path(__file__).resolve().parents[1]


def _req(kind: str, value: object, text: str, **kw: object) -> dict:
    base = dict(
        canonical_id="c1",
        requirement_kind=kind,
        normalized_value=value,
        original_text=text,
        raw_payload_sha256="payload",
        source_id="s1",
        evidence_ids=[f"ev.{kind.lower()}"],
    )
    base.update(kw)
    return build_requirement(**base)  # type: ignore[arg-type]


def _profile(**facts: object) -> dict:
    return build_profile(organization_id="org-1", facts=dict(facts))


# ============== the result is not a boolean ========================


def test_eligibility_is_not_a_boolean():
    model = describe_requirement_model()
    assert model["result_is_not_a_boolean"] is True
    assert len(ELIGIBILITY_RESULTS) == 6
    assert model["every_result_meaning_is_distinct"] is True


def test_unknown_is_not_eligible():
    """An unanswered question is not a yes."""
    assert UNKNOWN not in PURSUABLE
    assert REVIEW_REQUIRED not in PURSUABLE

    match = match_eligibility(
        canonical_id="c1",
        requirements=[
            _req(
                APPLICANT_TYPE,
                ["tribal_government"],
                "Indian tribes",
                applies_to_entity_classes=["tribal_government"],
            )
        ],
        profile=_profile(),  # nobody has been asked anything
    )
    assert match["eligibility_result"] == UNKNOWN
    assert match["eligibility_result"] not in PURSUABLE


# ============== negative requirements ==============================


def test_negative_requirements_are_first_class():
    """ "Tribes are excluded" is a row, not the absence of Tribes from a list."""
    assert EXCLUSION in (INCLUSION, EXCLUSION)
    assert describe_requirement_model()["negative_requirements_are_first_class"] is True


def test_a_hard_disqualifier_blocks_eligible():
    """An exclusion is not weighed against positives; it ends the question."""
    requirements = [
        _req(
            APPLICANT_TYPE,
            ["tribal_government"],
            "Indian tribes",
            applies_to_entity_classes=["tribal_government"],
        ),
        _req(MATCHING_FUNDS, True, "20% match"),
        _req(REGISTRATION, True, "SAM registration"),
        _req(
            APPLICANT_TYPE,
            ["tribal_government"],
            "Prior-year grantees are not eligible",
            polarity=EXCLUSION,
            applies_to_entity_classes=["tribal_government"],
        ),
    ]
    match = match_eligibility(
        canonical_id="c1",
        requirements=requirements,
        profile=_profile(
            entity_class="tribal_government",
            matching_funds_capability=True,
            sam_registration=True,
        ),
    )
    assert match["eligibility_result"] == INELIGIBLE
    assert match["applied_exclusions"]
    assert match_invariant_failures(match) == []


def test_an_ignored_exclusion_is_refused():
    match = match_eligibility(
        canonical_id="c1",
        requirements=[
            _req(
                APPLICANT_TYPE,
                ["tribal_government"],
                "Tribal governments are not eligible",
                polarity=EXCLUSION,
                applies_to_entity_classes=["tribal_government"],
            )
        ],
        profile=_profile(entity_class="tribal_government"),
    )
    forced = dict(match)
    forced["eligibility_result"] = ELIGIBLE
    failures = match_invariant_failures(forced)
    assert any("exclusion_applies_but_result_is" in f for f in failures), failures


# ============== structural vs addressable ==========================


def test_a_missing_match_capability_is_conditional_not_ineligible():
    """A cost-share gap can be closed before the deadline. Not being a Tribe

    cannot. Collapsing those into one "no" discards the actionable half.
    """
    match = match_eligibility(
        canonical_id="c1",
        requirements=[
            _req(
                APPLICANT_TYPE,
                ["tribal_government"],
                "Indian tribes",
                applies_to_entity_classes=["tribal_government"],
            ),
            _req(MATCHING_FUNDS, True, "A 20% non-federal match is required"),
        ],
        profile=_profile(
            entity_class="tribal_government", matching_funds_capability=False
        ),
    )
    assert match["eligibility_result"] == CONDITIONALLY_ELIGIBLE
    assert "MATCHING_FUNDS" in match["conditions_to_obtain"]
    assert match_invariant_failures(match) == []


def test_an_unanswered_match_capability_is_not_a_no():
    """Nobody asked. That is not the same as "cannot"."""
    match = match_eligibility(
        canonical_id="c1",
        requirements=[
            _req(
                APPLICANT_TYPE,
                ["tribal_government"],
                "Indian tribes",
                applies_to_entity_classes=["tribal_government"],
            ),
            _req(MATCHING_FUNDS, True, "A 20% match is required"),
        ],
        profile=_profile(entity_class="tribal_government"),
    )
    assert match["eligibility_result"] == LIKELY_ELIGIBLE
    assert match["unknown_requirements"]


def test_structural_and_addressable_kinds_are_disjoint():
    assert not (STRUCTURAL_KINDS & ADDRESSABLE_KINDS)


# ============== entity classes do not transfer =====================


@pytest.mark.parametrize(
    "applicant",
    ["tribal_enterprise", "tribal_college_or_university", "native_nonprofit"],
)
def test_naming_indian_tribes_does_not_name_another_native_class(applicant):
    """A notice for Indian tribes does not name a TCU or an enterprise.

    Telling a Tribe otherwise costs them a cycle and their standing with the
    funder.
    """
    assert not eligibility_transfers_between(
        named_class="tribal_government", applicant_class=applicant
    )
    match = match_eligibility(
        canonical_id="c1",
        requirements=[
            _req(
                APPLICANT_TYPE,
                ["tribal_government"],
                "Indian tribes",
                applies_to_entity_classes=["tribal_government"],
            )
        ],
        profile=_profile(entity_class=applicant),
    )
    assert match["eligibility_result"] == INELIGIBLE


def test_a_class_group_comes_from_source_language_not_inference():
    """Only phrases the SOURCE uses expand, and the lookup tolerates the

    spacing a source actually writes.
    """
    assert expand_class_group("tribal organizations") == [
        "native_nonprofit",
        "tribal_authority",
        "tribal_consortium",
        "tribal_government",
    ]
    assert expand_class_group("Indian Tribes") == ["tribal_government"]
    assert expand_class_group("something nobody wrote") == []


def test_tribal_entity_types_are_distinct():
    model = describe_requirement_model()
    assert model["entity_classes_do_not_transfer_by_default"] is True
    native = set(model["native_entity_classes"])
    assert {
        "tribal_government",
        "tribal_enterprise",
        "tribal_college_or_university",
    } <= native


# ============== evidence and original text =========================


def test_eligibility_requires_evidence():
    naked = _req(MATCHING_FUNDS, True, "20% match")
    stripped = dict(naked)
    stripped["evidence_ids"] = []
    stripped["raw_payload_sha256"] = None
    assert (
        "requirement_has_no_evidence_and_no_payload"
        in requirement_invariant_failures(stripped)
    )


def test_a_requirement_never_discards_the_funders_words():
    """Our normalization is a reading. The text is the fact, and only one of

    them survives a dispute with a programme officer.
    """
    good = _req(MATCHING_FUNDS, True, "A 20% non-federal match is required")
    assert requirement_invariant_failures(good) == []
    stripped = dict(good)
    stripped["original_text"] = None
    assert "requirement_discards_the_original_text" in requirement_invariant_failures(
        stripped
    )


def test_every_requirement_is_accounted_for():
    requirements = [
        _req(
            APPLICANT_TYPE,
            ["tribal_government"],
            "Indian tribes",
            applies_to_entity_classes=["tribal_government"],
        ),
        _req(MATCHING_FUNDS, True, "20% match"),
        _req(REGISTRATION, True, "SAM"),
    ]
    match = match_eligibility(
        canonical_id="c1",
        requirements=requirements,
        profile=_profile(entity_class="tribal_government"),
    )
    assert match["accounted_for"] == match["requirement_count"] == 3
    lost = dict(match)
    lost["requirement_count"] = 9
    assert any(
        "requirements_unaccounted_for" in f for f in match_invariant_failures(lost)
    )


# ============== the organization profile ===========================


def test_a_profile_field_defaults_to_unanswered_not_no():
    assert describe_profile_contract()["unanswered_is_not_no"] is True
    assert UNANSWERED not in ANSWERED
    blank = blank_profile()
    assert set(blank) == set(PROFILE_FIELDS)
    assert {entry["verification"] for entry in blank.values()} == {UNANSWERED}

    profile = _profile()
    assert field_value(profile, "matching_funds_capability") is None
    assert field_is_answered(profile, "matching_funds_capability") is False


def test_the_profile_is_versioned_from_its_content():
    one = _profile(entity_class="tribal_government")
    two = _profile(entity_class="tribal_government")
    three = _profile(entity_class="tribal_government", sam_registration=True)
    assert one["profile_version"] == two["profile_version"]
    assert one["profile_version"] != three["profile_version"]
    assert profile_invariant_failures(one) == []


def test_a_match_names_the_profile_version_it_used():
    """An eligibility answer is a claim about a moment."""
    profile = _profile(entity_class="tribal_government")
    match = match_eligibility(
        canonical_id="c1",
        requirements=[
            _req(
                APPLICANT_TYPE,
                ["tribal_government"],
                "Indian tribes",
                applies_to_entity_classes=["tribal_government"],
            )
        ],
        profile=profile,
    )
    assert match["profile_version"] == profile["profile_version"]
    unversioned = dict(match)
    unversioned["profile_version"] = None
    assert (
        "match_does_not_name_the_profile_version_it_used"
        in match_invariant_failures(unversioned)
    )


def test_gate174_cannot_verify_authority():
    """Gate 177 writes VERIFIED_BY_AUTHORITY. Nothing here may."""
    assert describe_profile_contract()["gate174_cannot_verify_authority"] == [
        VERIFIED_BY_AUTHORITY
    ]
    forged = build_profile(
        organization_id="org-1",
        facts={
            "federal_recognition": {
                "value": True,
                "verification": VERIFIED_BY_AUTHORITY,
            }
        },
    )
    failures = profile_invariant_failures(forged)
    assert any("gate174_produced_an_authority_verification" in f for f in failures)


def test_a_document_backed_fact_names_its_document():
    ok = build_profile(
        organization_id="org-1",
        facts={
            "sam_registration": {
                "value": True,
                "verification": DOCUMENT_PROVIDED,
                "evidence_ref": "doc-1",
            }
        },
    )
    assert profile_invariant_failures(ok) == []
    hollow = build_profile(
        organization_id="org-1",
        facts={"sam_registration": {"value": True, "verification": DOCUMENT_PROVIDED}},
    )
    assert any(
        "document_backed_field_names_no_document" in f
        for f in profile_invariant_failures(hollow)
    )


def test_a_self_declared_legal_status_is_flagged():
    """ "A Tribe told us it is federally recognised" and "an authority

    confirmed it" are different evidentiary positions.
    """
    match = match_eligibility(
        canonical_id="c1",
        requirements=[
            _req(
                "RECOGNITION_OR_DESIGNATION",
                True,
                "Applicant must be a federally recognized tribe",
            )
        ],
        profile=build_profile(
            organization_id="org-1",
            facts={
                "federal_recognition": {
                    "value": True,
                    "verification": SELF_DECLARED,
                }
            },
        ),
    )
    assert "legal_status_is_only_self_declared" in match["review_reasons"]


# ============== global vs tenant ===================================


def test_a_tenant_match_consumes_global_normalization():
    """Parsing per tenant means one NOFO producing a thousand readings that

    can drift apart.
    """
    match = match_eligibility(
        canonical_id="c1",
        requirements=[
            _req(
                APPLICANT_TYPE,
                ["tribal_government"],
                "Indian tribes",
                applies_to_entity_classes=["tribal_government"],
            )
        ],
        profile=_profile(entity_class="tribal_government"),
        tenant_id="tenant-1",
    )
    assert match["consumed_global_normalization"] is True
    assert match["reparsed_source_per_tenant"] is False

    reparsed = dict(match)
    reparsed["reparsed_source_per_tenant"] = True
    assert "match_reparsed_the_source_per_tenant" in match_invariant_failures(reparsed)
    assert describe_match_engine()["match_consumes_global_normalization"] is True


def test_the_same_opportunity_can_differ_by_tenant():
    """Which is the point of separating global parsing from the match."""
    requirements = [
        _req(
            APPLICANT_TYPE,
            ["tribal_government"],
            "Indian tribes",
            applies_to_entity_classes=["tribal_government"],
        ),
        _req(MATCHING_FUNDS, True, "20% match"),
    ]
    can = match_eligibility(
        canonical_id="c1",
        requirements=requirements,
        profile=build_profile(
            organization_id="a",
            facts={
                "entity_class": "tribal_government",
                "matching_funds_capability": True,
            },
        ),
        tenant_id="a",
    )
    cannot = match_eligibility(
        canonical_id="c1",
        requirements=requirements,
        profile=build_profile(
            organization_id="b",
            facts={
                "entity_class": "tribal_government",
                "matching_funds_capability": False,
            },
        ),
        tenant_id="b",
    )
    assert can["eligibility_result"] != cannot["eligibility_result"]


# ============== the instruments ====================================


def test_the_eligibility_corpus_feeds_the_real_engine():
    described = describe_corpus()
    assert described["no_row_states_its_own_answer"] is True
    assert described["keys_are_unique"] is True
    for row in corpus():
        assert "eligibility_result" not in row["facts"]


def test_the_eligibility_detector_can_fail():
    """A naive engine that ignores entity-class boundaries must score worse on

    the same rows, or the corpus is not measuring anything.
    """
    report = run_corpus()
    naive_hits = sum(
        1
        for row in report["results"]
        if ("tribe" in row["key"] or "native" in row["key"])
        == row["truth_is_pursuable"]
    )
    naive_accuracy = naive_hits / len(report["results"])
    assert report["result_accuracy"] > naive_accuracy


def test_the_eligibility_corpus_has_no_false_positives():
    """A false positive tells somebody to spend three weeks on an application

    they were never permitted to submit.
    """
    report = run_corpus()
    assert report["eligibility_false_positive_count"] == 0, report[
        "eligibility_false_positives"
    ]
    assert report["invariant_failures"] == []


def test_the_survey_distinguishes_a_naming_convention_from_a_capability():
    """Its first run reported four Stage 7 modules as spine-wired because they

    import the STAGE 6 relevance preview, which is itself unwired.
    """
    result = subprocess.run(  # noqa: S603
        [sys.executable, "scripts/_g174_survey_eligibility.py"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=600,
    )
    report = json.loads(
        [line for line in result.stdout.splitlines() if line.startswith("{")][-1]
    )
    assert report["survey_can_report_unknown"] is True
    assert report["existing_eligibility_is_unwired_from_canonical_graph"] is True
    assert report["stage7_consumes_an_unwired_stage6_preview"] is True
    assert report["network_attempts_during_this_phase"] == 0


def test_migration_0060_puts_the_two_rules_in_the_schema():
    text = (
        REPO / "alembic" / "versions" / "0060_eligibility_intelligence.py"
    ).read_text(encoding="utf-8")
    assert "excl_blocks_a_pursuable_result" in text
    assert "keeps_the_orig_text" in text
    assert "every_req_is_acct_for" in text
    assert "names_its_profile_version" in text
    assert "conditional_names_condition" in text
    assert "match_consumed_global" in text


def test_no_second_change_pipeline_was_built():
    """174J reuses Gate 170 rather than starting a parallel change engine."""
    services = REPO / "src" / "nativeforge" / "services"
    assert not list(services.glob("eligibility_change*.py"))
    assert (services / "opportunity_change_taxonomy_service.py").is_file()
