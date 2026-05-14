"""Sprint 145: M1 lessons learned and post-pilot optimization packet (preview-only).

Deterministic operator artifact that defines lessons-learned capture domains, post-pilot review
report scaffolding, optimization backlog categories, improvement recommendation rules, and
controlled transition guidance after a hypothetical future M1 pilot—without running a pilot,
collecting live metrics, executing optimizations, or performing closeout. It follows Sprint 144
metrics and closeout reporting templates as prerequisite framing and remains preview-only: no
runtime execution, live customer data, onboarding, source activation, production activation,
external calls, database migrations, real metric collection, real pilot closeout, optimization
execution, or runnable implementation workflows.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = "nf_active_source_activation_m1_lessons_learned_post_pilot_optimization_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

_PREREQUISITE_SPRINT144_ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_pilot_metrics_closeout_reporting_packet_v1"
)
_VERIFICATION_SPRINT143_ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_pilot_operational_launch_simulation_packet_v1"
)
_VERIFICATION_SPRINT142_ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_pilot_implementation_pre_launch_checklist_packet_v1"
)
_VERIFICATION_SPRINT141_ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_controlled_build_authorization_review_packet_v1"
)

_LESSONS_DOMAIN_DISCLAIMER = (
    "This lessons-learned domain is template and narrative scaffolding only; it is not live "
    "lessons capture, is not post-pilot review execution, is not optimization execution, is not "
    "pilot launch, is not customer onboarding, is not source activation, is not production "
    "activation, and is not real metric collection unless a later sprint records explicit human "
    "operator authorization outside this packet."
)

_LESSONS_LEARNED_CAPTURE_MODEL: tuple[tuple[str, str], ...] = (
    (
        "Operator workflow friction",
        "Captures where operator checklists, handoffs, or rehearsal steps felt heavy or ambiguous "
        "relative to Sprint 143 simulation notes and Sprint 144 reporting templates—qualitative "
        "only. " + _LESSONS_DOMAIN_DISCLAIMER,
    ),
    (
        "Evidence quality gaps",
        "Captures missing pointers, weak attestations, or unclear artifact lineage against Sprint "
        "142 checklist and Sprint 144 evidence expectations—still no ingestion of live payloads. "
        + _LESSONS_DOMAIN_DISCLAIMER,
    ),
    (
        "Human gate effectiveness",
        "Captures whether human gates surfaced risk early enough in preview layers without "
        "claiming gate automation or approval from software. " + _LESSONS_DOMAIN_DISCLAIMER,
    ),
    (
        "Deferred item patterns",
        "Captures recurring deferral themes, ownership drift, or exception clusters carried "
        "forward from earlier sprints—planning visibility only. " + _LESSONS_DOMAIN_DISCLAIMER,
    ),
    (
        "Sovereignty and trust concerns",
        "Captures sovereignty, residency, consent, and trust-boundary unease expressed during "
        "reviews—no enforcement claims from this sprint. " + _LESSONS_DOMAIN_DISCLAIMER,
    ),
    (
        "Support and escalation findings",
        "Captures how support tiers and escalation paths from rehearsal would need tuning before "
        "any real pilot—no ticket system integration. " + _LESSONS_DOMAIN_DISCLAIMER,
    ),
    (
        "Rollback rehearsal findings",
        "Captures rollback tabletop gaps or unclear ownership without executing rollback. "
        + _LESSONS_DOMAIN_DISCLAIMER,
    ),
    (
        "Monitoring and evidence capture findings",
        "Captures monitoring rehearsal blind spots and evidence capture mechanics as narrative "
        "findings—no live signals. " + _LESSONS_DOMAIN_DISCLAIMER,
    ),
    (
        "Documentation clarity findings",
        "Captures where operator documents were ambiguous or misaligned with gates—appendix "
        "pointers only, no repository writes. " + _LESSONS_DOMAIN_DISCLAIMER,
    ),
    (
        "User or pilot stakeholder feedback placeholders",
        "Reserves labeled placeholder fields for future anonymized or synthetic stakeholder notes; "
        "this sprint does not collect or store stakeholder feedback. " + _LESSONS_DOMAIN_DISCLAIMER,
    ),
)

_POST_PILOT_REVIEW_STRUCTURE: tuple[tuple[str, str], ...] = (
    (
        "Executive summary",
        "One-page operator summary of lessons themes, optimization posture, and recommendation "
        "stance without asserting real pilot outcomes.",
    ),
    (
        "Evidence reviewed",
        "Pointer list across Sprint 144, Sprint 143, Sprint 142, Sprint 141, Sprint 140, and "
        "earlier artifacts with explicit unknowns where pointers are missing.",
    ),
    (
        "Metrics reviewed",
        "Qualitative recap of how Sprint 144 metric domains would be interpreted after a "
        "hypothetical pilot—still not real metric collection.",
    ),
    (
        "Gates completed",
        "Human-attested list of gates satisfied in planning or rehearsal layers only; silence "
        "cannot imply completion.",
    ),
    (
        "Gates blocked",
        "Human-attested list of blocked gates with owners and follow-ups; still preview-only.",
    ),
    (
        "Deferred items",
        "Table of deferrals tied to Sprint 142, Sprint 143, and Sprint 144 outputs without "
        "rewriting history.",
    ),
    (
        "Risk findings",
        "Narrative risk register excerpt referencing mitigations from this packet.",
    ),
    (
        "Sovereignty and trust findings",
        "Explicit subsection for sovereignty and trust observations without claiming production "
        "enforcement.",
    ),
    (
        "Operator findings",
        "Operator-authored observations on friction, clarity, and readiness—not auto-generated "
        "scores.",
    ),
    (
        "Recommended optimizations",
        "Human-prioritized optimization themes mapped to backlog categories; software does not "
        "execute changes.",
    ),
    (
        "Required human approvals before any next phase",
        "Checklist of named human operator approvals before runtime expansion, new pilots, "
        "activation, onboarding, migration, live metric capture, optimization execution, or "
        "runnable implementation workflows—this sprint does not grant them.",
    ),
)

_OPTIMIZATION_BACKLOG_FRAMEWORK: tuple[tuple[str, str], ...] = (
    (
        "Must fix before runtime expansion",
        "Hard prerequisites that block safe expansion; requires explicit human prioritization.",
    ),
    (
        "Should fix before next pilot",
        "Strongly advised fixes before another rehearsal or pilot wave; still recommendation-only.",
    ),
    (
        "Nice to have",
        "Quality-of-life improvements that must not be mistaken for launch blockers.",
    ),
    (
        "Requires tribal/customer validation",
        "Items that cannot be closed without tribal nation or customer attestation outside this "
        "software packet.",
    ),
    (
        "Requires security or sovereignty review",
        "Items needing dedicated security or sovereignty review tracks—not implied by template "
        "completion.",
    ),
    (
        "Requires pricing or support model review",
        "Commercial or support-structure dependencies that cannot be resolved in engineering-only "
        "artifacts.",
    ),
    (
        "Deferred with rationale",
        "Explicit deferrals with dated rationale and owners; deferral cannot imply closure.",
    ),
)

_IMPROVEMENT_RECOMMENDATION_RULES: tuple[str, ...] = (
    "Recommendations must be human-authored with named owners; software rendering cannot imply "
    "approval or execution.",
    "Each recommendation maps to exactly one optimization backlog category unless explicitly "
    "labeled as cross-cutting with human rationale.",
    "Recommendations must cite evidence pointers or unknown labels; silent assumptions are "
    "forbidden in final human-reviewed packets.",
    "No recommendation may authorize source activation, production activation, customer "
    "onboarding, database migration, real metric collection, real pilot closeout, optimization "
    "execution, or runnable implementation workflows.",
    "Binding sequencing and resourcing decisions remain outside Sprint 145; this sprint only "
    "defines recommendation templates.",
)

_REQUIRED_EVIDENCE_INPUTS: tuple[tuple[str, str, str], ...] = (
    (
        "Sprint 144 M1 pilot metrics and closeout reporting packet",
        "Sprint 144",
        "Mandatory prerequisite: treat "
        f"{_PREREQUISITE_SPRINT144_ARTIFACT_TYPE} as the metrics and closeout reporting template "
        "artifact before lessons learned and optimization backlog scaffolding is treated as "
        "grounded.",
    ),
    (
        "Sprint 143 M1 pilot operational launch simulation packet",
        "Sprint 143",
        "Must remain visible as operational launch simulation evidence "
        f"({_VERIFICATION_SPRINT143_ARTIFACT_TYPE}) in the verification path; Sprint 145 does not "
        "replace Sprint 143 outputs.",
    ),
    (
        "Sprint 142 M1 pilot implementation pre-launch checklist packet",
        "Sprint 142",
        "Checklist readiness continuity "
        f"({_VERIFICATION_SPRINT142_ARTIFACT_TYPE}) stays in the verification path for regression "
        "coverage alongside Sprint 144.",
    ),
    (
        "Sprint 141 controlled build authorization review packet",
        "Sprint 141",
        "Authorization review continuity "
        f"({_VERIFICATION_SPRINT141_ARTIFACT_TYPE}) remains in the verification path.",
    ),
    (
        "Sprint 140 demo-to-build transition closeout packet and prior sprint chain (131–139)",
        "Sprints 131–140",
        "Transition closeout and earlier sprint summaries referenced as read-only context; gaps "
        "must be labeled unknown.",
    ),
)

_DEFERRED_ITEM_AND_EXCEPTION_HANDLING: tuple[str, ...] = (
    "Deferred items carry owners, review dates, and explicit open or mitigated labels; deferral "
    "cannot be silently treated as closure.",
    "Exceptions require human narrative, impact class, and whether they block gates; no "
    "automatic exception clearing.",
    "Items deferred from Sprint 142, Sprint 143, or Sprint 144 must be traceable without "
    "rewriting history.",
    "New deferrals discovered during template review are planning inputs only—no ticket or "
    "workflow mutations from this sprint.",
)

_HUMAN_REVIEW_AND_APPROVAL_REQUIREMENTS: tuple[str, ...] = (
    "Human operator approval is required before any lessons-learned packet is treated as complete; "
    "software-only checkboxes cannot substitute for human operator approval.",
    "Human-authored sign-off fields must name approvers, dates, and scope boundaries before any "
    "next phase work is attempted.",
    "Optimization backlog entries must not be executed or scheduled by this builder; execution "
    "requires separate human-authorized sprints.",
    "Binding go-forward decisions remain outside Sprint 145; this packet only defines capture "
    "models, review structure, backlog categories, and recommendation templates.",
    "Separate human operator approvals remain required for pilot launch, onboarding, source "
    "activation, production activation, database migration, real metric collection, real pilot "
    "closeout, optimization execution, and any runnable implementation workflow.",
)

_SOVEREIGNTY_TRUST_AND_DATA_HANDLING_CONSTRAINTS: tuple[str, ...] = (
    "Customer owns its data; Sprint 145 artifacts must not embed or fetch live customer data.",
    "Sovereignty, residency, consent, and export expectations from prior packets must remain "
    "visible in templates without claiming production enforcement from this sprint.",
    "Trust-boundary language must not imply activation or optimization execution from template "
    "completion.",
    "Stakeholder feedback placeholders must remain empty or synthetic in preview artifacts—no "
    "live PII in this builder.",
    "Provenance for evidence pointers must remain traceable to named sprint artifacts or explicit "
    "unknown labels.",
    "Human judgment remains final for sovereignty, trust, and data-handling outcomes tied to "
    "post-pilot review.",
)

_SPRINT145_DOES_NOT_BUILD: tuple[str, ...] = (
    "no pilot launch",
    "no customer onboarding",
    "no customer data access",
    "no database migration",
    "no source activation",
    "no production activation",
    "no real metric collection",
    "no real pilot closeout",
    "no optimization execution",
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
    "Sprint 144 prerequisite is named with artifact type and treated as mandatory metrics and "
    "closeout reporting evidence before lessons learned and optimization templates are treated as "
    "grounded.",
    "Sprint 143 operational launch simulation and Sprint 142 checklist packets remain referenced "
    "in the verification path for regression continuity with Sprint 141 authorization review.",
    "All ten lessons-learned capture domains are enumerated with preview-only disclaimers.",
    "All eleven post-pilot review sections are enumerated with human approval and sovereignty "
    "cues.",
    "All seven optimization backlog categories are enumerated with scope boundaries.",
    "Improvement recommendation rules, deferral handling, sovereignty constraints, does-not-build "
    "scope, and exit criteria are listed without contradiction.",
    "Preview-only posture and zero actual counters are reflected in the structured packet and "
    "markdown render.",
    "Risks and mitigations are recorded before recommendation-only next-phase guidance.",
    "Recommended next phase decision text remains recommendation-only and does not authorize "
    "launch, activation, metric collection, closeout execution, or optimization execution.",
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "Lessons templates mistaken for executed post-mortems",
        "Label every domain as planning-only and forbid real pilot closeout keys from incrementing "
        "in this sprint.",
    ),
    (
        "Sprint 144 metrics packet skipped",
        "Bind prerequisite evidence to the Sprint 144 artifact type and forbid silent substitution.",
    ),
    (
        "Optimization backlog treated as execution plan",
        "Keep no_runnable_plan true and state explicitly that no runnable implementation workflow "
        "is built here.",
    ),
    (
        "Customer data pulled into optimization drafts",
        "Forbid customer data access in requirements and keep actual_customer_data_access at zero.",
    ),
    (
        "Human approvals implied by software rendering",
        "Require explicit human operator approval language and named approver fields in templates.",
    ),
    (
        "Next phase treated as authorization from Sprint 145",
        "Label the recommended next phase decision as recommendation-only and separate from any "
        "launch or activation authorization.",
    ),
)

_RECOMMENDED_NEXT_PHASE_DECISION = (
    "The recommended next phase decision is recommendation-only: operators should either (a) "
    "remain preview-only with additional planning artifacts, or (b) open a future sprint "
    "explicitly authorized for bounded optimization design, controlled transition execution, "
    "human-gated measurement or closeout work, and recorded human operator approvals outside "
    "Sprint 145. No pilot launch, source activation, production activation, customer onboarding, "
    "runtime execution, real metric collection, real pilot closeout, database migration, "
    "optimization execution, or runnable implementation workflow should begin from Sprint 145 "
    "output alone."
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _lessons_payloads() -> list[dict[str, str]]:
    return [{"capture_domain": d, "capture_focus": f} for d, f in _LESSONS_LEARNED_CAPTURE_MODEL]


def _review_structure_payloads() -> list[dict[str, str]]:
    return [{"section": s, "outline": o} for s, o in _POST_PILOT_REVIEW_STRUCTURE]


def _backlog_payloads() -> list[dict[str, str]]:
    return [{"category": c, "scope_note": n} for c, n in _OPTIMIZATION_BACKLOG_FRAMEWORK]


def _evidence_input_payloads() -> list[dict[str, str]]:
    return [
        {"evidence_label": lab, "sprint_reference": ref, "expectation_note": note}
        for lab, ref, note in _REQUIRED_EVIDENCE_INPUTS
    ]


def _risk_payloads() -> list[dict[str, str]]:
    return [{"risk": r, "mitigation": m} for r, m in _RISK_MITIGATIONS]


def build_active_source_activation_m1_lessons_learned_post_pilot_optimization_packet() -> (
    dict[str, Any]
):
    """Return the Sprint 145 M1 lessons learned and post-pilot optimization packet (deterministic)."""
    proof = {
        "sprint_145_m1_lessons_learned_post_pilot_optimization_packet_is_stateless": True,
        "sprint_145_m1_lessons_learned_post_pilot_optimization_packet_is_side_effect_free": True,
        "sprint_145_m1_lessons_learned_post_pilot_optimization_packet_is_preview_only": True,
        "sprint_145_m1_lessons_learned_post_pilot_optimization_packet_performs_no_runtime_work": (
            True
        ),
        "sprint_145_m1_lessons_learned_post_pilot_optimization_packet_emits_operator_templates_only": (
            True
        ),
    }
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 145,
        "packet_name": "NativeForge M1 Lessons Learned & Post-Pilot Optimization Packet",
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_define_lessons_learned_capture_model_preview_only": True,
        "may_define_post_pilot_review_structure_preview_only": True,
        "may_define_optimization_backlog_framework_preview_only": True,
        "may_define_improvement_recommendation_rules_preview_only": True,
        "may_define_controlled_transition_guidance_templates_only": True,
        "prerequisite_metrics_closeout_reporting_sprint": 144,
        "prerequisite_metrics_closeout_reporting_artifact_type": _PREREQUISITE_SPRINT144_ARTIFACT_TYPE,
        "verification_path_operational_launch_simulation_artifact_type": (
            _VERIFICATION_SPRINT143_ARTIFACT_TYPE
        ),
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
        "lessons_learned_capture_model": _lessons_payloads(),
        "post_pilot_review_structure": _review_structure_payloads(),
        "optimization_backlog_framework": _backlog_payloads(),
        "improvement_recommendation_rules": list(_IMPROVEMENT_RECOMMENDATION_RULES),
        "required_evidence_inputs": _evidence_input_payloads(),
        "deferred_item_and_exception_handling": list(_DEFERRED_ITEM_AND_EXCEPTION_HANDLING),
        "human_review_and_approval_requirements": list(_HUMAN_REVIEW_AND_APPROVAL_REQUIREMENTS),
        "sovereignty_trust_and_data_handling_constraints": list(
            _SOVEREIGNTY_TRUST_AND_DATA_HANDLING_CONSTRAINTS
        ),
        "sprint_145_does_not_build": list(_SPRINT145_DOES_NOT_BUILD),
        "packet_exit_criteria": list(_PACKET_EXIT_CRITERIA),
        "risks_and_mitigations": _risk_payloads(),
        "recommended_next_phase_decision": _RECOMMENDED_NEXT_PHASE_DECISION,
        "lessons_learned_domain_universal_disclaimer": _LESSONS_DOMAIN_DISCLAIMER,
        "sprint_145_m1_lessons_learned_post_pilot_optimization_packet_proof": proof,
    }
    return _json_safe(out)


def render_active_source_activation_m1_lessons_learned_post_pilot_optimization_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render the operator-facing markdown packet (deterministic; uses ``packet`` when provided)."""
    pkt = (
        packet
        if isinstance(packet, dict)
        else build_active_source_activation_m1_lessons_learned_post_pilot_optimization_packet()
    )
    lines: list[str] = [
        "# NativeForge M1 Lessons Learned & Post-Pilot Optimization Packet v1",
        "",
        "## 1. Purpose",
        "",
        "This packet is a deterministic, preview-only operator artifact that defines the "
        "lessons-learned capture model, post-pilot review structure, optimization backlog framework, "
        "improvement recommendation rules, deferral handling expectations, sovereignty and trust "
        "constraints, explicit non-scope, exit criteria, risks, mitigations, and recommendation-only "
        "next-phase guidance after a hypothetical future M1 pilot. It does not run a pilot, perform "
        "real pilot closeout, collect live metrics, onboard customers, activate sources, touch "
        "production systems, execute optimizations, or ship runnable implementation workflows.",
        "",
        "## 2. Why This Comes After Sprint 144",
        "",
        "Sprint 144 delivered the M1 pilot metrics and closeout reporting packet: preview-only "
        "templates for qualitative metric domains, closeout report sections, evidence capture "
        "language, and human review scaffolding—still without real metric collection or runnable "
        "closeout workflows. Sprint 145 is intentionally sequential: operators first anchor on that "
        "metrics and closeout reporting artifact as prerequisite framing, then use this packet to "
        "structure how lessons learned, post-pilot review, and optimization backlog thinking would "
        "be organized after such reporting templates exist—still without authorizing measurement, "
        "closeout execution, optimization execution, launch, onboarding, or activation. Sprint 145 "
        "does not replace Sprint 143 operational launch simulation outputs or Sprint 142 checklist "
        "evidence in the broader verification path.",
        "",
        "## 3. Lessons Learned Objective",
        "",
        "Provide a single planning surface that names capture domains as qualitative reflection "
        "scaffolding and ties them to evidence pointers, human approvals, and backlog categories. "
        "The objective is traceability and controlled transition discipline, not live retrospectives, "
        "not customer data access, and not automated optimization.",
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
    lines.extend(["", "## 5. Lessons Learned Capture Model", "", "Each domain is preview-only:", ""])
    for row in pkt.get("lessons_learned_capture_model") or _lessons_payloads():
        if isinstance(row, dict):
            d = row.get("capture_domain")
            f = row.get("capture_focus")
            if isinstance(d, str) and isinstance(f, str):
                lines.append(f"### {d}")
                lines.append("")
                lines.append(f)
                lines.append("")
    u = pkt.get("lessons_learned_domain_universal_disclaimer") or _LESSONS_DOMAIN_DISCLAIMER
    if isinstance(u, str) and u.strip():
        lines.extend(["**Universal lessons-learned disclaimer**:", "", u, ""])
    lines.extend(["", "## 6. Post-Pilot Review Structure", ""])
    for row in pkt.get("post_pilot_review_structure") or _review_structure_payloads():
        if isinstance(row, dict):
            s = row.get("section")
            o = row.get("outline")
            if isinstance(s, str) and isinstance(o, str):
                lines.append(f"- **{s}**: {o}")
    lines.extend(["", "## 7. Optimization Backlog Framework", ""])
    for row in pkt.get("optimization_backlog_framework") or _backlog_payloads():
        if isinstance(row, dict):
            c = row.get("category")
            n = row.get("scope_note")
            if isinstance(c, str) and isinstance(n, str):
                lines.append(f"- **{c}**: {n}")
    lines.extend(["", "## 8. Improvement Recommendation Rules", ""])
    for item in pkt.get("improvement_recommendation_rules") or list(_IMPROVEMENT_RECOMMENDATION_RULES):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 9. Deferred Item and Exception Handling", ""])
    for item in pkt.get("deferred_item_and_exception_handling") or list(
        _DEFERRED_ITEM_AND_EXCEPTION_HANDLING
    ):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 10. Human Review and Approval Requirements", ""])
    for item in pkt.get("human_review_and_approval_requirements") or list(
        _HUMAN_REVIEW_AND_APPROVAL_REQUIREMENTS
    ):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 11. Sovereignty, Trust, and Data Handling Constraints", ""])
    for item in pkt.get("sovereignty_trust_and_data_handling_constraints") or list(
        _SOVEREIGNTY_TRUST_AND_DATA_HANDLING_CONSTRAINTS
    ):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 12. What Sprint 145 Does Not Build", "", "Sprint 145 explicitly does not build:", ""])
    for item in pkt.get("sprint_145_does_not_build") or list(_SPRINT145_DOES_NOT_BUILD):
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
            "## 15. Recommended Next Phase Decision",
            "",
            pkt.get("recommended_next_phase_decision") or _RECOMMENDED_NEXT_PHASE_DECISION,
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
