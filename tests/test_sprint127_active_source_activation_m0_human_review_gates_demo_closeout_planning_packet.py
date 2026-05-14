"""Sprint 127: M0 human review gates and demo closeout planning packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT127_MOD = (
    "nativeforge.services."
    "active_source_activation_m0_human_review_gates_demo_closeout_planning_packet_service"
)
sprint127_pkt = importlib.import_module(_SPRINT127_MOD)
M0_HUMAN_REVIEW_AND_DEMO_CLOSEOUT_FOUNDATIONS = (
    sprint127_pkt.M0_HUMAN_REVIEW_AND_DEMO_CLOSEOUT_FOUNDATIONS
)
build_pkt = (
    sprint127_pkt.build_active_source_activation_m0_human_review_gates_demo_closeout_planning_packet
)
render_md = (
    sprint127_pkt.render_active_source_activation_m0_human_review_gates_demo_closeout_planning_packet_markdown
)

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m0_human_review_gates_demo_closeout_planning_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Closes the M0 Planning Sequence",
    "## 3. M0 Human Review Objective",
    "## 4. Demo-Safe Review Rules",
    "## 5. Required Review Gate Field Groups",
    "## 6. Review Status Definitions",
    "## 7. Field-Level Acceptance Criteria",
    "## 8. Review Gates by M0 Feature",
    "## 9. Demo Closeout Criteria",
    "## 10. Human Override and Correction Rules",
    "## 11. Sovereignty and Trust Requirements",
    "## 12. What Sprint 127 Does Not Build",
    "## 13. M0 Exit Criteria for Human Review and Demo Closeout Planning",
    "## 14. Risks and Mitigations",
    "## 15. Sprint 128 Recommended Next Step",
)

EXPECTED_FIELD_GROUP_NAMES = (
    "Review gate identity",
    "Review gate source feature",
    "Review trigger",
    "Required reviewer role",
    "Review status",
    "Human override reason",
    "Field provenance visibility",
    "Source confidence visibility",
    "Missing data visibility",
    "Demo-safe data confirmation",
    "Approval limitation statement",
    "Buyer-facing caveat",
    "Audit readiness note",
    "Export readiness note",
    "Sovereignty trust note",
    "Runtime readiness dependency",
    "Closeout evidence",
    "Next sprint recommendation",
)

EXPECTED_REVIEW_STATUSES = (
    "Not reviewed",
    "Review needed",
    "Reviewed for demo",
    "Needs correction",
    "Blocked by missing data",
    "Blocked by low confidence",
    "Approved for demo narrative only",
    "Excluded from demo",
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
    assert pkt["sprint_number"] == 127
    assert pkt["packet_name"] == "NativeForge M0 Human Review Gates and Demo Closeout Planning Packet"
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True
    assert pkt["may_define_human_review_gate_scope"] is True
    assert pkt["may_define_demo_closeout_criteria"] is True
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
    assert pkt["actual_review_routes_created"] == 0
    assert pkt["actual_approval_records_created"] == 0
    assert pkt["actual_demo_closures_executed"] == 0


def test_m0_foundations_match_required_ten() -> None:
    pkt = build_pkt()
    assert pkt["m0_human_review_and_demo_closeout_foundations"] == list(
        M0_HUMAN_REVIEW_AND_DEMO_CLOSEOUT_FOUNDATIONS
    )
    assert len(M0_HUMAN_REVIEW_AND_DEMO_CLOSEOUT_FOUNDATIONS) == 10


def test_eighteen_review_gate_field_groups_present() -> None:
    pkt = build_pkt()
    groups = pkt["review_gate_field_groups"]
    assert len(groups) == 18
    names = [g["name"] for g in groups]
    for expected in EXPECTED_FIELD_GROUP_NAMES:
        assert expected in names


def test_eight_review_statuses_present() -> None:
    pkt = build_pkt()
    statuses = [s["status"] for s in pkt["review_status_definitions"]]
    assert len(statuses) == 8
    for expected in EXPECTED_REVIEW_STATUSES:
        assert expected in statuses


def test_each_review_status_disclaims_production_legal_submission() -> None:
    pkt = build_pkt()
    needle = "not a production approval, not a legal approval, and not a submission authorization"
    for s in pkt["review_status_definitions"]:
        desc = (s.get("description") or "").lower()
        note = (s.get("not_production_legal_or_submission") or "").lower()
        assert needle in desc or needle in note


def test_each_field_group_has_at_least_two_acceptance_criteria() -> None:
    pkt = build_pkt()
    for g in pkt["review_gate_field_groups"]:
        crit = g["acceptance_criteria"]
        assert isinstance(crit, list)
        assert len(crit) >= 2


def test_at_least_eight_risks_documented() -> None:
    pkt = build_pkt()
    assert len(pkt["risks_and_mitigations"]) >= 8


def test_markdown_required_section_headers() -> None:
    md = render_md()
    assert md.startswith(
        "# NativeForge M0 Human Review Gates and Demo Closeout Planning Packet v1\n"
    )
    for h in REQUIRED_SECTION_HEADERS:
        assert h in md


def test_markdown_demo_safe_review_rules() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 4. demo-safe review rules" in lower
    assert "demo-safe" in lower
    assert "no real customer data" in lower
    assert "no production approval" in lower
    assert "no legal approval" in lower
    assert "no submission authorization" in lower
    assert "no runtime workflow creation" in lower
    assert "no external calls" in lower


def test_markdown_review_gates_by_m0_feature() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 8. review gates by m0 feature" in lower
    assert "organizational entity profile" in lower
    assert "data sovereignty policy and export preview" in lower


def test_markdown_demo_closeout_criteria() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 9. demo closeout criteria" in lower
    assert "review status" in lower
    assert "seeded" in lower
    assert "low-confidence" in lower or "low confidence" in lower


def test_markdown_human_override_and_correction_rules() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 10. human override and correction rules" in lower
    assert "human override" in lower
    assert "provenance" in lower


def test_markdown_sovereignty_and_trust_requirements() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 11. sovereignty and trust requirements" in lower
    assert "customer owns its data" in lower
    assert "no model training on customer data without explicit written consent" in lower


def test_markdown_explicit_does_not_build_phrases() -> None:
    md = render_md()
    lower = md.lower()
    assert "no real review route creation" in lower
    assert "no approval record creation" in lower
    assert "no customer data access" in lower
    assert "no database migration" in lower


def test_markdown_recommends_sprint128_narrative_packet() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 128" in lower
    assert "m0 demo narrative and buyer walkthrough packet" in lower


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
