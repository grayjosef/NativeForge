"""Sprint 308 / GG completeness: parse Grants.gov synopsis + forecast eligibility."""

from __future__ import annotations

import json
import re
from typing import Any

from nativeforge.services.source_connectors.grants_gov_shaped import (
    _infer_tribal_signals_from_eligibility_body,
)

SCHEMA_VERSION = "nf_grants_gov_eligibility_parser_v3"
_ATTACHMENT_INVENTORY_SCHEMA = "nf_grants_gov_attachment_inventory_v1"

_TRIBAL_TYPE_IDS = frozenset({"07", "11"})
_THIN_ELIGIBILITY_DESC_RE = re.compile(
    r"^(see section|see the |refer to the |for eligibility information)",
    re.IGNORECASE,
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text).replace("&sect;", "§").strip()


def _parse_eligibility_block(
    block: dict[str, Any] | None,
    *,
    narrative_key: str,
    block_label: str,
) -> dict[str, Any]:
    """Parse a Grants.gov synopsis- or forecast-shaped eligibility block."""
    blk = block or {}
    applicant_types = [x for x in (blk.get("applicantTypes") or []) if isinstance(x, dict)]
    type_labels = [
        str(x.get("description") or "").strip()
        for x in applicant_types
        if str(x.get("description") or "").strip()
    ]
    applicant_types_text = "; ".join(type_labels)
    eligibility_desc = _strip_html(str(blk.get("applicantEligibilityDesc") or ""))
    narrative_desc = _strip_html(str(blk.get(narrative_key) or ""))

    parts: list[str] = []
    if applicant_types_text:
        parts.append(f"Applicant types: {applicant_types_text}")
    if eligibility_desc:
        parts.append(eligibility_desc)
    thin_desc = (
        not eligibility_desc
        or len(eligibility_desc) < 80
        or bool(_THIN_ELIGIBILITY_DESC_RE.match(eligibility_desc.strip()))
    )
    if thin_desc and narrative_desc:
        parts.append(narrative_desc)
    eligibility_text = "\n\n".join(parts)

    tribal_from_types = any(
        str(x.get("id") or "") in _TRIBAL_TYPE_IDS
        or "native american tribal" in str(x.get("description") or "").lower()
        for x in applicant_types
    )
    body = "\n".join(parts)
    tribal_from_body, tags = _infer_tribal_signals_from_eligibility_body(body)
    tribal_eligible = tribal_from_types or tribal_from_body

    return {
        "block_label": block_label,
        "applicant_types_text": applicant_types_text,
        "applicant_type_ids": [
            str(x.get("id") or "").strip()
            for x in applicant_types
            if str(x.get("id") or "").strip()
        ],
        "applicant_types_json": applicant_types,
        "applicant_eligibility_desc": eligibility_desc,
        "narrative_desc_included": thin_desc and bool(narrative_desc),
        "eligibility_text": eligibility_text,
        "tribal_eligible": tribal_eligible,
        "eligibility_tags": tags,
        "agency_name": str(blk.get("agencyName") or blk.get("agencyCode") or ""),
    }


def parse_grants_gov_synopsis_eligibility(
    synopsis: dict[str, Any] | None,
) -> dict[str, Any]:
    syn = synopsis or {}
    parsed = _parse_eligibility_block(syn, narrative_key="synopsisDesc", block_label="synopsis")
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "applicant_types_text": parsed["applicant_types_text"],
            "applicant_type_ids": parsed["applicant_type_ids"],
            "applicant_types_json": parsed["applicant_types_json"],
            "applicant_eligibility_desc": parsed["applicant_eligibility_desc"],
            "synopsis_desc_included": parsed["narrative_desc_included"],
            "eligibility_text": parsed["eligibility_text"],
            "tribal_eligible": parsed["tribal_eligible"],
            "eligibility_tags": parsed["eligibility_tags"],
        }
    )


