"""Grant document text extraction (Gate 91G).

Extracts text from local grant documents so obligations can be read out of them.

## This is a seam over the Gate 81/82 stack, not a second parser

Gate 91A surveyed for existing deterministic parsers and found a complete one::

    notice_artifact_model_service      artifact typing, hashing, live-fetch guard
    notice_ingestion_pipeline_service  run_text_adapter dispatch
    html_notice_text_adapter_service   stdlib HTMLParser
    pdf_notice_text_adapter_service    page-reader seam; honest parser_unavailable
    nofo_text_extraction_service       detect_sections with character spans

This module dispatches to that stack and adds nothing of its own beyond
document-shaped naming and section headings. Writing a second parser would mean
two things that could disagree about the same file, which is how a quote stops
matching its source.

## No AI, no OCR, no network

Deterministic parsers only. The same input produces the same output, byte for
byte, and a test asserts it across every supported type.

There is no model call, no embedding, no heuristic classifier - a test greps
this module's source for the obvious names. OCR is not added: the PDF adapter
already reports ``needs_ocr_or_manual_review`` where it applies, and adding OCR
would be a dependency decision rather than an extraction one.

## Unsupported is visible, never silent

No PDF backend is installed (``available_pdf_backends() == []``), so a PDF
returns ``parser_unavailable`` and ``manual_review_required``. It does **not**
return empty text and a success status. A silent fallback would let a document
with obligations in it read as a document with none.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from nativeforge.services.nofo_text_extraction_service import detect_sections
from nativeforge.services.notice_artifact_model_service import (
    build_notice_artifact,
    sniff_artifact_type,
)
from nativeforge.services.notice_ingestion_pipeline_service import run_text_adapter

SCHEMA_VERSION = "nf_grant_document_text_extraction_v1"

EXTRACTION_STATUSES = frozenset(
    {
        "extracted",
        "parser_unavailable",
        "manual_review_required",
        "blocked",
    }
)

# Artifact types this seam will dispatch. Derived from what the underlying
# adapters actually implement, so a type added upstream is unsupported here
# until someone wires it deliberately.
SUPPORTED_ARTIFACT_TYPES = frozenset(
    {"html", "plain_text", "markdown", "json_recorded_transport"}
)

# Recognised, dispatchable, and currently unable to produce text because no
# backend is installed. Kept separate from "unsupported" because the failure
# and its fix are different.
BACKEND_DEPENDENT_TYPES = frozenset({"pdf"})


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _blocked(
    *,
    document_id: str,
    status: str,
    reasons: list[str],
    parser_used: str | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "document_id": document_id,
            "text": None,
            "text_hash_sha256": None,
            "page_count": None,
            "section_headings": [],
            "extraction_status": status,
            "parser_used": parser_used,
            "warnings": list(warnings or []),
            "blocked_reasons": list(reasons),
            "evidence_spans": [],
            "ai_used": False,
            "ocr_used": False,
            "network_access_performed": False,
            "deterministic": True,
            "fabricated": False,
        }
    )


def extract_grant_document_text(
    *,
    document_id: str,
    local_path: str | Path | None = None,
    artifact_type: str | None = None,
    source_id: str | None = None,
) -> dict[str, Any]:
    """Extract text from one local grant document.

    Never fetches. A document with no local path is blocked, because this gate
    downloads nothing.
    """
    if not local_path:
        return _blocked(
            document_id=document_id,
            status="blocked",
            reasons=["no_local_path_and_no_download_in_this_gate"],
        )

    path = Path(local_path)
    if not path.is_file():
        return _blocked(
            document_id=document_id,
            status="blocked",
            reasons=["local_path_does_not_exist"],
        )

    resolved_type = artifact_type or sniff_artifact_type(path)

    if resolved_type in BACKEND_DEPENDENT_TYPES:
        # Dispatch anyway: the adapter is the authority on whether a backend
        # exists, and it reports honestly. Guessing here would duplicate that
        # judgement in a second place.
        pass
    elif resolved_type not in SUPPORTED_ARTIFACT_TYPES:
        return _blocked(
            document_id=document_id,
            status="blocked",
            reasons=[f"unsupported_artifact_type:{resolved_type}"],
        )

    artifact = build_notice_artifact(
        artifact_id=document_id,
        source_id=source_id,
        artifact_type=resolved_type,
        local_path=str(path),
    )

    if artifact.get("blocked_reasons"):
        return _blocked(
            document_id=document_id,
            status="blocked",
            reasons=list(artifact["blocked_reasons"]),
            warnings=list(artifact.get("warnings") or []),
        )

    try:
        adapter_result = run_text_adapter(artifact)
    except ValueError as exc:
        return _blocked(
            document_id=document_id,
            status="blocked",
            reasons=[f"no_adapter_for_type:{resolved_type}", str(exc)[:120]],
        )

    text = adapter_result.get("text")
    adapter_status = adapter_result.get("extraction_status")
    warnings = list(adapter_result.get("warnings") or [])
    blocked = list(adapter_result.get("blocked_reasons") or [])
    parser_used = adapter_result.get("parser_used") or adapter_result.get(
        "schema_version"
    )

    if not text:
        # The adapter could not produce text. Map its reason onto this seam's
        # vocabulary without softening it.
        if resolved_type in BACKEND_DEPENDENT_TYPES:
            status = "parser_unavailable"
            blocked.append("manual_review_required")
        elif adapter_status == "needs_ocr_or_manual_review":
            status = "manual_review_required"
        else:
            status = "blocked"
        return _blocked(
            document_id=document_id,
            status=status,
            reasons=blocked or [f"adapter_returned_no_text:{adapter_status}"],
            parser_used=parser_used,
            warnings=warnings,
        )

    sections = detect_sections(text)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "document_id": document_id,
            "text": text,
            "text_hash_sha256": _sha256(text),
            "page_count": adapter_result.get("page_count"),
            "section_headings": [
                {
                    "kind": s.get("kind"),
                    "heading": s.get("heading"),
                    "start": s.get("start"),
                    "end": s.get("end"),
                }
                for s in sections
            ],
            "extraction_status": "extracted",
            "parser_used": parser_used,
            "warnings": warnings,
            "blocked_reasons": blocked,
            # Spans, so every later quote can point at where it came from.
            "evidence_spans": [
                {
                    "kind": s.get("kind"),
                    "start": s.get("start"),
                    "end": s.get("end"),
                }
                for s in sections
            ],
            "ai_used": False,
            "ocr_used": False,
            "network_access_performed": False,
            "deterministic": True,
            "fabricated": False,
        }
    )


def extraction_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    # The four constants that make this an honest deterministic parser.
    if result.get("ai_used") is not False:
        fails.append("ai_used_for_extraction")
    if result.get("ocr_used") is not False:
        fails.append("ocr_used_without_approval")
    if result.get("network_access_performed") is not False:
        fails.append("extraction_performed_network_access")
    if result.get("deterministic") is not True:
        fails.append("extraction_not_marked_deterministic")

    status = result.get("extraction_status")
    if status not in EXTRACTION_STATUSES:
        fails.append(f"extraction_status_out_of_vocabulary:{status}")

    if status == "extracted":
        if not result.get("text"):
            fails.append("extracted_without_text")
        if not result.get("text_hash_sha256"):
            fails.append("extracted_without_text_hash")
    else:
        # A failure must say why, and must not carry text.
        if result.get("text"):
            fails.append(f"non_extracted_status_with_text:{status}")
        if not result.get("blocked_reasons"):
            fails.append(f"{status}_without_blocked_reason")

    # A parser_unavailable must escalate to a person rather than end there.
    if status == "parser_unavailable":
        reasons = result.get("blocked_reasons") or []
        if not any("manual_review" in str(r) for r in reasons):
            fails.append("parser_unavailable_without_manual_review_escalation")

    # Every span must be orderable and inside the text.
    text_len = len(result.get("text") or "")
    for span in result.get("evidence_spans") or []:
        start, end = span.get("start"), span.get("end")
        if start is None or end is None:
            fails.append("evidence_span_without_offsets")
        elif start > end:
            fails.append("evidence_span_inverted")
        elif text_len and end > text_len:
            fails.append("evidence_span_beyond_text")

    return fails
