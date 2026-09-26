"""Gate 182: bounded OCR, and the states it is allowed to claim.

The engine call is three lines. Everything that matters here is the bounds
around it and the honesty about what was not read.

The rule this gate defends, in one sentence: **a document nobody finished
reading may never be used to prove that something is absent.** NativeForge
already encodes that as ``ABSENCE_IS_MEANINGFUL = {PARSED}`` in
``opportunity_document_service``; these tests prove the extractor cannot
smuggle a half-read document into that state.

Fixtures are committed rather than generated. A generated corpus depends on
the fonts present wherever the tests happen to run, and the slim container
image carries none - synthetic pages render at ~11px in Pillow's default
bitmap font and OCR poorly, which would look like an engine regression and is
not one.
"""

from __future__ import annotations

import pathlib

import pytest

from nativeforge.services.document_extraction_service import (
    extract_image_bytes,
    extract_pdf_bytes,
)
from nativeforge.services.document_ocr_engine_service import (
    METHOD_FAILED,
    METHOD_NATIVE,
    METHOD_OCR,
    STATUS_EMPTY_CONFIRMED,
    STATUS_EXTRACTED,
    STATUS_FAILED,
    STATUS_PARTIAL,
    OcrLimits,
)
from nativeforge.services.document_text_sanitization_service import (
    sanitize_postgres_text,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "document_ocr"

#: The sentence that decides whether a Tribe may apply. Matched lowercase:
#: OCR does not preserve case reliably.
DECISIVE = "eligible applicants"


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


# ── native first ─────────────────────────────────────────────────────────────


def test_born_digital_pdf_is_read_natively_without_ocr() -> None:
    result = extract_pdf_bytes(fixture("native_text.pdf"))
    assert result.status == STATUS_EXTRACTED
    assert result.measured["pages_ocr"] == 0
    assert DECISIVE in result.text.lower()


def test_native_extraction_supports_meaningful_absence() -> None:
    result = extract_pdf_bytes(fixture("native_text.pdf"))
    assert result.pages_unread == 0
    assert result.absence_is_meaningful is True


# ── OCR fallback ─────────────────────────────────────────────────────────────


def test_a_scanned_pdf_falls_back_to_ocr() -> None:
    result = extract_pdf_bytes(fixture("scanned_page1.pdf"))
    assert result.status == STATUS_EXTRACTED
    assert result.extraction_method == "ocr_pdf"
    assert DECISIVE in result.text.lower()


def test_ocr_records_real_engine_confidence() -> None:
    """From ``image_to_data``, not from a character-ratio heuristic.

    An engine measurement and a derived score are different claims and must
    not share a field.
    """
    result = extract_pdf_bytes(fixture("scanned_page1.pdf"))
    confidence = result.pages[0].ocr_confidence
    assert confidence is not None
    assert 0.0 <= confidence <= 100.0


# ── the case a five-page ceiling cannot read ─────────────────────────────────


def test_decisive_text_on_page_seven_is_found() -> None:
    """An eligibility appendix deep in a scanned NOFO.

    ContractForge OCRs the first five pages and stops, on the reasoning that
    the identifying content is at the front of a document. That holds for an
    award notice and fails for a solicitation: eligibility appendices, match
    requirements and amendments sit at the back.
    """
    result = extract_pdf_bytes(fixture("scanned_decisive_page7.pdf"))
    assert result.pages_unread == 0
    assert DECISIVE in result.text.lower()

    page_seven = next(p for p in result.pages if p.page_number == 7)
    assert page_seven.method == METHOD_OCR
    assert DECISIVE in page_seven.text.lower()


def test_a_five_page_budget_misses_it_and_says_so() -> None:
    """The miss is the point: it must be reported, not silently absorbed.

    Under a five-page budget the decisive sentence is not found - and the
    document is PARTIAL with unread pages counted, so nothing downstream may
    read its silence as evidence.
    """
    result = extract_pdf_bytes(
        fixture("scanned_decisive_page7.pdf"), OcrLimits(max_ocr_pages=5)
    )
    assert DECISIVE not in result.text.lower()
    assert result.status == STATUS_PARTIAL
    assert result.pages_unread == 3
    assert result.absence_is_meaningful is False


# ── mixed documents ──────────────────────────────────────────────────────────


def test_mixed_document_routes_per_page() -> None:
    """A born-digital cover with a scanned appendix bolted on.

    Judged per document, this passes a native-text test on its digital page
    and the appendix is never rendered. The decision is per page.
    """
    result = extract_pdf_bytes(fixture("mixed_native_and_scan.pdf"))
    assert result.extraction_method == "mixed_pdf"
    assert result.measured["pages_native"] == 1
    assert result.measured["pages_ocr"] == 1
    assert DECISIVE in result.text.lower()


# ── failure is never emptiness ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "name",
    ["corrupt.pdf", "pixel_bomb.png", "pixel_budget_bomb.png", "extreme_aspect.png"],
)
def test_a_document_we_could_not_read_is_failed_not_empty(name: str) -> None:
    data = fixture(name)
    result = (
        extract_pdf_bytes(data) if name.endswith(".pdf") else extract_image_bytes(data)
    )
    assert result.status == STATUS_FAILED
    assert result.absence_is_meaningful is False


