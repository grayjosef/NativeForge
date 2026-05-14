"""Sprint 137: M1 human review workflow controlled build readiness packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT137_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_human_review_workflow_controlled_build_readiness_packet_service"
)
sprint137_pkt = importlib.import_module(_SPRINT137_MOD)
build_pkt = (
    sprint137_pkt.build_active_source_activation_m1_human_review_workflow_controlled_build_readiness_packet
)
render_md = (
    sprint137_pkt.render_active_source_activation_m1_human_review_workflow_controlled_build_readiness_packet_markdown
)

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m1_human_review_workflow_controlled_build_readiness_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After Form Package Readiness",
    "## 3. M1 Human Review Workflow Readiness Objective",
    "## 4. Preview-Only Human Review Readiness Rules",
    "## 5. Required Human Review Readiness Field Groups",
    "## 6. Human Review Readiness Status Definitions",
    "## 7. Field-Level Acceptance Criteria",
    "## 8. Human Review Readiness by Product Area",
    "## 9. Review Gate Prerequisite Rules",
    "## 10. Routing, Override, and Audit Rules",
    "## 11. Sovereignty and Trust Requirements",
    "## 12. What Sprint 137 Does Not Build",
    "## 13. M1 Human Review Workflow Readiness Exit Criteria",
    "## 14. Risks and Mitigations",
    "## 15. Sprint 138 Recommended Next Step",
)

EXPECTED_FIELD_GROUP_NAMES = (
    "Human review readiness item identity",
    "Review gate name",
    "Review gate product area",
    "Reviewer role",
    "Buyer-owned or operator-owned flag",
    "Required review decision",
    "Required evidence",
    "Override reason requirement",
    "Audit trail requirement",
    "Routing prerequisite",
    "Sovereignty prerequisite",
    "Security prerequisite",
    "Submission-adjacent blocker status",
    "Escalation rule",
    "Acceptance criteria",
    "Risk note",
    "Non-production disclaimer",
    "Next sprint recommendation",
)

EXPECTED_HUMAN_REVIEW_READINESS_STATUSES = (
    "Not assessed",
    "Ready for controlled build planning",
    "Needs reviewer assignment",
    "Needs routing review",
    "Needs audit rule review",
    "Needs sovereignty review",
    "Blocked before workflow activation",
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
    assert pkt["sprint_number"] == 137
    assert pkt["packet_name"] == "NativeForge M1 Human Review Workflow Controlled Build Readiness Packet"
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True
    assert pkt["may_define_human_review_workflow_readiness"] is True
    assert pkt["may_define_review_gate_prerequisites"] is True
    assert pkt["may_define_audit_and_override_requirements"] is True
    assert pkt["may_define_acceptance_criteria"] is True
    assert pkt["may_define_guardrails"] is True


def test_packet_actual_counts_zero() -> None:
    pkt = build_pkt()
    for key, value in pkt.items():
        if key.startswith("actual_"):
            assert value == 0, key
    assert pkt["actual_review_routes_created"] == 0
    assert pkt["actual_approval_records_created"] == 0
    assert pkt["actual_workflows_activated"] == 0


def test_twelve_m1_human_review_workflow_readiness_foundations() -> None:
    pkt = build_pkt()
    rows = pkt["m1_human_review_workflow_controlled_build_readiness_foundations"]
    assert len(rows) == 12
    titles = {r["foundation_area"] for r in rows}
    assert "Review gate scope readiness" in titles
    assert "Buyer/operator ownership readiness" in titles


def test_eleven_human_review_readiness_by_product_area() -> None:
    pkt = build_pkt()
    areas = pkt["human_review_readiness_by_product_area"]
    assert len(areas) == 11
    keys = {a["product_area"] for a in areas}
    assert "source ingestion review" in keys
    assert "audit/export review" in keys


def test_eighteen_human_review_readiness_field_groups_present() -> None:
    pkt = build_pkt()
    groups = pkt["human_review_readiness_field_groups"]
    assert len(groups) == 18
    names = [g["name"] for g in groups]
    for expected in EXPECTED_FIELD_GROUP_NAMES:
        assert expected in names


def test_eight_human_review_readiness_statuses_present_with_disclaimers() -> None:
    pkt = build_pkt()
    rows = pkt["human_review_readiness_statuses"]
    assert len(rows) == 8
    statuses = [r["status"] for r in rows]
    for expected in EXPECTED_HUMAN_REVIEW_READINESS_STATUSES:
        assert expected in statuses
    disclaimer_phrases = (
        "not workflow activation",
        "not approval record creation",
        "not customer approval",
    )
    for r in rows:
        d = (r.get("definition") or "").lower()
        for needle in disclaimer_phrases:
            assert needle in d


def test_universal_disclaimer_present() -> None:
    pkt = build_pkt()
    u = (pkt.get("human_review_readiness_status_universal_disclaimer") or "").lower()
    assert "not workflow activation" in u
    assert "not approval record creation" in u
    assert "not customer approval" in u


def test_each_field_group_has_at_least_two_acceptance_criteria() -> None:
    pkt = build_pkt()
    for g in pkt["human_review_readiness_field_groups"]:
        crit = g["acceptance_criteria"]
        assert isinstance(crit, list)
        assert len(crit) >= 2


def test_at_least_eight_risks_documented() -> None:
    pkt = build_pkt()
    assert len(pkt["risks_and_mitigations"]) >= 8


def test_markdown_required_section_headers() -> None:
    md = render_md()
    assert md.startswith(
        "# NativeForge M1 Human Review Workflow Controlled Build Readiness Packet v1\n"
    )
    for h in REQUIRED_SECTION_HEADERS:
        assert h in md


def test_markdown_preview_only_human_review_readiness_rules() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 4. preview-only human review readiness rules" in lower
    assert "demo-safe" in lower or "demo safe" in lower
    assert "no real customer data" in lower
    assert "no external calls" in lower


def test_markdown_human_review_readiness_by_product_area() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 8. human review readiness by product area" in lower
    assert "source ingestion review" in lower
    assert "audit/export review" in lower


def test_markdown_review_gate_prerequisite_rules() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 9. review gate prerequisite rules" in lower
    assert "reviewer role" in lower
    assert "required evidence" in lower


def test_markdown_routing_override_and_audit_rules() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 10. routing, override, and audit rules" in lower
    assert "buyer-owned" in lower or "buyer owned" in lower
    assert "low-confidence" in lower or "low confidence" in lower


def test_markdown_sovereignty_and_trust_requirements() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 11. sovereignty and trust requirements" in lower
    assert "customer owns its data" in lower
    assert "no model training on customer data without explicit written consent" in lower


def test_markdown_explicit_does_not_build_phrases() -> None:
    md = render_md()
    lower = md.lower()
    assert "no review route creation" in lower
    assert "no approval record creation" in lower
    assert "no workflow activation" in lower
    assert "no customer approval" in lower
    assert "no customer data access" in lower
    assert "no database migration" in lower


def test_markdown_recommends_sprint138_audit_export_sovereignty_packet() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 138" in lower
    assert "m1 audit export and sovereignty controlled build readiness packet" in lower


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
