"""Sprint 141: M1 controlled build authorization review packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT141_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_controlled_build_authorization_review_packet_service"
)
sprint141_pkt = importlib.import_module(_SPRINT141_MOD)
build_pkt = sprint141_pkt.build_active_source_activation_m1_controlled_build_authorization_review_packet
render_md = sprint141_pkt.render_active_source_activation_m1_controlled_build_authorization_review_packet_markdown

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m1_controlled_build_authorization_review_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After Sprint 140",
    "## 3. Authorization Objective",
    "## 4. Evidence & Gate Readiness",
    "## 5. Deferred Items",
    "## 6. Human Approval Rules",
    "## 7. Sovereignty & Trust Requirements",
    "## 8. What Sprint 141 Does Not Build",
    "## 9. Exit Criteria",
    "## 10. Risks & Mitigations",
    "## 11. Sprint 142 Recommended Next Step",
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
    assert pkt["sprint_number"] == 141
    assert pkt["packet_name"] == "NativeForge M1 Controlled Build Authorization Review Packet"
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True
    assert pkt["may_define_authorization_readiness_review"] is True
    assert pkt["may_define_evidence_validation_framework"] is True
    assert pkt["may_define_human_gate_expectations"] is True
    assert pkt["may_define_deferred_item_handling"] is True
    assert pkt["may_prepare_runtime_authorization_planning_only"] is True


def test_packet_actual_counts_zero() -> None:
    pkt = build_pkt()
    for key, value in pkt.items():
        if key.startswith("actual_"):
            assert value == 0, key


def test_eight_authorization_review_preview_foundations() -> None:
    pkt = build_pkt()
    rows = pkt["m1_controlled_build_authorization_review_preview_foundations"]
    assert len(rows) == 8
    titles = {r["foundation_area"] for r in rows}
    assert "Prior sprint evidence consolidation" in titles
    assert "Non-execution guardrails" in titles


def test_ten_prior_sprint_evidence_rows_131_through_140() -> None:
    pkt = build_pkt()
    ev = pkt["prior_sprint_evidence_sprints_131_through_140"]
    assert len(ev) == 10
    nums = [r["sprint_number"] for r in ev]
    assert nums == list(range(131, 141))
    assert ev[0]["artifact_summary"]
    assert ev[-1]["sprint_number"] == 140


def test_five_evidence_validation_rules() -> None:
    pkt = build_pkt()
    rules = pkt["evidence_validation_rules"]
    assert len(rules) == 5


def test_six_gate_readiness_statuses_with_disclaimers() -> None:
    pkt = build_pkt()
    rows = pkt["authorization_gate_readiness_statuses"]
    assert len(rows) == 6
    disclaimer_phrases = (
        "not pilot launch",
        "not customer onboarding",
        "not production activation",
    )
    for r in rows:
        d = (r.get("definition") or "").lower()
        for needle in disclaimer_phrases:
            assert needle in d


def test_universal_gate_disclaimer_present() -> None:
    pkt = build_pkt()
    u = (pkt.get("authorization_gate_status_universal_disclaimer") or "").lower()
    assert "not pilot launch" in u
    assert "not customer onboarding" in u
    assert "not production activation" in u


def test_five_deferred_items() -> None:
    pkt = build_pkt()
    assert len(pkt["deferred_items"]) == 5


def test_six_human_approval_rules() -> None:
    pkt = build_pkt()
    assert len(pkt["human_approval_rules"]) == 6


def test_seven_sovereignty_and_trust_requirements() -> None:
    pkt = build_pkt()
    assert len(pkt["sovereignty_and_trust_requirements"]) == 7


def test_four_runtime_authorization_preparation_items() -> None:
    pkt = build_pkt()
    prep = pkt["runtime_authorization_preparation_if_explicitly_approved"]
    assert len(prep) == 4


def test_sprint141_does_not_build_includes_no_runtime_execution() -> None:
    pkt = build_pkt()
    items = [x.lower() for x in pkt["sprint_141_does_not_build"]]
    assert "no runtime execution" in items
    assert "no pilot launch" in items


def test_seven_authorization_review_exit_criteria() -> None:
    pkt = build_pkt()
    assert len(pkt["authorization_review_exit_criteria"]) == 7


def test_eight_risks_documented() -> None:
    pkt = build_pkt()
    assert len(pkt["risks_and_mitigations"]) == 8


def test_markdown_required_section_headers() -> None:
    md = render_md()
    assert md.startswith("# NativeForge M1 Controlled Build Authorization Review Packet v1\n")
    for h in REQUIRED_SECTION_HEADERS:
        assert h in md


def test_markdown_evidence_section_includes_prior_sprints_and_runtime_prep() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 4. evidence & gate readiness" in lower
    assert "sprint 131" in lower
    assert "sprint 140" in lower
    assert "runtime authorization preparation" in lower


def test_markdown_references_sprint140_closeout() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 140" in lower
    assert "demo-to-build" in lower or "demo to build" in lower


def test_markdown_sprint142_next_step() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 11. sprint 142 recommended next step" in lower
    assert "sprint 142" in lower


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
