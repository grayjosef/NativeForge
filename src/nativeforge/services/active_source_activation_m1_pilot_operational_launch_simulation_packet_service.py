"""Sprint 143: M1 pilot operational launch simulation packet (preview-only).

Deterministic operator artifact that rehearses the operational launch sequence for a future M1
pilot without launching anything. It follows Sprint 142 pre-launch checklist readiness and models
handoffs, evidence checks, escalation, rollback rehearsal, monitoring expectations, and a final
simulated no-go/go-style decision record only—no runtime execution, customer data, onboarding,
source activation, production activation, external calls, or runnable launch plans.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = "nf_active_source_activation_m1_pilot_operational_launch_simulation_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

_PREREQUISITE_SPRINT142_ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_pilot_implementation_pre_launch_checklist_packet_v1"
)
_PREREQUISITE_SPRINT141_ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_controlled_build_authorization_review_packet_v1"
)

_SIMULATION_DOMAIN_DISCLAIMER = (
    "This step is simulation-only rehearsal; it is not pilot launch, is not customer onboarding, "
    "is not source activation, is not production activation, and is not runtime execution unless "
    "a later sprint records explicit human operator authorization outside this packet."
)

_SIMULATED_LAUNCH_SEQUENCE: tuple[tuple[str, str], ...] = (
    (
        "Evidence package review",
        "Operators walk through evidence pointers and Sprint 142 checklist outputs in read-only "
        "fashion, confirming gaps are labeled and Sprint 141 authorization evidence remains "
        "traceable. " + _SIMULATION_DOMAIN_DISCLAIMER,
    ),
    (
        "Environment boundary review",
        "Operators restate allowed environments for any future work and confirm language cannot "
        "silently imply production scope. " + _SIMULATION_DOMAIN_DISCLAIMER,
    ),
    (
        "Human gate confirmation",
        "Operators rehearse who states mandatory human operator approvals and how human-authored "
        "decision records are captured without software-only substitutes. "
        + _SIMULATION_DOMAIN_DISCLAIMER,
    ),
    (
        "Deferred item review",
        "Operators enumerate deferred items with owners and dates, confirming deferrals cannot "
        "read as cleared readiness. " + _SIMULATION_DOMAIN_DISCLAIMER,
    ),
    (
        "Support owner confirmation",
        "Operators confirm named support owners and escalation paths as rehearsal inputs only—no "
        "live ticket queues or customer intake. " + _SIMULATION_DOMAIN_DISCLAIMER,
    ),
    (
        "Rollback rehearsal",
        "Operators verbally or documentarily rehearse rollback triggers and owner actions without "
        "executing rollback against any system. " + _SIMULATION_DOMAIN_DISCLAIMER,
    ),
    (
        "Monitoring checkpoint rehearsal",
        "Operators rehearse which signals would be watched post-authorization and how evidence "
        "would be captured, without enabling production monitors or ingesting live data here. "
        + _SIMULATION_DOMAIN_DISCLAIMER,
    ),
    (
        "Final simulated decision record",
        "Operators record a simulated no-go, go, or remain-preview-only outcome in human-authored "
        "fields explicitly labeled as simulation-only and not binding authorization to launch. "
        + _SIMULATION_DOMAIN_DISCLAIMER,
    ),
)

_SIMULATION_EVIDENCE_INPUTS: tuple[tuple[str, str, str], ...] = (
    (
        "Sprint 142 M1 pilot implementation pre-launch checklist packet",
        "Sprint 142",
        "Mandatory prerequisite: treat "
        f"{_PREREQUISITE_SPRINT142_ARTIFACT_TYPE} as completed checklist planning evidence before "
        "operational launch simulation is treated as grounded.",
    ),
    (
        "Sprint 141 controlled build authorization review packet",
        "Sprint 141",
        "Must remain visible as authorization review evidence "
        f"({_PREREQUISITE_SPRINT141_ARTIFACT_TYPE}) in the verification path; Sprint 143 does not "
        "replace Sprint 141 outputs.",
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
        "Summarized or explicitly labeled unknown; simulation completeness cannot rely on unstated "
        "assumptions from earlier readiness packets.",
    ),
    (
        "Human decision record template (simulation-labeled)",
        "Cross-cutting",
        "Fields ready for simulated no-go, go, or remain-preview-only outcomes with explicit "
        "simulation-only labeling and human operator authorship requirements.",
    ),
)

_OPERATOR_HANDOFF_AND_ROLE_READINESS: tuple[tuple[str, str], ...] = (
    (
        "Primary operator handoff",
        "Names who receives simulation notes, evidence pointers, and decision rehearsal outputs as "
        "read-only handoff without activating systems.",
    ),
    (
        "Secondary operator coverage",
        "Names backup coverage for rehearsal continuity if the primary operator is unavailable; "
        "still no execution or onboarding.",
    ),
    (
        "Engineering liaison (read-only)",
        "Identifies who answers clarifying questions about bounded future work without starting "
        "implementation from this sprint.",
    ),
    (
        "Security and trust reviewer",
        "Confirms sovereignty and trust language is restated during simulation; no customer data "
        "access in this artifact.",
    ),
)

_SUPPORT_ESCALATION_AND_ROLLBACK_REHEARSAL: tuple[tuple[str, str], ...] = (
    (
        "Support escalation path rehearsal",
        "Operators trace escalation tiers and owners as a tabletop path only; no external calls or "
        "ticket system mutations.",
    ),
    (
        "Rollback rehearsal tabletop",
        "Operators describe rollback triggers, communications, and owner sequence without running "
        "rollback tooling or touching databases.",
    ),
    (
        "Customer-visible incident rehearsal boundary",
        "Rehearsal language stays generic; no live customer data, no customer onboarding, and no "
        "pilot launch messaging.",
    ),
)

_MONITORING_AND_EVIDENCE_CAPTURE_EXPECTATIONS: tuple[str, ...] = (
    "Monitoring expectations are documented as future signal lists and evidence capture templates "
    "only; Sprint 143 does not enable production telemetry or scrape live sources.",
    "Evidence capture rehearsal names where logs, screenshots, or human notes would be filed after "
    "a hypothetical authorization—still without collecting customer-identifying material here.",
    "Checkpoint owners rehearse who would acknowledge each monitoring milestone in a real launch, "
    "without performing those acknowledgments against production systems in this sprint.",
    "Alert routing is described, not wired; no pager integrations or webhooks execute from this "
    "packet.",
)

_HUMAN_DECISION_RECORD_REQUIREMENTS: tuple[str, ...] = (
    "Human operator judgment is required to record any simulated no-go, simulated go, or "
    "simulated remain-preview-only outcome; software-only toggles cannot substitute.",
    "Simulated go does not authorize pilot launch, source activation, production activation, "
    "runtime execution, customer onboarding, or customer data access.",
    "Simulated no-go must be an explicit human-authored statement with reasons and follow-up "
    "owners; silence cannot imply no-go.",
    "Human-authored decision records must label outcomes as simulation-only and state that binding "
    "authorization requires a separate explicit authorization sprint.",
    "Separate human operator approvals remain required for any future real launch versus this "
    "rehearsal artifact.",
    "Any wording resembling production go-live must be paired with the simulation-only disclaimer "
    "in operator training materials referencing this packet.",
)

_SOVEREIGNTY_TRUST_AND_DATA_HANDLING_CONSTRAINTS: tuple[str, ...] = (
    "Customer owns its data; Sprint 143 artifacts must not embed or fetch live customer data.",
    "Sovereignty, residency, consent, and export expectations from prior packets must be visible "
    "during simulation without claiming production enforcement from this sprint.",
    "Trust-boundary language must not imply source activation or production activation from "
    "simulation completion.",
    "Provenance for evidence pointers must remain traceable to named sprint artifacts or explicit "
    "unknown labels.",
    "Operator-facing rehearsal notes must avoid customer-identifying details in this "
    "preview-only builder.",
    "Human judgment remains final for sovereignty, trust, and data-handling outcomes tied to the "
    "simulation.",
)

_SPRINT143_DOES_NOT_BUILD: tuple[str, ...] = (
    "no pilot launch",
    "no customer onboarding",
    "no customer data access",
    "no database migration",
    "no source activation",
    "no production activation",
    "no runnable launch plan",
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

_SIMULATION_EXIT_CRITERIA: tuple[str, ...] = (
    "Sprint 142 prerequisite is named with artifact type and treated as mandatory pre-launch "
    "checklist evidence before simulation sign-off.",
    "Sprint 141 authorization review and Sprint 140 closeout remain referenced in the verification "
    "path.",
    "All eight simulated launch sequence steps are enumerated with simulation-only disclaimers.",
    "Operator handoff, support and rollback rehearsal, monitoring expectations, human decision "
    "record requirements, sovereignty constraints, and does-not-build scope are listed without "
    "contradiction.",
    "Preview-only posture and zero actual counters are reflected in the structured packet and "
    "markdown render.",
    "Risks and mitigations are recorded before Sprint 144 recommendation-only guidance.",
    "Sprint 144 guidance remains recommendation-only and does not authorize launch or activation.",
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "Simulation mistaken for authorized launch",
        "Title artifacts as preview-only simulation and repeat not pilot launch, not customer "
        "onboarding, not source activation, and not production activation beside every sequence "
        "step.",
    ),
    (
        "Sprint 142 checklist skipped",
        "Bind prerequisite evidence to the Sprint 142 artifact type and forbid silent substitution.",
    ),
    (
        "Simulated go treated as binding authorization",
        "Require human-authored simulation-only labels and explicit separate authorization sprint "
        "language in decision record requirements.",
    ),
    (
        "Rollback rehearsal triggers real changes",
        "Keep rollback rehearsal as tabletop narrative only with zero actual counters and "
        "no_runnable_plan true.",
    ),
    (
        "Monitoring rehearsal enables live telemetry",
        "Describe monitoring only as expectations and forbid wiring integrations from this sprint.",
    ),
    (
        "Customer data enters simulation artifacts",
        "Forbid customer data access in requirements and keep actual_customer_data_access at zero.",
    ),
    (
        "Sprint 144 treated as execution authorization",
        "Label Sprint 144 as recommendation-only and separate from any launch authorization.",
    ),
)

_SPRINT144_RECOMMENDED_NEXT_STEP = (
    "Sprint 144 is recommendation-only: operators should either (a) remain preview-only with "
    "additional planning or rehearsal artifacts, or (b) open a future sprint explicitly "
    "authorized for binding decisions, bounded engineering scope, rollback owners, environment "
    "boundaries, and human operator approvals recorded outside Sprint 143. No pilot launch, source "
    "activation, production activation, customer onboarding, runtime execution, or runnable launch "
    "plan should begin from Sprint 143 output alone."
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _simulation_sequence_payloads() -> list[dict[str, str]]:
    return [{"step": s, "rehearsal_focus": d} for s, d in _SIMULATED_LAUNCH_SEQUENCE]


def _evidence_input_payloads() -> list[dict[str, str]]:
    return [
        {"evidence_label": lab, "sprint_reference": ref, "expectation_note": note}
        for lab, ref, note in _SIMULATION_EVIDENCE_INPUTS
    ]


def _handoff_payloads() -> list[dict[str, str]]:
    return [{"handoff_area": a, "readiness_focus": b} for a, b in _OPERATOR_HANDOFF_AND_ROLE_READINESS]


def _support_rollback_payloads() -> list[dict[str, str]]:
    return [{"topic": t, "rehearsal_note": n} for t, n in _SUPPORT_ESCALATION_AND_ROLLBACK_REHEARSAL]


def _risk_payloads() -> list[dict[str, str]]:
    return [{"risk": r, "mitigation": m} for r, m in _RISK_MITIGATIONS]


def build_active_source_activation_m1_pilot_operational_launch_simulation_packet() -> dict[str, Any]:
    """Return the Sprint 143 M1 pilot operational launch simulation packet (deterministic)."""
    proof = {
        "sprint_143_m1_pilot_operational_launch_simulation_packet_is_stateless": True,
        "sprint_143_m1_pilot_operational_launch_simulation_packet_is_side_effect_free": True,
        "sprint_143_m1_pilot_operational_launch_simulation_packet_is_preview_only": True,
        "sprint_143_m1_pilot_operational_launch_simulation_packet_performs_no_runtime_work": True,
        "sprint_143_m1_pilot_operational_launch_simulation_packet_emits_operator_simulation_only": True,
    }
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 143,
        "packet_name": "NativeForge M1 Pilot Operational Launch Simulation Packet",
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_define_operational_launch_simulation_readiness": True,
        "may_define_simulation_evidence_inputs": True,
        "may_define_simulated_launch_sequence": True,
        "may_define_operator_handoff_and_role_readiness": True,
        "may_define_support_escalation_and_rollback_rehearsal": True,
        "may_define_monitoring_and_evidence_capture_expectations": True,
        "may_define_human_decision_record_requirements": True,
        "may_rehearse_launch_path_without_authorization": True,
        "prerequisite_pre_launch_checklist_sprint": 142,
        "prerequisite_pre_launch_checklist_artifact_type": _PREREQUISITE_SPRINT142_ARTIFACT_TYPE,
        "verification_path_authorization_review_artifact_type": _PREREQUISITE_SPRINT141_ARTIFACT_TYPE,
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
        "simulated_launch_sequence": _simulation_sequence_payloads(),
        "simulation_evidence_inputs": _evidence_input_payloads(),
        "operator_handoff_and_role_readiness": _handoff_payloads(),
        "support_escalation_and_rollback_rehearsal": _support_rollback_payloads(),
        "monitoring_and_evidence_capture_expectations": list(_MONITORING_AND_EVIDENCE_CAPTURE_EXPECTATIONS),
        "human_decision_record_requirements": list(_HUMAN_DECISION_RECORD_REQUIREMENTS),
        "sovereignty_trust_and_data_handling_constraints": list(_SOVEREIGNTY_TRUST_AND_DATA_HANDLING_CONSTRAINTS),
        "sprint_143_does_not_build": list(_SPRINT143_DOES_NOT_BUILD),
        "simulation_exit_criteria": list(_SIMULATION_EXIT_CRITERIA),
        "risks_and_mitigations": _risk_payloads(),
        "sprint_144_recommended_next_step": _SPRINT144_RECOMMENDED_NEXT_STEP,
        "simulated_launch_step_universal_disclaimer": _SIMULATION_DOMAIN_DISCLAIMER,
        "sprint_143_m1_pilot_operational_launch_simulation_packet_proof": proof,
    }
    return _json_safe(out)


def render_active_source_activation_m1_pilot_operational_launch_simulation_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render the operator-facing markdown packet (deterministic; uses ``packet`` when provided)."""
    pkt = (
        packet
        if isinstance(packet, dict)
        else build_active_source_activation_m1_pilot_operational_launch_simulation_packet()
    )
    lines: list[str] = [
        "# NativeForge M1 Pilot Operational Launch Simulation Packet v1",
        "",
        "## 1. Purpose",
        "",
        "This packet is a deterministic, preview-only operator artifact that simulates the "
        "operational launch sequence for a future M1 pilot without launching anything. It rehearses "
        "launch-readiness drills, operator handoffs, evidence checks, support escalation paths, "
        "rollback rehearsal, monitoring expectations, and a final simulated no-go/go-style decision "
        "record only. It does not authorize runtime execution, customer onboarding, source "
        "activation, pilot launch, live customer data access, external calls, database migrations, "
        "production activation, or runnable launch plans.",
        "",
        "## 2. Why This Comes After Sprint 142",
        "",
        "Sprint 142 delivered the M1 pilot implementation pre-launch checklist packet: a structured "
        "readiness pass over evidence, human gates, deferrals, environments, rollback ownership, "
        "support readiness, and operator decision records—still without execution or activation. "
        "Sprint 143 is intentionally sequential: operators first complete that checklist lens, "
        "then use this operational launch simulation to rehearse how a hypothetical launch day "
        "would unfold across roles and controls. The simulation depends on Sprint 142 outputs as "
        "prerequisite planning evidence and does not replace Sprint 141 authorization review or "
        "Sprint 140 closeout references in the broader verification path.",
        "",
        "## 3. Operational Launch Simulation Objective",
        "",
        "Provide a single rehearsal surface that walks operators through a credible launch-day "
        "sequence while keeping all outcomes explicitly simulation-only. The objective is "
        "coordination literacy and evidence discipline, not go-live, onboarding, activation, or "
        "runtime work.",
        "",
        "## 4. Simulation Evidence Inputs",
        "",
    ]
    for row in pkt.get("simulation_evidence_inputs") or _evidence_input_payloads():
        if isinstance(row, dict):
            lab = row.get("evidence_label")
            ref = row.get("sprint_reference")
            note = row.get("expectation_note")
            if isinstance(lab, str) and isinstance(ref, str) and isinstance(note, str):
                lines.append(f"- **{lab}** ({ref}): {note}")
    lines.extend(["", "## 5. Simulated Launch Sequence", "", "Each step is simulation-only:", ""])
    for row in pkt.get("simulated_launch_sequence") or _simulation_sequence_payloads():
        if isinstance(row, dict):
            s = row.get("step")
            d = row.get("rehearsal_focus")
            if isinstance(s, str) and isinstance(d, str):
                lines.append(f"### {s}")
                lines.append("")
                lines.append(d)
                lines.append("")
    u = pkt.get("simulated_launch_step_universal_disclaimer") or _SIMULATION_DOMAIN_DISCLAIMER
    if isinstance(u, str) and u.strip():
        lines.extend(["**Universal simulation step disclaimer**:", "", u, ""])
    lines.extend(["", "## 6. Operator Handoff and Role Readiness", ""])
    for row in pkt.get("operator_handoff_and_role_readiness") or _handoff_payloads():
        if isinstance(row, dict):
            a = row.get("handoff_area")
            b = row.get("readiness_focus")
            if isinstance(a, str) and isinstance(b, str):
                lines.append(f"- **{a}**: {b}")
    lines.extend(["", "## 7. Support, Escalation, and Rollback Rehearsal", ""])
    for row in pkt.get("support_escalation_and_rollback_rehearsal") or _support_rollback_payloads():
        if isinstance(row, dict):
            t = row.get("topic")
            n = row.get("rehearsal_note")
            if isinstance(t, str) and isinstance(n, str):
                lines.append(f"- **{t}**: {n}")
    lines.extend(["", "## 8. Monitoring and Evidence Capture Expectations", ""])
    for item in pkt.get("monitoring_and_evidence_capture_expectations") or list(
        _MONITORING_AND_EVIDENCE_CAPTURE_EXPECTATIONS
    ):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 9. Human Decision Record Requirements", ""])
    for item in pkt.get("human_decision_record_requirements") or list(_HUMAN_DECISION_RECORD_REQUIREMENTS):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 10. Sovereignty, Trust, and Data Handling Constraints", ""])
    for item in pkt.get("sovereignty_trust_and_data_handling_constraints") or list(
        _SOVEREIGNTY_TRUST_AND_DATA_HANDLING_CONSTRAINTS
    ):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 11. What Sprint 143 Does Not Build", "", "Sprint 143 explicitly does not build:", ""])
    for item in pkt.get("sprint_143_does_not_build") or list(_SPRINT143_DOES_NOT_BUILD):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 12. Exit Criteria", ""])
    for c in pkt.get("simulation_exit_criteria") or list(_SIMULATION_EXIT_CRITERIA):
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
            "## 14. Sprint 144 Recommended Next Step",
            "",
            pkt.get("sprint_144_recommended_next_step") or _SPRINT144_RECOMMENDED_NEXT_STEP,
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
