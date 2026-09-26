"""Document extraction: native first, per page, OCR only what native could not read.

The routing decisions live here; the bounds and the tesseract call live in
``document_ocr_engine``. Ported in mechanism from ContractForge ``10dcc5ba``
(``parse_text.py``), with the two changes argued in the engine module's
docstring: the page ceiling becomes a budget, and the native-vs-OCR decision is
made per page rather than per document.
"""

from __future__ import annotations

import time
from io import BytesIO
from typing import Any

from nativeforge.services.document_image_bounds_service import (
    ImageBounds,
    ImageRejected,
    guard_image,
    log_rejection,
    safe_render_scale,
)
from nativeforge.services.document_ocr_engine_service import (
    DOC_METHOD_MIXED_PDF,
    DOC_METHOD_NATIVE_PDF,
    DOC_METHOD_NONE,
    DOC_METHOD_OCR_IMAGE,
    DOC_METHOD_OCR_PDF,
    METHOD_FAILED,
    METHOD_NATIVE,
    METHOD_OCR,
    METHOD_UNREAD,
    STATUS_EMPTY_CONFIRMED,
    STATUS_EXTRACTED,
    STATUS_FAILED,
    STATUS_PARTIAL,
    DocumentExtraction,
    OcrLimits,
    PageExtraction,
    normalize_ocr_text,
    ocr_image_to_text,
    page_needs_ocr,
    tesseract_version,
)
from nativeforge.services.document_text_sanitization_service import (
    sanitize_postgres_text,
)


def _failed(error: str, *, pages: int = 0, measured: dict[str, Any] | None = None):
    page_rows: tuple[PageExtraction, ...] = ()
    if pages:
        page_rows = tuple(
            PageExtraction(
                page_number=i + 1, method=METHOD_FAILED, failure_reason=error
            )
            for i in range(pages)
        )
    return DocumentExtraction(
        status=STATUS_FAILED,
        text="",
        extraction_method=DOC_METHOD_NONE,
        pages=page_rows,
        page_count=pages,
        error=error,
        engine="tesseract",
        engine_version=tesseract_version(),
        measured=measured or {},
    )


