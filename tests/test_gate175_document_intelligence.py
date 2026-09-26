"""Gate 175: document / NOFO / attachment intelligence.

Hermetic. No socket, no live document download, no writes to the real
database.

The premise: **the landing page is not the authoritative answer.** Eligibility
lives on page 14 of an attachment, the match requirement lives in Appendix C,
and the FAQ published a month later is what the programme officer will cite.

The single most important rule below is that a document we could not READ must
never read as a document with nothing in it.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys

import pytest

from nativeforge.services.document_fact_extraction_service import (
    AMENDMENT_SUPERSEDES,
    COST_SHARE,
    DEADLINE,
    ELIGIBILITY,
    FACT_KINDS,
    FAQ_CLARIFIES,
    NOTICE_OUTRANKS_SUMMARY,
    SELECTS_A_WINNER,
    UNRESOLVED,
    build_citation,
    build_fact,
    citation_invariant_failures,
    conflict_invariant_failures,
    describe_fact_model,
    detect_conflicts,
    fact_invariant_failures,
)
from nativeforge.services.opportunity_document_service import (
    ABSENCE_IS_MEANINGFUL,
    AMENDMENT,
    APPENDIX,
    DOCUMENT_STATES,
    FAQ,
    NO_FACTS_POSSIBLE,
    NOFO,
    NOT_FETCHED,
    PARSED,
    PARTIAL,
    UNSUPPORTED,
    WEBPAGE,
    build_document,
    build_version_chain,
    describe_document_model,
    document_invariant_failures,
    document_types,
    register_document_type,
    reset_registered_document_types,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
CID = "c1"


def _doc(kind: str, body: str, **kw: object) -> dict:
    base = dict(
        canonical_id=CID,
        document_type=kind,
        content_sha256=hashlib.sha256(body.encode()).hexdigest(),
        size_bytes=max(len(body), 1),
        page_count=20,
        document_state=PARSED,
        extraction_method="test_parser",
    )
    base.update(kw)
    return build_document(**base)  # type: ignore[arg-type]


def _fact(document: dict, kind: str, value: object, text: str, **kw: object) -> dict:
    base = dict(
        canonical_id=CID,
        document=document,
        fact_kind=kind,
        value=value,
        source_text=text,
        page_ref=1,
    )
    base.update(kw)
    return build_fact(**base)  # type: ignore[arg-type]


# ============ documents are first class ============================


def test_documents_are_first_class_and_bound_to_an_opportunity():
    document = _doc(NOFO, "notice body")
    assert document_invariant_failures(document) == []
    assert document["canonical_id"] == CID

    orphan = dict(document)
    orphan["canonical_id"] = None
    assert (
        "document_not_bound_to_a_canonical_opportunity"
        in document_invariant_failures(orphan)
    )


def test_document_types_are_extensible():
    reset_registered_document_types()
    try:
        before = len(document_types())
        assert register_document_type("Program Announcement") == (
            "PROGRAM_ANNOUNCEMENT"
        )
        assert len(document_types()) == before + 1
    finally:
        reset_registered_document_types()


# ============ the rule this gate exists for ========================


def test_a_missing_parser_is_not_empty_truth():
    """A scanned PDF with no text layer must never read as "no requirements

    found". That is byte-identical to a NOFO which genuinely imposes none.
    """
    scanned = _doc(NOFO, "scanned", document_state=UNSUPPORTED, extraction_method=None)
    assert scanned["absence_is_meaningful"] is False
    assert scanned["can_support_facts"] is False
    assert describe_document_model()["missing_parser_is_not_empty_truth"] is True


def test_a_partial_parse_is_not_empty_truth():
    """An absent fact may be in the part we could not read."""
    partial = _doc(NOFO, "half read", document_state=PARTIAL)
    assert partial["absence_is_meaningful"] is False
    assert PARTIAL not in ABSENCE_IS_MEANINGFUL


def test_only_a_parsed_document_makes_absence_meaningful():
    for state in DOCUMENT_STATES:
        document = _doc(
            NOFO,
            "body",
            document_state=state,
            extraction_method=None if state == NOT_FETCHED else "test_parser",
        )
        assert document["absence_is_meaningful"] == (state == PARSED), state


def test_a_document_cannot_claim_absence_means_something_when_unparsed():
    lying = dict(
        _doc(NOFO, "scanned", document_state=UNSUPPORTED, extraction_method=None)
    )
    lying["absence_is_meaningful"] = True
    failures = document_invariant_failures(lying)
    assert any("claims_absence_is_meaningful" in f for f in failures), failures


def test_no_fact_can_come_from_a_document_that_cannot_support_one():
    scanned = _doc(NOFO, "scanned", document_state=UNSUPPORTED, extraction_method=None)
    assert UNSUPPORTED in NO_FACTS_POSSIBLE
    invented = _fact(scanned, ELIGIBILITY, ["tribal_government"], "invented")
    failures = fact_invariant_failures(invented, document=scanned)
    assert any("state_UNSUPPORTED" in f for f in failures), failures


# ============ versions =============================================


def test_the_same_url_with_changed_bytes_creates_a_new_version():
    one = _doc(NOFO, "version one", location_ref="https://x/nofo.pdf")
    two = _doc(NOFO, "version TWO", location_ref="https://x/nofo.pdf")
    assert one["document_id"] != two["document_id"]


def test_the_same_bytes_at_a_different_url_is_the_same_document():
    """An agency's mirror is not an amendment."""
    original = _doc(NOFO, "identical body", location_ref="https://x/nofo.pdf")
    mirror = _doc(NOFO, "identical body", location_ref="https://mirror/nofo.pdf")
    assert original["document_id"] == mirror["document_id"]
    assert describe_document_model()["identity_is_the_content_hash"] is True


