"""Sprint 123: M0 pursuit pipeline kanban and deadline tracking planning packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT123_MOD = (
    "nativeforge.services."
    "active_source_activation_m0_pursuit_pipeline_kanban_deadline_tracking_planning_packet_service"
)
sprint123_pkt = importlib.import_module(_SPRINT123_MOD)
M0_PIPELINE_PREVIEW_FOUNDATIONS = sprint123_pkt.M0_PIPELINE_PREVIEW_FOUNDATIONS
build_pkt = sprint123_pkt.build_active_source_activation_m0_pursuit_pipeline_kanban_deadline_tracking_planning_packet
render_md = (
    sprint123_pkt.render_active_source_activation_m0_pursuit_pipeline_kanban_deadline_tracking_planning_packet_markdown
)

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m0_pursuit_pipeline_kanban_deadline_tracking_planning_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After Recommendation Planning",
    "## 3. M0 Pipeline Preview Objective",
    "## 4. Demo-Safe Pipeline Rules",
    "## 5. Required Pipeline Field Groups",
    "## 6. Pipeline Status Definitions",
    "## 7. Field-Level Acceptance Criteria",
    "## 8. Pipeline Preview to M0 Feature Mapping",
    "## 9. Deadline Tracking Guardrails",
    "## 10. Human Review Gates",
    "## 11. Sovereignty and Trust Requirements",
    "## 12. What Sprint 123 Does Not Build",
    "## 13. M0 Exit Criteria for Pipeline Planning",
    "## 14. Risks and Mitigations",
    "## 15. Sprint 124 Recommended Next Step",
)

EXPECTED_FIELD_GROUP_NAMES = (
    "Pursuit card identity",
    "Opportunity reference",
    "Entity profile reference",
    "Recommendation reference",
    "Pipeline status",
    "Priority level",
    "Deadline date",
    "Deadline timezone",
    "Days remaining",
    "Owner assignment",
    "Reviewer assignment",
    "Required action checklist",
    "Form readiness status",
    "Attachment readiness status",
    "Eligibility review status",
    "Source provenance status",
    "Human override reason",
    "Audit and export readiness",
)

EXPECTED_PIPELINE_STATUSES = (
    "Review Needed",
    "Pursue Preview",
    "Preparing Materials",
    "Waiting on Resolution",
    "Ready for Final Review",
    "Submitted Outside System",
    "Paused",
    "Do Not Pursue",
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
    assert pkt["sprint_number"] == 123
    assert (
        pkt["packet_name"]
        == "NativeForge M0 Pursuit Pipeline Kanban and Deadline Tracking Planning Packet"
    )
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True
    assert pkt["may_define_pipeline_preview_scope"] is True
    assert pkt["may_define_demo_safe_pipeline_states"] is True
    assert pkt["may_define_deadline_tracking_fields"] is True
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
    assert pkt["actual_pipeline_creations"] == 0
    assert pkt["actual_calendar_writes"] == 0
    assert pkt["actual_task_assignments"] == 0


def test_m0_foundations_match_required_ten() -> None:
    pkt = build_pkt()
    assert pkt["m0_pipeline_preview_foundations"] == list(M0_PIPELINE_PREVIEW_FOUNDATIONS)
    assert len(M0_PIPELINE_PREVIEW_FOUNDATIONS) == 10


def test_eighteen_pipeline_field_groups_present() -> None:
    pkt = build_pkt()
    groups = pkt["pipeline_field_groups"]
    assert len(groups) == 18
    names = [g["name"] for g in groups]
    for expected in EXPECTED_FIELD_GROUP_NAMES:
        assert expected in names


def test_each_field_group_has_at_least_two_acceptance_criteria() -> None:
    pkt = build_pkt()
    for g in pkt["pipeline_field_groups"]:
        crit = g["acceptance_criteria"]
        assert isinstance(crit, list)
        assert len(crit) >= 2


def test_eight_pipeline_statuses_present() -> None:
    pkt = build_pkt()
    rows = pkt["pipeline_statuses"]
    assert len(rows) == 8
    names = [r["status_name"] for r in rows]
    for expected in EXPECTED_PIPELINE_STATUSES:
        assert expected in names


def test_each_pipeline_status_includes_m0_disclaimers() -> None:
    pkt = build_pkt()
    needle = "M0 does not submit applications"
    for row in pkt["pipeline_statuses"]:
        desc = row["status_description"]
        assert isinstance(desc, str)
        assert needle in desc
        assert "does not automate outreach" in desc
        assert "does not create production tasks" in desc


def test_at_least_eight_risks_documented() -> None:
    pkt = build_pkt()
    assert len(pkt["risks_and_mitigations"]) >= 8


def test_markdown_required_section_headers() -> None:
    md = render_md()
    assert md.startswith(
        "# NativeForge M0 Pursuit Pipeline Kanban and Deadline Tracking Planning Packet v1\n"
    )
    for h in REQUIRED_SECTION_HEADERS:
        assert h in md


def test_markdown_demo_safe_pipeline_restrictions() -> None:
    md = render_md()
    lower = md.lower()
    assert "demo-safe pipeline" in lower or "demo-safe pursuit" in lower
    assert "no real customer data" in lower
    assert "no production task creation" in lower


def test_markdown_deadline_tracking_guardrails() -> None:
    md = render_md()
    lower = md.lower()
    assert "timezone" in lower
    assert "missing deadline" in lower or "blocks pursuit-ready" in lower
    assert "no calendar writes" in lower


def test_markdown_human_review_gate_language() -> None:
    md = render_md()
    lower = md.lower()
    assert "pursuit pipeline preview card cannot be treated as a production task" in lower
    assert "do-not-pursue status cannot block" in lower


def test_markdown_sovereignty_and_trust_requirements() -> None:
    md = render_md()
    lower = md.lower()
    assert "no customer data required for seeded pipeline demos" in lower
    assert "no customer data leaves the product during seeded demos" in lower
    assert "no model training on customer data without explicit written" in lower


def test_markdown_sprint123_does_not_build_phrases() -> None:
    md = render_md()
    lower = md.lower()
    assert "no database migration" in lower
    assert "no frontend ui" in lower
    assert "no api route" in lower
    assert "no calendar write" in lower
    assert "no production task creation" in lower


def test_markdown_sprint124_sf424_autofill_planning_packet() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 124" in lower
    assert "m0 sf-424 autofill preview planning packet" in lower


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
