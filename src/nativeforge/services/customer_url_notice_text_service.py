"""Turn a fetched response into notice text, or say honestly that it could not.

The fetcher returns bytes and a content type. Everything downstream — contact
extraction, submission path, deadlines — reads prose. This is the one step in
between, and it is separate from the fetcher because the failure modes are
completely different: the fetcher's are about *whether to open* an address,
these are about *what a document turned out to be*.

## A PDF is not text

`body.decode("utf-8", errors="replace")` on a PDF produces thousands of
replacement characters with a few legible fragments scattered through it.
Handing that to the contact extractor would not raise anything; it would
return a plausible, wrong answer, which is worse. So PDFs go through the PDF
adapter, on the raw bytes, and the adapter is allowed to say
`needs_ocr_or_manual_review` rather than guess.

## Nothing here fetches

Both adapters refuse a URL where they expect a path, and this module never
gives them one. The temporary file a PDF needs lives inside a private
directory for the length of one extraction and is removed with it.
"""

from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nativeforge.services.html_notice_text_adapter_service import (
    extract_html_notice_text,
)
from nativeforge.services.pdf_notice_text_adapter_service import (
    extract_pdf_notice_text,
)

HTML_TYPES = frozenset({"text/html", "application/xhtml+xml"})
PDF_TYPES = frozenset({"application/pdf"})
PLAIN_TYPES = frozenset({"text/plain"})


@dataclass(frozen=True)
class NoticeText:
    """Readable text, plus how much of it to believe."""

    text: str
    #: `extracted`, `needs_ocr_or_manual_review`, or `blocked`.
    status: str
    #: Which adapter produced it, for the provenance record.
    method: str
    confidence: str = "unknown"
    human_review_required: bool = True
    page_count: int | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)
    blocked_reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def usable(self) -> bool:
        """Enough text to run extraction over at all.

        `needs_ocr_or_manual_review` is deliberately included: a scanned NOFO
        with one readable cover page is still worth showing to the customer,
        as long as it arrives labelled rather than presented as complete.
        """
        return bool(self.text.strip()) and self.status != "blocked"

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "method": self.method,
            "confidence": self.confidence,
            "human_review_required": self.human_review_required,
            "page_count": self.page_count,
            "text_chars": len(self.text),
            "warnings": list(self.warnings),
            "blocked_reasons": list(self.blocked_reasons),
        }


def _blocked(reason: str, method: str = "none") -> NoticeText:
    return NoticeText(
        text="",
        status="blocked",
        method=method,
        confidence="none",
        human_review_required=True,
        blocked_reasons=(reason,),
    )


def _from_adapter(result: dict[str, Any], method: str) -> NoticeText:
    status = str(result.get("extraction_status") or "blocked")
    return NoticeText(
        text=str(result.get("text") or ""),
        status=status,
        method=method,
        confidence=str(result.get("adapter_confidence") or "unknown"),
        human_review_required=bool(result.get("human_review_required", True)),
        page_count=result.get("page_count"),
        warnings=tuple(result.get("warnings") or ()),
        blocked_reasons=tuple(result.get("blocked_reasons") or ()),
    )


def _collapse(text: str) -> str:
    text = re.sub(r"[ \t\x0b\f\r]+", " ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n" if text.strip() else ""


def notice_text_from_response(*, content_type: str, content_bytes: bytes) -> NoticeText:
    """Read one fetched document. Never opens anything."""
    kind = (content_type or "").split(";", 1)[0].strip().lower()

    if not content_bytes:
        return _blocked("empty_response_body")

    if kind in PDF_TYPES:
        return _pdf(content_bytes)

    if kind in HTML_TYPES:
        decoded = content_bytes.decode("utf-8", errors="replace")
        return _from_adapter(
            extract_html_notice_text(html=decoded), "stdlib_html_parser"
        )

    if kind in PLAIN_TYPES:
        decoded = _collapse(content_bytes.decode("utf-8", errors="replace"))
        if not decoded.strip():
            return _blocked("no_text_after_extraction", "plain_text")
        return NoticeText(
            text=decoded,
            status="extracted",
            method="plain_text",
            confidence="medium",
            # Plain text has no headings to section on, so the extractor is
            # working with less structure than it gets from a notice page.
            human_review_required=True,
        )

    # The fetcher's allow-list is the gate; this is the disagreement case, and
    # guessing at an unexpected type is exactly what the allow-list is for.
    return _blocked(f"content_type_not_readable:{kind or 'unknown'}")


def _pdf(content_bytes: bytes) -> NoticeText:
    """Write the bytes down just long enough for the adapter to read them.

    The adapter takes a path because it drives page-oriented backends, so a
    file is unavoidable. `TemporaryDirectory` is created 0700 and removed on
    exit, including when extraction raises.
    """
    try:
        with tempfile.TemporaryDirectory(prefix="nf-url-notice-") as tmp:
            path = Path(tmp) / "document.pdf"
            path.write_bytes(content_bytes)
            result = extract_pdf_notice_text(local_path=path)
    except OSError as exc:
        return _blocked(f"could_not_stage_document:{type(exc).__name__}", "pdf")

    return _from_adapter(result, "pdf_text_extraction")
