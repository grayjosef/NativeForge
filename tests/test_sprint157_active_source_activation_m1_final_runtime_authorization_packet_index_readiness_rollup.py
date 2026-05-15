"""Sprint 157: M1 final runtime authorization packet index & readiness rollup (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT157_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_final_runtime_authorization_packet_index_readiness_rollup_service"
)
sprint157_pkt = importlib.import_module(_SPRINT157_MOD)
build_pkt = (
    sprint157_pkt.build_active_source_activation_m1_final_runtime_authorization_packet_index_readiness_rollup
)
render_md = (
    sprint157_pkt.render_active_source_activation_m1_final_runtime_authorization_packet_index_readiness_rollup_markdown
)

_SPRINT156_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_runtime_authorization_decision_record_audit_evidence_packet_service"
)
sprint156_pkt = importlib.import_module(_SPRINT156_MOD)
build_sprint156 = (
    sprint156_pkt.build_active_source_activation_m1_runtime_authorization_decision_record_audit_evidence_packet
)
render_sprint156_md = (
    sprint156_pkt.render_active_source_activation_m1_runtime_authorization_decision_record_audit_evidence_packet_markdown
)

_SPRINT155_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_re_review_board_readiness_evidence_closure_packet_service"
)
sprint155_pkt = importlib.import_module(_SPRINT155_MOD)
build_sprint155 = (
    sprint155_pkt.build_active_source_activation_m1_re_review_board_readiness_evidence_closure_packet
)
render_sprint155_md = (
    sprint155_pkt.render_active_source_activation_m1_re_review_board_readiness_evidence_closure_packet_markdown
)

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m1_final_runtime_authorization_packet_index_readiness_rollup_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After Sprint 156",
    "## 3. Final Runtime Authorization Packet Index Objective",
    "## 4. Packet Chain Index",
    "## 5. Readiness Rollup Model",
    "## 6. Evidence Coverage Summary",
    "## 7. Blocked Action Rollup",
    "## 8. Human Review Dependency Summary",
    "## 9. Decision Record and Audit Evidence Summary",
    "## 10. No-Execution Default",
    "## 11. Runtime Authorization Boundary",
    "## 12. What Sprint 157 Does Not Build",
    "## 13. Exit Criteria",
    "## 14. Risks and Mitigations",
    "## 15. Recommended Next Safe Action",
)

RECHAIN_ARTIFACTS_149_156 = (
    "nf_active_source_activation_m1_technical_architecture_review_runtime_boundary_packet_v1",
    "nf_active_source_activation_m1_bounded_implementation_design_human_gate_packet_v1",
    "nf_active_source_activation_m1_runtime_authorization_review_readiness_no_execution_packet_v1",
    "nf_active_source_activation_m1_human_runtime_authorization_board_packet_v1",
    "nf_active_source_activation_m1_post_board_decision_routing_next_safe_action_packet_v1",
    "nf_active_source_activation_m1_evidence_remediation_queue_re_review_packet_v1",
    "nf_active_source_activation_m1_re_review_board_readiness_evidence_closure_packet_v1",
    "nf_active_source_activation_m1_runtime_authorization_decision_record_audit_evidence_packet_v1",
)

READINESS_CATEGORIES = (
    "Technical architecture boundary readiness",
    "Bounded implementation design readiness",
    "Runtime authorization review readiness",
    "Human board review readiness",
    "Post-board decision routing readiness",
    "Evidence remediation readiness",
    "Re-review and evidence closure readiness",
    "Decision record and audit evidence readiness",
    "Human approval dependency",
    "Runtime authorization remains blocked",
)

EVIDENCE_PLACEHOLDERS = (
    "Security review evidence placeholder",
    "Sovereignty and trust evidence placeholder",
    "Customer validation evidence placeholder",
    "Technical architecture evidence placeholder",
    "Rollback and support evidence placeholder",
    "Data handling and export evidence placeholder",
    "Human approval evidence placeholder",
    "Denial and deferral evidence placeholder",
    "Audit export evidence placeholder",
    "Decision record evidence placeholder",
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
    ):
        assert phrase in src


def test_packet_sprint_and_flags() -> None:
    pkt = build_pkt()
    assert pkt["sprint_number"] == 157
    assert pkt["artifact_type"] == (
        "nf_active_source_activation_m1_final_runtime_authorization_packet_index_readiness_rollup_v1"
    )
    assert pkt["packet_name"] == (
        "NativeForge M1 Final Runtime Authorization Packet Index & Readiness Rollup"
    )
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True


def test_prerequisite_sprint156_runtime_authorization_decision_record_audit_evidence_packet() -> (
    None
):
    pkt = build_pkt()
    assert pkt["prerequisite_runtime_authorization_decision_record_audit_evidence_sprint"] == 156
    assert (
        pkt["prerequisite_runtime_authorization_decision_record_audit_evidence_artifact_type"]
        == "nf_active_source_activation_m1_runtime_authorization_decision_record_audit_evidence_packet_v1"
    )


def test_verification_path_includes_sprint156_and_sprint155_artifact_types() -> None:
    pkt = build_pkt()
    assert pkt["verification_path_runtime_authorization_decision_record_audit_evidence_sprint"] == 156
    assert (
        pkt["verification_path_runtime_authorization_decision_record_audit_evidence_artifact_type"]
        == "nf_active_source_activation_m1_runtime_authorization_decision_record_audit_evidence_packet_v1"
    )
    assert pkt["verification_path_re_review_board_readiness_evidence_closure_sprint"] == 155
    assert (
        pkt["verification_path_re_review_board_readiness_evidence_closure_artifact_type"]
        == "nf_active_source_activation_m1_re_review_board_readiness_evidence_closure_packet_v1"
    )


def test_packet_actual_counts_zero() -> None:
    pkt = build_pkt()
    for key, value in pkt.items():
        if key.startswith("actual_"):
            assert value == 0, key


def test_packet_chain_includes_sprints_149_through_156() -> None:
    pkt = build_pkt()
    nums = sorted(row["sprint_number"] for row in pkt["packet_chain_index"])
    assert nums == [149, 150, 151, 152, 153, 154, 155, 156]
    joined = json.dumps(pkt["packet_chain_index"], sort_keys=True)
    for at in RECHAIN_ARTIFACTS_149_156:
        assert at in joined


def test_readiness_rollup_model_includes_all_categories() -> None:
    pkt = build_pkt()
    cats = [row["readiness_category"] for row in pkt["readiness_rollup_model"]]
    for label in READINESS_CATEGORIES:
        assert label in cats


def test_evidence_coverage_summary_includes_all_placeholders() -> None:
    pkt = build_pkt()
    items = list(pkt["evidence_coverage_summary"])
    for label in EVIDENCE_PLACEHOLDERS:
        assert label in items


def test_human_review_dependency_summary_present() -> None:
    pkt = build_pkt()
    joined = "\n".join(pkt["human_review_dependency_summary"]).lower()
    assert "human review dependency" in joined


def test_decision_record_and_audit_evidence_summary_present() -> None:
    pkt = build_pkt()
    joined = "\n".join(pkt["decision_record_and_audit_evidence_summary"]).lower()
    assert "decision record and audit evidence summary" in joined
    assert "sprint 156" in joined
    assert (
        "nf_active_source_activation_m1_runtime_authorization_decision_record_audit_evidence_packet_v1"
        in joined
    )


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


def test_sprint157_does_not_build_required_phrases() -> None:
    pkt = build_pkt()
    items = [x.lower() for x in pkt["sprint_157_does_not_build"]]
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
        "# NativeForge M1 Final Runtime Authorization Packet Index & Readiness Rollup v1\n"
    )
    positions = [md.index(h) for h in REQUIRED_SECTION_HEADERS]
    assert positions == sorted(positions)


def test_markdown_prerequisite_sprint156_decision_record_audit_packet() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 156" in lower
    assert (
        "nf_active_source_activation_m1_runtime_authorization_decision_record_audit_evidence_packet_v1"
        in md
    )


def test_markdown_no_execution_default_section() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 10. no-execution default" in lower
    assert "no-execution default" in lower
    assert "no packet-chain execution" in lower


def test_markdown_runtime_authorization_boundary_language() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 11. runtime authorization boundary" in lower
    assert "runtime authorization boundary" in lower


def test_markdown_what_sprint157_does_not_build_lists_required_exclusions() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 12. what sprint 157 does not build" in lower
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
        "no runnable implementation workflow",
    ):
        assert phrase in lower


def test_markdown_human_review_and_decision_record_sections() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 8. human review dependency summary" in lower
    assert "## 9. decision record and audit evidence summary" in lower
    assert "human review dependency" in lower
    assert "decision record and audit evidence summary" in lower


def test_markdown_verification_path_regression_sprint156_sprint155() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 156" in lower
    assert "sprint 155" in lower


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


def test_regression_sprint156_packet_still_valid() -> None:
    p156 = build_sprint156()
    assert p156["sprint_number"] == 156
    assert p156["preview_only"] is True
    assert p156["no_execution"] is True
    assert p156["no_activation"] is True
    assert p156["no_runnable_plan"] is True
    for key, value in p156.items():
        if key.startswith("actual_"):
            assert value == 0, key
    md156 = render_sprint156_md()
    assert "## 1. purpose" in md156.lower()
    assert "sprint 155" in md156.lower()


def test_regression_sprint155_packet_still_valid() -> None:
    p155 = build_sprint155()
    assert p155["sprint_number"] == 155
    assert p155["preview_only"] is True
    assert p155["no_execution"] is True
    assert p155["no_activation"] is True
    assert p155["no_runnable_plan"] is True
    for key, value in p155.items():
        if key.startswith("actual_"):
            assert value == 0, key
    md155 = render_sprint155_md()
    assert "## 1. purpose" in md155.lower()
    assert "sprint 154" in md155.lower()
