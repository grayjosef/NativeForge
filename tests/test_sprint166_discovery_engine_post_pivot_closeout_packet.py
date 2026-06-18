"""Sprint 166: discovery engine post-pivot closeout packet (stateless, no DB, no network)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

_S166_MOD = (
    "nativeforge.services.discovery_engine_post_pivot_closeout_packet_service"
)
s166 = importlib.import_module(_S166_MOD)
build_pkt = s166.build_discovery_engine_post_pivot_closeout_packet
render_md = s166.render_discovery_engine_post_pivot_closeout_packet_markdown

_S159_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_no_execution_authorization_chain_closeout_"
    "roadmap_pivot_readiness_packet_service"
)
s159 = importlib.import_module(_S159_MOD)
build_s159 = (
    s159.build_active_source_activation_m1_no_execution_authorization_chain_closeout_roadmap_pivot_readiness_packet
)

_S158_MOD = (
    "nativeforge.services."
    "active_source_activation_m1_human_authorization_handoff_final_no_execution_decision_brief_service"
)
s158 = importlib.import_module(_S158_MOD)
build_s158 = (
    s158.build_active_source_activation_m1_human_authorization_handoff_final_no_execution_decision_brief
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "discovery_engine_post_pivot_closeout_packet_service.py"
)

HEADERS = (
    "## 1. Purpose",
    "## 2. Why This Comes After Sprint 159",
    "## 3. Discovery Post-Pivot Closeout Objective",
    "## 4. Discovery Engine Capability Summary",
    "## 5. Post-Pivot Deliverables Summary",
    "## 6. Intentional Non-Goals",
    "## 7. Evidence and Validation Gap Summary",
    "## 8. Blocked Action Summary",
    "## 9. Human Review Dependency Summary",
    "## 10. No-Execution Default",
    "## 11. Runtime Authorization Boundary",
    "## 12. What Sprint 166 Does Not Build",
    "## 13. Exit Criteria",
    "## 14. Risks and Mitigations",
    "## 15. Recommended Next Safe Action",
)

POST_PIVOT_ARTIFACTS = (
    "nf_discovery_review_item_v1 / nf_source_check_run_v1",
    "nf_discovery_operator_continuity_rollup_v1",
    "nf_discovery_dedupe_fingerprint_v1",
    "nf_discovery_api_inventory_manifest_v1",
)


def test_packet_sprint_and_flags() -> None:
    pkt = build_pkt()
    assert pkt["sprint_number"] == 166
    assert pkt["artifact_type"] == "nf_discovery_engine_post_pivot_closeout_packet_v1"
    assert pkt["preview_only"] is True
    assert pkt["no_execution"] is True
    assert pkt["no_activation"] is True
    assert pkt["no_runnable_plan"] is True


def test_prerequisite_sprint159() -> None:
    pkt = build_pkt()
    assert pkt["prerequisite_authorization_chain_closeout_sprint"] == 159
    assert (
        pkt["prerequisite_authorization_chain_closeout_artifact_type"]
        == "nf_active_source_activation_m1_no_execution_authorization_chain_closeout_roadmap_pivot_readiness_packet_v1"
    )


def test_verification_path_sprint159_and_sprint158() -> None:
    pkt = build_pkt()
    assert pkt["verification_path_authorization_chain_closeout_sprint"] == 159
    assert pkt["verification_path_human_authorization_handoff_sprint"] == 158


def test_actual_counts_zero() -> None:
    pkt = build_pkt()
    for key, value in pkt.items():
        if key.startswith("actual_"):
            assert value == 0, key


def test_post_pivot_deliverables_present() -> None:
    pkt = build_pkt()
    joined = json.dumps(pkt["post_pivot_deliverables_summary"])
    for art in POST_PIVOT_ARTIFACTS:
        assert art in joined


def test_discovery_capabilities_include_sprint38() -> None:
    pkt = build_pkt()
    nums = [r["sprint_number"] for r in pkt["discovery_capability_summary"]]
    assert 10 in nums
    assert 38 in nums


def test_markdown_headers_in_order() -> None:
    md = render_md()
    positions = [md.index(h) for h in HEADERS]
    assert positions == sorted(positions)


def test_markdown_runtime_authorization_boundary() -> None:
    md = render_md().lower()
    assert "runtime authorization boundary" in md
    assert "no runtime authorization" in md


def test_deterministic() -> None:
    a = build_pkt()
    b = build_pkt()
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert render_md() == render_md(a)


def test_service_no_subprocess_or_network() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in {"subprocess", "requests", "httpx", "socket"}
    assert "urllib.request" not in src


def test_regression_sprint159_still_valid() -> None:
    p159 = build_s159()
    assert p159["sprint_number"] == 159
    assert p159["preview_only"] is True
    for key, value in p159.items():
        if key.startswith("actual_"):
            assert value == 0, key


def test_regression_sprint158_still_valid() -> None:
    p158 = build_s158()
    assert p158["sprint_number"] == 158
    assert p158["preview_only"] is True
