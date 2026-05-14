"""Sprint 142: M1 pilot implementation pre-launch checklist packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_SPRINT142_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_pilot_implementation_pre_launch_checklist_packet_service"
)
sprint142_pkt = importlib.import_module(_SPRINT142_MOD)
build_pkt = sprint142_pkt.build_active_source_activation_m1_pilot_implementation_pre_launch_checklist_packet
render_md = (
    sprint142_pkt.render_active_source_activation_m1_pilot_implementation_pre_launch_checklist_packet_markdown
)

_SPRINT140_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_pilot_demo_to_build_transition_closeout_packet_service"
)
sprint140_pkt = importlib.import_module(_SPRINT140_MOD)
build_sprint140 = sprint140_pkt.build_active_source_activation_m1_pilot_demo_to_build_transition_closeout_packet
render_sprint140_md = (
    sprint140_pkt.render_active_source_activation_m1_pilot_demo_to_build_transition_closeout_packet_markdown
)

_SPRINT141_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_controlled_build_authorization_review_packet_service"
)
sprint141_pkt = importlib.import_module(_SPRINT141_MOD)
build_sprint141 = sprint141_pkt.build_active_source_activation_m1_controlled_build_authorization_review_packet
render_sprint141_md = (
    sprint141_pkt.render_active_source_activation_m1_controlled_build_authorization_review_packet_markdown
)

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_m1_pilot_implementation_pre_launch_checklist_packet_service.py"
)

REQUIRED_SECTION_HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After Sprint 141",
    "## 3. Pre-Launch Objective",
    "## 4. Required Evidence Inputs",
    "## 5. Checklist Readiness Domains",
    "## 6. Human Approval Requirements",
    "## 7. Deferred Item Handling",
    "## 8. Sovereignty, Trust, and Data Handling Requirements",
    "## 9. What Sprint 142 Does Not Build",
    "## 10. Exit Criteria",
    "## 11. Risks and Mitigations",
    "## 12. Sprint 143 Recommended Next Step",
)

EXPECTED_CHECKLIST_DOMAINS = (
    "Evidence package completeness",
    "Human gate readiness",
    "Deferred item disposition",
    "Sovereignty and trust review",
    "Environment boundary confirmation",
    "Rollback owner identification",
    "Support and escalation readiness",
    "Documentation handoff readiness",
    "Operator decision record readiness",
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


def test_packet_sprint_and_flags() -> None:
    pkt = build_pkt()
    assert pkt["sprint_number"] == 142
    assert pkt["artifact_type"] == (
        "nf_active_source_activation_m1_pilot_implementation_pre_launch_checklist_packet_v1"
    )
    assert pkt["packet_name"] == "NativeForge M1 Pilot Implementation Pre-Launch Checklist Packet"
    assert pkt["packet_version"] == "v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True
    assert pkt["may_generate_operator_packet"] is True
    assert pkt["may_define_pre_launch_checklist_readiness"] is True
    assert pkt["may_prepare_bounded_implementation_slice_planning_only"] is True


def test_prerequisite_sprint141_authorization_review_packet() -> None:
    pkt = build_pkt()
    assert pkt["prerequisite_authorization_review_sprint"] == 141
    assert (
        pkt["prerequisite_authorization_review_artifact_type"]
        == "nf_active_source_activation_m1_controlled_build_authorization_review_packet_v1"
    )


def test_packet_actual_counts_zero() -> None:
    pkt = build_pkt()
    for key, value in pkt.items():
        if key.startswith("actual_"):
            assert value == 0, key


def test_nine_checklist_readiness_domains() -> None:
    pkt = build_pkt()
    rows = pkt["checklist_readiness_domains"]
    assert len(rows) == 9
    names = [r["domain"] for r in rows]
    for expected in EXPECTED_CHECKLIST_DOMAINS:
        assert expected in names


def test_domain_disclaimers_reject_launch_onboarding_activation() -> None:
    pkt = build_pkt()
    disclaimer_phrases = (
        "not pilot launch",
        "not customer onboarding",
        "not source activation",
        "not production activation",
    )
    u = (pkt.get("checklist_readiness_domain_universal_disclaimer") or "").lower()
    for needle in disclaimer_phrases:
        assert needle in u
    for r in pkt["checklist_readiness_domains"]:
        d = (r.get("readiness_focus") or "").lower()
        for needle in disclaimer_phrases:
            assert needle in d


def test_five_required_evidence_inputs_reference_sprint141_and_140() -> None:
    pkt = build_pkt()
    ev = pkt["required_evidence_inputs"]
    assert len(ev) == 5
    text = json.dumps(ev).lower()
    assert "sprint 141" in text
    assert "sprint 140" in text
    assert "nf_active_source_activation_m1_controlled_build_authorization_review_packet_v1" in text


def test_human_approval_requirements_explicit() -> None:
    pkt = build_pkt()
    joined = " ".join(pkt["human_approval_requirements"]).lower()
    assert "human operator approval" in joined
    assert "human-authored" in joined or "human authored" in joined


def test_sprint142_does_not_build_required_phrases() -> None:
    pkt = build_pkt()
    items = [x.lower() for x in pkt["sprint_142_does_not_build"]]
    assert "no pilot launch" in items
    assert "no customer onboarding" in items
    assert "no customer data access" in items
    assert "no database migration" in items
    assert "no source activation" in items
    assert "no production activation" in items


def test_markdown_what_sprint142_does_not_build_lists_required_exclusions() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 9. what sprint 142 does not build" in lower
    for phrase in (
        "no pilot launch",
        "no customer onboarding",
        "no customer data access",
        "no database migration",
        "no source activation",
        "no production activation",
    ):
        assert phrase in lower


def test_sprint143_recommendation_only() -> None:
    pkt = build_pkt()
    step = (pkt.get("sprint_143_recommended_next_step") or "").lower()
    assert "recommendation-only" in step or "recommendation only" in step
    assert "sprint 143" in step


def test_markdown_required_section_headers_in_order() -> None:
    md = render_md()
    assert md.startswith("# NativeForge M1 Pilot Implementation Pre-Launch Checklist Packet v1\n")
    positions = [md.index(h) for h in REQUIRED_SECTION_HEADERS]
    assert positions == sorted(positions)


def test_markdown_prerequisite_sprint141_and_sequencing() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 141" in lower
    assert "controlled build authorization review" in lower
    assert "sprint 142" in lower


def test_markdown_sovereignty_trust_and_data_handling_section() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 8. sovereignty, trust, and data handling requirements" in lower
    assert "customer owns its data" in lower


def test_markdown_explicit_human_approval_language() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 6. human approval requirements" in lower
    assert "human operator approval" in lower


def test_markdown_sprint143_next_step_header() -> None:
    md = render_md()
    lower = md.lower()
    assert "## 12. sprint 143 recommended next step" in lower


def test_markdown_regression_sprint140_and_sprint141_verification_path() -> None:
    md = render_md()
    lower = md.lower()
    assert "sprint 140" in lower
    assert "demo-to-build" in lower or "demo to build" in lower
    assert "131" in lower and "139" in lower


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


def test_regression_sprint141_packet_still_valid() -> None:
    p141 = build_sprint141()
    assert p141["sprint_number"] == 141
    assert p141["preview_only"] is True
    assert p141["no_execution"] is True
    assert p141["no_activation"] is True
    assert p141["no_runnable_plan"] is True
    for key, value in p141.items():
        if key.startswith("actual_"):
            assert value == 0, key
    md141 = render_sprint141_md()
    assert "## 1. purpose" in md141.lower()
    assert "sprint 142" in md141.lower()


def test_regression_sprint140_packet_still_valid() -> None:
    p140 = build_sprint140()
    assert p140["sprint_number"] == 140
    assert p140["preview_only"] is True
    assert p140["no_execution"] is True
    assert p140["no_activation"] is True
    assert p140["no_runnable_plan"] is True
    for key, value in p140.items():
        if key.startswith("actual_"):
            assert value == 0, key
    md140 = render_sprint140_md()
    assert "## 1. purpose" in md140.lower()
    assert "sprint 141" in md140.lower()
