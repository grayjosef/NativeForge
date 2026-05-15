"""Sprint 155: M1 re-review board readiness and evidence closure packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT155_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_re_review_board_readiness_evidence_closure_packet_service"
)
sprint155_pkt = importlib.import_module(_SPRINT155_MOD)
build_pkt = (
    sprint155_pkt.build_active_source_activation_m1_re_review_board_readiness_evidence_closure_packet
)
render_md = (
    sprint155_pkt.render_active_source_activation_m1_re_review_board_readiness_evidence_closure_packet_markdown
)

_SPRINT154_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_evidence_remediation_queue_re_review_packet_service"
)
sprint154_pkt = importlib.import_module(_SPRINT154_MOD)
build_sprint154 = (
    sprint154_pkt.build_active_source_activation_m1_evidence_remediation_queue_re_review_packet
)
render_sprint154_md = (
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

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m1_re_review_board_readiness_evidence_closure_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After Sprint 154",
    "## 3. Re-Review Board Readiness Objective",
    "## 4. Evidence Closure Criteria",
    "## 5. Re-Review Docket Readiness Model",
    "## 6. Evidence Sufficiency Checks",
    "## 7. Owner Signoff Model",
    "## 8. Rejection and Deferral Paths",
    "## 9. Return-to-Remediation Routing",
    "## 10. No-Execution Default",
    "## 11. Runtime Authorization Boundary",
    "## 12. What Sprint 155 Does Not Build",
    "## 13. Exit Criteria",
    "## 14. Risks and Mitigations",
    "## 15. Recommended Next Safe Action",
)

REQUIRED_EVIDENCE_CLOSURE_CRITERIA = (
    "Security review evidence closed",
    "Sovereignty and trust review evidence closed",
    "Customer validation evidence closed",
    "Rollback plan evidence closed",
    "Support readiness evidence closed",
    "Audit export evidence closed",
    "Data handling evidence closed",
    "Technical architecture review evidence closed",
    "Written approval evidence closed",
    "Bounded implementation scope evidence closed",
)

REQUIRED_DOCKET_READINESS_STATES = (
    "Remediation item closed",
    "Evidence owner signoff recorded",
    "Evidence sufficiency checked",
    "Denial conditions re-checked",
    "Blocked actions confirmed",
    "No-execution default confirmed",
    "Runtime boundary confirmed",
    "Re-review packet prepared for future human review only",
    "No board approval actually granted",
    "No runtime authorization granted",
)

REQUIRED_BOUNDARY_PHRASES = (
    "Evidence closure is not approval.",
    "Re-review readiness is not approval.",
    "Re-review docket preparation is not runtime authorization.",
    "Owner signoff is not runtime authorization.",
    "Future human re-review remains required.",
    "Written human approval remains required.",
    "No pilot launch may occur from this packet.",
    "No customer onboarding may occur from this packet.",
    "No source activation may occur from this packet.",
    "No production activation may occur from this packet.",
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


def test_service_source_rejects_forbidden_execution_and_activation_language() -> None:
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
        "no evidence closure execution",
        "no re-review board convened",
    ):
        assert phrase in src


def test_packet_sprint_and_flags() -> None:
    pkt = build_pkt()
    assert pkt["sprint_number"] == 155
    assert pkt["artifact_type"] == (
        "nf_active_source_activation_m1_re_review_board_readiness_evidence_closure_packet_v1"
    )
    assert pkt["packet_name"] == (
        "NativeForge M1 Re-Review Board Readiness & Evidence Closure Packet"
    )
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True


def test_prerequisite_sprint154_evidence_remediation_queue_re_review_packet() -> None:
    pkt = build_pkt()
    assert pkt["prerequisite_evidence_remediation_queue_re_review_sprint"] == 154
    assert (
        pkt["prerequisite_evidence_remediation_queue_re_review_artifact_type"]
        == "nf_active_source_activation_m1_evidence_remediation_queue_re_review_packet_v1"
    )


def test_verification_path_includes_sprint154_and_sprint153_artifact_types() -> None:
    pkt = build_pkt()
    assert pkt["verification_path_evidence_remediation_queue_re_review_sprint"] == 154
    assert (
        pkt["verification_path_evidence_remediation_queue_re_review_artifact_type"]
        == "nf_active_source_activation_m1_evidence_remediation_queue_re_review_packet_v1"
    )
    assert pkt["verification_path_post_board_decision_routing_sprint"] == 153
    assert (
        pkt["verification_path_post_board_decision_routing_artifact_type"]
        == "nf_active_source_activation_m1_post_board_decision_routing_next_safe_action_packet_v1"
    )


def test_packet_actual_counts_zero() -> None:
    pkt = build_pkt()
    for key, value in pkt.items():
        if key.startswith("actual_"):
            assert value == 0, key


def test_outreach_scheduling_remediation_closure_and_board_counters_zero() -> None:
    pkt = build_pkt()
    assert pkt["actual_customer_outreach_attempts"] == 0
    assert pkt["actual_interviews_scheduled"] == 0
    assert pkt["actual_remediation_executions"] == 0
    assert pkt["actual_evidence_closure_executions"] == 0
    assert pkt["actual_re_review_board_convened"] == 0


def test_evidence_closure_criteria_include_all_required() -> None:
    pkt = build_pkt()
    criteria = list(pkt["evidence_closure_criteria"])
    for label in REQUIRED_EVIDENCE_CLOSURE_CRITERIA:
        assert label in criteria


def test_re_review_docket_readiness_model_includes_all_required_states() -> None:
    pkt = build_pkt()
    states = list(pkt["re_review_docket_readiness_model"])
    for label in REQUIRED_DOCKET_READINESS_STATES:
        assert label in states


def test_evidence_sufficiency_checks_present() -> None:
    pkt = build_pkt()
    joined = "\n".join(pkt["evidence_sufficiency_checks"]).lower()
    assert "sufficiency" in joined
    assert "evidence closure is not approval" in joined


def test_owner_signoff_model_present() -> None:
    pkt = build_pkt()
    rows = pkt["owner_signoff_model"]
    assert len(rows) >= 1
    first = rows[0]
    assert "owner_role" in first
    assert "responsibility" in first
    assert "limits" in first
    joined_limits = "\n".join(r.get("limits", "") for r in rows).lower()
    assert "owner signoff is not runtime authorization" in joined_limits


def test_rejection_deferral_and_return_to_remediation_present() -> None:
    pkt = build_pkt()
    rj = "\n".join(pkt["rejection_paths"]).lower()
    df = "\n".join(pkt["deferral_paths"]).lower()
    rt = "\n".join(pkt["return_to_remediation_routing"]).lower()
    assert "rejection" in rj
    assert "deferral" in df
    assert "return-to-remediation" in rt or "return to remediation" in rt
    assert "sprint 154" in rt


def test_blocked_action_rules_include_required_boundary_language() -> None:
    pkt = build_pkt()
    rules = list(pkt["blocked_action_rules"])
    for phrase in REQUIRED_BOUNDARY_PHRASES:
        assert phrase in rules


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
    assert "no evidence closure execution" in joined
    assert "no re-review board convened" in joined


def test_sprint155_does_not_build_required_phrases() -> None:
    pkt = build_pkt()
    items = [x.lower() for x in pkt["sprint_155_does_not_build"]]
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
        "no evidence closure execution",
        "no re-review board convened",
        "no runnable implementation workflow",
    ):
        assert phrase in items


def test_markdown_what_sprint155_does_not_build_lists_required_exclusions() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 12. what sprint 155 does not build" in lower
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
        "no evidence closure execution",
        "no re-review board convened",
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
        "# NativeForge M1 Re-Review Board Readiness & Evidence Closure Packet v1\n"
    )
    positions = [md.index(h) for h in REQUIRED_SECTION_HEADERS]
    assert positions == sorted(positions)


def test_markdown_prerequisite_sprint154_evidence_remediation_packet() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 154" in lower
    assert "evidence remediation queue" in lower
    assert (
        "nf_active_source_activation_m1_evidence_remediation_queue_re_review_packet_v1"
        in md
    )


def test_markdown_no_execution_default_section() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 10. no-execution default" in lower
    assert "no-execution default" in lower
    assert "no evidence closure execution" in lower


def test_markdown_runtime_authorization_boundary_language() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 11. runtime authorization boundary" in lower
    assert "runtime authorization boundary" in lower


def test_markdown_verification_path_regression_sprint154_sprint153() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 154" in lower
    assert "sprint 153" in lower


def test_markdown_blocked_action_rules_required_statements() -> None:
    md = render_md()
    sec_start = md.index("## 11. Runtime Authorization Boundary")
    sec_end = md.index("## 12. What Sprint 155 Does Not Build")
    section = md[sec_start:sec_end]
    for phrase in REQUIRED_BOUNDARY_PHRASES:
        assert phrase in section


def test_routing_rejection_deferral_sections_in_markdown() -> None:
    md = render_md()
    assert "## 8. Rejection and Deferral Paths" in md
    assert "### Rejection paths" in md
    assert "### Deferral paths" in md
    assert "## 9. Return-to-Remediation Routing" in md
    lower = md.lower()
    assert "rejection path" in lower
    assert "deferral path" in lower


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


def test_regression_sprint154_packet_still_valid() -> None:
    p154 = build_sprint154()
    assert p154["sprint_number"] == 154
    assert p154["preview_only"] is True
    assert p154["no_execution"] is True
    assert p154["no_activation"] is True
    assert p154["no_runnable_plan"] is True
    for key, value in p154.items():
        if key.startswith("actual_"):
            assert value == 0, key
    md154 = render_sprint154_md()
    assert "## 1. purpose" in md154.lower()
    assert "sprint 153" in md154.lower()


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
