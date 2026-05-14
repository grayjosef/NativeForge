"""Sprint 131: M1 pilot scope and delivery boundary packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT131_MOD = (
    "nativeforge.services.active_source_activation_m1_pilot_scope_delivery_boundary_packet_service"
)
sprint131_pkt = importlib.import_module(_SPRINT131_MOD)
build_pkt = sprint131_pkt.build_active_source_activation_m1_pilot_scope_delivery_boundary_packet
render_md = sprint131_pkt.render_active_source_activation_m1_pilot_scope_delivery_boundary_packet_markdown

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m1_pilot_scope_delivery_boundary_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After M0 Pilot Transition Planning",
    "## 3. M1 Pilot Scope Objective",
    "## 4. Preview-Only Pilot Scope Rules",
    "## 5. Required Pilot Scope Field Groups",
    "## 6. Pilot Scope Status Definitions",
    "## 7. Field-Level Acceptance Criteria",
    "## 8. M1 Pilot Scope by Product Area",
    "## 9. Included M1 Capability Boundary",
    "## 10. Excluded and Deferred Capability Boundary",
    "## 11. Sovereignty and Trust Requirements",
    "## 12. What Sprint 131 Does Not Build",
    "## 13. M1 Pilot Scope Exit Criteria",
    "## 14. Risks and Mitigations",
    "## 15. Sprint 132 Recommended Next Step",
)

EXPECTED_FIELD_GROUP_NAMES = (
    "Scope item identity",
    "Pilot capability area",
    "Included in M1 flag",
    "Excluded from M1 flag",
    "Delivery boundary",
    "Buyer dependency",
    "Operator dependency",
    "Technical dependency",
    "Sovereignty dependency",
    "Security/access dependency",
    "Human review dependency",
    "Source ingestion dependency",
    "Form package dependency",
    "Acceptance criteria",
    "Risk note",
    "Out-of-scope note",
    "Non-production disclaimer",
    "Next sprint recommendation",
)

EXPECTED_PILOT_SCOPE_STATUSES = (
    "In M1 pilot scope",
    "Out of M1 pilot scope",
    "Needs buyer decision",
    "Needs operator decision",
    "Needs technical discovery",
    "Needs sovereignty review",
    "Needs security review",
    "Deferred beyond M1",
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
    assert pkt["sprint_number"] == 131
    assert pkt["packet_name"] == "NativeForge M1 Pilot Scope and Delivery Boundary Packet"
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True
    assert pkt["may_define_m1_pilot_scope"] is True
    assert pkt["may_define_delivery_boundaries"] is True
    assert pkt["may_define_pilot_acceptance_criteria"] is True
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
    assert pkt["actual_pilot_accounts_created"] == 0
    assert pkt["actual_customer_onboarding_started"] == 0
    assert pkt["actual_m1_features_activated"] == 0


def test_twelve_m1_scope_delivery_foundations() -> None:
    pkt = build_pkt()
    rows = pkt["m1_pilot_scope_delivery_boundary_foundations"]
    assert len(rows) == 12
    titles = {r["foundation_area"] for r in rows}
    assert "Pilot scope definition" in titles
    assert "Support and delivery boundary" in titles


def test_eleven_m1_pilot_scope_product_areas() -> None:
    pkt = build_pkt()
    areas = pkt["m1_pilot_scope_by_product_area"]
    assert len(areas) == 11
    keys = {a["product_area"] for a in areas}
    assert "manual NOFO upload" in keys
    assert "pilot support and delivery operations" in keys


def test_eighteen_pilot_scope_field_groups_present() -> None:
    pkt = build_pkt()
    groups = pkt["pilot_scope_field_groups"]
    assert len(groups) == 18
    names = [g["name"] for g in groups]
    for expected in EXPECTED_FIELD_GROUP_NAMES:
        assert expected in names


def test_eight_pilot_scope_statuses_present_with_disclaimers() -> None:
    pkt = build_pkt()
    rows = pkt["pilot_scope_statuses"]
    assert len(rows) == 8
    statuses = [r["status"] for r in rows]
    for expected in EXPECTED_PILOT_SCOPE_STATUSES:
        assert expected in statuses
    disclaimer_phrases = (
        "not customer onboarding",
        "not production activation",
        "not a delivery commitment",
    )
    for r in rows:
        d = (r.get("definition") or "").lower()
        for needle in disclaimer_phrases:
            assert needle in d


def test_universal_disclaimer_present() -> None:
    pkt = build_pkt()
    u = (pkt.get("pilot_scope_status_universal_disclaimer") or "").lower()
    assert "not customer onboarding" in u
    assert "not production activation" in u
    assert "not a delivery commitment" in u


def test_each_field_group_has_at_least_two_acceptance_criteria() -> None:
    pkt = build_pkt()
    for g in pkt["pilot_scope_field_groups"]:
        crit = g["acceptance_criteria"]
        assert isinstance(crit, list)
        assert len(crit) >= 2


def test_at_least_eight_risks_documented() -> None:
    pkt = build_pkt()
    assert len(pkt["risks_and_mitigations"]) >= 8


def test_markdown_required_section_headers() -> None:
    md = render_md()
    assert md.startswith("# NativeForge M1 Pilot Scope and Delivery Boundary Packet v1\n")
    for h in REQUIRED_SECTION_HEADERS:
        assert h in md


def test_markdown_preview_only_pilot_scope_rules() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 4. preview-only pilot scope rules" in lower
    assert "demo-safe" in lower or "demo-safe" in md.lower()
    assert "no real customer data" in lower
    assert "no external calls" in lower


def test_markdown_m1_pilot_scope_by_product_area() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 8. m1 pilot scope by product area" in lower
    assert "organizational entity profile" in lower
    assert "manual nofo upload" in lower


def test_markdown_included_m1_capability_boundary() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 9. included m1 capability boundary" in lower
    assert "structured extraction may be planned but not executed by this sprint" in lower


def test_markdown_excluded_and_deferred_capability_boundary() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 10. excluded and deferred capability boundary" in lower
    assert "no production submission" in lower


def test_markdown_sovereignty_and_trust_requirements() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 11. sovereignty and trust requirements" in lower
    assert "customer owns its data" in lower
    assert "no model training on customer data without explicit written consent" in lower


def test_markdown_explicit_scope_phrases() -> None:
    md = render_md()
    lower = md.lower()
    assert "no pilot account creation" in lower
    assert "no customer onboarding" in lower
    assert "no m1 feature activation" in lower
    assert "no customer data access" in lower
    assert "no database migration" in lower


def test_markdown_recommends_sprint132_dependency_map_packet() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 132" in lower
    assert "m1 pilot implementation dependency map packet" in lower


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
