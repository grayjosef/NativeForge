# 457 — Gate 82D: PDF notice text adapter

`src/nativeforge/services/pdf_notice_text_adapter_service.py`
Schema `nf_pdf_notice_text_adapter_v1`.

Extracts text from a **local** PDF path.

## The honest state of this adapter today

**No PDF parser is installed, so every real call returns `parser_unavailable`
and blocks.**

```text
pypdf MISSING   PyPDF2 MISSING   fitz MISSING
pdfminer MISSING   pdfplumber MISSING
```

Declared runtime dependencies are FastAPI, Uvicorn, SQLAlchemy, Alembic,
psycopg, pydantic-settings and PyJWT. Nothing reads a PDF.

This is a deliberate outcome, not an oversight. Two alternatives were considered
and rejected:

**Adding a dependency.** Out of scope for this gate, and it would touch
`uv.lock` and `pyproject.toml`. A test asserts no PDF or HTML package appeared
in `pyproject.toml`, so this cannot happen quietly later either.

**Hand-rolling an extractor.** A PDF is a text-based container, so a naive
extractor over uncompressed content streams is easy to write and works on the
simplest files. It degrades to garbage everywhere else — and garbage here does
not stay garbage. It flows into Gate 81, gets sectioned, and becomes *cited
eligibility evidence* attributed to a sentence nobody wrote. An honest refusal
is strictly better than a parser that is right sometimes and confidently wrong
the rest of the time.

## The extraction path is still tested

`page_reader` is an injection seam: a callable taking a path and returning one
string per page. Tests use it to exercise assembly, page spans, low-text
detection and parser failure without any PDF dependency.

So the extraction logic is **exercised code, not dead code waiting on a
dependency**. When a backend is installed, `available_pdf_backends()` finds it
via `importlib.util.find_spec` — probing without importing, so it costs nothing
and cannot execute third-party module code as a side effect — and the same
tested path runs for real.

Known backends, most preferred first:

```text
pypdf   pypdf2   fitz   pdfplumber   pdfminer
```

## Local path only

Never opens a URL. A `local_path` that looks like one is refused:

```text
local_path_is_a_url_not_a_path
```

The file must exist and must begin with the `%PDF-` magic bytes; a text file
handed to this adapter is rejected with `not_a_pdf_missing_magic_bytes` rather
than parsed into noise.

No shelling out. No OCR. `ocr_performed`, `url_fetch_performed` and
`text_fabricated` are hardcoded `False` and invariant-checked.

## Image-only PDFs

Scanned notices are common and this gate does not OCR them. Detection is by text
density:

```text
MIN_TOTAL_CHARS      40    nothing meaningful at all
MIN_CHARS_PER_PAGE   50    per-page floor
```

Below either, the status is `needs_ocr_or_manual_review` with
`human_review_required` and two warnings:

```text
low_text_density_suggests_image_only_pdf
ocr_not_performed_by_this_gate
```

The partial text is still returned so a human can see what little was found —
but it is never presented as a complete extraction. An invariant fails an OCR
candidate that does not demand review.

## Page spans

Each page records `start`/`end` offsets into the assembled text plus its
character count, so a quote can be attributed to a page even though the
underlying document has no character offsets in the sense Gate 81 uses.

Spans must be **contiguous** — page *n* starts where page *n−1* ended — and an
invariant checks it. A gap would mean a quote could be attributed to the wrong
page, which is worse than not attributing it at all.

Pages yielding no text are counted and warned (`pages_with_no_text:n/total`).

## Failure behaviour

A backend that raises on a corrupt file blocks with
`pdf_parse_failed:<ExceptionType>` rather than propagating. A broken PDF must
not take down a caller ingesting a batch of notices, and the failure is recorded
rather than swallowed.

## Evidence span limitations

As with HTML, Gate 81 spans index the **adapter output**, not the PDF file.
There is no byte offset in a PDF that corresponds to a character in the
extracted text. Page attribution via `page_spans` is the honest granularity
available, and the pipeline records `spans_relative_to: "adapter_text"`.

## Why no live coverage is claimed

The adapter reads files somebody already has, and today it reads none of them.
It identifies no source, fetches nothing, and monitors nothing.
