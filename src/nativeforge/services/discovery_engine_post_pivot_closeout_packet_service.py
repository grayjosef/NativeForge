"""Sprint 166: discovery engine post-pivot closeout packet (preview-only).

Deterministic operator artifact documenting discovery-engine state after realignment
from Sprint 159 roadmap pivot, including Sprints 10–38 lineage and Sprints 162–165
post-pivot deliverables, without live ingestion, scraping, source activation, customer
data access, customer outreach, or runtime authorization.
Depends on Sprint 159 as prerequisite after authorization chain closeout; verification
path retains Sprint 159 and Sprint 158 for regression continuity.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = "nf_discovery_engine_post_pivot_closeout_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

_PREREQUISITE_SPRINT159_ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_no_execution_authorization_chain_closeout_"
    "roadmap_pivot_readiness_packet_v1"
)
_VERIFICATION_SPRINT159_ARTIFACT_TYPE = _PREREQUISITE_SPRINT159_ARTIFACT_TYPE
_VERIFICATION_SPRINT158_ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_human_authorization_handoff_final_no_execution_"
    "decision_brief_v1"
)

_DISCOVERY_CAPABILITY_SUMMARY: tuple[dict[str, str | int], ...] = (
    {"sprint_number": 10, "capability": "Opportunity source registry + discovery metadata"},
    {"sprint_number": 12, "capability": "Discovery intake runs + structured candidates"},
    {"sprint_number": 13, "capability": "Discovery quality scoring (offline)"},
    {"sprint_number": 14, "capability": "Discovery review queue API"},
    {"sprint_number": 15, "capability": "Source freshness + check runs"},
    {"sprint_number": 16, "capability": "Coverage gap intelligence"},
    {"sprint_number": 17, "capability": "Operator decision pack / workbench"},
    {"sprint_number": 18, "capability": "Operator action ledger"},
    {"sprint_number": 19, "capability": "Discovery evidence packs"},
    {"sprint_number": 20, "capability": "Discovery engine closeout documentation"},
    {"sprint_number": 23, "capability": "Static connector intake dry run"},
    {"sprint_number": 30, "capability": "Connector closeout validation"},
    {"sprint_number": 33, "capability": "Source quality command layer"},
    {"sprint_number": 36, "capability": "Source coverage plan"},
    {"sprint_number": 37, "capability": "Source candidate registry"},
    {"sprint_number": 38, "capability": "Source onboarding decision pack"},
)

_POST_PIVOT_DELIVERABLES: tuple[dict[str, str | int], ...] = (
    {
        "sprint_number": 162,
        "deliverable": "Review item + check run schema_version contract",
        "artifact_type": "nf_discovery_review_item_v1 / nf_source_check_run_v1",
    },
    {
        "sprint_number": 163,
        "deliverable": "Discovery operator continuity rollup",
        "artifact_type": "nf_discovery_operator_continuity_rollup_v1",
    },
    {
        "sprint_number": 164,
        "deliverable": "Advisory intake batch dedupe fingerprint report",
        "artifact_type": "nf_discovery_dedupe_fingerprint_v1",
    },
    {
        "sprint_number": 165,
        "deliverable": "Discovery API inventory verification manifest",
        "artifact_type": "nf_discovery_api_inventory_manifest_v1",
    },
)

_INTENTIONAL_NON_GOALS: tuple[str, ...] = (
    "Live Grants.gov or external grant portal ingestion",
    "Web scraping or crawling pipelines",
    "Network calls from discovery services",
    "LLM-based ranking or summarization inside discovery engines",
    "Source activation or production runtime authorization",
    "Customer data access or customer outreach",
    "UI surfaces (backend-first closeout only)",
)

_EVIDENCE_GAP_SUMMARY: tuple[dict[str, str], ...] = (
    {
        "gap_area": "Live ingestion readiness",
        "gap_status": "Connector live-readiness checklist remains open; offline only.",
    },
    {
        "gap_area": "Customer validation",
        "gap_status": "Discovery pivot does not substitute customer validation planning.",
    },
    {
        "gap_area": "Coverage completeness",
        "gap_status": "Coverage gaps remain heuristic until richer catalogs are ingested.",
    },
)

_BLOCKED_ACTIONS: tuple[str, ...] = (
    "Post-pivot closeout is documentation-only; no ingestion or activation.",
    "No source activation, scraping, or live network from this packet.",
    "No customer data access, outreach, or interview scheduling.",
    "No runtime authorization granted from Sprint 166 software.",
    "M1 authorization chain execution lanes remain closed after Sprint 159 closeout.",
)

_HUMAN_REVIEW: tuple[str, ...] = (
    "Human review dependency: Sprint 159 closeout selected discovery-engine realignment.",
    "Human review dependency: Sprint 158 handoff brief remains prerequisite context.",
    "Human review dependency: UI and live sourcing phases require separate approval.",
)

_NO_EXECUTION_DEFAULT: tuple[str, ...] = (
    "No-execution default: Sprint 166 documents discovery post-pivot state only.",
    "No-execution default: no scraping, live ingestion, activation, or customer outreach.",
    "No-execution default: preview-only deterministic output; human approval external.",
)

_RUNTIME_AUTHORIZATION_BOUNDARY: tuple[str, ...] = (
    "Runtime authorization boundary: discovery services remain offline-first in closeout.",
    "Runtime authorization boundary: connector and dedupe outputs are advisory only.",
    "Runtime authorization boundary: no runtime authorization or source activation here.",
)

_SPRINT166_DOES_NOT_BUILD: tuple[str, ...] = (
    "no pilot launch",
    "no customer outreach",
    "no interview scheduling",
    "no customer onboarding",
    "no customer data access",
    "no database migration",
    "no source activation",
    "no production activation",
    "no real metric collection",
    "no real pilot closeout",
    "no optimization execution",
    "no architecture implementation",
    "no implementation execution",
    "no runtime authorization granted",
    "no board approval actually granted",
    "no post-board execution",
    "no remediation execution",
    "no evidence closure execution",
    "no re-review board convened",
    "no decision record execution",
    "no audit evidence execution",
    "no packet-chain execution",
    "no handoff execution",
    "no roadmap pivot execution",
    "no runnable implementation workflow",
    "no live scraping",
    "no external API calls",
)

_EXIT_CRITERIA: tuple[str, ...] = (
    "Sprint 159 prerequisite named with matching artifact type.",
    "Verification path retains Sprint 159 and Sprint 158 artifact types.",
    "Discovery capability and post-pivot deliverable summaries present.",
    "Intentional non-goals, gaps, blocked actions, and boundaries documented.",
    "All actual_* counters remain zero.",
)

_RISKS: tuple[tuple[str, str], ...] = (
    (
        "Ingestion boundary mistaken for live-ingestion authorization",
        "State runtime authorization boundary and no-execution default explicitly.",
    ),
    (
        "Sprint 159 prerequisite skipped",
        "Bind prerequisite to Sprint 159 authorization chain closeout artifact.",
    ),
)

_RECOMMENDED_NEXT = (
    "Recommendation-only: use this closeout with Sprint 165 API inventory manifest "
    "and Sprint 163 continuity rollup for operator desk review; pursue UI pass or "
    "live sourcing only after separate human authorization."
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_discovery_engine_post_pivot_closeout_packet() -> dict[str, Any]:
    """Return Sprint 166 discovery post-pivot closeout packet."""
    proof = {
        "sprint_166_discovery_engine_post_pivot_closeout_is_stateless": True,
        "sprint_166_discovery_engine_post_pivot_closeout_is_preview_only": True,
        "sprint_166_discovery_engine_post_pivot_closeout_performs_no_runtime_work": True,
    }
    return _json_safe(
        {
            "artifact_type": ARTIFACT_TYPE,
            "artifact_version": ARTIFACT_VERSION,
            "version": PACKET_VERSION,
            "generated_at": DETERMINISTIC_GENERATED_AT,
            "sprint_number": 166,
            "packet_name": "NativeForge Discovery Engine Post-Pivot Closeout Packet",
            "packet_version": "v1",
            "preview_only": True,
            "no_execution": True,
            "no_activation": True,
            "no_runnable_plan": True,
            "prerequisite_authorization_chain_closeout_sprint": 159,
            "prerequisite_authorization_chain_closeout_artifact_type": (
                _PREREQUISITE_SPRINT159_ARTIFACT_TYPE
            ),
            "verification_path_authorization_chain_closeout_sprint": 159,
            "verification_path_authorization_chain_closeout_artifact_type": (
                _VERIFICATION_SPRINT159_ARTIFACT_TYPE
            ),
            "verification_path_human_authorization_handoff_sprint": 158,
            "verification_path_human_authorization_handoff_artifact_type": (
                _VERIFICATION_SPRINT158_ARTIFACT_TYPE
            ),
            "actual_external_calls": 0,
            "actual_source_ingestions": 0,
            "actual_scrapes": 0,
            "actual_source_activations": 0,
            "actual_customer_data_access": 0,
            "actual_customer_outreach_attempts": 0,
            "discovery_capability_summary": [dict(r) for r in _DISCOVERY_CAPABILITY_SUMMARY],
            "post_pivot_deliverables_summary": [dict(r) for r in _POST_PIVOT_DELIVERABLES],
            "intentional_non_goals": list(_INTENTIONAL_NON_GOALS),
            "evidence_and_validation_gap_summary": [dict(r) for r in _EVIDENCE_GAP_SUMMARY],
            "blocked_action_summary": list(_BLOCKED_ACTIONS),
            "human_review_dependency_summary": list(_HUMAN_REVIEW),
            "no_execution_default": list(_NO_EXECUTION_DEFAULT),
            "runtime_authorization_boundary": list(_RUNTIME_AUTHORIZATION_BOUNDARY),
            "sprint_166_does_not_build": list(_SPRINT166_DOES_NOT_BUILD),
            "packet_exit_criteria": list(_EXIT_CRITERIA),
            "risks_and_mitigations": [
                {"risk": r, "mitigation": m} for r, m in _RISKS
            ],
            "recommended_next_safe_action": _RECOMMENDED_NEXT,
            "sprint_166_discovery_engine_post_pivot_closeout_proof": proof,
        }
    )


def render_discovery_engine_post_pivot_closeout_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render operator markdown (deterministic)."""
    pkt = (
        packet
        if isinstance(packet, dict)
        else build_discovery_engine_post_pivot_closeout_packet()
    )
    lines = [
        "# NativeForge Discovery Engine Post-Pivot Closeout Packet v1",
        "",
        "## 1. Purpose",
        "",
        "Preview-only closeout documenting discovery-engine capabilities and "
        f"post-pivot deliverables after Sprint 159 `{_PREREQUISITE_SPRINT159_ARTIFACT_TYPE}`.",
        "",
        "## 2. Why This Comes After Sprint 159",
        "",
        "Sprint 159 closed the M1 no-execution authorization chain and defined roadmap "
        "pivot options. Sprint 166 documents discovery-engine realignment outcomes "
        "without authorizing ingestion or activation.",
        "",
        "## 3. Discovery Post-Pivot Closeout Objective",
        "",
        "Summarize discovery capabilities (Sprints 10–38) and post-pivot deliverables "
        "(Sprints 162–165) for operator review.",
        "",
        "## 4. Discovery Engine Capability Summary",
        "",
    ]
    for row in pkt.get("discovery_capability_summary") or []:
        if isinstance(row, dict):
            lines.append(
                f"- Sprint {row.get('sprint_number')}: {row.get('capability')}"
            )
    lines.extend(["", "## 5. Post-Pivot Deliverables Summary", ""])
    for row in pkt.get("post_pivot_deliverables_summary") or []:
        if isinstance(row, dict):
            lines.append(
                f"- Sprint {row.get('sprint_number')}: {row.get('deliverable')} "
                f"(`{row.get('artifact_type')}`)"
            )
    lines.extend(["", "## 6. Intentional Non-Goals", ""])
    for item in pkt.get("intentional_non_goals") or list(_INTENTIONAL_NON_GOALS):
        if isinstance(item, str):
            lines.append(f"- {item}")
    lines.extend(["", "## 7. Evidence and Validation Gap Summary", ""])
    for row in pkt.get("evidence_and_validation_gap_summary") or []:
        if isinstance(row, dict):
            lines.append(f"### {row.get('gap_area')}")
            lines.append("")
            lines.append(str(row.get("gap_status") or ""))
            lines.append("")
    lines.extend(["", "## 8. Blocked Action Summary", ""])
    for item in pkt.get("blocked_action_summary") or list(_BLOCKED_ACTIONS):
        if isinstance(item, str):
            lines.append(f"- {item}")
    lines.extend(["", "## 9. Human Review Dependency Summary", ""])
    for item in pkt.get("human_review_dependency_summary") or list(_HUMAN_REVIEW):
        if isinstance(item, str):
            lines.append(f"- {item}")
    lines.extend(["", "## 10. No-Execution Default", ""])
    for item in pkt.get("no_execution_default") or list(_NO_EXECUTION_DEFAULT):
        if isinstance(item, str):
            lines.append(f"- {item}")
    lines.extend(["", "## 11. Runtime Authorization Boundary", ""])
    for item in pkt.get("runtime_authorization_boundary") or list(
        _RUNTIME_AUTHORIZATION_BOUNDARY
    ):
        if isinstance(item, str):
            lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 12. What Sprint 166 Does Not Build",
            "",
        ]
    )
    for item in pkt.get("sprint_166_does_not_build") or list(_SPRINT166_DOES_NOT_BUILD):
        if isinstance(item, str):
            lines.append(f"- {item}")
    lines.extend(["", "## 13. Exit Criteria", ""])
    for c in pkt.get("packet_exit_criteria") or list(_EXIT_CRITERIA):
        if isinstance(c, str):
            lines.append(f"- {c}")
    lines.extend(["", "## 14. Risks and Mitigations", ""])
    for row in pkt.get("risks_and_mitigations") or []:
        if isinstance(row, dict):
            lines.append(
                f"- **Risk**: {row.get('risk')} — **Mitigation**: {row.get('mitigation')}"
            )
    lines.extend(
        [
            "",
            "## 15. Recommended Next Safe Action",
            "",
            pkt.get("recommended_next_safe_action") or _RECOMMENDED_NEXT,
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
