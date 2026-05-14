"""Sprint 124: M0 SF-424 autofill preview planning packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT124_MOD = (
    "nativeforge.services.active_source_activation_m0_sf424_autofill_preview_planning_packet_service"
)
sprint124_pkt = importlib.import_module(_SPRINT124_MOD)
M0_SF424_PREVIEW_FOUNDATIONS = sprint124_pkt.M0_SF424_PREVIEW_FOUNDATIONS
build_pkt = sprint124_pkt.build_active_source_activation_m0_sf424_autofill_preview_planning_packet
render_md = sprint124_pkt.render_active_source_activation_m0_sf424_autofill_preview_planning_packet_markdown

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m0_sf424_autofill_preview_planning_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After Pipeline Planning",
    "## 3. M0 SF-424 Preview Objective",
    "## 4. Demo-Safe Autofill Rules",
    "## 5. Required SF-424 Field Groups",
    "## 6. Field-Level Acceptance Criteria",
    "## 7. SF-424 Preview to M0 Feature Mapping",
    "## 8. Missing Data and Validation Preview Rules",
    "## 9. Human Review Gates",
    "## 10. Sovereignty and Trust Requirements",
    "## 11. What Sprint 124 Does Not Build",
    "## 12. M0 Exit Criteria for SF-424 Preview Planning",
    "## 13. Risks and Mitigations",
    "## 14. Sprint 125 Recommended Next Step",
)

EXPECTED_FIELD_GROUP_NAMES = (
    "Application type",
    "Applicant legal name",
    "Employer identification number",
    "UEI",
    "Applicant address",
    "Applicant type",
    "Congressional district",
    "Federal agency",
    "Assistance listing / CFDA",
    "Funding opportunity number",
    "Funding opportunity title",
    "Competition identification number",
    "Authorized representative name",
    "Authorized representative title",
    "Authorized representative contact information",
    "Certification and signature readiness",
    "Human correction notes",
    "Field provenance and confidence",
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
    assert pkt["sprint_number"] == 124
    assert pkt["packet_name"] == "NativeForge M0 SF-424 Autofill Preview Planning Packet"
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True
    assert pkt["may_define_sf424_preview_scope"] is True
    assert pkt["may_define_demo_safe_autofill_fields"] is True
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
    assert pkt["actual_form_generations"] == 0
    assert pkt["actual_autofill_writes"] == 0
    assert pkt["actual_grants_workspace_calls"] == 0


def test_m0_foundations_match_required_ten() -> None:
    pkt = build_pkt()
    assert pkt["m0_sf424_preview_foundations"] == list(M0_SF424_PREVIEW_FOUNDATIONS)
    assert len(M0_SF424_PREVIEW_FOUNDATIONS) == 10


def test_eighteen_sf424_field_groups_present() -> None:
    pkt = build_pkt()
    groups = pkt["sf424_field_groups"]
    assert len(groups) == 18
    names = [g["name"] for g in groups]
    for expected in EXPECTED_FIELD_GROUP_NAMES:
        assert expected in names


def test_each_field_group_has_at_least_two_acceptance_criteria() -> None:
    pkt = build_pkt()
    for g in pkt["sf424_field_groups"]:
        crit = g["acceptance_criteria"]
        assert isinstance(crit, list)
        assert len(crit) >= 2


def test_at_least_eight_risks_documented() -> None:
    pkt = build_pkt()
    assert len(pkt["risks_and_mitigations"]) >= 8


def test_markdown_required_section_headers() -> None:
    md = render_md()
    assert md.startswith(
        "# NativeForge M0 SF-424 Autofill Preview Planning Packet v1\n"
    )
    for h in REQUIRED_SECTION_HEADERS:
        assert h in md


def test_markdown_demo_safe_autofill_restrictions() -> None:
    md = render_md()
    lower = md.lower()
    assert "demo-safe" in lower and "autofill" in lower
    assert "no real customer data" in lower
    assert "no external validation" in lower


def test_markdown_missing_data_and_validation_preview_rules() -> None:
    md = render_md()
    lower = md.lower()
    assert "missing uei" in lower
    assert "missing ein" in lower
    assert "authorized representative" in lower
    assert "opportunity number" in lower
    assert "field confidence" in lower


def test_markdown_human_review_gate_language() -> None:
    md = render_md()
    lower = md.lower()
    assert "autofill preview cannot be treated as a final form" in lower
    assert "every autofilled field must remain editable" in lower
    assert "field provenance must be visible" in lower


def test_markdown_sovereignty_and_trust_requirements() -> None:
    md = render_md()
    lower = md.lower()
    assert "no customer data is required for seeded sf-424 demos" in lower
    assert "no customer data leaves the product during seeded demos" in lower
    assert "no model training on customer data without explicit written" in lower


def test_markdown_sprint124_does_not_build_phrases() -> None:
    md = render_md()
    lower = md.lower()
    assert "no real sf-424 generation" in lower
    assert "no form submission" in lower
    assert "no grants.gov workspace integration" in lower
    assert "no database migration" in lower


def test_markdown_sprint125_requirement_extraction_checklist() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 125" in lower
    assert "m0 requirement extraction checklist preview planning packet" in lower


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
