"""Gate 81 — NOFO text extraction, eligibility parsing, amendment detection.

Every fixture used here is synthetic and says so on its first line. Nothing in
this file fetches, and nothing asserts live coverage.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from nativeforge.services.eligibility_exclusion_evidence_service import (
    APPLICANT_CLASSES,
    all_classes_invariant_failures,
    evaluate_all_applicant_classes,
    evaluate_applicant_class,
    exclusion_invariant_failures,
)
from nativeforge.services.native_opportunity_discovery_service import (
    build_native_opportunity_record,
    opportunity_record_invariant_failures,
)
from nativeforge.services.nofo_amendment_detector_service import (
    CURRENT_NOTICE_STATUSES,
    EVIDENCE_REQUIRED_STATUSES,
    FRESHNESS_PROJECTION,
    NON_CURRENT_NOTICE_STATUSES,
    NOTICE_STATUSES,
    amendment_invariant_failures,
    detect_notice_status,
    evaluate_notice_supersession,
)
from nativeforge.services.nofo_eligibility_parser_service import (
    NON_NATIVE_CLASSES,
    PARSER_APPLICANT_CLASSES,
    parse_nofo_eligibility,
    parser_invariant_failures,
)
from nativeforge.services.nofo_text_extraction_service import (
    ELIGIBILITY_CONTEXT_KINDS,
    detect_sections,
    extract_dates,
    extract_nofo_text,
    extraction_invariant_failures,
    normalise_with_offsets,
)
from nativeforge.services.opportunity_discovery_quality_service import (
    build_discovery_quality_score,
    discovery_quality_invariant_failures,
)
from nativeforge.services.opportunity_freshness_service import (
    CURRENT_STATES,
    FRESHNESS_STATES,
    evaluate_opportunity_freshness,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "nofo_text"

FIXTURE_NAMES = (
    "federal_recognition_only_nofo.txt",
    "state_recognized_allowed_nofo.txt",
    "bie_school_only_nofo.txt",
    "federal_trust_land_restriction_nofo.txt",
    "deadline_extended_amendment_nofo.txt",
    "cancelled_notice_nofo.txt",
    "ambiguous_native_relevance_nofo.txt",
)


def _text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _extract(name: str, **kwargs):
    return extract_nofo_text(
        notice_id=name.removesuffix(".txt"),
        source_id="synthetic-source",
        notice_url=f"https://example.test/{name}",
        raw_text=_text(name),
        **kwargs,
    )


def _parse(name: str, **kwargs):
    extraction = _extract(name, **kwargs)
    return parse_nofo_eligibility(
        opportunity_id=name.removesuffix(".txt"),
        extraction=extraction,
        raw_text=_text(name),
    )


# --------------------------------------------------------------------------
# Fixtures are synthetic
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_every_fixture_declares_itself_synthetic(name: str) -> None:
    head = _text(name).splitlines()[0].upper()
    assert "SYNTHETIC" in head
    assert "NOT A REAL NOTICE" in head


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_no_fixture_claims_a_real_opportunity_number(name: str) -> None:
    body = _text(name).lower()
    assert "no opportunity number is claimed" in body
    # Grants.gov-style identifiers would read as a real notice.
    for marker in ("hhs-", "usda-", "doe-", "epa-", "hud-", "bia-", "ihs-"):
        assert marker not in body, f"{name} looks like it names a real programme"


def test_all_seven_fixtures_exist() -> None:
    assert sorted(p.name for p in FIXTURES.glob("*.txt")) == sorted(FIXTURE_NAMES)


# --------------------------------------------------------------------------
# 81B — extraction
# --------------------------------------------------------------------------


def test_no_raw_text_blocks_extraction() -> None:
    for empty in (None, "", "   \n\t  "):
        result = extract_nofo_text(notice_id="n1", raw_text=empty)
        assert result["extraction_status"] == "blocked"
        assert "no_raw_text" in result["blocked_reasons"]
        assert result["raw_text_present"] is False
        assert result["human_review_required"] is True
        assert extraction_invariant_failures(result) == []


def test_blocked_extraction_produces_no_evidence() -> None:
    result = extract_nofo_text(notice_id="n1", raw_text=None)
    assert result["evidence_quotes"] == []
    assert result["eligibility_sections"] == []
    assert result["eligibility_text"] is None


def test_missing_raw_text_cannot_be_reported_as_extracted() -> None:
    forged = extract_nofo_text(notice_id="n1", raw_text=None)
    forged["extraction_status"] = "extracted"
    assert "missing_raw_text_did_not_block" in extraction_invariant_failures(forged)


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_extraction_invariants_hold_for_every_fixture(name: str) -> None:
    assert extraction_invariant_failures(_extract(name)) == []


def test_every_evidence_quote_carries_a_span_and_text() -> None:
    result = _extract("federal_trust_land_restriction_nofo.txt")
    assert result["evidence_quotes"]
    for q in result["evidence_quotes"]:
        assert q["end"] > q["start"] >= 0
        assert q["quote"].strip()


def test_spans_point_at_the_real_text() -> None:
    name = "federal_recognition_only_nofo.txt"
    raw = _text(name)
    result = _extract(name)
    section = result["eligibility_sections"][0]
    assert "federally recognized" in raw[section["start"] : section["end"]].lower()


def test_headings_split_sections_so_purpose_prose_stays_out_of_eligibility() -> None:
    result = _extract("federal_recognition_only_nofo.txt")
    kinds = [s["kind"] for s in result["sections"]]
    assert "eligibility" in kinds
    elig = [s for s in result["sections"] if s["kind"] == "eligibility"][0]
    raw = _text("federal_recognition_only_nofo.txt")
    body = raw[elig["start"] : elig["end"]].lower()
    # The PROGRAM PURPOSE paragraph must not have leaked in.
    assert "identified infrastructure needs" not in body


def test_a_wrapped_prose_line_is_not_treated_as_a_heading() -> None:
    text = (
        "OVERVIEW\n\n"
        "This programme serves many communities across the whole region and\n"
        "beyond, including several described below.\n\n"
        "ELIGIBILITY INFORMATION\n\n"
        "Eligible applicants are federally recognized tribes.\n"
    )
    sections = detect_sections(text)
    headings = [s["heading"] for s in sections if s["heading"]]
    assert "ELIGIBILITY INFORMATION" in headings
    assert not any(h.startswith("This programme serves") for h in headings)
    assert not any(h.startswith("beyond, including") for h in headings)


# --------------------------------------------------------------------------
# Keyword-only behaviour
# --------------------------------------------------------------------------


def test_tribal_keyword_outside_eligibility_gives_no_eligibility_credit() -> None:
    name = "ambiguous_native_relevance_nofo.txt"
    extraction = _extract(name)
    tribal = [
        m for m in extraction["bare_keyword_mentions"] if m["phrase"] == "tribal"
    ]
    assert tribal, "fixture should mention tribal in the purpose section"
    assert all(not m["in_eligibility_context"] for m in tribal)

    parsed = _parse(name)
    assert "federally_recognized_tribe" not in parsed["named_classes"]
    assert "tribal_organization" not in parsed["named_classes"]
    assert parsed["eligible_classes"] == []


def test_native_keyword_outside_eligibility_gives_no_eligibility_credit() -> None:
    extraction = _extract("ambiguous_native_relevance_nofo.txt")
    native = [
        m
        for m in extraction["bare_keyword_mentions"]
        if m["phrase"] in {"native", "american indian", "alaska native"}
    ]
    assert native
    assert all(not m["in_eligibility_context"] for m in native)
    assert extraction["keyword_counted_as_eligibility"] is False


def test_out_of_context_mention_cannot_be_recorded_as_eligibility() -> None:
    result = _extract("ambiguous_native_relevance_nofo.txt")
    forged = dict(result)
    forged["applicant_class_mentions"] = [
        {
            "phrase": "tribal",
            "start": 1,
            "end": 7,
            "section_kind": "other",
            "in_eligibility_context": False,
        }
    ]
    failures = extraction_invariant_failures(forged)
    assert any(
        f.startswith("out_of_context_mention_recorded_as_eligibility") for f in failures
    )


def test_only_eligibility_sections_feed_the_parser() -> None:
    extraction = _extract("ambiguous_native_relevance_nofo.txt")
    assert ELIGIBILITY_CONTEXT_KINDS == frozenset({"eligibility"})
    elig = (extraction["eligibility_text"] or "").lower()
    assert "units of local government" in elig
    assert "prior planning efforts" not in elig


# --------------------------------------------------------------------------
# 81C — eligibility parsing
# --------------------------------------------------------------------------


def test_federally_recognized_only_supports_that_class() -> None:
    parsed = _parse("federal_recognition_only_nofo.txt")
    assert parsed["named_classes"] == ["federally_recognized_tribe"]
    assert "federally_recognized_tribe" in parsed["eligible_classes"]
    assert parser_invariant_failures(parsed) == []


def test_federally_recognized_only_excludes_state_recognized_when_exclusive() -> None:
    parsed = _parse("federal_recognition_only_nofo.txt")
    assert parsed["exclusivity_markers_present"] is True
    assert "state_recognized_tribe" in parsed["excluded_classes"]
    assert "state_recognized_tribe" not in parsed["eligible_classes"]


def test_state_recognized_text_supports_state_recognized() -> None:
    parsed = _parse("state_recognized_allowed_nofo.txt")
    assert "state_recognized_tribe" in parsed["named_classes"]
    assert "state_recognized_tribe" in parsed["eligible_classes"]
    assert parsed["excluded_classes"] == []


def test_the_two_recognition_tiers_are_not_collapsed() -> None:
    only_federal = _parse("federal_recognition_only_nofo.txt")
    both = _parse("state_recognized_allowed_nofo.txt")
    assert "state_recognized_tribe" in only_federal["excluded_classes"]
    assert "state_recognized_tribe" in both["eligible_classes"]


def test_bie_schools_do_not_imply_tribal_government_eligibility() -> None:
    parsed = _parse("bie_school_only_nofo.txt")
    assert parsed["named_classes"] == ["bie_funded_school"]
    assert "bie_funded_school" in parsed["eligible_classes"]
    assert "federally_recognized_tribe" not in parsed["eligible_classes"]
    assert "federally_recognized_tribe" in parsed["excluded_classes"]


def test_tribal_organization_is_not_a_tribal_government() -> None:
    text = (
        "ELIGIBILITY INFORMATION\n\n"
        "Eligibility is limited to tribal organizations.\n"
    )
    extraction = extract_nofo_text(
        notice_id="n", notice_url="https://example.test/n", raw_text=text
    )
    parsed = parse_nofo_eligibility(
        opportunity_id="n", extraction=extraction, raw_text=text
    )
    assert "tribal_organization" in parsed["eligible_classes"]
    assert "federally_recognized_tribe" not in parsed["eligible_classes"]


def test_federal_trust_land_is_preserved_as_a_restriction() -> None:
    parsed = _parse("federal_trust_land_restriction_nofo.txt")
    assert "federal_trust_land" in parsed["restriction_names"]
    for r in parsed["restrictions"]:
        assert r["is_eligibility_rule"] is False
        assert r["end"] > r["start"]
        assert r["quote"].strip()
    assert parsed["restriction_counted_as_eligibility"] is False
    # A land-use condition must not remove the class the text admits.
    assert "federally_recognized_tribe" in parsed["eligible_classes"]


def test_a_restriction_cannot_be_promoted_to_an_eligibility_rule() -> None:
    parsed = _parse("federal_trust_land_restriction_nofo.txt")
    forged = dict(parsed)
    forged["restrictions"] = [
        {**parsed["restrictions"][0], "is_eligibility_rule": True}
    ]
    failures = parser_invariant_failures(forged)
    assert any(f.startswith("restriction_promoted_to_eligibility") for f in failures)


def test_exclusion_requires_a_citation() -> None:
    text = _text("federal_recognition_only_nofo.txt")
    extraction = extract_nofo_text(notice_id="n", raw_text=text)  # no urls at all
    parsed = parse_nofo_eligibility(
        opportunity_id="n", extraction=extraction, raw_text=text
    )
    assert parsed["has_citation"] is False
    assert parsed["excluded_classes"] == []
    assert "no_citable_reference_for_this_notice" in parsed["review_reasons"]
    assert parsed["human_review_required"] is True
    assert parser_invariant_failures(parsed) == []


def test_uncited_exclusion_is_an_invariant_failure() -> None:
    parsed = _parse("federal_recognition_only_nofo.txt")
    forged = dict(parsed)
    forged["has_citation"] = False
    forged["evidence_reference"] = None
    assert "exclusion_without_citation" in parser_invariant_failures(forged)


def test_absence_of_a_class_is_not_exclusion_without_an_exclusive_list() -> None:
    text = (
        "ELIGIBILITY INFORMATION\n\n"
        "Eligible applicants include federally recognized tribes.\n"
    )
    extraction = extract_nofo_text(
        notice_id="n", notice_url="https://example.test/n", raw_text=text
    )
    parsed = parse_nofo_eligibility(
        opportunity_id="n", extraction=extraction, raw_text=text
    )
    assert parsed["exclusivity_markers_present"] is False
    assert parsed["excluded_classes"] == []
    per_class = parsed["exclusion_result"]["per_class"]["state_recognized_tribe"]
    assert per_class["result_state"] == "not_supported_by_evidence"


def test_ambiguous_eligibility_requires_human_review() -> None:
    text = (
        "ELIGIBILITY INFORMATION\n\n"
        "Eligibility is limited to entities described in Appendix C.\n"
    )
    extraction = extract_nofo_text(
        notice_id="n", notice_url="https://example.test/n", raw_text=text
    )
    parsed = parse_nofo_eligibility(
        opportunity_id="n", extraction=extraction, raw_text=text
    )
    assert parsed["human_review_required"] is True
    assert "exclusive_list_names_no_recognised_class" in parsed["review_reasons"]
    assert parsed["excluded_classes"] == []


def test_a_class_named_and_negated_is_a_conflict_needing_review() -> None:
    text = (
        "ELIGIBILITY INFORMATION\n\n"
        "Eligible applicants include federally recognized tribes.\n"
        "For the supplemental award, federally recognized tribes are not "
        "eligible.\n"
    )
    extraction = extract_nofo_text(
        notice_id="n", notice_url="https://example.test/n", raw_text=text
    )
    parsed = parse_nofo_eligibility(
        opportunity_id="n", extraction=extraction, raw_text=text
    )
    assert "federally_recognized_tribe" in parsed["conflicting_classes"]
    assert parsed["human_review_required"] is True
    assert parser_invariant_failures(parsed) == []


def test_conflict_cannot_resolve_itself_without_review() -> None:
    parsed = _parse("federal_recognition_only_nofo.txt")
    forged = dict(parsed)
    forged["conflicting_classes"] = ["federally_recognized_tribe"]
    forged["human_review_required"] = False
    assert "conflicting_classes_without_human_review" in parser_invariant_failures(
        forged
    )


def test_explicit_negation_excludes_rather_than_admits() -> None:
    """The failure mode this closes: the class is *named*, so naive matching
    reads it as eligible when the sentence says the opposite."""
    text = "Federally recognized tribes are not eligible under this program."
    verdict = evaluate_applicant_class(
        opportunity_id="n",
        applicant_class="federally_recognized_tribe",
        eligibility_text=text,
        evidence_reference="https://example.test/n",
        negated_classes=["federally_recognized_tribe"],
    )
    assert verdict["result_state"] == "excluded_by_evidence"
    assert verdict["negated"] is True
    assert exclusion_invariant_failures(verdict) == []


def test_negation_without_a_citation_goes_to_human_review() -> None:
    verdict = evaluate_applicant_class(
        opportunity_id="n",
        applicant_class="federally_recognized_tribe",
        eligibility_text="Federally recognized tribes are not eligible.",
        negated_classes=["federally_recognized_tribe"],
    )
    assert verdict["result_state"] == "human_review_required"
    assert verdict["excluded"] is False


def test_non_native_exclusive_list_can_exclude_native_classes() -> None:
    """Before Gate 81 this list named nothing the exclusion service knew, so it
    did not register as exclusive and tribes came back unsupported."""
    parsed = _parse("ambiguous_native_relevance_nofo.txt")
    assert parsed["additional_named_classes"] == ["local_government"]
    for cls in ("federally_recognized_tribe", "state_recognized_tribe"):
        assert cls in parsed["excluded_classes"]
    assert parsed["eligible_classes"] == []
    assert parser_invariant_failures(parsed) == []


def test_additional_named_classes_cannot_manufacture_eligibility() -> None:
    verdict = evaluate_applicant_class(
        opportunity_id="n",
        applicant_class="federally_recognized_tribe",
        eligibility_text="Eligibility is limited to units of local government.",
        evidence_reference="https://example.test/n",
        additional_named_classes=["local_government"],
    )
    assert verdict["result_state"] == "excluded_by_evidence"
    assert "federally_recognized_tribe" not in verdict["named_classes"]
    assert verdict["additional_named_classes"] == ["local_government"]


def test_whitespace_wrapped_phrases_are_still_found() -> None:
    text = (
        "ELIGIBILITY INFORMATION\n\n"
        "Eligible applicants are federally recognized\ntribes.\n"
    )
    extraction = extract_nofo_text(
        notice_id="n", notice_url="https://example.test/n", raw_text=text
    )
    parsed = parse_nofo_eligibility(
        opportunity_id="n", extraction=extraction, raw_text=text
    )
    assert "federally_recognized_tribe" in parsed["named_classes"]


def test_normalise_with_offsets_maps_back_to_real_positions() -> None:
    raw = "Eligible:  federally   recognized\ntribes."
    norm, idx = normalise_with_offsets(raw)
    assert "federally recognized tribes" in norm
    start = norm.index("federally")
    assert raw[idx[start] : idx[start] + 9] == "federally"


def test_every_mention_carries_a_valid_span() -> None:
    parsed = _parse("state_recognized_allowed_nofo.txt")
    raw = _text("state_recognized_allowed_nofo.txt")
    assert parsed["class_mentions"]
    for m in parsed["class_mentions"]:
        assert m["end"] > m["start"] >= 0
        assert raw[m["start"] : m["end"]].lower().replace("\n", " ") != ""


def test_blocked_extraction_blocks_the_parser() -> None:
    extraction = extract_nofo_text(notice_id="n", raw_text=None)
    parsed = parse_nofo_eligibility(opportunity_id="n", extraction=extraction)
    assert parsed["parse_status"] == "blocked"
    assert parsed["excluded_classes"] == []
    assert parsed["human_review_required"] is True
    assert parser_invariant_failures(parsed) == []


def test_parser_never_asserts_universal_ineligibility() -> None:
    for name in FIXTURE_NAMES:
        parsed = _parse(name)
        assert parsed["not_eligible_asserted"] is False


# --------------------------------------------------------------------------
# Vocabulary drift
# --------------------------------------------------------------------------


def test_parser_vocabulary_is_a_superset_not_a_fork() -> None:
    assert APPLICANT_CLASSES < PARSER_APPLICANT_CLASSES
    assert PARSER_APPLICANT_CLASSES - APPLICANT_CLASSES == NON_NATIVE_CLASSES
    assert len(PARSER_APPLICANT_CLASSES) == 12


def test_non_native_classes_never_reach_the_exclusion_contract() -> None:
    parsed = _parse("ambiguous_native_relevance_nofo.txt")
    for cls in parsed["excluded_classes"] + parsed["eligible_classes"]:
        assert cls in APPLICANT_CLASSES
    assert all_classes_invariant_failures(parsed["exclusion_result"]) == []


def test_a_non_canonical_class_in_the_exclusion_result_fails() -> None:
    parsed = _parse("ambiguous_native_relevance_nofo.txt")
    forged = dict(parsed)
    forged["excluded_classes"] = ["local_government"]
    failures = parser_invariant_failures(forged)
    assert "non_canonical_class_in_exclusion_result:local_government" in failures


def test_notice_status_vocabulary_is_the_single_declared_set() -> None:
    assert NOTICE_STATUSES == frozenset(
        {
            "original",
            "amended",
            "corrected",
            "supplemented",
            "extended",
            "cancelled",
            "withdrawn",
            "superseded",
            "unknown",
        }
    )
    assert CURRENT_NOTICE_STATUSES | NON_CURRENT_NOTICE_STATUSES == NOTICE_STATUSES
    assert not (CURRENT_NOTICE_STATUSES & NON_CURRENT_NOTICE_STATUSES)


def test_freshness_projection_stays_inside_the_freshness_vocabulary() -> None:
    for status, projected in FRESHNESS_PROJECTION.items():
        assert status in NOTICE_STATUSES
        assert projected is None or projected in FRESHNESS_STATES


def test_no_dead_notice_projects_onto_a_current_freshness_state() -> None:
    for status in NON_CURRENT_NOTICE_STATUSES:
        assert FRESHNESS_PROJECTION[status] not in CURRENT_STATES


# --------------------------------------------------------------------------
# 81D — amendment / version detection
# --------------------------------------------------------------------------


def test_extended_deadline_produces_extended_status_with_evidence() -> None:
    name = "deadline_extended_amendment_nofo.txt"
    detection = detect_notice_status(
        notice_id=name,
        raw_text=_text(name),
        extraction=_extract(name),
        notice_url=f"https://example.test/{name}",
    )
    assert detection["notice_status"] == "extended"
    assert detection["status_evidence"]
    assert detection["status_evidence"][0]["quote"].strip()
    assert detection["projected_freshness_state"] == "amended"
    assert detection["is_current_notice"] is True
    assert detection["extension_evidence"][0]["kind"] == "amendment_notice_url"
    assert amendment_invariant_failures(detection) == []


def test_version_label_is_detected() -> None:
    name = "deadline_extended_amendment_nofo.txt"
    detection = detect_notice_status(notice_id=name, raw_text=_text(name))
    assert detection["version_label"] == "2"
    assert detection["version_evidence"]["end"] > detection["version_evidence"]["start"]


def test_declared_version_wins_over_parsed_version() -> None:
    name = "deadline_extended_amendment_nofo.txt"
    detection = detect_notice_status(
        notice_id=name, raw_text=_text(name), declared_version="7"
    )
    assert detection["version_label"] == "7"


def test_no_evidence_means_unknown_not_amended() -> None:
    detection = detect_notice_status(notice_id="n", raw_text=None)
    assert detection["notice_status"] == "unknown"
    assert detection["status_evidence"] == []
    assert detection["is_current_notice"] is False
    assert amendment_invariant_failures(detection) == []


def test_amendment_asserted_without_evidence_is_an_invariant_failure() -> None:
    detection = detect_notice_status(notice_id="n", raw_text=None)
    forged = dict(detection)
    forged["notice_status"] = "amended"
    failures = amendment_invariant_failures(forged)
    assert "status_asserted_without_evidence:amended" in failures


def test_a_plain_notice_is_original() -> None:
    detection = detect_notice_status(
        notice_id="n", raw_text=_text("federal_recognition_only_nofo.txt")
    )
    assert detection["notice_status"] == "original"
    assert detection["is_current_notice"] is True
    assert detection["projected_freshness_state"] is None


def test_cancelled_notice_remains_visible_and_not_current() -> None:
    name = "cancelled_notice_nofo.txt"
    detection = detect_notice_status(
        notice_id=name, raw_text=_text(name), extraction=_extract(name)
    )
    assert detection["notice_status"] == "cancelled"
    assert detection["visible"] is True
    assert detection["is_current_notice"] is False
    assert detection["projected_freshness_state"] not in CURRENT_STATES
    assert detection["projection_lossy"] is True
    assert detection["cancelled_notice_hidden"] is False
    assert amendment_invariant_failures(detection) == []


def test_cancellation_outranks_an_amendment_cue() -> None:
    text = (
        "NOTICE OF CANCELLATION\n\n"
        "This notice is amended. This notice is cancelled and no awards will be "
        "made.\n"
    )
    detection = detect_notice_status(notice_id="n", raw_text=text)
    assert detection["notice_status"] == "cancelled"


def test_hiding_a_cancelled_notice_is_an_invariant_failure() -> None:
    name = "cancelled_notice_nofo.txt"
    detection = detect_notice_status(notice_id=name, raw_text=_text(name))
    forged = dict(detection)
    forged["visible"] = False
    assert "notice_hidden_instead_of_marked" in amendment_invariant_failures(forged)


def test_a_dead_notice_cannot_be_reported_as_current() -> None:
    name = "cancelled_notice_nofo.txt"
    detection = detect_notice_status(notice_id=name, raw_text=_text(name))
    forged = dict(detection)
    forged["is_current_notice"] = True
    failures = amendment_invariant_failures(forged)
    assert "non_current_status_reported_as_current:cancelled" in failures


def test_withdrawn_notice_stays_visible_and_non_current() -> None:
    text = "NOTICE OF WITHDRAWAL\n\nThis notice is withdrawn.\n"
    detection = detect_notice_status(notice_id="n", raw_text=text)
    assert detection["notice_status"] == "withdrawn"
    assert detection["visible"] is True
    assert detection["is_current_notice"] is False
    assert amendment_invariant_failures(detection) == []


def test_evidence_required_statuses_are_the_ones_that_matter() -> None:
    assert "amended" in EVIDENCE_REQUIRED_STATUSES
    assert "extended" in EVIDENCE_REQUIRED_STATUSES
    assert "cancelled" in EVIDENCE_REQUIRED_STATUSES
    assert "original" not in EVIDENCE_REQUIRED_STATUSES


# --------------------------------------------------------------------------
# Supersession
# --------------------------------------------------------------------------


_OLDER = {
    "opportunity_id": "syn-1",
    "source_id": "s1",
    "agency_or_funder": "Synthetic Agency",
    "title": "Example Program",
}
_NEWER = {
    "opportunity_id": "syn-2",
    "source_id": "s1",
    "agency_or_funder": "Synthetic Agency",
    "title": "Example Program",
}


def test_supersession_requires_evidence() -> None:
    result = evaluate_notice_supersession(older=_OLDER, newer=_NEWER)
    assert result["supersession"]["supersedes"] is False


def test_supersession_with_evidence_is_delegated_and_accepted() -> None:
    text = "This notice supersedes the prior announcement.\n"
    detection = detect_notice_status(
        notice_id="syn-2", raw_text=text, notice_url="https://example.test/syn-2"
    )
    assert detection["notice_status"] == "superseded"
    result = evaluate_notice_supersession(
        older=_OLDER, newer=_NEWER, detection=detection
    )
    assert result["evidence_supplied"]
    assert result["supersession"]["supersedes"] is True
    assert result["delegated_to"].endswith("evaluate_supersession")


def test_same_title_alone_does_not_supersede() -> None:
    result = evaluate_notice_supersession(
        older=_OLDER,
        newer=_NEWER,
        evidence=[{"kind": "same_title", "reference": "x"}],
    )
    assert result["supersession"]["supersedes"] is False


def test_older_version_remains_visible_as_superseded() -> None:
    text = "This notice supersedes the prior announcement.\n"
    detection = detect_notice_status(
        notice_id="syn-2", raw_text=text, notice_url="https://example.test/syn-2"
    )
    result = evaluate_notice_supersession(
        older=_OLDER, newer=_NEWER, detection=detection
    )
    assert result["older_remains_visible"] is True
    assert result["older_status_if_superseded"] == "superseded"
    assert "superseded" not in CURRENT_STATES


# --------------------------------------------------------------------------
# Deadlines and freshness
# --------------------------------------------------------------------------


def test_missing_close_date_becomes_unknown_freshness() -> None:
    extraction = _extract("state_recognized_allowed_nofo.txt")
    assert extraction["close_date"] is None
    assert extraction["close_date_certain"] is False
    assert "no_close_date_supplied" in extraction["blocked_reasons"]

    freshness = evaluate_opportunity_freshness(
        opportunity_id="n",
        close_date=None,
        last_checked_at="2026-08-24T00:00:00Z",
        now="2026-08-24T00:00:00Z",
    )
    assert freshness["freshness_state"] == "unknown"
    assert freshness["freshness_state"] not in {"fresh"}


def test_a_parsed_date_is_never_promoted_to_the_close_date() -> None:
    extraction = _extract("state_recognized_allowed_nofo.txt")
    assert extraction["dates_found"], "fixture carries a date in its deadline section"
    assert extraction["close_date"] is None
    assert extraction["close_date_certain"] is False


def test_missing_close_date_cannot_be_claimed_certain() -> None:
    extraction = _extract("state_recognized_allowed_nofo.txt")
    forged = dict(extraction)
    forged["close_date_certain"] = True
    assert "missing_close_date_claimed_certain" in extraction_invariant_failures(forged)


def test_date_precision_is_preserved() -> None:
    dates = extract_dates("Applications are due March 2027 at the latest.")
    assert dates[0]["precision"] == "month"
    assert dates[0]["certain"] is False


def test_hedged_dates_are_not_certain() -> None:
    dates = extract_dates("Awards will be made on or about March 15, 2027.")
    assert dates[0]["value"] == "2027-03-15"
    assert dates[0]["uncertainty_markers"] == ["on or about"]
    assert dates[0]["certain"] is False


def test_a_firm_day_date_is_certain() -> None:
    dates = extract_dates("Applications are due March 15, 2027.")
    assert dates[0]["certain"] is True


def test_a_hedged_date_claimed_certain_is_an_invariant_failure() -> None:
    extraction = _extract("federal_trust_land_restriction_nofo.txt")
    forged = dict(extraction)
    forged["dates_found"] = [
        {
            "value": "2027-11",
            "precision": "month",
            "raw": "November 2027",
            "start": 1,
            "end": 14,
            "uncertainty_markers": ["on or about"],
            "certain": True,
        }
    ]
    failures = extraction_invariant_failures(forged)
    assert any(f.startswith("hedged_date_claimed_certain") for f in failures)


def test_parser_confidence_is_not_eligibility_confidence() -> None:
    extraction = _extract("federal_recognition_only_nofo.txt")
    assert extraction["parser_confidence"] in {"low", "medium", "high"}
    assert extraction["eligibility_confidence"] == "none"
    assert extraction["parser_confidence_used_as_eligibility_confidence"] is False


# --------------------------------------------------------------------------
# End to end into discovery and scoring
# --------------------------------------------------------------------------


def _record_for(name: str):
    parsed = _parse(name)
    record = build_native_opportunity_record(
        opportunity_id=name.removesuffix(".txt"),
        source_id="synthetic-source",
        title="Synthetic Example",
        agency_or_funder="Synthetic Agency",
        funding_geography="federal",
        native_relevance_evidence=[{"kind": "eligibility_text", "reference": "x"}],
        eligibility_evidence=[{"kind": "notice_text", "reference": "x"}],
        recognition_routing_tags=["federally_recognized"],
        provenance_url="https://example.test/x",
        exclusion_result=parsed["exclusion_result"],
    )
    return parsed, record


def test_excluded_opportunity_stays_visible_in_the_discovery_record() -> None:
    _parsed, record = _record_for("federal_recognition_only_nofo.txt")
    assert "state_recognized_tribe" in record["excluded_classes"]
    assert record["visible"] is True
    assert opportunity_record_invariant_failures(record) == []


def test_excluded_class_loses_eligible_coverage_but_stays_counted() -> None:
    _parsed, record = _record_for("federal_recognition_only_nofo.txt")
    opportunity = {
        **record,
        "duplicate_of": None,
        "eligibility_evidence": "cited",
        "eligibility_state": "eligible",
        "source_id": "s1",
        "source_url": "https://example.test/x",
        "extraction_timestamp": "2026-08-24T00:00:00Z",
        "recognition_tier": "federally_recognized",
        "native_relevance_evidence": "cited",
    }
    coverage = {"source_freshness_score": 1.0}

    excluded_view = build_discovery_quality_score(
        opportunities=[opportunity],
        coverage=coverage,
        applicant_class="state_recognized_tribe",
    )
    eligible_view = build_discovery_quality_score(
        opportunities=[opportunity],
        coverage=coverage,
        applicant_class="federally_recognized_tribe",
    )

    assert excluded_view["eligibility_evidence_score"] == 0.0
    assert excluded_view["negative_intelligence_count"] == 1
    assert eligible_view["eligibility_evidence_score"] == 1.0
    assert eligible_view["negative_intelligence_count"] == 0

    # Visible in both: raw and unique counts never move.
    assert excluded_view["opportunity_count_raw"] == 1
    assert excluded_view["opportunity_count_unique"] == 1
    assert excluded_view["excluded_counted_as_eligible_coverage"] is False
    assert discovery_quality_invariant_failures(excluded_view) == []
    assert discovery_quality_invariant_failures(eligible_view) == []


def test_the_full_chain_runs_from_text_to_scored_coverage() -> None:
    """The customer answer this gate exists to produce."""
    name = "ambiguous_native_relevance_nofo.txt"
    extraction = _extract(name)
    parsed = _parse(name)

    assert extraction["extraction_status"] == "extracted"
    # Native words appear, but only outside the eligibility section.
    assert extraction["bare_keyword_mentions"]
    assert parsed["eligible_classes"] == []
    assert "federally_recognized_tribe" in parsed["excluded_classes"]
    # And the exclusion carries the sentence that caused it.
    verdict = parsed["exclusion_result"]["per_class"]["federally_recognized_tribe"]
    assert verdict["result_state"] == "excluded_by_evidence"
    assert verdict["has_citation"] is True


# --------------------------------------------------------------------------
# Claim boundaries
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_no_live_fetch_is_ever_claimed(name: str) -> None:
    extraction = _extract(name)
    parsed = _parse(name)
    detection = detect_notice_status(notice_id=name, raw_text=_text(name))
    assert extraction["live_fetch_performed"] is False
    assert parsed["live_fetch_performed"] is False
    assert detection["live_fetch_performed"] is False


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_no_coverage_or_freshness_is_claimed(name: str) -> None:
    extraction = _extract(name)
    parsed = _parse(name)
    assert extraction["freshness_claimed"] is False
    assert parsed["coverage_claimed"] is False


def test_no_gate81_module_claims_live_coverage_or_an_improvement() -> None:
    services = ROOT / "src" / "nativeforge" / "services"
    for fname in (
        "nofo_text_extraction_service.py",
        "nofo_eligibility_parser_service.py",
        "nofo_amendment_detector_service.py",
    ):
        body = (services / fname).read_text(encoding="utf-8").lower()
        assert "65%" not in body
        assert "live coverage" not in body
        for banned in ("requests.", "httpx.", "urllib.request", "aiohttp"):
            assert banned not in body, f"{fname} must not reach the network"


def test_readiness_doc_still_claims_no_coverage() -> None:
    doc = ROOT / "docs" / "operations" / "453_GATE81_PRODUCTION_READINESS_DELTA.md"
    body = doc.read_text(encoding="utf-8")
    assert "Live SC source coverage:   NONE" in body
    assert "65% improvement:           NOT CLAIMED" in body
    assert "Controlled customer pilot: NO_GO" in body


def test_hermetic_and_corpus_guards_untouched() -> None:
    guard = (
        ROOT / "src" / "nativeforge" / "services" / "hermetic_test_guard_service.py"
    ).read_text(encoding="utf-8")
    assert "ENV_ALLOW_LIVE_NETWORK" in guard
    assert "ENV_ALLOW_CORPUS_WRITEBACK" in guard
    assert "ENV_ALLOW_SOURCE_FIXTURE_OVERWRITE" in guard
    # The defaults are what matter: opt-in, never opt-out.
    assert 'NATIVEFORGE_ALLOW_LIVE_GRANTS_GOV_TESTS' in guard
    assert "TRUTHY" in guard


def test_gate79_exclusion_contract_still_holds_without_gate81_params() -> None:
    """Every Gate 81 parameter is optional; omitting them is Gate 79 behaviour."""
    before = evaluate_all_applicant_classes(
        opportunity_id="n",
        eligibility_text="Eligibility is limited to federally recognized tribes.",
        evidence_reference="https://example.test/n",
    )
    after = evaluate_all_applicant_classes(
        opportunity_id="n",
        eligibility_text="Eligibility is limited to federally recognized tribes.",
        evidence_reference="https://example.test/n",
        additional_named_classes=None,
        negated_classes=None,
    )
    assert before["excluded_classes"] == after["excluded_classes"]
    assert before["eligible_classes"] == after["eligible_classes"]
    assert all_classes_invariant_failures(before) == []
