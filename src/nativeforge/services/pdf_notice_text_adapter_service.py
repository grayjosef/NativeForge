"""PDF notice text adapter (Gate 82D).

Extracts text from a **local** PDF path. Never opens a URL.

## The honest state of this adapter

No PDF parser is installed in this project. Declared runtime dependencies are
FastAPI, Uvicorn, SQLAlchemy, Alembic, psycopg, pydantic-settings and PyJWT;
``pypdf``, ``PyPDF2``, ``fitz``, ``pdfminer`` and ``pdfplumber`` are all absent.

So today every call returns ``parser_unavailable`` and blocks. That is
deliberate. Two alternatives were rejected:

  * **Adding a dependency.** Out of scope for this gate, and it would touch
    ``uv.lock`` and ``pyproject.toml``.
  * **Hand-rolling an extractor.** A PDF is a text-based container, so a naive
    extractor that reads uncompressed content streams is easy to write and
    works on the simplest files. It degrades to garbage everywhere else - and
    garbage here does not stay garbage. It flows into Gate 81, gets sectioned,
    and becomes *cited eligibility evidence* attributed to a sentence nobody
    wrote. An honest refusal is strictly better than a parser that is right
    sometimes and confidently wrong the rest of the time.

The extraction path is nonetheless written and tested, by injecting a parser.
It is exercised code, not dead code waiting on a dependency, and the moment a
backend is installed :func:`available_pdf_backends` finds it and the same path
runs for real.

Nothing here fetches, shells out, or performs OCR.
"""

from __future__ import annotations

import importlib.util
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_pdf_notice_text_adapter_v1"
ADAPTER_VERSION = "gate82_v1"

# Backends this adapter knows how to drive, most preferred first.
KNOWN_BACKENDS: tuple[str, ...] = ("pypdf", "pypdf2", "fitz", "pdfplumber", "pdfminer")

# Import name per backend, since two of them differ from their package name.
_BACKEND_MODULES: dict[str, str] = {
    "pypdf": "pypdf",
    "pypdf2": "PyPDF2",
    "fitz": "fitz",
    "pdfplumber": "pdfplumber",
    "pdfminer": "pdfminer.high_level",
}

_PDF_MAGIC = b"%PDF-"

# Below this many characters per page, a PDF is almost certainly scanned images
# rather than text. OCR is out of scope, so it goes to a human.
MIN_CHARS_PER_PAGE = 50

# Below this in total, there is effectively nothing to parse whatever the page
# count says.
MIN_TOTAL_CHARS = 40

