"""Sprint 140: M1 pilot demo-to-build transition closeout packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT140_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_pilot_demo_to_build_transition_closeout_packet_service"
)
sprint140_pkt = importlib.import_module(_SPRINT140_MOD)
build_pkt = sprint140_pkt.build_active_source_activation_m1_pilot_demo_to_build_transition_closeout_packet
render_md = (
    sprint140_pkt.render_active_source_activation_m1_pilot_demo_to_build_transition_closeout_packet_markdown
)

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m1_pilot_demo_to_build_transition_closeout_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After Pilot Operations and Support Readiness",
    "## 3. M1 Demo-to-Build Transition Objective",
    "## 4. Preview-Only Transition Closeout Rules",
    "## 5. Required Transition Closeout Field Groups",
    "## 6. Transition Closeout Status Definitions",
    "## 7. Field-Level Acceptance Criteria",
    "## 8. M1 Readiness Evidence by Product Area",
    "## 9. Blocker and Approval Gate Rules",
    "## 10. Demo-to-Build Transition Rules",
    "## 11. Sovereignty and Trust Requirements",
    "## 12. What Sprint 140 Does Not Build",
    "## 13. M1 Transition Closeout Exit Criteria",
    "## 14. Risks and Mitigations",
    "## 15. Sprint 141 Recommended Next Step",
)

EXPECTED_FIELD_GROUP_NAMES = (
    "Transition closeout item identity",
    "M1 readiness area",
    "Source sprint reference",
    "Evidence summary",
    "Closeout status",
    "Blocker status",
    "Human approval requirement",
    "Deferred item flag",
    "Buyer-facing note",
    "Operator-facing note",
    "Risk transfer note",
    "Sovereignty prerequisite",
    "Security prerequisite",
    "Controlled build authorization requirement",
    "Acceptance criteria",
    "Risk note",
    "Non-production disclaimer",
    "Next sprint recommendation",
)

EXPECTED_TRANSITION_CLOSEOUT_STATUSES = (
    "Not assessed",
    "Ready for closeout review",
    "Ready for controlled build authorization review",
    "Needs human approval",
    "Needs blocker resolution",
    "Deferred beyond M1",
    "Blocked before build transition",
    "Closed for planning only",
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
    assert pkt["sprint_number"] == 140
    assert pkt["packet_name"] == "NativeForge M1 Pilot Demo-to-Build Transition Closeout Packet"
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True
    assert pkt["may_define_transition_closeout_readiness"] is True
    assert pkt["may_define_m1_evidence_summary"] is True
    assert pkt["may_define_blockers_and_approvals"] is True
    assert pkt["may_define_acceptance_criteria"] is True
    assert pkt["may_define_guardrails"] is True


def test_packet_actual_counts_zero() -> None:
    pkt = build_pkt()
    for key, value in pkt.items():
        if key.startswith("actual_"):
            assert value == 0, key
    assert pkt["actual_pilots_launched"] == 0
    assert pkt["actual_customer_onboarding_started"] == 0
    assert pkt["actual_production_systems_activated"] == 0


def test_twelve_m1_demo_to_build_transition_closeout_preview_foundations() -> None:
    pkt = build_pkt()
    rows = pkt["m1_demo_to_build_transition_closeout_preview_foundations"]
    assert len(rows) == 12
    titles = {r["foundation_area"] for r in rows}
    assert "M1 evidence summary readiness" in titles
    assert "Sprint 141 transition readiness" in titles


def test_eleven_m1_readiness_evidence_by_product_area() -> None:
    pkt = build_pkt()
    areas = pkt["m1_readiness_evidence_by_product_area"]
    assert len(areas) == 11
    keys = {a["product_area"] for a in areas}
    assert "source ingestion readiness" in keys
    assert "controlled build authorization readiness" in keys


def test_eighteen_transition_closeout_field_groups_present() -> None:
    pkt = build_pkt()
    groups = pkt["transition_closeout_field_groups"]
    assert len(groups) == 18
    names = [g["name"] for g in groups]
    for expected in EXPECTED_FIELD_GROUP_NAMES:
        assert expected in names


def test_eight_transition_closeout_statuses_present_with_disclaimers() -> None:
    pkt = build_pkt()
    rows = pkt["transition_closeout_statuses"]
    assert len(rows) == 8
    statuses = [r["status"] for r in rows]
    for expected in EXPECTED_TRANSITION_CLOSEOUT_STATUSES:
        assert expected in statuses
    disclaimer_phrases = (
        "not pilot launch",
        "not customer onboarding",
        "not production activation",
    )
    for r in rows:
        d = (r.get("definition") or "").lower()
        for needle in disclaimer_phrases:
            assert needle in d


def test_universal_disclaimer_present() -> None:
    pkt = build_pkt()
    u = (pkt.get("transition_closeout_status_universal_disclaimer") or "").lower()
    assert "not pilot launch" in u
    assert "not customer onboarding" in u
    assert "not production activation" in u


def test_each_field_group_has_at_least_two_acceptance_criteria() -> None:
    pkt = build_pkt()
    for g in pkt["transition_closeout_field_groups"]:
        crit = g["acceptance_criteria"]
        assert isinstance(crit, list)
        assert len(crit) >= 2


def test_at_least_eight_risks_documented() -> None:
    pkt = build_pkt()
    assert len(pkt["risks_and_mitigations"]) >= 8


def test_markdown_required_section_headers() -> None:
    md = render_md()
    assert md.startswith("# NativeForge M1 Pilot Demo-to-Build Transition Closeout Packet v1\n")
    for h in REQUIRED_SECTION_HEADERS:
        assert h in md


def test_markdown_preview_only_transition_closeout_rules() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 4. preview-only transition closeout rules" in lower
    assert "demo-safe" in lower or "demo safe" in lower
    assert "no real customer data" in lower
    assert "no external calls" in lower


def test_markdown_m1_readiness_evidence_by_product_area() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 8. m1 readiness evidence by product area" in lower
    assert "source ingestion readiness" in lower
    assert "nofo extraction readiness" in lower


def test_markdown_blocker_and_approval_gate_rules() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 9. blocker and approval gate rules" in lower
    assert "owner" in lower
    assert "human approval" in lower


def test_markdown_demo_to_build_transition_rules() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 10. demo-to-build transition rules" in lower
    assert "source sprint" in lower
    assert "roadmap" in lower


def test_markdown_sovereignty_and_trust_requirements() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 11. sovereignty and trust requirements" in lower
    assert "customer owns its data" in lower
    assert "no model training on customer data without explicit written consent" in lower


def test_markdown_explicit_does_not_build_phrases() -> None:
    md = render_md()
    lower = md.lower()
    assert "no pilot launch" in lower
    assert "no customer onboarding" in lower
    assert "no production activation" in lower
    assert "no customer record creation" in lower
    assert "no customer data access" in lower
    assert "no database migration" in lower


def test_markdown_recommends_sprint141_controlled_build_authorization_review_packet() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 141" in lower
    assert "m1 controlled build authorization review packet" in lower


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
