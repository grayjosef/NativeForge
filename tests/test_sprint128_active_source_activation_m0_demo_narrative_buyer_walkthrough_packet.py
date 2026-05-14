"""Sprint 128: M0 demo narrative and buyer walkthrough packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT128_MOD = (
    "nativeforge.services.active_source_activation_m0_demo_narrative_buyer_walkthrough_packet_service"
)
sprint128_pkt = importlib.import_module(_SPRINT128_MOD)
M0_DEMO_NARRATIVE_CHAPTERS = sprint128_pkt.M0_DEMO_NARRATIVE_CHAPTERS
build_pkt = sprint128_pkt.build_active_source_activation_m0_demo_narrative_buyer_walkthrough_packet
render_md = sprint128_pkt.render_active_source_activation_m0_demo_narrative_buyer_walkthrough_packet_markdown

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m0_demo_narrative_buyer_walkthrough_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After Human Review Closeout",
    "## 3. M0 Demo Narrative Objective",
    "## 4. Demo-Safe Narrative Rules",
    "## 5. Required Walkthrough Field Groups",
    "## 6. Walkthrough Stage Definitions",
    "## 7. Field-Level Acceptance Criteria",
    "## 8. Buyer Walkthrough by M0 Feature",
    "## 9. Buyer Proof Points",
    "## 10. Demo Caveats and Boundaries",
    "## 11. Sovereignty and Trust Requirements",
    "## 12. What Sprint 128 Does Not Build",
    "## 13. M0 Exit Criteria for Demo Narrative Planning",
    "## 14. Risks and Mitigations",
    "## 15. Sprint 129 Recommended Next Step",
)

EXPECTED_FIELD_GROUP_NAMES = (
    "Walkthrough step identity",
    "Buyer pain point",
    "Demo feature shown",
    "Source data used",
    "Demo-safe caveat",
    "Buyer value proof point",
    "Sovereignty/trust proof point",
    "Human review proof point",
    "Risk or limitation note",
    "Transition to next step",
    "Operator talking point",
    "Evidence artifact reference",
    "Field provenance visibility",
    "Non-production disclaimer",
    "Buyer question prompt",
    "Follow-up discovery question",
    "Closeout evidence",
    "Next sprint recommendation",
)

EXPECTED_WALKTHROUGH_STAGES = (
    "Opening problem frame",
    "Entity profile setup",
    "Opportunity discovery preview",
    "Eligibility and mission fit preview",
    "NOFO summary preview",
    "Recommendation preview",
    "Pipeline and deadline preview",
    "SF-424 autofill preview",
    "Requirement checklist preview",
    "Sovereignty and export preview",
    "Human review closeout",
    "Buyer next-step discussion",
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
    assert pkt["sprint_number"] == 128
    assert pkt["packet_name"] == "NativeForge M0 Demo Narrative and Buyer Walkthrough Packet"
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True
    assert pkt["may_define_demo_narrative_scope"] is True
    assert pkt["may_define_buyer_walkthrough_steps"] is True
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
    assert pkt["actual_demo_scripts_generated"] == 0
    assert pkt["actual_buyer_records_created"] == 0
    assert pkt["actual_sales_automation_runs"] == 0


def test_twelve_demo_narrative_chapters() -> None:
    pkt = build_pkt()
    assert pkt["m0_demo_narrative_chapters"] == list(M0_DEMO_NARRATIVE_CHAPTERS)
    assert len(M0_DEMO_NARRATIVE_CHAPTERS) == 12


def test_eighteen_walkthrough_field_groups_present() -> None:
    pkt = build_pkt()
    groups = pkt["walkthrough_field_groups"]
    assert len(groups) == 18
    names = [g["name"] for g in groups]
    for expected in EXPECTED_FIELD_GROUP_NAMES:
        assert expected in names


def test_twelve_walkthrough_stages_present() -> None:
    pkt = build_pkt()
    stages = [s["stage"] for s in pkt["walkthrough_stages"]]
    assert len(stages) == 12
    for expected in EXPECTED_WALKTHROUGH_STAGES:
        assert expected in stages


def test_each_stage_states_demo_safe_data_and_boundaries() -> None:
    pkt = build_pkt()
    needle_data = "seeded or demo-safe data only"
    needle_submit = "does not submit applications"
    needle_elig = "does not make final eligibility determinations"
    needle_cust = "does not access real customer data"
    for s in pkt["walkthrough_stages"]:
        b = (s.get("mandatory_demo_boundary_statement") or "").lower()
        assert needle_data in b
        assert needle_submit in b
        assert needle_elig in b
        assert needle_cust in b


def test_each_field_group_has_at_least_two_acceptance_criteria() -> None:
    pkt = build_pkt()
    for g in pkt["walkthrough_field_groups"]:
        crit = g["acceptance_criteria"]
        assert isinstance(crit, list)
        assert len(crit) >= 2


def test_at_least_eight_risks_documented() -> None:
    pkt = build_pkt()
    assert len(pkt["risks_and_mitigations"]) >= 8


def test_markdown_required_section_headers() -> None:
    md = render_md()
    assert md.startswith("# NativeForge M0 Demo Narrative and Buyer Walkthrough Packet v1\n")
    for h in REQUIRED_SECTION_HEADERS:
        assert h in md


def test_markdown_demo_safe_narrative_rules() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 4. demo-safe narrative rules" in lower
    assert "demo-safe" in lower
    assert "no real customer data" in lower
    assert "no live application submission" in lower
    assert "no final eligibility determination" in lower
    assert "no external calls" in lower


def test_markdown_buyer_walkthrough_by_m0_feature() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 8. buyer walkthrough by m0 feature" in lower
    assert "organizational entity profile" in lower
    assert "human review closeout" in lower


def test_markdown_buyer_proof_points() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 9. buyer proof points" in lower
    assert "fewer repeated fields" in lower
    assert "visible source provenance" in lower


def test_markdown_demo_caveats_and_boundaries() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 10. demo caveats and boundaries" in lower
    assert "seeded/demo-safe data only" in lower
    assert "no production workflow execution" in lower


def test_markdown_sovereignty_and_trust_requirements() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 11. sovereignty and trust requirements" in lower
    assert "customer owns its data" in lower
    assert "no model training on customer data without explicit written consent" in lower


def test_markdown_explicit_does_not_build_phrases() -> None:
    md = render_md()
    lower = md.lower()
    assert "no live sales script generation" in lower
    assert "no buyer record creation" in lower
    assert "no customer data access" in lower
    assert "no database migration" in lower


def test_markdown_recommends_sprint129_evidence_pack() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 129" in lower
    assert "m0 demo readiness evidence pack" in lower
    assert "operator checklist packet" in lower


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