def test_document_versions_are_preserved_through_an_amendment():
    original = _doc(NOFO, "original", version_ordinal=1)
    amended = _doc(
        AMENDMENT,
        "amendment",
        version_ordinal=2,
        supersedes_document_id=original["document_id"],
    )
    chain = build_version_chain([original, amended])
    assert chain["chain_is_valid"] is True
    assert chain["document_count"] == 2
    assert chain["latest_document_ids"] == [amended["document_id"]]
    assert chain["superseded_count"] == 1


def test_a_supersession_cycle_is_refused():
    a = _doc(NOFO, "a", version_ordinal=2)
    b = _doc(NOFO, "b", version_ordinal=2)
    a_loop = dict(a)
    a_loop["supersedes_document_id"] = b["document_id"]
    b_loop = dict(b)
    b_loop["supersedes_document_id"] = a["document_id"]
    chain = build_version_chain([a_loop, b_loop])
    assert any(f.startswith("supersession_cycle:") for f in chain["chain_failures"]), (
        chain["chain_failures"]
    )


def test_an_amendment_referencing_a_missing_predecessor_is_refused():
    orphan = _doc(AMENDMENT, "orphan", version_ordinal=2)
    forced = dict(orphan)
    forced["supersedes_document_id"] = "0" * 64
    chain = build_version_chain([forced])
    assert any(
        f.startswith("amendment_references_missing_predecessor:")
        for f in chain["chain_failures"]
    )


def test_a_latest_pointer_that_is_not_newest_is_refused():
    original = _doc(NOFO, "original", version_ordinal=2)
    backwards = _doc(
        AMENDMENT,
        "amendment",
        version_ordinal=1,
        supersedes_document_id=original["document_id"],
    )
    chain = build_version_chain([original, backwards])
    assert any(
        f.startswith("successor_ordinal_not_newer:") for f in chain["chain_failures"]
    )


def test_a_document_cannot_supersede_itself():
    document = _doc(NOFO, "self")
    forced = dict(document)
    forced["supersedes_document_id"] = forced["document_id"]
    assert "document_supersedes_itself" in document_invariant_failures(forced)


# ============ facts and citations ==================================


def test_a_document_fact_requires_provenance():
    document = _doc(NOFO, "body")
    fact = _fact(document, DEADLINE, "2026-11-15", "Applications are due")
    assert fact_invariant_failures(fact, document=document) == []

    unquoted = dict(fact)
    unquoted["source_text"] = None
    assert "fact_has_no_source_text" in fact_invariant_failures(unquoted)


