"""Sprint 125: M0 requirement extraction checklist preview planning packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT125_MOD = (
    "nativeforge.services."
    "active_source_activation_m0_requirement_extraction_checklist_preview_planning_packet_service"
)
sprint125_pkt = importlib.import_module(_SPRINT125_MOD)
M0_REQUIREMENT_CHECKLIST_PREVIEW_FOUNDATIONS = sprint125_pkt.M0_REQUIREMENT_CHECKLIST_PREVIEW_FOUNDATIONS
build_pkt = (
    sprint125_pkt.build_active_source_activation_m0_requirement_extraction_checklist_preview_planning_packet
)
render_md = (
    sprint125_pkt.render_active_source_activation_m0_requirement_extraction_checklist_preview_planning_packet_markdown
)

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m0_requirement_extraction_checklist_preview_planning_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After SF-424 Preview Planning",
    "## 3. M0 Checklist Preview Objective",
    "## 4. Demo-Safe Requirement Rules",
    "## 5. Required Checklist Field Groups",
    "## 6. Requirement Category Definitions",
    "## 7. Field-Level Acceptance Criteria",
    "## 8. Checklist Preview to M0 Feature Mapping",
    "## 9. Missing Data and Confidence Rules",
    "## 10. Human Review Gates",
    "## 11. Sovereignty and Trust Requirements",
    "## 12. What Sprint 125 Does Not Build",
    "## 13. M0 Exit Criteria for Checklist Planning",
    "## 14. Risks and Mitigations",
    "## 15. Sprint 126 Recommended Next Step",
)

EXPECTED_FIELD_GROUP_NAMES = (
    "Requirement identity",
    "Requirement category",
    "Requirement source section",
    "Requirement plain-language label",
    "Requirement detail",
    "Required attachment flag",
    "Required form flag",
    "Eligibility documentation flag",
    "Match/cost-share documentation flag",
    "Narrative response flag",
    "Due date relationship",
    "Pipeline status relationship",
    "Owner preview",
    "Reviewer preview",
    "Missing data flag",
    "Source provenance and confidence",
    "Human correction notes",
    "Audit and export readiness",
)

EXPECTED_CATEGORY_NAMES = (
    "Eligibility requirement",
    "Narrative requirement",
    "Budget requirement",
    "Attachment requirement",
    "Form requirement",
    "Match/cost-share requirement",
    "Resolution or authorization requirement",
    "Reporting requirement",
    "Deadline requirement",
    "Human review required",
)


def _source_imports_subprocess(src: str) -> bool:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "subprocess":
                    return True
        if isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            return True
    return False


def test_service_has_no_subprocess_import() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert not _source_imports_subprocess(src)


def test_packet_sprint_and_flags() -> None:
    pkt = build_pkt()
    assert pkt["sprint_number"] == 125
    assert pkt["packet_name"] == "NativeForge M0 Requirement Extraction Checklist Preview Planning Packet"
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True
    assert pkt["may_define_requirement_checklist_scope"] is True
    assert pkt["may_define_demo_safe_requirement_fields"] is True
    assert pkt["may_define_acceptance_criteria"] is True
    assert pkt["may_define_guardrails"] is True


def test_packet_actual_counts_zero() -> None:
    pkt = build_pkt()
    assert pkt["actual_external_calls"] == 0
    assert pkt["actual_source_ingestions"] == 0
    assert pkt["actual_api_calls"] == 0
    assert pkt["actual_scrapes"] == 0
    assert pkt["actual_ai_generations"] == 0
    assert pkt["actual_form_submissions"] == 0
    assert pkt["actual_customer_data_access"] == 0
    assert pkt["actual_runtime_writes"] == 0
    assert pkt["actual_requirement_extractions"] == 0
    assert pkt["actual_checklist_creations"] == 0
    assert pkt["actual_task_creations"] == 0


def test_m0_foundations_match_required_ten() -> None:
    pkt = build_pkt()
    assert pkt["m0_requirement_checklist_preview_foundations"] == list(
        M0_REQUIREMENT_CHECKLIST_PREVIEW_FOUNDATIONS
    )
    assert len(M0_REQUIREMENT_CHECKLIST_PREVIEW_FOUNDATIONS) == 10


def test_eighteen_checklist_field_groups_present() -> None:
    pkt = build_pkt()
    groups = pkt["checklist_field_groups"]
    assert len(groups) == 18
    names = [g["name"] for g in groups]
    for expected in EXPECTED_FIELD_GROUP_NAMES:
        assert expected in names


def test_ten_requirement_categories_present() -> None:
    pkt = build_pkt()
    cats = pkt["requirement_categories"]
    assert len(cats) == 10
    names = [c["name"] for c in cats]
    for expected in EXPECTED_CATEGORY_NAMES:
        assert expected in names


def test_each_field_group_has_at_least_two_acceptance_criteria() -> None:
    pkt = build_pkt()
    for g in pkt["checklist_field_groups"]:
        crit = g["acceptance_criteria"]
        assert isinstance(crit, list)
        assert len(crit) >= 2


def test_at_least_eight_risks_documented() -> None:
    pkt = build_pkt()
    assert len(pkt["risks_and_mitigations"]) >= 8


def test_markdown_required_section_headers() -> None:
    md = render_md()
    assert md.startswith(
        "# NativeForge M0 Requirement Extraction Checklist Preview Planning Packet v1\n"
    )
    for h in REQUIRED_SECTION_HEADERS:
        assert h in md


def test_markdown_demo_safe_requirement_rules() -> None:
    md = render_md()
    lower = md.lower()
    assert "demo-safe" in lower and "requirement" in lower
    assert "no real customer data" in lower
    assert "no external validation" in lower


def test_markdown_missing_data_and_confidence_rules() -> None:
    md = render_md()
    lower = md.lower()
    assert "missing source section" in lower and "human review" in lower
    assert "low confidence" in lower
    assert "ambiguous requirement category" in lower
    assert "due-date relationship" in lower or "due-date" in lower
    assert "owner/reviewer" in lower or "owner" in lower


def test_markdown_human_review_gate_language() -> None:
    md = render_md()
    lower = md.lower()
    assert "checklist preview cannot be treated as a final submission checklist" in lower
    assert "every requirement must remain editable" in lower
    assert "source provenance must be visible" in lower


def test_markdown_sovereignty_and_trust_requirements() -> None:
    md = render_md()
    lower = md.lower()
    assert "no customer data is required for seeded checklist demos" in lower
    assert "no customer data leaves the product during seeded demos" in lower
    assert "no model training on customer data without explicit written" in lower


def test_markdown_sprint125_does_not_build_phrases() -> None:
    md = render_md()
    lower = md.lower()
    assert "no real nofo parsing" in lower
    assert "no llm extraction" in lower
    assert "no database migration" in lower
    assert "no production task creation" in lower


def test_markdown_sprint126_data_sovereignty_export_preview() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 126" in lower
    assert "m0 data sovereignty policy and export preview planning packet" in lower


def test_deterministic_packet_and_markdown() -> None:
    a = build_pkt()
    b = build_pkt()
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    md_a = render_md(a)
    md_b = render_md(b)
    assert md_a == md_b


def test_render_without_argument_matches_explicit_packet() -> None:
    pkt = build_pkt()
    assert render_md() == render_md(pkt)
