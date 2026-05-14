"""Sprint 136: M1 form package controlled build readiness packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT136_MOD = (
    "nativeforge.services.active_source_activation_m1_form_package_controlled_build_readiness_packet_service"
)
sprint136_pkt = importlib.import_module(_SPRINT136_MOD)
build_pkt = sprint136_pkt.build_active_source_activation_m1_form_package_controlled_build_readiness_packet
render_md = sprint136_pkt.render_active_source_activation_m1_form_package_controlled_build_readiness_packet_markdown

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m1_form_package_controlled_build_readiness_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After NOFO Extraction Readiness",
    "## 3. M1 Form Package Readiness Objective",
    "## 4. Preview-Only Form Readiness Rules",
    "## 5. Required Form Readiness Field Groups",
    "## 6. Form Readiness Status Definitions",
    "## 7. Field-Level Acceptance Criteria",
    "## 8. Form Readiness by Form Package Area",
    "## 9. Autofill Prerequisite Rules",
    "## 10. Human Gate and Review Rules",
    "## 11. Sovereignty and Trust Requirements",
    "## 12. What Sprint 136 Does Not Build",
    "## 13. M1 Form Package Readiness Exit Criteria",
    "## 14. Risks and Mitigations",
    "## 15. Sprint 137 Recommended Next Step",
)

EXPECTED_FIELD_GROUP_NAMES = (
    "Form readiness item identity",
    "Form package reference",
    "Form type",
    "Form field group",
    "Profile source field",
    "Autofill mapping expectation",
    "Provenance requirement",
    "Confidence threshold",
    "Missing data rule",
    "Human review prerequisite",
    "Field override rule",
    "Attachment dependency",
    "Signature or authorization dependency",
    "Submission-adjacent blocker status",
    "Acceptance criteria",
    "Risk note",
    "Non-production disclaimer",
    "Next sprint recommendation",
)

EXPECTED_FORM_READINESS_STATUSES = (
    "Not assessed",
    "Ready for controlled build planning",
    "Needs form verification",
    "Needs profile mapping review",
    "Needs confidence rule review",
    "Needs human review gate",
    "Blocked before autofill",
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
    assert pkt["sprint_number"] == 136
    assert pkt["packet_name"] == "NativeForge M1 Form Package Controlled Build Readiness Packet"
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True
    assert pkt["may_define_form_package_readiness"] is True
    assert pkt["may_define_autofill_prerequisites"] is True
    assert pkt["may_define_human_gate_requirements"] is True
    assert pkt["may_define_acceptance_criteria"] is True
    assert pkt["may_define_guardrails"] is True


def test_packet_actual_counts_zero() -> None:
    pkt = build_pkt()
    for key, value in pkt.items():
        if key.startswith("actual_"):
            assert value == 0, key
    assert pkt["actual_form_packages_created"] == 0
    assert pkt["actual_autofill_runs"] == 0
    assert pkt["actual_forms_processed"] == 0


def test_twelve_m1_form_package_readiness_foundations() -> None:
    pkt = build_pkt()
    rows = pkt["m1_form_package_controlled_build_readiness_foundations"]
    assert len(rows) == 12
    titles = {r["foundation_area"] for r in rows}
    assert "Form package scope readiness" in titles
    assert "Data sovereignty and security readiness" in titles


def test_ten_form_readiness_by_form_package_area() -> None:
    pkt = build_pkt()
    areas = pkt["form_readiness_by_form_package_area"]
    assert len(areas) == 10
    keys = {a["form_package_area"] for a in areas}
    assert "SF-424 application cover form" in keys
    assert "review and override controls" in keys


def test_eighteen_form_readiness_field_groups_present() -> None:
    pkt = build_pkt()
    groups = pkt["form_readiness_field_groups"]
    assert len(groups) == 18
    names = [g["name"] for g in groups]
    for expected in EXPECTED_FIELD_GROUP_NAMES:
        assert expected in names


def test_eight_form_readiness_statuses_present_with_disclaimers() -> None:
    pkt = build_pkt()
    rows = pkt["form_readiness_statuses"]
    assert len(rows) == 8
    statuses = [r["status"] for r in rows]
    for expected in EXPECTED_FORM_READINESS_STATUSES:
        assert expected in statuses
    disclaimer_phrases = (
        "not form processing",
        "not autofill execution",
        "not form submission",
    )
    for r in rows:
        d = (r.get("definition") or "").lower()
        for needle in disclaimer_phrases:
            assert needle in d


def test_universal_disclaimer_present() -> None:
    pkt = build_pkt()
    u = (pkt.get("form_readiness_status_universal_disclaimer") or "").lower()
    assert "not form processing" in u
    assert "not autofill execution" in u
    assert "not form submission" in u


def test_each_field_group_has_at_least_two_acceptance_criteria() -> None:
    pkt = build_pkt()
    for g in pkt["form_readiness_field_groups"]:
        crit = g["acceptance_criteria"]
        assert isinstance(crit, list)
        assert len(crit) >= 2


def test_at_least_eight_risks_documented() -> None:
    pkt = build_pkt()
    assert len(pkt["risks_and_mitigations"]) >= 8


def test_markdown_required_section_headers() -> None:
    md = render_md()
    assert md.startswith(
        "# NativeForge M1 Form Package Controlled Build Readiness Packet v1\n"
    )
    for h in REQUIRED_SECTION_HEADERS:
        assert h in md


def test_markdown_preview_only_form_readiness_rules() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 4. preview-only form readiness rules" in lower
    assert "demo-safe" in lower or "demo safe" in lower
    assert "no real customer data" in lower
    assert "no external calls" in lower


def test_markdown_form_readiness_by_form_package_area() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 8. form readiness by form package area" in lower
    assert "sf-424 application cover form" in lower
    assert "review and override controls" in lower


def test_markdown_autofill_prerequisite_rules() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 9. autofill prerequisite rules" in lower
    assert "profile source field" in lower
    assert "provenance" in lower


def test_markdown_human_gate_and_review_rules() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 10. human gate and review rules" in lower
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
    assert "no form package creation" in lower
    assert "no autofill execution" in lower
    assert "no form processing" in lower
    assert "no form submission" in lower
    assert "no customer data access" in lower
    assert "no database migration" in lower


def test_markdown_recommends_sprint137_human_review_workflow_packet() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 137" in lower
    assert "m1 human review workflow controlled build readiness packet" in lower


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
