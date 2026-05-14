"""Sprint 139: M1 pilot operations and support controlled build readiness packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT139_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_pilot_operations_support_controlled_build_readiness_packet_service"
)
sprint139_pkt = importlib.import_module(_SPRINT139_MOD)
build_pkt = (
    sprint139_pkt.build_active_source_activation_m1_pilot_operations_support_controlled_build_readiness_packet
)
render_md = (
    sprint139_pkt.render_active_source_activation_m1_pilot_operations_support_controlled_build_readiness_packet_markdown
)

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m1_pilot_operations_support_controlled_build_readiness_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After Audit Export and Sovereignty Readiness",
    "## 3. M1 Pilot Operations and Support Readiness Objective",
    "## 4. Preview-Only Pilot Operations Rules",
    "## 5. Required Pilot Operations Readiness Field Groups",
    "## 6. Pilot Operations Readiness Status Definitions",
    "## 7. Field-Level Acceptance Criteria",
    "## 8. Pilot Operations Readiness by Support Area",
    "## 9. Support Workflow Prerequisite Rules",
    "## 10. Success Evidence, Feedback, and Escalation Rules",
    "## 11. Sovereignty and Trust Requirements",
    "## 12. What Sprint 139 Does Not Build",
    "## 13. M1 Pilot Operations and Support Readiness Exit Criteria",
    "## 14. Risks and Mitigations",
    "## 15. Sprint 140 Recommended Next Step",
)

EXPECTED_FIELD_GROUP_NAMES = (
    "Pilot operations readiness item identity",
    "Pilot operations area",
    "Support workflow area",
    "Human owner",
    "Buyer-facing or operator-facing flag",
    "Support intake prerequisite",
    "Escalation prerequisite",
    "Success evidence requirement",
    "Feedback capture requirement",
    "Training or handoff requirement",
    "Data handling prerequisite",
    "Sovereignty prerequisite",
    "Security prerequisite",
    "Pilot blocker status",
    "Acceptance criteria",
    "Risk note",
    "Non-production disclaimer",
    "Next sprint recommendation",
)

EXPECTED_PILOT_OPERATIONS_READINESS_STATUSES = (
    "Not assessed",
    "Ready for controlled build planning",
    "Needs support owner",
    "Needs intake review",
    "Needs escalation review",
    "Needs success evidence review",
    "Blocked before pilot operations build",
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
    assert pkt["sprint_number"] == 139
    assert pkt["packet_name"] == "NativeForge M1 Pilot Operations and Support Controlled Build Readiness Packet"
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True
    assert pkt["may_define_pilot_operations_readiness"] is True
    assert pkt["may_define_support_workflow_prerequisites"] is True
    assert pkt["may_define_success_evidence_requirements"] is True
    assert pkt["may_define_acceptance_criteria"] is True
    assert pkt["may_define_guardrails"] is True


def test_packet_actual_counts_zero() -> None:
    pkt = build_pkt()
    for key, value in pkt.items():
        if key.startswith("actual_"):
            assert value == 0, key
    assert pkt["actual_pilot_accounts_created"] == 0
    assert pkt["actual_support_workflows_activated"] == 0
    assert pkt["actual_customer_records_created"] == 0


def test_twelve_m1_pilot_operations_support_readiness_foundations() -> None:
    pkt = build_pkt()
    rows = pkt["m1_pilot_operations_support_controlled_build_readiness_foundations"]
    assert len(rows) == 12
    titles = {r["foundation_area"] for r in rows}
    assert "Pilot operations scope readiness" in titles
    assert "Pilot closeout readiness" in titles


def test_eleven_pilot_operations_readiness_by_support_area() -> None:
    pkt = build_pkt()
    areas = pkt["pilot_operations_readiness_by_support_area"]
    assert len(areas) == 11
    keys = {a["support_area"] for a in areas}
    assert "pilot kickoff planning" in keys
    assert "pilot closeout" in keys


def test_eighteen_pilot_operations_readiness_field_groups_present() -> None:
    pkt = build_pkt()
    groups = pkt["pilot_operations_readiness_field_groups"]
    assert len(groups) == 18
    names = [g["name"] for g in groups]
    for expected in EXPECTED_FIELD_GROUP_NAMES:
        assert expected in names


def test_eight_pilot_operations_readiness_statuses_present_with_disclaimers() -> None:
    pkt = build_pkt()
    rows = pkt["pilot_operations_readiness_statuses"]
    assert len(rows) == 8
    statuses = [r["status"] for r in rows]
    for expected in EXPECTED_PILOT_OPERATIONS_READINESS_STATUSES:
        assert expected in statuses
    disclaimer_phrases = (
        "not pilot onboarding",
        "not support workflow activation",
        "not customer record creation",
    )
    for r in rows:
        d = (r.get("definition") or "").lower()
        for needle in disclaimer_phrases:
            assert needle in d


def test_universal_disclaimer_present() -> None:
    pkt = build_pkt()
    u = (pkt.get("pilot_operations_readiness_status_universal_disclaimer") or "").lower()
    assert "not pilot onboarding" in u
    assert "not support workflow activation" in u
    assert "not customer record creation" in u


def test_each_field_group_has_at_least_two_acceptance_criteria() -> None:
    pkt = build_pkt()
    for g in pkt["pilot_operations_readiness_field_groups"]:
        crit = g["acceptance_criteria"]
        assert isinstance(crit, list)
        assert len(crit) >= 2


def test_at_least_eight_risks_documented() -> None:
    pkt = build_pkt()
    assert len(pkt["risks_and_mitigations"]) >= 8


def test_markdown_required_section_headers() -> None:
    md = render_md()
    assert md.startswith(
        "# NativeForge M1 Pilot Operations and Support Controlled Build Readiness Packet v1\n"
    )
    for h in REQUIRED_SECTION_HEADERS:
        assert h in md


def test_markdown_preview_only_pilot_operations_rules() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 4. preview-only pilot operations rules" in lower
    assert "demo-safe" in lower or "demo safe" in lower
    assert "no real customer data" in lower
    assert "no external calls" in lower


def test_markdown_pilot_operations_readiness_by_support_area() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 8. pilot operations readiness by support area" in lower
    assert "pilot kickoff planning" in lower
    assert "buyer follow-up capture" in lower


def test_markdown_support_workflow_prerequisite_rules() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 9. support workflow prerequisite rules" in lower
    assert "human owner" in lower
    assert "support intake" in lower


def test_markdown_success_evidence_feedback_and_escalation_rules() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 10. success evidence, feedback, and escalation rules" in lower
    assert "observable" in lower
    assert "operator-owned" in lower or "operator owned" in lower


def test_markdown_sovereignty_and_trust_requirements() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 11. sovereignty and trust requirements" in lower
    assert "customer owns its data" in lower
    assert "no model training on customer data without explicit written consent" in lower


def test_markdown_explicit_does_not_build_phrases() -> None:
    md = render_md()
    lower = md.lower()
    assert "no pilot account creation" in lower
    assert "no support workflow activation" in lower
    assert "no customer record creation" in lower
    assert "no customer onboarding" in lower
    assert "no customer data access" in lower
    assert "no database migration" in lower


def test_markdown_recommends_sprint140_demo_to_build_closeout_packet() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 140" in lower
    assert "m1 pilot demo-to-build transition closeout packet" in lower


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
