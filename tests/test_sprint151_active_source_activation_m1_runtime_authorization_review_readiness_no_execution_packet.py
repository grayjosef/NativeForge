"""Sprint 151: M1 runtime authorization review readiness no-execution packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT151_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_runtime_authorization_review_readiness_no_execution_packet_service"
)
sprint151_pkt = importlib.import_module(_SPRINT151_MOD)
build_pkt = (
    sprint151_pkt.build_active_source_activation_m1_runtime_authorization_review_readiness_no_execution_packet
)
render_md = (
    sprint151_pkt.render_active_source_activation_m1_runtime_authorization_review_readiness_no_execution_packet_markdown
)

_SPRINT150_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_bounded_implementation_design_human_gate_packet_service"
)
sprint150_pkt = importlib.import_module(_SPRINT150_MOD)
build_sprint150 = (
    sprint150_pkt.build_active_source_activation_m1_bounded_implementation_design_human_gate_packet
)
render_sprint150_md = (
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

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m1_runtime_authorization_review_readiness_no_execution_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After Sprint 150",
    "## 3. Runtime Authorization Review Readiness Objective",
    "## 4. Required Evidence Before Review",
    "## 5. Authorization Review Checklist",
    "## 6. Mandatory Denial Conditions",
    "## 7. Approval Prerequisites",
    "## 8. Human Gate and Signoff Model",
    "## 9. Runtime Boundary Model",
    "## 10. Sovereignty, Trust, and Security Constraints",
    "## 11. Explicit No-Execution Decision",
    "## 12. What Sprint 151 Does Not Build",
    "## 13. Exit Criteria",
    "## 14. Risks and Mitigations",
    "## 15. Recommended Next Safe Action",
)

REQUIRED_EVIDENCE_SUBSTRINGS = (
    "Completed M1 readiness chain reference",
    "Sprint 150 bounded implementation design reference",
    "Product owner review evidence",
    "Security review evidence",
    "Sovereignty and trust review evidence",
    "Customer validation evidence",
    "Runtime architecture review evidence",
    "Rollback and support evidence",
    "Data handling and audit export evidence",
    "Written approval requirement evidence",
)

REQUIRED_CHECKLIST_SUBSTRINGS = (
    "Confirm implementation scope is bounded",
    "Confirm no live customer data without approval",
    "Confirm no live source activation without approval",
    "Confirm no production deployment without approval",
    "Confirm human review gates are preserved",
    "Confirm audit/export requirements are documented",
    "Confirm data sovereignty constraints are documented",
    "Confirm rollback plan is documented",
    "Confirm support plan is documented",
    "Confirm written approval exists before runtime work",
)

REQUIRED_DENIAL_SUBSTRINGS = (
    "Missing human approval",
    "Missing customer validation evidence",
    "Missing security review",
    "Missing sovereignty and trust review",
    "Missing rollback plan",
    "Missing support plan",
    "Unbounded implementation scope",
    "Any attempt to bypass human review",
    "Any request for live customer data without approval",
    "Any request for source activation without approval",
    "Any request for production activation without approval",
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
        "no runtime authorization granted",
        "no customer data access",
        "no database migration",
        "no architecture implementation",
        "no implementation execution",
    ):
        assert phrase in src


def test_packet_sprint_and_flags() -> None:
    pkt = build_pkt()
    assert pkt["sprint_number"] == 151
    assert pkt["artifact_type"] == (
        "nf_active_source_activation_m1_runtime_authorization_review_readiness_no_execution_packet_v1"
    )
    assert pkt["packet_name"] == (
        "NativeForge M1 Runtime Authorization Review Readiness & No-Execution Packet"
    )
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True


def test_prerequisite_sprint150_bounded_implementation_design_human_gate_packet() -> None:
    pkt = build_pkt()
    assert pkt["prerequisite_bounded_implementation_design_human_gate_sprint"] == 150
    assert (
        pkt["prerequisite_bounded_implementation_design_human_gate_artifact_type"]
        == "nf_active_source_activation_m1_bounded_implementation_design_human_gate_packet_v1"
    )


def test_verification_path_includes_sprint150_and_sprint149_artifact_types() -> None:
    pkt = build_pkt()
    assert pkt["verification_path_bounded_implementation_design_human_gate_sprint"] == 150
    assert (
        pkt["verification_path_bounded_implementation_design_human_gate_artifact_type"]
        == "nf_active_source_activation_m1_bounded_implementation_design_human_gate_packet_v1"
    )
    assert pkt["verification_path_technical_architecture_review_runtime_boundary_sprint"] == 149
    assert (
        pkt["verification_path_technical_architecture_review_runtime_boundary_artifact_type"]
        == "nf_active_source_activation_m1_technical_architecture_review_runtime_boundary_packet_v1"
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


def test_required_evidence_before_review_includes_all_required_items() -> None:
    pkt = build_pkt()
    joined = "\n".join(pkt["required_evidence_before_review"])
    for sub in REQUIRED_EVIDENCE_SUBSTRINGS:
        assert sub in joined


def test_authorization_review_checklist_includes_all_required_items() -> None:
    pkt = build_pkt()
    joined = "\n".join(pkt["authorization_review_checklist"])
    for sub in REQUIRED_CHECKLIST_SUBSTRINGS:
        assert sub in joined


def test_mandatory_denial_conditions_include_all_required_items() -> None:
    pkt = build_pkt()
    joined = "\n".join(pkt["mandatory_denial_conditions"])
    for sub in REQUIRED_DENIAL_SUBSTRINGS:
        assert sub in joined


def test_human_approval_language_explicit() -> None:
    pkt = build_pkt()
    joined = " ".join(row["expectation"] for row in pkt["human_gate_and_signoff_model"]).lower()
    assert "human operator approval" in joined


def test_runtime_authorization_boundary_language_explicit() -> None:
    pkt = build_pkt()
    joined = " | ".join(pkt["runtime_boundary_model"]).lower()
    assert "runtime authorization boundary" in joined
    assert "no runtime authorization" in joined or "runtime authorization" in joined


def test_sovereignty_trust_and_security_constraints_present() -> None:
    pkt = build_pkt()
    joined = " ".join(pkt["sovereignty_trust_and_security_constraints"]).lower()
    assert "sovereignty" in joined
    assert "trust" in joined
    assert "security" in joined


def test_explicit_no_execution_decision_language_present() -> None:
    pkt = build_pkt()
    joined = " ".join(pkt["explicit_no_execution_decision"]).lower()
    assert "explicit no-execution decision" in joined


def test_sprint151_does_not_build_required_phrases() -> None:
    pkt = build_pkt()
    items = [x.lower() for x in pkt["sprint_151_does_not_build"]]
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
        "no runtime authorization granted",
        "no runnable implementation workflow",
    ):
        assert phrase in items


def test_markdown_what_sprint151_does_not_build_lists_required_exclusions() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 12. what sprint 151 does not build" in lower
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
        "no runtime authorization granted",
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
        "# NativeForge M1 Runtime Authorization Review Readiness & No-Execution Packet v1\n"
    )
    positions = [md.index(h) for h in REQUIRED_SECTION_HEADERS]
    assert positions == sorted(positions)


def test_markdown_prerequisite_sprint150_bounded_implementation_design() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 150" in lower
    assert "bounded implementation design" in lower
    assert "human gate" in lower
    assert (
        "nf_active_source_activation_m1_bounded_implementation_design_human_gate_packet_v1"
        in md
    )


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
    assert "## 8. human gate and signoff model" in lower
    assert "human operator approval" in lower


def test_markdown_explicit_no_execution_decision_section() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 11. explicit no-execution decision" in lower
    assert "explicit no-execution decision" in lower


def test_markdown_runtime_authorization_boundary_language() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 9. runtime boundary model" in lower
    assert "runtime authorization boundary" in lower


def test_markdown_verification_path_regression_sprint150_sprint149() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 150" in lower
    assert "sprint 149" in lower


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


def test_regression_sprint150_packet_still_valid() -> None:
    p150 = build_sprint150()
    assert p150["sprint_number"] == 150
    assert p150["preview_only"] is True
    assert p150["no_execution"] is True
    assert p150["no_activation"] is True
    assert p150["no_runnable_plan"] is True
    for key, value in p150.items():
        if key.startswith("actual_"):
            assert value == 0, key
    md150 = render_sprint150_md()
    assert "## 1. purpose" in md150.lower()
    assert "sprint 149" in md150.lower()


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
