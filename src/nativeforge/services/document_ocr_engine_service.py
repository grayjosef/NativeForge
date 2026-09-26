"""Bounded document extraction: native first, OCR only where native failed.

Ported in mechanism from ContractForge ``10dcc5ba`` (``ocr_recovery.py``,
``parse_text.py``). The engine call is three lines; the bounds, the routing and
the honesty about failure are the part worth copying.

## What is deliberately NOT ported: the five-page ceiling

ContractForge OCRs ``min(len(pdf), 5)`` pages and stops, on the reasoning that
"OCR reads the *front* of a document, which is where the identifying content
is". That is true of a contract award notice. It is false of a grant
solicitation, and its own architecture note lists the ceiling under "known
limitations".

NativeForge reads NOFOs. The facts that decide whether a Tribe may apply are
routinely *not* at the front:

    eligibility appendices        definitions of "eligible applicant"
    cost-share / match sections   preference and set-aside language
    evaluation criteria           amendments appended to the original notice

A five-page ceiling on a sixty-page NOFO does not merely lose information. It
produces a document that *looks* fully read - status ``extracted``, text
present, no error - while the eligibility appendix on page 41 was never
rendered. Downstream that becomes "no Tribal eligibility found", which is a
fabricated negative.

So the ceiling becomes a **budget**, and exhausting the budget is a reportable
state rather than a silent stop:

    pages OCR'd            max_ocr_pages
    wall-clock OCR         max_ocr_seconds (whole document)
    per-page wall-clock    ocr_timeout_seconds (one tesseract call)

When a budget is exhausted with pages still unread, the result is ``PARTIAL``
and ``pages_unread`` says how many. ``PARTIAL`` is never ``EXTRACTED``, and the
closure layer above refuses to let a ``PARTIAL`` material document support a
final negative conclusion.

## Native first, per page, not per document

ContractForge decides native-vs-OCR once for the whole document on a 40-char
threshold. That is right for a document that is either born-digital or scanned.
Real solicitations are frequently **mixed**: a born-digital NOFO with scanned
signature pages, or a digital cover with a photocopied appendix bolted on.

Judged per document, a mixed file passes the 40-char test on its digital pages
and the scanned appendix is never OCR'd - the same fabricated-negative shape as
the page ceiling. So the decision is made **per page**, and the result records
which method produced each page.

## Empty is not failed, and unread is neither

    EXTRACTED        every page was read; text was found
    EMPTY_CONFIRMED  every page was read; there was genuinely nothing to read
    PARTIAL          some pages were not read - budget, timeout or page failure
    FAILED           the document could not be opened at all
    UNSUPPORTED      we have no parser for this media type

``EMPTY_CONFIRMED`` is the only one of these that may support "the funder
imposed no such requirement", and it may do so only because every page was
actually rendered and inspected. That distinction is the entire reason this
module reports pages rather than a single string.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ── extraction states ────────────────────────────────────────────────────────

STATUS_EXTRACTED = "EXTRACTED"
STATUS_EMPTY_CONFIRMED = "EMPTY_CONFIRMED"
STATUS_PARTIAL = "PARTIAL"
STATUS_FAILED = "FAILED"
STATUS_UNSUPPORTED = "UNSUPPORTED"

#: Only this status may support "the funder imposed no such requirement".
#: Named so the closure layer cannot get the rule subtly wrong by re-deriving it.
ABSENCE_CAPABLE_STATUSES = frozenset({STATUS_EXTRACTED, STATUS_EMPTY_CONFIRMED})

# ── per-page extraction methods ──────────────────────────────────────────────

METHOD_NATIVE = "native"
METHOD_OCR = "ocr"
METHOD_UNREAD = "unread"
METHOD_FAILED = "failed"

#: Document-level labels, derived from the page mix rather than asserted.
DOC_METHOD_NATIVE_PDF = "native_pdf"
DOC_METHOD_OCR_PDF = "ocr_pdf"
DOC_METHOD_MIXED_PDF = "mixed_pdf"
DOC_METHOD_OCR_IMAGE = "ocr_image"
DOC_METHOD_NONE = "none"


@dataclass(frozen=True, slots=True)
class OcrLimits:
    """Resource budgets. Exhausting one is a reportable state, not a silent stop."""

    #: Below ~2x, tesseract accuracy falls off badly on 8-10pt procurement type.
    render_scale: float = 2.0

    #: Wall-clock ceiling for ONE tesseract invocation.
    #:
    #: Pixel bounds limit MEMORY; they do not limit TIME. OCR cost is driven by
    #: glyph density and noise, not area, so an image comfortably inside the
    #: pixel budget can still occupy a worker for minutes. Without this, a batch
    #: of such pages is a queue-exhaustion vector that every size-based bound
    #: passes. pytesseract raises when the subprocess is killed.
    ocr_timeout_seconds: int = 45

    #: Whole-document OCR wall clock. The per-page timeout bounds one page; this
    #: bounds the document, so forty slow pages cannot serially consume forty
    #: times the per-page budget.
    max_ocr_seconds: float = 300.0

    #: How many pages may be OCR'd. Replaces ContractForge's hard ceiling of 5.
    max_ocr_pages: int = 40

    #: How many pages native extraction will walk. Cheap, so far higher.
    max_native_pages: int = 500

    #: A page with fewer than this many native characters is treated as scanned
    #: and sent to OCR. Per PAGE, not per document - see the module docstring.
    min_page_native_chars: int = 40

    #: A page whose native text is mostly non-alphanumeric is scan noise dressed
    #: as text. ContractForge's doc_enrichment layer uses the same ratio.
    low_quality_alnum_ratio: float = 0.15

    #: Document-level floor for "OCR found text" rather than "OCR found noise".
    min_text_chars: int = 40

    #: Caps what reaches the database.
    max_text_chars: int = 250_000

    #: Encoded ceiling for a single image handed to OCR.
    max_image_bytes: int = 25 * 1024 * 1024

    #: Ask tesseract for real per-word confidence via image_to_data. The export
    #: derives confidence from character ratios instead and says so in its
    #: limitations; a heuristic and an engine measurement are different claims
    #: and must not share a field.
    collect_word_confidence: bool = True

    def __post_init__(self) -> None:
        """Refuse a configuration that would disable a load-bearing bound.

        ``pytesseract`` treats ``timeout=0`` as NO timeout, so a zero here does
        not tighten the bound - it removes it, silently, in the one place that
        protects against queue exhaustion. Worse, the resulting read looks
        ordinary: a page that should have failed comes back empty, and an empty
        page that was never really read is how EMPTY_CONFIRMED gets awarded to a
        document nobody inspected. Measured, not assumed, includes measuring
        that the instrument was switched on.
        """
        if self.ocr_timeout_seconds <= 0:
            raise ValueError(
                "ocr_timeout_seconds must be positive: pytesseract treats 0 as "
                "no timeout, which removes the bound instead of tightening it"
            )
        if self.max_ocr_pages < 0 or self.max_ocr_seconds < 0:
            raise ValueError("OCR budgets must not be negative")
        if self.render_scale <= 0:
            raise ValueError("render_scale must be positive")


@dataclass(frozen=True, slots=True)
class PageExtraction:
    """What happened to one page. The unit of provenance."""

    page_number: int  # 1-based, as a human would cite it
    method: str
    text: str = ""
    native_chars: int = 0
    ocr_chars: int = 0
    ocr_confidence: float | None = None
    ocr_seconds: float | None = None
    failure_reason: str | None = None

    @property
    def was_read(self) -> bool:
        """Whether this page was actually inspected, whatever it turned out to hold."""
        return self.method in (METHOD_NATIVE, METHOD_OCR)


@dataclass(frozen=True, slots=True)
class DocumentExtraction:
    """The document-level result, derived from pages rather than asserted."""

    status: str
    text: str
    extraction_method: str
    pages: tuple[PageExtraction, ...] = ()
    page_count: int = 0
    error: str | None = None
    budget_exhausted: bool = False
    ocr_seconds: float = 0.0
    engine: str | None = None
    engine_version: str | None = None
    extractor_version: str = "nf-ocr-1"
    measured: dict[str, Any] = field(default_factory=dict)

    @property
    def pages_read(self) -> int:
        return sum(1 for p in self.pages if p.was_read)

    @property
    def pages_unread(self) -> int:
        return self.page_count - self.pages_read

    @property
    def pages_native(self) -> int:
        return sum(1 for p in self.pages if p.method == METHOD_NATIVE)

    @property
    def pages_ocr(self) -> int:
        return sum(1 for p in self.pages if p.method == METHOD_OCR)

    @property
    def absence_is_meaningful(self) -> bool:
        """May a missing fact in this document be read as the funder imposing none?

        Only when every page was actually read. A PARTIAL document has pages
        nobody inspected, so nothing can be concluded from what it does not say.
        """
        return self.status in ABSENCE_CAPABLE_STATUSES and self.pages_unread == 0


def _alnum_ratio(text: str) -> float:
    if not text:
        return 0.0
    return sum(1 for ch in text if ch.isalnum()) / len(text)


def page_needs_ocr(native_text: str, limits: OcrLimits) -> bool:
    """Whether this page's native text is too thin or too noisy to trust.

    A scanned page still 'extracts' successfully with pypdf - it just returns
    almost nothing. Treating a near-empty native extract as success is how
    scanned documents silently become empty records.
    """
    stripped = (native_text or "").strip()
    if len(stripped) < limits.min_page_native_chars:
        return True
    return _alnum_ratio(stripped) < limits.low_quality_alnum_ratio


def normalize_ocr_text(text: str, max_chars: int) -> str:
    lines = [ln.strip() for ln in (text or "").splitlines()]
    out = "\n".join(ln for ln in lines if ln)
    return out[:max_chars] if len(out) > max_chars else out


def tesseract_version() -> str | None:
    try:
        import pytesseract

        return str(pytesseract.get_tesseract_version())
    except Exception:  # noqa: BLE001 - absence is a fact, not an error
        return None


def ocr_image_to_text(image: Any, limits: OcrLimits) -> tuple[str, float | None]:
    """One tesseract call. Returns (text, mean word confidence or None).

    Confidence comes from ``image_to_data`` when asked for, which is tesseract's
    own measurement. It is deliberately separate from any text-quality heuristic:
    conflating an engine confidence with a derived score produces a number that
    means neither.
    """
    import pytesseract

    if not limits.collect_word_confidence:
        raw = pytesseract.image_to_string(image, timeout=limits.ocr_timeout_seconds)
        return raw or "", None

    data = pytesseract.image_to_data(
        image,
        timeout=limits.ocr_timeout_seconds,
        output_type=pytesseract.Output.DICT,
    )
    words: list[str] = []
    confidences: list[float] = []
    for word, conf in zip(data.get("text", []), data.get("conf", []), strict=False):
        if not str(word).strip():
            continue
        words.append(str(word))
        try:
            value = float(conf)
        except (TypeError, ValueError):
            continue
        # tesseract uses -1 for "no confidence available"; averaging it in would
        # drag a good page's score down for words it simply did not score.
        if value >= 0:
            confidences.append(value)
    text = " ".join(words)
    mean = sum(confidences) / len(confidences) if confidences else None
    return text, mean
