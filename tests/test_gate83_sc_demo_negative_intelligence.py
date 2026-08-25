"""Gate 83 — SC demo negative intelligence surface.

The surface runs the real Gate 82 pipeline over the committed synthetic notice,
so these tests check a produced result rather than hand-authored demo copy.
"""

from __future__ import annotations

import json
from pathlib import Path

from nativeforge.services.sc_demo_negative_intelligence_service import (
    DEMO_APPLICANT_CLASSES,
    DEMO_ARTIFACT,
    build_sc_demo_negative_intelligence_surface,
    sc_demo_negative_intelligence_invariant_failures,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO_JSON = ROOT / "frontend" / "src" / "demo" / "sc_customer_demo.json"

SURFACE = build_sc_demo_negative_intelligence_surface()


def _row(applicant_class: str) -> dict:
    return next(
        r for r in SURFACE["rows"] if r["applicant_class"] == applicant_class
    )


# --------------------------------------------------------------------------
# Claim boundaries
# --------------------------------------------------------------------------


def test_surface_is_marked_synthetic() -> None:
    assert SURFACE["synthetic_demo"] is True
    assert SURFACE["demo_only"] is True


def test_no_live_coverage_is_claimed() -> None:
    assert SURFACE["live_coverage_claimed"] is False


def test_no_source_monitoring_is_claimed() -> None:
    assert SURFACE["source_monitored"] is False


def test_no_freshness_is_claimed() -> None:
    assert SURFACE["freshness_claimed"] is False


def test_no_url_fetch_was_performed() -> None:
    assert SURFACE["url_fetch_performed"] is False


def test_no_final_eligibility_or_ineligibility_is_asserted() -> None:
    assert SURFACE["final_eligibility_claimed"] is False
    assert SURFACE["not_eligible_asserted"] is False
    for row in SURFACE["rows"]:
        assert row["not_eligible_asserted"] is False


def test_surface_invariants_hold() -> None:
    assert sc_demo_negative_intelligence_invariant_failures(SURFACE) == []


def test_the_demo_notice_is_a_committed_synthetic_fixture() -> None:
    assert DEMO_ARTIFACT.is_file()
    head = DEMO_ARTIFACT.read_text(encoding="utf-8")
    flat = " ".join(head.split())
    assert "SYNTHETIC TEST FIXTURE - NOT A REAL NOTICE" in flat
    assert "No opportunity number is claimed" in flat
    assert SURFACE["artifact_is_recorded_fixture"] is True


# --------------------------------------------------------------------------
# The applicant-class contrast
# --------------------------------------------------------------------------


def test_state_recognized_tribe_is_excluded_by_evidence() -> None:
    row = _row("state_recognized_tribe")
    assert row["exclusion_status"] == "excluded_by_evidence"
    assert row["has_citation"] is True


def test_federally_recognized_tribe_does_not_receive_the_same_exclusion() -> None:
    row = _row("federally_recognized_tribe")
    assert row["exclusion_status"] != "excluded_by_evidence"
    assert row["exclusion_status"] == "eligible"


def test_applicant_class_changes_the_answer() -> None:
    assert SURFACE["applicant_class_changes_the_answer"] is True
    assert SURFACE["excluded_class_count"] >= 1
    assert SURFACE["eligible_class_count"] >= 1


def test_the_recognition_tiers_are_not_collapsed() -> None:
    state = _row("state_recognized_tribe")["exclusion_status"]
    federal = _row("federally_recognized_tribe")["exclusion_status"]
    assert state != federal


def test_collapsing_the_tiers_fails_the_invariant() -> None:
    forged = json.loads(json.dumps(SURFACE))
    for row in forged["rows"]:
        row["exclusion_status"] = "eligible"
    failures = sc_demo_negative_intelligence_invariant_failures(forged)
    assert "recognition_tiers_collapsed_to_one_answer" in failures


def test_both_recognition_tiers_are_present() -> None:
    classes = {r["applicant_class"] for r in SURFACE["rows"]}
    assert classes == {c for c, _label in DEMO_APPLICANT_CLASSES}


# --------------------------------------------------------------------------
# Excluded stays visible
# --------------------------------------------------------------------------


def test_excluded_opportunity_remains_visible() -> None:
    assert _row("state_recognized_tribe")["remains_visible"] is True
    assert SURFACE["excluded_hidden"] is False


def test_hiding_an_excluded_row_fails_the_invariant() -> None:
    forged = json.loads(json.dumps(SURFACE))
    forged["rows"][0]["remains_visible"] = False
    failures = sc_demo_negative_intelligence_invariant_failures(forged)
    assert any(f.startswith("excluded_row_hidden") for f in failures)


def test_the_excluded_row_is_the_one_that_leads() -> None:
    """The negative answer is the one a customer cannot get anywhere else."""
    assert SURFACE["rows"][0]["applicant_class"] == "state_recognized_tribe"


# --------------------------------------------------------------------------
# The quote comes from the parser
# --------------------------------------------------------------------------


def test_every_row_carries_an_evidence_quote() -> None:
    for row in SURFACE["rows"]:
        assert row["evidence_quote"].strip()


def test_the_quote_is_text_from_the_notice_not_demo_copy() -> None:
    """Every quoted word must appear in the fixture itself."""
    fixture = " ".join(DEMO_ARTIFACT.read_text(encoding="utf-8").split()).lower()
    for row in SURFACE["rows"]:
        quote = " ".join(row["evidence_quote"].split()).lower()
        # The adapter drops markup, so compare on the words the notice carries.
        for word in quote.split():
            if word.isalpha() and len(word) > 4:
                assert word in fixture, f"{word!r} is not in the notice fixture"


def test_the_excluding_sentence_is_the_one_quoted() -> None:
    quote = _row("state_recognized_tribe")["evidence_quote"].lower()
    assert "limited to federally recognized indian tribes" in " ".join(quote.split())


def test_every_row_carries_a_valid_evidence_span() -> None:
    for row in SURFACE["rows"]:
        span = row["evidence_span"]
        assert isinstance(span, list) and len(span) == 2
        assert span[1] > span[0] >= 0


def test_a_row_without_a_quote_fails_the_invariant() -> None:
    forged = json.loads(json.dumps(SURFACE))
    forged["rows"][0]["evidence_quote"] = ""
    failures = sc_demo_negative_intelligence_invariant_failures(forged)
    assert any(f.startswith("row_without_an_evidence_quote") for f in failures)


def test_an_uncited_exclusion_fails_the_invariant() -> None:
    forged = json.loads(json.dumps(SURFACE))
    for row in forged["rows"]:
        if row["exclusion_status"] == "excluded_by_evidence":
            row["has_citation"] = False
    failures = sc_demo_negative_intelligence_invariant_failures(forged)
    assert any(f.startswith("exclusion_without_citation") for f in failures)


# --------------------------------------------------------------------------
# Provenance
# --------------------------------------------------------------------------


def test_artifact_hash_is_present_on_the_surface_and_every_row() -> None:
    assert SURFACE["artifact_hash"]
    assert len(SURFACE["artifact_hash"]) == 64
    for row in SURFACE["rows"]:
        assert row["artifact_hash"] == SURFACE["artifact_hash"]


def test_the_hash_matches_the_fixture_on_disk() -> None:
    import hashlib

    expected = hashlib.sha256(DEMO_ARTIFACT.read_bytes()).hexdigest()
    assert SURFACE["artifact_hash"] == expected


def test_the_pipeline_actually_ran() -> None:
    assert SURFACE["pipeline_status"] == "ingested"
    assert SURFACE["artifact_type"] == "html"
    for row in SURFACE["rows"]:
        assert row["text_extraction_method"] == "stdlib_html_parser"


def test_span_basis_is_declared() -> None:
    assert SURFACE["evidence_spans_relative_to"] == "adapter_text"


def test_adapter_confidence_is_not_eligibility_confidence() -> None:
    assert SURFACE["adapter_confidence"] in {"low", "medium", "high"}
    assert SURFACE["eligibility_confidence"] == "none"


def test_claiming_eligibility_confidence_fails_the_invariant() -> None:
    forged = json.loads(json.dumps(SURFACE))
    forged["eligibility_confidence"] = "high"
    failures = sc_demo_negative_intelligence_invariant_failures(forged)
    assert "eligibility_confidence_claimed_on_a_demo_surface" in failures


def test_deadline_is_reported_honestly() -> None:
    """The fixture carries a date in its deadline section, but nobody supplied
    a verified close date, and Gate 81 refuses to promote a parsed one."""
    for row in SURFACE["rows"]:
        assert row["deadline_status"] == "date_in_text_not_promoted_to_close_date"


# --------------------------------------------------------------------------
# Copy concepts required by Gate 83D
# --------------------------------------------------------------------------


def test_required_copy_concepts_are_present() -> None:
    joined = " ".join(SURFACE["copy_concepts"]).lower()
    assert "relevant does not mean eligible" in joined
    assert "remain visible" in joined
    assert "applicant class matters" in joined
    assert "sentence" in joined


def test_headline_does_not_assert_legal_ineligibility() -> None:
    text = (SURFACE["headline"] + " " + SURFACE["why_it_matters"]).lower()
    for banned in (
        "you are not eligible",
        "you are ineligible",
        "legally ineligible",
        "you cannot apply",
    ):
        assert banned not in text


def test_no_row_label_asserts_legal_ineligibility() -> None:
    for row in SURFACE["rows"]:
        label = row["exclusion_status_label"].lower()
        assert "legally" not in label
        assert "you are not eligible" not in label


# --------------------------------------------------------------------------
# Determinism and bridge wiring
# --------------------------------------------------------------------------


def test_the_surface_is_deterministic() -> None:
    """Unlike the wider demo payload, this surface must not churn between
    builds - it is derived only from a committed fixture."""
    a = json.dumps(build_sc_demo_negative_intelligence_surface(), sort_keys=True)
    b = json.dumps(build_sc_demo_negative_intelligence_surface(), sort_keys=True)
    assert a == b


def test_the_committed_demo_json_carries_the_surface() -> None:
    payload = json.loads(DEMO_JSON.read_text(encoding="utf-8"))
    surface = payload.get("negative_intelligence")
    assert surface, "regenerate frontend/src/demo/sc_customer_demo.json"
    assert surface["synthetic_demo"] is True
    assert surface["live_coverage_claimed"] is False
    assert len(surface["rows"]) == 2
    assert sc_demo_negative_intelligence_invariant_failures(surface) == []


def test_the_committed_demo_json_matches_the_current_surface() -> None:
    """If the parser changes, the committed demo must be regenerated."""
    payload = json.loads(DEMO_JSON.read_text(encoding="utf-8"))
    assert payload["negative_intelligence"] == json.loads(json.dumps(SURFACE))


def test_the_bridge_refuses_a_broken_surface() -> None:
    """Generation-time enforcement: a claim-boundary violation must never reach
    the committed JSON."""
    from nativeforge.services import sc_monday_demo_bridge_service as bridge

    source = Path(bridge.__file__).read_text(encoding="utf-8")
    assert "build_sc_demo_negative_intelligence_surface()" in source
    assert "Negative intelligence surface invariants failed" in source
    assert '"negative_intelligence": negative_intelligence_surface' in source


def test_the_service_never_reaches_the_network() -> None:
    service = (
        ROOT
        / "src"
        / "nativeforge"
        / "services"
        / "sc_demo_negative_intelligence_service.py"
    ).read_text(encoding="utf-8")
    for banned in (
        "import requests",
        "import httpx",
        "import aiohttp",
        "import urllib.request",
        "urlopen",
    ):
        assert banned not in service


def test_readiness_doc_still_claims_no_coverage() -> None:
    doc = ROOT / "docs" / "operations" / "463_GATE83_PRODUCTION_READINESS_DELTA.md"
    body = doc.read_text(encoding="utf-8")
    assert "Live SC source coverage:   NONE" in body
    assert "65% improvement:           NOT CLAIMED" in body
    assert "Controlled customer pilot: NO_GO" in body