def _native_pdf_pages(
    content: bytes, limits: OcrLimits
) -> tuple[list[str], int, str | None]:
    """Native text per page. Cheap, tried first, never trusted blindly."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return [], 0, "pdf_backend_unavailable: pypdf is not installed"

    try:
        reader = PdfReader(BytesIO(content))
    except Exception as exc:  # noqa: BLE001
        return [], 0, f"pdf_open_failed: {exc}"

    try:
        total = len(reader.pages)
    except Exception as exc:  # noqa: BLE001
        return [], 0, f"pdf_page_count_failed: {exc}"

    texts: list[str] = []
    for index in range(min(total, limits.max_native_pages)):
        try:
            texts.append(reader.pages[index].extract_text() or "")
        except Exception:  # noqa: BLE001
            # One unreadable page is not a failed document. It becomes a page
            # with no native text, which sends it to OCR like any scan.
            texts.append("")
    return texts, total, None


def extract_pdf_bytes(
    content: bytes, limits: OcrLimits | None = None
) -> DocumentExtraction:
    lim = limits or OcrLimits()
    native_texts, page_count, native_error = _native_pdf_pages(content, lim)

    if native_error and not native_texts:
        return _failed(native_error)
    if page_count == 0:
        return _failed("pdf_no_pages: the document reports zero pages")

    needs_ocr = [i for i, text in enumerate(native_texts) if page_needs_ocr(text, lim)]
    #: Pages beyond the native budget were never looked at by either pass.
    unseen = list(range(len(native_texts), page_count))

    pages: dict[int, PageExtraction] = {}
    for index, text in enumerate(native_texts):
        if index in needs_ocr:
            continue
        clean = sanitize_postgres_text(text) or ""
        pages[index] = PageExtraction(
            page_number=index + 1,
            method=METHOD_NATIVE,
            text=clean,
            native_chars=len(clean.strip()),
        )

    ocr_seconds = 0.0
    budget_exhausted = False
    queued = list(needs_ocr)
    pdf_doc: Any = None

    if queued:
        try:
            import pypdfium2 as pdfium

            pdf_doc = pdfium.PdfDocument(content)
        except Exception as exc:  # noqa: BLE001
            # Native pages still stand. The scanned ones become failed pages,
            # which makes the document PARTIAL - not failed, and not empty.
            for index in queued:
                pages[index] = PageExtraction(
                    page_number=index + 1,
                    method=METHOD_FAILED,
                    native_chars=len((native_texts[index] or "").strip()),
                    failure_reason=f"ocr_render_unavailable: {exc}",
                )
            queued = []

    if pdf_doc is not None:
        started = time.monotonic()
        attempted = 0
        for index in queued:
            over_pages = attempted >= lim.max_ocr_pages
            over_time = (time.monotonic() - started) >= lim.max_ocr_seconds
            if over_pages or over_time:
                budget_exhausted = True
                break
            attempted += 1
            page_started = time.monotonic()
            try:
                page = pdf_doc[index]
                scale = safe_render_scale(
                    float(getattr(page, "get_width", lambda: 612.0)()),
                    float(getattr(page, "get_height", lambda: 792.0)()),
                    lim.render_scale,
                )
                image = page.render(scale=scale).to_pil()
            except Exception as exc:  # noqa: BLE001
                pages[index] = PageExtraction(
                    page_number=index + 1,
                    method=METHOD_FAILED,
                    failure_reason=f"ocr_render_failed: {exc}",
                )
                continue
            try:
                raw, confidence = ocr_image_to_text(image, lim)
            except Exception as exc:  # noqa: BLE001
                # Includes the per-page timeout. pytesseract raises when the
                # subprocess is killed, so a pathological page fails as an
                # ordinary page instead of hanging the document.
                pages[index] = PageExtraction(
                    page_number=index + 1,
                    method=METHOD_FAILED,
                    failure_reason=f"ocr_failed: {exc}",
                    ocr_seconds=round(time.monotonic() - page_started, 3),
                )
                continue
            clean = (
                sanitize_postgres_text(normalize_ocr_text(raw, lim.max_text_chars))
                or ""
            )
            pages[index] = PageExtraction(
                page_number=index + 1,
                method=METHOD_OCR,
                text=clean,
                native_chars=len((native_texts[index] or "").strip()),
                ocr_chars=len(clean.strip()),
                ocr_confidence=confidence,
                ocr_seconds=round(time.monotonic() - page_started, 3),
            )
        ocr_seconds = round(time.monotonic() - started, 3)
        try:
            pdf_doc.close()
        except Exception:  # noqa: BLE001
            pass

    # Anything still unaccounted for was never inspected. Recording it is the
    # point: pages_unread is what stops a budget stop from looking like a
    # complete read.
    for index in queued:
        if index not in pages:
            pages[index] = PageExtraction(
                page_number=index + 1,
                method=METHOD_UNREAD,
                native_chars=len((native_texts[index] or "").strip()),
                failure_reason="ocr_budget_exhausted",
            )
            budget_exhausted = True
    for index in unseen:
        pages[index] = PageExtraction(
            page_number=index + 1,
            method=METHOD_UNREAD,
            failure_reason="native_page_budget_exhausted",
        )
        budget_exhausted = True

    ordered = tuple(pages[i] for i in sorted(pages))
    joined = "\n\n".join(p.text for p in ordered if p.text.strip())
    combined = (sanitize_postgres_text(joined) or "")[: lim.max_text_chars]

    n_native = sum(1 for p in ordered if p.method == METHOD_NATIVE)
    n_ocr = sum(1 for p in ordered if p.method == METHOD_OCR)
    unread = page_count - sum(1 for p in ordered if p.was_read)

    if n_native and n_ocr:
        method = DOC_METHOD_MIXED_PDF
    elif n_ocr:
        method = DOC_METHOD_OCR_PDF
    elif n_native:
        method = DOC_METHOD_NATIVE_PDF
    else:
        method = DOC_METHOD_NONE

    if unread > 0:
        status = STATUS_PARTIAL
        error = f"extraction_partial: {unread} of {page_count} pages were not read"
    elif len(combined.strip()) >= lim.min_text_chars:
        status, error = STATUS_EXTRACTED, None
    elif combined.strip():
        # Every page was read and something was found, just not enough to call
        # it text. Still a complete read, so absence stays meaningful.
        status, error = STATUS_EMPTY_CONFIRMED, "extraction_below_min_text_chars"
    else:
        status, error = STATUS_EMPTY_CONFIRMED, "extraction_no_text_found"

    return DocumentExtraction(
        status=status,
        text=combined,
        extraction_method=method,
        pages=ordered,
        page_count=page_count,
        error=error,
        budget_exhausted=budget_exhausted,
        ocr_seconds=ocr_seconds,
        engine="tesseract",
        engine_version=tesseract_version(),
        measured={"pages_native": n_native, "pages_ocr": n_ocr, "pages_unread": unread},
    )


def extract_image_bytes(
    content: bytes, limits: OcrLimits | None = None
) -> DocumentExtraction:
    """OCR one image, bounded before decode."""
    lim = limits or OcrLimits()
    try:
        guard_image(content, ImageBounds(max_encoded_bytes=lim.max_image_bytes))
    except ImageRejected as rejected:
        log_rejection(rejected, context="extract_image_bytes")
        # A refused image is FAILED, never EMPTY. Nobody may read "we would not
        # open this" as "there was nothing in it".
        return _failed(
            f"image_rejected: {rejected.reason}", pages=1, measured=rejected.measured
        )

    started = time.monotonic()
    try:
        from PIL import Image

        with Image.open(BytesIO(content)) as im:
            raw, confidence = ocr_image_to_text(im.convert("RGB"), lim)
    except Exception as exc:  # noqa: BLE001
        return _failed(f"ocr_image_failed: {exc}", pages=1)

    elapsed = round(time.monotonic() - started, 3)
    clean = sanitize_postgres_text(normalize_ocr_text(raw, lim.max_text_chars)) or ""
    enough = len(clean.strip()) >= lim.min_text_chars
    return DocumentExtraction(
        status=STATUS_EXTRACTED if enough else STATUS_EMPTY_CONFIRMED,
        text=clean,
        extraction_method=DOC_METHOD_OCR_IMAGE,
        pages=(
            PageExtraction(
                page_number=1,
                method=METHOD_OCR,
                text=clean,
                ocr_chars=len(clean.strip()),
                ocr_confidence=confidence,
                ocr_seconds=elapsed,
            ),
        ),
        page_count=1,
        error=None if enough else "extraction_no_text_found",
        ocr_seconds=elapsed,
        engine="tesseract",
        engine_version=tesseract_version(),
        measured={"pages_native": 0, "pages_ocr": 1, "pages_unread": 0},
    )