def test_the_pixel_bomb_is_refused_on_declared_geometry() -> None:
    """Before decode. 60000 x 60000 is caught by the cheaper dimension bound."""
    result = extract_image_bytes(fixture("pixel_bomb.png"))
    assert "dimension_exceeded" in (result.error or "")


def test_the_pixel_budget_bound_catches_what_dimension_does_not() -> None:
    """20000 x 20000 passes max_dimension and still declares 400 megapixels."""
    result = extract_image_bytes(fixture("pixel_budget_bomb.png"))
    assert "pixel_budget_exceeded" in (result.error or "")


def test_a_truncated_image_fails_at_decode() -> None:
    """The guard bounds resource use; it does not certify the file.

    A truncated PNG keeps a valid signature and IHDR, so the probe succeeds on
    declared geometry and the decode is what fails. Callers must still handle
    that - which is why this is FAILED rather than empty.
    """
    result = extract_image_bytes(fixture("truncated.png"))
    assert result.status == STATUS_FAILED


# ── emptiness, when it is real ───────────────────────────────────────────────


def test_a_genuinely_blank_scan_is_empty_confirmed() -> None:
    """Every page read, nothing on them. The only clean route to absence."""
    result = extract_image_bytes(fixture("blank_scan.png"))
    assert result.status == STATUS_EMPTY_CONFIRMED
    assert result.pages_unread == 0
    assert result.absence_is_meaningful is True


# ── bounds that must not be switchable-off ───────────────────────────────────


def test_a_zero_ocr_timeout_is_refused() -> None:
    """``pytesseract`` treats ``timeout=0`` as NO timeout.

    Measured, not assumed: the benchmark that found this passed zero, tesseract
    ran unbounded, the page came back blank, and the document was awarded
    EMPTY_CONFIRMED with absence_is_meaningful=True. A disabled bound that
    produces meaningful absence is the failure this whole design exists to
    prevent, so the configuration is now unrepresentable.
    """
    with pytest.raises(ValueError, match="ocr_timeout_seconds must be positive"):
        OcrLimits(ocr_timeout_seconds=0)

    with pytest.raises(ValueError):
        OcrLimits(ocr_timeout_seconds=-1)


def test_a_fired_timeout_becomes_a_failed_page(monkeypatch: pytest.MonkeyPatch) -> None:
    """Not an empty one. pytesseract raises when it kills the subprocess."""
    import pytesseract

    def always_times_out(*args: object, **kwargs: object) -> None:
        raise RuntimeError("Tesseract process timeout")

    monkeypatch.setattr(pytesseract, "image_to_data", always_times_out)
    monkeypatch.setattr(pytesseract, "image_to_string", always_times_out)

    result = extract_pdf_bytes(
        fixture("scanned_page1.pdf"), OcrLimits(ocr_timeout_seconds=1)
    )
    assert result.pages[0].method == METHOD_FAILED
    assert result.status == STATUS_PARTIAL
    assert result.absence_is_meaningful is False


def test_the_document_time_budget_produces_partial() -> None:
    result = extract_pdf_bytes(
        fixture("scanned_decisive_page7.pdf"), OcrLimits(max_ocr_seconds=0.001)
    )
    assert result.status == STATUS_PARTIAL
    assert result.pages_unread > 0
    assert result.absence_is_meaningful is False


# ── persistence safety ───────────────────────────────────────────────────────


def test_nul_bytes_never_reach_the_database() -> None:
    """PostgreSQL ``text`` rejects embedded NUL outright, and OCR emits it."""
    raw = fixture("nul_text.txt").decode("utf-8")
    assert "\x00" in raw
    cleaned = sanitize_postgres_text(raw)
    assert cleaned is not None
    assert "\x00" not in cleaned
    assert cleaned == "eligibleapplicants"


def test_sanitisation_preserves_absence() -> None:
    assert sanitize_postgres_text(None) is None


# ── the contract downstream depends on ───────────────────────────────────────


def test_only_a_complete_read_can_support_absence() -> None:
    """The invariant, stated once, over every fixture in the corpus."""
    for name in (
        "native_text.pdf",
        "scanned_page1.pdf",
        "scanned_decisive_page7.pdf",
        "mixed_native_and_scan.pdf",
        "corrupt.pdf",
        "blank_scan.png",
        "truncated.png",
        "pixel_bomb.png",
    ):
        data = fixture(name)
        result = (
            extract_pdf_bytes(data)
            if name.endswith(".pdf")
            else extract_image_bytes(data)
        )
        if result.absence_is_meaningful:
            assert result.status in (STATUS_EXTRACTED, STATUS_EMPTY_CONFIRMED), name
            assert result.pages_unread == 0, name


def test_every_page_records_how_it_was_read() -> None:
    result = extract_pdf_bytes(fixture("mixed_native_and_scan.pdf"))
    assert len(result.pages) == result.page_count
    for page in result.pages:
        assert page.method in (METHOD_NATIVE, METHOD_OCR, METHOD_FAILED, "unread")
        assert page.page_number >= 1
