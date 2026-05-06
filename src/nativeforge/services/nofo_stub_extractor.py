"""Deterministic NOFO extraction stub (Sprint 3 — schema discipline, no LLM)."""

from __future__ import annotations

import hashlib
from typing import Any

from nativeforge.db.models import NfGrantSpark
from nativeforge.domain.enums import SparkRequirementKind

ENGINE_KEY = "deterministic_stub_v1"


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_stub(spark: NfGrantSpark, raw_nofo_text: str | None) -> dict[str, Any]:
    """
    Produce summary, structured JSON (research/domain/nofo-extraction-schema.md shape),
    and flat checklist rows for nf_spark_requirements.
    """
    body = (raw_nofo_text or "").strip()
    if not body:
        body = (
            f"(No NOFO body stored — stub generated from Spark metadata only.) "
            f"Title: {spark.opportunity_title}. Agency: {spark.agency}."
        )
    digest = _digest(body)
    seed = int(digest[:8], 16)

    summary = (
        f"Deterministic Sprint 3 stub summary for “{spark.opportunity_title}”, "
        f"issued by {spark.agency}. Source digest prefix {digest[:12]}… "
        "Covers eligibility, standard federal forms, and reporting burden — "
        "human review is required before treating extraction as final."
    )

    structured: dict[str, Any] = {
        "metadata": {
            "opportunity_title": spark.opportunity_title,
            "opportunity_number": spark.opportunity_number,
            "cfda_assistance_listing": spark.cfda_assistance_listing,
            "issuing_agency": spark.agency,
            "sub_agency": spark.sub_agency,
            "opportunity_url": spark.url,
            "_confidence": 1.0,
        },
        "eligibility": {
            "eligible_entity_types": ["tribal_government", "tribal_nonprofit"],
            "federally_recognized_tribe_required": True,
            "sam_registration_required": True,
            "_confidence": 0.95,
        },
        "funding": {
            "award_floor": float(spark.funding_floor)
            if spark.funding_floor is not None
            else None,
            "award_ceiling": float(spark.funding_ceiling)
            if spark.funding_ceiling is not None
            else None,
            "match_required": spark.match_required,
            "match_percent": float(spark.match_percent)
            if spark.match_percent is not None
            else None,
            "indirect_cost_allowable": spark.indirect_cost_allowable,
            "_confidence": 1.0,
        },
        "timeline": {
            "application_deadline": spark.application_deadline.isoformat()
            if spark.application_deadline
            else None,
            "loi_deadline": spark.loi_deadline.isoformat()
            if spark.loi_deadline
            else None,
            "_confidence": 1.0,
        },
        "requirements_forms": [
            {
                "form_name": "SF-424",
                "required": True,
                "notes": "Standard application for federal assistance.",
                "_confidence": 1.0,
            },
            {
                "form_name": "SF-424A",
                "required": True,
                "notes": "Budget information for non-construction programs.",
                "_confidence": 1.0,
            },
            {
                "form_name": "Tribal Council Resolution",
                "required": bool(seed % 2),
                "notes": "Stub toggled deterministically from digest.",
                "_confidence": 0.85,
            },
        ],
        "requirements_attachments": [
            {
                "attachment_name": "Logic model",
                "required": True,
                "format": "PDF",
                "page_limit": 5,
                "_confidence": 0.9,
            },
            {
                "attachment_name": "Letters of support",
                "required": False,
                "format": "PDF",
                "_confidence": 0.88,
            },
        ],
        "requirements_narrative": [
            {
                "section_title": "Project narrative",
                "description": "Describe need, objectives, and tribal benefit.",
                "page_limit": 10,
                "_confidence": 0.92,
            },
            {
                "section_title": "Evaluation plan",
                "description": "Metrics and data collection aligned to objectives.",
                "page_limit": 5,
                "_confidence": 0.9,
            },
        ],
        "evaluation": {
            "criteria_text": "Stub evaluation criteria placeholder.",
            "_confidence": 0.75,
        },
        "compliance_reporting": {
            "post_award_reporting_frequency": "annual",
            "_confidence": 0.8,
        },
        "risk_flags": [
            "deterministic_stub: verify deadlines against official NOFO",
            "deterministic_stub: confirm tribal eligibility with counsel",
        ],
        "ai_summary": {
            "plain_language_summary": summary,
            "key_requirements_summary": [
                "Submit SF-424 family forms",
                "Provide narrative sections per page limits",
                "Attach logic model where required",
            ],
            "_confidence": 1.0,
        },
        "human_review_required": [
            "evaluation.criteria_text",
            "requirements_narrative[1]._confidence",
        ],
        "_extractor": ENGINE_KEY,
        "_input_digest": digest,
        "_source_char_len": len(body),
    }

    checklist: list[dict[str, Any]] = []
    order = 0

    def add_row(
        kind: SparkRequirementKind,
        label: str,
        *,
        description: str | None = None,
        required: bool = True,
        page_limit: int | None = None,
        notes: str | None = None,
    ) -> None:
        nonlocal order
        checklist.append(
            {
                "requirement_type": kind.value,
                "label": label,
                "description": description,
                "required": required,
                "page_limit": page_limit,
                "sort_order": order,
                "notes": notes,
            }
        )
        order += 1

    add_row(
        SparkRequirementKind.eligibility,
        "Confirm tribal eligibility and SAM registration",
        description="Align entity profile with NOFO eligibility rules.",
        notes="Stub eligibility gate.",
    )
    for f in structured["requirements_forms"]:
        add_row(
            SparkRequirementKind.form,
            str(f["form_name"]),
            description=f.get("notes"),
            required=bool(f.get("required", True)),
        )
    for a in structured["requirements_attachments"]:
        add_row(
            SparkRequirementKind.attachment,
            str(a["attachment_name"]),
            description=a.get("attachment_name"),
            required=bool(a.get("required", True)),
            page_limit=a.get("page_limit"),
        )
    for n in structured["requirements_narrative"]:
        add_row(
            SparkRequirementKind.narrative_section,
            str(n["section_title"]),
            description=str(n.get("description", "")),
            required=True,
            page_limit=n.get("page_limit"),
        )
    add_row(
        SparkRequirementKind.reporting,
        "Post-award reporting",
        description=str(
            structured["compliance_reporting"]["post_award_reporting_frequency"]
        ),
        required=True,
    )

    return {
        "digest": digest,
        "nofo_summary": summary,
        "structured_requirements": structured,
        "checklist_rows": checklist,
        "checklist_snapshot": checklist,
    }
