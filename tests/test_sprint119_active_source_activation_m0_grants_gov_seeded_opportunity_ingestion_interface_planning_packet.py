"""Sprint 119: M0 Grants.gov seeded opportunity ingestion interface planning packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT119_MOD = (
    "nativeforge.services."
    "active_source_activation_m0_grants_gov_seeded_opportunity_ingestion_interface_planning_packet_service"
)
sprint119_pkt = importlib.import_module(_SPRINT119_MOD)
M0_SEEDED_OPPORTUNITY_FOUNDATIONS = sprint119_pkt.M0_SEEDED_OPPORTUNITY_FOUNDATIONS
build_pkt = sprint119_pkt.build_active_source_activation_m0_grants_gov_seeded_opportunity_ingestion_interface_planning_packet
render_md = (
    sprint119_pkt.render_active_source_activation_m0_grants_gov_seeded_opportunity_ingestion_interface_planning_packet_markdown
)

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m0_grants_gov_seeded_opportunity_ingestion_interface_planning_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After Entity Profile",
    "## 3. M0 Seeded Opportunity Objective",
    "## 4. Demo-Safe Source Rules",
    "## 5. Required Seeded Opportunity Field Groups",
    "## 6. Field-Level Acceptance Criteria",
    "## 7. Seeded Opportunity to M0 Feature Mapping",
    "## 8. Human Review Gates",
    "## 9. Source Provenance and Freshness Requirements",
    "## 10. Sovereignty and Trust Requirements",
    "## 11. What Sprint 119 Does Not Build",
    "## 12. M0 Exit Criteria for Seeded Opportunity Planning",
    "## 13. Risks and Mitigations",
    "## 14. Sprint 120 Recommended Next Step",
)

EXPECTED_FIELD_GROUP_NAMES = (
    "Opportunity identity",
    "Source metadata",
    "Agency and sub-agency data",
    "Assistance listing / CFDA data",
    "Eligibility data",
    "Tribal relevance tags",
    "Funding amount data",
    "Deadline and timeline data",
    "NOFO attachment metadata",
    "Requirement preview metadata",
    "Match and cost-share metadata",
    "Reporting burden metadata",
    "Mission fit taxonomy tags",
    "Pursuit recommendation preview data",
    "Human review and override metadata",
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
    assert pkt["sprint_number"] == 119
    assert (
        pkt["packet_name"]
        == "NativeForge M0 Grants.gov Seeded Opportunity Ingestion Interface Planning Packet"
    )
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True
    assert pkt["may_define_seeded_ingestion_scope"] is True
    assert pkt["may_define_demo_safe_opportunity_contract"] is True
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
    assert pkt["m0_seeded_opportunity_foundations"] == list(M0_SEEDED_OPPORTUNITY_FOUNDATIONS)
    assert len(M0_SEEDED_OPPORTUNITY_FOUNDATIONS) == 10


def test_fifteen_field_groups_present() -> None:
    pkt = build_pkt()
    groups = pkt["seeded_opportunity_field_groups"]
    assert len(groups) == 15
    names = [g["name"] for g in groups]
    for expected in EXPECTED_FIELD_GROUP_NAMES:
        assert expected in names


def test_each_field_group_has_at_least_two_acceptance_criteria() -> None:
    pkt = build_pkt()
    for g in pkt["seeded_opportunity_field_groups"]:
        crit = g["acceptance_criteria"]
        assert isinstance(crit, list)
        assert len(crit) >= 2


def test_at_least_eight_risks_documented() -> None:
    pkt = build_pkt()
    assert len(pkt["risks_and_mitigations"]) >= 8


def test_markdown_required_section_headers() -> None:
    md = render_md()
    assert md.startswith(
        "# NativeForge M0 Grants.gov Seeded Opportunity Ingestion Interface Planning Packet v1\n"
    )
    for h in REQUIRED_SECTION_HEADERS:
        assert h in md


def test_markdown_demo_safe_source_restrictions() -> None:
    md = render_md()
    lower = md.lower()
    assert "demo-safe" in lower or "seeded" in lower
    assert "no live grants.gov ingestion" in lower
    assert "no grants.gov api call" in lower
    assert "no sam.gov integration" in lower
    assert "no agency scraping" in lower
    assert "no real customer data" in lower
    assert "no ai-generated extraction from real nofos" in lower


def test_markdown_human_review_gate_language() -> None:
    md = render_md()
    lower = md.lower()
    assert "eligibility preview cannot be treated as confirmed without human review" in lower
    assert "pursuit recommendation must be reviewable and overrideable" in lower
    assert "missing or ambiguous eligibility must be flagged" in lower
    assert "missing deadline data must block pursuit-ready status" in lower
    assert "seeded source provenance must be visible in every opportunity detail view" in lower


def test_markdown_source_provenance_and_freshness_requirements() -> None:
    md = render_md()
    lower = md.lower()
    assert "every seeded record must identify its demo source basis" in lower
    assert "seeded_at" in lower and "fixture_version" in lower
    assert "every displayed opportunity must clearly indicate demo-safe seeded data" in lower
    assert "future live ingestion must preserve source urls" in lower
    assert "no live freshness monitoring occurs in m0 planning" in lower


def test_markdown_sovereignty_and_trust_requirements() -> None:
    md = render_md()
    lower = md.lower()
    assert "no customer data required to view seeded opportunities" in lower
    assert "no customer data leaves the product during seeded demos" in lower
    assert "no model training on customer data without explicit written consent" in lower
    assert "future live ingestion must preserve auditability" in lower
    assert "opportunity recommendations must never override human judgment" in lower


def test_markdown_no_live_grants_gov_ingestion() -> None:
    md = render_md()
    assert "No live Grants.gov ingestion" in md


def test_markdown_no_grants_gov_api_call() -> None:
    md = render_md()
    assert "No Grants.gov API call" in md


def test_markdown_no_database_migration() -> None:
    md = render_md()
    assert "No database migration" in md


def test_markdown_sprint120_tribal_eligibility_and_mission_fit_preview_planning_packet() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 120" in lower
    assert "m0 tribal eligibility tagging and mission fit scoring preview planning packet" in lower


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
