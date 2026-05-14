"""Sprint 145: M1 lessons learned & post-pilot optimization packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT145_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_lessons_learned_post_pilot_optimization_packet_service"
)
sprint145_pkt = importlib.import_module(_SPRINT145_MOD)
build_pkt = sprint145_pkt.build_active_source_activation_m1_lessons_learned_post_pilot_optimization_packet
render_md = (
    sprint145_pkt.render_active_source_activation_m1_lessons_learned_post_pilot_optimization_packet_markdown
)

_SPRINT144_MOD = (
    "nativeforge.services.active_source_activation_m1_pilot_metrics_closeout_reporting_packet_service"
)
sprint144_pkt = importlib.import_module(_SPRINT144_MOD)
build_sprint144 = sprint144_pkt.build_active_source_activation_m1_pilot_metrics_closeout_reporting_packet
render_sprint144_md = (
    sprint144_pkt.render_active_source_activation_m1_pilot_metrics_closeout_reporting_packet_markdown
)

_SPRINT143_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_pilot_operational_launch_simulation_packet_service"
)
sprint143_pkt = importlib.import_module(_SPRINT143_MOD)
build_sprint143 = sprint143_pkt.build_active_source_activation_m1_pilot_operational_launch_simulation_packet
render_sprint143_md = (
    sprint143_pkt.render_active_source_activation_m1_pilot_operational_launch_simulation_packet_markdown
)

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m1_lessons_learned_post_pilot_optimization_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After Sprint 144",
    "## 3. Lessons Learned Objective",
    "## 4. Required Evidence Inputs",
    "## 5. Lessons Learned Capture Model",
    "## 6. Post-Pilot Review Structure",
    "## 7. Optimization Backlog Framework",
    "## 8. Improvement Recommendation Rules",
    "## 9. Deferred Item and Exception Handling",
    "## 10. Human Review and Approval Requirements",
    "## 11. Sovereignty, Trust, and Data Handling Constraints",
    "## 12. What Sprint 145 Does Not Build",
    "## 13. Exit Criteria",
    "## 14. Risks and Mitigations",
    "## 15. Recommended Next Phase Decision",
)

EXPECTED_LESSONS_DOMAINS = (
    "Operator workflow friction",
    "Evidence quality gaps",
    "Human gate effectiveness",
    "Deferred item patterns",
    "Sovereignty and trust concerns",
    "Support and escalation findings",
    "Rollback rehearsal findings",
    "Monitoring and evidence capture findings",
    "Documentation clarity findings",
    "User or pilot stakeholder feedback placeholders",
)

EXPECTED_REVIEW_SECTIONS = (
    "Executive summary",
    "Evidence reviewed",
    "Metrics reviewed",
    "Gates completed",
    "Gates blocked",
    "Deferred items",
    "Risk findings",
    "Sovereignty and trust findings",
    "Operator findings",
    "Recommended optimizations",
    "Required human approvals before any next phase",
)

EXPECTED_BACKLOG_CATEGORIES = (
    "Must fix before runtime expansion",
    "Should fix before next pilot",
    "Nice to have",
    "Requires tribal/customer validation",
    "Requires security or sovereignty review",
    "Requires pricing or support model review",
    "Deferred with rationale",
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


def test_service_source_rejects_runtime_launch_activation_collection_closeout_optimization() -> (
    None
):
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
    ):
        assert phrase in src


def test_packet_sprint_and_flags() -> None:
    pkt = build_pkt()
    assert pkt["sprint_number"] == 145
    assert pkt["artifact_type"] == (
        "nf_active_source_activation_m1_lessons_learned_post_pilot_optimization_packet_v1"
    )
    assert pkt["packet_name"] == "NativeForge M1 Lessons Learned & Post-Pilot Optimization Packet"
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True
    assert pkt["may_define_lessons_learned_capture_model_preview_only"] is True
    assert pkt["may_define_post_pilot_review_structure_preview_only"] is True
    assert pkt["may_define_optimization_backlog_framework_preview_only"] is True


def test_prerequisite_sprint144_metrics_closeout_reporting_packet() -> None:
    pkt = build_pkt()
    assert pkt["prerequisite_metrics_closeout_reporting_sprint"] == 144
    assert (
        pkt["prerequisite_metrics_closeout_reporting_artifact_type"]
        == "nf_active_source_activation_m1_pilot_metrics_closeout_reporting_packet_v1"
    )


def test_verification_path_includes_sprint143_sprint142_sprint141_artifact_types() -> None:
    pkt = build_pkt()
    assert (
        pkt["verification_path_operational_launch_simulation_artifact_type"]
        == "nf_active_source_activation_m1_pilot_operational_launch_simulation_packet_v1"
    )
    assert (
        pkt["verification_path_pre_launch_checklist_artifact_type"]
        == "nf_active_source_activation_m1_pilot_implementation_pre_launch_checklist_packet_v1"
    )
    assert (
        pkt["verification_path_authorization_review_artifact_type"]
        == "nf_active_source_activation_m1_controlled_build_authorization_review_packet_v1"
    )


def test_packet_actual_counts_zero() -> None:
    pkt = build_pkt()
    for key, value in pkt.items():
        if key.startswith("actual_"):
            assert value == 0, key


def test_ten_lessons_learned_capture_domains() -> None:
    pkt = build_pkt()
    rows = pkt["lessons_learned_capture_model"]
    assert len(rows) == 10
    names = [r["capture_domain"] for r in rows]
    for expected in EXPECTED_LESSONS_DOMAINS:
        assert expected in names


def test_lessons_domain_disclaimers_reject_launch_onboarding_activation() -> None:
    pkt = build_pkt()
    disclaimer_phrases = (
        "not pilot launch",
        "not customer onboarding",
        "not source activation",
        "not production activation",
    )
    u = (pkt.get("lessons_learned_domain_universal_disclaimer") or "").lower()
    for needle in disclaimer_phrases:
        assert needle in u
    for r in pkt["lessons_learned_capture_model"]:
        d = (r.get("capture_focus") or "").lower()
        for needle in disclaimer_phrases:
            assert needle in d


def test_eleven_post_pilot_review_sections() -> None:
    pkt = build_pkt()
    rows = pkt["post_pilot_review_structure"]
    assert len(rows) == 11
    names = [r["section"] for r in rows]
    for expected in EXPECTED_REVIEW_SECTIONS:
        assert expected in names


def test_seven_optimization_backlog_categories() -> None:
    pkt = build_pkt()
    rows = pkt["optimization_backlog_framework"]
    assert len(rows) == 7
    names = [r["category"] for r in rows]
    for expected in EXPECTED_BACKLOG_CATEGORIES:
        assert expected in names


def test_five_required_evidence_inputs_reference_sprint144_and_verification_chain() -> None:
    pkt = build_pkt()
    ev = pkt["required_evidence_inputs"]
    assert len(ev) == 5
    text = json.dumps(ev).lower()
    assert "sprint 144" in text
    assert "sprint 143" in text
    assert "nf_active_source_activation_m1_pilot_metrics_closeout_reporting_packet_v1" in text
    assert "nf_active_source_activation_m1_pilot_operational_launch_simulation_packet_v1" in text


def test_human_review_and_approval_requirements_explicit() -> None:
    pkt = build_pkt()
    joined = " ".join(pkt["human_review_and_approval_requirements"]).lower()
    assert "human operator approval" in joined
    assert "human-authored" in joined or "human authored" in joined


def test_sprint145_does_not_build_required_phrases() -> None:
    pkt = build_pkt()
    items = [x.lower() for x in pkt["sprint_145_does_not_build"]]
    assert "no pilot launch" in items
    assert "no customer onboarding" in items
    assert "no customer data access" in items
    assert "no database migration" in items
    assert "no source activation" in items
    assert "no production activation" in items
    assert "no real metric collection" in items
    assert "no real pilot closeout" in items
    assert "no optimization execution" in items
    assert "no runnable implementation workflow" in items


def test_markdown_what_sprint145_does_not_build_lists_required_exclusions() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 12. what sprint 145 does not build" in lower
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
        "no runnable implementation workflow",
    ):
        assert phrase in lower


def test_recommended_next_phase_decision_recommendation_only() -> None:
    pkt = build_pkt()
    step = (pkt.get("recommended_next_phase_decision") or "").lower()
    assert "recommendation-only" in step or "recommendation only" in step


def test_markdown_required_section_headers_in_order() -> None:
    md = render_md()
    assert md.startswith("# NativeForge M1 Lessons Learned & Post-Pilot Optimization Packet v1\n")
    positions = [md.index(h) for h in REQUIRED_SECTION_HEADERS]
    assert positions == sorted(positions)


def test_markdown_prerequisite_sprint144_and_sequencing() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 144" in lower
    assert "metrics and closeout" in lower or "closeout reporting" in lower
    assert "sprint 145" in lower


def test_markdown_sovereignty_trust_constraints_section() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 11. sovereignty, trust, and data handling constraints" in lower
    assert "customer owns its data" in lower


def test_markdown_explicit_human_approval_language() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 10. human review and approval requirements" in lower
    assert "human operator approval" in lower


def test_markdown_recommended_next_phase_header() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 15. recommended next phase decision" in lower


def test_markdown_lessons_learned_capture_model_contains_required_domains() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 5. lessons learned capture model" in lower
    for label in (
        "operator workflow friction",
        "evidence quality gaps",
        "human gate effectiveness",
        "deferred item patterns",
        "sovereignty and trust concerns",
        "support and escalation findings",
        "rollback rehearsal findings",
        "monitoring and evidence capture findings",
        "documentation clarity findings",
        "user or pilot stakeholder feedback placeholders",
    ):
        assert label in lower


def test_markdown_post_pilot_review_structure_contains_required_sections() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 6. post-pilot review structure" in lower
    assert "executive summary" in lower
    assert "evidence reviewed" in lower
    assert "metrics reviewed" in lower
    assert "gates completed" in lower
    assert "gates blocked" in lower
    assert "deferred items" in lower
    assert "risk findings" in lower
    assert "sovereignty and trust findings" in lower
    assert "operator findings" in lower
    assert "recommended optimizations" in lower
    assert "required human approvals before any next phase" in lower


def test_markdown_optimization_backlog_contains_required_categories() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 7. optimization backlog framework" in lower
    assert "must fix before runtime expansion" in lower
    assert "should fix before next pilot" in lower
    assert "nice to have" in lower
    assert "requires tribal/customer validation" in lower
    assert "requires security or sovereignty review" in lower
    assert "requires pricing or support model review" in lower
    assert "deferred with rationale" in lower


def test_markdown_regression_sprint143_sprint142_verification_path() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 141" in lower
    assert "sprint 140" in lower
    assert "demo-to-build" in lower or "demo to build" in lower
    assert "131" in lower and "139" in lower


def test_markdown_improvement_recommendation_rules_forbid_execution_paths() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 8. improvement recommendation rules" in lower
    assert "database migration" in lower
    assert "optimization execution" in lower


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


def test_regression_sprint144_packet_still_valid() -> None:
    p144 = build_sprint144()
    assert p144["sprint_number"] == 144
    assert p144["preview_only"] is True
    assert p144["no_execution"] is True
    assert p144["no_activation"] is True
    assert p144["no_runnable_plan"] is True
    for key, value in p144.items():
        if key.startswith("actual_"):
            assert value == 0, key
    md144 = render_sprint144_md()
    assert "## 1. purpose" in md144.lower()
    assert "sprint 143" in md144.lower()


def test_regression_sprint143_packet_still_valid() -> None:
    p143 = build_sprint143()
    assert p143["sprint_number"] == 143
    assert p143["preview_only"] is True
    assert p143["no_execution"] is True
    assert p143["no_activation"] is True
    assert p143["no_runnable_plan"] is True
    for key, value in p143.items():
        if key.startswith("actual_"):
            assert value == 0, key
    md143 = render_sprint143_md()
    assert "## 1. purpose" in md143.lower()
    assert "sprint 142" in md143.lower()
