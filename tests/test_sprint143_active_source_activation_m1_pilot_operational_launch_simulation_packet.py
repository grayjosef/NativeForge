"""Sprint 143: M1 pilot operational launch simulation packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT143_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_pilot_operational_launch_simulation_packet_service"
)
sprint143_pkt = importlib.import_module(_SPRINT143_MOD)
build_pkt = sprint143_pkt.build_active_source_activation_m1_pilot_operational_launch_simulation_packet
render_md = (
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

_SPRINT141_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_controlled_build_authorization_review_packet_service"
)
sprint141_pkt = importlib.import_module(_SPRINT141_MOD)
build_sprint141 = sprint141_pkt.build_active_source_activation_m1_controlled_build_authorization_review_packet
render_sprint141_md = (
    sprint141_pkt.render_active_source_activation_m1_controlled_build_authorization_review_packet_markdown
)

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m1_pilot_operational_launch_simulation_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After Sprint 142",
    "## 3. Operational Launch Simulation Objective",
    "## 4. Simulation Evidence Inputs",
    "## 5. Simulated Launch Sequence",
    "## 6. Operator Handoff and Role Readiness",
    "## 7. Support, Escalation, and Rollback Rehearsal",
    "## 8. Monitoring and Evidence Capture Expectations",
    "## 9. Human Decision Record Requirements",
    "## 10. Sovereignty, Trust, and Data Handling Constraints",
    "## 11. What Sprint 143 Does Not Build",
    "## 12. Exit Criteria",
    "## 13. Risks and Mitigations",
    "## 14. Sprint 144 Recommended Next Step",
)

EXPECTED_SIMULATION_STEPS = (
    "Evidence package review",
    "Environment boundary review",
    "Human gate confirmation",
    "Deferred item review",
    "Support owner confirmation",
    "Rollback rehearsal",
    "Monitoring checkpoint rehearsal",
    "Final simulated decision record",
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


def test_packet_sprint_and_flags() -> None:
    pkt = build_pkt()
    assert pkt["sprint_number"] == 143
    assert pkt["artifact_type"] == (
        "nf_active_source_activation_m1_pilot_operational_launch_simulation_packet_v1"
    )
    assert pkt["packet_name"] == "NativeForge M1 Pilot Operational Launch Simulation Packet"
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True
    assert pkt["may_define_operational_launch_simulation_readiness"] is True
    assert pkt["may_rehearse_launch_path_without_authorization"] is True


def test_prerequisite_sprint142_pre_launch_checklist_packet() -> None:
    pkt = build_pkt()
    assert pkt["prerequisite_pre_launch_checklist_sprint"] == 142
    assert (
        pkt["prerequisite_pre_launch_checklist_artifact_type"]
        == "nf_active_source_activation_m1_pilot_implementation_pre_launch_checklist_packet_v1"
    )


def test_verification_path_includes_sprint141_artifact_type() -> None:
    pkt = build_pkt()
    assert (
        pkt["verification_path_authorization_review_artifact_type"]
        == "nf_active_source_activation_m1_controlled_build_authorization_review_packet_v1"
    )


def test_packet_actual_counts_zero() -> None:
    pkt = build_pkt()
    for key, value in pkt.items():
        if key.startswith("actual_"):
            assert value == 0, key


def test_eight_simulated_launch_sequence_steps() -> None:
    pkt = build_pkt()
    rows = pkt["simulated_launch_sequence"]
    assert len(rows) == 8
    names = [r["step"] for r in rows]
    for expected in EXPECTED_SIMULATION_STEPS:
        assert expected in names


def test_simulation_step_disclaimers_reject_launch_onboarding_activation() -> None:
    pkt = build_pkt()
    disclaimer_phrases = (
        "not pilot launch",
        "not customer onboarding",
        "not source activation",
        "not production activation",
    )
    u = (pkt.get("simulated_launch_step_universal_disclaimer") or "").lower()
    for needle in disclaimer_phrases:
        assert needle in u
    for r in pkt["simulated_launch_sequence"]:
        d = (r.get("rehearsal_focus") or "").lower()
        for needle in disclaimer_phrases:
            assert needle in d


def test_five_simulation_evidence_inputs_reference_sprint142_and_141() -> None:
    pkt = build_pkt()
    ev = pkt["simulation_evidence_inputs"]
    assert len(ev) == 5
    text = json.dumps(ev).lower()
    assert "sprint 142" in text
    assert "sprint 141" in text
    assert "nf_active_source_activation_m1_pilot_implementation_pre_launch_checklist_packet_v1" in text
    assert "nf_active_source_activation_m1_controlled_build_authorization_review_packet_v1" in text


def test_human_decision_record_requirements_explicit() -> None:
    pkt = build_pkt()
    joined = " ".join(pkt["human_decision_record_requirements"]).lower()
    assert "human operator" in joined
    assert "simulated" in joined
    assert "no-go" in joined or "no go" in joined
    assert "go" in joined


def test_sprint143_does_not_build_required_phrases() -> None:
    pkt = build_pkt()
    items = [x.lower() for x in pkt["sprint_143_does_not_build"]]
    assert "no pilot launch" in items
    assert "no customer onboarding" in items
    assert "no customer data access" in items
    assert "no database migration" in items
    assert "no source activation" in items
    assert "no production activation" in items
    assert "no runnable launch plan" in items


def test_markdown_what_sprint143_does_not_build_lists_required_exclusions() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 11. what sprint 143 does not build" in lower
    for phrase in (
        "no pilot launch",
        "no customer onboarding",
        "no customer data access",
        "no database migration",
        "no source activation",
        "no production activation",
        "no runnable launch plan",
    ):
        assert phrase in lower


def test_sprint144_recommendation_only() -> None:
    pkt = build_pkt()
    step = (pkt.get("sprint_144_recommended_next_step") or "").lower()
    assert "recommendation-only" in step or "recommendation only" in step
    assert "sprint 144" in step


def test_markdown_required_section_headers_in_order() -> None:
    md = render_md()
    assert md.startswith("# NativeForge M1 Pilot Operational Launch Simulation Packet v1\n")
    positions = [md.index(h) for h in REQUIRED_SECTION_HEADERS]
    assert positions == sorted(positions)


def test_markdown_prerequisite_sprint142_and_sequencing() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 142" in lower
    assert "pre-launch checklist" in lower or "pre launch checklist" in lower
    assert "sprint 143" in lower


def test_markdown_sovereignty_trust_constraints_section() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 10. sovereignty, trust, and data handling constraints" in lower
    assert "customer owns its data" in lower


def test_markdown_explicit_human_decision_record_language() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 9. human decision record requirements" in lower
    assert "human operator" in lower
    assert "simulation-only" in lower or "simulation only" in lower


def test_markdown_sprint144_next_step_header() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 14. sprint 144 recommended next step" in lower


def test_markdown_simulated_sequence_contains_required_steps() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 5. simulated launch sequence" in lower
    for label in (
        "evidence package review",
        "environment boundary review",
        "human gate confirmation",
        "deferred item review",
        "support owner confirmation",
        "rollback rehearsal",
        "monitoring checkpoint rehearsal",
        "final simulated decision record",
    ):
        assert label in lower


def test_markdown_regression_sprint142_sprint141_verification_path() -> None:
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


def test_regression_sprint141_packet_still_valid() -> None:
    p141 = build_sprint141()
    assert p141["sprint_number"] == 141
    assert p141["preview_only"] is True
    assert p141["no_execution"] is True
    assert p141["no_activation"] is True
    assert p141["no_runnable_plan"] is True
    for key, value in p141.items():
        if key.startswith("actual_"):
            assert value == 0, key
    md141 = render_sprint141_md()
    assert "## 1. purpose" in md141.lower()
    assert "sprint 142" in md141.lower()
