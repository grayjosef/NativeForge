"""NOFO extraction pilot contract (Campaign Block 09).

Controlled one-opportunity pilot. Never claims full/broad PDF extraction.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_nofo_extraction_pilot_contract_v1"

EXTRACTION_STATUSES = frozenset(
    {
        "not_started",
        "fixture_controlled",
        "extracted",
        "partial",
        "needs_human_review",
        "unsupported",
        "failed",
    }
)

EXTRACTION_SCOPES = frozenset(
    {
        "one_showcase_opportunity",
        "controlled_fixture",
        "read_only_source",
        "not_generalized",
    }
)

FIELD_STATUSES = frozenset(
    {
        "extracted",
        "partial",
        "not_in_source",
        "needs_confirmation",
        "not_supported",
        "missing",
    }
)

CONFIDENCE_LABELS = frozenset({"high", "medium", "low", "none"})


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_nofo_extraction_id(opportunity_id: str, source_document_id: str) -> str:
    raw = f"nx::{opportunity_id}::{source_document_id}".encode()
    return f"nx_{hashlib.sha256(raw).hexdigest()[:16]}"


def make_extracted_field(
    *,
    field_id: str,
    label: str,
    value: Any,
    status: str,
    confidence: str,
    source_span: str | None = None,
    human_review_required: bool = True,
) -> dict[str, Any]:
    st = status if status in FIELD_STATUSES else "missing"
    conf = confidence if confidence in CONFIDENCE_LABELS else "none"
    if st in {"not_in_source", "not_supported", "missing"}:
        value = None
        conf = "none"
    return _json_safe(
        {
            "field_id": field_id,
            "label": label,
            "value": value,
            "status": st,
            "confidence": conf,
            "source_span": source_span,
            "human_review_required": human_review_required,
            "fabricated": False,
        }
    )


def build_nofo_extraction_contract(
    *,
    opportunity_id: str,
    source_document_id: str,
    source_document_label: str,
    source_document_type: str,
    source_layer: str,
    document_url_or_fixture_reference: str,
    data_mode: str,
    extraction_mode: str,
    extraction_scope: str,
    extraction_status: str,
    extracted_at: str | None,
    extractor_version: str,
    sections: list[dict[str, Any]] | None = None,
    requirements_map: list[dict[str, Any]] | None = None,
    human_review_required: bool = True,
) -> dict[str, Any]:
    scope = (
        extraction_scope if extraction_scope in EXTRACTION_SCOPES else "not_generalized"
    )
    status = (
        extraction_status
        if extraction_status in EXTRACTION_STATUSES
        else "needs_human_review"
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "nofo_extraction_id": make_nofo_extraction_id(
                opportunity_id, source_document_id
            ),
            "opportunity_id": opportunity_id,
            "source_document_id": source_document_id,
            "source_document_label": source_document_label,
            "source_document_type": source_document_type,
            "source_layer": source_layer,
            "document_url_or_fixture_reference": document_url_or_fixture_reference,
            "data_mode": data_mode,
            "extraction_mode": extraction_mode,
            "extraction_scope": scope,
            "extraction_status": status,
            "extracted_at": extracted_at,
            "extractor_version": extractor_version,
            "human_review_required": human_review_required,
            "sections": list(sections or []),
            "requirements_map": list(requirements_map or []),
            "full_pdf_extraction_claimed": False,
            "broad_pdf_support_claimed": False,
            "proposal_drafting_claimed": False,
            "final_eligibility_claimed": False,
            "live_ingest_claimed": False,
            "pdf_bytes_parsed": False,
        }
    )


def nofo_extraction_invariant_failures(packet: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "full_pdf_extraction_claimed",
        "broad_pdf_support_claimed",
        "proposal_drafting_claimed",
        "final_eligibility_claimed",
        "live_ingest_claimed",
        "pdf_bytes_parsed",
    ):
        if packet.get(key) is True:
            fails.append(key)
    if packet.get("extraction_scope") not in EXTRACTION_SCOPES:
        fails.append("bad_scope")
    if packet.get("extraction_status") not in EXTRACTION_STATUSES:
        fails.append("bad_status")
    if packet.get("extraction_scope") not in {
        "one_showcase_opportunity",
        "controlled_fixture",
        "read_only_source",
        "not_generalized",
    }:
        fails.append("generalized_scope")
    for req in packet.get("requirements_map") or []:
        if req.get("status") in {
            "not_in_source",
            "missing",
            "not_supported",
        } and req.get("value") not in (None, "", []):
            fails.append(f"invented_requirement:{req.get('requirement_id')}")
        if req.get("fabricated") is True:
            fails.append(f"fabricated_requirement:{req.get('requirement_id')}")
    return fails
