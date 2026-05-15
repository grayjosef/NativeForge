"""Sprint 153: M1 post-board decision routing and next-safe-action packet (preview-only).

Deterministic operator artifact that defines how hypothetical future human runtime authorization
board outcomes would route into safe next actions, denial paths, evidence remediation, deferral,
or future human review—after Sprint 152 human runtime authorization board packet. It does not
grant runtime authorization, board approval actually granted, source activation, customer
onboarding, pilot launch, production activation, post-board execution, implementation execution,
architecture implementation, live customer data access, customer outreach, interview scheduling,
external calls, database migrations, real metric collection, real pilot closeout, optimization
execution, or runnable implementation workflows. Depends on Sprint 152 as mandatory prerequisite
after the human runtime authorization board model; verification path retains Sprint 152 and
Sprint 151 for regression continuity.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_post_board_decision_routing_next_safe_action_packet_v1"
)
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

_PREREQUISITE_SPRINT152_ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_human_runtime_authorization_board_packet_v1"
)
_VERIFICATION_SPRINT152_ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_human_runtime_authorization_board_packet_v1"
)
_VERIFICATION_SPRINT151_ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_runtime_authorization_review_readiness_no_execution_packet_v1"
)

_SUPPORTED_BOARD_OUTCOME_TYPES: tuple[str, ...] = (
    "Recommend approval for future human review",
    "Deny runtime authorization",
    "Defer pending missing evidence",
    "Require narrowed implementation scope",
    "Require additional customer validation",
    "Require additional security review",
    "Require additional sovereignty and trust review",
    "Require rollback and support remediation",
    "Require documentation remediation",
    "Maintain no-execution default",
)

_DECISION_ROUTING_MATRIX: tuple[dict[str, str], ...] = (
    {
        "outcome": "Recommend approval for future human review",
        "required_evidence": (
            "Sprint 152 board docket completeness reference; Sprint 151 readiness artifacts; "
            "written rationale that recommendation is not authorization."
        ),
        "human_owner": "Human gate owner with product and audit reviewers as readers only.",
        "allowed_next_action": (
            "Schedule or reference a separate future human authorization process as "
            "documentation-only planning; no execution."
        ),
        "blocked_actions": (
            "Runtime execution, pilot launch, customer onboarding, source activation, production "
            "activation, post-board execution, implementation execution, architecture "
            "implementation, customer outreach, interview scheduling, live customer data access, "
            "database migration, real metric collection, real pilot closeout, optimization "
            "execution, runnable implementation workflow start."
        ),
        "required_follow_up": (
            "Route packet output to a distinct future human authorization workflow outside this "
            "sprint; retain evidence indexes only."
        ),
        "exit_criteria": (
            "Future human authorization records exist outside Sprint 153 software artifacts "
            "before any runtime phase; until then maintain no-execution default."
        ),
    },
    {
        "outcome": "Deny runtime authorization",
        "required_evidence": (
            "Written denial reasons mapped to mandatory denial conditions from Sprint 152; "
            "Sprint 151 denial rails cross-check."
        ),
        "human_owner": "Human gate owner with security and sovereignty reviewers.",
        "allowed_next_action": (
            "Archive denial documentation templates; plan evidence remediation as text-only "
            "operator notes."
        ),
        "blocked_actions": (
            "Any activation, launch, onboarding, outreach, scheduling, runtime writes, source "
            "enablement, production toggles, post-board execution, implementation execution."
        ),
        "required_follow_up": (
            "Document remediation path and re-entry evidence requirements without executing "
            "systems work."
        ),
        "exit_criteria": (
            "Reconvening would require new human board outcomes; software emits no automatic "
            "reopen signals."
        ),
    },
    {
        "outcome": "Defer pending missing evidence",
        "required_evidence": (
            "Enumeration of missing evidence classes against Sprint 152 docket and Sprint 151 "
            "readiness lists."
        ),
        "human_owner": "Audit and export reviewer coordinating evidence owners.",
        "allowed_next_action": (
            "Request additional written artifacts via human processes external to this builder; "
            "preview-only gap analysis."
        ),
        "blocked_actions": (
            "Pilot launch, customer outreach, interview scheduling, customer onboarding, runtime "
            "execution, source activation, production activation, post-board execution, database "
            "migration, real metric collection."
        ),
        "required_follow_up": (
            "Collect missing evidence through non-software channels; re-attach pointers in a "
            "future human session."
        ),
        "exit_criteria": (
            "Evidence bundle completeness reviewed in a future board session; Sprint 153 remains "
            "no-execution."
        ),
    },
    {
        "outcome": "Require narrowed implementation scope",
        "required_evidence": (
            "Scope delta memo referencing Sprint 150 bounded design boundaries when present in "
            "verification path context."
        ),
        "human_owner": "Technical architecture reviewer with product owner reviewer.",
        "allowed_next_action": (
            "Publish narrowed scope text for human review only; no implementation execution."
        ),
        "blocked_actions": (
            "Architecture implementation, implementation execution, activation, launch, "
            "onboarding, production activation, runnable workflow execution."
        ),
        "required_follow_up": (
            "Update human-readable scope statements offline; re-run future board preview lanes."
        ),
        "exit_criteria": (
            "Narrowed scope accepted in a future human review; execution remains blocked here."
        ),
    },
    {
        "outcome": "Require additional customer validation",
        "required_evidence": (
            "Customer validation planning artifacts per Sprint 152; no live customer data pulled "
            "by this sprint."
        ),
        "human_owner": "Customer validation reviewer.",
        "allowed_next_action": (
            "Plan additional validation steps as documentation; does not perform outreach or "
            "scheduling."
        ),
        "blocked_actions": (
            "Customer outreach, interview scheduling, customer onboarding, live customer data "
            "access, pilot launch, production activation."
        ),
        "required_follow_up": (
            "Human operators execute validation under separate approvals; Sprint 153 emits no "
            "campaigns or invites."
        ),
        "exit_criteria": (
            "Future evidence of validation planning retained; no execution implied from packet "
            "output."
        ),
    },
    {
        "outcome": "Require additional security review",
        "required_evidence": (
            "Security evidence gap list; references Sprint 152 security reviewer role limits."
        ),
        "human_owner": "Security reviewer.",
        "allowed_next_action": (
            "Request deeper written security review artifacts; no security tooling execution from "
            "this sprint."
        ),
        "blocked_actions": (
            "Runtime execution, external calls from this artifact, production activation, source "
            "activation, post-board execution, implementation execution."
        ),
        "required_follow_up": (
            "Produce additional written security materials offline; reconvene humans later."
        ),
        "exit_criteria": (
            "Security evidence completeness judged in a future human session; counters stay zero."
        ),
    },
    {
        "outcome": "Require additional sovereignty and trust review",
        "required_evidence": (
            "Sovereignty and trust gap list tied to Sprint 152 sovereignty reviewer expectations."
        ),
        "human_owner": "Sovereignty and trust reviewer.",
        "allowed_next_action": (
            "Request supplementary sovereignty and trust documentation for humans; no data plane "
            "expansion."
        ),
        "blocked_actions": (
            "Live customer data access, production activation, source activation, onboarding, "
            "pilot launch, post-board execution."
        ),
        "required_follow_up": (
            "Authors add residency, deletion, and portability statements offline for future review."
        ),
        "exit_criteria": (
            "Sovereignty and trust evidence completeness in a future board read; software grants "
            "nothing."
        ),
    },
    {
        "outcome": "Require rollback and support remediation",
        "required_evidence": (
            "Rollback and support playbooks from Sprint 152 docket; gap analysis text-only."
        ),
        "human_owner": "Operations and support reviewer.",
        "allowed_next_action": (
            "Document rollback and support remediation steps for humans; no automated rollback "
            "execution from this packet."
        ),
        "blocked_actions": (
            "Executing rollbacks, toggling production, activating sources, launching pilots, "
            "runtime writes, post-board execution."
        ),
        "required_follow_up": (
            "Operators update playbooks offline; future drills occur outside Sprint 153 software."
        ),
        "exit_criteria": (
            "Playbook completeness accepted by humans in a future session; no execution here."
        ),
    },
    {
        "outcome": "Require documentation remediation",
        "required_evidence": (
            "Documentation defect list against Sprint 151 readiness and Sprint 152 board "
            "materials."
        ),
        "human_owner": "Audit and export reviewer with human gate owner.",
        "allowed_next_action": (
            "Assign documentation fixes as human tasks; emit no writes to product systems from "
            "this builder."
        ),
        "blocked_actions": (
            "Implementation execution, architecture implementation, database migration, production "
            "activation, source activation, customer outreach, interview scheduling."
        ),
        "required_follow_up": (
            "Authors revise documents offline; attach in future human reviews."
        ),
        "exit_criteria": (
            "Documentation set complete for a future board read; Sprint 153 remains preview-only."
        ),
    },
    {
        "outcome": "Maintain no-execution default",
        "required_evidence": (
            "Acknowledgment that all lanes default closed until separate human authorization; "
            "cross-check Sprint 152 limits."
        ),
        "human_owner": "Human gate owner.",
        "allowed_next_action": (
            "Continue preview-only operator education; no activation or launch from artifacts."
        ),
        "blocked_actions": (
            "All runtime execution, pilot launch, onboarding, outreach, scheduling, activation, "
            "production activation, post-board execution, runnable workflows, optimization "
            "execution, real metric collection, real pilot closeout."
        ),
        "required_follow_up": (
            "Retain no-execution posture until explicit out-of-band human authorization exists."
        ),
        "exit_criteria": (
            "No execution begins from Sprint 153 output; human authorization remains external."
        ),
    },
)

_APPROVAL_RECOMMENDATION_ROUTING: tuple[str, ...] = (
    "Approval recommendation is not runtime authorization.",
    "Approval recommendation does not launch a pilot.",
    "Approval recommendation does not onboard customers.",
    "Approval recommendation does not activate sources.",
    "Approval recommendation does not activate production.",
    "Approval recommendation must route to a separate future human authorization process.",
    "Routing is preview-only: deterministic dict and markdown describe allowed documentation "
    "lanes only; they do not open execution, grant board approval actually granted, or start "
    "post-board execution.",
)

_DENIAL_ROUTING: tuple[str, ...] = (
    "Denial routes to stop planning for runtime phases in operator materials until humans "
    "document remediation and reconvene outside software.",
    "Denial preserves no-execution default: no pilot launch, no customer outreach, no interview "
    "scheduling, no customer onboarding, no customer data access, no database migration, no "
    "source activation, no production activation, no real metric collection, no real pilot "
    "closeout, no optimization execution, no architecture implementation, no implementation "
    "execution, no runtime authorization granted, no board approval actually granted, no "
    "post-board execution, and no runnable implementation workflow.",
    "Denial may require evidence remediation lists as text-only outputs for future humans.",
)

_DEFERRAL_AND_EVIDENCE_REMEDIATION_ROUTING: tuple[str, ...] = (
    "Deferral routes to a paused state: operators gather missing written evidence without "
    "pulling live customer data or activating systems.",
    "Evidence remediation routes to human-authored artifact updates and checklist completions; "
    "Sprint 153 performs no collection jobs, no external calls, and no database migrations.",
    "Deferral and remediation explicitly block pilot launch, customer outreach, interview "
    "scheduling, customer onboarding, source activation, production activation, post-board "
    "execution, and runnable implementation workflows until future human processes complete.",
    "Re-entry after deferral requires a future board session outcome; software does not auto "
    "advance gates.",
)

_NARROWED_SCOPE_ROUTING: tuple[str, ...] = (
    "Narrowed scope routes to revised written slice boundaries for human review; it does not "
    "authorize architecture implementation or implementation execution.",
    "Narrowed scope keeps no-execution default until separate human authorization outside this "
    "artifact.",
    "Narrowed scope blocks pilot launch, production activation, source activation, customer "
    "onboarding, customer outreach, interview scheduling, post-board execution, and runnable "
    "implementation workflow starts from Sprint 153 output alone.",
)

_NO_EXECUTION_DEFAULT: tuple[str, ...] = (
    "No-execution default: Sprint 153 defines post-board routing templates only; all runtime "
    "execution, post-board execution, activation, launch, onboarding, outreach, and scheduling "
    "lanes remain closed from this software output.",
    "No-execution default: no pilot launch, no customer outreach, no interview scheduling, no "
    "customer onboarding, no customer data access, no database migration, no source activation, "
    "no production activation, no real metric collection, no real pilot closeout, no "
    "optimization execution, no architecture implementation, no implementation execution, no "
    "runtime authorization granted, no board approval actually granted, no post-board execution, "
    "and no runnable implementation workflow may begin from this packet.",
    "No-execution default: human operator approval for any future runtime phase remains mandatory "
    "and external to Sprint 153 deterministic builders.",
)

_RUNTIME_AUTHORIZATION_BOUNDARY: tuple[str, ...] = (
    "Runtime authorization boundary: Sprint 153 classifies hypothetical board outcomes into "
    "documentation-only next routes; it grants no runtime authorization granted and no board "
    "approval actually granted.",
    "Runtime authorization boundary: preview-only deterministic dict and markdown emission only; "
    "no runtime writes, queues, workers, external calls, or post-board execution.",
    "Runtime authorization boundary: separation between routing templates and any future recorded "
    "authorization acts must remain explicit in operator training and documentation.",
)

_SPRINT153_DOES_NOT_BUILD: tuple[str, ...] = (
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

_PACKET_EXIT_CRITERIA: tuple[str, ...] = (
    "Sprint 152 prerequisite is named with human runtime authorization board packet artifact type "
    "as mandatory context after Sprint 152 templates.",
    "Verification path retains Sprint 152 human runtime authorization board artifact type "
    "alongside Sprint 151 runtime authorization review readiness no-execution artifact type for "
    "regression continuity.",
    "Supported board outcome types include all mandated outcome labels.",
    "Decision routing matrix rows include outcome, required evidence, human owner, allowed next "
    "action, blocked actions, required follow-up, and exit criteria fields with zero actual "
    "counters.",
    "Approval recommendation routing, denial routing, deferral and evidence remediation routing, "
    "narrowed scope routing, no-execution default, runtime authorization boundary, sprint 153 "
    "does not build list, exit criteria, risks, mitigations, and recommendation-only next safe "
    "action are present.",
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "Routing table mistaken for authorization",
        "Keep runtime authorization boundary language, approval recommendation is not runtime "
        "authorization statements, and explicit no runtime authorization granted and no board "
        "approval actually granted phrasing in routing and does-not-build lists.",
    ),
    (
        "Sprint 152 prerequisite skipped",
        "Bind prerequisite evidence to the Sprint 152 artifact type and section two sequencing "
        "rationale after the human runtime authorization board model.",
    ),
    (
        "Sprint 151 or Sprint 152 verification path dropped",
        "Keep both artifact types in verification path keys and regression tests importing Sprint "
        "152 and Sprint 151 builders.",
    ),
    (
        "Post-board execution inferred from templates",
        "State no post-board execution explicitly in no-execution default, denial routing, and "
        "deferral routing bullets; block runnable workflows in matrix blocked actions.",
    ),
)

_RECOMMENDED_NEXT_SAFE_ACTION = (
    "The recommended next safe action is recommendation-only: operators should retain Sprint 152 "
    "human runtime authorization board packets and Sprint 151 runtime authorization review "
    "readiness no-execution artifacts in the verification path, map hypothetical board outcomes to "
    "this routing matrix as a documentation exercise only, and prepare human-only follow-ups "
    "without starting runtime execution, customer outreach, interview scheduling, customer "
    "onboarding, customer data access, database migration, source activation, production "
    "activation, pilot launch, real metric collection, real pilot closeout, optimization "
    "execution, architecture implementation, implementation execution, runtime authorization "
    "granted, board approval actually granted, post-board execution, or runnable implementation "
    "workflow. Recorded human operator approval in a separate future human authorization process "
    "would be required before any execution phase; Sprint 153 software does not perform that "
    "process."
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _matrix_rows() -> list[dict[str, str]]:
    return [dict(row) for row in _DECISION_ROUTING_MATRIX]


def _risk_payloads() -> list[dict[str, str]]:
    return [{"risk": r, "mitigation": m} for r, m in _RISK_MITIGATIONS]


def build_active_source_activation_m1_post_board_decision_routing_next_safe_action_packet() -> (
    dict[str, Any]
):
    """Return the Sprint 153 M1 post-board decision routing and next-safe-action packet."""
    proof = {
        "sprint_153_m1_post_board_decision_routing_packet_is_stateless": True,
        "sprint_153_m1_post_board_decision_routing_packet_is_side_effect_free": True,
        "sprint_153_m1_post_board_decision_routing_packet_is_preview_only": True,
        "sprint_153_m1_post_board_decision_routing_packet_performs_no_runtime_work": True,
        "sprint_153_m1_post_board_decision_routing_packet_emits_operator_templates_only": True,
    }
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 153,
        "packet_name": "NativeForge M1 Post-Board Decision Routing & Next-Safe-Action Packet",
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_present_post_board_decision_routing_preview_only": True,
        "may_reference_m1_evidence_base_preview_only": True,
        "prerequisite_human_runtime_authorization_board_sprint": 152,
        "prerequisite_human_runtime_authorization_board_artifact_type": _PREREQUISITE_SPRINT152_ARTIFACT_TYPE,
        "verification_path_human_runtime_authorization_board_sprint": 152,
        "verification_path_human_runtime_authorization_board_artifact_type": (
            _VERIFICATION_SPRINT152_ARTIFACT_TYPE
        ),
        "verification_path_runtime_authorization_review_readiness_no_execution_sprint": 151,
        "verification_path_runtime_authorization_review_readiness_no_execution_artifact_type": (
            _VERIFICATION_SPRINT151_ARTIFACT_TYPE
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
        "supported_board_outcome_types": list(_SUPPORTED_BOARD_OUTCOME_TYPES),
        "decision_routing_matrix": _matrix_rows(),
        "approval_recommendation_routing": list(_APPROVAL_RECOMMENDATION_ROUTING),
        "denial_routing": list(_DENIAL_ROUTING),
        "deferral_and_evidence_remediation_routing": list(_DEFERRAL_AND_EVIDENCE_REMEDIATION_ROUTING),
        "narrowed_scope_routing": list(_NARROWED_SCOPE_ROUTING),
        "no_execution_default": list(_NO_EXECUTION_DEFAULT),
        "runtime_authorization_boundary": list(_RUNTIME_AUTHORIZATION_BOUNDARY),
        "sprint_153_does_not_build": list(_SPRINT153_DOES_NOT_BUILD),
        "packet_exit_criteria": list(_PACKET_EXIT_CRITERIA),
        "risks_and_mitigations": _risk_payloads(),
        "recommended_next_safe_action": _RECOMMENDED_NEXT_SAFE_ACTION,
        "sprint_153_m1_post_board_decision_routing_next_safe_action_packet_proof": proof,
    }
    return _json_safe(out)


def render_active_source_activation_m1_post_board_decision_routing_next_safe_action_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render the operator-facing markdown packet (deterministic; uses ``packet`` when provided)."""
    pkt = (
        packet
        if isinstance(packet, dict)
        else build_active_source_activation_m1_post_board_decision_routing_next_safe_action_packet()
    )
    lines: list[str] = [
        "# NativeForge M1 Post-Board Decision Routing & Next-Safe-Action Packet v1",
        "",
        "## 1. Purpose",
        "",
        "This packet is a deterministic, preview-only operator artifact that defines post-board "
        "decision routing after Sprint 152 human runtime authorization board packet. It maps "
        "hypothetical future board outcomes to safe next actions, denial paths, evidence "
        "remediation, deferral, narrowed scope handling, or future human review—without granting "
        "runtime authorization, board approval actually granted, post-board execution, runtime "
        "execution, accessing live customer data, performing customer outreach, scheduling "
        "interviews, onboarding customers, activating sources, launching pilots, activating "
        "production systems, making external calls, running database migrations, collecting real "
        "metrics, executing real pilot closeout, running optimization, implementing architecture, "
        "executing implementation, or emitting runnable implementation workflows.",
        "",
        "## 2. Why This Comes After Sprint 152",
        "",
        "Sprint 152 delivered the human runtime authorization board packet: it names board "
        "composition, evidence review docket, decision rights and limits, mandatory denial "
        "conditions, approval documentation requirements for a future process, no-execution "
        "default, sovereignty trust and security constraints, and runtime authorization boundary "
        "language—while withholding runtime authorization granted and board approval actually "
        "granted. Sprint 153 is sequential because operators need a documented way to route "
        "potential board outcomes into safe next steps after that board model exists; without "
        "Sprint 152, outcome labels and denial rails would lack the human runtime authorization "
        "board framing that Sprint 153 extends as routing-only templates. Sprint 151 runtime "
        "authorization review readiness and no-execution artifacts remain in the verification path "
        "alongside Sprint 152 for regression continuity. Sprint 153 does not replace Sprint 152; "
        "it depends on Sprint 152 as prerequisite human runtime authorization board context "
        f"(artifact type `{_PREREQUISITE_SPRINT152_ARTIFACT_TYPE}`), "
        "then adds post-board routing lanes only—still without granting runtime authorization, "
        "board approval actually granted, implementation execution, activation, launch, onboarding, "
        "customer data access, production scope, or post-board execution.",
        "",
        "## 3. Post-Board Decision Routing Objective",
        "",
        "Provide deterministic routing scaffolding that classifies hypothetical board outcomes into "
        "allowed documentation-only next actions and explicitly blocked actions, while keeping all "
        "execution, deployment, measurement, and post-board execution lanes closed in this sprint.",
        "",
        "## 4. Supported Board Outcome Types",
        "",
        "The following outcome types are supported as labels for future human decisions; none "
        "imply authorization from Sprint 153 software output:",
        "",
    ]
    for o in pkt.get("supported_board_outcome_types") or list(_SUPPORTED_BOARD_OUTCOME_TYPES):
        if isinstance(o, str) and o.strip():
            lines.append(f"- {o}")
    lines.extend(["", "## 5. Decision Routing Matrix", "", "Each row lists routing fields:"])
    lines.append("")
    matrix = pkt.get("decision_routing_matrix") or _matrix_rows()
    for row in matrix:
        if not isinstance(row, dict):
            continue
        outcome = row.get("outcome")
        if isinstance(outcome, str) and outcome.strip():
            lines.append(f"### {outcome}")
            lines.append("")
        for key, title in (
            ("required_evidence", "Required evidence"),
            ("human_owner", "Human owner"),
            ("allowed_next_action", "Allowed next action"),
            ("blocked_actions", "Blocked actions"),
            ("required_follow_up", "Required follow-up"),
            ("exit_criteria", "Exit criteria"),
        ):
            val = row.get(key)
            if isinstance(val, str) and val.strip():
                lines.append(f"- **{title}**: {val}")
        lines.append("")
    lines.extend(["", "## 6. Approval Recommendation Routing", ""])
    for item in pkt.get("approval_recommendation_routing") or list(_APPROVAL_RECOMMENDATION_ROUTING):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 7. Denial Routing", ""])
    for item in pkt.get("denial_routing") or list(_DENIAL_ROUTING):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 8. Deferral and Evidence Remediation Routing", ""])
    for item in pkt.get("deferral_and_evidence_remediation_routing") or list(
        _DEFERRAL_AND_EVIDENCE_REMEDIATION_ROUTING
    ):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 9. Narrowed Scope Routing", ""])
    for item in pkt.get("narrowed_scope_routing") or list(_NARROWED_SCOPE_ROUTING):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 10. No-Execution Default", ""])
    for item in pkt.get("no_execution_default") or list(_NO_EXECUTION_DEFAULT):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 11. Runtime Authorization Boundary", ""])
    for item in pkt.get("runtime_authorization_boundary") or list(_RUNTIME_AUTHORIZATION_BOUNDARY):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 12. What Sprint 153 Does Not Build", "", "Sprint 153 explicitly does not build:", ""])
    for item in pkt.get("sprint_153_does_not_build") or list(_SPRINT153_DOES_NOT_BUILD):
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
            pkt.get("recommended_next_safe_action") or _RECOMMENDED_NEXT_SAFE_ACTION,
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
