"""Sprint 150: M1 bounded implementation design & human gate packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT150_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_bounded_implementation_design_human_gate_packet_service"
)
sprint150_pkt = importlib.import_module(_SPRINT150_MOD)
build_pkt = (
    sprint150_pkt.build_active_source_activation_m1_bounded_implementation_design_human_gate_packet
)
render_md = (
    sprint150_pkt.render_active_source_activation_m1_bounded_implementation_design_human_gate_packet_markdown
)

_SPRINT149_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_technical_architecture_review_runtime_boundary_packet_service"
)
sprint149_pkt = importlib.import_module(_SPRINT149_MOD)
build_sprint149 = (
    sprint149_pkt.build_active_source_activation_m1_technical_architecture_review_runtime_boundary_packet
)
render_sprint149_md = (
    sprint149_pkt.render_active_source_activation_m1_technical_architecture_review_runtime_boundary_packet_markdown
)

_SPRINT148_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_customer_validation_planning_interview_readiness_packet_service"
)
sprint148_pkt = importlib.import_module(_SPRINT148_MOD)
build_sprint148 = (
    sprint148_pkt.build_active_source_activation_m1_customer_validation_planning_interview_readiness_packet
)
render_sprint148_md = (
    sprint148_pkt.render_active_source_activation_m1_customer_validation_planning_interview_readiness_packet_markdown
)

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m1_bounded_implementation_design_human_gate_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After Sprint 149",
    "## 3. Bounded Implementation Design Objective",
    "## 4. Implementation Slice Categories",
    "## 5. Human Gate Model",
    "## 6. Required Pre-Implementation Evidence",
    "## 7. Runtime Boundary Model",
    "## 8. Source Activation Boundary",
    "## 9. Customer Data Boundary",
    "## 10. Sovereignty, Trust, and Security Constraints",
    "## 11. Runtime Authorization Boundary",
    "## 12. What Sprint 150 Does Not Build",
    "## 13. Exit Criteria",
    "## 14. Risks and Mitigations",
    "## 15. Recommended Next Safe Action",
)

REQUIRED_IMPLEMENTATION_SLICE_CATEGORIES = (
    "Documentation-only implementation design",
    "Source ingestion design slice",
    "NOFO extraction design slice",
    "Form package preview design slice",
    "Human review workflow design slice",
    "Audit export design slice",
    "Sovereignty and data handling design slice",
    "Runtime monitoring design slice",
    "Rollback and support design slice",
    "Deployment separation design slice",
)

REQUIRED_HUMAN_GATES = (
    "Operator review gate",
    "Product owner review gate",
    "Security review gate",
    "Sovereignty and trust review gate",
    "Customer validation review gate",
    "Runtime authorization review gate",
    "Explicit no-execution default",
    "Written approval requirement before any runtime phase",
)

REQUIRED_RUNTIME_BOUNDARY_SUBSTRINGS = (
    "preview-only artifact generation",
    "no runtime writes",
    "no live source execution",
    "no customer data access",
    "no production deployment",
    "no automated customer workflow",
    "no scheduler or worker activation",
    "no external api calls",
    "no database migration",
    "human approval required before runtime phase",
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
        "no customer outreach",
        "no interview scheduling",
        "no runtime execution",
        "no source activation",
        "no production activation",
        "no real metric collection",
        "no real pilot closeout",
        "no optimization execution",
        "no runnable implementation workflow",
        "no customer onboarding",
        "no runtime authorization",
        "no customer data access",
        "no database migration",
        "no architecture implementation",
        "no implementation execution",
    ):
        assert phrase in src


def test_packet_sprint_and_flags() -> None:
    pkt = build_pkt()
    assert pkt["sprint_number"] == 150
    assert pkt["artifact_type"] == (
        "nf_active_source_activation_m1_bounded_implementation_design_human_gate_packet_v1"
    )
    assert pkt["packet_name"] == "NativeForge M1 Bounded Implementation Design & Human Gate Packet"
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True


def test_prerequisite_sprint149_technical_architecture_review_runtime_boundary_packet() -> None:
    pkt = build_pkt()
    assert pkt["prerequisite_technical_architecture_review_runtime_boundary_sprint"] == 149
    assert (
        pkt["prerequisite_technical_architecture_review_runtime_boundary_artifact_type"]
        == "nf_active_source_activation_m1_technical_architecture_review_runtime_boundary_packet_v1"
    )


def test_verification_path_includes_sprint149_and_sprint148_artifact_types() -> None:
    pkt = build_pkt()
    assert pkt["verification_path_technical_architecture_review_runtime_boundary_sprint"] == 149
    assert (
        pkt["verification_path_technical_architecture_review_runtime_boundary_artifact_type"]
        == "nf_active_source_activation_m1_technical_architecture_review_runtime_boundary_packet_v1"
    )
    assert pkt["verification_path_customer_validation_planning_interview_readiness_sprint"] == 148
    assert (
        pkt["verification_path_customer_validation_planning_interview_readiness_artifact_type"]
        == "nf_active_source_activation_m1_customer_validation_planning_interview_readiness_packet_v1"
    )


def test_packet_actual_counts_zero() -> None:
    pkt = build_pkt()
    for key, value in pkt.items():
        if key.startswith("actual_"):
            assert value == 0, key


def test_outreach_and_scheduling_counters_zero() -> None:
    pkt = build_pkt()
    assert pkt["actual_customer_outreach_attempts"] == 0
    assert pkt["actual_interviews_scheduled"] == 0


def test_implementation_slice_categories_include_all_required_categories() -> None:
    pkt = build_pkt()
    cats = [row["category"] for row in pkt["implementation_slice_categories"]]
    for expected in REQUIRED_IMPLEMENTATION_SLICE_CATEGORIES:
        assert expected in cats


def test_human_gate_model_includes_all_required_gates() -> None:
    pkt = build_pkt()
    gates = [row["gate"] for row in pkt["human_gate_model"]]
    for expected in REQUIRED_HUMAN_GATES:
        assert expected in gates


def test_runtime_boundary_model_includes_all_required_boundaries() -> None:
    pkt = build_pkt()
    joined = " | ".join(pkt["runtime_boundary_model"]).lower()
    for sub in REQUIRED_RUNTIME_BOUNDARY_SUBSTRINGS:
        assert sub in joined


def test_human_approval_requirements_explicit() -> None:
    pkt = build_pkt()
    joined = " ".join(row["expectation"] for row in pkt["human_gate_model"]).lower()
    assert "human operator approval" in joined


def test_runtime_authorization_boundary_explicit() -> None:
    pkt = build_pkt()
    joined = " ".join(pkt["runtime_authorization_boundary"]).lower()
    assert "runtime authorization boundary" in joined
    assert "runtime authorization" in joined


def test_sovereignty_trust_and_security_constraints_present() -> None:
    pkt = build_pkt()
    joined = " ".join(pkt["sovereignty_trust_and_security_constraints"]).lower()
    assert "sovereignty" in joined
    assert "trust" in joined
    assert "security" in joined


def test_sprint150_does_not_build_required_phrases() -> None:
    pkt = build_pkt()
    items = [x.lower() for x in pkt["sprint_150_does_not_build"]]
    for phrase in (
        "no pilot launch",
        "no customer outreach",
        "no interview scheduling",
        "no customer onboarding",
        "no customer data access",
        "no database migration",
        "no source activation",
        "no production activation",
        "no real metric collection",
        "no real pilot closeout",
        "no optimization execution",
        "no architecture implementation",
        "no implementation execution",
        "no runtime authorization",
        "no runnable implementation workflow",
    ):
        assert phrase in items


def test_markdown_what_sprint150_does_not_build_lists_required_exclusions() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 12. what sprint 150 does not build" in lower
    for phrase in (
        "no pilot launch",
        "no customer outreach",
        "no interview scheduling",
        "no customer onboarding",
        "no customer data access",
        "no database migration",
        "no source activation",
        "no production activation",
        "no real metric collection",
        "no real pilot closeout",
        "no optimization execution",
        "no architecture implementation",
        "no implementation execution",
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
        "# NativeForge M1 Bounded Implementation Design & Human Gate Packet v1\n"
    )
    positions = [md.index(h) for h in REQUIRED_SECTION_HEADERS]
    assert positions == sorted(positions)


def test_markdown_prerequisite_sprint149_technical_architecture_review() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 149" in lower
    assert "technical architecture review" in lower
    assert "runtime boundary" in lower


def test_markdown_sovereignty_trust_security_section() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 10. sovereignty, trust, and security constraints" in lower
    assert "sovereignty" in lower
    assert "trust" in lower
    assert "security" in lower


def test_markdown_explicit_human_approval_language() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 5. human gate model" in lower
    assert "human operator approval" in lower


def test_markdown_runtime_authorization_boundary_section() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 11. runtime authorization boundary" in lower
    assert "runtime authorization boundary" in lower


def test_markdown_verification_path_regression_sprint149_sprint148() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 149" in lower
    assert "sprint 148" in lower


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


def test_regression_sprint149_packet_still_valid() -> None:
    p149 = build_sprint149()
    assert p149["sprint_number"] == 149
    assert p149["preview_only"] is True
    assert p149["no_execution"] is True
    assert p149["no_activation"] is True
    assert p149["no_runnable_plan"] is True
    for key, value in p149.items():
        if key.startswith("actual_"):
            assert value == 0, key
    md149 = render_sprint149_md()
    assert "## 1. purpose" in md149.lower()
    assert "sprint 148" in md149.lower()


def test_regression_sprint148_packet_still_valid() -> None:
    p148 = build_sprint148()
    assert p148["sprint_number"] == 148
    assert p148["preview_only"] is True
    assert p148["no_execution"] is True
    assert p148["no_activation"] is True
    assert p148["no_runnable_plan"] is True
    for key, value in p148.items():
        if key.startswith("actual_"):
            assert value == 0, key
    md148 = render_sprint148_md()
    assert "## 1. purpose" in md148.lower()
    assert "sprint 147" in md148.lower()
