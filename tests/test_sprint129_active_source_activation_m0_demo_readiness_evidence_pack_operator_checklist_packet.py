"""Sprint 129: M0 demo readiness evidence pack and operator checklist packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT129_MOD = (
    "nativeforge.services.active_source_activation_m0_demo_readiness_evidence_pack_operator_checklist_packet_service"
)
sprint129_pkt = importlib.import_module(_SPRINT129_MOD)
build_pkt = sprint129_pkt.build_active_source_activation_m0_demo_readiness_evidence_pack_operator_checklist_packet
render_md = sprint129_pkt.render_active_source_activation_m0_demo_readiness_evidence_pack_operator_checklist_packet_markdown

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m0_demo_readiness_evidence_pack_operator_checklist_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After Demo Narrative Planning",
    "## 3. M0 Demo Readiness Objective",
    "## 4. Demo-Safe Readiness Rules",
    "## 5. Required Evidence Field Groups",
    "## 6. Operator Checklist Status Definitions",
    "## 7. Field-Level Acceptance Criteria",
    "## 8. Evidence Pack by M0 Feature",
    "## 9. Operator Go/No-Go Checklist",
    "## 10. Buyer Question and Follow-Up Capture",
    "## 11. Sovereignty and Trust Requirements",
    "## 12. What Sprint 129 Does Not Build",
    "## 13. M0 Exit Criteria for Demo Readiness Planning",
    "## 14. Risks and Mitigations",
    "## 15. Sprint 130 Recommended Next Step",
)

EXPECTED_FIELD_GROUP_NAMES = (
    "Evidence item identity",
    "Evidence item source sprint",
    "M0 feature covered",
    "Buyer proof point",
    "Demo-safe data confirmation",
    "Human review status",
    "Source provenance status",
    "Sovereignty/trust status",
    "Caveat visibility status",
    "Missing data status",
    "Risk note",
    "Operator action required",
    "Go/no-go status",
    "Closeout note",
    "Artifact path or reference",
    "Non-production disclaimer",
    "Buyer question linkage",
    "Next sprint recommendation",
)

EXPECTED_CHECKLIST_STATUSES = (
    "Not checked",
    "Ready for demo",
    "Needs operator review",
    "Needs seeded data correction",
    "Blocked by missing evidence",
    "Blocked by unclear caveat",
    "Excluded from buyer walkthrough",
    "Deferred to later sprint",
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
    assert pkt["sprint_number"] == 129
    assert pkt["packet_name"] == "NativeForge M0 Demo Readiness Evidence Pack and Operator Checklist Packet"
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True
    assert pkt["may_define_demo_readiness_scope"] is True
    assert pkt["may_define_evidence_pack_items"] is True
    assert pkt["may_define_operator_checklist"] is True
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
    assert pkt["actual_demo_runs"] == 0
    assert pkt["actual_evidence_files_created"] == 0
    assert pkt["actual_buyer_sessions_created"] == 0


def test_ten_demo_readiness_foundation_areas() -> None:
    pkt = build_pkt()
    areas = pkt["demo_readiness_foundation_areas"]
    assert len(areas) == 10
    titles = {a["foundation_area"] for a in areas}
    assert "Demo artifact inventory" in titles
    assert "Operator go/no-go readiness" in titles


def test_eighteen_evidence_field_groups_present() -> None:
    pkt = build_pkt()
    groups = pkt["evidence_field_groups"]
    assert len(groups) == 18
    names = [g["name"] for g in groups]
    for expected in EXPECTED_FIELD_GROUP_NAMES:
        assert expected in names


def test_eight_checklist_statuses_present_with_disclaimers() -> None:
    pkt = build_pkt()
    rows = pkt["operator_checklist_statuses"]
    assert len(rows) == 8
    statuses = [r["status"] for r in rows]
    for expected in EXPECTED_CHECKLIST_STATUSES:
        assert expected in statuses
    disclaimer_phrases = (
        "not production readiness",
        "not legal approval",
        "not submission authorization",
    )
    for r in rows:
        d = (r.get("definition") or "").lower()
        for needle in disclaimer_phrases:
            assert needle in d


def test_universal_disclaimer_present() -> None:
    pkt = build_pkt()
    u = (pkt.get("checklist_status_universal_disclaimer") or "").lower()
    assert "not production readiness" in u
    assert "not legal approval" in u
    assert "not submission authorization" in u


def test_each_field_group_has_at_least_two_acceptance_criteria() -> None:
    pkt = build_pkt()
    for g in pkt["evidence_field_groups"]:
        crit = g["acceptance_criteria"]
        assert isinstance(crit, list)
        assert len(crit) >= 2


def test_at_least_eight_risks_documented() -> None:
    pkt = build_pkt()
    assert len(pkt["risks_and_mitigations"]) >= 8


def test_markdown_required_section_headers() -> None:
    md = render_md()
    assert md.startswith(
        "# NativeForge M0 Demo Readiness Evidence Pack and Operator Checklist Packet v1\n"
    )
    for h in REQUIRED_SECTION_HEADERS:
        assert h in md


def test_markdown_demo_safe_readiness_rules() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 4. demo-safe readiness rules" in lower
    assert "demo-safe" in lower
    assert "no real customer data" in lower
    assert "no external calls" in lower


def test_markdown_evidence_pack_by_m0_feature() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 8. evidence pack by m0 feature" in lower
    assert "organizational entity profile" in lower
    assert "demo narrative and buyer walkthrough" in lower


def test_markdown_operator_go_no_go_checklist() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 9. operator go/no-go checklist" in lower
    assert "all demo-visible artifacts exist" in lower
    assert "no submission pathway is implied" in lower


def test_markdown_buyer_question_and_follow_up_capture() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 10. buyer question and follow-up capture" in lower
    assert "operators capture buyer questions" in lower


def test_markdown_sovereignty_and_trust_requirements() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 11. sovereignty and trust requirements" in lower
    assert "customer owns its data" in lower
    assert "no model training on customer data without explicit written consent" in lower


def test_markdown_explicit_scope_phrases() -> None:
    md = render_md()
    lower = md.lower()
    assert "no real demo execution" in lower
    assert "no evidence file creation" in lower
    assert "no buyer session creation" in lower
    assert "no customer data access" in lower
    assert "no database migration" in lower


def test_markdown_recommends_sprint130_m1_packet() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 130" in lower
    assert "m0 pilot transition" in lower
    assert "m1 readiness planning packet" in lower


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
