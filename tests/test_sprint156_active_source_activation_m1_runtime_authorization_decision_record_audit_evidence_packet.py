"""Sprint 156: M1 runtime authorization decision record & audit evidence packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT156_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_runtime_authorization_decision_record_audit_evidence_packet_service"
)
sprint156_pkt = importlib.import_module(_SPRINT156_MOD)
build_pkt = (
    sprint156_pkt.build_active_source_activation_m1_runtime_authorization_decision_record_audit_evidence_packet
)
render_md = (
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

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m1_runtime_authorization_decision_record_audit_evidence_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After Sprint 155",
    "## 3. Runtime Authorization Decision Record Objective",
    "## 4. Decision Record Field Model",
    "## 5. Required Audit Evidence Artifacts",
    "## 6. Approval Evidence Requirements",
    "## 7. Denial Evidence Requirements",
    "## 8. Deferral Evidence Requirements",
    "## 9. Evidence Retention and Export Expectations",
    "## 10. No-Execution Default",
    "## 11. Runtime Authorization Boundary",
    "## 12. What Sprint 156 Does Not Build",
    "## 13. Exit Criteria",
    "## 14. Risks and Mitigations",
    "## 15. Recommended Next Safe Action",
)

REQUIRED_DECISION_RECORD_FIELDS = (
    "Decision record identifier",
    "Related sprint chain",
    "Requested runtime scope",
    "Requested implementation slice",
    "Decision type",
    "Decision status",
    "Decision date placeholder",
    "Human approver placeholder",
    "Evidence docket reference",
    "Denial condition review reference",
    "Risk acceptance reference",
    "Runtime boundary acknowledgement",
    "Blocked-action acknowledgement",
    "Audit export reference",
    "Follow-up action reference",
)

REQUIRED_AUDIT_ARTIFACT_SUBSTRINGS = (
    "Sprint 155 evidence closure packet reference",
    "Sprint 154 remediation queue packet reference",
    "Sprint 153 post-board routing packet reference",
    "Human review record",
    "Security review record",
    "Sovereignty and trust review record",
    "Customer validation record",
    "Rollback and support record",
    "Data handling and export record",
    "Runtime boundary acknowledgement",
    "Written approval placeholder",
    "Denial or deferral rationale placeholder",
)

REQUIRED_APPROVAL_EVIDENCE = (
    "Approval evidence is not runtime authorization by itself.",
    "Written human approval must be separate and explicit.",
    "Runtime scope must be bounded.",
    "Customer data access must remain blocked unless separately approved.",
    "Source activation must remain blocked unless separately approved.",
    "Production activation must remain blocked unless separately approved.",
    "Pilot launch must remain blocked unless separately approved.",
    "Database migration must remain blocked unless separately approved.",
)

REQUIRED_BOUNDARY_PHRASES = (
    "Decision record template assembly is not runtime authorization.",
    "Audit evidence checklist emission is not approval.",
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
        "no decision record execution",
        "no audit evidence execution",
    ):
        assert phrase in src


def test_packet_sprint_and_flags() -> None:
    pkt = build_pkt()
    assert pkt["sprint_number"] == 156
    assert pkt["artifact_type"] == (
        "nf_active_source_activation_m1_runtime_authorization_decision_record_audit_evidence_packet_v1"
    )
    assert pkt["packet_name"] == (
        "NativeForge M1 Runtime Authorization Decision Record & Audit Evidence Packet"
    )
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True


def test_prerequisite_sprint155_re_review_readiness_evidence_closure_packet() -> None:
    pkt = build_pkt()
    assert pkt["prerequisite_re_review_board_readiness_evidence_closure_sprint"] == 155
    assert (
        pkt["prerequisite_re_review_board_readiness_evidence_closure_artifact_type"]
        == "nf_active_source_activation_m1_re_review_board_readiness_evidence_closure_packet_v1"
    )


def test_verification_path_includes_sprint155_and_sprint154_artifact_types() -> None:
    pkt = build_pkt()
    assert pkt["verification_path_re_review_board_readiness_evidence_closure_sprint"] == 155
    assert (
        pkt["verification_path_re_review_board_readiness_evidence_closure_artifact_type"]
        == "nf_active_source_activation_m1_re_review_board_readiness_evidence_closure_packet_v1"
    )
    assert pkt["verification_path_evidence_remediation_queue_re_review_sprint"] == 154
    assert (
        pkt["verification_path_evidence_remediation_queue_re_review_artifact_type"]
        == "nf_active_source_activation_m1_evidence_remediation_queue_re_review_packet_v1"
    )


def test_packet_actual_counts_zero() -> None:
    pkt = build_pkt()
    for key, value in pkt.items():
        if key.startswith("actual_"):
            assert value == 0, key


def test_outreach_scheduling_remediation_closure_board_decision_audit_counters_zero() -> None:
    pkt = build_pkt()
    assert pkt["actual_customer_outreach_attempts"] == 0
    assert pkt["actual_interviews_scheduled"] == 0
    assert pkt["actual_remediation_executions"] == 0
    assert pkt["actual_evidence_closure_executions"] == 0
    assert pkt["actual_re_review_board_convened"] == 0
    assert pkt["actual_decision_record_executions"] == 0
    assert pkt["actual_audit_evidence_executions"] == 0


def test_decision_record_field_model_includes_all_required_fields() -> None:
    pkt = build_pkt()
    names = [row["field_name"] for row in pkt["decision_record_field_model"]]
    for label in REQUIRED_DECISION_RECORD_FIELDS:
        assert label in names


def test_required_audit_evidence_artifacts_include_all_required() -> None:
    pkt = build_pkt()
    joined = "\n".join(pkt["required_audit_evidence_artifacts"])
    for sub in REQUIRED_AUDIT_ARTIFACT_SUBSTRINGS:
        assert sub in joined


def test_approval_evidence_requirements_include_all_boundary_statements() -> None:
    pkt = build_pkt()
    reqs = list(pkt["approval_evidence_requirements"])
    for phrase in REQUIRED_APPROVAL_EVIDENCE:
        assert phrase in reqs


def test_denial_evidence_requirements_present() -> None:
    pkt = build_pkt()
    joined = "\n".join(pkt["denial_evidence_requirements"]).lower()
    assert "denial" in joined
    assert "no runtime authorization granted" in joined


def test_deferral_evidence_requirements_present() -> None:
    pkt = build_pkt()
    joined = "\n".join(pkt["deferral_evidence_requirements"]).lower()
    assert "deferral" in joined
    assert "sprint 155" in joined


def test_evidence_retention_and_export_expectations_present() -> None:
    pkt = build_pkt()
    joined = "\n".join(pkt["evidence_retention_and_export_expectations"]).lower()
    assert "retention" in joined
    assert "export" in joined


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
    assert "no decision record execution" in joined
    assert "no audit evidence execution" in joined
    assert "no re-review board convened" in joined


def test_sprint156_does_not_build_required_phrases() -> None:
    pkt = build_pkt()
    items = [x.lower() for x in pkt["sprint_156_does_not_build"]]
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
        "no runnable implementation workflow",
    ):
        assert phrase in items


def test_recommended_next_safe_action_recommendation_only() -> None:
    pkt = build_pkt()
    step = (pkt.get("recommended_next_safe_action") or "").lower()
    assert "recommendation-only" in step or "recommendation only" in step


def test_markdown_required_section_headers_in_order() -> None:
    md = render_md()
    assert md.startswith(
        "# NativeForge M1 Runtime Authorization Decision Record & Audit Evidence Packet v1\n"
    )
    positions = [md.index(h) for h in REQUIRED_SECTION_HEADERS]
    assert positions == sorted(positions)


def test_markdown_prerequisite_sprint155_re_review_evidence_closure_packet() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 155" in lower
    assert "re-review" in lower or "re review" in lower
    assert "evidence closure" in lower
    assert (
        "nf_active_source_activation_m1_re_review_board_readiness_evidence_closure_packet_v1"
        in md
    )


def test_markdown_no_execution_default_section() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 10. no-execution default" in lower
    assert "no-execution default" in lower
    assert "no decision record execution" in lower
    assert "no audit evidence execution" in lower


def test_markdown_runtime_authorization_boundary_language() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 11. runtime authorization boundary" in lower
    assert "runtime authorization boundary" in lower


def test_markdown_what_sprint156_does_not_build_lists_required_exclusions() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 12. what sprint 156 does not build" in lower
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
        "no runnable implementation workflow",
    ):
        assert phrase in lower


def test_markdown_blocked_action_rules_required_statements() -> None:
    md = render_md()
    sec_start = md.index("## 11. Runtime Authorization Boundary")
    sec_end = md.index("## 12. What Sprint 156 Does Not Build")
    section = md[sec_start:sec_end]
    for phrase in REQUIRED_BOUNDARY_PHRASES:
        assert phrase in section


def test_markdown_denial_deferral_retention_sections() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 7. denial evidence requirements" in lower
    assert "## 8. deferral evidence requirements" in lower
    assert "## 9. evidence retention and export expectations" in lower
    assert "denial evidence" in lower
    assert "deferral evidence" in lower
    assert "retention" in lower


def test_markdown_verification_path_regression_sprint155_sprint154() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 155" in lower
    assert "sprint 154" in lower


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
