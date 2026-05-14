"""Sprint 142: M1 pilot implementation pre-launch checklist packet (preview-only).

Deterministic operator checklist that follows Sprint 141 controlled build authorization review.
It prepares operators to decide whether a later sprint may authorize a tightly bounded
implementation slice—without runtime execution, customer data, pilot launch, source activation,
external calls, or production activation.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = "nf_active_source_activation_m1_pilot_implementation_pre_launch_checklist_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

_PREREQUISITE_SPRINT141_ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_controlled_build_authorization_review_packet_v1"
)

_CHECKLIST_DOMAIN_DISCLAIMER = (
    "This domain supports preview-only checklist readiness; it is not pilot launch, is not "
    "customer onboarding, is not source activation, is not production activation, and is not "
    "runtime authorization unless a later sprint records explicit human operator approval."
)

_M1_PRE_LAUNCH_CHECKLIST_PREVIEW_FOUNDATIONS: tuple[tuple[str, str], ...] = (
    (
        "Sprint 141 authorization review as gate",
        "Treats the Sprint 141 controlled build authorization review packet as mandatory "
        "prerequisite evidence before any M1 pilot implementation pre-launch checklist is treated as "
        "informed.",
    ),
    (
        "Sprint 140 demo-to-build closeout continuity",
        "Carries Sprint 140 transition closeout expectations forward as read-only checklist context "
        "without re-running closeout work.",
    ),
    (
        "Evidence package discipline",
        "Requires explicit evidence pointers and forbids substituting live customer data for "
        "checklist completeness.",
    ),
    (
        "Human gate explicitness",
        "Keeps mandatory human operator approval language visible beside every readiness domain that "
        "could imply go-live.",
    ),
    (
        "Deferred item visibility",
        "Ensures deferred items have disposition notes so deferrals cannot masquerade as ready.",
    ),
    (
        "Environment boundary clarity",
        "Separates demo, staging, and production language so environment claims cannot blur silently.",
    ),
    (
        "Rollback and escalation ownership",
        "Names rollback owners and escalation paths as checklist inputs, not executed runbooks.",
    ),
    (
        "Non-execution guardrails",
        "Repeats that this sprint emits checklist planning only and performs no implementation, "
        "activation, or launch work.",
    ),
)

_REQUIRED_EVIDENCE_INPUTS: tuple[tuple[str, str, str], ...] = (
    (
        "Sprint 141 controlled build authorization review packet",
        "Sprint 141",
        "Must be present as the prerequisite authorization review artifact "
        f"({_PREREQUISITE_SPRINT141_ARTIFACT_TYPE}) with validation posture notes before pre-launch "
        "checklist sign-off is treated as informed.",
    ),
    (
        "Sprint 140 demo-to-build transition closeout packet",
        "Sprint 140",
        "Must be referenced for transition closeout statuses, blockers, approvals, and deferrals as "
        "read-only evidence feeding checklist completeness.",
    ),
    (
        "Prior sprint evidence chain summary (131–139)",
        "Sprints 131–139",
        "Must be summarized or explicitly labeled unknown when gaps exist; checklist completeness "
        "cannot rely on unstated assumptions from earlier readiness packets.",
    ),
    (
        "Operator decision record template readiness",
        "Cross-cutting",
        "Human operator decision fields must be ready to record approve, defer, or remain "
        "preview-only outcomes without implying execution from this packet.",
    ),
    (
        "Environment boundary statements",
        "Cross-cutting",
        "Written statements naming allowed environments for any future bounded slice, defaulting "
        "to preview or non-production unless explicit later authorization states otherwise.",
    ),
)

_CHECKLIST_READINESS_DOMAINS: tuple[tuple[str, str], ...] = (
    (
        "Evidence package completeness",
        "Verify Sprint 141 outputs, Sprint 140 closeout references, and summarized 131–139 evidence "
        "are attached or explicitly gap-labeled. " + _CHECKLIST_DOMAIN_DISCLAIMER,
    ),
    (
        "Human gate readiness",
        "Confirm mandatory human operator approval steps are scheduled, owned, and documented before "
        "treating checklist items as satisfied. " + _CHECKLIST_DOMAIN_DISCLAIMER,
    ),
    (
        "Deferred item disposition",
        "Enumerate deferred items with owners, dates, and accept-or-block decisions recorded in "
        "planning artifacts only. " + _CHECKLIST_DOMAIN_DISCLAIMER,
    ),
    (
        "Sovereignty and trust review",
        "Align checklist sign-off with data ownership, consent, residency, and provenance "
        "expectations without accessing customer data in this sprint. " + _CHECKLIST_DOMAIN_DISCLAIMER,
    ),
    (
        "Environment boundary confirmation",
        "Document which environments may be referenced by future work and forbid silent production "
        "scope expansion from checklist language. " + _CHECKLIST_DOMAIN_DISCLAIMER,
    ),
    (
        "Rollback owner identification",
        "Name rollback owners and test expectations as checklist inputs; no rollback execution occurs "
        "here. " + _CHECKLIST_DOMAIN_DISCLAIMER,
    ),
    (
        "Support and escalation readiness",
        "Capture escalation paths and support ownership as planning readiness, not live ticket "
        "ingestion or customer onboarding. " + _CHECKLIST_DOMAIN_DISCLAIMER,
    ),
    (
        "Documentation handoff readiness",
        "List documentation artifacts required for a future bounded slice without generating "
        "runnable implementation plans in this sprint. " + _CHECKLIST_DOMAIN_DISCLAIMER,
    ),
    (
        "Operator decision record readiness",
        "Ensure fields exist for explicit human operator decisions and timestamps separate from any "
        "software flag pretending to be approval. " + _CHECKLIST_DOMAIN_DISCLAIMER,
    ),
)

_HUMAN_APPROVAL_REQUIREMENTS: tuple[str, ...] = (
    "Human operator approval is required before any M1 pilot implementation pre-launch checklist is "
    "treated as complete for planning purposes.",
    "Human operator approval must be recorded in a human-authored decision artifact; software-only "
    "checkboxes cannot substitute for human judgment.",
    "Human operator approval meetings must restate that this checklist is not pilot launch, not "
    "customer onboarding, not source activation, not production activation, and not runtime "
    "execution.",
    "Separate human operator approvals are required for preview checklist completion versus any "
    "future bounded implementation engineering sprint.",
    "Any deferral that could affect customers or sovereign data requires explicit human operator "
    "acknowledgment in the decision record.",
    "Human operator approval cannot be inferred from Sprint 142 output alone; later sprints must "
    "carry explicit written authorization if engineering proceeds.",
)

_DEFERRED_ITEM_HANDLING_EXPECTATIONS: tuple[str, ...] = (
    "Deferred items must remain visible in the structured packet and markdown with owners and "
    "follow-up dates.",
    "Deferrals must not silently clear checklist domains; disposition must be accept-with-visibility "
    "or remain blocked.",
    "Deferred engineering for ingestion, extraction, workflows, or activation remains out of scope "
    "for Sprint 142 and must be referenced only as planning pointers.",
    "Customer-specific deferrals must avoid customer data access in this preview-only artifact.",
    "Deferred runtime or activation work requires a distinct later sprint authorization packet.",
)

_SOVEREIGNTY_TRUST_AND_DATA_HANDLING_REQUIREMENTS: tuple[str, ...] = (
    "Customer owns its data; Sprint 142 artifacts must not embed or fetch live customer data.",
    "No model training on customer data without explicit written consent recorded outside this "
    "packet.",
    "Data residency and export expectations from prior sovereignty packets must be visible during "
    "checklist review without claiming production enforcement from this sprint.",
    "Provenance for evidence pointers must remain traceable to named sprint artifacts or explicit "
    "unknown labels.",
    "Trust-boundary language must not imply production activation or source activation from "
    "checklist completion.",
    "Human judgment remains final for sovereignty, trust, and data-handling outcomes tied to the "
    "checklist.",
    "Operator-facing notes must avoid customer-identifying details in this preview-only builder.",
)

_SPRINT142_DOES_NOT_BUILD: tuple[str, ...] = (
    "no pilot launch",
    "no customer onboarding",
    "no customer data access",
    "no database migration",
    "no source activation",
    "no production activation",
    "no runtime execution",
    "no controlled build execution",
    "no live customer data",
    "no external service call",
    "no AI generation",
    "no runnable implementation plan",
    "no API route",
    "no frontend UI",
    "no workflow activation",
    "no form submission",
    "no implicit authorization from this packet",
)

_PRE_LAUNCH_CHECKLIST_EXIT_CRITERIA: tuple[str, ...] = (
    "Sprint 141 prerequisite is named with artifact type and treated as mandatory authorization "
    "review evidence.",
    "Sprint 140 demo-to-build closeout is referenced for continuity in the verification path.",
    "All nine checklist readiness domains are enumerated with preview-only disclaimers.",
    "Human approval requirements, deferred item handling expectations, sovereignty and trust "
    "requirements, and does-not-build scope are listed without contradiction.",
    "Preview-only posture and zero actual counters are reflected in the structured packet and "
    "markdown render.",
    "Risks and mitigations are recorded before Sprint 143 recommendation-only guidance.",
    "Sprint 143 guidance remains recommendation-only and does not authorize engineering execution.",
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "Checklist completion mistaken for pilot launch approval",
        "Title artifacts as preview-only and repeat not pilot launch, not customer onboarding, not "
        "source activation, and not production activation beside readiness language.",
    ),
    (
        "Sprint 141 outputs skipped",
        "Bind prerequisite evidence to the Sprint 141 artifact type and block silent substitution.",
    ),
    (
        "Environment boundaries blur into production",
        "Require explicit environment statements and forbid production claims without later written "
        "authorization.",
    ),
    (
        "Rollback owners unnamed",
        "Keep rollback owner identification as a checklist domain with explicit owner fields.",
    ),
    (
        "Deferred items disappear after review",
        "Mirror deferred handling expectations in structured data and markdown with owner dates.",
    ),
    (
        "Customer data enters checklist artifacts",
        "Forbid customer data access in requirements and keep actual_customer_data_access at zero.",
    ),
    (
        "Software flags replace human operator approval",
        "Require human-authored decision records and forbid software-only approval language.",
    ),
    (
        "Sprint 143 treated as execution authorization",
        "Label Sprint 143 as recommendation-only and separate from any implementation authorization.",
    ),
)

_SPRINT143_RECOMMENDED_NEXT_STEP = (
    "Sprint 143 is recommendation-only: operators should either (a) keep work preview-only with "
    "additional planning artifacts, or (b) open a future sprint explicitly authorized for a tightly "
    "bounded implementation slice with written scope, rollback owners, environment boundaries, and "
    "human operator approvals recorded outside Sprint 142. No engineering execution, pilot launch, "
    "source activation, or production activation should begin from Sprint 142 output alone."
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _foundation_payloads() -> list[dict[str, str]]:
    return [{"foundation_area": a, "operator_focus": b} for a, b in _M1_PRE_LAUNCH_CHECKLIST_PREVIEW_FOUNDATIONS]


def _evidence_input_payloads() -> list[dict[str, str]]:
    return [
        {"evidence_label": lab, "sprint_reference": ref, "expectation_note": note}
        for lab, ref, note in _REQUIRED_EVIDENCE_INPUTS
    ]


def _domain_payloads() -> list[dict[str, str]]:
    return [{"domain": d, "readiness_focus": f} for d, f in _CHECKLIST_READINESS_DOMAINS]


def _risk_payloads() -> list[dict[str, str]]:
    return [{"risk": r, "mitigation": m} for r, m in _RISK_MITIGATIONS]


def build_active_source_activation_m1_pilot_implementation_pre_launch_checklist_packet() -> (
    dict[str, Any]
):
    """Return the Sprint 142 M1 pilot implementation pre-launch checklist packet (deterministic)."""
    proof = {
        "sprint_142_m1_pilot_implementation_pre_launch_checklist_packet_is_stateless": True,
        "sprint_142_m1_pilot_implementation_pre_launch_checklist_packet_is_side_effect_free": True,
        "sprint_142_m1_pilot_implementation_pre_launch_checklist_packet_is_preview_only": True,
        "sprint_142_m1_pilot_implementation_pre_launch_checklist_packet_performs_no_runtime_work": True,
        "sprint_142_m1_pilot_implementation_pre_launch_checklist_packet_emits_operator_planning_only": True,
    }
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 142,
        "packet_name": "NativeForge M1 Pilot Implementation Pre-Launch Checklist Packet",
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_define_pre_launch_checklist_readiness": True,
        "may_define_required_evidence_inputs": True,
        "may_define_checklist_readiness_domains": True,
        "may_define_human_approval_requirements": True,
        "may_define_deferred_item_handling_expectations": True,
        "may_define_sovereignty_trust_and_data_handling_requirements": True,
        "may_prepare_bounded_implementation_slice_planning_only": True,
        "prerequisite_authorization_review_sprint": 141,
        "prerequisite_authorization_review_artifact_type": _PREREQUISITE_SPRINT141_ARTIFACT_TYPE,
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
        "m1_pilot_implementation_pre_launch_checklist_preview_foundations": _foundation_payloads(),
        "required_evidence_inputs": _evidence_input_payloads(),
        "checklist_readiness_domains": _domain_payloads(),
        "human_approval_requirements": list(_HUMAN_APPROVAL_REQUIREMENTS),
        "deferred_item_handling_expectations": list(_DEFERRED_ITEM_HANDLING_EXPECTATIONS),
        "sovereignty_trust_and_data_handling_requirements": list(
            _SOVEREIGNTY_TRUST_AND_DATA_HANDLING_REQUIREMENTS
        ),
        "sprint_142_does_not_build": list(_SPRINT142_DOES_NOT_BUILD),
        "pre_launch_checklist_exit_criteria": list(_PRE_LAUNCH_CHECKLIST_EXIT_CRITERIA),
        "risks_and_mitigations": _risk_payloads(),
        "sprint_143_recommended_next_step": _SPRINT143_RECOMMENDED_NEXT_STEP,
        "checklist_readiness_domain_universal_disclaimer": _CHECKLIST_DOMAIN_DISCLAIMER,
        "sprint_142_m1_pilot_implementation_pre_launch_checklist_packet_proof": proof,
    }
    return _json_safe(out)


def render_active_source_activation_m1_pilot_implementation_pre_launch_checklist_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render the operator-facing markdown packet (deterministic; uses ``packet`` when provided)."""
    pkt = (
        packet
        if isinstance(packet, dict)
        else build_active_source_activation_m1_pilot_implementation_pre_launch_checklist_packet()
    )
    lines: list[str] = [
        "# NativeForge M1 Pilot Implementation Pre-Launch Checklist Packet v1",
        "",
        "## 1. Purpose",
        "",
        "This packet is a deterministic, preview-only operator artifact that records the final "
        "pre-launch checklist for any future M1 pilot implementation path. It follows Sprint 141 "
        "controlled build authorization review and prepares operators to decide whether a later "
        "sprint may authorize a tightly bounded implementation slice. It does not perform runtime "
        "authorization, customer onboarding, source activation, pilot launch, live customer data "
        "access, external calls, database migrations, or runnable implementation planning execution.",
        "",
        "## 2. Why This Comes After Sprint 141",
        "",
        "Sprint 141 delivered the controlled build authorization review packet, consolidating prior "
        "sprint evidence (131–140), validation rules, human gate expectations, deferred items, and "
        "sovereignty posture for authorization readiness. Sprint 142 is intentionally sequential: "
        "operators first complete the authorization review lens, then use this pre-launch checklist "
        "to confirm evidence packaging, human gates, deferrals, trust boundaries, environments, "
        "rollback ownership, support readiness, documentation handoff, and operator decision records "
        "before any later sprint considers bounded implementation—still without execution, activation, "
        "or launch.",
        "",
        "## 3. Pre-Launch Objective",
        "",
        "Provide a single checklist surface that states whether planning inputs are complete enough "
        "for operators to judge readiness for a potential future bounded implementation slice. The "
        "objective is disciplined checklist completion with explicit human operator approval "
        "requirements, not engineering execution or go-live.",
        "",
        "Pre-launch checklist preview foundations:",
        "",
    ]
    for row in pkt.get("m1_pilot_implementation_pre_launch_checklist_preview_foundations") or (
        _foundation_payloads()
    ):
        if isinstance(row, dict):
            a = row.get("foundation_area")
            b = row.get("operator_focus")
            if isinstance(a, str) and isinstance(b, str):
                lines.append(f"- **{a}**: {b}")
    lines.extend(["", "## 4. Required Evidence Inputs", ""])
    for row in pkt.get("required_evidence_inputs") or _evidence_input_payloads():
        if isinstance(row, dict):
            lab = row.get("evidence_label")
            ref = row.get("sprint_reference")
            note = row.get("expectation_note")
            if isinstance(lab, str) and isinstance(ref, str) and isinstance(note, str):
                lines.append(f"- **{lab}** ({ref}): {note}")
    lines.extend(
        [
            "",
            "## 5. Checklist Readiness Domains",
            "",
            "Each domain includes explicit preview-only disclaimers: not pilot launch, not customer "
            "onboarding, not source activation, not production activation, and not runtime "
            "authorization unless a later sprint records explicit human operator approval:",
            "",
        ]
    )
    for row in pkt.get("checklist_readiness_domains") or _domain_payloads():
        if isinstance(row, dict):
            d = row.get("domain")
            f = row.get("readiness_focus")
            if isinstance(d, str) and isinstance(f, str):
                lines.append(f"### {d}")
                lines.append("")
                lines.append(f)
                lines.append("")
    u = pkt.get("checklist_readiness_domain_universal_disclaimer") or _CHECKLIST_DOMAIN_DISCLAIMER
    if isinstance(u, str) and u.strip():
        lines.extend(["**Universal checklist domain disclaimer**:", "", u, ""])
    lines.extend(["", "## 6. Human Approval Requirements", ""])
    for item in pkt.get("human_approval_requirements") or list(_HUMAN_APPROVAL_REQUIREMENTS):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 7. Deferred Item Handling", ""])
    for item in pkt.get("deferred_item_handling_expectations") or list(_DEFERRED_ITEM_HANDLING_EXPECTATIONS):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 8. Sovereignty, Trust, and Data Handling Requirements", ""])
    for item in pkt.get("sovereignty_trust_and_data_handling_requirements") or list(
        _SOVEREIGNTY_TRUST_AND_DATA_HANDLING_REQUIREMENTS
    ):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 9. What Sprint 142 Does Not Build", "", "Sprint 142 explicitly does not build:", ""])
    for item in pkt.get("sprint_142_does_not_build") or list(_SPRINT142_DOES_NOT_BUILD):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 10. Exit Criteria", ""])
    for c in pkt.get("pre_launch_checklist_exit_criteria") or list(_PRE_LAUNCH_CHECKLIST_EXIT_CRITERIA):
        if isinstance(c, str) and c.strip():
            lines.append(f"- {c}")
    lines.extend(["", "## 11. Risks and Mitigations", ""])
    for row in pkt.get("risks_and_mitigations") or _risk_payloads():
        if isinstance(row, dict):
            r = row.get("risk")
            m = row.get("mitigation")
            if isinstance(r, str) and isinstance(m, str):
                lines.append(f"- **Risk**: {r} — **Mitigation**: {m}")
    lines.extend(
        [
            "",
            "## 12. Sprint 143 Recommended Next Step",
            "",
            pkt.get("sprint_143_recommended_next_step") or _SPRINT143_RECOMMENDED_NEXT_STEP,
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
