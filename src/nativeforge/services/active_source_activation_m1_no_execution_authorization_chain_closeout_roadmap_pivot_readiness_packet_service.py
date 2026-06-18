"""Sprint 159: M1 no-execution authorization chain closeout & roadmap pivot readiness (preview-only).

Deterministic operator artifact that closes the Sprint 149 through Sprint 158 no-execution
runtime authorization readiness chain and defines roadmap pivot options without authorizing
runtime work, board approval, customer onboarding, source activation, pilot launch,
production activation, packet-chain execution, handoff execution, decision record execution,
audit evidence execution, evidence closure execution, remediation execution, re-review board
convening, roadmap pivot execution, implementation execution, architecture implementation,
live customer data access, customer outreach, interview scheduling, external calls, database
migrations, real metric collection, real pilot closeout, or optimization execution.
Depends on Sprint 158 as mandatory prerequisite after the human authorization handoff final
no-execution decision brief; verification path retains Sprint 158 and Sprint 157 for
regression continuity.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_no_execution_authorization_chain_closeout_"
    "roadmap_pivot_readiness_packet_v1"
)
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

_PREREQUISITE_SPRINT158_ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_human_authorization_handoff_final_no_execution_"
    "decision_brief_v1"
)
_VERIFICATION_SPRINT158_ARTIFACT_TYPE = _PREREQUISITE_SPRINT158_ARTIFACT_TYPE
_VERIFICATION_SPRINT157_ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_final_runtime_authorization_packet_index_readiness_rollup_v1"
)

_S149 = "nf_active_source_activation_m1_technical_architecture_review_runtime_boundary_packet_v1"
_S150 = "nf_active_source_activation_m1_bounded_implementation_design_human_gate_packet_v1"
_S151 = "nf_active_source_activation_m1_runtime_authorization_review_readiness_no_execution_packet_v1"
_S152 = "nf_active_source_activation_m1_human_runtime_authorization_board_packet_v1"
_S153 = "nf_active_source_activation_m1_post_board_decision_routing_next_safe_action_packet_v1"
_S154 = "nf_active_source_activation_m1_evidence_remediation_queue_re_review_packet_v1"
_S155 = "nf_active_source_activation_m1_re_review_board_readiness_evidence_closure_packet_v1"
_S156 = "nf_active_source_activation_m1_runtime_authorization_decision_record_audit_evidence_packet_v1"
_S157 = _VERIFICATION_SPRINT157_ARTIFACT_TYPE
_S158 = _PREREQUISITE_SPRINT158_ARTIFACT_TYPE

_AUTHORIZATION_CHAIN_CLOSEOUT_SUMMARY: tuple[dict[str, str | int], ...] = (
    {
        "sprint_number": 149,
        "packet_title": (
            "Sprint 149 technical architecture review runtime boundary packet"
        ),
        "artifact_type": _S149,
    },
    {
        "sprint_number": 150,
        "packet_title": (
            "Sprint 150 bounded implementation design human gate packet"
        ),
        "artifact_type": _S150,
    },
    {
        "sprint_number": 151,
        "packet_title": (
            "Sprint 151 runtime authorization review readiness no-execution packet"
        ),
        "artifact_type": _S151,
    },
    {
        "sprint_number": 152,
        "packet_title": "Sprint 152 human runtime authorization board packet",
        "artifact_type": _S152,
    },
    {
        "sprint_number": 153,
        "packet_title": (
            "Sprint 153 post-board decision routing next-safe-action packet"
        ),
        "artifact_type": _S153,
    },
    {
        "sprint_number": 154,
        "packet_title": "Sprint 154 evidence remediation queue re-review packet",
        "artifact_type": _S154,
    },
    {
        "sprint_number": 155,
        "packet_title": (
            "Sprint 155 re-review board readiness evidence closure packet"
        ),
        "artifact_type": _S155,
    },
    {
        "sprint_number": 156,
        "packet_title": (
            "Sprint 156 runtime authorization decision record audit evidence packet"
        ),
        "artifact_type": _S156,
    },
    {
        "sprint_number": 157,
        "packet_title": (
            "Sprint 157 final runtime authorization packet index readiness rollup"
        ),
        "artifact_type": _S157,
    },
    {
        "sprint_number": 158,
        "packet_title": (
            "Sprint 158 human authorization handoff final no-execution decision brief"
        ),
        "artifact_type": _S158,
    },
)

_ROADMAP_PIVOT_OPTIONS: tuple[str, ...] = (
    "Close the authorization chain with no execution",
    "Continue documentation-only planning",
    "Request evidence remediation",
    "Request narrowed-scope review",
    "Request additional security review",
    "Request additional sovereignty and trust review",
    "Request additional customer validation",
    "Realign to M0/M1 product roadmap review",
    "Prepare a separate future authorization process",
    "Maintain no-execution default",
)

_RECOMMENDED_PIVOT_DECISION_CRITERIA: tuple[str, ...] = (
    "Does the next lane require runtime work?",
    "Does the next lane require customer data access?",
    "Does the next lane require customer outreach?",
    "Does the next lane require source activation?",
    "Does the next lane require production activation?",
    "Does the next lane require database migration?",
    "Does the next lane require pilot launch?",
    "Does the next lane require written human approval?",
    "Does the next lane preserve NativeForge grant discovery as a core product engine?",
    "Does the next lane preserve sovereignty-first data boundaries?",
)

_EVIDENCE_AND_VALIDATION_GAP_SUMMARY: tuple[dict[str, str], ...] = (
    {
        "gap_area": "Security review",
        "gap_status": (
            "Documentation-only closeout: security narratives may exist in governance "
            "folders; Sprint 159 does not perform audit evidence execution or ingest live "
            "evidence."
        ),
    },
    {
        "gap_area": "Sovereignty and trust",
        "gap_status": (
            "Validation gap remains for human judgment: sovereignty-first boundaries are "
            "indexed but not attested by software in this packet."
        ),
    },
    {
        "gap_area": "Customer validation",
        "gap_status": (
            "Preview-only gap summary: customer validation planning may be referenced; no "
            "customer data access, customer outreach, or interview scheduling from Sprint 159."
        ),
    },
    {
        "gap_area": "Technical architecture",
        "gap_status": (
            "Sprint 149 boundary packet closes in documentation only; architecture "
            "implementation remains blocked in software outputs."
        ),
    },
    {
        "gap_area": "Decision record and audit export",
        "gap_status": (
            "Sprint 156 templates referenced in chain closeout; decision record execution "
            "and audit evidence execution counters remain zero."
        ),
    },
    {
        "gap_area": "Human authorization handoff",
        "gap_status": (
            "Sprint 158 handoff brief is prerequisite; written human approval remains "
            "explicitly separated from this closeout packet."
        ),
    },
)

_BLOCKED_ACTION_SUMMARY: tuple[str, ...] = (
    "Authorization chain closeout summary references Sprints 149–158 without "
    "packet-chain execution or authorization chain execution.",
    "Roadmap pivot options are documentation templates only; roadmap pivot execution is "
    "blocked in software.",
    "No runtime authorization granted and no board approval actually granted from "
    "Sprint 159 software.",
    "No pilot launch, customer outreach, interview scheduling, or customer onboarding.",
    "No source activation, production activation, or database migration.",
    "No customer data access, real metric collection, or real pilot closeout.",
    "No optimization execution, architecture implementation, or implementation execution.",
    "No post-board execution, remediation execution, evidence closure execution, or "
    "re-review board convened in software.",
    "No decision record execution, audit evidence execution, handoff execution, or runnable "
    "implementation workflow may begin from this packet.",
    "All execution-class actions remain blocked by default until separate human "
    "authorization outside this closeout packet.",
)

_HUMAN_REVIEW_DEPENDENCY_SUMMARY: tuple[str, ...] = (
    "Human review dependency: the completed authorization chain is documentation-only and "
    "review-only; Sprint 159 closes the chain in software outputs without human decision "
    "execution.",
    "Human review dependency: Sprint 158 human authorization handoff final no-execution "
    "decision brief is prerequisite; operators must not treat this closeout as substitute "
    "written human approval.",
    "Human review dependency: Sprint 157 final packet index and Sprint 156 decision record "
    "lineage remain in the verification path for regression continuity.",
    "Human review dependency: roadmap pivot selection occurs outside software; pivot "
    "criteria guide human choice only.",
    "Human review dependency: recommendation-only next actions require desk review without "
    "activating systems, convening boards, or performing roadmap pivot execution.",
)

_NO_EXECUTION_DEFAULT: tuple[str, ...] = (
    "No-execution default: Sprint 159 emits an authorization chain closeout and roadmap "
    "pivot readiness packet only; runtime execution, packet-chain execution, handoff "
    "execution, roadmap pivot execution, activation, launch, onboarding, outreach, "
    "scheduling, board convening, remediation execution, evidence closure execution, "
    "decision record execution, and audit evidence execution remain closed in software.",
    "No-execution default: no pilot launch, no customer outreach, no interview scheduling, "
    "no customer onboarding, no customer data access, no database migration, no source "
    "activation, no production activation, no real metric collection, no real pilot "
    "closeout, no optimization execution, no architecture implementation, no implementation "
    "execution, no runtime authorization granted, no board approval actually granted, no "
    "post-board execution, no remediation execution, no evidence closure execution, no "
    "re-review board convened, no decision record execution, no audit evidence execution, "
    "no packet-chain execution, no handoff execution, no roadmap pivot execution, and no "
    "runnable implementation workflow may begin from this packet.",
    "No-execution default: deterministic markdown and dict output are preview-only; human "
    "operator approval for any execution phase remains mandatory and external.",
)

_RUNTIME_AUTHORIZATION_BOUNDARY: tuple[str, ...] = (
    "Runtime authorization boundary: Sprint 159 closes Sprint 149–158 as documentation "
    "lineage for human roadmap pivot choice; it grants no runtime authorization granted "
    "and no board approval actually granted.",
    "Runtime authorization boundary: preview-only deterministic dict and markdown emission "
    "only; no runtime writes, workers, external calls, packet-chain execution, handoff "
    "execution, roadmap pivot execution, decision record execution, audit evidence execution, "
    "evidence closure execution, remediation execution, post-board execution, re-review "
    "board convened, or pilot launch.",
    "Runtime authorization boundary: roadmap pivot options and pivot decision criteria "
    "must not be interpreted as authorization to execute, activate, migrate, onboard, export "
    "live data, or convene governance bodies from this codebase.",
)

_SPRINT159_DOES_NOT_BUILD: tuple[str, ...] = (
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
    "no runtime execution",
    "no live customer data",
    "no external service call",
    "no AI generation",
    "no API route",
    "no frontend UI",
    "no workflow activation",
    "no form submission",
    "no implicit authorization from this packet",
)

_NEXT_SAFE_ACTION_OPTIONS: tuple[str, ...] = (
    "Recommendation-only (review-only): read this closeout packet alongside Sprint 158 "
    "handoff brief and Sprint 157 rollup indices as a desk exercise—no software execution.",
    "Recommendation-only (review-only): evaluate roadmap pivot options using pivot "
    "decision criteria in a human-maintained decision log without customer outreach.",
    "Recommendation-only (review-only): if evidence gaps remain, document remediation "
    "requests outside software without remediation execution.",
    "Recommendation-only (review-only): re-run verification path imports for Sprint 158 "
    "and Sprint 157 builders to preserve regression continuity.",
)

_PACKET_EXIT_CRITERIA: tuple[str, ...] = (
    "Sprint 158 prerequisite is named as the human authorization handoff final "
    "no-execution decision brief with matching artifact type after Sprint 157 chain capstone.",
    "Verification path retains Sprint 158 handoff artifact type alongside Sprint 157 final "
    "rollup artifact type.",
    "Authorization chain closeout summary lists Sprints 149 through 158 with artifact "
    "type references.",
    "Roadmap pivot options, recommended pivot decision criteria, evidence and validation "
    "gap summary, blocked action summary, and human review dependency summary are present "
    "with zero actual counters.",
    "No-execution default, runtime authorization boundary, sprint 159 does not build list, "
    "risks, mitigations, and recommendation-only next safe action options are present.",
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "Closeout mistaken for runtime authorization or roadmap pivot execution",
        "State roadmap pivot execution is blocked, runtime authorization remains blocked, "
        "and keep explicit no runtime authorization granted and no board approval actually "
        "granted phrasing in boundary, blocked summary, and no-execution default.",
    ),
    (
        "Sprint 158 prerequisite skipped",
        "Bind prerequisite to Sprint 158 artifact type and section two sequencing after "
        "human authorization handoff final no-execution decision brief.",
    ),
    (
        "Sprint 158 or Sprint 157 verification path dropped",
        "Keep both artifact types in verification path keys and regression tests importing "
        "Sprint 158 and Sprint 157 builders.",
    ),
    (
        "Roadmap pivot option treated as executed pivot",
        "Separate written human approval from this packet and restate pivot options are "
        "human-only outside software with no roadmap pivot execution.",
    ),
)

_RECOMMENDED_NEXT_SAFE_ACTION = (
    "The recommended next safe action is recommendation-only and review-only: operators "
    "should retain Sprint 158 human authorization handoff final no-execution decision brief "
    "and Sprint 157 final runtime authorization packet index readiness rollup artifacts in "
    "the verification path, use this Sprint 159 closeout packet to make the next human "
    "roadmap pivot choice explicit, and perform human-only governance review without "
    "starting runtime execution, packet-chain execution, handoff execution, roadmap pivot "
    "execution, decision record execution, audit evidence execution, customer outreach, "
    "interview scheduling, customer onboarding, customer data access, database migration, "
    "source activation, production activation, pilot launch, real metric collection, real "
    "pilot closeout, optimization execution, architecture implementation, implementation "
    "execution, runtime authorization granted, board approval actually granted, post-board "
    "execution, remediation execution, evidence closure execution, re-review board convened, "
    "or runnable implementation workflow. Recorded human operator approval in a separate "
    "future authorization process would be required before any execution phase; Sprint 159 "
    "software does not perform that process."
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _closeout_rows() -> list[dict[str, str | int]]:
    return [dict(r) for r in _AUTHORIZATION_CHAIN_CLOSEOUT_SUMMARY]


def _gap_rows() -> list[dict[str, str]]:
    return [dict(r) for r in _EVIDENCE_AND_VALIDATION_GAP_SUMMARY]


def _risk_payloads() -> list[dict[str, str]]:
    return [{"risk": r, "mitigation": m} for r, m in _RISK_MITIGATIONS]


def build_active_source_activation_m1_no_execution_authorization_chain_closeout_roadmap_pivot_readiness_packet() -> (
    dict[str, Any]
):
    """Return the Sprint 159 M1 authorization chain closeout roadmap pivot readiness packet."""
    proof = {
        "sprint_159_m1_no_execution_authorization_chain_closeout_roadmap_pivot_readiness_is_stateless": True,
        "sprint_159_m1_no_execution_authorization_chain_closeout_roadmap_pivot_readiness_is_side_effect_free": True,
        "sprint_159_m1_no_execution_authorization_chain_closeout_roadmap_pivot_readiness_is_preview_only": True,
        "sprint_159_m1_no_execution_authorization_chain_closeout_roadmap_pivot_readiness_performs_no_runtime_work": True,
        "sprint_159_m1_no_execution_authorization_chain_closeout_roadmap_pivot_readiness_emits_operator_templates_only": True,
    }
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 159,
        "packet_name": (
            "NativeForge M1 No-Execution Authorization Chain Closeout & "
            "Roadmap Pivot Readiness Packet"
        ),
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_present_m1_no_execution_authorization_chain_closeout_roadmap_pivot_readiness_preview_only": True,
        "may_reference_m1_evidence_base_preview_only": True,
        "prerequisite_human_authorization_handoff_final_no_execution_decision_brief_sprint": 158,
        "prerequisite_human_authorization_handoff_final_no_execution_decision_brief_artifact_type": (
            _PREREQUISITE_SPRINT158_ARTIFACT_TYPE
        ),
        "verification_path_human_authorization_handoff_final_no_execution_decision_brief_sprint": 158,
        "verification_path_human_authorization_handoff_final_no_execution_decision_brief_artifact_type": (
            _VERIFICATION_SPRINT158_ARTIFACT_TYPE
        ),
        "verification_path_final_runtime_authorization_packet_index_readiness_rollup_sprint": 157,
        "verification_path_final_runtime_authorization_packet_index_readiness_rollup_artifact_type": (
            _VERIFICATION_SPRINT157_ARTIFACT_TYPE
        ),
        "actual_external_calls": 0,
        "actual_source_ingestions": 0,
        "actual_api_calls": 0,
        "actual_scrapes": 0,
        "actual_ai_generations": 0,
        "actual_form_submissions": 0,
        "actual_customer_data_access": 0,
        "actual_runtime_writes": 0,
        "actual_pilots_launched": 0,
        "actual_customer_onboarding_started": 0,
        "actual_production_systems_activated": 0,
        "actual_source_activations": 0,
        "actual_implementation_slices_executed": 0,
        "actual_customer_outreach_attempts": 0,
        "actual_interviews_scheduled": 0,
        "actual_remediation_executions": 0,
        "actual_evidence_closure_executions": 0,
        "actual_re_review_board_convened": 0,
        "actual_decision_record_executions": 0,
        "actual_audit_evidence_executions": 0,
        "actual_packet_chain_executions": 0,
        "actual_handoff_executions": 0,
        "actual_roadmap_pivot_executions": 0,
        "authorization_chain_closeout_summary": _closeout_rows(),
        "roadmap_pivot_options": list(_ROADMAP_PIVOT_OPTIONS),
        "recommended_pivot_decision_criteria": list(_RECOMMENDED_PIVOT_DECISION_CRITERIA),
        "evidence_and_validation_gap_summary": _gap_rows(),
        "blocked_action_summary": list(_BLOCKED_ACTION_SUMMARY),
        "human_review_dependency_summary": list(_HUMAN_REVIEW_DEPENDENCY_SUMMARY),
        "no_execution_default": list(_NO_EXECUTION_DEFAULT),
        "runtime_authorization_boundary": list(_RUNTIME_AUTHORIZATION_BOUNDARY),
        "sprint_159_does_not_build": list(_SPRINT159_DOES_NOT_BUILD),
        "next_safe_action_options": list(_NEXT_SAFE_ACTION_OPTIONS),
        "packet_exit_criteria": list(_PACKET_EXIT_CRITERIA),
        "risks_and_mitigations": _risk_payloads(),
        "recommended_next_safe_action": _RECOMMENDED_NEXT_SAFE_ACTION,
        "sprint_159_m1_no_execution_authorization_chain_closeout_roadmap_pivot_readiness_proof": proof,
    }
    return _json_safe(out)


def render_active_source_activation_m1_no_execution_authorization_chain_closeout_roadmap_pivot_readiness_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render operator markdown (deterministic; uses ``packet`` when provided)."""
    pkt = (
        packet
        if isinstance(packet, dict)
        else build_active_source_activation_m1_no_execution_authorization_chain_closeout_roadmap_pivot_readiness_packet()
    )
    lines: list[str] = [
        "# NativeForge M1 No-Execution Authorization Chain Closeout & "
        "Roadmap Pivot Readiness Packet v1",
        "",
        "## 1. Purpose",
        "",
        "This packet is a deterministic, preview-only operator artifact that closes the "
        "completed M1 no-execution runtime authorization readiness chain from Sprint 149 "
        "through Sprint 158 and defines roadmap pivot options for the next human choice "
        f"after the prerequisite `{_PREREQUISITE_SPRINT158_ARTIFACT_TYPE}` packet (Sprint 158). "
        "It does not grant runtime authorization, board approval actually granted, source "
        "activation, customer onboarding, pilot launch, production activation, post-board "
        "execution, remediation execution, evidence closure execution, re-review board "
        "convening, decision record execution, audit evidence execution, packet-chain "
        "execution, handoff execution, roadmap pivot execution, runtime execution, live "
        "customer data access, customer outreach, interview scheduling, external calls, "
        "database migrations, real metric collection, real pilot closeout, optimization "
        "execution, architecture implementation, implementation execution, or runnable "
        "implementation workflows.",
        "",
        "## 2. Why This Comes After Sprint 158",
        "",
        "Sprint 158 delivered the **human authorization handoff final no-execution decision "
        "brief**: it converts the Sprint 149–157 packet chain into human-readable decision "
        "language while keeping handoff execution and runtime authorization granted out of "
        "software. Sprint 159 **does not replace** that brief; it **depends** on Sprint 158 "
        "as mandatory prerequisite framing **after** the human authorization handoff exists, "
        "because only then can operators **close** the authorization chain documentation and "
        "make the **next roadmap pivot choice** explicit without implying execution. Sprint "
        "157 final rollup and Sprint 158 handoff lineages remain in the **verification path** "
        "for regression continuity. Sprint 159 adds closeout and roadmap-pivot readiness "
        "documentation only; it does not perform roadmap pivot execution, grant runtime "
        "authorization, board approval actually granted, or authorize any execution lane.",
        "",
        "## 3. No-Execution Chain Closeout Objective",
        "",
        "Provide documentation-only scaffolding that closes the no-execution runtime "
        "authorization readiness chain (Sprints 149–158), lists roadmap pivot options and "
        "pivot decision criteria, summarizes evidence and validation gaps, and recommends "
        "review-only next actions while keeping activation, launch, onboarding, measurement, "
        "closure, governance execution, handoff execution, and roadmap pivot execution "
        "lanes closed in this sprint.",
        "",
        "## 4. Authorization Chain Closeout Summary",
        "",
        "Closed chain packets (artifact types are template references; summary is not execution):",
        "",
    ]
    for row in pkt.get("authorization_chain_closeout_summary") or _closeout_rows():
        if not isinstance(row, dict):
            continue
        sp = row.get("sprint_number")
        title = row.get("packet_title")
        at = row.get("artifact_type")
        if isinstance(sp, int) and isinstance(title, str) and isinstance(at, str):
            lines.append(f"### Sprint {sp}")
            lines.append("")
            lines.append(title)
            lines.append("")
            lines.append(f"- Artifact type: `{at}`")
            lines.append("")
    lines.extend(["", "## 5. Roadmap Pivot Options", ""])
    for opt in pkt.get("roadmap_pivot_options") or list(_ROADMAP_PIVOT_OPTIONS):
        if isinstance(opt, str) and opt.strip():
            lines.append(f"- {opt}")
    lines.extend(
        [
            "",
            "## 6. Recommended Pivot Decision Criteria",
            "",
            "Criteria for human roadmap pivot choice (not executed here):",
            "",
        ]
    )
    for crit in pkt.get("recommended_pivot_decision_criteria") or list(
        _RECOMMENDED_PIVOT_DECISION_CRITERIA
    ):
        if isinstance(crit, str) and crit.strip():
            lines.append(f"- {crit}")
    lines.extend(
        [
            "",
            "## 7. Evidence and Validation Gap Summary",
            "",
            "Gap areas and preview-only status (not live ingestion):",
            "",
        ]
    )
    for row in pkt.get("evidence_and_validation_gap_summary") or _gap_rows():
        if not isinstance(row, dict):
            continue
        area = row.get("gap_area")
        st = row.get("gap_status")
        if isinstance(area, str) and area.strip():
            lines.append(f"### {area}")
            lines.append("")
        if isinstance(st, str) and st.strip():
            lines.append(st)
            lines.append("")
    lines.extend(["", "## 8. Blocked Action Summary", ""])
    for item in pkt.get("blocked_action_summary") or list(_BLOCKED_ACTION_SUMMARY):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 9. Human Review Dependency Summary", ""])
    for item in pkt.get("human_review_dependency_summary") or list(
        _HUMAN_REVIEW_DEPENDENCY_SUMMARY
    ):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 10. No-Execution Default", ""])
    for item in pkt.get("no_execution_default") or list(_NO_EXECUTION_DEFAULT):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 11. Runtime Authorization Boundary", ""])
    for item in pkt.get("runtime_authorization_boundary") or list(
        _RUNTIME_AUTHORIZATION_BOUNDARY
    ):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 12. What Sprint 159 Does Not Build",
            "",
            "Sprint 159 explicitly does not build:",
            "",
        ]
    )
    for item in pkt.get("sprint_159_does_not_build") or list(_SPRINT159_DOES_NOT_BUILD):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 13. Exit Criteria", ""])
    for c in pkt.get("packet_exit_criteria") or list(_PACKET_EXIT_CRITERIA):
        if isinstance(c, str) and c.strip():
            lines.append(f"- {c}")
    lines.extend(["", "## 14. Risks and Mitigations", ""])
    for row in pkt.get("risks_and_mitigations") or _risk_payloads():
        if isinstance(row, dict):
            r = row.get("risk")
            m = row.get("mitigation")
            if isinstance(r, str) and isinstance(m, str):
                lines.append(f"- **Risk**: {r} — **Mitigation**: {m}")
    lines.extend(
        [
            "",
            "## 15. Recommended Next Safe Action",
            "",
            "### Next safe action options (recommendation-only, review-only)",
            "",
        ]
    )
    for opt in pkt.get("next_safe_action_options") or list(_NEXT_SAFE_ACTION_OPTIONS):
        if isinstance(opt, str) and opt.strip():
            lines.append(f"- {opt}")
    lines.extend(
        [
            "",
            pkt.get("recommended_next_safe_action") or _RECOMMENDED_NEXT_SAFE_ACTION,
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
