"""Sprint 133: M1 controlled build sequencing and human gate packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT133_MOD = (
    "nativeforge.services.active_source_activation_m1_controlled_build_sequencing_human_gate_packet_service"
)
sprint133_pkt = importlib.import_module(_SPRINT133_MOD)
build_pkt = sprint133_pkt.build_active_source_activation_m1_controlled_build_sequencing_human_gate_packet
render_md = sprint133_pkt.render_active_source_activation_m1_controlled_build_sequencing_human_gate_packet_markdown

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m1_controlled_build_sequencing_human_gate_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After Implementation Dependency Mapping",
    "## 3. M1 Controlled Build Objective",
    "## 4. Preview-Only Build Sequencing Rules",
    "## 5. Required Build Gate Field Groups",
    "## 6. Build Gate Status Definitions",
    "## 7. Field-Level Acceptance Criteria",
    "## 8. Controlled Build Sequence by Product Area",
    "## 9. Human Gate Ownership Rules",
    "## 10. Controlled Build Sequencing Rules",
    "## 11. Sovereignty and Trust Requirements",
    "## 12. What Sprint 133 Does Not Build",
    "## 13. M1 Controlled Build Sequencing Exit Criteria",
    "## 14. Risks and Mitigations",
    "## 15. Sprint 134 Recommended Next Step",
)

EXPECTED_FIELD_GROUP_NAMES = (
    "Build gate identity",
    "Build phase",
    "Product area",
    "Human gate owner",
    "Required approval decision",
    "Required evidence",
    "Dependency prerequisite",
    "Sovereignty prerequisite",
    "Security prerequisite",
    "Data handling prerequisite",
    "Human review prerequisite",
    "Source provenance prerequisite",
    "Sequencing position",
    "Blocker status",
    "Acceptance criteria",
    "Risk note",
    "Non-production disclaimer",
    "Next sprint recommendation",
)

EXPECTED_BUILD_GATE_STATUSES = (
    "Not gated",
    "Gate mapped",
    "Needs human owner",
    "Needs evidence",
    "Needs sovereignty review",
    "Needs security review",
    "Blocked before implementation",
    "Deferred beyond pilot",
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
    assert pkt["sprint_number"] == 133
    assert pkt["packet_name"] == "NativeForge M1 Controlled Build Sequencing and Human Gate Packet"
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True
    assert pkt["may_define_controlled_build_sequence"] is True
    assert pkt["may_define_human_gate_requirements"] is True
    assert pkt["may_define_build_readiness_criteria"] is True
    assert pkt["may_define_acceptance_criteria"] is True
    assert pkt["may_define_guardrails"] is True


def test_packet_actual_counts_zero() -> None:
    pkt = build_pkt()
    for key, value in pkt.items():
        if key.startswith("actual_"):
            assert value == 0, key
    assert pkt["actual_build_steps_executed"] == 0
    assert pkt["actual_features_activated"] == 0
    assert pkt["actual_human_gate_records_created"] == 0


def test_thirteen_m1_controlled_build_sequencing_foundations() -> None:
    pkt = build_pkt()
    rows = pkt["m1_controlled_build_sequencing_and_human_gate_foundations"]
    assert len(rows) == 13
    titles = {r["foundation_area"] for r in rows}
    assert "Controlled build phase inventory" in titles
    assert "Export/audit build gate" in titles


def test_eleven_m1_controlled_build_sequence_product_areas() -> None:
    pkt = build_pkt()
    areas = pkt["m1_controlled_build_sequence_by_product_area"]
    assert len(areas) == 11
    keys = {a["product_area"] for a in areas}
    assert "manual NOFO upload" in keys
    assert "pilot support and implementation operations" in keys


def test_eighteen_build_gate_field_groups_present() -> None:
    pkt = build_pkt()
    groups = pkt["build_gate_field_groups"]
    assert len(groups) == 18
    names = [g["name"] for g in groups]
    for expected in EXPECTED_FIELD_GROUP_NAMES:
        assert expected in names


def test_eight_build_gate_statuses_present_with_disclaimers() -> None:
    pkt = build_pkt()
    rows = pkt["build_gate_statuses"]
    assert len(rows) == 8
    statuses = [r["status"] for r in rows]
    for expected in EXPECTED_BUILD_GATE_STATUSES:
        assert expected in statuses
    disclaimer_phrases = (
        "not runtime execution",
        "not feature activation",
        "not customer approval",
    )
    for r in rows:
        d = (r.get("definition") or "").lower()
        for needle in disclaimer_phrases:
            assert needle in d


def test_universal_disclaimer_present() -> None:
    pkt = build_pkt()
    u = (pkt.get("build_gate_status_universal_disclaimer") or "").lower()
    assert "not runtime execution" in u
    assert "not feature activation" in u
    assert "not customer approval" in u


def test_each_field_group_has_at_least_two_acceptance_criteria() -> None:
    pkt = build_pkt()
    for g in pkt["build_gate_field_groups"]:
        crit = g["acceptance_criteria"]
        assert isinstance(crit, list)
        assert len(crit) >= 2


def test_at_least_eight_risks_documented() -> None:
    pkt = build_pkt()
    assert len(pkt["risks_and_mitigations"]) >= 8


def test_markdown_required_section_headers() -> None:
    md = render_md()
    assert md.startswith("# NativeForge M1 Controlled Build Sequencing and Human Gate Packet v1\n")
    for h in REQUIRED_SECTION_HEADERS:
        assert h in md


def test_markdown_preview_only_build_sequencing_rules() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 4. preview-only build sequencing rules" in lower
    assert "demo-safe" in lower or "demo safe" in lower
    assert "no real customer data" in lower
    assert "no external calls" in lower


def test_markdown_controlled_build_sequence_by_product_area() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 8. controlled build sequence by product area" in lower
    assert "organizational entity profile" in lower
    assert "manual nofo upload" in lower


def test_markdown_human_gate_ownership_rules() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 9. human gate ownership rules" in lower
    assert "buyer-owned" in lower


def test_markdown_controlled_build_sequencing_rules() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 10. controlled build sequencing rules" in lower
    assert "sovereignty" in lower and "security" in lower


def test_markdown_sovereignty_and_trust_requirements() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 11. sovereignty and trust requirements" in lower
    assert "customer owns its data" in lower
    assert "no model training on customer data without explicit written consent" in lower


def test_markdown_explicit_does_not_build_phrases() -> None:
    md = render_md()
    lower = md.lower()
    assert "no build step execution" in lower
    assert "no feature activation" in lower
    assert "no human gate record creation" in lower
    assert "no customer data access" in lower
    assert "no database migration" in lower


def test_markdown_recommends_sprint134_source_ingestion_readiness_packet() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 134" in lower
    assert "m1 source ingestion controlled build readiness packet" in lower


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
