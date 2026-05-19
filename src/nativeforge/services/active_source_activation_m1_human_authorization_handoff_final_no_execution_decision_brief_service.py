"""Sprint 158: M1 human authorization handoff & final no-execution decision brief (preview-only).

Deterministic operator artifact that converts the completed Sprint 149 through Sprint 157
runtime authorization readiness packet chain into a human-readable handoff brief for
Mayhem or another human reviewer. It does not grant runtime authorization, board approval
actually granted, customer onboarding, source activation, pilot launch, production activation,
packet-chain execution, decision record execution, audit evidence execution, evidence
closure execution, remediation execution, re-review board convening, handoff execution,
implementation execution, architecture implementation, live customer data access, customer
outreach, interview scheduling, external calls, database migrations, real metric collection,
real pilot closeout, optimization execution, or runnable implementation workflows.
Depends on Sprint 157 as mandatory prerequisite after the final runtime authorization packet
index readiness rollup; verification path retains Sprint 157 and Sprint 156 for regression
continuity.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_human_authorization_handoff_final_no_execution_decision_brief_v1"
)
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

_PREREQUISITE_SPRINT157_ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_final_runtime_authorization_packet_index_readiness_rollup_v1"
)
_VERIFICATION_SPRINT157_ARTIFACT_TYPE = _PREREQUISITE_SPRINT157_ARTIFACT_TYPE
_VERIFICATION_SPRINT156_ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_runtime_authorization_decision_record_audit_evidence_packet_v1"
)

_S149 = "nf_active_source_activation_m1_technical_architecture_review_runtime_boundary_packet_v1"
_S150 = "nf_active_source_activation_m1_bounded_implementation_design_human_gate_packet_v1"
_S151 = "nf_active_source_activation_m1_runtime_authorization_review_readiness_no_execution_packet_v1"
_S152 = "nf_active_source_activation_m1_human_runtime_authorization_board_packet_v1"
_S153 = "nf_active_source_activation_m1_post_board_decision_routing_next_safe_action_packet_v1"
_S154 = "nf_active_source_activation_m1_evidence_remediation_queue_re_review_packet_v1"
_S155 = "nf_active_source_activation_m1_re_review_board_readiness_evidence_closure_packet_v1"
_S156 = _VERIFICATION_SPRINT156_ARTIFACT_TYPE
_S157 = _PREREQUISITE_SPRINT157_ARTIFACT_TYPE

_PACKET_CHAIN_SUMMARY: tuple[dict[str, str | int], ...] = (
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
)

_HUMAN_DECISION_OPTIONS: tuple[str, ...] = (
    "Hold with no execution",
    "Request evidence remediation",
    "Request narrowed scope review",
    "Request additional security review",
    "Request additional sovereignty and trust review",
    "Request additional customer validation",
    "Prepare a separate future authorization process",
    "Decline runtime authorization",
    "Continue documentation-only planning",
    "Maintain no-execution default",
)

_EVIDENCE_STATUS_SUMMARY: tuple[dict[str, str], ...] = (
    {
        "evidence_area": "Security review",
        "status": (
            "Placeholder only: evidence narratives may exist in governance folders; "
            "Sprint 158 does not ingest live evidence or perform audit evidence execution."
        ),
    },
    {
        "evidence_area": "Sovereignty and trust",
        "status": (
            "Documentation-only handoff: sovereignty and trust completeness is for human "
            "judgment; software emits no trust attestation."
        ),
    },
    {
        "evidence_area": "Customer validation",
        "status": (
            "Preview-only status: customer validation planning may be referenced from prior "
            "sprints; no customer data access or customer outreach from this brief."
        ),
    },
    {
        "evidence_area": "Technical architecture",
        "status": (
            "Indexed from Sprint 149 boundary packet; architecture implementation remains "
            "blocked in software outputs."
        ),
    },
    {
        "evidence_area": "Decision record and audit export",
        "status": (
            "Sprint 156 templates referenced; decision record execution and audit evidence "
            "execution counters remain zero."
        ),
    },
    {
        "evidence_area": "Human approval",
        "status": (
            "Written human approval is explicitly separated from this packet; this brief is "
            "not an approval substitute."
        ),
    },
)

_BLOCKED_ACTION_SUMMARY: tuple[str, ...] = (
    "Handoff brief emission is not handoff execution and does not activate systems.",
    "Human decision options are documentation templates only; selecting an option in "
    "software is impossible—humans decide outside this artifact.",
    "Packet chain summary references Sprints 149–157 without packet-chain execution.",
    "No runtime authorization granted and no board approval actually granted from "
    "Sprint 158 software.",
    "No pilot launch, customer outreach, interview scheduling, or customer onboarding.",
    "No source activation, production activation, or database migration.",
    "No customer data access, real metric collection, or real pilot closeout.",
    "No optimization execution, architecture implementation, or implementation execution.",
    "No post-board execution, remediation execution, evidence closure execution, or "
    "re-review board convened in software.",
    "No decision record execution, audit evidence execution, or runnable implementation "
    "workflow may begin from this brief.",
    "All execution-class actions remain blocked by default until separate human "
    "authorization outside this brief.",
)

_RECOMMENDED_HUMAN_REVIEW_QUESTIONS: tuple[str, ...] = (
    "Is the implementation scope bounded enough for a future review?",
    "Is customer data access still blocked?",
    "Is source activation still blocked?",
    "Is production activation still blocked?",
    "Is pilot launch still blocked?",
    "Is database migration still blocked?",
    "Is sovereignty and trust review complete enough?",
    "Is security review complete enough?",
    "Is customer validation complete enough?",
    "Is written human approval explicitly separated from this packet?",
)

_DECISION_BRIEF_TEMPLATE: tuple[dict[str, str], ...] = (
    {
        "field_name": "Reviewer identity (human-only)",
        "description": (
            "Reserved for the human reviewer name or role; Sprint 158 does not collect "
            "or store live identity data."
        ),
    },
    {
        "field_name": "Review date (human-only)",
        "description": (
            "Reserved for a human-recorded review date; deterministic packet uses fixed "
            "generated_at only as a template timestamp."
        ),
    },
    {
        "field_name": "Selected human decision option",
        "description": (
            "One of the documented human decision options chosen outside software; this "
            "field is a template slot, not an executed decision."
        ),
    },
    {
        "field_name": "Rationale summary",
        "description": (
            "Free-text narrative for why the selected option applies; must be authored by "
            "humans— not generated as authorization by this service."
        ),
    },
    {
        "field_name": "Evidence gaps noted",
        "description": (
            "List of evidence areas requiring remediation or additional review; noting gaps "
            "is not remediation execution."
        ),
    },
    {
        "field_name": "Blocked actions acknowledged",
        "description": (
            "Attestation that execution lanes remain blocked until a separate future "
            "authorization process if ever approved."
        ),
    },
    {
        "field_name": "Written human approval reference",
        "description": (
            "Pointer to explicit written human approval outside this packet when applicable; "
            "this brief never substitutes written human approval."
        ),
    },
    {
        "field_name": "Next safe action (human-only)",
        "description": (
            "Human-authored next step such as hold, remediate evidence, or prepare a separate "
            "future authorization process— not software execution."
        ),
    },
)

_NO_EXECUTION_DEFAULT: tuple[str, ...] = (
    "No-execution default: Sprint 158 emits a human authorization handoff and final "
    "no-execution decision brief only; runtime execution, packet-chain execution, handoff "
    "execution, activation, launch, onboarding, outreach, scheduling, board convening, "
    "remediation execution, evidence closure execution, decision record execution, and "
    "audit evidence execution remain closed in software.",
    "No-execution default: no pilot launch, no customer outreach, no interview scheduling, "
    "no customer onboarding, no customer data access, no database migration, no source "
    "activation, no production activation, no real metric collection, no real pilot "
    "closeout, no optimization execution, no architecture implementation, no implementation "
    "execution, no runtime authorization granted, no board approval actually granted, no "
    "post-board execution, no remediation execution, no evidence closure execution, no "
    "re-review board convened, no decision record execution, no audit evidence execution, "
    "no packet-chain execution, no handoff execution, and no runnable implementation "
    "workflow may begin from this packet.",
    "No-execution default: deterministic markdown and dict output are preview-only; human "
    "operator approval for any execution phase remains mandatory and external.",
)

_RUNTIME_AUTHORIZATION_BOUNDARY: tuple[str, ...] = (
    "Runtime authorization boundary: Sprint 158 summarizes Sprint 149–157 packets as "
    "documentation lineage for human review; it grants no runtime authorization granted "
    "and no board approval actually granted.",
    "Runtime authorization boundary: preview-only deterministic dict and markdown emission "
    "only; no runtime writes, workers, external calls, packet-chain execution, handoff "
    "execution, decision record execution, audit evidence execution, evidence closure "
    "execution, remediation execution, post-board execution, re-review board convened, "
    "or pilot launch.",
    "Runtime authorization boundary: human decision options and decision brief template "
    "fields must not be interpreted as authorization to execute, activate, migrate, "
    "onboard, export live data, or convene governance bodies from this codebase.",
)

_SPRINT158_DOES_NOT_BUILD: tuple[str, ...] = (
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
    "Recommendation-only (review-only): read this handoff brief alongside Sprint 157 "
    "rollup indices as a desk exercise—no software execution.",
    "Recommendation-only (review-only): answer recommended human review questions in a "
    "human-maintained decision log without customer outreach or interview scheduling.",
    "Recommendation-only (review-only): if evidence gaps remain, document remediation "
    "requests outside software without remediation execution.",
    "Recommendation-only (review-only): re-run verification path imports for Sprint 157 "
    "and Sprint 156 builders to preserve regression continuity.",
)

_PACKET_EXIT_CRITERIA: tuple[str, ...] = (
    "Sprint 157 prerequisite is named as the final runtime authorization packet index "
    "readiness rollup with matching artifact type after Sprint 156 chain capstone.",
    "Verification path retains Sprint 157 final rollup artifact type alongside Sprint 156 "
    "decision record audit evidence artifact type.",
    "Packet chain summary lists Sprints 149 through 157 with artifact type references.",
    "Human decision options, evidence status summary, blocked action summary, recommended "
    "human review questions, and decision brief template are present with zero actual "
    "counters.",
    "No-execution default, runtime authorization boundary, sprint 158 does not build list, "
    "risks, mitigations, and recommendation-only next safe action options are present.",
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "Handoff brief mistaken for authorization or handoff execution",
        "State handoff execution is blocked, runtime authorization remains blocked, and "
        "keep explicit no runtime authorization granted and no board approval actually "
        "granted phrasing in boundary, blocked summary, and no-execution default.",
    ),
    (
        "Sprint 157 prerequisite skipped",
        "Bind prerequisite to Sprint 157 artifact type and section two sequencing after "
        "final runtime authorization packet index readiness rollup.",
    ),
    (
        "Sprint 157 or Sprint 156 verification path dropped",
        "Keep both artifact types in verification path keys and regression tests importing "
        "Sprint 157 and Sprint 156 builders.",
    ),
    (
        "Decision brief template treated as executed decision",
        "Separate written human approval from this packet and restate decision options are "
        "human-only outside software.",
    ),
)

_RECOMMENDED_NEXT_SAFE_ACTION = (
    "The recommended next safe action is recommendation-only and review-only: operators "
    "should retain Sprint 157 final runtime authorization packet index readiness rollup "
    "and Sprint 156 runtime authorization decision record and audit evidence artifacts in "
    "the verification path, use this Sprint 158 handoff brief as a documentation-only "
    "human decision aid, and perform human-only governance review without starting runtime "
    "execution, packet-chain execution, handoff execution, decision record execution, audit "
    "evidence execution, customer outreach, interview scheduling, customer onboarding, "
    "customer data access, database migration, source activation, production activation, "
    "pilot launch, real metric collection, real pilot closeout, optimization execution, "
    "architecture implementation, implementation execution, runtime authorization granted, "
    "board approval actually granted, post-board execution, remediation execution, evidence "
    "closure execution, re-review board convened, or runnable implementation workflow. "
    "Recorded human operator approval in a separate future authorization process would be "
    "required before any execution phase; Sprint 158 software does not perform that process."
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _chain_rows() -> list[dict[str, str | int]]:
    return [dict(r) for r in _PACKET_CHAIN_SUMMARY]


def _evidence_rows() -> list[dict[str, str]]:
    return [dict(r) for r in _EVIDENCE_STATUS_SUMMARY]


def _template_rows() -> list[dict[str, str]]:
    return [dict(r) for r in _DECISION_BRIEF_TEMPLATE]


def _risk_payloads() -> list[dict[str, str]]:
    return [{"risk": r, "mitigation": m} for r, m in _RISK_MITIGATIONS]


def build_active_source_activation_m1_human_authorization_handoff_final_no_execution_decision_brief() -> (
    dict[str, Any]
):
    """Return the Sprint 158 M1 human authorization handoff decision brief."""
    proof = {
        "sprint_158_m1_human_authorization_handoff_final_no_execution_decision_brief_is_stateless": True,
        "sprint_158_m1_human_authorization_handoff_final_no_execution_decision_brief_is_side_effect_free": True,
        "sprint_158_m1_human_authorization_handoff_final_no_execution_decision_brief_is_preview_only": True,
        "sprint_158_m1_human_authorization_handoff_final_no_execution_decision_brief_performs_no_runtime_work": True,
        "sprint_158_m1_human_authorization_handoff_final_no_execution_decision_brief_emits_operator_templates_only": True,
    }
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 158,
        "packet_name": (
            "NativeForge M1 Human Authorization Handoff & Final No-Execution Decision Brief"
        ),
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_present_m1_human_authorization_handoff_final_no_execution_decision_brief_preview_only": True,
        "may_reference_m1_evidence_base_preview_only": True,
        "prerequisite_final_runtime_authorization_packet_index_readiness_rollup_sprint": 157,
        "prerequisite_final_runtime_authorization_packet_index_readiness_rollup_artifact_type": (
            _PREREQUISITE_SPRINT157_ARTIFACT_TYPE
        ),
        "verification_path_final_runtime_authorization_packet_index_readiness_rollup_sprint": 157,
        "verification_path_final_runtime_authorization_packet_index_readiness_rollup_artifact_type": (
            _VERIFICATION_SPRINT157_ARTIFACT_TYPE
        ),
        "verification_path_runtime_authorization_decision_record_audit_evidence_sprint": 156,
        "verification_path_runtime_authorization_decision_record_audit_evidence_artifact_type": (
            _VERIFICATION_SPRINT156_ARTIFACT_TYPE
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
        "packet_chain_summary": _chain_rows(),
        "human_decision_options": list(_HUMAN_DECISION_OPTIONS),
        "evidence_status_summary": _evidence_rows(),
        "blocked_action_summary": list(_BLOCKED_ACTION_SUMMARY),
        "recommended_human_review_questions": list(_RECOMMENDED_HUMAN_REVIEW_QUESTIONS),
        "decision_brief_template": _template_rows(),
        "no_execution_default": list(_NO_EXECUTION_DEFAULT),
        "runtime_authorization_boundary": list(_RUNTIME_AUTHORIZATION_BOUNDARY),
        "sprint_158_does_not_build": list(_SPRINT158_DOES_NOT_BUILD),
        "next_safe_action_options": list(_NEXT_SAFE_ACTION_OPTIONS),
        "packet_exit_criteria": list(_PACKET_EXIT_CRITERIA),
        "risks_and_mitigations": _risk_payloads(),
        "recommended_next_safe_action": _RECOMMENDED_NEXT_SAFE_ACTION,
        "sprint_158_m1_human_authorization_handoff_final_no_execution_decision_brief_proof": proof,
    }
    return _json_safe(out)


def render_active_source_activation_m1_human_authorization_handoff_final_no_execution_decision_brief_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render operator markdown (deterministic; uses ``packet`` when provided)."""
    pkt = (
        packet
        if isinstance(packet, dict)
        else build_active_source_activation_m1_human_authorization_handoff_final_no_execution_decision_brief()
    )
    lines: list[str] = [
        "# NativeForge M1 Human Authorization Handoff & Final No-Execution Decision Brief v1",
        "",
        "## 1. Purpose",
        "",
        "This packet is a deterministic, preview-only operator artifact that converts the "
        "completed M1 runtime authorization readiness packet chain from Sprint 149 through "
        f"Sprint 157 into a human-readable handoff brief for Mayhem or another human reviewer "
        f"after the prerequisite `{_PREREQUISITE_SPRINT157_ARTIFACT_TYPE}` packet (Sprint 157). "
        "It does not grant runtime authorization, board approval actually granted, source "
        "activation, customer onboarding, pilot launch, production activation, post-board "
        "execution, remediation execution, evidence closure execution, re-review board "
        "convening, decision record execution, audit evidence execution, packet-chain "
        "execution, handoff execution, runtime execution, live customer data access, customer "
        "outreach, interview scheduling, external calls, database migrations, real metric "
        "collection, real pilot closeout, optimization execution, architecture implementation, "
        "implementation execution, or runnable implementation workflows.",
        "",
        "## 2. Why This Comes After Sprint 157",
        "",
        "Sprint 157 delivered the **final runtime authorization packet index and readiness "
        "rollup**: it indexes Sprints 149–156 and rolls up readiness categories while "
        "keeping packet-chain execution and runtime authorization granted out of software. "
        "Sprint 158 **does not replace** that rollup; it **depends** on Sprint 157 as "
        "mandatory prerequisite framing **after** the final packet index exists, because "
        "only then can operators receive a **human authorization handoff** that explains why "
        "Sprint 158 follows the **final runtime authorization packet index** and converts "
        "the full chain into decision-oriented language without implying execution. Sprint "
        "156 decision record and audit evidence and Sprint 157 index lineages remain in the "
        "**verification path** for regression continuity. Sprint 158 adds handoff and "
        "decision-brief documentation only; it does not perform handoff execution, grant "
        "runtime authorization, board approval actually granted, or authorize any execution "
        "lane.",
        "",
        "## 3. Human Authorization Handoff Objective",
        "",
        "Provide documentation-only scaffolding that summarizes the runtime authorization "
        "readiness chain (Sprints 149–157), lists human decision options and review "
        "questions, supplies a decision brief template, and recommends review-only next "
        "actions while keeping activation, launch, onboarding, measurement, closure, "
        "governance execution, and handoff execution lanes closed in this sprint.",
        "",
        "## 4. Packet Chain Summary",
        "",
        "Summarized packets (artifact types are template references; summary is not execution):",
        "",
    ]
    for row in pkt.get("packet_chain_summary") or _chain_rows():
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
    lines.extend(["", "## 5. Human Decision Options", ""])
    for opt in pkt.get("human_decision_options") or list(_HUMAN_DECISION_OPTIONS):
        if isinstance(opt, str) and opt.strip():
            lines.append(f"- {opt}")
    lines.extend(
        [
            "",
            "## 6. Evidence Status Summary",
            "",
            "Evidence areas and preview-only status (not live ingestion):",
            "",
        ]
    )
    for row in pkt.get("evidence_status_summary") or _evidence_rows():
        if not isinstance(row, dict):
            continue
        area = row.get("evidence_area")
        st = row.get("status")
        if isinstance(area, str) and area.strip():
            lines.append(f"### {area}")
            lines.append("")
        if isinstance(st, str) and st.strip():
            lines.append(st)
            lines.append("")
    lines.extend(["", "## 7. Blocked Action Summary", ""])
    for item in pkt.get("blocked_action_summary") or list(_BLOCKED_ACTION_SUMMARY):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 8. Recommended Human Review Questions", ""])
    for q in pkt.get("recommended_human_review_questions") or list(
        _RECOMMENDED_HUMAN_REVIEW_QUESTIONS
    ):
        if isinstance(q, str) and q.strip():
            lines.append(f"- {q}")
    lines.extend(
        [
            "",
            "## 9. Decision Brief Template",
            "",
            "Template fields for human-authored decision briefs (not executed here):",
            "",
        ]
    )
    for row in pkt.get("decision_brief_template") or _template_rows():
        if not isinstance(row, dict):
            continue
        fn = row.get("field_name")
        desc = row.get("description")
        if isinstance(fn, str) and fn.strip():
            lines.append(f"### {fn}")
            lines.append("")
        if isinstance(desc, str) and desc.strip():
            lines.append(desc)
            lines.append("")
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
            "## 12. What Sprint 158 Does Not Build",
            "",
            "Sprint 158 explicitly does not build:",
            "",
        ]
    )
    for item in pkt.get("sprint_158_does_not_build") or list(_SPRINT158_DOES_NOT_BUILD):
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
