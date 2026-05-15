"""Sprint 152: M1 human runtime authorization board packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT152_MOD = (
    "nativeforge.services.active_source_activation_m1_human_runtime_authorization_board_packet_service"
)
sprint152_pkt = importlib.import_module(_SPRINT152_MOD)
build_pkt = sprint152_pkt.build_active_source_activation_m1_human_runtime_authorization_board_packet
render_md = (
    sprint152_pkt.render_active_source_activation_m1_human_runtime_authorization_board_packet_markdown
)

_SPRINT151_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_runtime_authorization_review_readiness_no_execution_packet_service"
)
sprint151_pkt = importlib.import_module(_SPRINT151_MOD)
build_sprint151 = (
    sprint151_pkt.build_active_source_activation_m1_runtime_authorization_review_readiness_no_execution_packet
)
render_sprint151_md = (
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

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m1_human_runtime_authorization_board_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After Sprint 151",
    "## 3. Human Runtime Authorization Board Objective",
    "## 4. Board Composition Model",
    "## 5. Evidence Review Docket",
    "## 6. Decision Rights and Limits",
    "## 7. Mandatory Denial Conditions",
    "## 8. Approval Documentation Requirements",
    "## 9. No-Execution Default",
    "## 10. Sovereignty, Trust, and Security Constraints",
    "## 11. Runtime Authorization Boundary",
    "## 12. What Sprint 152 Does Not Build",
    "## 13. Exit Criteria",
    "## 14. Risks and Mitigations",
    "## 15. Recommended Next Safe Action",
)

REQUIRED_BOARD_ROLES = (
    "Product owner reviewer",
    "Technical architecture reviewer",
    "Security reviewer",
    "Sovereignty and trust reviewer",
    "Customer validation reviewer",
    "Operations and support reviewer",
    "Audit and export reviewer",
    "Human gate owner",
)

REQUIRED_DOCKET_SUBSTRINGS = (
    "Sprint 151 runtime authorization review readiness reference",
    "Sprint 150 bounded implementation design reference",
    "Technical architecture review evidence",
    "Customer validation planning evidence",
    "Security and audit evidence",
    "Sovereignty and data handling evidence",
    "Rollback and support evidence",
    "Human review gate evidence",
    "Written approval evidence",
    "Explicit denial condition review",
)

REQUIRED_RIGHT_SUBSTRINGS = (
    "May recommend approval for future human review only",
    "May recommend denial",
    "May request missing evidence",
    "May require narrowed implementation scope",
    "May require additional customer validation",
    "May require additional security review",
)

REQUIRED_LIMIT_SUBSTRINGS = (
    "May not activate runtime",
    "May not start pilot",
    "May not onboard customers",
    "May not activate sources",
    "May not approve production activation from this packet alone",
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
        "no board approval actually granted",
        "no customer data access",
        "no database migration",
        "no architecture implementation",
        "no implementation execution",
    ):
        assert phrase in src


def test_packet_sprint_and_flags() -> None:
    pkt = build_pkt()
    assert pkt["sprint_number"] == 152
    assert pkt["artifact_type"] == (
        "nf_active_source_activation_m1_human_runtime_authorization_board_packet_v1"
    )
    assert pkt["packet_name"] == "NativeForge M1 Human Runtime Authorization Board Packet"
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True


def test_prerequisite_sprint151_runtime_authorization_review_readiness_packet() -> None:
    pkt = build_pkt()
    assert pkt["prerequisite_runtime_authorization_review_readiness_no_execution_sprint"] == 151
    assert (
        pkt["prerequisite_runtime_authorization_review_readiness_no_execution_artifact_type"]
        == "nf_active_source_activation_m1_runtime_authorization_review_readiness_no_execution_packet_v1"
    )


def test_verification_path_includes_sprint151_and_sprint150_artifact_types() -> None:
    pkt = build_pkt()
    assert pkt["verification_path_runtime_authorization_review_readiness_no_execution_sprint"] == 151
    assert (
        pkt["verification_path_runtime_authorization_review_readiness_no_execution_artifact_type"]
        == "nf_active_source_activation_m1_runtime_authorization_review_readiness_no_execution_packet_v1"
    )
    assert pkt["verification_path_bounded_implementation_design_human_gate_sprint"] == 150
    assert (
        pkt["verification_path_bounded_implementation_design_human_gate_artifact_type"]
        == "nf_active_source_activation_m1_bounded_implementation_design_human_gate_packet_v1"
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


def test_board_composition_includes_all_required_reviewers() -> None:
    pkt = build_pkt()
    roles = [row["role"] for row in pkt["board_composition_model"]]
    for role in REQUIRED_BOARD_ROLES:
        assert role in roles


def test_evidence_review_docket_includes_all_required_items() -> None:
    pkt = build_pkt()
    joined = "\n".join(pkt["evidence_review_docket"])
    for sub in REQUIRED_DOCKET_SUBSTRINGS:
        assert sub in joined


def test_decision_rights_and_limits_include_all_required_items() -> None:
    pkt = build_pkt()
    rights = "\n".join(r["right"] for r in pkt["decision_rights"])
    limits = "\n".join(x["limit"] for x in pkt["decision_limits"])
    for sub in REQUIRED_RIGHT_SUBSTRINGS:
        assert sub in rights
    for sub in REQUIRED_LIMIT_SUBSTRINGS:
        assert sub in limits


def test_mandatory_denial_conditions_present() -> None:
    pkt = build_pkt()
    joined = "\n".join(pkt["mandatory_denial_conditions"])
    assert "deny" in joined.lower()
    assert "sprint 151" in joined.lower()
    assert "sprint 150" in joined.lower()


def test_approval_documentation_requirements_present() -> None:
    pkt = build_pkt()
    joined = "\n".join(pkt["approval_documentation_requirements"]).lower()
    assert "human operator approval" in joined
    assert "future" in joined


def test_human_approval_language_explicit() -> None:
    pkt = build_pkt()
    board_text = " ".join(
        row["responsibility"] for row in pkt["board_composition_model"]
    ).lower()
    assert "human operator approval" in board_text
    assert "no board approval actually granted" in board_text


def test_runtime_authorization_boundary_language_explicit() -> None:
    pkt = build_pkt()
    joined = " | ".join(pkt["runtime_authorization_boundary"]).lower()
    assert "runtime authorization boundary" in joined
    assert "no runtime authorization granted" in joined
    assert "no board approval actually granted" in joined


def test_sovereignty_trust_and_security_constraints_present() -> None:
    pkt = build_pkt()
    joined = " ".join(pkt["sovereignty_trust_and_security_constraints"]).lower()
    assert "sovereignty" in joined
    assert "trust" in joined
    assert "security" in joined


def test_no_execution_default_language_present() -> None:
    pkt = build_pkt()
    joined = " ".join(pkt["no_execution_default"]).lower()
    assert "no-execution default" in joined


def test_sprint152_does_not_build_required_phrases() -> None:
    pkt = build_pkt()
    items = [x.lower() for x in pkt["sprint_152_does_not_build"]]
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
        "no board approval actually granted",
        "no runnable implementation workflow",
    ):
        assert phrase in items


def test_markdown_what_sprint152_does_not_build_lists_required_exclusions() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 12. what sprint 152 does not build" in lower
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
        "no board approval actually granted",
        "no runnable implementation workflow",
    ):
        assert phrase in lower


def test_recommended_next_safe_action_recommendation_only() -> None:
    pkt = build_pkt()
    step = (pkt.get("recommended_next_safe_action") or "").lower()
    assert "recommendation-only" in step or "recommendation only" in step


def test_markdown_required_section_headers_in_order() -> None:
    md = render_md()
    assert md.startswith("# NativeForge M1 Human Runtime Authorization Board Packet v1\n")
    positions = [md.index(h) for h in REQUIRED_SECTION_HEADERS]
    assert positions == sorted(positions)


def test_markdown_prerequisite_sprint151_runtime_authorization_review_readiness() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 151" in lower
    assert "runtime authorization review readiness" in lower
    assert (
        "nf_active_source_activation_m1_runtime_authorization_review_readiness_no_execution_packet_v1"
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
    assert "## 4. board composition model" in lower
    assert "human operator approval" in lower


def test_markdown_no_execution_default_section() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 9. no-execution default" in lower
    assert "no-execution default" in lower


def test_markdown_runtime_authorization_boundary_language() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 11. runtime authorization boundary" in lower
    assert "runtime authorization boundary" in lower


def test_markdown_verification_path_regression_sprint151_sprint150() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 151" in lower
    assert "sprint 150" in lower


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


def test_regression_sprint151_packet_still_valid() -> None:
    p151 = build_sprint151()
    assert p151["sprint_number"] == 151
    assert p151["preview_only"] is True
    assert p151["no_execution"] is True
    assert p151["no_activation"] is True
    assert p151["no_runnable_plan"] is True
    for key, value in p151.items():
        if key.startswith("actual_"):
            assert value == 0, key
    md151 = render_sprint151_md()
    assert "## 1. purpose" in md151.lower()
    assert "sprint 150" in md151.lower()


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
