"""Sprint 155: M1 re-review board readiness and evidence closure packet (preview-only).

Deterministic operator artifact that defines how remediated evidence would be closed,
marked ready for future human re-review, rejected, deferred, or routed back to
remediation after Sprint 154's evidence remediation queue and re-review packet. It does
not grant runtime authorization, board approval actually granted, source activation,
customer onboarding, pilot launch, production activation, post-board execution,
remediation execution, evidence closure execution, implementation execution,
architecture implementation, re-review board convening, live customer data access,
customer outreach, interview scheduling, external calls, database migrations, real metric
collection, real pilot closeout, optimization execution, or runnable implementation
workflows. Depends on Sprint 154 as mandatory prerequisite after the evidence
remediation queue and re-review packet; verification path retains Sprint 154 and Sprint
153 for regression continuity.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_re_review_board_readiness_evidence_closure_packet_v1"
)
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

_PREREQUISITE_SPRINT154_ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_evidence_remediation_queue_re_review_packet_v1"
)
_VERIFICATION_SPRINT154_ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_evidence_remediation_queue_re_review_packet_v1"
)
_VERIFICATION_SPRINT153_ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_post_board_decision_routing_next_safe_action_packet_v1"
)

_EVIDENCE_CLOSURE_CRITERIA: tuple[str, ...] = (
    "Security review evidence closed",
    "Sovereignty and trust review evidence closed",
    "Customer validation evidence closed",
    "Rollback plan evidence closed",
    "Support readiness evidence closed",
    "Audit export evidence closed",
    "Data handling evidence closed",
    "Technical architecture review evidence closed",
    "Written approval evidence closed",
    "Bounded implementation scope evidence closed",
)

_REVIEW_DOCKET_READINESS_MODEL: tuple[str, ...] = (
    "Remediation item closed",
    "Evidence owner signoff recorded",
    "Evidence sufficiency checked",
    "Denial conditions re-checked",
    "Blocked actions confirmed",
    "No-execution default confirmed",
    "Runtime boundary confirmed",
    "Re-review packet prepared for future human review only",
    "No board approval actually granted",
    "No runtime authorization granted",
)

_EVIDENCE_SUFFICIENCY_CHECKS: tuple[str, ...] = (
    "Each closure criterion has a corresponding human-attested artifact reference "
    "outside Sprint 155 software; templates do not ingest live records.",
    "Cross-check that closed labels do not contradict Sprint 154 queue states until "
    "humans reconcile documentation out of band.",
    "Verify bounded scope language is present wherever implementation scope evidence "
    "is marked closed.",
    "Confirm rollback and support readiness narratives include operator-visible "
    "plain-language steps without executing them from this sprint.",
    "Sufficiency checks are documentation gates only; evidence closure is not approval.",
)

_OWNER_SIGNOFF_MODEL: tuple[dict[str, str], ...] = (
    {
        "owner_role": "Security evidence owner",
        "responsibility": (
            "Record attestations that security review evidence is closed in human systems "
            "only; no security tooling execution from this builder."
        ),
        "limits": (
            "Owner signoff is not runtime authorization; may not close production gates "
            "or activate sources from Sprint 155 output."
        ),
    },
    {
        "owner_role": "Sovereignty and trust evidence owner",
        "responsibility": (
            "Attest sovereignty and trust evidence closure narratives for future human "
            "re-review packets."
        ),
        "limits": (
            "May not access live customer data or expand data planes from this packet."
        ),
    },
    {
        "owner_role": "Customer validation evidence owner",
        "responsibility": (
            "Document customer validation evidence closure as planning artifacts without "
            "outreach or scheduling."
        ),
        "limits": (
            "May not perform customer outreach, interview scheduling, or customer onboarding."
        ),
    },
    {
        "owner_role": "Operations evidence owner",
        "responsibility": (
            "Attest rollback plan and support readiness evidence closed as text-only "
            "operator records."
        ),
        "limits": (
            "May not execute rollbacks, launch pilots, or activate production from "
            "signoff labels."
        ),
    },
    {
        "owner_role": "Audit and data handling evidence owner",
        "responsibility": (
            "Attest audit export and data handling evidence closure checklists for humans."
        ),
        "limits": (
            "May not run database migrations or collect real metrics from this sprint."
        ),
    },
    {
        "owner_role": "Architecture and scope evidence owner",
        "responsibility": (
            "Attest technical architecture review and bounded implementation scope evidence "
            "closure for future docket assembly."
        ),
        "limits": (
            "May not authorize architecture implementation or implementation execution."
        ),
    },
    {
        "owner_role": "Written approval gate owner",
        "responsibility": (
            "Record written approval evidence closure as human process documentation only."
        ),
        "limits": (
            "Written human approval remains required; signoff text does not substitute "
            "a future board outcome."
        ),
    },
)

_REJECTION_PATHS: tuple[str, ...] = (
    "Rejection path: insufficient remediation narrative—route back to Sprint 154-style "
    "remediation queue documentation without executing remediation.",
    "Rejection path: denial conditions persist after re-check—keep no-execution default "
    "and block activation, launch, onboarding, and production labels.",
    "Rejection path: owner declines attestations—do not mark evidence closed; preserve "
    "preview-only docket state.",
    "Rejection clarifies evidence closure is not approval and conveys no runtime "
    "authorization granted.",
)

_DEFERRAL_PATHS: tuple[str, ...] = (
    "Deferral path: partial sufficiency—leave docket in documentation-only pending state "
    "until humans supply remaining artifacts out of band.",
    "Deferral path: scope ambiguity—route to future human clarification sessions without "
    "scheduling interviews or contacting customers from software.",
    "Deferral path: dependency on external human calendar—record deferral labels only; "
    "no automation of board or re-review convening.",
    "Deferral preserves re-review readiness is not approval until separate human decisions "
    "exist.",
)

_RETURN_TO_REMEDIATION_ROUTING: tuple[str, ...] = (
    "Return-to-remediation routing: failed sufficiency checks map items back to evidence "
    "remediation queue categories from Sprint 154 as documentation references only.",
    "Return-to-remediation routing: reopened denial triggers re-label toward remediation "
    "templates without remediation execution or evidence closure execution.",
    "Return-to-remediation routing: owner withdraws signoff—strip closed labels in human "
    "records first; Sprint 155 software performs no writes.",
    "Return routing keeps execution blocked by default and excludes runnable workflows.",
)

_BLOCKED_ACTION_RULES: tuple[str, ...] = (
    "Evidence closure is not approval.",
    "Re-review readiness is not approval.",
    "Re-review docket preparation is not runtime authorization.",
    "Owner signoff is not runtime authorization.",
    "Future human re-review remains required.",
    "Written human approval remains required.",
    "No pilot launch may occur from this packet.",
    "No customer onboarding may occur from this packet.",
    "No source activation may occur from this packet.",
    "No production activation may occur from this packet.",
    "Docket-ready labels do not authorize pilot launch.",
    "Docket-ready labels do not authorize customer outreach or interview scheduling.",
    "Docket-ready labels do not authorize database migration.",
    "Docket-ready labels do not authorize implementation execution.",
)

_NO_EXECUTION_DEFAULT: tuple[str, ...] = (
    "No-execution default: Sprint 155 defines re-review board readiness and evidence "
    "closure documentation lanes only; runtime execution, remediation execution, "
    "evidence closure execution, activation, launch, onboarding, outreach, scheduling, "
    "and board convening remain closed in software.",
    "No-execution default: no pilot launch, no customer outreach, no interview scheduling, "
    "no customer onboarding, no customer data access, no database migration, no source "
    "activation, no production activation, no real metric collection, no real pilot "
    "closeout, no optimization execution, no architecture implementation, no implementation "
    "execution, no runtime authorization granted, no board approval actually granted, no "
    "post-board execution, no remediation execution, no evidence closure execution, no "
    "re-review board convened, and no runnable implementation workflow may begin from this "
    "packet.",
    "No-execution default: closure and docket labels are templates; human operator "
    "approval for any future runtime phase remains mandatory and external.",
)

_RUNTIME_AUTHORIZATION_BOUNDARY: tuple[str, ...] = (
    "Runtime authorization boundary: Sprint 155 prepares documentation for future human "
    "re-review only; it grants no runtime authorization granted and no board approval "
    "actually granted.",
    "Runtime authorization boundary: preview-only deterministic dict and markdown "
    "emission only; no runtime writes, workers, external calls, remediation execution, "
    "evidence closure execution, post-board execution, or re-review board convened.",
    "Runtime authorization boundary: sufficiency checks, signoffs, and docket readiness "
    "states must not be interpreted as authorization to execute, activate, launch, onboard, "
    "or close evidence in live systems.",
)

_SPRINT155_DOES_NOT_BUILD: tuple[str, ...] = (
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
    "Recommendation-only: align closed evidence labels with Sprint 154 queue exit states "
    "as a desk exercise—no software execution.",
    "Recommendation-only: draft a future human re-review docket appendix referencing this "
    "packet’s criteria without convening a board.",
    "Recommendation-only: re-run verification path imports for Sprint 154 and Sprint 153 "
    "artifacts to preserve roadmap continuity checks.",
    "Recommendation-only: if sufficiency fails, document return-to-remediation routing "
    "text for operators without starting remediation execution.",
)

_PACKET_EXIT_CRITERIA: tuple[str, ...] = (
    "Sprint 154 prerequisite is named with evidence remediation queue and re-review packet "
    "artifact type as mandatory context after Sprint 154 templates.",
    "Verification path retains Sprint 154 evidence remediation queue artifact type "
    "alongside Sprint 153 post-board decision routing artifact type for regression "
    "continuity.",
    "Evidence closure criteria include all mandated closure classes with zero actual counters.",
    "Re-review docket readiness model includes all mandated readiness states.",
    "Evidence sufficiency checks, owner signoff model, rejection paths, deferral paths, "
    "return-to-remediation routing, blocked action rules, no-execution default, runtime "
    "authorization boundary, sprint 155 does not build list, risks, mitigations, and "
    "recommendation-only next safe action options are present.",
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "Closure label mistaken for approval",
        "State evidence closure is not approval, re-review readiness is not approval, and "
        "keep explicit no runtime authorization granted and no board approval actually "
        "granted phrasing in boundary and blocked rules.",
    ),
    (
        "Sprint 154 prerequisite skipped",
        "Bind prerequisite evidence to the Sprint 154 artifact type and section two "
        "sequencing rationale after the evidence remediation queue and re-review packet.",
    ),
    (
        "Sprint 153 or Sprint 154 verification path dropped",
        "Keep both artifact types in verification path keys and regression tests importing "
        "Sprint 154 and Sprint 153 builders.",
    ),
    (
        "Evidence closure execution inferred from templates",
        "State no evidence closure execution and no remediation execution in "
        "no-execution default and does-not-build lists; block runnable workflows.",
    ),
)

_RECOMMENDED_NEXT_SAFE_ACTION = (
    "The recommended next safe action is recommendation-only: operators should retain "
    "Sprint 154 evidence remediation queue and re-review packets and Sprint 153 post-board "
    "decision routing artifacts in the verification path, map closure and docket readiness "
    "outcomes to this model as documentation only, and prepare human-only re-review "
    "materials without starting runtime execution, remediation execution, evidence closure "
    "execution, customer outreach, interview scheduling, customer onboarding, customer data "
    "access, database migration, source activation, production activation, pilot launch, "
    "real metric collection, real pilot closeout, optimization execution, architecture "
    "implementation, implementation execution, runtime authorization granted, board "
    "approval actually granted, post-board execution, re-review board convened, or runnable "
    "implementation workflow. Recorded human operator approval in a separate future human "
    "re-review or authorization process would be required before any execution phase; "
    "Sprint 155 software does not perform that process."
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _owner_rows() -> list[dict[str, str]]:
    return [dict(row) for row in _OWNER_SIGNOFF_MODEL]


def _risk_payloads() -> list[dict[str, str]]:
    return [{"risk": r, "mitigation": m} for r, m in _RISK_MITIGATIONS]


def build_active_source_activation_m1_re_review_board_readiness_evidence_closure_packet() -> (
    dict[str, Any]
):
    """Return the Sprint 155 M1 re-review board readiness and evidence closure packet."""
    proof = {
        "sprint_155_m1_re_review_evidence_closure_packet_is_stateless": True,
        "sprint_155_m1_re_review_evidence_closure_packet_is_side_effect_free": True,
        "sprint_155_m1_re_review_evidence_closure_packet_is_preview_only": True,
        "sprint_155_m1_re_review_evidence_closure_packet_performs_no_runtime_work": True,
        "sprint_155_m1_re_review_evidence_closure_packet_emits_operator_templates_only": True,
    }
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 155,
        "packet_name": (
            "NativeForge M1 Re-Review Board Readiness & Evidence Closure Packet"
        ),
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_present_re_review_readiness_evidence_closure_preview_only": True,
        "may_reference_m1_evidence_base_preview_only": True,
        "prerequisite_evidence_remediation_queue_re_review_sprint": 154,
        "prerequisite_evidence_remediation_queue_re_review_artifact_type": (
            _PREREQUISITE_SPRINT154_ARTIFACT_TYPE
        ),
        "verification_path_evidence_remediation_queue_re_review_sprint": 154,
        "verification_path_evidence_remediation_queue_re_review_artifact_type": (
            _VERIFICATION_SPRINT154_ARTIFACT_TYPE
        ),
        "verification_path_post_board_decision_routing_sprint": 153,
        "verification_path_post_board_decision_routing_artifact_type": (
            _VERIFICATION_SPRINT153_ARTIFACT_TYPE
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
        "evidence_closure_criteria": list(_EVIDENCE_CLOSURE_CRITERIA),
        "re_review_docket_readiness_model": list(_REVIEW_DOCKET_READINESS_MODEL),
        "evidence_sufficiency_checks": list(_EVIDENCE_SUFFICIENCY_CHECKS),
        "owner_signoff_model": _owner_rows(),
        "rejection_paths": list(_REJECTION_PATHS),
        "deferral_paths": list(_DEFERRAL_PATHS),
        "return_to_remediation_routing": list(_RETURN_TO_REMEDIATION_ROUTING),
        "blocked_action_rules": list(_BLOCKED_ACTION_RULES),
        "no_execution_default": list(_NO_EXECUTION_DEFAULT),
        "runtime_authorization_boundary": list(_RUNTIME_AUTHORIZATION_BOUNDARY),
        "sprint_155_does_not_build": list(_SPRINT155_DOES_NOT_BUILD),
        "next_safe_action_options": list(_NEXT_SAFE_ACTION_OPTIONS),
        "packet_exit_criteria": list(_PACKET_EXIT_CRITERIA),
        "risks_and_mitigations": _risk_payloads(),
        "recommended_next_safe_action": _RECOMMENDED_NEXT_SAFE_ACTION,
        "sprint_155_m1_re_review_board_readiness_evidence_closure_packet_proof": proof,
    }
    return _json_safe(out)


def render_active_source_activation_m1_re_review_board_readiness_evidence_closure_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render the operator-facing markdown packet (deterministic; uses ``packet`` when provided)."""
    pkt = (
        packet
        if isinstance(packet, dict)
        else build_active_source_activation_m1_re_review_board_readiness_evidence_closure_packet()
    )
    lines: list[str] = [
        "# NativeForge M1 Re-Review Board Readiness & Evidence Closure Packet v1",
        "",
        "## 1. Purpose",
        "",
        "This packet is a deterministic, preview-only operator artifact that defines how "
        "remediated evidence would be closed, marked ready for future human re-review, "
        "rejected, deferred, or routed back to remediation after Sprint 154's evidence "
        "remediation queue and re-review packet. It does not grant runtime authorization, "
        "board approval actually granted, source activation, customer onboarding, pilot "
        "launch, production activation, post-board execution, remediation execution, evidence "
        "closure execution, re-review board convening, runtime execution, live customer data "
        "access, customer outreach, interview scheduling, external calls, database "
        "migrations, real metric collection, real pilot closeout, optimization execution, "
        "architecture implementation, implementation execution, or runnable implementation "
        "workflows.",
        "",
        "## 2. Why This Comes After Sprint 154",
        "",
        "Sprint 154 delivered the evidence remediation queue and re-review packet: it "
        "defines remediation item categories, queue states, evidence owners, re-review "
        "readiness signals, blocked action rules, and deferred outcome handling while "
        "withholding runtime authorization granted, board approval actually granted, "
        "remediation execution, and post-board execution. Sprint 155 is sequential because "
        "operators need a deterministic model for how remediated evidence would be closed "
        "and how a future re-review docket would be prepared only after queue scaffolding "
        "exists; without Sprint 154, closure and docket readiness would lack the remediation "
        "framing Sprint 155 extends as documentation-only templates. Sprint 153 post-board "
        "decision routing artifacts remain in the verification path alongside Sprint 154 for "
        "regression continuity. Sprint 155 does not replace Sprint 154; it depends on "
        "Sprint 154 as prerequisite evidence remediation queue context "
        f"(artifact type `{_PREREQUISITE_SPRINT154_ARTIFACT_TYPE}`), "
        "then adds evidence closure criteria, docket readiness, sufficiency checks, and "
        "signoff models—still without granting runtime authorization, board approval actually "
        "granted, evidence closure execution, remediation execution, activation, launch, "
        "onboarding, customer data access, production scope, or post-board execution.",
        "",
        "## 3. Re-Review Board Readiness Objective",
        "",
        "Provide deterministic documentation-only scaffolding that describes how a "
        "re-review board docket would be considered ready for future human review after "
        "evidence closure criteria are satisfied in human records, while keeping execution, "
        "deployment, measurement, remediation execution, evidence closure execution, board "
        "convening, and post-board execution lanes closed in this sprint.",
        "",
        "## 4. Evidence Closure Criteria",
        "",
        "The following closure criteria are labels for future human records; none imply "
        "authorization from Sprint 155 software output:",
        "",
    ]
    for crit in pkt.get("evidence_closure_criteria") or list(_EVIDENCE_CLOSURE_CRITERIA):
        if isinstance(crit, str) and crit.strip():
            lines.append(f"- {crit}")
    lines.extend(
        [
            "",
            "## 5. Re-Review Docket Readiness Model",
            "",
            "The following readiness states describe documentation-only docket assembly; "
            "they do not convene a board or grant authorization:",
            "",
        ]
    )
    for item in pkt.get("re_review_docket_readiness_model") or list(
        _REVIEW_DOCKET_READINESS_MODEL
    ):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 6. Evidence Sufficiency Checks", ""])
    for item in pkt.get("evidence_sufficiency_checks") or list(_EVIDENCE_SUFFICIENCY_CHECKS):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 7. Owner Signoff Model", ""])
    for row in pkt.get("owner_signoff_model") or _owner_rows():
        if not isinstance(row, dict):
            continue
        role = row.get("owner_role")
        if isinstance(role, str) and role.strip():
            lines.append(f"### {role}")
            lines.append("")
        for key, title in (
            ("responsibility", "Responsibility"),
            ("limits", "Limits"),
        ):
            val = row.get(key)
            if isinstance(val, str) and val.strip():
                lines.append(f"- **{title}**: {val}")
        lines.append("")
    lines.extend(["", "## 8. Rejection and Deferral Paths", ""])
    lines.append("### Rejection paths")
    lines.append("")
    for item in pkt.get("rejection_paths") or list(_REJECTION_PATHS):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "### Deferral paths", ""])
    for item in pkt.get("deferral_paths") or list(_DEFERRAL_PATHS):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 9. Return-to-Remediation Routing", ""])
    for item in pkt.get("return_to_remediation_routing") or list(
        _RETURN_TO_REMEDIATION_ROUTING
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
    lines.append("")
    lines.append(
        "Additional blocked-action and boundary affirmations (documentation-only; not a "
        "separate numbered section):"
    )
    lines.append("")
    for item in pkt.get("blocked_action_rules") or list(_BLOCKED_ACTION_RULES):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 12. What Sprint 155 Does Not Build",
            "",
            "Sprint 155 explicitly does not build:",
            "",
        ]
    )
    for item in pkt.get("sprint_155_does_not_build") or list(_SPRINT155_DOES_NOT_BUILD):
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
            "### Next safe action options (recommendation-only)",
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
