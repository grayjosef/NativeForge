"""Sprint 117: M0 demo build execution packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from nativeforge.services.active_source_activation_m0_demo_build_execution_packet_service import (
    M0_DEMO_BUILD_SEQUENCE_ORDER,
    build_active_source_activation_m0_demo_build_execution_packet,
    render_active_source_activation_m0_demo_build_execution_packet_markdown,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m0_demo_build_execution_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Source Thesis",
    "## 3. M0 Demo Objective",
    "## 4. M0 Demo Narrative",
    "## 5. M0 Build Sequence",
    "## 6. Feature Acceptance Criteria",
    "## 7. Demo-Safe Data Rules",
    "## 8. Human Review Gates",
    "## 9. Sovereignty Guardrails",
    "## 10. What Sprint 117 Does Not Build",
    "## 11. M0 Exit Criteria",
    "## 12. Risks and Mitigations",
    "## 13. Sprint 118 Recommended Next Step",
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


def test_packet_sprint_and_flags() -> None:
    pkt = build_active_source_activation_m0_demo_build_execution_packet()
    assert pkt["sprint_number"] == 117
    assert pkt["packet_name"] == "NativeForge M0 Demo Build Execution Packet"
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True
    assert pkt["may_define_m0_demo_scope"] is True
    assert pkt["may_define_acceptance_criteria"] is True
    assert pkt["may_define_guardrails"] is True
    assert pkt["may_define_sequencing"] is True


def test_packet_actual_counts_zero() -> None:
    pkt = build_active_source_activation_m0_demo_build_execution_packet()
    assert pkt["actual_external_calls"] == 0
    assert pkt["actual_source_ingestions"] == 0
    assert pkt["actual_ai_generations"] == 0
    assert pkt["actual_form_submissions"] == 0
    assert pkt["actual_customer_data_access"] == 0
    assert pkt["actual_runtime_writes"] == 0


def test_m0_feature_order_matches_required_priority() -> None:
    pkt = build_active_source_activation_m0_demo_build_execution_packet()
    assert pkt["m0_build_sequence"] == list(M0_DEMO_BUILD_SEQUENCE_ORDER)
    titles = [f["title"] for f in pkt["m0_demo_features"]]
    assert titles == list(M0_DEMO_BUILD_SEQUENCE_ORDER)


def test_each_m0_feature_has_at_least_three_acceptance_criteria() -> None:
    pkt = build_active_source_activation_m0_demo_build_execution_packet()
    for feat in pkt["m0_demo_features"]:
        crit = feat["acceptance_criteria"]
        assert isinstance(crit, list)
        assert len(crit) >= 3


def test_at_least_eight_risks_documented() -> None:
    pkt = build_active_source_activation_m0_demo_build_execution_packet()
    assert len(pkt["risks_and_mitigations"]) >= 8


def test_markdown_required_section_headers() -> None:
    md = render_active_source_activation_m0_demo_build_execution_packet_markdown()
    assert md.startswith("# NativeForge M0 Demo Build Execution Packet v1\n")
    for h in REQUIRED_SECTION_HEADERS:
        assert h in md


def test_markdown_demo_safe_restrictions() -> None:
    md = render_active_source_activation_m0_demo_build_execution_packet_markdown()
    assert "seeded" in md.lower() or "demo-safe" in md.lower()
    assert "no real customer data" in md
    assert "no live API pulls" in md
    assert "no scraped sources" in md
    assert "no production tribal data" in md
    assert "no AI vendor calls" in md


def test_markdown_human_review_gate_language() -> None:
    md = render_active_source_activation_m0_demo_build_execution_packet_markdown()
    assert "AI draft preview cannot be marked final without human approval" in md
    assert "Form autofill preview cannot be marked final without human approval" in md
    assert "Eligibility recommendation must be reviewable and overrideable" in md
    assert "Submission status cannot be marked submitted by automation" in md
    assert "Any ambiguous eligibility must be flagged for human review" in md


def test_markdown_sovereignty_guardrails() -> None:
    md = render_active_source_activation_m0_demo_build_execution_packet_markdown()
    assert "tribe owns its data" in md
    assert "no model training on customer data without explicit written consent" in md
    assert "full export path required before pilot readiness" in md
    assert "audit logs required before pilot readiness" in md
    assert "private deployment remains future M3, not M0" in md
    assert "M0 must include policy page or trust explainer" in md


def test_markdown_no_live_grants_gov_ingestion() -> None:
    md = render_active_source_activation_m0_demo_build_execution_packet_markdown()
    assert "no live grants.gov ingestion" in md.lower()


def test_markdown_sprint118_organizational_entity_profile_planning() -> None:
    md = render_active_source_activation_m0_demo_build_execution_packet_markdown()
    assert "sprint 118" in md.lower()
    assert "organizational entity profile" in md.lower()
    assert "preview-only" in md.lower()
    assert "demo-safe" in md.lower()
    assert "explicitly authorizes" in md.lower()


def test_deterministic_packet_and_markdown() -> None:
    a = build_active_source_activation_m0_demo_build_execution_packet()
    b = build_active_source_activation_m0_demo_build_execution_packet()
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    md_a = render_active_source_activation_m0_demo_build_execution_packet_markdown(a)
    md_b = render_active_source_activation_m0_demo_build_execution_packet_markdown(b)
    assert md_a == md_b


def test_render_without_argument_matches_explicit_packet() -> None:
    pkt = build_active_source_activation_m0_demo_build_execution_packet()
    assert (
        render_active_source_activation_m0_demo_build_execution_packet_markdown()
        == render_active_source_activation_m0_demo_build_execution_packet_markdown(pkt)
    )
