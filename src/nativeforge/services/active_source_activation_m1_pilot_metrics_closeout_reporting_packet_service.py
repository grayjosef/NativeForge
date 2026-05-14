"""Sprint 144: M1 pilot metrics and closeout reporting packet (preview-only).

Deterministic operator artifact that defines metrics framing, evidence capture templates,
closeout reporting structure, and human review format for a future M1 pilot without collecting
real metrics or running closeout workflows. It follows Sprint 143 operational launch simulation
outputs as prerequisite rehearsal context and remains simulation or preview-only: no runtime
execution, live customer data, onboarding, source activation, production activation, external calls,
database migrations, or runnable automation.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = "nf_active_source_activation_m1_pilot_metrics_closeout_reporting_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

_PREREQUISITE_SPRINT143_ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_pilot_operational_launch_simulation_packet_v1"
)
_VERIFICATION_SPRINT142_ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_pilot_implementation_pre_launch_checklist_packet_v1"
)
_VERIFICATION_SPRINT141_ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_controlled_build_authorization_review_packet_v1"
)

_METRICS_DOMAIN_DISCLAIMER = (
    "This metric domain is planning and template definition only; it is not real metric "
    "collection, is not pilot launch, is not customer onboarding, is not source activation, is "
    "not production activation, and is not runtime execution unless a later sprint records "
    "explicit human operator authorization outside this packet."
)

_PILOT_METRICS_FRAMEWORK: tuple[tuple[str, str], ...] = (
    (
        "Readiness evidence completeness",
        "Defines how operators would score evidence coverage against Sprint 142 checklist outputs "
        "and Sprint 143 simulation notes using qualitative scales only—no ingestion of live "
        "telemetry. " + _METRICS_DOMAIN_DISCLAIMER,
    ),
    (
        "Human gate completion",
        "Defines how human gate checkpoints from prior packets would be summarized in a closeout "
        "without auto-approving any gate. " + _METRICS_DOMAIN_DISCLAIMER,
    ),
    (
        "Deferred item resolution status",
        "Defines disposition labels for deferred items and exceptions without muting open risk; "
        "still no workflow engine. " + _METRICS_DOMAIN_DISCLAIMER,
    ),
    (
        "Sovereignty and trust compliance readiness",
        "Defines how sovereignty, residency, consent, and trust-boundary evidence would be "
        "referenced in a report—no enforcement claims from this sprint. " + _METRICS_DOMAIN_DISCLAIMER,
    ),
    (
        "Operator handoff readiness",
        "Defines handoff completeness criteria for named operators only as narrative readiness, "
        "not system handoff execution. " + _METRICS_DOMAIN_DISCLAIMER,
    ),
    (
        "Support and escalation readiness",
        "Defines how support tiers and escalation paths rehearsed in Sprint 143 would be reflected "
        "in closeout text—no ticket system calls. " + _METRICS_DOMAIN_DISCLAIMER,
    ),
    (
        "Rollback rehearsal readiness",
        "Defines how tabletop rollback rehearsal coverage would be summarized without executing "
        "rollback. " + _METRICS_DOMAIN_DISCLAIMER,
    ),
    (
        "Monitoring rehearsal readiness",
        "Defines how monitoring rehearsal expectations would be scored qualitatively without "
        "wiring monitors or ingesting live signals. " + _METRICS_DOMAIN_DISCLAIMER,
    ),
    (
        "Documentation closeout readiness",
        "Defines which documentation artifacts must appear in a future closeout appendix as "
        "pointers only—no document repository mutations here. " + _METRICS_DOMAIN_DISCLAIMER,
    ),
    (
        "Recommendation confidence for next phase",
        "Defines how operators would state confidence in a next-phase recommendation using "
        "human-authored rationale fields—not model scores or collected KPIs. "
        + _METRICS_DOMAIN_DISCLAIMER,
    ),
)

_CLOSEOUT_REPORTING_STRUCTURE: tuple[tuple[str, str], ...] = (
    (
        "Executive summary",
        "One-page operator-facing summary of readiness posture, blocked items, and recommendation "
        "stance without asserting pilot outcomes.",
    ),
    (
        "Evidence reviewed",
        "Pointer list to Sprint 142, Sprint 143, Sprint 141, Sprint 140, and earlier sprint "
        "artifacts with explicit unknowns where pointers are missing.",
    ),
    (
        "Gates passed",
        "Human-attested list of gates satisfied in planning or rehearsal layers only; silence "
        "cannot imply pass.",
    ),
    (
        "Gates blocked",
        "Human-attested list of blocked gates with owners and follow-ups; still preview-only.",
    ),
    (
        "Deferred items",
        "Table of deferrals, exceptions, and dates tied to Sprint 142 and Sprint 143 outputs.",
    ),
    (
        "Risk findings",
        "Narrative risk register excerpt for closeout readers referencing mitigations from this "
        "packet.",
    ),
    (
        "Sovereignty and trust findings",
        "Explicit subsection restating sovereignty and trust observations without claiming "
        "production enforcement.",
    ),
    (
        "Operator recommendation",
        "Human-authored recommendation for next phase confidence and sequencing—software cannot "
        "auto-submit this section.",
    ),
    (
        "Required human approvals before any future runtime step",
        "Checklist of named human operator approvals required before any future runtime, "
        "activation, onboarding, migration, or live metric capture—this sprint does not grant them.",
    ),
)

_REQUIRED_EVIDENCE_INPUTS: tuple[tuple[str, str, str], ...] = (
    (
        "Sprint 143 M1 pilot operational launch simulation packet",
        "Sprint 143",
        "Mandatory prerequisite: treat "
        f"{_PREREQUISITE_SPRINT143_ARTIFACT_TYPE} as the operational launch simulation rehearsal "
        "artifact before metrics and closeout reporting templates are treated as grounded.",
    ),
    (
        "Sprint 142 M1 pilot implementation pre-launch checklist packet",
        "Sprint 142",
        "Must remain visible as checklist readiness evidence "
        f"({_VERIFICATION_SPRINT142_ARTIFACT_TYPE}) in the verification path; Sprint 144 does not "
        "replace Sprint 142 outputs.",
    ),
    (
        "Sprint 141 controlled build authorization review packet",
        "Sprint 141",
        "Authorization review continuity "
        f"({_VERIFICATION_SPRINT141_ARTIFACT_TYPE}) stays in the verification path for regression "
        "coverage alongside Sprint 143.",
    ),
    (
        "Sprint 140 demo-to-build transition closeout packet",
        "Sprint 140",
        "Continuity evidence for transition closeout statuses and deferrals, referenced as "
        "read-only context in the verification path.",
    ),
    (
        "Prior sprint evidence chain summary (131–139)",
        "Sprints 131–139",
        "Summarized or explicitly labeled unknown; closeout template completeness cannot rely on "
        "unstated assumptions from earlier readiness packets.",
    ),
)

_EVIDENCE_CAPTURE_REQUIREMENTS: tuple[str, ...] = (
    "Evidence capture is described as filenames, artifact types, and human note fields only; "
    "Sprint 144 does not open customer systems or fetch live payloads.",
    "Screenshots, log excerpts, and decision records referenced in templates must be redacted or "
    "synthetic in preview artifacts—no customer-identifying material in this builder.",
    "Each evidence pointer must name a sprint artifact or an explicit unknown label; gaps must "
    "remain visible in closeout drafts.",
    "Human operators must attest to evidence authenticity outside this software-only packet.",
)

_HUMAN_REVIEW_AND_APPROVAL_REQUIREMENTS: tuple[str, ...] = (
    "Human operator approval is required to treat any closeout draft as complete; software-only "
    "checkboxes cannot substitute for human operator approval.",
    "Human-authored sign-off fields must name approvers, dates, and scope boundaries before any "
    "future runtime step is attempted.",
    "Simulated or templated metrics must never be promoted to live KPIs without a separate "
    "authorized collection sprint and explicit human approvals.",
    "Binding go-forward decisions remain outside Sprint 144; this packet only defines reporting "
    "structure and preview templates.",
    "Separate human operator approvals remain required for pilot launch, onboarding, source "
    "activation, production activation, database migration, real metric collection, and any "
    "runnable closeout workflow.",
)

_DEFERRED_ITEM_AND_EXCEPTION_HANDLING: tuple[str, ...] = (
    "Deferred items carry owners, review dates, and explicit open or mitigated labels; deferral "
    "cannot be silently treated as closure.",
    "Exceptions require human narrative, impact class, and whether they block gates; no "
    "automatic exception clearing.",
    "Items deferred from Sprint 142 or Sprint 143 must be traceable in the deferred items section "
    "of the closeout structure without rewriting history.",
    "New deferrals discovered during template review are recorded as planning inputs only—no "
    "ticket or workflow mutations from this sprint.",
)

_SOVEREIGNTY_TRUST_AND_DATA_HANDLING_CONSTRAINTS: tuple[str, ...] = (
    "Customer owns its data; Sprint 144 artifacts must not embed or fetch live customer data.",
    "Sovereignty, residency, consent, and export expectations from prior packets must be visible "
    "in closeout templates without claiming production enforcement from this sprint.",
    "Trust-boundary language must not imply source activation or production activation from "
    "template completion.",
    "Provenance for evidence pointers must remain traceable to named sprint artifacts or explicit "
    "unknown labels.",
    "Operator-facing template notes must avoid customer-identifying details in this "
    "preview-only builder.",
    "Human judgment remains final for sovereignty, trust, and data-handling outcomes tied to "
    "closeout reporting.",
)

_SPRINT144_DOES_NOT_BUILD: tuple[str, ...] = (
    "no pilot launch",
    "no customer onboarding",
    "no customer data access",
    "no database migration",
    "no source activation",
    "no production activation",
    "no real metric collection",
    "no runnable closeout workflow",
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

_CLOSEOUT_EXIT_CRITERIA: tuple[str, ...] = (
    "Sprint 143 prerequisite is named with artifact type and treated as mandatory operational "
    "launch simulation evidence before metrics and closeout templates are treated as grounded.",
    "Sprint 142 checklist packet and Sprint 141 authorization review remain referenced in the "
    "verification path for regression continuity.",
    "All ten pilot metric domains are enumerated with preview-only disclaimers.",
    "All nine closeout reporting sections are enumerated with human approval and sovereignty cues.",
    "Evidence capture, human review, deferral handling, sovereignty constraints, does-not-build "
    "scope, and exit criteria are listed without contradiction.",
    "Preview-only posture and zero actual counters are reflected in the structured packet and "
    "markdown render.",
    "Risks and mitigations are recorded before Sprint 145 recommendation-only guidance.",
    "Sprint 145 guidance remains recommendation-only and does not authorize launch, activation, "
    "or metric collection.",
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "Templates mistaken for live KPI dashboards",
        "Label every metric domain as planning-only and forbid real metric collection keys from "
        "incrementing in this sprint.",
    ),
    (
        "Sprint 143 simulation skipped",
        "Bind prerequisite evidence to the Sprint 143 artifact type and forbid silent substitution.",
    ),
    (
        "Closeout structure treated as executed workflow",
        "Keep no_runnable_plan true and state explicitly that no runnable closeout workflow is "
        "built here.",
    ),
    (
        "Customer data pulled into closeout drafts",
        "Forbid customer data access in requirements and keep actual_customer_data_access at zero.",
    ),
    (
        "Human approvals implied by software rendering",
        "Require explicit human operator approval language and named approver fields in templates.",
    ),
    (
        "Sprint 145 treated as execution authorization",
        "Label Sprint 145 as recommendation-only and separate from any launch authorization.",
    ),
)

_SPRINT145_RECOMMENDED_NEXT_STEP = (
    "Sprint 145 is recommendation-only: operators should either (a) remain preview-only with "
    "additional planning artifacts, or (b) open a future sprint explicitly authorized for "
    "bounded measurement design, evidence-backed KPI definitions, human-gated collection rules, "
    "and recorded human operator approvals outside Sprint 144. No pilot launch, source "
    "activation, production activation, customer onboarding, runtime execution, real metric "
    "collection, database migration, or runnable closeout workflow should begin from Sprint 144 "
    "output alone."
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _metrics_framework_payloads() -> list[dict[str, str]]:
    return [{"metric_domain": d, "planning_focus": f} for d, f in _PILOT_METRICS_FRAMEWORK]


def _closeout_sections_payloads() -> list[dict[str, str]]:
    return [{"section": s, "outline": o} for s, o in _CLOSEOUT_REPORTING_STRUCTURE]


def _evidence_input_payloads() -> list[dict[str, str]]:
    return [
        {"evidence_label": lab, "sprint_reference": ref, "expectation_note": note}
        for lab, ref, note in _REQUIRED_EVIDENCE_INPUTS
    ]


def _risk_payloads() -> list[dict[str, str]]:
    return [{"risk": r, "mitigation": m} for r, m in _RISK_MITIGATIONS]


def build_active_source_activation_m1_pilot_metrics_closeout_reporting_packet() -> dict[str, Any]:
    """Return the Sprint 144 M1 pilot metrics and closeout reporting packet (deterministic)."""
    proof = {
        "sprint_144_m1_pilot_metrics_closeout_reporting_packet_is_stateless": True,
        "sprint_144_m1_pilot_metrics_closeout_reporting_packet_is_side_effect_free": True,
        "sprint_144_m1_pilot_metrics_closeout_reporting_packet_is_preview_only": True,
        "sprint_144_m1_pilot_metrics_closeout_reporting_packet_performs_no_runtime_work": True,
        "sprint_144_m1_pilot_metrics_closeout_reporting_packet_emits_operator_templates_only": True,
    }
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 144,
        "packet_name": "NativeForge M1 Pilot Metrics & Closeout Reporting Packet",
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_define_pilot_metrics_framework_preview_only": True,
        "may_define_closeout_reporting_structure_preview_only": True,
        "may_define_evidence_capture_templates_without_collection": True,
        "may_define_human_review_and_approval_templates_only": True,
        "may_define_deferred_item_and_exception_handling_templates_only": True,
        "prerequisite_operational_launch_simulation_sprint": 143,
        "prerequisite_operational_launch_simulation_artifact_type": _PREREQUISITE_SPRINT143_ARTIFACT_TYPE,
        "verification_path_pre_launch_checklist_artifact_type": _VERIFICATION_SPRINT142_ARTIFACT_TYPE,
        "verification_path_authorization_review_artifact_type": _VERIFICATION_SPRINT141_ARTIFACT_TYPE,
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
        "pilot_metrics_framework": _metrics_framework_payloads(),
        "closeout_reporting_structure": _closeout_sections_payloads(),
        "required_evidence_inputs": _evidence_input_payloads(),
        "evidence_capture_requirements": list(_EVIDENCE_CAPTURE_REQUIREMENTS),
        "human_review_and_approval_requirements": list(_HUMAN_REVIEW_AND_APPROVAL_REQUIREMENTS),
        "deferred_item_and_exception_handling": list(_DEFERRED_ITEM_AND_EXCEPTION_HANDLING),
        "sovereignty_trust_and_data_handling_constraints": list(_SOVEREIGNTY_TRUST_AND_DATA_HANDLING_CONSTRAINTS),
        "sprint_144_does_not_build": list(_SPRINT144_DOES_NOT_BUILD),
        "closeout_exit_criteria": list(_CLOSEOUT_EXIT_CRITERIA),
        "risks_and_mitigations": _risk_payloads(),
        "sprint_145_recommended_next_step": _SPRINT145_RECOMMENDED_NEXT_STEP,
        "pilot_metrics_domain_universal_disclaimer": _METRICS_DOMAIN_DISCLAIMER,
        "sprint_144_m1_pilot_metrics_closeout_reporting_packet_proof": proof,
    }
    return _json_safe(out)


def render_active_source_activation_m1_pilot_metrics_closeout_reporting_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render the operator-facing markdown packet (deterministic; uses ``packet`` when provided)."""
    pkt = (
        packet
        if isinstance(packet, dict)
        else build_active_source_activation_m1_pilot_metrics_closeout_reporting_packet()
    )
    lines: list[str] = [
        "# NativeForge M1 Pilot Metrics & Closeout Reporting Packet v1",
        "",
        "## 1. Purpose",
        "",
        "This packet is a deterministic, preview-only operator artifact that defines the metrics "
        "lens, evidence capture expectations, closeout reporting structure, and human review format "
        "for a future M1 pilot without collecting real metrics or running closeout workflows. It "
        "templates qualitative readiness domains and report sections only. It does not authorize "
        "runtime execution, pilot launch, customer onboarding, source activation, production "
        "activation, live customer data access, external calls, database migrations, real metric "
        "collection, or runnable closeout automation.",
        "",
        "## 2. Why This Comes After Sprint 143",
        "",
        "Sprint 143 delivered the M1 pilot operational launch simulation packet: a structured, "
        "simulation-only rehearsal of launch-day coordination, handoffs, escalation tabletops, "
        "rollback and monitoring rehearsals, and simulated human decision records—still without "
        "execution or activation. Sprint 144 is intentionally sequential: operators first anchor "
        "on that operational launch simulation artifact as prerequisite rehearsal evidence, then "
        "use this packet to define how metrics framing and closeout reporting would be structured "
        "after such a rehearsal—still as preview templates only. Sprint 144 does not replace Sprint "
        "142 checklist outputs or Sprint 141 authorization review references in the broader "
        "verification path.",
        "",
        "## 3. Metrics and Closeout Objective",
        "",
        "Provide a single planning surface that names pilot metric domains as qualitative readiness "
        "and reporting sections as human-authored closeout scaffolding. The objective is "
        "traceability and approval discipline for a hypothetical closeout, not measurement, "
        "ingestion, onboarding, activation, or runtime work.",
        "",
        "## 4. Required Evidence Inputs",
        "",
    ]
    for row in pkt.get("required_evidence_inputs") or _evidence_input_payloads():
        if isinstance(row, dict):
            lab = row.get("evidence_label")
            ref = row.get("sprint_reference")
            note = row.get("expectation_note")
            if isinstance(lab, str) and isinstance(ref, str) and isinstance(note, str):
                lines.append(f"- **{lab}** ({ref}): {note}")
    lines.extend(["", "## 5. Pilot Metrics Framework", "", "Each domain is preview-only:", ""])
    for row in pkt.get("pilot_metrics_framework") or _metrics_framework_payloads():
        if isinstance(row, dict):
            d = row.get("metric_domain")
            f = row.get("planning_focus")
            if isinstance(d, str) and isinstance(f, str):
                lines.append(f"### {d}")
                lines.append("")
                lines.append(f)
                lines.append("")
    u = pkt.get("pilot_metrics_domain_universal_disclaimer") or _METRICS_DOMAIN_DISCLAIMER
    if isinstance(u, str) and u.strip():
        lines.extend(["**Universal metric-domain disclaimer**:", "", u, ""])
    lines.extend(["", "## 6. Closeout Reporting Structure", ""])
    for row in pkt.get("closeout_reporting_structure") or _closeout_sections_payloads():
        if isinstance(row, dict):
            s = row.get("section")
            o = row.get("outline")
            if isinstance(s, str) and isinstance(o, str):
                lines.append(f"- **{s}**: {o}")
    lines.extend(["", "## 7. Evidence Capture Requirements", ""])
    for item in pkt.get("evidence_capture_requirements") or list(_EVIDENCE_CAPTURE_REQUIREMENTS):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 8. Human Review and Approval Requirements", ""])
    for item in pkt.get("human_review_and_approval_requirements") or list(
        _HUMAN_REVIEW_AND_APPROVAL_REQUIREMENTS
    ):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 9. Deferred Item and Exception Handling", ""])
    for item in pkt.get("deferred_item_and_exception_handling") or list(
        _DEFERRED_ITEM_AND_EXCEPTION_HANDLING
    ):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 10. Sovereignty, Trust, and Data Handling Constraints", ""])
    for item in pkt.get("sovereignty_trust_and_data_handling_constraints") or list(
        _SOVEREIGNTY_TRUST_AND_DATA_HANDLING_CONSTRAINTS
    ):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 11. What Sprint 144 Does Not Build", "", "Sprint 144 explicitly does not build:", ""])
    for item in pkt.get("sprint_144_does_not_build") or list(_SPRINT144_DOES_NOT_BUILD):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 12. Exit Criteria", ""])
    for c in pkt.get("closeout_exit_criteria") or list(_CLOSEOUT_EXIT_CRITERIA):
        if isinstance(c, str) and c.strip():
            lines.append(f"- {c}")
    lines.extend(["", "## 13. Risks and Mitigations", ""])
    for row in pkt.get("risks_and_mitigations") or _risk_payloads():
        if isinstance(row, dict):
            r = row.get("risk")
            m = row.get("mitigation")
            if isinstance(r, str) and isinstance(m, str):
                lines.append(f"- **Risk**: {r} — **Mitigation**: {m}")
    lines.extend(
        [
            "",
            "## 14. Sprint 145 Recommended Next Step",
            "",
            pkt.get("sprint_145_recommended_next_step") or _SPRINT145_RECOMMENDED_NEXT_STEP,
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
