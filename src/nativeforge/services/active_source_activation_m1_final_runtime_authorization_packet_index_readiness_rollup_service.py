"""Sprint 157: M1 final runtime authorization packet index & readiness rollup (preview-only).

Deterministic operator artifact that indexes and rolls up the runtime authorization readiness
chain from Sprint 149 through Sprint 156 after Sprint 156's Runtime Authorization Decision
Record & Audit Evidence Packet. It summarizes packet dependencies, readiness categories,
evidence placeholders, blocked-action rules, human review dependencies, and decision record /
audit evidence lineage—without granting runtime authorization, board approval actually
granted, source activation, customer onboarding, pilot launch, production activation,
post-board execution, remediation execution, evidence closure execution, re-review board
convening, decision record execution, audit evidence execution, packet-chain execution,
implementation execution, architecture implementation, live customer data access, customer
outreach, interview scheduling, external calls, database migrations, real metric collection,
real pilot closeout, optimization execution, or runnable implementation workflows.
Depends on Sprint 156 as mandatory prerequisite after decision record and audit evidence
templates exist; verification path retains Sprint 156 and Sprint 155 for regression
continuity.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_final_runtime_authorization_packet_index_readiness_rollup_v1"
)
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

_PREREQUISITE_SPRINT156_ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_runtime_authorization_decision_record_audit_evidence_packet_v1"
)
_VERIFICATION_SPRINT156_ARTIFACT_TYPE = _PREREQUISITE_SPRINT156_ARTIFACT_TYPE
_VERIFICATION_SPRINT155_ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_re_review_board_readiness_evidence_closure_packet_v1"
)

_S149 = "nf_active_source_activation_m1_technical_architecture_review_runtime_boundary_packet_v1"
_S150 = "nf_active_source_activation_m1_bounded_implementation_design_human_gate_packet_v1"
_S151 = "nf_active_source_activation_m1_runtime_authorization_review_readiness_no_execution_packet_v1"
_S152 = "nf_active_source_activation_m1_human_runtime_authorization_board_packet_v1"
_S153 = "nf_active_source_activation_m1_post_board_decision_routing_next_safe_action_packet_v1"
_S154 = "nf_active_source_activation_m1_evidence_remediation_queue_re_review_packet_v1"
_S155 = _VERIFICATION_SPRINT155_ARTIFACT_TYPE
_S156 = _PREREQUISITE_SPRINT156_ARTIFACT_TYPE

_PACKET_CHAIN_INDEX: tuple[dict[str, str | int], ...] = (
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
)

_READINESS_ROLLUP_MODEL: tuple[dict[str, str], ...] = (
    {
        "readiness_category": "Technical architecture boundary readiness",
        "rollup_status": (
            "Documentation-only index: Sprint 149 runtime boundary packet is listed in the "
            "chain; software emits no architecture implementation and performs no runtime "
            "authorization."
        ),
    },
    {
        "readiness_category": "Bounded implementation design readiness",
        "rollup_status": (
            "Index position only: Sprint 150 human-gated design packet precedes review "
            "readiness; this rollup does not authorize implementation execution."
        ),
    },
    {
        "readiness_category": "Runtime authorization review readiness",
        "rollup_status": (
            "Sprint 151 no-execution review readiness is referenced as a chain dependency; "
            "readiness labels are not runtime authorization granted."
        ),
    },
    {
        "readiness_category": "Human board review readiness",
        "rollup_status": (
            "Sprint 152 board packet is indexed; human board convening and outcomes remain "
            "outside this preview rollup."
        ),
    },
    {
        "readiness_category": "Post-board decision routing readiness",
        "rollup_status": (
            "Sprint 153 routing packet is listed for traceability; post-board execution stays "
            "blocked in software outputs."
        ),
    },
    {
        "readiness_category": "Evidence remediation readiness",
        "rollup_status": (
            "Sprint 154 remediation queue packet is indexed; remediation execution is not "
            "performed by this service."
        ),
    },
    {
        "readiness_category": "Re-review and evidence closure readiness",
        "rollup_status": (
            "Sprint 155 re-review and evidence closure packet is listed; evidence closure "
            "execution and re-review board convening are blocked here."
        ),
    },
    {
        "readiness_category": "Decision record and audit evidence readiness",
        "rollup_status": (
            "Sprint 156 decision record and audit evidence packet is prerequisite; decision "
            "record execution and audit evidence execution remain zero in actual_* counters."
        ),
    },
    {
        "readiness_category": "Human approval dependency",
        "rollup_status": (
            "All execution-class actions require separate human approval; preview indices "
            "and rollups are not approval substitutes."
        ),
    },
    {
        "readiness_category": "Runtime authorization remains blocked",
        "rollup_status": (
            "No runtime authorization granted and no board approval actually granted from "
            "Sprint 157 software; boundary language is restated in this packet."
        ),
    },
)

_EVIDENCE_COVERAGE_SUMMARY: tuple[str, ...] = (
    "Security review evidence placeholder",
    "Sovereignty and trust evidence placeholder",
    "Customer validation evidence placeholder",
    "Technical architecture evidence placeholder",
    "Rollback and support evidence placeholder",
    "Data handling and export evidence placeholder",
    "Human approval evidence placeholder",
    "Denial and deferral evidence placeholder",
    "Audit export evidence placeholder",
    "Decision record evidence placeholder",
)

_BLOCKED_ACTION_ROLLUP: tuple[str, ...] = (
    "Packet-chain indexing is not packet-chain execution.",
    "Readiness rollup emission is not runtime authorization granted.",
    "Evidence coverage placeholders are not live evidence ingestion or audit evidence "
    "execution.",
    "This sprint does not convene a re-review board or close evidence in live systems.",
    "This sprint does not execute remediation, post-board execution, or decision record "
    "execution.",
    "No pilot launch, customer outreach, interview scheduling, or customer onboarding may "
    "derive from this rollup.",
    "No source activation, production activation, or database migration may derive from "
    "this rollup.",
    "No customer data access, real metric collection, or real pilot closeout may run from "
    "this artifact.",
    "No optimization execution, architecture implementation, or implementation execution is "
    "authorized by preview indices.",
    "Runnable implementation workflows remain disallowed outputs from this sprint.",
)

_HUMAN_REVIEW_DEPENDENCY_SUMMARY: tuple[str, ...] = (
    "Human review dependency: runtime authorization and board outcomes require governance "
    "outside this repository; Sprint 157 only documents the indexed chain.",
    "Human review dependency: Sprint 152 board packet and Sprint 156 decision record models "
    "assume future human-authored records not emitted as execution here.",
    "Human review dependency: Sprint 155 evidence closure and Sprint 154 remediation queue "
    "artifacts presuppose human-operated processes when execution is separately approved.",
    "Human review dependency: recommendation-only next actions must be desk review and "
    "operator planning without activating systems or convening boards in software.",
)

_DECISION_RECORD_AND_AUDIT_EVIDENCE_SUMMARY: tuple[str, ...] = (
    "Decision record and audit evidence summary: Sprint 156 is the prerequisite runtime "
    f"authorization decision record audit evidence packet (artifact type `{_S156}`) after "
    "Sprint 155; it defines decision record scaffolding and audit evidence checklists preview-only.",
    "Decision record and audit evidence summary: Sprint 157 aggregates indices after that "
    "packet exists so operators see end-to-end readiness documentation without executing "
    "decision record execution or audit evidence execution.",
    "Decision record and audit evidence summary: actual_decision_record_executions and "
    "actual_audit_evidence_executions remain zero; templates are not operational decisions.",
)

_NO_EXECUTION_DEFAULT: tuple[str, ...] = (
    "No-execution default: Sprint 157 emits a final packet index and readiness rollup only; "
    "runtime execution, packet-chain execution, activation, launch, onboarding, outreach, "
    "scheduling, board convening, remediation execution, evidence closure execution, decision "
    "record execution, and audit evidence execution remain closed in software.",
    "No-execution default: no pilot launch, no customer outreach, no interview scheduling, "
    "no customer onboarding, no customer data access, no database migration, no source "
    "activation, no production activation, no real metric collection, no real pilot "
    "closeout, no optimization execution, no architecture implementation, no implementation "
    "execution, no runtime authorization granted, no board approval actually granted, no "
    "post-board execution, no remediation execution, no evidence closure execution, no "
    "re-review board convened, no decision record execution, no audit evidence execution, "
    "no packet-chain execution, and no runnable implementation workflow may begin from this "
    "packet.",
    "No-execution default: deterministic markdown and dict output are preview-only; human "
    "operator approval for any execution phase remains mandatory and external.",
)

_RUNTIME_AUTHORIZATION_BOUNDARY: tuple[str, ...] = (
    "Runtime authorization boundary: Sprint 157 indexes Sprint 149–156 packets as "
    "documentation lineage; it grants no runtime authorization granted and no board "
    "approval actually granted.",
    "Runtime authorization boundary: preview-only deterministic dict and markdown emission "
    "only; no runtime writes, workers, external calls, packet-chain execution, decision "
    "record execution, audit evidence execution, evidence closure execution, remediation "
    "execution, post-board execution, re-review board convened, or pilot launch.",
    "Runtime authorization boundary: readiness rollup categories and evidence placeholders "
    "must not be interpreted as authorization to execute, activate, migrate, onboard, export "
    "live data, or convene governance bodies from this codebase.",
)

_SPRINT157_DOES_NOT_BUILD: tuple[str, ...] = (
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
    "Recommendation-only (review-only): walk the packet chain index against governance "
    "folders as a desk exercise—no software execution.",
    "Recommendation-only (review-only): confirm Sprint 156 decision record and audit "
    "evidence templates align with Sprint 155 closure narratives without evidence closure "
    "execution.",
    "Recommendation-only (review-only): re-run verification path imports for Sprint 156 and "
    "Sprint 155 builders to preserve regression continuity.",
    "Recommendation-only (review-only): if human approval is incomplete, document deferral "
    "outside software without customer outreach or interview scheduling.",
)

_PACKET_EXIT_CRITERIA: tuple[str, ...] = (
    "Sprint 156 prerequisite is named as the runtime authorization decision record and audit "
    "evidence packet with matching artifact type after Sprint 155 templates.",
    "Verification path retains Sprint 156 decision record audit evidence artifact type "
    "alongside Sprint 155 re-review board readiness evidence closure artifact type.",
    "Packet chain index lists Sprints 149 through 156 with artifact type references.",
    "Readiness rollup model enumerates all mandated readiness categories with zero actual "
    "counters.",
    "Evidence coverage summary lists all mandated evidence placeholders; blocked action "
    "rollup, human review dependency summary, and decision record and audit evidence summary "
    "are present.",
    "No-execution default, runtime authorization boundary, sprint 157 does not build list, "
    "risks, mitigations, and recommendation-only next safe action options are present.",
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "Index mistaken for authorization or packet-chain execution",
        "State packet-chain execution is blocked, runtime authorization remains blocked, and "
        "keep explicit no runtime authorization granted and no board approval actually "
        "granted phrasing in boundary, blocked rollup, and no-execution default.",
    ),
    (
        "Sprint 156 prerequisite skipped",
        "Bind prerequisite to Sprint 156 artifact type and section two sequencing after "
        "runtime authorization decision record and audit evidence packet.",
    ),
    (
        "Sprint 156 or Sprint 155 verification path dropped",
        "Keep both artifact types in verification path keys and regression tests importing "
        "Sprint 156 and Sprint 155 builders.",
    ),
    (
        "Readiness labels treated as sufficient for runtime",
        "Restate runtime authorization remains blocked and human approval dependency in "
        "readiness rollup narratives.",
    ),
)

_RECOMMENDED_NEXT_SAFE_ACTION = (
    "The recommended next safe action is recommendation-only and review-only: operators "
    "should retain Sprint 156 runtime authorization decision record and audit evidence "
    "packets and Sprint 155 re-review readiness evidence closure artifacts in the "
    "verification path, use this Sprint 157 rollup as a documentation-only chain index, "
    "and perform human-only governance review without starting runtime execution, "
    "packet-chain execution, decision record execution, audit evidence execution, customer "
    "outreach, interview scheduling, customer onboarding, customer data access, database "
    "migration, source activation, production activation, pilot launch, real metric "
    "collection, real pilot closeout, optimization execution, architecture implementation, "
    "implementation execution, runtime authorization granted, board approval actually "
    "granted, post-board execution, remediation execution, evidence closure execution, "
    "re-review board convened, or runnable implementation workflow. Recorded human operator "
    "approval in a separate future authorization process would be required before any "
    "execution phase; Sprint 157 software does not perform that process."
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _chain_rows() -> list[dict[str, str | int]]:
    return [dict(r) for r in _PACKET_CHAIN_INDEX]


def _readiness_rows() -> list[dict[str, str]]:
    return [dict(r) for r in _READINESS_ROLLUP_MODEL]


def _risk_payloads() -> list[dict[str, str]]:
    return [{"risk": r, "mitigation": m} for r, m in _RISK_MITIGATIONS]


def build_active_source_activation_m1_final_runtime_authorization_packet_index_readiness_rollup() -> (
    dict[str, Any]
):
    """Return the Sprint 157 M1 final packet index & readiness rollup."""
    proof = {
        "sprint_157_m1_final_packet_index_readiness_rollup_is_stateless": True,
        "sprint_157_m1_final_packet_index_readiness_rollup_is_side_effect_free": True,
        "sprint_157_m1_final_packet_index_readiness_rollup_is_preview_only": True,
        "sprint_157_m1_final_packet_index_readiness_rollup_performs_no_runtime_work": True,
        "sprint_157_m1_final_packet_index_readiness_rollup_emits_operator_templates_only": True,
    }
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 157,
        "packet_name": (
            "NativeForge M1 Final Runtime Authorization Packet Index & Readiness Rollup"
        ),
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_present_m1_final_runtime_authorization_packet_index_readiness_rollup_preview_only": True,
        "may_reference_m1_evidence_base_preview_only": True,
        "prerequisite_runtime_authorization_decision_record_audit_evidence_sprint": 156,
        "prerequisite_runtime_authorization_decision_record_audit_evidence_artifact_type": (
            _PREREQUISITE_SPRINT156_ARTIFACT_TYPE
        ),
        "verification_path_runtime_authorization_decision_record_audit_evidence_sprint": 156,
        "verification_path_runtime_authorization_decision_record_audit_evidence_artifact_type": (
            _VERIFICATION_SPRINT156_ARTIFACT_TYPE
        ),
        "verification_path_re_review_board_readiness_evidence_closure_sprint": 155,
        "verification_path_re_review_board_readiness_evidence_closure_artifact_type": (
            _VERIFICATION_SPRINT155_ARTIFACT_TYPE
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
        "packet_chain_index": _chain_rows(),
        "readiness_rollup_model": _readiness_rows(),
        "evidence_coverage_summary": list(_EVIDENCE_COVERAGE_SUMMARY),
        "blocked_action_rollup": list(_BLOCKED_ACTION_ROLLUP),
        "human_review_dependency_summary": list(_HUMAN_REVIEW_DEPENDENCY_SUMMARY),
        "decision_record_and_audit_evidence_summary": list(
            _DECISION_RECORD_AND_AUDIT_EVIDENCE_SUMMARY
        ),
        "no_execution_default": list(_NO_EXECUTION_DEFAULT),
        "runtime_authorization_boundary": list(_RUNTIME_AUTHORIZATION_BOUNDARY),
        "sprint_157_does_not_build": list(_SPRINT157_DOES_NOT_BUILD),
        "next_safe_action_options": list(_NEXT_SAFE_ACTION_OPTIONS),
        "packet_exit_criteria": list(_PACKET_EXIT_CRITERIA),
        "risks_and_mitigations": _risk_payloads(),
        "recommended_next_safe_action": _RECOMMENDED_NEXT_SAFE_ACTION,
        "sprint_157_m1_final_runtime_authorization_packet_index_readiness_rollup_proof": proof,
    }
    return _json_safe(out)


def render_active_source_activation_m1_final_runtime_authorization_packet_index_readiness_rollup_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render operator markdown (deterministic; uses ``packet`` when provided)."""
    pkt = (
        packet
        if isinstance(packet, dict)
        else build_active_source_activation_m1_final_runtime_authorization_packet_index_readiness_rollup()
    )
    lines: list[str] = [
        "# NativeForge M1 Final Runtime Authorization Packet Index & Readiness Rollup v1",
        "",
        "## 1. Purpose",
        "",
        "This packet is a deterministic, preview-only operator artifact that indexes and rolls "
        "up the M1 runtime authorization readiness chain from Sprint 149 through Sprint 156 "
        f"after the prerequisite `{_PREREQUISITE_SPRINT156_ARTIFACT_TYPE}` packet (Sprint 156). "
        "It does not grant runtime authorization, board approval actually granted, source "
        "activation, customer onboarding, pilot launch, production activation, post-board "
        "execution, remediation execution, evidence closure execution, re-review board "
        "convening, decision record execution, audit evidence execution, packet-chain "
        "execution, runtime execution, live customer data access, customer outreach, interview "
        "scheduling, external calls, database migrations, real metric collection, real pilot "
        "closeout, optimization execution, architecture implementation, implementation "
        "execution, or runnable implementation workflows.",
        "",
        "## 2. Why This Comes After Sprint 156",
        "",
        "Sprint 156 delivered the **runtime authorization decision record and audit evidence** "
        "packet: it defines how a future decision record and audit evidence binder would be "
        "structured while keeping decision record execution, audit evidence execution, and "
        "runtime authorization granted out of software. Sprint 157 **does not replace** that "
        "artifact; it **depends** on Sprint 156 as mandatory prerequisite framing **after** "
        "decision record and audit evidence templates exist, because only then can operators "
        "safely produce a **final chain-wide index** and **readiness rollup** that references "
        "the full Sprint 149–156 sequence—including governance, board, remediation, re-review, "
        "and closure packets—without implying execution. Sprint 155 re-review board readiness "
        "and evidence closure and Sprint 156 decision record lineages remain in the **"
        "verification path** for regression continuity. Sprint 157 adds index and rollup "
        "documentation only; it does not perform packet-chain execution, grant runtime "
        "authorization, board approval actually granted, or authorize any execution lane.",
        "",
        "## 3. Final Runtime Authorization Packet Index Objective",
        "",
        "Provide documentation-only scaffolding that lists each packet in the runtime "
        "authorization readiness sequence (Sprints 149–156), rolls up readiness categories and "
        "evidence placeholders, preserves blocked-action rules, and recommends review-only "
        "next actions while keeping activation, launch, onboarding, measurement, closure, and "
        "governance execution lanes closed in this sprint.",
        "",
        "## 4. Packet Chain Index",
        "",
        "Indexed packets (artifact types are template references; indexing is not execution):",
        "",
    ]
    for row in pkt.get("packet_chain_index") or _chain_rows():
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
    lines.extend(
        [
            "## 5. Readiness Rollup Model",
            "",
            "Readiness categories summarize index posture only; they are not approval:",
            "",
        ]
    )
    for row in pkt.get("readiness_rollup_model") or _readiness_rows():
        if not isinstance(row, dict):
            continue
        cat = row.get("readiness_category")
        st = row.get("rollup_status")
        if isinstance(cat, str) and cat.strip():
            lines.append(f"### {cat}")
            lines.append("")
        if isinstance(st, str) and st.strip():
            lines.append(st)
            lines.append("")
    lines.extend(["", "## 6. Evidence Coverage Summary", "", "Placeholder labels only:", ""])
    for item in pkt.get("evidence_coverage_summary") or list(_EVIDENCE_COVERAGE_SUMMARY):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 7. Blocked Action Rollup", ""])
    for item in pkt.get("blocked_action_rollup") or list(_BLOCKED_ACTION_ROLLUP):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 8. Human Review Dependency Summary", ""])
    for item in pkt.get("human_review_dependency_summary") or list(
        _HUMAN_REVIEW_DEPENDENCY_SUMMARY
    ):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 9. Decision Record and Audit Evidence Summary", ""])
    for item in pkt.get("decision_record_and_audit_evidence_summary") or list(
        _DECISION_RECORD_AND_AUDIT_EVIDENCE_SUMMARY
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
            "## 12. What Sprint 157 Does Not Build",
            "",
            "Sprint 157 explicitly does not build:",
            "",
        ]
    )
    for item in pkt.get("sprint_157_does_not_build") or list(_SPRINT157_DOES_NOT_BUILD):
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