EXTRACTION_STATUSES = frozenset(
    {"extracted", "blocked", "needs_ocr_or_manual_review"}
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def available_pdf_backends() -> list[str]:
    """Which known PDF backends are importable right now.

    Uses ``find_spec`` rather than importing, so probing costs nothing and
    cannot execute third-party module code as a side effect.
    """
    found: list[str] = []
    for name in KNOWN_BACKENDS:
        module = _BACKEND_MODULES[name]
        try:
            if importlib.util.find_spec(module) is not None:
                found.append(name)
        except (ImportError, ValueError):
            continue
    return found


def _read_pages_with_backend(path: Path, backend: str) -> list[str]:
    """Drive one backend. Only called when that backend is importable."""
    if backend in {"pypdf", "pypdf2"}:
        module = __import__(_BACKEND_MODULES[backend])
        reader = module.PdfReader(str(path))
        return [(page.extract_text() or "") for page in reader.pages]
    if backend == "fitz":
        import fitz  # type: ignore[import-not-found]

        with fitz.open(str(path)) as doc:
            return [page.get_text() or "" for page in doc]
    if backend == "pdfplumber":
        import pdfplumber  # type: ignore[import-not-found]

        with pdfplumber.open(str(path)) as doc:
            return [(page.extract_text() or "") for page in doc.pages]
    if backend == "pdfminer":
        from pdfminer.high_level import extract_text  # type: ignore[import-not-found]

        return [extract_text(str(path)) or ""]
    raise ValueError(f"unsupported backend: {backend}")


def _collapse(text: str) -> str:
    text = re.sub(r"[ \t\x0b\f\r]+", " ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n" if text.strip() else ""


def extract_pdf_notice_text(
    *,
    local_path: str | Path | None = None,
    artifact_id: str | None = None,
    backend: str | None = None,
    page_reader: Callable[[Path], list[str]] | None = None,
) -> dict[str, Any]:
    """Extract text from a local PDF.

    ``page_reader`` is an injection seam: a callable taking a path and returning
    one string per page. Tests use it to exercise the extraction, assembly,
    page-span and low-text paths without requiring a PDF dependency.
    """
    blocked_reasons: list[str] = []
    warnings: list[str] = []

    if local_path is None:
        blocked_reasons.append("missing_local_path")
        return _blocked(artifact_id, blocked_reasons, warnings, None)

    candidate = str(local_path)
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", candidate):
        # A URL is not a path, and this adapter does not resolve one.
        blocked_reasons.append("local_path_is_a_url_not_a_path")
        return _blocked(artifact_id, blocked_reasons, warnings, None)

    path = Path(candidate)
    if not path.is_file():
        blocked_reasons.append("local_path_does_not_exist")
        return _blocked(artifact_id, blocked_reasons, warnings, None)

    try:
        head = path.open("rb").read(len(_PDF_MAGIC))
    except OSError as exc:
        blocked_reasons.append(f"could_not_read_local_path:{type(exc).__name__}")
        return _blocked(artifact_id, blocked_reasons, warnings, None)

    if not head.startswith(_PDF_MAGIC):
        blocked_reasons.append("not_a_pdf_missing_magic_bytes")
        return _blocked(artifact_id, blocked_reasons, warnings, None)

    backends = available_pdf_backends()
    chosen = backend or (backends[0] if backends else None)

    if page_reader is not None:
        method = "injected_page_reader"
    elif chosen is None:
        # The honest default today.
        blocked_reasons.append("parser_unavailable")
        warnings.append(f"no_pdf_backend_installed_known:{','.join(KNOWN_BACKENDS)}")
        return _blocked(artifact_id, blocked_reasons, warnings, None)
    elif chosen not in backends:
        blocked_reasons.append(f"requested_backend_unavailable:{chosen}")
        return _blocked(artifact_id, blocked_reasons, warnings, None)
    else:
        method = f"backend:{chosen}"

    reader = page_reader or (lambda p: _read_pages_with_backend(p, str(chosen)))
    try:
        pages = list(reader(path))
    except Exception as exc:  # noqa: BLE001 - a broken PDF must not crash callers
        blocked_reasons.append(f"pdf_parse_failed:{type(exc).__name__}")
        return _blocked(artifact_id, blocked_reasons, warnings, method)

    # Assemble, tracking where each page begins in the assembled text so a
    # quote can at least be attributed to a page.
    parts: list[str] = []
    page_spans: list[dict[str, Any]] = []
    cursor = 0
    for number, page_text in enumerate(pages, start=1):
        cleaned = _collapse(str(page_text or ""))
        start = cursor
        parts.append(cleaned)
        cursor += len(cleaned)
        page_spans.append(
            {
                "page": number,
                "start": start,
                "end": cursor,
                "chars": len(cleaned.strip()),
            }
        )

    text = "".join(parts)
    total_chars = len(text.strip())
    page_count = len(pages)
    per_page = total_chars / page_count if page_count else 0.0

    empty_pages = [p["page"] for p in page_spans if p["chars"] == 0]
    if empty_pages:
        warnings.append(f"pages_with_no_text:{len(empty_pages)}/{page_count}")

    # Image-only detection. OCR is deliberately out of scope, so this asks for a
    # human rather than guessing at the content.
    if total_chars < MIN_TOTAL_CHARS or (page_count and per_page < MIN_CHARS_PER_PAGE):
        return _json_safe(
            {
                **_base(artifact_id, method),
                "extraction_status": "needs_ocr_or_manual_review",
                "text": text,
                "text_chars": len(text),
                "total_text_chars": total_chars,
                "page_count": page_count,
                "chars_per_page": round(per_page, 2),
                "page_spans": page_spans,
                "available_backends": backends,
                "backend_used": chosen if page_reader is None else None,
                "adapter_confidence": "low",
                "extraction_uncertain": True,
                "human_review_required": True,
                "blocked_reasons": blocked_reasons,
                "warnings": warnings
                + [
                    "low_text_density_suggests_image_only_pdf",
                    "ocr_not_performed_by_this_gate",
                ],
            }
        )

    confidence = "high" if per_page >= 400 else "medium"

    return _json_safe(
        {
            **_base(artifact_id, method),
            "extraction_status": "extracted",
            "text": text,
            "text_chars": len(text),
            "total_text_chars": total_chars,
            "page_count": page_count,
            "chars_per_page": round(per_page, 2),
            "page_spans": page_spans,
            "available_backends": backends,
            "backend_used": chosen if page_reader is None else None,
            "adapter_confidence": confidence,
            "extraction_uncertain": bool(empty_pages),
            "human_review_required": bool(empty_pages),
            "blocked_reasons": blocked_reasons,
            "warnings": warnings,
        }
    )


def _base(artifact_id: str | None, method: str | None) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "adapter_version": ADAPTER_VERSION,
        "artifact_id": artifact_id,
        "artifact_type": "pdf",
        "text_extraction_method": method,
        # Boundaries.
        "url_fetch_performed": False,
        "ocr_performed": False,
        "text_fabricated": False,
        "eligibility_claimed": False,
        "freshness_claimed": False,
    }


def _blocked(
    artifact_id: str | None,
    blocked_reasons: list[str],
    warnings: list[str],
    method: str | None,
) -> dict[str, Any]:
    return _json_safe(
        {
            **_base(artifact_id, method),
            "extraction_status": "blocked",
            "text": "",
            "text_chars": 0,
            "total_text_chars": 0,
            "page_count": 0,
            "chars_per_page": 0.0,
            "page_spans": [],
            "available_backends": available_pdf_backends(),
            "backend_used": None,
            "adapter_confidence": "none",
            "extraction_uncertain": True,
            "human_review_required": True,
            "blocked_reasons": blocked_reasons,
            "warnings": warnings,
        }
    )


def pdf_adapter_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    status = result.get("extraction_status")
    if status not in EXTRACTION_STATUSES:
        fails.append(f"unknown_extraction_status:{status}")

    if status == "blocked":
        if not result.get("blocked_reasons"):
            fails.append("blocked_without_a_reason")
        if result.get("text"):
            fails.append("blocked_result_carried_text")

    if status == "extracted":
        if not str(result.get("text") or "").strip():
            fails.append("extracted_result_without_text")
        if not result.get("text_extraction_method"):
            fails.append("extraction_method_not_declared")
        if not result.get("page_spans"):
            fails.append("extracted_result_without_page_spans")

    if status == "needs_ocr_or_manual_review" and not result.get(
        "human_review_required"
    ):
        fails.append("ocr_candidate_without_human_review")

    # Page spans must be contiguous and valid, or a quote cannot be attributed
    # to a page at all.
    cursor = 0
    for span in result.get("page_spans") or []:
        start, end = span.get("start"), span.get("end")
        if not isinstance(start, int) or not isinstance(end, int) or end < start:
            fails.append(f"invalid_page_span:{span.get('page')}")
            break
        if start != cursor:
            fails.append(f"non_contiguous_page_span:{span.get('page')}")
            break
        cursor = end

    if result.get("extraction_uncertain") and not result.get("human_review_required"):
        fails.append("uncertain_extraction_without_human_review")

    for forbidden in (
        "url_fetch_performed",
        "ocr_performed",
        "text_fabricated",
        "eligibility_claimed",
        "freshness_claimed",
    ):
        if result.get(forbidden) is not False:
            fails.append(f"forbidden_claim:{forbidden}")

    return fails
