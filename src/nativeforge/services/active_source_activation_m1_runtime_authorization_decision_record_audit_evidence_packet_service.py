"""Sprint 156: M1 runtime authorization decision record and audit evidence packet (preview-only).

Deterministic operator artifact that defines how a future runtime authorization decision
record and audit evidence would be structured after Sprint 155's Re-Review Board Readiness
& Evidence Closure Packet. It does not grant runtime authorization, board approval actually
granted, source activation, customer onboarding, pilot launch, production activation,
post-board execution, remediation execution, evidence closure execution, re-review board
convening, decision record execution, audit evidence execution, implementation execution,
architecture implementation, live customer data access, customer outreach, interview
scheduling, external calls, database migrations, real metric collection, real pilot
closeout, optimization execution, or runnable implementation workflows. Depends on Sprint
155 as mandatory prerequisite after re-review board readiness and evidence closure
templates exist; verification path retains Sprint 155 and Sprint 154 for regression
continuity.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_runtime_authorization_decision_record_audit_evidence_packet_v1"
)
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

_PREREQUISITE_SPRINT155_ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_re_review_board_readiness_evidence_closure_packet_v1"
)
_VERIFICATION_SPRINT155_ARTIFACT_TYPE = _PREREQUISITE_SPRINT155_ARTIFACT_TYPE
_VERIFICATION_SPRINT154_ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_evidence_remediation_queue_re_review_packet_v1"
)
_VERIFICATION_SPRINT153_ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_post_board_decision_routing_next_safe_action_packet_v1"
)

_DECISION_RECORD_FIELD_MODEL: tuple[dict[str, str], ...] = (
    {
        "field_name": "Decision record identifier",
        "description": (
            "Stable template key for a future human-issued decision record; Sprint 156 emits "
            "placeholders only, not executed identifiers."
        ),
    },
    {
        "field_name": "Related sprint chain",
        "description": (
            "Documentation references to Sprint 155 evidence closure, Sprint 154 remediation "
            "queue, and Sprint 153 post-board routing artifact types as audit lineage."
        ),
    },
    {
        "field_name": "Requested runtime scope",
        "description": (
            "Narrative bounds describing what runtime scope would be under consideration; must "
            "remain documentation-only until separate explicit authorization."
        ),
    },
    {
        "field_name": "Requested implementation slice",
        "description": (
            "Narrative bounds for implementation slices tied to M1 planning lanes; not an "
            "execution grant from this sprint."
        ),
    },
    {
        "field_name": "Decision type",
        "description": (
            "Template enumeration placeholder for approve, deny, defer, or blocked—no decision "
            "execution performed by software."
        ),
    },
    {
        "field_name": "Decision status",
        "description": (
            "Template status placeholder (for example draft, pending human review, closed "
            "without authorization); status text is not authorization."
        ),
    },
    {
        "field_name": "Decision date placeholder",
        "description": (
            "Reserved field for a future human-recorded decision date; Sprint 156 does not "
            "set operational dates."
        ),
    },
    {
        "field_name": "Human approver placeholder",
        "description": (
            "Reserved for named human approver attestations outside this codebase; "
            "placeholders do not substitute written human approval."
        ),
    },
    {
        "field_name": "Evidence docket reference",
        "description": (
            "Pointer to human-maintained evidence docket narratives; references are not "
            "decision record execution or audit evidence execution."
        ),
    },
    {
        "field_name": "Denial condition review reference",
        "description": (
            "Cross-check slot linking to documented denial conditions reviewed outside "
            "software execution paths."
        ),
    },
    {
        "field_name": "Risk acceptance reference",
        "description": (
            "Reserved for human risk acceptance registers; Sprint 156 does not accept risks "
            "or waive controls in software."
        ),
    },
    {
        "field_name": "Runtime boundary acknowledgement",
        "description": (
            "Explicit acknowledgement that preview artifacts, approvals evidence, and "
            "decision templates do not expand runtime authorization boundary."
        ),
    },
    {
        "field_name": "Blocked-action acknowledgement",
        "description": (
            "Operator acknowledgement that blocked actions remain blocked unless a separate "
            "approved process lifts them; not an unblock signal from templates."
        ),
    },
    {
        "field_name": "Audit export reference",
        "description": (
            "Template pointer to where audit exports would reside in human systems; no export "
            "execution from Sprint 156 builders."
        ),
    },
    {
        "field_name": "Follow-up action reference",
        "description": (
            "Recommendation-only linkage to next human process steps; excludes runnable "
            "implementation workflows from this packet."
        ),
    },
)

_REQUIRED_AUDIT_EVIDENCE_ARTIFACTS: tuple[str, ...] = (
    "Sprint 155 evidence closure packet reference "
    f"(artifact type `{_PREREQUISITE_SPRINT155_ARTIFACT_TYPE}`)",
    "Sprint 154 remediation queue packet reference "
    f"(artifact type `{_VERIFICATION_SPRINT154_ARTIFACT_TYPE}`)",
    "Sprint 153 post-board routing packet reference "
    f"(artifact type `{_VERIFICATION_SPRINT153_ARTIFACT_TYPE}`)",
    "Human review record",
    "Security review record",
    "Sovereignty and trust review record",
    "Customer validation record",
    "Rollback and support record",
    "Data handling and export record",
    "Runtime boundary acknowledgement",
    "Written approval placeholder",
    "Denial or deferral rationale placeholder",
)

_APPROVAL_EVIDENCE_REQUIREMENTS: tuple[str, ...] = (
    "Approval evidence is not runtime authorization by itself.",
    "Written human approval must be separate and explicit.",
    "Runtime scope must be bounded.",
    "Customer data access must remain blocked unless separately approved.",
    "Source activation must remain blocked unless separately approved.",
    "Production activation must remain blocked unless separately approved.",
    "Pilot launch must remain blocked unless separately approved.",
    "Database migration must remain blocked unless separately approved.",
    "Approval templates do not execute decision records or audit evidence retention.",
    "Bounded scopes must be restated wherever approval narratives appear in human records.",
)

_DENIAL_EVIDENCE_REQUIREMENTS: tuple[str, ...] = (
    "Denial evidence must cite which denial conditions or Sprint packet gates were not met, "
    "using human-authored text outside software execution.",
    "Denial evidence must restate no runtime authorization granted and no board approval "
    "actually granted without substituting a future appeal path.",
    "Denial evidence must preserve blocked-action acknowledgements and no-execution default "
    "until a separate approved process revisits the docket.",
    "Denial rationale placeholders in templates are not executed denials; operators record "
    "final denials only through separate human governance.",
)

_DEFERRAL_EVIDENCE_REQUIREMENTS: tuple[str, ...] = (
    "Deferral evidence must record pending human inputs, scope clarifications, or calendar "
    "dependencies without scheduling interviews or performing customer outreach from software.",
    "Deferral evidence must state deferral is not approval and conveys no runtime "
    "authorization granted.",
    "Deferral evidence must link back to Sprint 155 re-review readiness and evidence closure "
    "packets as documentation lineage, not as execution triggers.",
    "Deferral templates must avoid pilot launch, onboarding, source activation, production "
    "activation, database migration, remediation execution, evidence closure execution, "
    "decision record execution, or audit evidence execution.",
)

_EVIDENCE_RETENTION_AND_EXPORT_EXPECTATIONS: tuple[str, ...] = (
    "Human operators should retain immutable references to Sprint 155 evidence closure, "
    "Sprint 154 remediation queue, and Sprint 153 post-board routing packets plus "
    "review records in governance systems outside this repository.",
    "Retention expectations are policy placeholders; Sprint 156 performs no retention writes, "
    "export jobs, or database migrations.",
    "Audit export references should describe encryption, access class, and sovereign handling "
    "as narrative checklists without live export execution.",
    "Evidence packets should be versioned alongside decision record templates so auditors can "
    "reconcile preview sprints from deterministic artifacts only.",
    "Exports for regulators or customers require separate approvals; templates may not "
    "substitute customer data access or production scope.",
)

_BLOCKED_ACTION_RULES: tuple[str, ...] = (
    "Decision record template assembly is not runtime authorization.",
    "Audit evidence checklist emission is not approval.",
    "Preview-only packets do not convene a re-review board.",
    "Preview-only packets do not execute evidence closure or remediation.",
    "Preview-only packets do not grant board approval actually granted.",
    "No pilot launch may occur from this packet.",
    "No customer onboarding may occur from this packet.",
    "No source activation may occur from this packet.",
    "No production activation may occur from this packet.",
    "Docket-ready labels do not authorize customer outreach or interview scheduling.",
    "Docket-ready labels do not authorize database migration.",
    "Docket-ready labels do not authorize implementation execution.",
)

_NO_EXECUTION_DEFAULT: tuple[str, ...] = (
    "No-execution default: Sprint 156 defines runtime authorization decision record and "
    "audit evidence documentation lanes only; runtime execution, decision record execution, "
    "audit evidence execution, activation, launch, onboarding, outreach, scheduling, board "
    "convening, remediation execution, and evidence closure execution remain closed in "
    "software.",
    "No-execution default: no pilot launch, no customer outreach, no interview scheduling, "
    "no customer onboarding, no customer data access, no database migration, no source "
    "activation, no production activation, no real metric collection, no real pilot "
    "closeout, no optimization execution, no architecture implementation, no implementation "
    "execution, no runtime authorization granted, no board approval actually granted, no "
    "post-board execution, no remediation execution, no evidence closure execution, no "
    "re-review board convened, no decision record execution, no audit evidence execution, "
    "and no runnable implementation workflow may begin from this packet.",
    "No-execution default: decision templates and audit evidence lists are previews; human "
    "operator approval for any execution phase remains mandatory and external.",
)

_RUNTIME_AUTHORIZATION_BOUNDARY: tuple[str, ...] = (
    "Runtime authorization boundary: Sprint 156 prepares documentation describing how a "
    "future decision record and audit evidence packet would be structured; it grants no "
    "runtime authorization granted and no board approval actually granted.",
    "Runtime authorization boundary: preview-only deterministic dict and markdown emission "
    "only; no runtime writes, workers, external calls, decision record execution, audit "
    "evidence execution, evidence closure execution, remediation execution, post-board "
    "execution, re-review board convened, or pilot launch.",
    "Runtime authorization boundary: approval evidence requirements, denial evidence, deferral "
    "evidence, and retention expectations must not be interpreted as authorization to "
    "execute, activate, migrate, onboard, export live data, or close evidence in live "
    "systems.",
)

_SPRINT156_DOES_NOT_BUILD: tuple[str, ...] = (
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
    "Recommendation-only: align decision record field placeholders with Sprint 155 evidence "
    "closure packet sections as a desk exercise—no software execution.",
    "Recommendation-only: map required audit evidence artifacts to human governance folders "
    "without ingesting live records.",
    "Recommendation-only: re-run verification path imports for Sprint 155 and Sprint 154 "
    "artifacts to preserve regression continuity checks.",
    "Recommendation-only: if approval evidence is incomplete, document deferral narratives "
    "using deferral evidence requirements without customer outreach.",
)

_PACKET_EXIT_CRITERIA: tuple[str, ...] = (
    "Sprint 155 prerequisite is named as the re-review board readiness and evidence closure "
    "packet with matching artifact type after Sprint 155 templates.",
    "Verification path retains Sprint 155 re-review board readiness evidence closure "
    "artifact type alongside Sprint 154 evidence remediation queue artifact type for "
    "regression continuity.",
    "Decision record field model enumerates all mandated fields with zero actual counters.",
    "Required audit evidence artifacts list references Sprint 155, Sprint 154, and Sprint "
    "153 packet types plus mandated human and operational records.",
    "Approval evidence requirements, denial evidence requirements, deferral evidence "
    "requirements, evidence retention and export expectations, blocked action rules, "
    "no-execution default, runtime authorization boundary, sprint 156 does not build list, "
    "risks, mitigations, and recommendation-only next safe action options are present.",
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "Decision record template mistaken for authorization",
        "State decision record execution is blocked, audit evidence execution is blocked, "
        "and keep explicit no runtime authorization granted and no board approval actually "
        "granted phrasing in boundary, blocked rules, and no-execution default.",
    ),
    (
        "Sprint 155 prerequisite skipped",
        "Bind prerequisite evidence to Sprint 155 artifact type and section two sequencing "
        "rationale after re-review board readiness and evidence closure packet.",
    ),
    (
        "Sprint 155 or Sprint 154 verification path dropped",
        "Keep both artifact types in verification path keys and regression tests importing "
        "Sprint 155 and Sprint 154 builders.",
    ),
    (
        "Approval evidence treated as sufficient for runtime",
        "State approval evidence is not runtime authorization by itself and written human "
        "approval must be separate and explicit with bounded runtime scope.",
    ),
)

_RECOMMENDED_NEXT_SAFE_ACTION = (
    "The recommended next safe action is recommendation-only: operators should retain "
    "Sprint 155 re-review board readiness and evidence closure packets and Sprint 154 "
    "evidence remediation queue artifacts in the verification path, attach this decision "
    "record and audit evidence model as documentation-only templates, and prepare human-only "
    "authorization materials without starting runtime execution, decision record execution, "
    "audit evidence execution, customer outreach, interview scheduling, customer onboarding, "
    "customer data access, database migration, source activation, production activation, "
    "pilot launch, real metric collection, real pilot closeout, optimization execution, "
    "architecture implementation, implementation execution, runtime authorization granted, "
    "board approval actually granted, post-board execution, remediation execution, evidence "
    "closure execution, re-review board convened, or runnable implementation workflow. Recorded "
    "human operator approval in a separate future authorization process would be required "
    "before any execution phase; Sprint 156 software does not perform that process."
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _decision_record_rows() -> list[dict[str, str]]:
    return [dict(row) for row in _DECISION_RECORD_FIELD_MODEL]


def _risk_payloads() -> list[dict[str, str]]:
    return [{"risk": r, "mitigation": m} for r, m in _RISK_MITIGATIONS]


def build_active_source_activation_m1_runtime_authorization_decision_record_audit_evidence_packet() -> (
    dict[str, Any]
):
    """Return the Sprint 156 M1 runtime authorization decision record and audit evidence packet."""
    proof = {
        "sprint_156_m1_runtime_authz_decision_audit_packet_is_stateless": True,
        "sprint_156_m1_runtime_authz_decision_audit_packet_is_side_effect_free": True,
        "sprint_156_m1_runtime_authz_decision_audit_packet_is_preview_only": True,
        "sprint_156_m1_runtime_authz_decision_audit_packet_performs_no_runtime_work": True,
        "sprint_156_m1_runtime_authz_decision_audit_packet_emits_operator_templates_only": True,
    }
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 156,
        "packet_name": (
            "NativeForge M1 Runtime Authorization Decision Record & Audit Evidence Packet"
        ),
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_present_runtime_authorization_decision_record_audit_evidence_preview_only": True,
        "may_reference_m1_evidence_base_preview_only": True,
        "prerequisite_re_review_board_readiness_evidence_closure_sprint": 155,
        "prerequisite_re_review_board_readiness_evidence_closure_artifact_type": (
            _PREREQUISITE_SPRINT155_ARTIFACT_TYPE
        ),
        "verification_path_re_review_board_readiness_evidence_closure_sprint": 155,
        "verification_path_re_review_board_readiness_evidence_closure_artifact_type": (
            _VERIFICATION_SPRINT155_ARTIFACT_TYPE
        ),
        "verification_path_evidence_remediation_queue_re_review_sprint": 154,
        "verification_path_evidence_remediation_queue_re_review_artifact_type": (
            _VERIFICATION_SPRINT154_ARTIFACT_TYPE
        ),
        "audit_lineage_post_board_decision_routing_reference_sprint": 153,
        "audit_lineage_post_board_decision_routing_reference_artifact_type": (
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
        "actual_decision_record_executions": 0,
        "actual_audit_evidence_executions": 0,
        "decision_record_field_model": _decision_record_rows(),
        "required_audit_evidence_artifacts": list(_REQUIRED_AUDIT_EVIDENCE_ARTIFACTS),
        "approval_evidence_requirements": list(_APPROVAL_EVIDENCE_REQUIREMENTS),
        "denial_evidence_requirements": list(_DENIAL_EVIDENCE_REQUIREMENTS),
        "deferral_evidence_requirements": list(_DEFERRAL_EVIDENCE_REQUIREMENTS),
        "evidence_retention_and_export_expectations": list(
            _EVIDENCE_RETENTION_AND_EXPORT_EXPECTATIONS
        ),
        "blocked_action_rules": list(_BLOCKED_ACTION_RULES),
        "no_execution_default": list(_NO_EXECUTION_DEFAULT),
        "runtime_authorization_boundary": list(_RUNTIME_AUTHORIZATION_BOUNDARY),
        "sprint_156_does_not_build": list(_SPRINT156_DOES_NOT_BUILD),
        "next_safe_action_options": list(_NEXT_SAFE_ACTION_OPTIONS),
        "packet_exit_criteria": list(_PACKET_EXIT_CRITERIA),
        "risks_and_mitigations": _risk_payloads(),
        "recommended_next_safe_action": _RECOMMENDED_NEXT_SAFE_ACTION,
        "sprint_156_m1_runtime_authorization_decision_record_audit_evidence_packet_proof": proof,
    }
    return _json_safe(out)


def render_active_source_activation_m1_runtime_authorization_decision_record_audit_evidence_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render operator markdown (deterministic; uses ``packet`` when provided)."""
    pkt = (
        packet
        if isinstance(packet, dict)
        else build_active_source_activation_m1_runtime_authorization_decision_record_audit_evidence_packet()
    )
    lines: list[str] = [
        "# NativeForge M1 Runtime Authorization Decision Record & Audit Evidence Packet v1",
        "",
        "## 1. Purpose",
        "",
        "This packet is a deterministic, preview-only operator artifact that defines how a "
        "future runtime authorization decision record and audit evidence model would be "
        "structured after Sprint 155's Re-Review Board Readiness & Evidence Closure Packet. "
        "It does not grant runtime authorization, board approval actually granted, source "
        "activation, customer onboarding, pilot launch, production activation, post-board "
        "execution, remediation execution, evidence closure execution, re-review board "
        "convening, decision record execution, audit evidence execution, runtime execution, "
        "live customer data access, customer outreach, interview scheduling, external calls, "
        "database migrations, real metric collection, real pilot closeout, optimization "
        "execution, architecture implementation, implementation execution, or runnable "
        "implementation workflows.",
        "",
        "## 2. Why This Comes After Sprint 155",
        "",
        "Sprint 155 delivered the **Re-Review Board Readiness & Evidence Closure** packet: it "
        "defines evidence closure criteria, re-review docket readiness, sufficiency checks, "
        "owner signoff, rejection and deferral paths, return-to-remediation routing, blocked "
        "action rules, and no-execution defaults while withholding runtime authorization "
        "granted, board approval actually granted, evidence closure execution, remediation "
        "execution, and re-review board convening in software. Sprint 156 is sequential "
        "because operators need a deterministic template for how a **future** runtime "
        "authorization **decision record** and **audit evidence** binder would be assembled "
        "only after re-review board readiness and evidence closure documentation lanes "
        "exist; without Sprint 155, decision templates would lack the closure and docket "
        "framing Sprint 156 extends as documentation-only previews. Sprint 154 evidence "
        "remediation queue artifacts and Sprint 153 post-board routing references remain in "
        "audit lineage lists and the verification path for regression continuity. Sprint 156 "
        "does not replace Sprint 155; it depends on Sprint 155 as prerequisite re-review "
        "board readiness evidence closure context "
        f"(artifact type `{_PREREQUISITE_SPRINT155_ARTIFACT_TYPE}`), "
        "then adds decision record fields, audit artifact requirements, approval and denial "
        "evidence gates, deferral evidence, retention expectations, and blocked-action "
        "acknowledgements—still without granting runtime authorization, board approval "
        "actually granted, decision record execution, audit evidence execution, activation, "
        "launch, onboarding, customer data access, production scope, or post-board execution.",
        "",
        "## 3. Runtime Authorization Decision Record Objective",
        "",
        "Provide deterministic documentation-only scaffolding that describes how a runtime "
        "authorization decision record would be populated for future human governance after "
        "Sprint 155 closure narratives exist, while keeping execution, deployment, measurement, "
        "decision record execution, audit evidence execution, board convening, remediation "
        "execution, evidence closure execution, and post-board execution lanes closed in this "
        "sprint.",
        "",
        "## 4. Decision Record Field Model",
        "",
        "The following fields are templates for future human records; none imply authorization "
        "from Sprint 156 software output:",
        "",
    ]
    for row in pkt.get("decision_record_field_model") or _decision_record_rows():
        if not isinstance(row, dict):
            continue
        fn = row.get("field_name")
        if isinstance(fn, str) and fn.strip():
            lines.append(f"### {fn}")
            lines.append("")
        desc = row.get("description")
        if isinstance(desc, str) and desc.strip():
            lines.append(desc)
            lines.append("")
    lines.extend(
        [
            "",
            "## 5. Required Audit Evidence Artifacts",
            "",
            "The following artifacts are checklist labels for human systems; none execute "
            "retention, export, or authorization from Sprint 156 builders:",
            "",
        ]
    )
    for item in pkt.get("required_audit_evidence_artifacts") or list(
        _REQUIRED_AUDIT_EVIDENCE_ARTIFACTS
    ):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 6. Approval Evidence Requirements", ""])
    for item in pkt.get("approval_evidence_requirements") or list(
        _APPROVAL_EVIDENCE_REQUIREMENTS
    ):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 7. Denial Evidence Requirements", ""])
    for item in pkt.get("denial_evidence_requirements") or list(
        _DENIAL_EVIDENCE_REQUIREMENTS
    ):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 8. Deferral Evidence Requirements", ""])
    for item in pkt.get("deferral_evidence_requirements") or list(
        _DEFERRAL_EVIDENCE_REQUIREMENTS
    ):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 9. Evidence Retention and Export Expectations", ""])
    for item in pkt.get("evidence_retention_and_export_expectations") or list(
        _EVIDENCE_RETENTION_AND_EXPORT_EXPECTATIONS
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
            "## 12. What Sprint 156 Does Not Build",
            "",
            "Sprint 156 explicitly does not build:",
            "",
        ]
    )
    for item in pkt.get("sprint_156_does_not_build") or list(_SPRINT156_DOES_NOT_BUILD):
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
