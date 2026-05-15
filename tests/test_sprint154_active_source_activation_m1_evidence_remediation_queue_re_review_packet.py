"""Sprint 154: M1 evidence remediation queue and re-review packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT154_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_evidence_remediation_queue_re_review_packet_service"
)
sprint154_pkt = importlib.import_module(_SPRINT154_MOD)
build_pkt = (
    sprint154_pkt.build_active_source_activation_m1_evidence_remediation_queue_re_review_packet
)
render_md = (
    sprint154_pkt.render_active_source_activation_m1_evidence_remediation_queue_re_review_packet_markdown
)

_SPRINT153_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_post_board_decision_routing_next_safe_action_packet_service"
)
sprint153_pkt = importlib.import_module(_SPRINT153_MOD)
build_sprint153 = (
    sprint153_pkt.build_active_source_activation_m1_post_board_decision_routing_next_safe_action_packet
)
render_sprint153_md = (
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

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m1_evidence_remediation_queue_re_review_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After Sprint 153",
    "## 3. Evidence Remediation Queue Objective",
    "## 4. Remediation Item Categories",
    "## 5. Queue State Model",
    "## 6. Evidence Owner Model",
    "## 7. Re-Review Readiness Signals",
    "## 8. Blocked Action Rules",
    "## 9. Deferred Outcome Handling",
    "## 10. No-Execution Default",
    "## 11. Runtime Authorization Boundary",
    "## 12. What Sprint 154 Does Not Build",
    "## 13. Exit Criteria",
    "## 14. Risks and Mitigations",
    "## 15. Recommended Next Safe Action",
)

REQUIRED_REMEDIATION_CATEGORIES = (
    "Missing security review evidence",
    "Missing sovereignty and trust review evidence",
    "Missing customer validation evidence",
    "Missing rollback plan evidence",
    "Missing support readiness evidence",
    "Missing audit export evidence",
    "Missing data handling evidence",
    "Missing technical architecture review evidence",
    "Missing written approval evidence",
    "Unbounded implementation scope evidence",
)

REQUIRED_QUEUE_STATES = (
    "Identified",
    "Assigned",
    "Evidence requested",
    "Evidence received",
    "Re-review ready",
    "Deferred",
    "Rejected",
    "Closed without authorization",
    "Ready for future human review only",
    "Blocked by no-execution default",
)

REQUIRED_BLOCKED_ACTION_RULES = (
    "Remediation queue entry does not authorize runtime.",
    "Remediation queue entry does not authorize pilot launch.",
    "Remediation queue entry does not authorize customer onboarding.",
    "Remediation queue entry does not authorize source activation.",
    "Remediation queue entry does not authorize production activation.",
    "Remediation queue entry does not authorize database migration.",
    "Remediation queue entry does not authorize implementation execution.",
    "Re-review readiness is not approval.",
    "Evidence receipt is not approval.",
    "Written human approval remains required.",
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
        "no remediation execution",
    ):
        assert phrase in src


def test_packet_sprint_and_flags() -> None:
    pkt = build_pkt()
    assert pkt["sprint_number"] == 154
    assert pkt["artifact_type"] == (
        "nf_active_source_activation_m1_evidence_remediation_queue_re_review_packet_v1"
    )
    assert pkt["packet_name"] == "NativeForge M1 Evidence Remediation Queue & Re-Review Packet"
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True


def test_prerequisite_sprint153_post_board_decision_routing_packet() -> None:
    pkt = build_pkt()
    assert pkt["prerequisite_post_board_decision_routing_sprint"] == 153
    assert (
        pkt["prerequisite_post_board_decision_routing_artifact_type"]
        == "nf_active_source_activation_m1_post_board_decision_routing_next_safe_action_packet_v1"
    )


def test_verification_path_includes_sprint153_and_sprint152_artifact_types() -> None:
    pkt = build_pkt()
    assert pkt["verification_path_post_board_decision_routing_sprint"] == 153
    assert (
        pkt["verification_path_post_board_decision_routing_artifact_type"]
        == "nf_active_source_activation_m1_post_board_decision_routing_next_safe_action_packet_v1"
    )
    assert pkt["verification_path_human_runtime_authorization_board_sprint"] == 152
    assert (
        pkt["verification_path_human_runtime_authorization_board_artifact_type"]
        == "nf_active_source_activation_m1_human_runtime_authorization_board_packet_v1"
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
    assert pkt["actual_remediation_executions"] == 0


def test_remediation_item_categories_include_all_required() -> None:
    pkt = build_pkt()
    categories = list(pkt["remediation_item_categories"])
    for label in REQUIRED_REMEDIATION_CATEGORIES:
        assert label in categories


def test_queue_state_model_includes_all_required_states() -> None:
    pkt = build_pkt()
    states = list(pkt["queue_state_model"])
    for label in REQUIRED_QUEUE_STATES:
        assert label in states


def test_blocked_action_rules_include_all_required() -> None:
    pkt = build_pkt()
    rules = list(pkt["blocked_action_rules"])
    for rule in REQUIRED_BLOCKED_ACTION_RULES:
        assert rule in rules


def test_re_review_readiness_signals_present() -> None:
    pkt = build_pkt()
    joined = "\n".join(pkt["re_review_readiness_signals"]).lower()
    assert "re-review" in joined or "re-review ready" in joined
    assert "not approval" in joined


def test_deferred_outcome_handling_present() -> None:
    pkt = build_pkt()
    joined = "\n".join(pkt["deferred_outcome_handling"]).lower()
    assert "deferred" in joined or "deferral" in joined
    assert "sprint 153" in joined


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
    assert "no remediation execution" in joined


def test_sprint154_does_not_build_required_phrases() -> None:
    pkt = build_pkt()
    items = [x.lower() for x in pkt["sprint_154_does_not_build"]]
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
        "no remediation execution",
        "no runnable implementation workflow",
    ):
        assert phrase in items


def test_markdown_what_sprint154_does_not_build_lists_required_exclusions() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 12. what sprint 154 does not build" in lower
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
        "no remediation execution",
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
        "# NativeForge M1 Evidence Remediation Queue & Re-Review Packet v1\n"
    )
    positions = [md.index(h) for h in REQUIRED_SECTION_HEADERS]
    assert positions == sorted(positions)


def test_markdown_prerequisite_sprint153_post_board_decision_routing_packet() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 153" in lower
    assert "post-board decision routing" in lower
    assert (
        "nf_active_source_activation_m1_post_board_decision_routing_next_safe_action_packet_v1"
        in md
    )


def test_markdown_no_execution_default_section() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 10. no-execution default" in lower
    assert "no-execution default" in lower
    assert "no remediation execution" in lower


def test_markdown_runtime_authorization_boundary_language() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 11. runtime authorization boundary" in lower
    assert "runtime authorization boundary" in lower


def test_markdown_verification_path_regression_sprint153_sprint152() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 153" in lower
    assert "sprint 152" in lower


def test_markdown_blocked_action_rules_required_statements() -> None:
    md = render_md()
    sec_start = md.index("## 8. Blocked Action Rules")
    sec_end = md.index("## 9. Deferred Outcome Handling")
    section = md[sec_start:sec_end]
    for rule in REQUIRED_BLOCKED_ACTION_RULES:
        assert rule in section


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


def test_regression_sprint153_packet_still_valid() -> None:
    p153 = build_sprint153()
    assert p153["sprint_number"] == 153
    assert p153["preview_only"] is True
    assert p153["no_execution"] is True
    assert p153["no_activation"] is True
    assert p153["no_runnable_plan"] is True
    for key, value in p153.items():
        if key.startswith("actual_"):
            assert value == 0, key
    md153 = render_sprint153_md()
    assert "## 1. purpose" in md153.lower()
    assert "sprint 152" in md153.lower()


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
