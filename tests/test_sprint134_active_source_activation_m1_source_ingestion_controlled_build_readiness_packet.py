"""Sprint 134: M1 source ingestion controlled build readiness packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT134_MOD = (
    "nativeforge.services.active_source_activation_m1_source_ingestion_controlled_build_readiness_packet_service"
)
sprint134_pkt = importlib.import_module(_SPRINT134_MOD)
build_pkt = sprint134_pkt.build_active_source_activation_m1_source_ingestion_controlled_build_readiness_packet
render_md = sprint134_pkt.render_active_source_activation_m1_source_ingestion_controlled_build_readiness_packet_markdown

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m1_source_ingestion_controlled_build_readiness_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After Controlled Build Sequencing",
    "## 3. M1 Source Ingestion Readiness Objective",
    "## 4. Preview-Only Source Readiness Rules",
    "## 5. Required Source Readiness Field Groups",
    "## 6. Source Readiness Status Definitions",
    "## 7. Field-Level Acceptance Criteria",
    "## 8. Source Readiness by Source Type",
    "## 9. Source Activation Prerequisite Rules",
    "## 10. Human Gate and Review Rules",
    "## 11. Sovereignty and Trust Requirements",
    "## 12. What Sprint 134 Does Not Build",
    "## 13. M1 Source Ingestion Readiness Exit Criteria",
    "## 14. Risks and Mitigations",
    "## 15. Sprint 135 Recommended Next Step",
)

EXPECTED_FIELD_GROUP_NAMES = (
    "Source readiness item identity",
    "Source name",
    "Source type",
    "Source owner or maintainer",
    "Source access method",
    "Source trust level",
    "Source provenance requirement",
    "Native relevance rationale",
    "Eligibility signal expectation",
    "Freshness expectation",
    "Credential or access requirement",
    "Security prerequisite",
    "Sovereignty prerequisite",
    "Human review prerequisite",
    "Activation blocker status",
    "Acceptance criteria",
    "Non-production disclaimer",
    "Next sprint recommendation",
)

EXPECTED_SOURCE_READINESS_STATUSES = (
    "Not assessed",
    "Ready for controlled build planning",
    "Needs source verification",
    "Needs access decision",
    "Needs credential review",
    "Needs sovereignty review",
    "Blocked before activation",
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
    assert pkt["sprint_number"] == 134
    assert pkt["packet_name"] == "NativeForge M1 Source Ingestion Controlled Build Readiness Packet"
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True
    assert pkt["may_define_source_ingestion_readiness"] is True
    assert pkt["may_define_source_activation_prerequisites"] is True
    assert pkt["may_define_human_gate_requirements"] is True
    assert pkt["may_define_acceptance_criteria"] is True
    assert pkt["may_define_guardrails"] is True


def test_packet_actual_counts_zero() -> None:
    pkt = build_pkt()
    for key, value in pkt.items():
        if key.startswith("actual_"):
            assert value == 0, key
    assert pkt["actual_sources_activated"] == 0
    assert pkt["actual_ingestion_jobs_created"] == 0
    assert pkt["actual_credentials_configured"] == 0


def test_thirteen_m1_source_ingestion_readiness_foundations() -> None:
    pkt = build_pkt()
    rows = pkt["m1_source_ingestion_controlled_build_readiness_foundations"]
    assert len(rows) == 13
    titles = {r["foundation_area"] for r in rows}
    assert "Source inventory readiness" in titles
    assert "Data sovereignty readiness" in titles


def test_ten_source_readiness_by_source_type() -> None:
    pkt = build_pkt()
    areas = pkt["source_readiness_by_source_type"]
    assert len(areas) == 10
    keys = {a["source_type"] for a in areas}
    assert "Grants.gov" in keys
    assert "manual NOFO upload sources" in keys


def test_eighteen_source_readiness_field_groups_present() -> None:
    pkt = build_pkt()
    groups = pkt["source_readiness_field_groups"]
    assert len(groups) == 18
    names = [g["name"] for g in groups]
    for expected in EXPECTED_FIELD_GROUP_NAMES:
        assert expected in names


def test_eight_source_readiness_statuses_present_with_disclaimers() -> None:
    pkt = build_pkt()
    rows = pkt["source_readiness_statuses"]
    assert len(rows) == 8
    statuses = [r["status"] for r in rows]
    for expected in EXPECTED_SOURCE_READINESS_STATUSES:
        assert expected in statuses
    disclaimer_phrases = (
        "not source activation",
        "not live ingestion",
        "not credential configuration",
    )
    for r in rows:
        d = (r.get("definition") or "").lower()
        for needle in disclaimer_phrases:
            assert needle in d


def test_universal_disclaimer_present() -> None:
    pkt = build_pkt()
    u = (pkt.get("source_readiness_status_universal_disclaimer") or "").lower()
    assert "not source activation" in u
    assert "not live ingestion" in u
    assert "not credential configuration" in u


def test_each_field_group_has_at_least_two_acceptance_criteria() -> None:
    pkt = build_pkt()
    for g in pkt["source_readiness_field_groups"]:
        crit = g["acceptance_criteria"]
        assert isinstance(crit, list)
        assert len(crit) >= 2


def test_at_least_eight_risks_documented() -> None:
    pkt = build_pkt()
    assert len(pkt["risks_and_mitigations"]) >= 8


def test_markdown_required_section_headers() -> None:
    md = render_md()
    assert md.startswith(
        "# NativeForge M1 Source Ingestion Controlled Build Readiness Packet v1\n"
    )
    for h in REQUIRED_SECTION_HEADERS:
        assert h in md


def test_markdown_preview_only_source_readiness_rules() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 4. preview-only source readiness rules" in lower
    assert "demo-safe" in lower or "demo safe" in lower
    assert "no real customer data" in lower
    assert "no external calls" in lower


def test_markdown_source_readiness_by_source_type() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 8. source readiness by source type" in lower
    assert "grants.gov" in lower
    assert "manual nofo upload sources" in lower


def test_markdown_source_activation_prerequisite_rules() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 9. source activation prerequisite rules" in lower
    assert "source readiness item identity" in lower
    assert "source access method" in lower


def test_markdown_human_gate_and_review_rules() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 10. human gate and review rules" in lower
    assert "low trust" in lower


def test_markdown_sovereignty_and_trust_requirements() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 11. sovereignty and trust requirements" in lower
    assert "customer owns its data" in lower
    assert "no model training on customer data without explicit written consent" in lower


def test_markdown_explicit_does_not_build_phrases() -> None:
    md = render_md()
    lower = md.lower()
    assert "no source activation" in lower
    assert "no live ingestion" in lower
    assert "no ingestion job creation" in lower
    assert "no credential configuration" in lower
    assert "no customer data access" in lower
    assert "no database migration" in lower


def test_markdown_recommends_sprint135_nofo_extraction_readiness_packet() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 135" in lower
    assert "m1 nofo extraction controlled build readiness packet" in lower


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
