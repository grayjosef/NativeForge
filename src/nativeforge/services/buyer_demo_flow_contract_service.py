"""Monday buyer demo flow contract — story labels and claim guardrails.

Does not claim live ingest, full NOFO PDF extraction, or proposal drafting.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_monday_buyer_demo_flow_contract_v1"
DEMO_ROUTE_PATH = "/?view=sc_customer_demo"

OPENING_LINE = (
    "NativeForge structures South Carolina and federal grant opportunities "
    "for your organization — curated-current intelligence, honest gaps, and "
    "an application-plan skeleton — without fabricating live ingest, NOFO PDFs, "
    "or proposal prose."
)

CLOSING_LINE = (
    "Next step: human review of missing evidence and active rounds, then decide "
    "pursue or defer — NativeForge will not submit or invent facts for you."
)

REQUIRED_STORY_LABELS: tuple[str, ...] = (
    "organization_context",
    "sc_and_federal_opportunities",
    "fit_eligibility_uncertainty",
    "nofo_synopsis_intelligence",
    "application_plan_skeleton",
    "missing_information",
    "human_review_required",
    "workload_reduction",
    "curated_current_not_live_ingest",
    "demo_real_isolation",
)

ALLOWED_CLAIMS: tuple[str, ...] = (
    "Curated-current SC and federal opportunities in one workflow",
    "Recognition-tier eligibility gating with visible blockers",
    "Honest missing-field and needs-confirmation labels",
    "Synopsis/curated NOFO intelligence for selected showcase opportunities",
    "Application-plan skeleton and checklist (not a finished proposal)",
    "Human review required before pursuit or submission",
    "Material reduction of discovery and pursuit prep workload",
)

FORBIDDEN_CLAIMS: tuple[str, ...] = (
    "Automated live ingestion from live portals",
    "Full live NOFO PDF extraction",
    "Automated proposal narrative drafting",
    "Final eligibility determination without human evidence review",
    "Fabricated tribal facts, budgets, resolutions, or past performance",
    "Source activation or production data mutation",
    "Independent penetration test or production-ready auth",
    "Full sovereignty deployment or automated submission",
)

FLOW_STEPS: tuple[dict[str, str], ...] = (
    {
        "id": "opening",
        "title": "Opening state",
        "buyer_question": "What am I looking at?",
        "say": OPENING_LINE,
    },
    {
        "id": "organization_context",
        "title": "Organization context",
        "buyer_question": "Does NativeForge know our SC organization?",
        "say": "Show SC pilot profiles and recognition tiers (federal vs state_only).",
    },
    {
        "id": "opportunity_overview",
        "title": "SC + federal opportunity overview",
        "buyer_question": "What opportunities were found?",
        "say": "Show curated South Carolina and federal opportunities together.",
    },
    {
        "id": "selected_detail",
        "title": "Selected opportunity detail",
        "buyer_question": "What happens after we pick one?",
        "say": "Open NOFO/synopsis intelligence for a showcase opportunity.",
    },
    {
        "id": "eligibility",
        "title": "Eligibility explanation",
        "buyer_question": "Why might this fit — and what is uncertain?",
        "say": "Walk eligibility evidence, blockers, and needs-confirmation labels.",
    },
    {
        "id": "nofo_intelligence",
        "title": "NOFO/synopsis intelligence",
        "buyer_question": "What requirements are known vs missing?",
        "say": "Show known/inferred/missing/not_supported field statuses honestly.",
    },
    {
        "id": "application_plan",
        "title": "Application-plan skeleton",
        "buyer_question": "What do we do next to pursue?",
        "say": "Show checklist, missing-info questions, and human approval gates.",
    },
    {
        "id": "missing_and_review",
        "title": "Missing information + human review",
        "buyer_question": "What still needs people?",
        "say": "Emphasize human review; never invent answers for missing org facts.",
    },
    {
        "id": "close",
        "title": "Closing next step",
        "buyer_question": "What should we do after this meeting?",
        "say": CLOSING_LINE,
    },
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_buyer_demo_flow_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "demo_route_path": DEMO_ROUTE_PATH,
            "opening_line": OPENING_LINE,
            "closing_line": CLOSING_LINE,
            "required_story_labels": list(REQUIRED_STORY_LABELS),
            "allowed_claims": list(ALLOWED_CLAIMS),
            "forbidden_claims": list(FORBIDDEN_CLAIMS),
            "flow_steps": list(FLOW_STEPS),
            "trust_cues_required": [
                "curated_current",
                "not_automated_live_ingest",
                "source_evidence",
                "captured_or_retrieved_date",
                "missing_fields_visible",
                "human_review_required",
                "no_final_eligibility_claim",
                "nofo_pdf_extraction_not_supported",
                "proposal_drafting_not_supported",
                "application_plan_skeleton_only",
                "demo_real_isolation",
            ],
            "claim_matrix": {
                "sc_customer_demo_route": "IMPLEMENTED",
                "sc_federal_combined_workflow": "IMPLEMENTED",
                "nofo_synopsis_intelligence": "IMPLEMENTED",
                "application_plan_skeleton": "IMPLEMENTED",
                "buyer_story_polish": "IMPLEMENTED",
                "local_pytest_frontend_playwright": "LOCALLY_VALIDATED",
                "live_ingest": "BLOCKED",
                "full_nofo_pdf_extraction": "BLOCKED",
                "proposal_drafting": "BLOCKED",
                "final_eligibility_without_human_review": "BLOCKED",
                "production_customer_validation": "UNKNOWN",
                "monday_demo_ready": "DEMO_READY",
                "live_validated": "NOT_CLAIMED",
            },
            "live_ingest_claimed": False,
            "nofo_pdf_extraction_claimed": False,
            "proposal_drafting_claimed": False,
            "final_eligibility_claim_allowed": False,
        }
    )


def buyer_flow_contract_invariant_failures(contract: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if contract.get("demo_route_path") != DEMO_ROUTE_PATH:
        fails.append("route")
    if not contract.get("opening_line"):
        fails.append("opening_line")
    if not contract.get("closing_line"):
        fails.append("closing_line")
    if contract.get("live_ingest_claimed") is True:
        fails.append("live_ingest_claimed")
    if contract.get("nofo_pdf_extraction_claimed") is True:
        fails.append("nofo_pdf_claimed")
    if contract.get("proposal_drafting_claimed") is True:
        fails.append("proposal_claimed")
    if contract.get("final_eligibility_claim_allowed") is True:
        fails.append("final_eligibility")
    labels = set(contract.get("required_story_labels") or [])
    for required in REQUIRED_STORY_LABELS:
        if required not in labels:
            fails.append(f"missing_label:{required}")
    forbidden_blob = " ".join(contract.get("forbidden_claims") or []).lower()
    for needle in (
        "live ingestion",
        "nofo pdf",
        "proposal narrative",
        "final eligibility",
    ):
        if needle not in forbidden_blob:
            fails.append(f"forbidden_list_incomplete:{needle}")
    # Opening/closing must not overclaim
    text = f"{contract.get('opening_line')} {contract.get('closing_line')}".lower()
    for bad in (
        "live ingest complete",
        "full nofo pdf extracted",
        "we wrote your proposal",
        "you are eligible",
        "automatically submitted",
    ):
        if bad in text:
            fails.append(f"overclaim:{bad}")
    return fails


def assert_ui_text_has_required_buyer_labels(ui_text: str) -> list[str]:
    """Check rendered/demo text carries required honesty phrases."""
    t = ui_text.lower()
    fails: list[str] = []
    required_phrases = (
        ("curated", "curated_current"),
        ("live ingest", "live_ingest_honesty"),
        ("human review", "human_review"),
        ("missing", "missing_fields"),
        ("application plan", "application_plan"),
        ("proposal", "proposal_limit"),
        ("nofo", "nofo_limit"),
    )
    for phrase, code in required_phrases:
        if phrase not in t:
            fails.append(f"missing_phrase:{code}")
    # Forbidden overclaims in UI copy
    for bad, code in (
        ("live_ingestion=true", "live_true"),
        ("final_eligibility_claim_allowed=true", "final_true"),
        ("nofo_pdf_extraction_claimed=true", "pdf_true"),
        ("proposal_drafting_claimed=true", "proposal_true"),
    ):
        if bad in t:
            fails.append(f"forbidden_ui:{code}")
    return fails
