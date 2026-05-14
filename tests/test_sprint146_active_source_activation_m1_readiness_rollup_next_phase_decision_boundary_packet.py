"""Sprint 146: M1 readiness rollup & next-phase decision boundary packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT146_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_readiness_rollup_next_phase_decision_boundary_packet_service"
)
sprint146_pkt = importlib.import_module(_SPRINT146_MOD)
build_pkt = (
    sprint146_pkt.build_active_source_activation_m1_readiness_rollup_next_phase_decision_boundary_packet
)
render_md = (
    sprint146_pkt.render_active_source_activation_m1_readiness_rollup_next_phase_decision_boundary_packet_markdown
)

_SPRINT145_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_lessons_learned_post_pilot_optimization_packet_service"
)
sprint145_pkt = importlib.import_module(_SPRINT145_MOD)
build_sprint145 = sprint145_pkt.build_active_source_activation_m1_lessons_learned_post_pilot_optimization_packet
render_sprint145_md = (
    sprint145_pkt.render_active_source_activation_m1_lessons_learned_post_pilot_optimization_packet_markdown
)

_SPRINT144_MOD = (
    "nativeforge.services.active_source_activation_m1_pilot_metrics_closeout_reporting_packet_service"
)
sprint144_pkt = importlib.import_module(_SPRINT144_MOD)
build_sprint144 = sprint144_pkt.build_active_source_activation_m1_pilot_metrics_closeout_reporting_packet
render_sprint144_md = (
    sprint144_pkt.render_active_source_activation_m1_pilot_metrics_closeout_reporting_packet_markdown
)

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m1_readiness_rollup_next_phase_decision_boundary_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After Sprint 145",
    "## 3. M1 Readiness Rollup Objective",
    "## 4. Prior Sprint Evidence Map",
    "## 5. Readiness Domains Covered",
    "## 6. Remaining UNKNOWNs and Deferred Decisions",
    "## 7. Human Approval Requirements",
    "## 8. Runtime Authorization Boundary",
    "## 9. Safe Next-Phase Decision Lanes",
    "## 10. Roadmap Preservation Notes",
    "## 11. Sovereignty, Trust, and Data Handling Constraints",
    "## 12. What Sprint 146 Does Not Build",
    "## 13. Exit Criteria",
    "## 14. Risks and Mitigations",
    "## 15. Recommended Next Safe Action",
)

EXPECTED_PRIOR_SPRINT_TITLES = (
    "M1 Pilot Scope & Delivery Boundary",
    "M1 Pilot Implementation Dependency Map",
    "M1 Controlled Build Sequencing & Human Gate",
    "M1 Source Ingestion Controlled Build Readiness",
    "M1 NOFO Extraction Controlled Build Readiness",
    "M1 Form Package Controlled Build Readiness",
    "M1 Human Review Workflow Controlled Build Readiness",
    "M1 Audit Export & Sovereignty Controlled Build Readiness",
    "M1 Pilot Operations & Support Controlled Build Readiness",
    "M1 Pilot Demo-to-Build Transition Closeout",
    "M1 Controlled Build Authorization Review",
    "M1 Pilot Implementation Pre-Launch Checklist",
    "M1 Pilot Operational Launch Simulation",
    "M1 Pilot Metrics & Closeout Reporting",
    "M1 Lessons Learned & Post-Pilot Optimization",
)

EXPECTED_SAFE_LANES = (
    "Remain preview-only",
    "Open a documentation consolidation sprint",
    "Open a customer-validation planning sprint",
    "Open a technical architecture review sprint",
    "Open a bounded implementation design sprint",
    "Open a runtime authorization review sprint only after explicit human approval",
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


def test_service_source_rejects_runtime_launch_activation_collection_closeout_optimization() -> (
    None
):
    src = SERVICE_PATH.read_text(encoding="utf-8").lower()
    for phrase in (
        "no pilot launch",
        "no runtime execution",
        "no source activation",
        "no production activation",
        "no real metric collection",
        "no real pilot closeout",
        "no optimization execution",
        "no runnable implementation workflow",
        "no customer onboarding",
        "no runtime authorization",
    ):
        assert phrase in src


def test_packet_sprint_and_flags() -> None:
    pkt = build_pkt()
    assert pkt["sprint_number"] == 146
    assert pkt["artifact_type"] == (
        "nf_active_source_activation_m1_readiness_rollup_next_phase_decision_boundary_packet_v1"
    )
    assert pkt["packet_name"] == (
        "NativeForge M1 Readiness Rollup & Next-Phase Decision Boundary Packet"
    )
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True


def test_prerequisite_sprint145_lessons_learned_post_pilot_optimization_packet() -> None:
    pkt = build_pkt()
    assert pkt["prerequisite_lessons_learned_post_pilot_optimization_sprint"] == 145
    assert (
        pkt["prerequisite_lessons_learned_post_pilot_optimization_artifact_type"]
        == "nf_active_source_activation_m1_lessons_learned_post_pilot_optimization_packet_v1"
    )


def test_verification_path_includes_sprint144_metrics_closeout_artifact_type() -> None:
    pkt = build_pkt()
    assert pkt["verification_path_metrics_closeout_reporting_sprint"] == 144
    assert (
        pkt["verification_path_metrics_closeout_reporting_artifact_type"]
        == "nf_active_source_activation_m1_pilot_metrics_closeout_reporting_packet_v1"
    )


def test_packet_actual_counts_zero() -> None:
    pkt = build_pkt()
    for key, value in pkt.items():
        if key.startswith("actual_"):
            assert value == 0, key


def test_prior_sprint_evidence_map_covers_131_through_145() -> None:
    pkt = build_pkt()
    rows = pkt["prior_sprint_evidence_map"]
    assert len(rows) == 15
    numbers = [r["sprint_number"] for r in rows]
    assert numbers == list(range(131, 146))
    titles = [r["packet_title"] for r in rows]
    for expected in EXPECTED_PRIOR_SPRINT_TITLES:
        assert expected in titles


def test_human_approval_requirements_explicit() -> None:
    pkt = build_pkt()
    joined = " ".join(pkt["human_approval_requirements"]).lower()
    assert "human operator approval" in joined


def test_runtime_authorization_boundary_explicit() -> None:
    pkt = build_pkt()
    joined = " ".join(pkt["runtime_authorization_boundary"]).lower()
    assert "runtime authorization boundary" in joined
    assert "runtime authorization" in joined


def test_safe_next_phase_decision_lanes_recommendation_only() -> None:
    pkt = build_pkt()
    lanes = pkt["safe_next_phase_decision_lanes"]
    assert len(lanes) == 6
    names = [r["lane"] for r in lanes]
    for expected in EXPECTED_SAFE_LANES:
        assert expected in names
    assert all(r.get("recommendation_only") is True for r in lanes)


def test_sprint146_does_not_build_required_phrases() -> None:
    pkt = build_pkt()
    items = [x.lower() for x in pkt["sprint_146_does_not_build"]]
    assert "no pilot launch" in items
    assert "no customer onboarding" in items
    assert "no customer data access" in items
    assert "no database migration" in items
    assert "no source activation" in items
    assert "no production activation" in items
    assert "no real metric collection" in items
    assert "no real pilot closeout" in items
    assert "no optimization execution" in items
    assert "no runtime authorization" in items
    assert "no runnable implementation workflow" in items


def test_markdown_what_sprint146_does_not_build_lists_required_exclusions() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 12. what sprint 146 does not build" in lower
    for phrase in (
        "no pilot launch",
        "no customer onboarding",
        "no customer data access",
        "no database migration",
        "no source activation",
        "no production activation",
        "no real metric collection",
        "no real pilot closeout",
        "no optimization execution",
        "no runtime authorization",
        "no runnable implementation workflow",
    ):
        assert phrase in lower


def test_recommended_next_safe_action_recommendation_only() -> None:
    pkt = build_pkt()
    step = (pkt.get("recommended_next_safe_action") or "").lower()
    assert "recommendation-only" in step or "recommendation only" in step


def test_markdown_required_section_headers_in_order() -> None:
    md = render_md()
    assert md.startswith(
        "# NativeForge M1 Readiness Rollup & Next-Phase Decision Boundary Packet v1\n"
    )
    positions = [md.index(h) for h in REQUIRED_SECTION_HEADERS]
    assert positions == sorted(positions)


def test_markdown_prerequisite_sprint145_lessons_learned_and_post_pilot() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 145" in lower
    assert "lessons learned" in lower
    assert "post-pilot optimization" in lower or "post pilot optimization" in lower


def test_markdown_sovereignty_trust_constraints_section() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 11. sovereignty, trust, and data handling constraints" in lower
    assert "customer owns its data" in lower


def test_markdown_explicit_human_approval_language() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 7. human approval requirements" in lower
    assert "human operator approval" in lower


def test_markdown_runtime_authorization_boundary_section() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 8. runtime authorization boundary" in lower
    assert "runtime authorization boundary" in lower


def test_markdown_roadmap_preservation_notes_present() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 10. roadmap preservation notes" in lower
    assert "131" in lower and "145" in lower


def test_markdown_safe_lanes_recommendation_only_language() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 9. safe next-phase decision lanes" in lower
    assert "recommendation-only" in lower or "recommendation only" in lower
    for needle in (
        "remain preview-only",
        "documentation consolidation",
        "customer-validation planning",
        "technical architecture review",
        "bounded implementation design",
        "runtime authorization review sprint",
    ):
        assert needle in lower


def test_markdown_verification_path_regression_sprint145_sprint144() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 144" in lower
    assert "metrics" in lower and "closeout" in lower
    assert "sprint 145" in lower
    assert "lessons learned" in lower


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


def test_regression_sprint145_packet_still_valid() -> None:
    p145 = build_sprint145()
    assert p145["sprint_number"] == 145
    assert p145["preview_only"] is True
    assert p145["no_execution"] is True
    assert p145["no_activation"] is True
    assert p145["no_runnable_plan"] is True
    for key, value in p145.items():
        if key.startswith("actual_"):
            assert value == 0, key
    md145 = render_sprint145_md()
    assert "## 1. purpose" in md145.lower()
    assert "sprint 144" in md145.lower()


def test_regression_sprint144_packet_still_valid() -> None:
    p144 = build_sprint144()
    assert p144["sprint_number"] == 144
    assert p144["preview_only"] is True
    assert p144["no_execution"] is True
    assert p144["no_activation"] is True
    assert p144["no_runnable_plan"] is True
    for key, value in p144.items():
        if key.startswith("actual_"):
            assert value == 0, key
    md144 = render_sprint144_md()
    assert "## 1. purpose" in md144.lower()
    assert "sprint 143" in md144.lower()
