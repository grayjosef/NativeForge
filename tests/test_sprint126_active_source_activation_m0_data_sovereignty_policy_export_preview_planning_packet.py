"""Sprint 126: M0 data sovereignty policy and export preview planning packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT126_MOD = (
    "nativeforge.services."
    "active_source_activation_m0_data_sovereignty_policy_export_preview_planning_packet_service"
)
sprint126_pkt = importlib.import_module(_SPRINT126_MOD)
M0_SOVEREIGNTY_AND_EXPORT_PREVIEW_FOUNDATIONS = sprint126_pkt.M0_SOVEREIGNTY_AND_EXPORT_PREVIEW_FOUNDATIONS
build_pkt = (
    sprint126_pkt.build_active_source_activation_m0_data_sovereignty_policy_export_preview_planning_packet
)
render_md = (
    sprint126_pkt.render_active_source_activation_m0_data_sovereignty_policy_export_preview_planning_packet_markdown
)

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m0_data_sovereignty_policy_export_preview_planning_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After Requirement Checklist Planning",
    "## 3. M0 Sovereignty Preview Objective",
    "## 4. Demo-Safe Sovereignty Rules",
    "## 5. Required Policy Field Groups",
    "## 6. Field-Level Acceptance Criteria",
    "## 7. Sovereignty Preview to M0 Feature Mapping",
    "## 8. Export Preview Rules",
    "## 9. AI Usage and Consent Rules",
    "## 10. Human Review Gates",
    "## 11. Sovereignty and Trust Requirements",
    "## 12. What Sprint 126 Does Not Build",
    "## 13. M0 Exit Criteria for Sovereignty and Export Planning",
    "## 14. Risks and Mitigations",
    "## 15. Sprint 127 Recommended Next Step",
)

EXPECTED_FIELD_GROUP_NAMES = (
    "Customer data ownership statement",
    "No model training without explicit written consent",
    "Export availability statement",
    "Export content categories",
    "Audit log availability statement",
    "Data retention policy preview",
    "Deletion request policy preview",
    "Sensitive identifier handling",
    "User role and access preview",
    "Human review requirement",
    "AI disclosure statement",
    "Source provenance retention",
    "Customer data boundary statement",
    "Private deployment future option",
    "Third-party data sharing restriction",
    "Security and access control preview",
    "Policy acceptance notes",
    "Human correction notes",
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
    pkt = build_pkt()
    assert pkt["sprint_number"] == 126
    assert pkt["packet_name"] == "NativeForge M0 Data Sovereignty Policy and Export Preview Planning Packet"
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True
    assert pkt["may_define_sovereignty_policy_scope"] is True
    assert pkt["may_define_demo_safe_export_fields"] is True
    assert pkt["may_define_acceptance_criteria"] is True
    assert pkt["may_define_guardrails"] is True


def test_packet_actual_counts_zero() -> None:
    pkt = build_pkt()
    assert pkt["actual_external_calls"] == 0
    assert pkt["actual_source_ingestions"] == 0
    assert pkt["actual_api_calls"] == 0
    assert pkt["actual_scrapes"] == 0
    assert pkt["actual_ai_generations"] == 0
    assert pkt["actual_form_submissions"] == 0
    assert pkt["actual_customer_data_access"] == 0
    assert pkt["actual_runtime_writes"] == 0
    assert pkt["actual_exports_created"] == 0
    assert pkt["actual_policy_changes"] == 0
    assert pkt["actual_retention_changes"] == 0


def test_m0_foundations_match_required_ten() -> None:
    pkt = build_pkt()
    assert pkt["m0_sovereignty_and_export_preview_foundations"] == list(
        M0_SOVEREIGNTY_AND_EXPORT_PREVIEW_FOUNDATIONS
    )
    assert len(M0_SOVEREIGNTY_AND_EXPORT_PREVIEW_FOUNDATIONS) == 10


def test_eighteen_policy_field_groups_present() -> None:
    pkt = build_pkt()
    groups = pkt["policy_field_groups"]
    assert len(groups) == 18
    names = [g["name"] for g in groups]
    for expected in EXPECTED_FIELD_GROUP_NAMES:
        assert expected in names


def test_each_field_group_has_at_least_two_acceptance_criteria() -> None:
    pkt = build_pkt()
    for g in pkt["policy_field_groups"]:
        crit = g["acceptance_criteria"]
        assert isinstance(crit, list)
        assert len(crit) >= 2


def test_at_least_eight_risks_documented() -> None:
    pkt = build_pkt()
    assert len(pkt["risks_and_mitigations"]) >= 8


def test_markdown_required_section_headers() -> None:
    md = render_md()
    assert md.startswith(
        "# NativeForge M0 Data Sovereignty Policy and Export Preview Planning Packet v1\n"
    )
    for h in REQUIRED_SECTION_HEADERS:
        assert h in md


def test_markdown_demo_safe_sovereignty_rules() -> None:
    md = render_md()
    lower = md.lower()
    assert "demo-safe" in lower and "sovereignty" in lower
    assert "no real customer data" in lower
    assert "no export generation" in lower


def test_markdown_export_preview_rules() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 8. export preview rules" in lower
    assert "export preview must not create a file" in lower
    assert "export categories must be visible" in lower


def test_markdown_ai_usage_and_consent_rules() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 9. ai usage and consent rules" in lower
    assert "no model training on customer data without explicit written consent" in lower
    assert "ai disclosure must be visible" in lower


def test_markdown_human_review_gate_language() -> None:
    md = render_md()
    lower = md.lower()
    assert "policy preview cannot be treated as legal advice" in lower
    assert "export preview cannot be treated as an actual export" in lower
    assert "retention preview cannot change retention settings" in lower


def test_markdown_sovereignty_and_trust_requirements() -> None:
    md = render_md()
    lower = md.lower()
    assert "the customer or tribe owns its data" in lower
    assert "no customer data is required for seeded sovereignty" in lower
    assert "source provenance must remain visible to the user" in lower


def test_markdown_explicit_does_not_build_phrases() -> None:
    md = render_md()
    lower = md.lower()
    assert "no real data export" in lower
    assert "no customer data access" in lower
    assert "no policy setting change" in lower
    assert "no database migration" in lower


def test_markdown_sprint127_human_review_gates_demo_closeout() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 127" in lower
    assert "m0 human review gates and demo closeout planning packet" in lower


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
