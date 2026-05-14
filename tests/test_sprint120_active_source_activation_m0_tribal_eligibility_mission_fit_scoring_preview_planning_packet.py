"""Sprint 120: M0 tribal eligibility and mission fit scoring preview planning packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT120_MOD = (
    "nativeforge.services."
    "active_source_activation_m0_tribal_eligibility_mission_fit_scoring_preview_planning_packet_service"
)
sprint120_pkt = importlib.import_module(_SPRINT120_MOD)
M0_SCORING_PREVIEW_FOUNDATIONS = sprint120_pkt.M0_SCORING_PREVIEW_FOUNDATIONS
build_pkt = sprint120_pkt.build_active_source_activation_m0_tribal_eligibility_mission_fit_scoring_preview_planning_packet
render_md = (
    sprint120_pkt.render_active_source_activation_m0_tribal_eligibility_mission_fit_scoring_preview_planning_packet_markdown
)

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m0_tribal_eligibility_mission_fit_scoring_preview_planning_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After Seeded Opportunity Planning",
    "## 3. M0 Scoring Preview Objective",
    "## 4. Demo-Safe Scoring Rules",
    "## 5. Required Scoring Factor Groups",
    "## 6. Factor-Level Acceptance Criteria",
    "## 7. Scoring Preview to M0 Feature Mapping",
    "## 8. Recommendation Preview Tiers",
    "## 9. Human Review Gates",
    "## 10. Sovereignty and Trust Requirements",
    "## 11. What Sprint 120 Does Not Build",
    "## 12. M0 Exit Criteria for Scoring Preview Planning",
    "## 13. Risks and Mitigations",
    "## 14. Sprint 121 Recommended Next Step",
)

EXPECTED_FACTOR_GROUP_NAMES = (
    "Entity type match",
    "Federally recognized tribe eligibility",
    "Tribal organization eligibility",
    "Alaska Native entity eligibility",
    "Native Hawaiian organization eligibility",
    "Native nonprofit eligibility",
    "Tribal college eligibility",
    "Mission priority alignment",
    "Geographic service area alignment",
    "Funding amount fit",
    "Deadline feasibility",
    "Staff capacity fit",
    "Match and cost-share risk",
    "Reporting burden",
    "Source confidence",
    "Eligibility ambiguity",
    "Human override reason",
)

EXPECTED_RECOMMENDATION_TIERS = (
    "Strong preview fit",
    "Preview fit",
    "Preview fit with conditions",
    "Needs human review",
    "Preview do not pursue",
    "Preview disqualified",
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
    assert pkt["sprint_number"] == 120
    assert (
        pkt["packet_name"]
        == "NativeForge M0 Tribal Eligibility Tagging and Mission Fit Scoring Preview Planning Packet"
    )
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True
    assert pkt["may_define_scoring_preview_scope"] is True
    assert pkt["may_define_demo_safe_scoring_factors"] is True
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


def test_m0_foundations_match_required_ten() -> None:
    pkt = build_pkt()
    assert pkt["m0_scoring_preview_foundations"] == list(M0_SCORING_PREVIEW_FOUNDATIONS)
    assert len(M0_SCORING_PREVIEW_FOUNDATIONS) == 10


def test_seventeen_factor_groups_present() -> None:
    pkt = build_pkt()
    groups = pkt["scoring_factor_groups"]
    assert len(groups) == 17
    names = [g["name"] for g in groups]
    for expected in EXPECTED_FACTOR_GROUP_NAMES:
        assert expected in names


def test_each_factor_group_has_at_least_two_acceptance_criteria() -> None:
    pkt = build_pkt()
    for g in pkt["scoring_factor_groups"]:
        crit = g["acceptance_criteria"]
        assert isinstance(crit, list)
        assert len(crit) >= 2


def test_at_least_eight_risks_documented() -> None:
    pkt = build_pkt()
    assert len(pkt["risks_and_mitigations"]) >= 8


def test_markdown_required_section_headers() -> None:
    md = render_md()
    assert md.startswith(
        "# NativeForge M0 Tribal Eligibility Tagging and Mission Fit Scoring Preview Planning Packet v1\n"
    )
    for h in REQUIRED_SECTION_HEADERS:
        assert h in md


def test_markdown_demo_safe_scoring_restrictions() -> None:
    md = render_md()
    lower = md.lower()
    assert "demo-safe" in lower or "seeded" in lower
    assert "no live grants.gov ingestion" in lower
    assert "no grants.gov api call" in lower
    assert "no sam.gov integration" in lower
    assert "no agency scraping" in lower
    assert "no real nofo parsing" in lower
    assert "no real customer data" in lower
    assert "no llm-generated eligibility conclusions" in lower
    assert "no final eligibility determinations" in lower


def test_markdown_six_recommendation_preview_tiers() -> None:
    md = render_md()
    for tier in EXPECTED_RECOMMENDATION_TIERS:
        assert tier in md


def test_markdown_tiers_state_not_final_eligibility_determination() -> None:
    md = render_md()
    lower = md.lower()
    assert "not a final eligibility determination" in lower
    assert lower.count("not a final eligibility determination") >= 6


def test_markdown_human_review_gate_language() -> None:
    md = render_md()
    lower = md.lower()
    assert "eligibility preview cannot be treated as confirmed without human review" in lower
    assert "disqualification preview cannot block a user from reviewing the opportunity" in lower
    assert "pursuit recommendation must be reviewable and overrideable" in lower
    assert "ambiguous eligibility must always route to human review" in lower
    assert "source confidence must be visible beside scoring output" in lower
    assert "human override reason must be stored in future runtime design" in lower


def test_markdown_sovereignty_and_trust_requirements() -> None:
    md = render_md()
    lower = md.lower()
    assert "no customer data required for seeded scoring demos" in lower
    assert "no customer data leaves the product during seeded demos" in lower
    assert "no model training on customer data without explicit written consent" in lower
    assert "recommendation previews never override human judgment" in lower
    assert "future runtime scoring must be auditable and explainable" in lower
    assert "scoring rationale must be visible to the user" in lower


def test_markdown_no_real_eligibility_scoring() -> None:
    md = render_md()
    assert "No real eligibility scoring" in md


def test_markdown_no_final_eligibility_determination() -> None:
    md = render_md()
    assert "No final eligibility determination" in md


def test_markdown_no_database_migration() -> None:
    md = render_md()
    assert "No database migration" in md


def test_markdown_sprint121_nofo_plain_language_summary_preview_planning_packet() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 121" in lower
    assert "m0 nofo plain-language summary preview planning packet" in lower


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