def summarize_grants_gov_attachment_inventory(
    detail: dict[str, Any] | None,
) -> dict[str, Any]:
    """Metadata-only attachment inventory (no binary fetch/parse)."""
    data = detail or {}
    doc_type = str(data.get("docType") or "")
    syn = data.get("synopsis") or {}
    folders_raw = syn.get("synopsisAttachmentFolders") or data.get("synopsisAttachmentFolders") or []
    attachments: list[dict[str, Any]] = []
    for folder in folders_raw:
        if not isinstance(folder, dict):
            continue
        folder_type = str(folder.get("folderType") or folder.get("folderName") or "")
        for att in folder.get("synopsisAttachments") or []:
            if not isinstance(att, dict):
                continue
            attachments.append(
                {
                    "attachment_id": att.get("id"),
                    "file_name": str(att.get("fileName") or ""),
                    "mime_type": str(att.get("mimeType") or ""),
                    "file_size": att.get("fileLobSize"),
                    "folder_type": folder_type,
                }
            )
    pdf_count = sum(
        1
        for a in attachments
        if "pdf" in a["mime_type"].lower() or a["file_name"].lower().endswith(".pdf")
    )
    return _json_safe(
        {
            "schema_version": _ATTACHMENT_INVENTORY_SCHEMA,
            "doc_type": doc_type or None,
            "folder_count": len(folders_raw),
            "attachment_count": len(attachments),
            "pdf_count": pdf_count,
            "attachments": attachments,
            "parsed": False,
        }
    )


def _merge_applicant_type_ids(left: list[str], right: list[str]) -> list[str]:
    out: list[str] = []
    for tid in left + right:
        if tid and tid not in out:
            out.append(tid)
    return out


def parse_grants_gov_opportunity_eligibility(
    detail: dict[str, Any] | None,
) -> dict[str, Any]:
    """Merge synopsis + forecast eligibility from fetchOpportunity detail."""
    data = detail or {}
    syn_block = data.get("synopsis") or {}
    fc_block = data.get("forecast") or {}
    syn = _parse_eligibility_block(syn_block, narrative_key="synopsisDesc", block_label="synopsis")
    fc = _parse_eligibility_block(fc_block, narrative_key="forecastDesc", block_label="forecast")

    syn_text = str(syn.get("eligibility_text") or "").strip()
    fc_text = str(fc.get("eligibility_text") or "").strip()
    syn_substantive = bool(syn_text)
    fc_substantive = bool(fc_text)

    if syn_substantive and fc_substantive:
        eligibility_text = f"{syn_text}\n\n{fc_text}"
        eligibility_text_source = "merged"
    elif syn_substantive:
        eligibility_text = syn_text
        eligibility_text_source = "synopsis"
    elif fc_substantive:
        eligibility_text = fc_text
        eligibility_text_source = "forecast"
    else:
        eligibility_text = ""
        eligibility_text_source = "unknown"

    applicant_type_ids = _merge_applicant_type_ids(
        list(syn.get("applicant_type_ids") or []),
        list(fc.get("applicant_type_ids") or []),
    )
    applicant_types_json = list(syn.get("applicant_types_json") or []) + [
        x
        for x in (fc.get("applicant_types_json") or [])
        if x not in (syn.get("applicant_types_json") or [])
    ]
    tribal_eligible = bool(syn.get("tribal_eligible") or fc.get("tribal_eligible"))
    tags = list(dict.fromkeys((syn.get("eligibility_tags") or []) + (fc.get("eligibility_tags") or [])))

    doc_type = str(data.get("docType") or "")
    if not doc_type:
        if syn_substantive and not fc_substantive:
            doc_type = "synopsis"
        elif fc_substantive and not syn_substantive:
            doc_type = "forecast"
        elif syn_substantive and fc_substantive:
            doc_type = "synopsis"

    agency = (
        str(syn.get("agency_name") or "").strip()
        or str(fc.get("agency_name") or "").strip()
        or str(data.get("owningAgencyCode") or "")
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "eligibility_text": eligibility_text,
            "eligibility_text_source": eligibility_text_source,
            "eligibility_provenance": {
                "synopsis_present": bool(syn_block),
                "forecast_present": bool(fc_block),
                "synopsis_substantive": syn_substantive,
                "forecast_substantive": fc_substantive,
                "primary_source": eligibility_text_source,
            },
            "applicant_types_text": "; ".join(
                x
                for x in (syn.get("applicant_types_text"), fc.get("applicant_types_text"))
                if x
            ),
            "applicant_type_ids": applicant_type_ids,
            "applicant_types_json": applicant_types_json,
            "applicant_eligibility_desc": (
                str(syn.get("applicant_eligibility_desc") or "")
                + (
                    f"\n{fc.get('applicant_eligibility_desc')}"
                    if fc.get("applicant_eligibility_desc")
                    else ""
                )
            ).strip(),
            "synopsis": str(syn_block.get("synopsisDesc") or fc_block.get("forecastDesc") or ""),
            "tribal_eligible": tribal_eligible,
            "eligibility_tags": tags,
            "agency": agency,
            "grants_gov_doc_type": doc_type or None,
            "grants_gov_attachment_inventory": summarize_grants_gov_attachment_inventory(data),
        }
    )
