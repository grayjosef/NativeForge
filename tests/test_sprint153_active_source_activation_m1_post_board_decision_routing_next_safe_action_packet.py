"""Sprint 153: M1 post-board decision routing packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT153_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_post_board_decision_routing_next_safe_action_packet_service"
)
sprint153_pkt = importlib.import_module(_SPRINT153_MOD)
build_pkt = (
    sprint153_pkt.build_active_source_activation_m1_post_board_decision_routing_next_safe_action_packet
)
render_md = (
    sprint153_pkt.render_active_source_activation_m1_post_board_decision_routing_next_safe_action_packet_markdown
)

_SPRINT152_MOD = (
    "nativeforge.services.active_source_activation_m1_human_runtime_authorization_board_packet_service"
)
sprint152_pkt = importlib.import_module(_SPRINT152_MOD)
build_sprint152 = (
    sprint152_pkt.build_active_source_activation_m1_human_runtime_authorization_board_packet
)
render_sprint152_md = (
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

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m1_post_board_decision_routing_next_safe_action_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After Sprint 152",
    "## 3. Post-Board Decision Routing Objective",
    "## 4. Supported Board Outcome Types",
    "## 5. Decision Routing Matrix",
    "## 6. Approval Recommendation Routing",
    "## 7. Denial Routing",
    "## 8. Deferral and Evidence Remediation Routing",
    "## 9. Narrowed Scope Routing",
    "## 10. No-Execution Default",
    "## 11. Runtime Authorization Boundary",
    "## 12. What Sprint 153 Does Not Build",
    "## 13. Exit Criteria",
    "## 14. Risks and Mitigations",
    "## 15. Recommended Next Safe Action",
)

REQUIRED_OUTCOME_TYPES = (
    "Recommend approval for future human review",
    "Deny runtime authorization",
    "Defer pending missing evidence",
    "Require narrowed implementation scope",
    "Require additional customer validation",
    "Require additional security review",
    "Require additional sovereignty and trust review",
    "Require rollback and support remediation",
    "Require documentation remediation",
    "Maintain no-execution default",
)

MATRIX_FIELD_KEYS = (
    "outcome",
    "required_evidence",
    "human_owner",
    "allowed_next_action",
    "blocked_actions",
    "required_follow_up",
    "exit_criteria",
)

REQUIRED_APPROVAL_ROUTING_STATEMENTS = (
    "Approval recommendation is not runtime authorization.",
    "Approval recommendation does not launch a pilot.",
    "Approval recommendation does not onboard customers.",
    "Approval recommendation does not activate sources.",
    "Approval recommendation does not activate production.",
    "Approval recommendation must route to a separate future human authorization process.",
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
        "no post-board execution",
    ):
        assert phrase in src


def test_packet_sprint_and_flags() -> None:
    pkt = build_pkt()
    assert pkt["sprint_number"] == 153
    assert pkt["artifact_type"] == (
        "nf_active_source_activation_m1_post_board_decision_routing_next_safe_action_packet_v1"
    )
    assert pkt["packet_name"] == "NativeForge M1 Post-Board Decision Routing & Next-Safe-Action Packet"
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True


def test_prerequisite_sprint152_human_runtime_authorization_board_packet() -> None:
    pkt = build_pkt()
    assert pkt["prerequisite_human_runtime_authorization_board_sprint"] == 152
    assert (
        pkt["prerequisite_human_runtime_authorization_board_artifact_type"]
        == "nf_active_source_activation_m1_human_runtime_authorization_board_packet_v1"
    )


def test_verification_path_includes_sprint152_and_sprint151_artifact_types() -> None:
    pkt = build_pkt()
    assert pkt["verification_path_human_runtime_authorization_board_sprint"] == 152
    assert (
        pkt["verification_path_human_runtime_authorization_board_artifact_type"]
        == "nf_active_source_activation_m1_human_runtime_authorization_board_packet_v1"
    )
    assert pkt["verification_path_runtime_authorization_review_readiness_no_execution_sprint"] == 151
    assert (
        pkt["verification_path_runtime_authorization_review_readiness_no_execution_artifact_type"]
        == "nf_active_source_activation_m1_runtime_authorization_review_readiness_no_execution_packet_v1"
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


def test_supported_board_outcome_types_include_all_required() -> None:
    pkt = build_pkt()
    outcomes = list(pkt["supported_board_outcome_types"])
    for label in REQUIRED_OUTCOME_TYPES:
        assert label in outcomes


def test_decision_routing_matrix_includes_all_required_fields_per_row() -> None:
    pkt = build_pkt()
    for row in pkt["decision_routing_matrix"]:
        for key in MATRIX_FIELD_KEYS:
            assert key in row
            assert isinstance(row[key], str)
            assert row[key].strip()


def test_approval_recommendation_routing_contains_all_required_no_execution_statements() -> None:
    pkt = build_pkt()
    joined = "\n".join(pkt["approval_recommendation_routing"])
    for sentence in REQUIRED_APPROVAL_ROUTING_STATEMENTS:
        assert sentence in joined


def test_denial_routing_present() -> None:
    pkt = build_pkt()
    joined = "\n".join(pkt["denial_routing"]).lower()
    assert "denial" in joined
    assert "no-execution default" in joined or "no execution default" in joined


def test_deferral_and_evidence_remediation_routing_present() -> None:
    pkt = build_pkt()
    joined = "\n".join(pkt["deferral_and_evidence_remediation_routing"]).lower()
    assert "deferral" in joined or "defer" in joined
    assert "evidence" in joined
    assert "remediation" in joined


def test_narrowed_scope_routing_present() -> None:
    pkt = build_pkt()
    joined = "\n".join(pkt["narrowed_scope_routing"]).lower()
    assert "narrowed scope" in joined


def test_runtime_authorization_boundary_language_explicit() -> None:
    pkt = build_pkt()
    joined = " | ".join(pkt["runtime_authorization_boundary"]).lower()
    assert "runtime authorization boundary" in joined
    assert "no runtime authorization granted" in joined
    assert "no board approval actually granted" in joined


def test_no_execution_default_language_present() -> None:
    pkt = build_pkt()
    joined = " ".join(pkt["no_execution_default"]).lower()
    assert "no-execution default" in joined


def test_sprint153_does_not_build_required_phrases() -> None:
    pkt = build_pkt()
    items = [x.lower() for x in pkt["sprint_153_does_not_build"]]
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
        "no post-board execution",
        "no runnable implementation workflow",
    ):
        assert phrase in items


def test_markdown_what_sprint153_does_not_build_lists_required_exclusions() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 12. what sprint 153 does not build" in lower
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
        "no post-board execution",
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
        "# NativeForge M1 Post-Board Decision Routing & Next-Safe-Action Packet v1\n"
    )
    positions = [md.index(h) for h in REQUIRED_SECTION_HEADERS]
    assert positions == sorted(positions)


def test_markdown_prerequisite_sprint152_human_runtime_authorization_board_packet() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 152" in lower
    assert "human runtime authorization board" in lower
    assert (
        "nf_active_source_activation_m1_human_runtime_authorization_board_packet_v1"
        in md
    )


def test_markdown_no_execution_default_section() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 10. no-execution default" in lower
    assert "no-execution default" in lower


def test_markdown_runtime_authorization_boundary_language() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 11. runtime authorization boundary" in lower
    assert "runtime authorization boundary" in lower


def test_markdown_approval_recommendation_routing_required_statements() -> None:
    md = render_md()
    sec_start = md.index("## 6. Approval Recommendation Routing")
    sec_end = md.index("## 7. Denial Routing")
    section = md[sec_start:sec_end]
    for sentence in REQUIRED_APPROVAL_ROUTING_STATEMENTS:
        assert sentence in section


def test_markdown_verification_path_regression_sprint152_sprint151() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 152" in lower
    assert "sprint 151" in lower


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


def test_regression_sprint152_packet_still_valid() -> None:
    p152 = build_sprint152()
    assert p152["sprint_number"] == 152
    assert p152["preview_only"] is True
    assert p152["no_execution"] is True
    assert p152["no_activation"] is True
    assert p152["no_runnable_plan"] is True
    for key, value in p152.items():
        if key.startswith("actual_"):
            assert value == 0, key
    md152 = render_sprint152_md()
    assert "## 1. purpose" in md152.lower()
    assert "sprint 151" in md152.lower()


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
