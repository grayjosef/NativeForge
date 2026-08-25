"""Gate 82 — notice ingestion adapters: artifact model, HTML, PDF, pipeline.

Every fixture is synthetic and says so. Nothing here fetches.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nativeforge.services.html_notice_text_adapter_service import (
    CHROME_TAGS,
    DROPPED_CONTENT_TAGS,
    EXTRACTION_METHOD,
    extract_html_notice_text,
    html_adapter_invariant_failures,
)
from nativeforge.services.notice_artifact_model_service import (
    ARTIFACT_TYPES,
    EXTRACTABLE_TYPES,
    artifact_invariant_failures,
    build_notice_artifact,
    content_hash_of,
    sniff_artifact_type,
)
from nativeforge.services.notice_ingestion_pipeline_service import (
    extract_plain_text_notice,
    extract_recorded_transport_notice,
    ingest_notice_artifact,
    pipeline_invariant_failures,
    run_text_adapter,
)
from nativeforge.services.pdf_notice_text_adapter_service import (
    KNOWN_BACKENDS,
    MIN_CHARS_PER_PAGE,
    available_pdf_backends,
    extract_pdf_notice_text,
    pdf_adapter_invariant_failures,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "nofo_artifacts"

HTML_FIXTURE = FIXTURES / "synthetic_notice.html"
MD_FIXTURE = FIXTURES / "synthetic_notice.md"
TXT_FIXTURE = FIXTURES / "synthetic_notice.txt"
PDF_FIXTURE = FIXTURES / "synthetic_notice.pdf"

GATE82_MODULES = (
    "notice_artifact_model_service.py",
    "html_notice_text_adapter_service.py",
    "pdf_notice_text_adapter_service.py",
    "notice_ingestion_pipeline_service.py",
)


# --------------------------------------------------------------------------
# Fixtures are synthetic
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path", [HTML_FIXTURE, MD_FIXTURE, TXT_FIXTURE], ids=lambda p: p.name
)
def test_text_fixtures_declare_themselves_synthetic(path: Path) -> None:
    body = path.read_text(encoding="utf-8")
    # The disclaimer is hard-wrapped in the fixtures, so compare on collapsed
    # whitespace rather than requiring it to sit on one line.
    flat = " ".join(body.split())
    assert "SYNTHETIC TEST FIXTURE - NOT A REAL NOTICE" in flat
    assert "No opportunity number is claimed" in flat


def test_pdf_fixture_is_a_real_pdf_and_declares_itself_synthetic() -> None:
    data = PDF_FIXTURE.read_bytes()
    assert data.startswith(b"%PDF-")
    assert b"SYNTHETIC TEST FIXTURE - NOT A REAL NOTICE" in data
    assert b"No opportunity number is claimed" in data


def test_pdf_fixture_generator_is_committed_and_reproduces_it() -> None:
    """A committed binary nobody can regenerate is a committed binary nobody
    can check."""
    import importlib.util

    generator = FIXTURES / "make_synthetic_pdf.py"
    assert generator.is_file()
    spec = importlib.util.spec_from_file_location("_make_pdf", generator)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.build_pdf(module.LINES) == PDF_FIXTURE.read_bytes()


@pytest.mark.parametrize(
    "path",
    [HTML_FIXTURE, MD_FIXTURE, TXT_FIXTURE, PDF_FIXTURE],
    ids=lambda p: p.name,
)
def test_no_fixture_names_a_real_programme(path: Path) -> None:
    body = path.read_bytes().lower()
    for marker in (b"hhs-", b"usda-", b"doe-", b"epa-", b"hud-", b"bia-", b"ihs-"):
        assert marker not in body, f"{path.name} looks like it names a real programme"


# --------------------------------------------------------------------------
# 82B — artifact model
# --------------------------------------------------------------------------


def test_live_fetch_defaults_false() -> None:
    artifact = build_notice_artifact(
        artifact_id="a1", local_path=str(TXT_FIXTURE)
    )
    assert artifact["is_live_fetch"] is False
    assert artifact["fetch_mode"] == "fixture"
    assert artifact_invariant_failures(artifact) == []


def test_declared_live_fetch_is_refused_by_the_hermetic_guard() -> None:
    artifact = build_notice_artifact(
        artifact_id="a1",
        local_path=str(TXT_FIXTURE),
        declared_live_fetch=True,
    )
    assert artifact["is_live_fetch"] is False
    assert "live_fetch_declared_but_refused_by_hermetic_guard" in artifact["warnings"]
    assert artifact_invariant_failures(artifact) == []


def test_a_forged_live_fetch_claim_fails_the_invariant() -> None:
    artifact = build_notice_artifact(artifact_id="a1", local_path=str(TXT_FIXTURE))
    forged = dict(artifact)
    forged["is_live_fetch"] = True
    failures = artifact_invariant_failures(forged)
    assert "live_fetch_claimed_while_hermetic_guard_forbids_it" in failures


def test_unknown_artifact_type_blocks() -> None:
    artifact = build_notice_artifact(
        artifact_id="a1", local_path=str(ROOT / "README.md"), artifact_type="wat"
    )
    assert "unrecognised_declared_artifact_type:wat" in artifact["warnings"]
    assert artifact["artifact_type"] == "unknown"
    assert "unknown_artifact_type" in artifact["blocked_reasons"]
    assert artifact["extractable"] is False
    assert artifact_invariant_failures(artifact) == []


def test_missing_local_path_blocks() -> None:
    artifact = build_notice_artifact(artifact_id="a1")
    assert "missing_local_path" in artifact["blocked_reasons"]
    assert artifact["extractable"] is False


def test_nonexistent_local_path_blocks() -> None:
    artifact = build_notice_artifact(
        artifact_id="a1", local_path=str(FIXTURES / "does_not_exist.txt")
    )
    assert "local_path_does_not_exist" in artifact["blocked_reasons"]
    assert artifact["extractable"] is False


def test_blocked_artifact_cannot_be_reported_extractable() -> None:
    artifact = build_notice_artifact(artifact_id="a1")
    forged = dict(artifact)
    forged["extractable"] = True
    assert "blocked_artifact_reported_as_extractable" in artifact_invariant_failures(
        forged
    )


def test_content_hash_is_computed_and_mismatch_blocks() -> None:
    artifact = build_notice_artifact(
        artifact_id="a1", local_path=str(TXT_FIXTURE)
    )
    assert artifact["content_hash"] == content_hash_of(TXT_FIXTURE)

    wrong = build_notice_artifact(
        artifact_id="a1", local_path=str(TXT_FIXTURE), content_hash="0" * 64
    )
    assert "content_hash_mismatch" in wrong["blocked_reasons"]


def test_missing_hash_warns_by_default_and_blocks_when_required() -> None:
    missing = build_notice_artifact(artifact_id="a1", local_path="nope.txt")
    assert "no_content_hash_available" in missing["warnings"]

    required = build_notice_artifact(
        artifact_id="a1", local_path="nope.txt", require_hash=True
    )
    assert "missing_content_hash" in required["blocked_reasons"]


def test_committed_fixture_is_recognised_as_recorded() -> None:
    artifact = build_notice_artifact(
        artifact_id="a1", local_path=str(TXT_FIXTURE)
    )
    assert artifact["is_recorded_fixture"] is True


def test_recorded_fixture_and_live_fetch_are_mutually_exclusive() -> None:
    artifact = build_notice_artifact(artifact_id="a1", local_path=str(TXT_FIXTURE))
    forged = dict(artifact)
    forged["is_recorded_fixture"] = True
    forged["is_live_fetch"] = True
    failures = artifact_invariant_failures(forged)
    assert "artifact_claims_both_live_fetch_and_recorded_fixture" in failures


def test_suffix_sniffing() -> None:
    assert sniff_artifact_type("a.html") == "html"
    assert sniff_artifact_type("a.pdf") == "pdf"
    assert sniff_artifact_type("a.md") == "markdown"
    assert sniff_artifact_type("a.txt") == "plain_text"
    assert sniff_artifact_type("a.json") == "json_recorded_transport"
    assert sniff_artifact_type("a.xyz") == "unknown"
    assert sniff_artifact_type(None) == "unknown"


def test_magic_bytes_outrank_a_wrong_declared_type(tmp_path: Path) -> None:
    """A PDF named .txt is still a PDF, and reading it as text would produce
    binary noise that could be sectioned as prose."""
    mislabeled = tmp_path / "notice.txt"
    mislabeled.write_bytes(PDF_FIXTURE.read_bytes())
    artifact = build_notice_artifact(
        artifact_id="a1", local_path=str(mislabeled), artifact_type="plain_text"
    )
    assert artifact["artifact_type"] == "pdf"
    assert any(w.startswith("content_is_pdf_but_type_is") for w in artifact["warnings"])


def test_declared_type_disagreeing_with_suffix_warns() -> None:
    artifact = build_notice_artifact(
        artifact_id="a1", local_path=str(TXT_FIXTURE), artifact_type="markdown"
    )
    warnings = artifact["warnings"]
    assert any(w.startswith("declared_type_disagrees_with_suffix") for w in warnings)


def test_artifact_model_claims_neither_freshness_nor_eligibility() -> None:
    artifact = build_notice_artifact(artifact_id="a1", local_path=str(TXT_FIXTURE))
    assert artifact["freshness_claimed"] is False
    assert artifact["eligibility_claimed"] is False
    assert artifact["url_fetch_performed"] is False


def test_extractable_types_are_derived_not_hardcoded() -> None:
    assert EXTRACTABLE_TYPES == ARTIFACT_TYPES - {"unknown"}
    assert "unknown" not in EXTRACTABLE_TYPES


# --------------------------------------------------------------------------
# 82C — HTML adapter
# --------------------------------------------------------------------------


def test_html_adapter_never_fetches_a_url() -> None:
    result = extract_html_notice_text(local_path="https://example.test/notice.html")
    assert result["extraction_status"] == "blocked"
    assert "local_path_is_a_url_not_a_path" in result["blocked_reasons"]
    assert result["url_fetch_performed"] is False
    assert html_adapter_invariant_failures(result) == []


def test_html_adapter_reads_a_local_file() -> None:
    result = extract_html_notice_text(
        local_path=str(HTML_FIXTURE), artifact_id="a1"
    )
    assert result["extraction_status"] == "extracted"
    assert result["text_extraction_method"] == EXTRACTION_METHOD
    assert html_adapter_invariant_failures(result) == []


def test_script_text_never_becomes_notice_text() -> None:
    """The regex approach used elsewhere strips tags but keeps script bodies."""
    result = extract_html_notice_text(local_path=str(HTML_FIXTURE))
    assert "state-recognized tribes" not in result["text"].lower()
    assert "var trap" not in result["text"].lower()
    assert result["script_text_included"] is False
    assert result["dropped_tag_counts"].get("script", 0) >= 1


def test_style_text_never_becomes_notice_text() -> None:
    result = extract_html_notice_text(local_path=str(HTML_FIXTURE))
    assert "font-family" not in result["text"].lower()
    assert result["dropped_tag_counts"].get("style", 0) >= 1


def test_comment_text_never_becomes_notice_text() -> None:
    result = extract_html_notice_text(local_path=str(HTML_FIXTURE))
    assert "native nonprofit organizations" not in result["text"].lower()
    assert result["comment_chars"] > 0
    assert result["comment_text_included"] is False


def test_hidden_text_is_flagged_and_excluded() -> None:
    result = extract_html_notice_text(local_path=str(HTML_FIXTURE))
    assert "also eligible" not in result["text"].lower()
    assert result["hidden_text_chars"] > 0
    assert result["hidden_text_included"] is False
    assert any(w.startswith("hidden_text_excluded_chars") for w in result["warnings"])
    assert result["human_review_required"] is True


def test_chrome_elements_are_dropped() -> None:
    result = extract_html_notice_text(local_path=str(HTML_FIXTURE))
    assert "apply now" not in result["text"].lower()
    assert result["chrome_tag_counts"].get("nav", 0) >= 1


def test_headings_survive_for_gate81_section_detection() -> None:
    from nativeforge.services.nofo_text_extraction_service import detect_sections

    result = extract_html_notice_text(local_path=str(HTML_FIXTURE))
    assert result["heading_count"] >= 3
    kinds = {s["kind"] for s in detect_sections(result["text"])}
    assert "eligibility" in kinds
    assert "deadline" in kinds


def test_paragraph_boundaries_survive() -> None:
    result = extract_html_notice_text(
        html="<h2>ELIGIBILITY INFORMATION</h2><p>One.</p><p>Two.</p>"
    )
    assert "\n\n" in result["text"]


def test_empty_html_is_flagged() -> None:
    for empty in ("", "   \n  "):
        result = extract_html_notice_text(html=empty)
        assert result["extraction_status"] == "blocked"
        assert "empty_html" in result["blocked_reasons"]
        assert html_adapter_invariant_failures(result) == []


def test_html_with_no_text_at_all_blocks() -> None:
    result = extract_html_notice_text(html="<html><script>var x=1;</script></html>")
    assert result["extraction_status"] == "blocked"
    assert "no_text_after_extraction" in result["blocked_reasons"]


def test_no_html_supplied_blocks() -> None:
    result = extract_html_notice_text()
    assert result["extraction_status"] == "blocked"
    assert "no_html_supplied" in result["blocked_reasons"]


def test_blocked_html_result_carries_no_text() -> None:
    result = extract_html_notice_text(html="")
    forged = dict(result)
    forged["text"] = "smuggled"
    assert "blocked_result_carried_text" in html_adapter_invariant_failures(forged)


def test_malformed_html_does_not_crash() -> None:
    result = extract_html_notice_text(
        html="<h2>ELIGIBILITY<p>Eligible applicants are tribes.<div><span>"
    )
    assert result["extraction_status"] == "extracted"
    assert "eligible applicants" in result["text"].lower()


def test_no_headings_lowers_confidence_and_warns() -> None:
    result = extract_html_notice_text(html="<p>Just a paragraph of prose.</p>")
    assert result["adapter_confidence"] == "low"
    assert result["human_review_required"] is True
    assert "no_headings_found_section_detection_will_be_weak" in result["warnings"]


def test_dropped_and_chrome_tag_sets_are_disjoint() -> None:
    assert not (DROPPED_CONTENT_TAGS & CHROME_TAGS)


# --------------------------------------------------------------------------
# 82D — PDF adapter
# --------------------------------------------------------------------------


def test_pdf_adapter_fails_honestly_when_no_parser_is_installed() -> None:
    if available_pdf_backends():
        pytest.skip("a PDF backend is installed; the unavailable path cannot run")
    result = extract_pdf_notice_text(local_path=str(PDF_FIXTURE))
    assert result["extraction_status"] == "blocked"
    assert "parser_unavailable" in result["blocked_reasons"]
    assert result["text"] == ""
    assert result["text_fabricated"] is False
    assert result["human_review_required"] is True
    assert pdf_adapter_invariant_failures(result) == []


def test_known_backends_are_probed_without_importing() -> None:
    backends = available_pdf_backends()
    assert set(backends) <= set(KNOWN_BACKENDS)


def test_pdf_adapter_never_fetches_a_url() -> None:
    result = extract_pdf_notice_text(local_path="https://example.test/notice.pdf")
    assert result["extraction_status"] == "blocked"
    assert "local_path_is_a_url_not_a_path" in result["blocked_reasons"]
    assert result["url_fetch_performed"] is False


def test_pdf_adapter_requires_a_local_path() -> None:
    result = extract_pdf_notice_text()
    assert "missing_local_path" in result["blocked_reasons"]


def test_pdf_adapter_rejects_a_non_pdf() -> None:
    result = extract_pdf_notice_text(local_path=str(TXT_FIXTURE))
    assert "not_a_pdf_missing_magic_bytes" in result["blocked_reasons"]


def test_pdf_extraction_path_works_with_an_injected_parser() -> None:
    """The extraction path is exercised code, not dead code waiting on a
    dependency."""
    pages = [
        "SYNTHETIC TEST FIXTURE - NOT A REAL NOTICE\n\n" + "Filler prose. " * 40,
        "ELIGIBILITY INFORMATION\n\nEligibility is limited to federally "
        "recognized Indian tribes.\n" + "More prose. " * 40,
    ]
    result = extract_pdf_notice_text(
        local_path=str(PDF_FIXTURE), page_reader=lambda _p: pages
    )
    assert result["extraction_status"] == "extracted"
    assert result["page_count"] == 2
    assert result["text_extraction_method"] == "injected_page_reader"
    assert "federally recognized" in result["text"].lower()
    assert pdf_adapter_invariant_failures(result) == []


def test_injected_pdf_page_spans_are_contiguous_and_index_the_text() -> None:
    pages = ["A" * 200 + " page one prose.", "B" * 200 + " page two prose."]
    result = extract_pdf_notice_text(
        local_path=str(PDF_FIXTURE), page_reader=lambda _p: pages
    )
    spans = result["page_spans"]
    assert [s["page"] for s in spans] == [1, 2]
    assert spans[0]["start"] == 0
    assert spans[1]["start"] == spans[0]["end"]
    assert spans[-1]["end"] == len(result["text"])
    assert "page two prose" in result["text"][spans[1]["start"] : spans[1]["end"]]


def test_non_contiguous_page_spans_fail_the_invariant() -> None:
    pages = ["A" * 200, "B" * 200]
    result = extract_pdf_notice_text(
        local_path=str(PDF_FIXTURE), page_reader=lambda _p: pages
    )
    forged = dict(result)
    forged["page_spans"] = [
        {"page": 1, "start": 0, "end": 100, "chars": 100},
        {"page": 2, "start": 999, "end": 1200, "chars": 200},
    ]
    assert "non_contiguous_page_span:2" in pdf_adapter_invariant_failures(forged)


def test_image_only_pdf_requires_manual_review() -> None:
    result = extract_pdf_notice_text(
        local_path=str(PDF_FIXTURE), page_reader=lambda _p: ["", "", ""]
    )
    assert result["extraction_status"] == "needs_ocr_or_manual_review"
    assert result["human_review_required"] is True
    assert result["ocr_performed"] is False
    assert "low_text_density_suggests_image_only_pdf" in result["warnings"]
    assert "ocr_not_performed_by_this_gate" in result["warnings"]
    assert pdf_adapter_invariant_failures(result) == []


def test_low_text_density_is_the_threshold_not_emptiness() -> None:
    thin = "x" * (MIN_CHARS_PER_PAGE - 10)
    result = extract_pdf_notice_text(
        local_path=str(PDF_FIXTURE), page_reader=lambda _p: [thin, thin]
    )
    assert result["extraction_status"] == "needs_ocr_or_manual_review"


def test_a_broken_pdf_parser_blocks_rather_than_crashing() -> None:
    def boom(_path: Path) -> list[str]:
        raise RuntimeError("corrupt xref")

    result = extract_pdf_notice_text(
        local_path=str(PDF_FIXTURE), page_reader=boom
    )
    assert result["extraction_status"] == "blocked"
    assert "pdf_parse_failed:RuntimeError" in result["blocked_reasons"]
    assert pdf_adapter_invariant_failures(result) == []


def test_pdf_adapter_never_claims_ocr_or_fabricated_text() -> None:
    result = extract_pdf_notice_text(local_path=str(PDF_FIXTURE))
    assert result["ocr_performed"] is False
    assert result["text_fabricated"] is False
    assert result["eligibility_claimed"] is False


# --------------------------------------------------------------------------
# Plain text / markdown / recorded transport
# --------------------------------------------------------------------------


def test_plain_text_adapter_preserves_text_verbatim() -> None:
    result = extract_plain_text_notice(local_path=str(TXT_FIXTURE))
    assert result["extraction_status"] == "extracted"
    assert result["text"] == TXT_FIXTURE.read_text(encoding="utf-8")
    assert result["text_extraction_method"] == "verbatim_read"


def test_markdown_adapter_preserves_text_verbatim() -> None:
    result = extract_plain_text_notice(
        local_path=str(MD_FIXTURE), artifact_type="markdown"
    )
    assert result["text"] == MD_FIXTURE.read_text(encoding="utf-8")
    assert result["artifact_type"] == "markdown"


def test_empty_text_file_blocks(tmp_path: Path) -> None:
    empty = tmp_path / "empty.txt"
    empty.write_text("   \n", encoding="utf-8")
    result = extract_plain_text_notice(local_path=str(empty))
    assert result["extraction_status"] == "blocked"
    assert "empty_text_file" in result["blocked_reasons"]


def test_recorded_transport_adapter_reads_a_text_field(tmp_path: Path) -> None:
    payload = tmp_path / "recorded.json"
    payload.write_text(
        json.dumps({"notice_text": "ELIGIBILITY INFORMATION\n\nTribes may apply."}),
        encoding="utf-8",
    )
    result = extract_recorded_transport_notice(local_path=str(payload))
    assert result["extraction_status"] == "extracted"
    assert result["text_extraction_method"] == "recorded_field:notice_text"


def test_recorded_transport_without_a_text_field_blocks(tmp_path: Path) -> None:
    payload = tmp_path / "recorded.json"
    payload.write_text(json.dumps({"status": 200}), encoding="utf-8")
    result = extract_recorded_transport_notice(local_path=str(payload))
    assert "no_text_field_in_recorded_transport" in result["blocked_reasons"]


def test_recorded_transport_claiming_real_fetch_is_warned(tmp_path: Path) -> None:
    payload = tmp_path / "recorded.json"
    payload.write_text(
        json.dumps({"real_fetch": True, "text": "ELIGIBILITY\n\nTribes."}),
        encoding="utf-8",
    )
    result = extract_recorded_transport_notice(local_path=str(payload))
    assert "recorded_payload_claims_real_fetch" in result["warnings"]


def test_run_text_adapter_refuses_an_unknown_type() -> None:
    with pytest.raises(ValueError, match="no adapter"):
        run_text_adapter({"artifact_type": "unknown", "local_path": "x"})


# --------------------------------------------------------------------------
# 82F — pipeline
# --------------------------------------------------------------------------


def test_pipeline_blocks_an_unknown_artifact() -> None:
    result = ingest_notice_artifact(artifact_id="a1")
    assert result["pipeline_status"] == "blocked"
    assert result["excluded_classes"] == []
    assert result["eligible_classes"] == []
    assert result["human_review_required"] is True
    assert pipeline_invariant_failures(result) == []


def test_pipeline_blocks_when_text_extraction_fails() -> None:
    if available_pdf_backends():
        pytest.skip("a PDF backend is installed; the unavailable path cannot run")
    result = ingest_notice_artifact(
        artifact_id="a1", local_path=str(PDF_FIXTURE)
    )
    assert result["pipeline_status"] == "blocked"
    assert "text_extraction_failed:blocked" in result["review_reasons"]
    assert "adapter:parser_unavailable" in result["review_reasons"]
    assert result["extraction"] is None
    assert pipeline_invariant_failures(result) == []


def test_blocked_pipeline_cannot_produce_eligibility_answers() -> None:
    result = ingest_notice_artifact(artifact_id="a1")
    forged = dict(result)
    forged["excluded_classes"] = ["federally_recognized_tribe"]
    failures = pipeline_invariant_failures(forged)
    assert "blocked_pipeline_produced_eligibility_answers" in failures


def test_end_to_end_html_produces_cited_exclusion_evidence() -> None:
    result = ingest_notice_artifact(
        artifact_id="html-1",
        local_path=str(HTML_FIXTURE),
        notice_url="https://example.test/notice",
        source_id="syn",
    )
    assert result["pipeline_status"] == "ingested"
    assert result["text_extraction_method"] == EXTRACTION_METHOD

    # The exclusive list in the eligibility section excludes the other tiers.
    assert "state_recognized_tribe" in result["excluded_classes"]
    assert "federally_recognized_tribe" in result["eligible_classes"]

    verdict = result["eligibility"]["exclusion_result"]["per_class"][
        "state_recognized_tribe"
    ]
    assert verdict["result_state"] == "excluded_by_evidence"
    assert verdict["has_citation"] is True
    assert pipeline_invariant_failures(result) == []


def test_end_to_end_html_does_not_use_script_or_hidden_text_as_evidence() -> None:
    """Both traps in the fixture would have flipped the answer."""
    result = ingest_notice_artifact(
        artifact_id="html-1",
        local_path=str(HTML_FIXTURE),
        notice_url="https://example.test/notice",
    )
    # The <script> and the hidden <div> both say state-recognized tribes are
    # eligible. The visible eligibility section says otherwise.
    assert "state_recognized_tribe" in result["excluded_classes"]
    assert "state_recognized_tribe" not in result["eligible_classes"]
    assert "also eligible" not in result["adapter_text"].lower()


def test_end_to_end_text_produces_a_class_specific_answer() -> None:
    result = ingest_notice_artifact(
        artifact_id="txt-1",
        local_path=str(TXT_FIXTURE),
        notice_url="https://example.test/notice",
    )
    assert result["pipeline_status"] == "ingested"
    assert result["eligible_classes"] == ["bie_funded_school"]
    assert "federally_recognized_tribe" in result["excluded_classes"]
    assert pipeline_invariant_failures(result) == []


def test_end_to_end_markdown_produces_amendment_evidence() -> None:
    result = ingest_notice_artifact(
        artifact_id="md-1",
        local_path=str(MD_FIXTURE),
        notice_url="https://example.test/notice",
    )
    assert result["pipeline_status"] == "ingested"
    assert result["notice_status"] == "extended"
    assert result["is_current_notice"] is True
    assert result["amendment"]["status_evidence"]
    assert result["amendment"]["status_evidence"][0]["quote"].strip()
    assert result["amendment"]["version_label"] == "3"
    assert result["amendment"]["extension_evidence"][0]["kind"] == (
        "amendment_notice_url"
    )
    assert pipeline_invariant_failures(result) == []


def test_markdown_keeps_both_recognition_tiers_eligible() -> None:
    result = ingest_notice_artifact(
        artifact_id="md-1",
        local_path=str(MD_FIXTURE),
        notice_url="https://example.test/notice",
    )
    assert "state_recognized_tribe" in result["eligible_classes"]
    assert "federally_recognized_tribe" in result["eligible_classes"]
    assert result["excluded_classes"] == []


def test_pipeline_carries_artifact_provenance() -> None:
    result = ingest_notice_artifact(
        artifact_id="html-1", local_path=str(HTML_FIXTURE)
    )
    artifact = result["artifact"]
    assert artifact["artifact_id"] == "html-1"
    assert artifact["artifact_type"] == "html"
    assert artifact["content_hash"] == content_hash_of(HTML_FIXTURE)
    assert artifact["is_recorded_fixture"] is True
    assert artifact["is_live_fetch"] is False


def test_pipeline_spans_index_the_returned_adapter_text() -> None:
    result = ingest_notice_artifact(
        artifact_id="html-1",
        local_path=str(HTML_FIXTURE),
        notice_url="https://example.test/notice",
    )
    text = result["adapter_text"]
    assert result["spans_relative_to"] == "adapter_text"
    mentions = result["eligibility"]["class_mentions"]
    assert mentions
    for mention in mentions:
        assert 0 <= mention["start"] < mention["end"] <= len(text)
    hit = mentions[0]
    assert text[hit["start"] : hit["end"]].lower() == hit["phrase"].lower()


def test_a_span_outside_the_adapter_text_fails_the_invariant() -> None:
    result = ingest_notice_artifact(
        artifact_id="html-1",
        local_path=str(HTML_FIXTURE),
        notice_url="https://example.test/notice",
    )
    forged = json.loads(json.dumps(result))
    forged["eligibility"]["class_mentions"][0]["end"] = 10**9
    assert "span_outside_adapter_text" in pipeline_invariant_failures(forged)


def test_adapter_confidence_is_never_eligibility_confidence() -> None:
    result = ingest_notice_artifact(
        artifact_id="html-1", local_path=str(HTML_FIXTURE)
    )
    assert result["adapter_confidence"] == "high"
    assert result["eligibility_confidence"] == "none"
    assert result["adapter_confidence_used_as_eligibility_confidence"] is False

    forged = dict(result)
    forged["eligibility_confidence"] = "high"
    failures = pipeline_invariant_failures(forged)
    assert "eligibility_confidence_borrowed_from_the_adapter" in failures


def test_adapter_warnings_reach_the_review_reasons() -> None:
    result = ingest_notice_artifact(
        artifact_id="html-1", local_path=str(HTML_FIXTURE)
    )
    assert result["human_review_required"] is True
    assert any(
        r.startswith("adapter_warning:hidden_text_excluded_chars")
        for r in result["review_reasons"]
    )


def test_low_adapter_confidence_flags_manual_review(tmp_path: Path) -> None:
    page = tmp_path / "thin.html"
    page.write_text("<p>Just prose with no headings at all.</p>", encoding="utf-8")
    result = ingest_notice_artifact(artifact_id="a1", local_path=str(page))
    assert result["adapter_confidence"] == "low"
    assert "adapter_low_confidence:low" in result["review_reasons"]
    assert result["human_review_required"] is True


def test_pipeline_refuses_a_live_fetched_artifact() -> None:
    result = ingest_notice_artifact(
        artifact_id="html-1", local_path=str(HTML_FIXTURE)
    )
    forged = json.loads(json.dumps(result))
    forged["artifact"]["is_live_fetch"] = True
    failures = pipeline_invariant_failures(forged)
    assert "pipeline_ingested_a_live_fetched_artifact" in failures


def test_pipeline_never_claims_coverage_monitoring_or_freshness() -> None:
    result = ingest_notice_artifact(
        artifact_id="html-1", local_path=str(HTML_FIXTURE)
    )
    assert result["live_coverage_claimed"] is False
    assert result["source_monitored"] is False
    assert result["freshness_claimed"] is False
    assert result["url_fetch_performed"] is False


# --------------------------------------------------------------------------
# Claim boundaries
# --------------------------------------------------------------------------


def test_no_gate82_module_imports_a_network_client() -> None:
    services = ROOT / "src" / "nativeforge" / "services"
    for name in GATE82_MODULES:
        body = (services / name).read_text(encoding="utf-8")
        for banned in (
            "import requests",
            "import httpx",
            "import aiohttp",
            "import urllib.request",
            "from urllib.request",
            "urlopen",
        ):
            assert banned not in body, f"{name} must not reach the network"


def test_no_gate82_module_imports_a_live_fetch_service() -> None:
    """The five live-fetch modules found in the Gate 82A survey."""
    services = ROOT / "src" / "nativeforge" / "services"
    hazards = (
        "polite_http_fetch_service",
        "grants_gov_search_api_adapter_service",
        "real_url_resolver_service",
    )
    for name in GATE82_MODULES:
        body = (services / name).read_text(encoding="utf-8")
        for hazard in hazards:
            assert hazard not in body, f"{name} must not import {hazard}"


def test_no_gate82_module_claims_live_coverage_or_an_improvement() -> None:
    services = ROOT / "src" / "nativeforge" / "services"
    for name in GATE82_MODULES:
        body = (services / name).read_text(encoding="utf-8").lower()
        assert "65%" not in body
        assert "live coverage" not in body


def test_readiness_doc_still_claims_no_coverage() -> None:
    doc = ROOT / "docs" / "operations" / "459_GATE82_PRODUCTION_READINESS_DELTA.md"
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


def test_no_pdf_or_html_dependency_was_added() -> None:
    """This gate must not have quietly grown a dependency."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8").lower()
    for pkg in ("pypdf", "pdfminer", "pdfplumber", "pymupdf", "beautifulsoup", "lxml"):
        assert pkg not in pyproject, f"{pkg} appeared in pyproject.toml"
