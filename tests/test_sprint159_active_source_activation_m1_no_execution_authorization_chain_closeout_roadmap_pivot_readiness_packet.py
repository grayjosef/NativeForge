"""Sprint 159: M1 no-execution authorization chain closeout & roadmap pivot readiness (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT159_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_no_execution_authorization_chain_closeout_"
    "roadmap_pivot_readiness_packet_service"
)
sprint159_pkt = importlib.import_module(_SPRINT159_MOD)
build_pkt = (
    sprint159_pkt.build_active_source_activation_m1_no_execution_authorization_chain_closeout_roadmap_pivot_readiness_packet
)
render_md = (
    sprint159_pkt.render_active_source_activation_m1_no_execution_authorization_chain_closeout_roadmap_pivot_readiness_packet_markdown
)

_SPRINT158_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_human_authorization_handoff_final_no_execution_decision_brief_service"
)
sprint158_pkt = importlib.import_module(_SPRINT158_MOD)
build_sprint158 = (
    sprint158_pkt.build_active_source_activation_m1_human_authorization_handoff_final_no_execution_decision_brief
)
render_sprint158_md = (
    sprint158_pkt.render_active_source_activation_m1_human_authorization_handoff_final_no_execution_decision_brief_markdown
)

_SPRINT157_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_final_runtime_authorization_packet_index_readiness_rollup_service"
)
sprint157_pkt = importlib.import_module(_SPRINT157_MOD)
build_sprint157 = (
    sprint157_pkt.build_active_source_activation_m1_final_runtime_authorization_packet_index_readiness_rollup
)
render_sprint157_md = (
    sprint157_pkt.render_active_source_activation_m1_final_runtime_authorization_packet_index_readiness_rollup_markdown
)

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m1_no_execution_authorization_chain_closeout_roadmap_pivot_readiness_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After Sprint 158",
    "## 3. No-Execution Chain Closeout Objective",
    "## 4. Authorization Chain Closeout Summary",
    "## 5. Roadmap Pivot Options",
    "## 6. Recommended Pivot Decision Criteria",
    "## 7. Evidence and Validation Gap Summary",
    "## 8. Blocked Action Summary",
    "## 9. Human Review Dependency Summary",
    "## 10. No-Execution Default",
    "## 11. Runtime Authorization Boundary",
    "## 12. What Sprint 159 Does Not Build",
    "## 13. Exit Criteria",
    "## 14. Risks and Mitigations",
    "## 15. Recommended Next Safe Action",
)

RECHAIN_ARTIFACTS_149_158 = (
    "nf_active_source_activation_m1_technical_architecture_review_runtime_boundary_packet_v1",
    "nf_active_source_activation_m1_bounded_implementation_design_human_gate_packet_v1",
    "nf_active_source_activation_m1_runtime_authorization_review_readiness_no_execution_packet_v1",
    "nf_active_source_activation_m1_human_runtime_authorization_board_packet_v1",
    "nf_active_source_activation_m1_post_board_decision_routing_next_safe_action_packet_v1",
    "nf_active_source_activation_m1_evidence_remediation_queue_re_review_packet_v1",
    "nf_active_source_activation_m1_re_review_board_readiness_evidence_closure_packet_v1",
    "nf_active_source_activation_m1_runtime_authorization_decision_record_audit_evidence_packet_v1",
    "nf_active_source_activation_m1_final_runtime_authorization_packet_index_readiness_rollup_v1",
    "nf_active_source_activation_m1_human_authorization_handoff_final_no_execution_decision_brief_v1",
)

ROADMAP_PIVOT_OPTIONS = (
    "Close the authorization chain with no execution",
    "Continue documentation-only planning",
    "Request evidence remediation",
    "Request narrowed-scope review",
    "Request additional security review",
    "Request additional sovereignty and trust review",
    "Request additional customer validation",
    "Realign to M0/M1 product roadmap review",
    "Prepare a separate future authorization process",
    "Maintain no-execution default",
)

PIVOT_DECISION_CRITERIA = (
    "Does the next lane require runtime work?",
    "Does the next lane require customer data access?",
    "Does the next lane require customer outreach?",
    "Does the next lane require source activation?",
    "Does the next lane require production activation?",
    "Does the next lane require database migration?",
    "Does the next lane require pilot launch?",
    "Does the next lane require written human approval?",
    "Does the next lane preserve NativeForge grant discovery as a core product engine?",
    "Does the next lane preserve sovereignty-first data boundaries?",
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
        "no decision record execution",
        "no audit evidence execution",
        "no packet-chain execution",
        "no handoff execution",
        "no roadmap pivot execution",
    ):
        assert phrase in src


def test_packet_sprint_and_flags() -> None:
    pkt = build_pkt()
    assert pkt["sprint_number"] == 159
    assert pkt["artifact_type"] == (
        "nf_active_source_activation_m1_no_execution_authorization_chain_closeout_"
        "roadmap_pivot_readiness_packet_v1"
    )
    assert pkt["packet_name"] == (
        "NativeForge M1 No-Execution Authorization Chain Closeout & "
        "Roadmap Pivot Readiness Packet"
    )
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True


def test_prerequisite_sprint158_human_authorization_handoff_final_no_execution_decision_brief() -> None:
    pkt = build_pkt()
    assert (
        pkt["prerequisite_human_authorization_handoff_final_no_execution_decision_brief_sprint"]
        == 158
    )
    assert (
        pkt["prerequisite_human_authorization_handoff_final_no_execution_decision_brief_artifact_type"]
        == "nf_active_source_activation_m1_human_authorization_handoff_final_no_execution_decision_brief_v1"
    )


def test_verification_path_includes_sprint158_and_sprint157_artifact_types() -> None:
    pkt = build_pkt()
    assert (
        pkt["verification_path_human_authorization_handoff_final_no_execution_decision_brief_sprint"]
        == 158
    )
    assert (
        pkt["verification_path_human_authorization_handoff_final_no_execution_decision_brief_artifact_type"]
        == "nf_active_source_activation_m1_human_authorization_handoff_final_no_execution_decision_brief_v1"
    )
    assert (
        pkt["verification_path_final_runtime_authorization_packet_index_readiness_rollup_sprint"]
        == 157
    )
    assert (
        pkt["verification_path_final_runtime_authorization_packet_index_readiness_rollup_artifact_type"]
        == "nf_active_source_activation_m1_final_runtime_authorization_packet_index_readiness_rollup_v1"
    )


def test_packet_actual_counts_zero() -> None:
    pkt = build_pkt()
    for key, value in pkt.items():
        if key.startswith("actual_"):
            assert value == 0, key


def test_authorization_chain_closeout_includes_sprints_149_through_158() -> None:
    pkt = build_pkt()
    nums = sorted(
        row["sprint_number"] for row in pkt["authorization_chain_closeout_summary"]
    )
    assert nums == [149, 150, 151, 152, 153, 154, 155, 156, 157, 158]
    joined = json.dumps(pkt["authorization_chain_closeout_summary"], sort_keys=True)
    for at in RECHAIN_ARTIFACTS_149_158:
        assert at in joined


def test_roadmap_pivot_options_include_all_required_options() -> None:
    pkt = build_pkt()
    options = list(pkt["roadmap_pivot_options"])
    for label in ROADMAP_PIVOT_OPTIONS:
        assert label in options


def test_recommended_pivot_decision_criteria_include_all_required_criteria() -> None:
    pkt = build_pkt()
    criteria = list(pkt["recommended_pivot_decision_criteria"])
    for label in PIVOT_DECISION_CRITERIA:
        assert label in criteria


def test_evidence_and_validation_gap_summary_present() -> None:
    pkt = build_pkt()
    assert len(pkt["evidence_and_validation_gap_summary"]) >= 1
    joined = json.dumps(pkt["evidence_and_validation_gap_summary"]).lower()
    assert "gap_area" in joined
    assert "gap_status" in joined


def test_blocked_action_summary_present() -> None:
    pkt = build_pkt()
    joined = "\n".join(pkt["blocked_action_summary"]).lower()
    assert "blocked" in joined
    assert "roadmap pivot" in joined


def test_human_review_dependency_summary_present() -> None:
    pkt = build_pkt()
    joined = "\n".join(pkt["human_review_dependency_summary"]).lower()
    assert "human review dependency" in joined
    assert "sprint 158" in joined


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
    assert "no packet-chain execution" in joined
    assert "no roadmap pivot execution" in joined


def test_sprint159_does_not_build_required_phrases() -> None:
    pkt = build_pkt()
    items = [x.lower() for x in pkt["sprint_159_does_not_build"]]
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
        "no decision record execution",
        "no audit evidence execution",
        "no packet-chain execution",
        "no handoff execution",
        "no roadmap pivot execution",
        "no runnable implementation workflow",
    ):
        assert phrase in items


def test_recommended_next_safe_action_recommendation_only_review_only() -> None:
    pkt = build_pkt()
    step = (pkt.get("recommended_next_safe_action") or "").lower()
    assert "recommendation-only" in step or "recommendation only" in step
    assert "review-only" in step or "review only" in step


def test_markdown_required_section_headers_in_order() -> None:
    md = render_md()
    assert md.startswith(
        "# NativeForge M1 No-Execution Authorization Chain Closeout & "
        "Roadmap Pivot Readiness Packet v1\n"
    )
    positions = [md.index(h) for h in REQUIRED_SECTION_HEADERS]
    assert positions == sorted(positions)


def test_markdown_prerequisite_sprint158_human_authorization_handoff_brief() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 158" in lower
    assert (
        "nf_active_source_activation_m1_human_authorization_handoff_final_no_execution_decision_brief_v1"
        in md
    )


def test_markdown_no_execution_default_section() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 10. no-execution default" in lower
    assert "no-execution default" in lower
    assert "no roadmap pivot execution" in lower


def test_markdown_runtime_authorization_boundary_language() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 11. runtime authorization boundary" in lower
    assert "runtime authorization boundary" in lower


def test_markdown_what_sprint159_does_not_build_lists_required_exclusions() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 12. what sprint 159 does not build" in lower
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
        "no decision record execution",
        "no audit evidence execution",
        "no packet-chain execution",
        "no handoff execution",
        "no roadmap pivot execution",
        "no runnable implementation workflow",
    ):
        assert phrase in lower


def test_markdown_roadmap_pivot_and_criteria_sections() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 5. roadmap pivot options" in lower
    assert "## 6. recommended pivot decision criteria" in lower
    for opt in ROADMAP_PIVOT_OPTIONS:
        assert opt.lower() in lower
    for crit in PIVOT_DECISION_CRITERIA:
        assert crit.lower() in lower


def test_markdown_human_review_dependency_section() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 9. human review dependency summary" in lower
    assert "human review dependency" in lower


def test_markdown_verification_path_regression_sprint158_sprint157() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 158" in lower
    assert "sprint 157" in lower


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


def test_regression_sprint158_packet_still_valid() -> None:
    p158 = build_sprint158()
    assert p158["sprint_number"] == 158
    assert p158["preview_only"] is True
    assert p158["no_execution"] is True
    assert p158["no_activation"] is True
    assert p158["no_runnable_plan"] is True
    for key, value in p158.items():
        if key.startswith("actual_"):
            assert value == 0, key
    md158 = render_sprint158_md()
    assert "## 1. purpose" in md158.lower()
    assert "sprint 157" in md158.lower()


def test_regression_sprint157_packet_still_valid() -> None:
    p157 = build_sprint157()
    assert p157["sprint_number"] == 157
    assert p157["preview_only"] is True
    assert p157["no_execution"] is True
    assert p157["no_activation"] is True
    assert p157["no_runnable_plan"] is True
    for key, value in p157.items():
        if key.startswith("actual_"):
            assert value == 0, key
    md157 = render_sprint157_md()
    assert "## 1. purpose" in md157.lower()
    assert "sprint 156" in md157.lower()
