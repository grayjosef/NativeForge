"""Sprint 130: M0 pilot transition and M1 readiness planning packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT130_MOD = (
    "nativeforge.services.active_source_activation_m0_pilot_transition_m1_readiness_planning_packet_service"
)
sprint130_pkt = importlib.import_module(_SPRINT130_MOD)
build_pkt = sprint130_pkt.build_active_source_activation_m0_pilot_transition_m1_readiness_planning_packet
render_md = sprint130_pkt.render_active_source_activation_m0_pilot_transition_m1_readiness_planning_packet_markdown

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m0_pilot_transition_m1_readiness_planning_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After Demo Readiness Evidence Planning",
    "## 3. M0-to-M1 Transition Objective",
    "## 4. Demo-Safe Pilot Transition Rules",
    "## 5. Required Pilot Readiness Field Groups",
    "## 6. Pilot Readiness Status Definitions",
    "## 7. Field-Level Acceptance Criteria",
    "## 8. M1 Readiness by Product Area",
    "## 9. Buyer Follow-Up Question Capture",
    "## 10. M1 Implementation Dependency Rules",
    "## 11. Sovereignty and Trust Requirements",
    "## 12. What Sprint 130 Does Not Build",
    "## 13. M0 Exit Criteria for Pilot Transition Planning",
    "## 14. Risks and Mitigations",
    "## 15. Sprint 131 Recommended Next Step",
)

EXPECTED_FIELD_GROUP_NAMES = (
    "Pilot readiness item identity",
    "Source M0 evidence reference",
    "Buyer follow-up question",
    "Buyer concern category",
    "M1 feature dependency",
    "Pilot fit signal",
    "Data sovereignty dependency",
    "Security/access dependency",
    "Source ingestion dependency",
    "NOFO extraction dependency",
    "Form package dependency",
    "Human review dependency",
    "Export/audit dependency",
    "Implementation risk note",
    "Operator action required",
    "Go/no-go recommendation",
    "Non-production disclaimer",
    "Next sprint recommendation",
)

EXPECTED_PILOT_READINESS_STATUSES = (
    "Not assessed",
    "Ready for M1 planning",
    "Needs buyer clarification",
    "Needs technical discovery",
    "Needs sovereignty review",
    "Needs security review",
    "Blocked for pilot",
    "Deferred beyond M1",
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
    assert pkt["sprint_number"] == 130
    assert pkt["packet_name"] == "NativeForge M0 Pilot Transition and M1 Readiness Planning Packet"
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True
    assert pkt["may_define_m0_to_m1_transition_scope"] is True
    assert pkt["may_define_pilot_readiness_fields"] is True
    assert pkt["may_define_buyer_followup_questions"] is True
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
    assert pkt["actual_pilot_accounts_created"] == 0
    assert pkt["actual_customer_onboarding_started"] == 0
    assert pkt["actual_m1_workflows_activated"] == 0


def test_twelve_m0_to_m1_transition_foundations() -> None:
    pkt = build_pkt()
    areas = pkt["m0_to_m1_transition_foundations"]
    assert len(areas) == 12
    titles = {a["foundation_area"] for a in areas}
    assert "M0 demo outcome review" in titles
    assert "M1 implementation dependency tracking" in titles


def test_eighteen_pilot_readiness_field_groups_present() -> None:
    pkt = build_pkt()
    groups = pkt["pilot_readiness_field_groups"]
    assert len(groups) == 18
    names = [g["name"] for g in groups]
    for expected in EXPECTED_FIELD_GROUP_NAMES:
        assert expected in names


def test_eight_pilot_readiness_statuses_present_with_disclaimers() -> None:
    pkt = build_pkt()
    rows = pkt["pilot_readiness_statuses"]
    assert len(rows) == 8
    statuses = [r["status"] for r in rows]
    for expected in EXPECTED_PILOT_READINESS_STATUSES:
        assert expected in statuses
    disclaimer_phrases = (
        "not customer onboarding",
        "not production activation",
        "not a signed pilot commitment",
    )
    for r in rows:
        d = (r.get("definition") or "").lower()
        for needle in disclaimer_phrases:
            assert needle in d


def test_universal_disclaimer_present() -> None:
    pkt = build_pkt()
    u = (pkt.get("pilot_readiness_status_universal_disclaimer") or "").lower()
    assert "not customer onboarding" in u
    assert "not production activation" in u
    assert "not a signed pilot commitment" in u


def test_each_field_group_has_at_least_two_acceptance_criteria() -> None:
    pkt = build_pkt()
    for g in pkt["pilot_readiness_field_groups"]:
        crit = g["acceptance_criteria"]
        assert isinstance(crit, list)
        assert len(crit) >= 2


def test_at_least_eight_risks_documented() -> None:
    pkt = build_pkt()
    assert len(pkt["risks_and_mitigations"]) >= 8


def test_markdown_required_section_headers() -> None:
    md = render_md()
    assert md.startswith(
        "# NativeForge M0 Pilot Transition and M1 Readiness Planning Packet v1\n"
    )
    for h in REQUIRED_SECTION_HEADERS:
        assert h in md


def test_markdown_demo_safe_pilot_transition_rules() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 4. demo-safe pilot transition rules" in lower
    assert "demo-safe" in lower
    assert "no real customer data" in lower
    assert "no external calls" in lower


def test_markdown_m1_readiness_by_product_area() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 8. m1 readiness by product area" in lower
    assert "organizational entity profile" in lower
    assert "pilot support and implementation operations" in lower


def test_markdown_buyer_follow_up_question_capture() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 9. buyer follow-up question capture" in lower
    assert "buyer questions must map to m1 feature dependencies" in lower


def test_markdown_m1_implementation_dependency_rules() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 10. m1 implementation dependency rules" in lower
    assert "no runtime activation occurs in this sprint" in lower


def test_markdown_sovereignty_and_trust_requirements() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 11. sovereignty and trust requirements" in lower
    assert "customer owns its data" in lower
    assert "no model training on customer data without explicit written consent" in lower


def test_markdown_explicit_scope_phrases() -> None:
    md = render_md()
    lower = md.lower()
    assert "no pilot account creation" in lower
    assert "no customer onboarding" in lower
    assert "no m1 workflow activation" in lower
    assert "no customer data access" in lower
    assert "no database migration" in lower


def test_markdown_recommends_sprint131_m1_scope_packet() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 131" in lower
    assert "m1 pilot scope and delivery boundary packet" in lower


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
