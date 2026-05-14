"""Sprint 118: M0 Organizational Entity Profile planning packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from nativeforge.services.active_source_activation_m0_organizational_entity_profile_planning_packet_service import (
    M0_ENTITY_PROFILE_FOUNDATIONS,
    build_active_source_activation_m0_organizational_entity_profile_planning_packet,
    render_active_source_activation_m0_organizational_entity_profile_planning_packet_markdown,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m0_organizational_entity_profile_planning_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes First",
    "## 3. M0 Entity Profile Objective",
    "## 4. Demo-Safe Entity Profile Rules",
    "## 5. Required Field Groups",
    "## 6. Field-Level Acceptance Criteria",
    "## 7. Entity Profile to M0 Feature Mapping",
    "## 8. Human Review Gates",
    "## 9. Sovereignty and Trust Requirements",
    "## 10. What Sprint 118 Does Not Build",
    "## 11. M0 Exit Criteria for Entity Profile Planning",
    "## 12. Risks and Mitigations",
    "## 13. Sprint 119 Recommended Next Step",
)

EXPECTED_FIELD_GROUP_NAMES = (
    "Legal identity",
    "Entity classification",
    "Location and service area",
    "Authorized officials",
    "Grants and finance contacts",
    "Financial profile",
    "Certifications and assurances",
    "SAM.gov and UEI data",
    "Indirect cost rate data",
    "Organizational capacity narratives",
    "Community profile narrative",
    "Standard attachment inventory",
    "Funding priorities",
    "Match capacity and staff capacity",
    "Data sovereignty preferences",
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
    pkt = build_active_source_activation_m0_organizational_entity_profile_planning_packet()
    assert pkt["sprint_number"] == 118
    assert pkt["packet_name"] == "NativeForge M0 Organizational Entity Profile Planning Packet"
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True
    assert pkt["may_define_entity_profile_scope"] is True
    assert pkt["may_define_demo_safe_schema"] is True
    assert pkt["may_define_acceptance_criteria"] is True
    assert pkt["may_define_guardrails"] is True


def test_packet_actual_counts_zero() -> None:
    pkt = build_active_source_activation_m0_organizational_entity_profile_planning_packet()
    assert pkt["actual_external_calls"] == 0
    assert pkt["actual_source_ingestions"] == 0
    assert pkt["actual_ai_generations"] == 0
    assert pkt["actual_form_submissions"] == 0
    assert pkt["actual_customer_data_access"] == 0
    assert pkt["actual_runtime_writes"] == 0


def test_m0_foundations_match_required_ten() -> None:
    pkt = build_active_source_activation_m0_organizational_entity_profile_planning_packet()
    assert pkt["m0_entity_profile_foundations"] == list(M0_ENTITY_PROFILE_FOUNDATIONS)
    assert len(M0_ENTITY_PROFILE_FOUNDATIONS) == 10


def test_fifteen_field_groups_present() -> None:
    pkt = build_active_source_activation_m0_organizational_entity_profile_planning_packet()
    groups = pkt["entity_profile_field_groups"]
    assert len(groups) == 15
    names = [g["name"] for g in groups]
    for expected in EXPECTED_FIELD_GROUP_NAMES:
        assert expected in names


def test_each_field_group_has_at_least_two_acceptance_criteria() -> None:
    pkt = build_active_source_activation_m0_organizational_entity_profile_planning_packet()
    for g in pkt["entity_profile_field_groups"]:
        crit = g["acceptance_criteria"]
        assert isinstance(crit, list)
        assert len(crit) >= 2


def test_at_least_eight_risks_documented() -> None:
    pkt = build_active_source_activation_m0_organizational_entity_profile_planning_packet()
    assert len(pkt["risks_and_mitigations"]) >= 8


def test_markdown_required_section_headers() -> None:
    md = render_active_source_activation_m0_organizational_entity_profile_planning_packet_markdown()
    assert md.startswith("# NativeForge M0 Organizational Entity Profile Planning Packet v1\n")
    for h in REQUIRED_SECTION_HEADERS:
        assert h in md


def test_markdown_demo_safe_entity_profile_restrictions() -> None:
    md = render_active_source_activation_m0_organizational_entity_profile_planning_packet_markdown()
    lower = md.lower()
    assert "demo-safe" in lower or "seeded" in lower
    assert "no real tribal customer data" in lower
    assert "no live sam.gov lookups" in lower
    assert "no external validation calls" in lower
    assert "no production attachments" in lower
    assert "no sensitive financial documents" in lower


def test_markdown_human_review_gate_language() -> None:
    md = render_active_source_activation_m0_organizational_entity_profile_planning_packet_markdown()
    lower = md.lower()
    assert "profile data cannot be treated as verified unless manually reviewed" in lower
    assert "autofill preview cannot be finalized without human approval" in lower
    assert "narrative reuse must remain editable" in lower
    assert "missing uei" in lower and "sam" in lower and "authorized representative" in lower
    assert "profile-based recommendations must be overrideable" in lower


def test_markdown_sovereignty_and_trust_requirements() -> None:
    md = render_active_source_activation_m0_organizational_entity_profile_planning_packet_markdown()
    lower = md.lower()
    assert "tribe owns its data" in lower
    assert "no customer data is used for model training without explicit written consent" in lower
    assert "export path required before paid pilot readiness" in lower
    assert "audit log required before paid pilot readiness" in lower
    assert "configurable retention" in lower and "future readiness" in lower
    assert "private deployment remains later-stage, not m0" in lower


def test_markdown_no_sam_gov_integration() -> None:
    md = render_active_source_activation_m0_organizational_entity_profile_planning_packet_markdown()
    assert "no sam.gov integration" in md.lower()


def test_markdown_no_database_migration() -> None:
    md = render_active_source_activation_m0_organizational_entity_profile_planning_packet_markdown()
    assert "No database migration" in md


def test_markdown_sprint119_grants_gov_seeded_opportunity_planning_packet() -> None:
    md = render_active_source_activation_m0_organizational_entity_profile_planning_packet_markdown()
    lower = md.lower()
    assert "sprint 119" in lower
    assert "grants.gov seeded opportunity ingestion interface planning packet" in lower


def test_deterministic_packet_and_markdown() -> None:
    a = build_active_source_activation_m0_organizational_entity_profile_planning_packet()
    b = build_active_source_activation_m0_organizational_entity_profile_planning_packet()
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    md_a = render_active_source_activation_m0_organizational_entity_profile_planning_packet_markdown(a)
    md_b = render_active_source_activation_m0_organizational_entity_profile_planning_packet_markdown(b)
    assert md_a == md_b


def test_render_without_argument_matches_explicit_packet() -> None:
    pkt = build_active_source_activation_m0_organizational_entity_profile_planning_packet()
    assert (
        render_active_source_activation_m0_organizational_entity_profile_planning_packet_markdown()
        == render_active_source_activation_m0_organizational_entity_profile_planning_packet_markdown(pkt)
    )