def test_a_citation_requires_a_document():
    document = _doc(NOFO, "body")
    fact = _fact(document, DEADLINE, "2026-11-15", "due")
    homeless = dict(fact)
    homeless["document_id"] = None
    assert "fact_has_no_document" in fact_invariant_failures(homeless)

    citation = build_citation(fact, document)
    assert citation_invariant_failures(citation) == []
    assert citation["content_sha256"] == document["content_sha256"]
    assert citation["quoted_text"] == "due"


def test_a_citation_page_outside_the_document_is_refused():
    document = _doc(NOFO, "body", page_count=12)
    beyond = _fact(document, DEADLINE, "2026-11-15", "due", page_ref=99)
    failures = fact_invariant_failures(beyond, document=document)
    assert any("outside_a_12_page_document" in f for f in failures), failures


def test_appendix_only_eligibility_is_detected():
    """A fact found only in an appendix is still a fact."""
    appendix = _doc(APPENDIX, "Appendix B: federally recognized tribes")
    fact = _fact(
        appendix,
        ELIGIBILITY,
        ["tribal_government"],
        "Federally recognized Indian tribes are eligible",
        section_ref="Appendix B",
    )
    assert fact_invariant_failures(fact, document=appendix) == []
    assert fact["document_type"] == APPENDIX
    assert APPENDIX in describe_fact_model()["appendix_and_faq_are_fact_bearing"]


def test_a_match_requirement_found_only_in_an_faq_is_still_binding():
    faq = _doc(FAQ, "Q: is a match required? A: yes, 20 percent.")
    fact = _fact(faq, COST_SHARE, 0.20, "A: yes, 20 percent.", section_ref="FAQ 7")
    assert fact_invariant_failures(fact, document=faq) == []
    assert fact["is_material"] is True


@pytest.mark.parametrize("kind", sorted(FACT_KINDS))
def test_every_fact_kind_can_be_built_and_validated(kind):
    document = _doc(NOFO, "body")
    fact = _fact(document, kind, "value", "quoted text")
    assert fact_invariant_failures(fact, document=document) == []


# ============ conflicts ============================================


def test_a_document_conflict_is_not_silently_resolved():
    """Two appendices disagreeing, with no authority rule between them."""
    a = _doc(APPENDIX, "Appendix B: ceiling 500,000")
    b = _doc(APPENDIX, "Appendix C: ceiling 400,000")
    facts = [
        _fact(a, "AWARD_CEILING", 500000, "ceiling 500,000"),
        _fact(b, "AWARD_CEILING", 400000, "ceiling 400,000"),
    ]
    report = detect_conflicts(facts)
    conflict = report["conflicts"][0]
    assert conflict["resolution_rule"] == UNRESOLVED
    assert conflict["winning_fact_id"] is None
    assert conflict["review_required"] is True
    assert conflict["both_values_retained"] is True
    assert conflict_invariant_failures(conflict) == []


def test_an_faq_clarification_never_erases_the_original():
    nofo = _doc(NOFO, "Units of general local government are eligible")
    faq = _doc(FAQ, "Q: may tribes apply? A: yes.")
    facts = [
        _fact(nofo, ELIGIBILITY, ["local_government"], "Units of local government"),
        _fact(
            faq,
            ELIGIBILITY,
            ["local_government", "tribal_government"],
            "A: yes, tribes are included.",
        ),
    ]
    conflict = detect_conflicts(facts)["conflicts"][0]
    assert conflict["resolution_rule"] == FAQ_CLARIFIES
    assert conflict["winning_fact_id"] is None
    assert conflict["review_required"] is True
    assert len(conflict["values"]) == 2
    assert FAQ_CLARIFIES not in SELECTS_A_WINNER


def test_a_clarification_that_overwrote_the_original_is_refused():
    nofo = _doc(NOFO, "original")
    faq = _doc(FAQ, "clarification")
    facts = [
        _fact(nofo, ELIGIBILITY, ["a"], "original text"),
        _fact(faq, ELIGIBILITY, ["a", "b"], "clarifying text"),
    ]
    conflict = dict(detect_conflicts(facts)["conflicts"][0])
    conflict["winning_fact_id"] = facts[1]["fact_id"]
    assert "clarification_overwrote_the_original" in conflict_invariant_failures(
        conflict
    )


