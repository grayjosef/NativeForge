"""Sprint 144: M1 pilot metrics & closeout reporting packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT144_MOD = (
    "nativeforge.services.active_source_activation_m1_pilot_metrics_closeout_reporting_packet_service"
)
sprint144_pkt = importlib.import_module(_SPRINT144_MOD)
build_pkt = sprint144_pkt.build_active_source_activation_m1_pilot_metrics_closeout_reporting_packet
render_md = sprint144_pkt.render_active_source_activation_m1_pilot_metrics_closeout_reporting_packet_markdown

_SPRINT143_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_pilot_operational_launch_simulation_packet_service"
)
sprint143_pkt = importlib.import_module(_SPRINT143_MOD)
build_sprint143 = sprint143_pkt.build_active_source_activation_m1_pilot_operational_launch_simulation_packet
render_sprint143_md = (
    sprint143_pkt.render_active_source_activation_m1_pilot_operational_launch_simulation_packet_markdown
)

_SPRINT142_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_pilot_implementation_pre_launch_checklist_packet_service"
)
sprint142_pkt = importlib.import_module(_SPRINT142_MOD)
build_sprint142 = sprint142_pkt.build_active_source_activation_m1_pilot_implementation_pre_launch_checklist_packet
render_sprint142_md = (
    sprint142_pkt.render_active_source_activation_m1_pilot_implementation_pre_launch_checklist_packet_markdown
)

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m1_pilot_metrics_closeout_reporting_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After Sprint 143",
    "## 3. Metrics and Closeout Objective",
    "## 4. Required Evidence Inputs",
    "## 5. Pilot Metrics Framework",
    "## 6. Closeout Reporting Structure",
    "## 7. Evidence Capture Requirements",
    "## 8. Human Review and Approval Requirements",
    "## 9. Deferred Item and Exception Handling",
    "## 10. Sovereignty, Trust, and Data Handling Constraints",
    "## 11. What Sprint 144 Does Not Build",
    "## 12. Exit Criteria",
    "## 13. Risks and Mitigations",
    "## 14. Sprint 145 Recommended Next Step",
)

EXPECTED_METRIC_DOMAINS = (
    "Readiness evidence completeness",
    "Human gate completion",
    "Deferred item resolution status",
    "Sovereignty and trust compliance readiness",
    "Operator handoff readiness",
    "Support and escalation readiness",
    "Rollback rehearsal readiness",
    "Monitoring rehearsal readiness",
    "Documentation closeout readiness",
    "Recommendation confidence for next phase",
)

EXPECTED_CLOSEOUT_SECTIONS = (
    "Executive summary",
    "Evidence reviewed",
    "Gates passed",
    "Gates blocked",
    "Deferred items",
    "Risk findings",
    "Sovereignty and trust findings",
    "Operator recommendation",
    "Required human approvals before any future runtime step",
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


def test_no_external_network_in_service_source() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert "socket." not in src
    assert "requests." not in src
    assert "httpx." not in src
    assert "urllib.request" not in src
    for tok in ("import requests", "import httpx", "import openai", "import anthropic"):
        assert tok not in src


def test_service_source_has_no_migration_or_onboarding_execution_hooks() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8").lower()
    assert "alembic" not in src
    assert "op.create_table" not in src
    assert "subprocess.run" not in src
    assert "psycopg" not in src


def test_service_source_rejects_runtime_launch_activation_collection() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8").lower()
    for phrase in (
        "no pilot launch",
        "no runtime execution",
        "no source activation",
        "no production activation",
        "no real metric collection",
        "no runnable closeout workflow",
        "no customer onboarding",
    ):
        assert phrase in src


def test_packet_sprint_and_flags() -> None:
    pkt = build_pkt()
    assert pkt["sprint_number"] == 144
    assert pkt["artifact_type"] == (
        "nf_active_source_activation_m1_pilot_metrics_closeout_reporting_packet_v1"
    )
    assert pkt["packet_name"] == "NativeForge M1 Pilot Metrics & Closeout Reporting Packet"
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True
    assert pkt["may_define_pilot_metrics_framework_preview_only"] is True
    assert pkt["may_define_closeout_reporting_structure_preview_only"] is True


def test_prerequisite_sprint143_operational_launch_simulation_packet() -> None:
    pkt = build_pkt()
    assert pkt["prerequisite_operational_launch_simulation_sprint"] == 143
    assert (
        pkt["prerequisite_operational_launch_simulation_artifact_type"]
        == "nf_active_source_activation_m1_pilot_operational_launch_simulation_packet_v1"
    )


def test_verification_path_includes_sprint142_and_sprint141_artifact_types() -> None:
    pkt = build_pkt()
    assert (
        pkt["verification_path_pre_launch_checklist_artifact_type"]
        == "nf_active_source_activation_m1_pilot_implementation_pre_launch_checklist_packet_v1"
    )
    assert (
        pkt["verification_path_authorization_review_artifact_type"]
        == "nf_active_source_activation_m1_controlled_build_authorization_review_packet_v1"
    )


def test_packet_actual_counts_zero() -> None:
    pkt = build_pkt()
    for key, value in pkt.items():
        if key.startswith("actual_"):
            assert value == 0, key


def test_ten_pilot_metrics_framework_domains() -> None:
    pkt = build_pkt()
    rows = pkt["pilot_metrics_framework"]
    assert len(rows) == 10
    names = [r["metric_domain"] for r in rows]
    for expected in EXPECTED_METRIC_DOMAINS:
        assert expected in names


def test_metric_domain_disclaimers_reject_launch_onboarding_activation() -> None:
    pkt = build_pkt()
    disclaimer_phrases = (
        "not pilot launch",
        "not customer onboarding",
        "not source activation",
        "not production activation",
    )
    u = (pkt.get("pilot_metrics_domain_universal_disclaimer") or "").lower()
    for needle in disclaimer_phrases:
        assert needle in u
    for r in pkt["pilot_metrics_framework"]:
        d = (r.get("planning_focus") or "").lower()
        for needle in disclaimer_phrases:
            assert needle in d


def test_nine_closeout_reporting_sections() -> None:
    pkt = build_pkt()
    rows = pkt["closeout_reporting_structure"]
    assert len(rows) == 9
    names = [r["section"] for r in rows]
    for expected in EXPECTED_CLOSEOUT_SECTIONS:
        assert expected in names


def test_five_required_evidence_inputs_reference_sprint143_and_142() -> None:
    pkt = build_pkt()
    ev = pkt["required_evidence_inputs"]
    assert len(ev) == 5
    text = json.dumps(ev).lower()
    assert "sprint 143" in text
    assert "sprint 142" in text
    assert "nf_active_source_activation_m1_pilot_operational_launch_simulation_packet_v1" in text
    assert "nf_active_source_activation_m1_pilot_implementation_pre_launch_checklist_packet_v1" in text


def test_human_review_and_approval_requirements_explicit() -> None:
    pkt = build_pkt()
    joined = " ".join(pkt["human_review_and_approval_requirements"]).lower()
    assert "human operator approval" in joined
    assert "human-authored" in joined or "human authored" in joined


def test_sprint144_does_not_build_required_phrases() -> None:
    pkt = build_pkt()
    items = [x.lower() for x in pkt["sprint_144_does_not_build"]]
    assert "no pilot launch" in items
    assert "no customer onboarding" in items
    assert "no customer data access" in items
    assert "no database migration" in items
    assert "no source activation" in items
    assert "no production activation" in items
    assert "no real metric collection" in items
    assert "no runnable closeout workflow" in items


def test_markdown_what_sprint144_does_not_build_lists_required_exclusions() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 11. what sprint 144 does not build" in lower
    for phrase in (
        "no pilot launch",
        "no customer onboarding",
        "no customer data access",
        "no database migration",
        "no source activation",
        "no production activation",
        "no real metric collection",
        "no runnable closeout workflow",
    ):
        assert phrase in lower


def test_sprint145_recommendation_only() -> None:
    pkt = build_pkt()
    step = (pkt.get("sprint_145_recommended_next_step") or "").lower()
    assert "recommendation-only" in step or "recommendation only" in step
    assert "sprint 145" in step


def test_markdown_required_section_headers_in_order() -> None:
    md = render_md()
    assert md.startswith("# NativeForge M1 Pilot Metrics & Closeout Reporting Packet v1\n")
    positions = [md.index(h) for h in REQUIRED_SECTION_HEADERS]
    assert positions == sorted(positions)


def test_markdown_prerequisite_sprint143_and_sequencing() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 143" in lower
    assert "operational launch simulation" in lower
    assert "sprint 144" in lower


def test_markdown_sovereignty_trust_constraints_section() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 10. sovereignty, trust, and data handling constraints" in lower
    assert "customer owns its data" in lower


def test_markdown_explicit_human_approval_language() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 8. human review and approval requirements" in lower
    assert "human operator approval" in lower


def test_markdown_sprint145_next_step_header() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 14. sprint 145 recommended next step" in lower


def test_markdown_pilot_metrics_framework_contains_required_domains() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 5. pilot metrics framework" in lower
    for label in (
        "readiness evidence completeness",
        "human gate completion",
        "deferred item resolution status",
        "sovereignty and trust compliance readiness",
        "operator handoff readiness",
        "support and escalation readiness",
        "rollback rehearsal readiness",
        "monitoring rehearsal readiness",
        "documentation closeout readiness",
        "recommendation confidence for next phase",
    ):
        assert label in lower


def test_markdown_closeout_reporting_structure_contains_required_sections() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 6. closeout reporting structure" in lower
    assert "executive summary" in lower
    assert "evidence reviewed" in lower
    assert "gates passed" in lower
    assert "gates blocked" in lower
    assert "deferred items" in lower
    assert "risk findings" in lower
    assert "sovereignty and trust findings" in lower
    assert "operator recommendation" in lower
    assert "required human approvals before any future runtime step" in lower


def test_markdown_regression_sprint143_sprint142_verification_path() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 141" in lower
    assert "sprint 140" in lower
    assert "demo-to-build" in lower or "demo to build" in lower
    assert "131" in lower and "139" in lower


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


def test_regression_sprint143_packet_still_valid() -> None:
    p143 = build_sprint143()
    assert p143["sprint_number"] == 143
    assert p143["preview_only"] is True
    assert p143["no_execution"] is True
    assert p143["no_activation"] is True
    assert p143["no_runnable_plan"] is True
    for key, value in p143.items():
        if key.startswith("actual_"):
            assert value == 0, key
    md143 = render_sprint143_md()
    assert "## 1. purpose" in md143.lower()
    assert "sprint 142" in md143.lower()


def test_regression_sprint142_packet_still_valid() -> None:
    p142 = build_sprint142()
    assert p142["sprint_number"] == 142
    assert p142["preview_only"] is True
    assert p142["no_execution"] is True
    assert p142["no_activation"] is True
    assert p142["no_runnable_plan"] is True
    for key, value in p142.items():
        if key.startswith("actual_"):
            assert value == 0, key
    md142 = render_sprint142_md()
    assert "## 1. purpose" in md142.lower()
    assert "sprint 141" in md142.lower()
