"""Sprint 122: M0 opportunity scoring and draft recommendation planning packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT122_MOD = (
    "nativeforge.services."
    "active_source_activation_m0_opportunity_scoring_draft_recommendation_planning_packet_service"
)
sprint122_pkt = importlib.import_module(_SPRINT122_MOD)
M0_RECOMMENDATION_PREVIEW_FOUNDATIONS = sprint122_pkt.M0_RECOMMENDATION_PREVIEW_FOUNDATIONS
build_pkt = sprint122_pkt.build_active_source_activation_m0_opportunity_scoring_draft_recommendation_planning_packet
render_md = (
    sprint122_pkt.render_active_source_activation_m0_opportunity_scoring_draft_recommendation_planning_packet_markdown
)

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m0_opportunity_scoring_draft_recommendation_planning_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After NOFO Summary Preview",
    "## 3. M0 Recommendation Preview Objective",
    "## 4. Demo-Safe Recommendation Rules",
    "## 5. Required Recommendation Factor Groups",
    "## 6. Factor-Level Acceptance Criteria",
    "## 7. Recommendation Preview to M0 Feature Mapping",
    "## 8. Recommendation Preview Tiers",
    "## 9. Draft Recommendation Narrative Constraints",
    "## 10. Human Review Gates",
    "## 11. Sovereignty and Trust Requirements",
    "## 12. What Sprint 122 Does Not Build",
    "## 13. M0 Exit Criteria for Recommendation Planning",
    "## 14. Risks and Mitigations",
    "## 15. Sprint 123 Recommended Next Step",
)

EXPECTED_FACTOR_GROUP_NAMES = (
    "Eligibility preview result",
    "Eligibility confidence",
    "Mission fit score",
    "Tribal relevance score",
    "Funding priority alignment",
    "Deadline feasibility",
    "Staff capacity fit",
    "Match and cost-share risk",
    "Reporting burden risk",
    "Source confidence",
    "NOFO summary confidence",
    "Required attachment readiness",
    "Authorized representative readiness",
    "SF-424 preview readiness",
    "Pursuit effort estimate",
    "Pursuit recommendation tier",
    "Human override reason",
    "Draft recommendation narrative constraints",
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
    assert pkt["sprint_number"] == 122
    assert (
        pkt["packet_name"] == "NativeForge M0 Opportunity Scoring and Draft Recommendation Planning Packet"
    )
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True
    assert pkt["may_define_recommendation_preview_scope"] is True
    assert pkt["may_define_demo_safe_recommendation_factors"] is True
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
    assert pkt["actual_eligibility_adjudications"] == 0
    assert pkt["actual_submission_recommendations"] == 0
    assert pkt["actual_draft_generations"] == 0


def test_m0_foundations_match_required_ten() -> None:
    pkt = build_pkt()
    assert pkt["m0_recommendation_preview_foundations"] == list(M0_RECOMMENDATION_PREVIEW_FOUNDATIONS)
    assert len(M0_RECOMMENDATION_PREVIEW_FOUNDATIONS) == 10


def test_eighteen_recommendation_factor_groups_present() -> None:
    pkt = build_pkt()
    groups = pkt["recommendation_factor_groups"]
    assert len(groups) == 18
    names = [g["name"] for g in groups]
    for expected in EXPECTED_FACTOR_GROUP_NAMES:
        assert expected in names


def test_each_factor_group_has_at_least_two_acceptance_criteria() -> None:
    pkt = build_pkt()
    for g in pkt["recommendation_factor_groups"]:
        crit = g["acceptance_criteria"]
        assert isinstance(crit, list)
        assert len(crit) >= 2


def test_at_least_eight_risks_documented() -> None:
    pkt = build_pkt()
    assert len(pkt["risks_and_mitigations"]) >= 8


def test_markdown_required_section_headers() -> None:
    md = render_md()
    assert md.startswith(
        "# NativeForge M0 Opportunity Scoring and Draft Recommendation Planning Packet v1\n"
    )
    for h in REQUIRED_SECTION_HEADERS:
        assert h in md


def test_markdown_demo_safe_recommendation_restrictions() -> None:
    md = render_md()
    lower = md.lower()
    assert "demo-safe" in lower or "seeded" in lower
    assert "no live grants.gov" in lower
    assert "no sam.gov" in lower
    assert "no agency scraping" in lower
    assert "no real nofo parsing" in lower
    assert "no llm-generated recommendation" in lower or "no llm" in lower


def test_markdown_six_recommendation_preview_tiers() -> None:
    md = render_md()
    lower = md.lower()
    assert "strong pursue preview" in lower
    assert "pursue preview" in lower
    assert "pursue with conditions preview" in lower
    assert "needs human review" in lower
    assert "hold for clarification" in lower
    assert "do not pursue preview" in lower


def test_markdown_tiers_not_final_pursuit_or_eligibility() -> None:
    md = render_md()
    lower = md.lower()
    assert "not a final pursuit decision" in lower
    assert "not a final eligibility determination" in lower


def test_markdown_draft_recommendation_narrative_constraints() -> None:
    md = render_md()
    lower = md.lower()
    assert "narrative must explain factors" in lower
    assert "pan-indian" in lower or "pan-indian language" in lower


def test_markdown_human_review_gate_language() -> None:
    md = render_md()
    lower = md.lower()
    assert "recommendation preview cannot be treated as final without human review" in lower
    assert "do-not-pursue preview cannot block a user from reviewing the opportunity" in lower


def test_markdown_sovereignty_and_trust_requirements() -> None:
    md = render_md()
    lower = md.lower()
    assert "no customer data required for seeded recommendation demos" in lower
    assert "no customer data leaves the product during seeded demos" in lower
    assert "no model training on customer data without explicit written consent" in lower


def test_markdown_no_real_scoring_or_final_recommendation_or_migration() -> None:
    md = render_md()
    lower = md.lower()
    assert "no real opportunity scoring" in lower
    assert "no final pursuit recommendation" in lower
    assert "no database migration" in lower


def test_markdown_sprint123_kanban_deadline_planning_packet() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 123" in lower
    assert "m0 pursuit pipeline kanban and deadline tracking planning packet" in lower


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
