"""Sprint 121: M0 NOFO plain-language summary preview planning packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT121_MOD = (
    "nativeforge.services."
    "active_source_activation_m0_nofo_plain_language_summary_preview_planning_packet_service"
)
sprint121_pkt = importlib.import_module(_SPRINT121_MOD)
M0_NOFO_SUMMARY_PREVIEW_FOUNDATIONS = sprint121_pkt.M0_NOFO_SUMMARY_PREVIEW_FOUNDATIONS
build_pkt = sprint121_pkt.build_active_source_activation_m0_nofo_plain_language_summary_preview_planning_packet
render_md = (
    sprint121_pkt.render_active_source_activation_m0_nofo_plain_language_summary_preview_planning_packet_markdown
)

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m0_nofo_plain_language_summary_preview_planning_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After Tribal Eligibility Scoring",
    "## 3. M0 Summary Preview Objective",
    "## 4. Demo-Safe Summary Rules",
    "## 5. Required Field Groups",
    "## 6. Field-Level Acceptance Criteria",
    "## 7. Summary Preview to M0 Feature Mapping",
    "## 8. Human Review Gates",
    "## 9. Sovereignty and Trust Requirements",
    "## 10. What Sprint 121 Does Not Build",
    "## 11. M0 Exit Criteria",
    "## 12. Risks and Mitigations",
    "## 13. Sprint 122 Recommended Next Step",
)

EXPECTED_FIELD_GROUP_NAMES = (
    "NOFO title",
    "Funding agency",
    "Opportunity number",
    "Assistance listing/CFDA",
    "Eligibility preview",
    "Tribal relevance tags",
    "Mission alignment tags",
    "Key deadlines",
    "Funding amounts",
    "Match requirements",
    "Reporting burden",
    "Human review notes",
    "Demo-safe sample text",
    "Preview generation notes",
    "Source provenance",
    "Field-level acceptance criteria",
    "Human override reason",
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
    assert pkt["sprint_number"] == 121
    assert (
        pkt["packet_name"] == "NativeForge M0 NOFO Plain-Language Summary Preview Planning Packet"
    )
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True
    assert pkt["may_define_demo_safe_summary_scope"] is True
    assert pkt["may_define_plain_language_mapping_rules"] is True
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


def test_m0_foundations_match_required_ten() -> None:
    pkt = build_pkt()
    assert pkt["m0_nofo_summary_preview_foundations"] == list(M0_NOFO_SUMMARY_PREVIEW_FOUNDATIONS)
    assert len(M0_NOFO_SUMMARY_PREVIEW_FOUNDATIONS) == 10


def test_seventeen_field_groups_present() -> None:
    pkt = build_pkt()
    groups = pkt["summary_preview_field_groups"]
    assert len(groups) == 17
    names = [g["name"] for g in groups]
    for expected in EXPECTED_FIELD_GROUP_NAMES:
        assert expected in names


def test_each_field_group_has_at_least_two_acceptance_criteria() -> None:
    pkt = build_pkt()
    for g in pkt["summary_preview_field_groups"]:
        crit = g["acceptance_criteria"]
        assert isinstance(crit, list)
        assert len(crit) >= 2


def test_at_least_eight_risks_documented() -> None:
    pkt = build_pkt()
    assert len(pkt["risks_and_mitigations"]) >= 8


def test_markdown_required_section_headers() -> None:
    md = render_md()
    assert md.startswith(
        "# NativeForge M0 NOFO Plain-Language Summary Preview Planning Packet v1\n"
    )
    for h in REQUIRED_SECTION_HEADERS:
        assert h in md


def test_markdown_demo_safe_summary_restrictions() -> None:
    md = render_md()
    lower = md.lower()
    assert "demo-safe" in lower or "seeded" in lower
    assert "no live nofo parsing" in lower
    assert "no grants.gov api call" in lower
    assert "no sam.gov integration" in lower
    assert "no agency scraping" in lower
    assert "no llm calls" in lower


def test_markdown_human_review_gate_language() -> None:
    md = render_md()
    lower = md.lower()
    assert "plain-language summaries cannot be treated as legal or eligibility determinations" in lower
    assert "summary previews cannot hide conflicting seeded eligibility language" in lower
    assert "every summary block must remain overrideable" in lower


def test_markdown_sovereignty_and_trust_requirements() -> None:
    md = render_md()
    lower = md.lower()
    assert "no customer data is required to render m0 summary preview planning artifacts" in lower
    assert "no customer data leaves the product during seeded summary demos" in lower
    assert "no model training on customer data without explicit written consent" in lower


def test_markdown_no_live_nofo_parsing_or_generation() -> None:
    md = render_md()
    lower = md.lower()
    assert "no live nofo parsing" in lower
    assert "no real plain-language text generation from live sources" in lower


def test_markdown_sprint122_opportunity_scoring_planning_packet() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 122" in lower
    assert "m0 opportunity scoring & draft recommendation planning packet" in lower


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