def test_an_amendment_supersedes_and_keeps_the_predecessor():
    nofo = _doc(NOFO, "due November 15")
    amendment = _doc(AMENDMENT, "the deadline is extended to December 15")
    facts = [
        _fact(nofo, DEADLINE, "2026-11-15", "Applications are due November 15"),
        _fact(amendment, DEADLINE, "2026-12-15", "extended to December 15"),
    ]
    conflict = detect_conflicts(facts)["conflicts"][0]
    assert conflict["resolution_rule"] == AMENDMENT_SUPERSEDES
    assert conflict["winning_fact_id"] == facts[1]["fact_id"]
    assert conflict["both_values_retained"] is True
    assert conflict_invariant_failures(conflict) == []


def test_a_notice_outranks_a_landing_page_summary():
    landing = _doc(WEBPAGE, "Due November 1", page_count=1)
    nofo = _doc(NOFO, "Applications are due November 15")
    facts = [
        _fact(landing, DEADLINE, "2026-11-01", "Due November 1"),
        _fact(nofo, DEADLINE, "2026-11-15", "due November 15"),
    ]
    conflict = detect_conflicts(facts)["conflicts"][0]
    assert conflict["resolution_rule"] == NOTICE_OUTRANKS_SUMMARY
    assert conflict["winning_fact_id"] == facts[1]["fact_id"]


def test_a_winner_without_a_selecting_rule_is_refused():
    a = _doc(APPENDIX, "one")
    b = _doc(APPENDIX, "two")
    facts = [
        _fact(a, "AWARD_CEILING", 1, "one"),
        _fact(b, "AWARD_CEILING", 2, "two"),
    ]
    conflict = dict(detect_conflicts(facts)["conflicts"][0])
    conflict["winning_fact_id"] = facts[0]["fact_id"]
    failures = conflict_invariant_failures(conflict)
    assert any("picked_a_winner_under_rule" in f for f in failures), failures


# ============ the instruments ======================================


def test_the_document_phase_makes_no_network_request():
    """175I: the mechanism exists without the crawling."""
    result = subprocess.run(  # noqa: S603
        [sys.executable, "scripts/_g175_phase_document_intelligence.py"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=900,
    )
    report = json.loads(
        [line for line in result.stdout.splitlines() if line.startswith("{")][-1]
    )
    assert report["network_attempts_during_this_phase"] == 0
    assert report["live_document_downloads"] == 0
    assert report["all_bytes_are_synthetic_fixtures"] is True
    assert report["fixture_residue"] == 0


def test_the_document_self_health_detects_broken_fixtures():
    """Eight planted breakages, each asserted to be caught by the SPECIFIC

    detector rather than by any failure at all - a detector that passes for
    the wrong reason is not a detector.
    """
    result = subprocess.run(  # noqa: S603
        [sys.executable, "scripts/_g175_phase_document_intelligence.py"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=900,
    )
    report = json.loads(
        [line for line in result.stdout.splitlines() if line.startswith("{")][-1]
    )
    assert report["document_self_health_ready"] is True
    for check in (
        "supersession_cycle_is_caught",
        "missing_predecessor_is_caught",
        "latest_pointer_not_newest_is_caught",
        "citation_beyond_the_document_is_caught",
        "fact_without_a_document_is_caught",
        "fact_from_an_unreadable_document_is_caught",
        "clarification_overwrite_is_caught",
        "false_absence_claim_is_caught",
    ):
        assert report["falsifiability"][check] is True, check


def test_migration_0061_puts_the_document_rules_in_the_schema():
    text = (REPO / "alembic" / "versions" / "0061_document_intelligence.py").read_text(
        encoding="utf-8"
    )
    assert "absence_meaningful_only_when_parsed" in text
    assert "fact_needs_a_document" in text
    assert "fact_quotes_its_source" in text
    assert "winner_needs_a_sel_rule" in text
    assert "clarif_does_not_overwrite" in text
    assert "no_self_supersession" in text


def test_the_award_document_table_was_not_reused():
    """`nf_award_documents` is post-award compliance, bound to

    `awarded_grant_id`. Filing a funder's eligibility language there would
    conflate two lifecycle stages permanently.
    """
    text = (REPO / "alembic" / "versions" / "0061_document_intelligence.py").read_text(
        encoding="utf-8"
    )
    assert "nf_opportunity_documents" in text
    assert "awarded_grant_id" not in text.split('"""')[2]
