"""Sprint 147: M1 documentation consolidation & operator roadmap packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT147_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_documentation_consolidation_operator_roadmap_packet_service"
)
sprint147_pkt = importlib.import_module(_SPRINT147_MOD)
build_pkt = (
    sprint147_pkt.build_active_source_activation_m1_documentation_consolidation_operator_roadmap_packet
)
render_md = (
    sprint147_pkt.render_active_source_activation_m1_documentation_consolidation_operator_roadmap_packet_markdown
)

_SPRINT146_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_readiness_rollup_next_phase_decision_boundary_packet_service"
)
sprint146_pkt = importlib.import_module(_SPRINT146_MOD)
build_sprint146 = (
    sprint146_pkt.build_active_source_activation_m1_readiness_rollup_next_phase_decision_boundary_packet
)
render_sprint146_md = (
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

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m1_documentation_consolidation_operator_roadmap_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After Sprint 146",
    "## 3. Documentation Consolidation Objective",
    "## 4. M1 Packet Family Map",
    "## 5. Operator Roadmap State",
    "## 6. Evidence Reference Rules",
    "## 7. Future Sprint Continuity Rules",
    "## 8. Documentation Gaps and UNKNOWNs",
    "## 9. Human Approval Requirements",
    "## 10. Runtime Authorization Boundary",
    "## 11. Sovereignty, Trust, and Data Handling Constraints",
    "## 12. What Sprint 147 Does Not Build",
    "## 13. Exit Criteria",
    "## 14. Risks and Mitigations",
    "## 15. Recommended Next Safe Action",
)

REQUIRED_PACKET_FAMILIES = (
    "Scope and delivery boundary packets",
    "Dependency map packets",
    "Human gate and sequencing packets",
    "Controlled build readiness packets",
    "Demo-to-build transition packets",
    "Authorization review packets",
    "Pre-launch checklist packets",
    "Launch simulation packets",
    "Metrics and closeout packets",
    "Lessons learned and optimization packets",
    "Readiness rollup and decision boundary packets",
    "Documentation consolidation packets",
)

REQUIRED_OPERATOR_ROADMAP_PHRASES = (
    "m1 readiness chain completed through sprint 146",
    "sprint 147 documentation consolidation",
    "runtime remains unauthorized",
    "pilot launch remains unauthorized",
    "customer onboarding remains unauthorized",
    "source activation remains unauthorized",
    "next safe lanes are recommendation-only",
    "future implementation requires explicit human approval",
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


def test_service_source_rejects_runtime_launch_activation_collection_closeout_optimization() -> None:
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
    assert pkt["sprint_number"] == 147
    assert pkt["artifact_type"] == (
        "nf_active_source_activation_m1_documentation_consolidation_operator_roadmap_packet_v1"
    )
    assert pkt["packet_name"] == "NativeForge M1 Documentation Consolidation & Operator Roadmap Packet"
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True


def test_prerequisite_sprint146_readiness_rollup_next_phase_decision_boundary_packet() -> None:
    pkt = build_pkt()
    assert pkt["prerequisite_readiness_rollup_next_phase_decision_boundary_sprint"] == 146
    assert (
        pkt["prerequisite_readiness_rollup_next_phase_decision_boundary_artifact_type"]
        == "nf_active_source_activation_m1_readiness_rollup_next_phase_decision_boundary_packet_v1"
    )


def test_verification_path_includes_sprint145_lessons_learned_artifact_type() -> None:
    pkt = build_pkt()
    assert pkt["verification_path_lessons_learned_post_pilot_optimization_sprint"] == 145
    assert (
        pkt["verification_path_lessons_learned_post_pilot_optimization_artifact_type"]
        == "nf_active_source_activation_m1_lessons_learned_post_pilot_optimization_packet_v1"
    )


def test_packet_actual_counts_zero() -> None:
    pkt = build_pkt()
    for key, value in pkt.items():
        if key.startswith("actual_"):
            assert value == 0, key


def test_m1_packet_family_map_includes_all_required_families() -> None:
    pkt = build_pkt()
    families = [row["family"] for row in pkt["m1_packet_family_map"]]
    for expected in REQUIRED_PACKET_FAMILIES:
        assert expected in families


def test_operator_roadmap_state_includes_required_statuses() -> None:
    pkt = build_pkt()
    joined = " ".join(
        f"{row['roadmap_item']} {row['state']}" for row in pkt["operator_roadmap_state"]
    ).lower()
    for phrase in REQUIRED_OPERATOR_ROADMAP_PHRASES:
        assert phrase in joined


def test_future_sprint_continuity_rules_present() -> None:
    pkt = build_pkt()
    rules = pkt["future_sprint_continuity_rules"]
    assert len(rules) >= 4
    joined = " ".join(rules).lower()
    assert "sprint 146" in joined
    assert "sprint 145" in joined or "145" in joined
    assert "verification" in joined or "regression" in joined


def test_human_approval_requirements_explicit() -> None:
    pkt = build_pkt()
    joined = " ".join(pkt["human_approval_requirements"]).lower()
    assert "human operator approval" in joined


def test_runtime_authorization_boundary_explicit() -> None:
    pkt = build_pkt()
    joined = " ".join(pkt["runtime_authorization_boundary"]).lower()
    assert "runtime authorization boundary" in joined
    assert "runtime authorization" in joined


def test_sprint147_does_not_build_required_phrases() -> None:
    pkt = build_pkt()
    items = [x.lower() for x in pkt["sprint_147_does_not_build"]]
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


def test_markdown_what_sprint147_does_not_build_lists_required_exclusions() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 12. what sprint 147 does not build" in lower
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
        "# NativeForge M1 Documentation Consolidation & Operator Roadmap Packet v1\n"
    )
    positions = [md.index(h) for h in REQUIRED_SECTION_HEADERS]
    assert positions == sorted(positions)


def test_markdown_prerequisite_sprint146_readiness_rollup_and_decision_boundary() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 146" in lower
    assert "readiness rollup" in lower
    assert "decision boundary" in lower


def test_markdown_sovereignty_trust_constraints_section() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 11. sovereignty, trust, and data handling constraints" in lower
    assert "customer owns its data" in lower


def test_markdown_explicit_human_approval_language() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 9. human approval requirements" in lower
    assert "human operator approval" in lower


def test_markdown_runtime_authorization_boundary_section() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 10. runtime authorization boundary" in lower
    assert "runtime authorization boundary" in lower


def test_markdown_future_sprint_continuity_rules_present() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 7. future sprint continuity rules" in lower
    assert "sprint 146" in lower


def test_markdown_m1_packet_family_map_lists_all_required_families() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 4. m1 packet family map" in lower
    for fam in REQUIRED_PACKET_FAMILIES:
        assert fam.lower() in lower


def test_markdown_verification_path_regression_sprint146_sprint145() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 146" in lower
    assert "sprint 145" in lower
    assert "lessons learned" in lower or "post-pilot" in lower


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


def test_regression_sprint146_packet_still_valid() -> None:
    p146 = build_sprint146()
    assert p146["sprint_number"] == 146
    assert p146["preview_only"] is True
    assert p146["no_execution"] is True
    assert p146["no_activation"] is True
    assert p146["no_runnable_plan"] is True
    for key, value in p146.items():
        if key.startswith("actual_"):
            assert value == 0, key
    md146 = render_sprint146_md()
    assert "## 1. purpose" in md146.lower()
    assert "sprint 145" in md146.lower()


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
