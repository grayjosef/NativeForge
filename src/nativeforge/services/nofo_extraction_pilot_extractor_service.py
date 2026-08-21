"""Controlled NOFO text extraction + section detection (Campaign Block 09).

Reads fixture text derived from Grants.gov synopsis for la-real-006 (TEDC).
Does not parse PDF bytes. Does not invent missing sections.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nativeforge.services.nofo_extraction_pilot_contract_service import (
    build_nofo_extraction_contract,
    make_extracted_field,
    nofo_extraction_invariant_failures,
)

SCHEMA_VERSION = "nf_nofo_extraction_pilot_extractor_v1"
EXTRACTOR_VERSION = "campaign_block09_v1"
PILOT_OPPORTUNITY_ID = "la-real-006"
DEFAULT_FIXTURE = Path(
    "fixtures/nofo_extraction_pilot/tedc_la_real_006_controlled_source.txt"
)

SECTION_KEYS = (
    ("overview_summary", "OVERVIEW / SUMMARY"),
    ("eligibility", "ELIGIBILITY"),
    ("deadline_award_period", "DEADLINE / AWARD PERIOD"),
    ("funding_amount", "FUNDING AMOUNT"),
    ("match_cost_share", "MATCH / COST-SHARE"),
    ("required_forms_attachments", "REQUIRED FORMS / ATTACHMENTS"),
    ("narrative_requirements", "NARRATIVE REQUIREMENTS"),
    ("budget_requirements", "BUDGET REQUIREMENTS"),
    ("scoring_evaluation", "SCORING / EVALUATION CRITERIA"),
    ("reporting_compliance", "REPORTING / COMPLIANCE"),
    ("contact_source", "CONTACT / SOURCE INFO"),
)


def _load_text(path: Path | None = None) -> str:
    p = path or DEFAULT_FIXTURE
    return p.read_text(encoding="utf-8")


def _section_body(text: str, heading: str) -> str | None:
    pattern = rf"=== {re.escape(heading)} ===\n(.*?)(?=\n=== |\Z)"
    m = re.search(pattern, text, flags=re.DOTALL)
    if not m:
        return None
    return m.group(1).strip()


def _section_status(body: str | None) -> tuple[str, str, str | None]:
    if body is None:
        return "not_supported", "none", None
    if body.lower().startswith("not_in_source"):
        return "not_in_source", "none", body[:240]
    if "do not invent" in body.lower() or "incomplete without" in body.lower():
        return "partial", "medium", body[:240]
    return "extracted", "high" if len(body) > 40 else "medium", body[:240]


def detect_sections(text: str) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for sid, heading in SECTION_KEYS:
        body = _section_body(text, heading)
        status, confidence, span = _section_status(body)
        value = (
            None if status in {"not_in_source", "not_supported", "missing"} else body
        )
        sections.append(
            {
                "section_id": sid,
                "heading": heading,
                "status": status,
                "confidence": confidence,
                "value": value,
                "source_span": span,
                "human_review_required": True,
            }
        )
    # Always include unsupported/not found rollup
    unsupported = [
        s["section_id"]
        for s in sections
        if s["status"]
        in {
            "not_in_source",
            "not_supported",
            "missing",
        }
    ]
    sections.append(
        {
            "section_id": "unsupported_not_found",
            "heading": "UNSUPPORTED / NOT FOUND",
            "status": "extracted",
            "confidence": "high",
            "value": unsupported,
            "source_span": None,
            "human_review_required": True,
        }
    )
    return sections


def build_requirements_map(
    text: str, sections: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_id = {s["section_id"]: s for s in sections}

    def from_section(
        requirement_id: str,
        label: str,
        section_id: str,
        *,
        extract_fn=None,
    ) -> dict[str, Any]:
        sec = by_id.get(section_id) or {}
        status = sec.get("status") or "missing"
        value = sec.get("value")
        if extract_fn and status == "extracted" and isinstance(value, str):
            value = extract_fn(value)
        if status in {"not_in_source", "not_supported", "missing"}:
            value = None
        return make_extracted_field(
            field_id=requirement_id,
            label=label,
            value=value,
            status=status
            if status
            in {
                "extracted",
                "partial",
                "not_in_source",
                "needs_confirmation",
                "not_supported",
                "missing",
            }
            else "missing",
            confidence=str(sec.get("confidence") or "none"),
            source_span=sec.get("source_span"),
            human_review_required=True,
        ) | {"requirement_id": requirement_id, "section_id": section_id}

    def first_line_match(body: str, prefix: str) -> str | None:
        for line in body.splitlines():
            if line.lower().startswith(prefix.lower()):
                return line.split(":", 1)[-1].strip() if ":" in line else line
        return None

    reqs = [
        from_section(
            "applicant_eligibility_language",
            "Applicant eligibility language",
            "eligibility",
        ),
        from_section(
            "native_tribal_eligibility_references",
            "Native/tribal eligibility references",
            "eligibility",
            extract_fn=lambda v: (
                v if re.search(r"tribal|indian|federally recognized", v, re.I) else None
            ),
        ),
        from_section(
            "funding_ceiling_floor",
            "Funding ceiling / floor",
            "funding_amount",
            extract_fn=lambda v: {
                "award_ceiling": first_line_match(v, "award_ceiling"),
                "award_floor": first_line_match(v, "award_floor"),
                "estimated_funding": first_line_match(v, "estimated_funding"),
            },
        ),
        from_section(
            "deadline",
            "Deadline",
            "deadline_award_period",
            extract_fn=lambda v: (
                first_line_match(v, "response_date_desc")
                or first_line_match(v, "response_date")
            ),
        ),
        from_section(
            "match_cost_share",
            "Match / cost-share requirement",
            "match_cost_share",
            extract_fn=lambda v: first_line_match(v, "cost_sharing"),
        ),
        from_section(
            "required_attachments",
            "Required attachments",
            "required_forms_attachments",
        ),
        from_section(
            "required_forms",
            "Required forms",
            "required_forms_attachments",
            extract_fn=lambda v: (
                "incomplete — forms inventory needs full NOFO PDF bytes"
                if "incomplete" in v.lower()
                else v
            ),
        ),
        from_section(
            "narrative_section_requirements",
            "Narrative section requirements",
            "narrative_requirements",
        ),
        from_section(
            "budget_narrative_requirements",
            "Budget narrative requirements",
            "budget_requirements",
        ),
        from_section(
            "evaluation_scoring_criteria",
            "Evaluation / scoring criteria",
            "scoring_evaluation",
        ),
        from_section(
            "reporting_obligations",
            "Reporting obligations",
            "reporting_compliance",
        ),
        from_section(
            "compliance_requirements",
            "Compliance requirements",
            "reporting_compliance",
            extract_fn=lambda v: first_line_match(v, "mod_comments") or None,
        ),
        from_section(
            "contact_source_references",
            "Contact / source references",
            "contact_source",
        ),
    ]
    # Fix native tribal: if extract returned None but section extracted, mark needs_confirmation
    for r in reqs:
        if r["requirement_id"] == "native_tribal_eligibility_references":
            if (
                r.get("value") is None
                and by_id.get("eligibility", {}).get("status") == "extracted"
            ):
                # Still have tribal language in eligibility section — re-check
                elig = by_id["eligibility"].get("value") or ""
                if re.search(r"tribal|indian|federally recognized", elig, re.I):
                    r["value"] = (
                        "Federally recognized Tribal entities / TEDOs referenced in eligibility"
                    )
                    r["status"] = "extracted"
                    r["confidence"] = "high"
                else:
                    r["status"] = "not_in_source"
                    r["confidence"] = "none"
        if r["requirement_id"] == "required_forms" and r.get("status") == "partial":
            r["status"] = "needs_confirmation"
            r["value"] = None
            r["confidence"] = "none"
        # Normalize make_extracted_field keys
        r["fabricated"] = False
    return reqs


def run_controlled_nofo_extraction(
    *,
    fixture_path: Path | None = None,
) -> dict[str, Any]:
    path = fixture_path or DEFAULT_FIXTURE
    text = _load_text(path)
    sections = detect_sections(text)
    requirements = build_requirements_map(text, sections)
    extracted_count = sum(
        1 for s in sections if s["status"] in {"extracted", "partial"}
    )
    missing_count = sum(
        1
        for s in sections
        if s["section_id"] != "unsupported_not_found"
        and s["status"] in {"not_in_source", "not_supported", "missing"}
    )
    status = "partial" if missing_count else "extracted"
    if missing_count:
        status = "needs_human_review"

    packet = build_nofo_extraction_contract(
        opportunity_id=PILOT_OPPORTUNITY_ID,
        source_document_id="tedc_la_real_006_controlled_source",
        source_document_label="TEDC FY2026 controlled Grants.gov synopsis text (PDF bytes not parsed)",
        source_document_type="controlled_fixture_text",
        source_layer="federal",
        document_url_or_fixture_reference=str(path),
        data_mode="fixture_controlled",
        extraction_mode="controlled_text_extraction",
        extraction_scope="one_showcase_opportunity",
        extraction_status=status,
        extracted_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        extractor_version=EXTRACTOR_VERSION,
        sections=sections,
        requirements_map=requirements,
        human_review_required=True,
    )
    packet["schema_version_extractor"] = SCHEMA_VERSION
    packet["section_extracted_count"] = extracted_count
    packet["section_missing_count"] = missing_count
    packet["named_pdf_attachment_referenced"] = "TEDC NOFO FY 2026.pdf"
    packet["honesty_notes"] = [
        "Extraction uses controlled fixture text derived from Grants.gov fetch 362648",
        "Named PDF attachment is referenced but PDF bytes are not stored or parsed",
        "full_pdf_extraction_claimed=false; broad_pdf_support_claimed=false",
        "Human review required before customer reliance",
    ]
    fails = nofo_extraction_invariant_failures(packet)
    packet["invariant_failures"] = fails
    return packet
