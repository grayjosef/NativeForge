"""Sprint 139: M1 pilot operations and support controlled build readiness packet (preview-only).

Deterministic operator packet that defines pilot operations readiness fields, support ownership,
support intake prerequisites, success evidence, escalation rules, sovereignty and security guardrails,
and acceptance criteria—without pilot account creation, support workflow activation, customer record
creation, external calls, customer data access, or runtime activation.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_pilot_operations_support_controlled_build_readiness_packet_v1"
)
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

_STATUS_DISCLAIMER = (
    "This status is not pilot onboarding, is not support workflow activation, and is not customer record "
    "creation."
)

_M1_PILOT_OPERATIONS_SUPPORT_READINESS_FOUNDATIONS: tuple[tuple[str, str], ...] = (
    (
        "Pilot operations scope readiness",
        "Names pilot kickoff, in-scope support touchpoints, and operator boundaries without activating "
        "workflows.",
    ),
    (
        "Support intake readiness",
        "Defines intake channels, required fields, and demo-safe fixtures without intake execution.",
    ),
    (
        "Operator handoff readiness",
        "Captures who receives escalations and how context transfers without runtime handoff automation.",
    ),
    (
        "Buyer follow-up readiness",
        "Plans buyer-visible follow-ups and commitments without implying customer onboarding.",
    ),
    (
        "Success evidence readiness",
        "Lists observable evidence operators will collect later without inventing outcomes.",
    ),
    (
        "Escalation path readiness",
        "Documents escalation owners, triggers, and routing previews without activating escalation systems.",
    ),
    (
        "Support boundary readiness",
        "States what M1 support can and cannot promise so operators avoid overpromising capability.",
    ),
    (
        "Training/documentation readiness",
        "Covers training artifacts and operator documentation prerequisites without delivering live training.",
    ),
    (
        "Customer feedback readiness",
        "Plans feedback capture that preserves sovereignty and trust without customer record creation.",
    ),
    (
        "Pilot risk tracking readiness",
        "Surfaces pilot risks, owners, and review cadence without mutating production risk registers.",
    ),
    (
        "Data sovereignty and security readiness",
        "Aligns pilot operations planning with sovereignty, residency, consent, and security prerequisites.",
    ),
    (
        "Pilot closeout readiness",
        "Defines closeout evidence, provenance, and review history expectations without closing a pilot.",
    ),
)

_PILOT_OPERATIONS_READINESS_FIELD_GROUP_ROWS: tuple[tuple[str, str, tuple[str, str]], ...] = (
    (
        "Pilot operations readiness item identity",
        "Stable id, title, and version for each readiness row across operator artifacts.",
        (
            "Identity strings remain identical across repeated packet generations.",
            "Each readiness item exposes a single primary identity key for traceability.",
        ),
    ),
    (
        "Pilot operations area",
        "Maps the readiness item to pilot kickoff, intake, triage, escalation, handoff, or closeout slices.",
        (
            "Every row lists exactly one primary pilot operations area before readiness is treated as informed.",
            "Pilot operations area labels stay preview-only and forbid silent promotion to runtime execution.",
        ),
    ),
    (
        "Support workflow area",
        "Names the support slice covered such as intake, triage, escalation, or feedback without activation.",
        (
            "Support workflow areas are enumerated or explicitly marked undecided before planning improves.",
            "Support workflow language disclaims support workflow activation and customer record creation.",
        ),
    ),
    (
        "Human owner",
        "Identifies the accountable human or marks owner-needed without creating accounts or records.",
        (
            "Owners are named or flagged as needed before support intake readiness is treated as informed.",
            "Owner fields never imply pilot account creation or customer record creation from this sprint.",
        ),
    ),
    (
        "Buyer-facing or operator-facing flag",
        "Clarifies whether language, evidence, or follow-up is buyer-visible versus operator-only.",
        (
            "Each row states buyer-facing, operator-facing, or mixed with rationale before triage planning.",
            "Buyer-facing language disclaims customer onboarding and customer record creation.",
        ),
    ),
    (
        "Support intake prerequisite",
        "Lists required information, approvals, and demo-safe fixtures before intake build planning.",
        (
            "Intake prerequisites are visible or explicitly marked as gaps before intake readiness improves.",
            "Intake language disclaims support workflow activation and runtime intake execution.",
        ),
    ),
    (
        "Escalation prerequisite",
        "Captures triggers, owners, and buyer versus operator routing expectations for escalations only.",
        (
            "Escalation prerequisites appear before escalation path readiness is treated as informed.",
            "Escalation language disclaims workflow activation and customer record creation.",
        ),
    ),
    (
        "Success evidence requirement",
        "Defines observable evidence operators will require without fabricating success metrics.",
        (
            "Evidence requirements name what will be observed or marked unknown before closeout planning.",
            "Evidence language disclaims invented outcomes and customer data access in this sprint.",
        ),
    ),
    (
        "Feedback capture requirement",
        "States how feedback is captured with sovereignty and trust boundaries without live capture.",
        (
            "Feedback requirements appear before customer feedback readiness is treated as informed.",
            "Feedback language disclaims customer onboarding and customer record creation.",
        ),
    ),
    (
        "Training or handoff requirement",
        "Documents training, runbooks, and handoff checkpoints without scheduling live training.",
        (
            "Training or handoff requirements are visible before operator handoff readiness improves.",
            "Training language disclaims pilot account creation and production workflow change.",
        ),
    ),
    (
        "Data handling prerequisite",
        "Covers demo-safe data, minimization, and handling expectations without accessing customer data.",
        (
            "Data handling prerequisites are explicit before data sovereignty readiness improves.",
            "Data handling language disclaims customer data access and live ingestion.",
        ),
    ),
    (
        "Sovereignty prerequisite",
        "Records residency, export, consent, and channel expectations as planning-only controls.",
        (
            "Sovereignty prerequisites are visible before pilot operations readiness closes.",
            "Sovereignty language disclaims customer record creation and external calls.",
        ),
    ),
    (
        "Security prerequisite",
        "Captures least privilege, secrets handling, and review expectations without runtime changes.",
        (
            "Security prerequisites are visible before pilot blocker status clears.",
            "Security language disclaims API routes, production workflow change, and runtime activation.",
        ),
    ),
    (
        "Pilot blocker status",
        "Signals ownership, intake, escalation, evidence, feedback, sovereignty, or security gaps.",
        (
            "Blocker status stays preview-only and does not activate support workflows or create records.",
            "Blocker notes repeat not pilot onboarding, not support workflow activation, not customer record "
            "creation.",
        ),
    ),
    (
        "Acceptance criteria",
        "Field-level pass or fail checks operators use before assigning a pilot operations readiness status.",
        (
            "Each field group carries at least two criteria tied to evidence or explicit gap labels.",
            "Criteria reinforce preview-only posture and non-commitment language.",
        ),
    ),
    (
        "Risk note",
        "Captures residual ambiguity, ownership confusion, or dependency risk for operator attention.",
        (
            "Risk notes pair with mitigations listed in the risks and mitigations section when material.",
            "Risk notes never assert that risks were cleared without documented human review.",
        ),
    ),
    (
        "Non-production disclaimer",
        (
            "Restates preview-only posture and lack of pilot onboarding, support workflow activation, customer "
            "record creation, and live calls."
        ),
        (
            "Disclaimers repeat not pilot onboarding, not support workflow activation, and not customer record "
            "creation.",
            "Disclaimers appear wherever status language could be misread as go-live pilot support work.",
        ),
    ),
    (
        "Next sprint recommendation",
        "Points operators to Sprint 140 demo-to-build transition closeout in preview-only language.",
        (
            "Recommendations name Sprint 140 as the M1 Pilot Demo-to-Build Transition Closeout Packet.",
            "Recommendations forbid silent expansion into runtime work without explicit authorization.",
        ),
    ),
)

_PILOT_OPERATIONS_READINESS_STATUS_ROWS: tuple[tuple[str, str], ...] = (
    (
        "Not assessed",
        "Readiness row exists but lacks minimum field coverage; must be assessed before planning improves. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Ready for controlled build planning",
        "Field groups are sufficient for operator-controlled pilot operations and support build planning without "
        "execution promises. " + _STATUS_DISCLAIMER,
    ),
    (
        "Needs support owner",
        "Human owner is missing or unclear for a support workflow area and must be assigned in planning. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Needs intake review",
        "Support intake prerequisites, channels, or required fields need operator review. " + _STATUS_DISCLAIMER,
    ),
    (
        "Needs escalation review",
        "Escalation prerequisites, triggers, or routing assumptions need operator review. " + _STATUS_DISCLAIMER,
    ),
    (
        "Needs success evidence review",
        "Success evidence requirements are vague, unobservable, or need operator review. " + _STATUS_DISCLAIMER,
    ),
    (
        "Blocked before pilot operations build",
        "Unresolved ownership, intake, escalation, evidence, feedback, training, sovereignty, or security issues "
        "block readiness in planning. " + _STATUS_DISCLAIMER,
    ),
    (
        "Deferred beyond M1",
        "Support area or readiness row is intentionally deferred past M1 while remaining visible in the "
        "inventory. " + _STATUS_DISCLAIMER,
    ),
)

_PREVIEW_ONLY_PILOT_OPERATIONS_RULES: tuple[str, ...] = (
    "Require seeded or demo-safe records only; never import production customer extracts into pilot operations "
    "readiness rows.",
    "Do not access real customer data while building or reviewing this pilot operations and support readiness "
    "packet.",
    "Do not create pilot accounts, activate support workflows, or create customer records from this sprint "
    "packet.",
    "Do not place external API calls, scrapes, live ingestions, or live AI generations while using this packet.",
    "Do not submit forms, invoke AI generation, or perform runtime writes while using this packet.",
    "Do not activate sources, perform live ingestion, or change production workflows while using this packet.",
    "Keep human judgment, sovereignty boundaries, provenance visibility, and non-execution disclaimers explicit.",
)

_PILOT_OPERATIONS_READINESS_BY_SUPPORT_AREA: tuple[tuple[str, str], ...] = (
    (
        "pilot kickoff planning",
        "Readiness aligns kickoff agendas, scope language, and demo-safe fixtures without pilot account creation.",
    ),
    (
        "buyer follow-up capture",
        "Readiness plans follow-up prompts and commitments without implying customer onboarding.",
    ),
    (
        "support intake",
        "Readiness defines intake fields and owners without support workflow activation.",
    ),
    (
        "issue triage",
        "Readiness documents triage categories and human gates without production ticketing changes.",
    ),
    (
        "escalation paths",
        "Readiness maps operator-owned versus buyer-owned escalations without activating routing systems.",
    ),
    (
        "operator handoff",
        "Readiness captures handoff checklists and context packets without automated runtime handoff.",
    ),
    (
        "training and documentation",
        "Readiness lists training artifacts and doc gaps without scheduling live customer training.",
    ),
    (
        "success evidence capture",
        "Readiness ties evidence to observable signals without inventing pilot outcomes.",
    ),
    (
        "customer feedback loops",
        "Readiness defines feedback capture that preserves sovereignty without customer record creation.",
    ),
    (
        "pilot risk tracking",
        "Readiness inventories risks and owners without mutating production risk systems.",
    ),
    (
        "pilot closeout",
        "Readiness defines closeout evidence and provenance expectations without closing a live pilot.",
    ),
)

_SUPPORT_WORKFLOW_PREREQUISITE_RULES: tuple[str, ...] = (
    "Every support workflow area must have a human owner or an explicit owner-needed status.",
    "Support intake must be defined before support activation planning proceeds.",
    "Escalation paths must be defined before pilot operations readiness closes.",
    "Success evidence must be defined before pilot closeout planning proceeds.",
    "Customer feedback capture must preserve sovereignty and trust boundaries.",
    "Unresolved support ownership blocks pilot operations readiness until addressed in planning.",
)

_SUCCESS_EVIDENCE_FEEDBACK_AND_ESCALATION_RULES: tuple[str, ...] = (
    "Success evidence must be observable and not invented.",
    "Buyer feedback must be captured without implying customer onboarding.",
    "Escalations must distinguish operator-owned and buyer-owned issues.",
    "Support boundaries must prevent overpromising M1 capability.",
    "Pilot closeout readiness must preserve source provenance and review history.",
    "No support workflow is activated in this sprint.",
    "No runtime activation occurs in this sprint.",
)

_SOVEREIGNTY_AND_TRUST_REQUIREMENTS: tuple[str, ...] = (
    "Customer owns its data.",
    "No customer data is required for this planning sprint.",
    "No customer data leaves the product during seeded demos.",
    "No model training on customer data without explicit written consent.",
    "Human judgment remains final.",
    "Source provenance remains visible.",
    "Pilot operations readiness must not overpromise implementation readiness.",
)

_SPRINT139_DOES_NOT_BUILD: tuple[str, ...] = (
    "no pilot account creation",
    "no support workflow activation",
    "no customer record creation",
    "no customer onboarding",
    "no customer data access",
    "no AI generation",
    "no source activation",
    "no live ingestion",
    "no form submission",
    "no workflow activation",
    "no real application submission",
    "no production readiness certification",
    "no external service call",
    "no database migration",
    "no frontend UI",
    "no API route",
    "no production workflow change",
)

_M1_PILOT_OPERATIONS_SUPPORT_READINESS_EXIT_CRITERIA: tuple[str, ...] = (
    "All eighteen pilot operations readiness field groups are documented with purposes and acceptance criteria.",
    "All eight pilot operations readiness statuses include explicit not pilot onboarding, not support workflow "
    "activation, and not customer record creation disclaimers.",
    "All twelve M1 pilot operations and support readiness foundations include operator focus statements without "
    "runtime execution.",
    "All eleven pilot operations readiness by support area rows include preview mapping language and caveat "
    "expectations.",
    "Support workflow prerequisite rules, success evidence and escalation rules, sovereignty and trust "
    "requirements, and preview-only rules are listed.",
    "Risks and mitigations are recorded with operator discipline expectations for controlled build planning.",
    "Sprint 140 recommendation is captured as the next preview-only demo-to-build transition closeout step.",
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "Pilot onboarding is implied by planning language",
        "Pair pilot language with explicit not pilot onboarding statements until a later authorized sprint.",
    ),
    (
        "Support workflow activation is implied too early",
        "Repeat not support workflow activation beside every readiness status and in non-production disclaimers.",
    ),
    (
        "Customer record creation is implied too early",
        "Restate not customer record creation wherever intake, feedback, or follow-up language appears.",
    ),
    (
        "Support ownership is missing",
        "Block readiness improvements until every support workflow area names an owner or owner-needed status.",
    ),
    (
        "Escalation paths are under-scoped",
        "Require operator-owned versus buyer-owned routing before escalation readiness is treated as informed.",
    ),
    (
        "Success evidence is vague or invented",
        "Bind evidence to observable signals and explicit unknowns before success evidence review clears.",
    ),
    (
        "Customer feedback capture implies customer data handling too early",
        "Sequence sovereignty prerequisites and demo-safe handling rules before buyer-visible feedback language.",
    ),
    (
        "Support boundaries overpromise M1 capability",
        "Tie support promises to documented boundaries and deferrals instead of marketing language.",
    ),
    (
        "Pilot operations readiness becomes theater instead of control",
        "Require traceable identities, explicit blockers, risk notes, and acceptance criteria alongside every "
        "status.",
    ),
)

_SPRINT140_RECOMMENDED_NEXT_STEP = (
    "Sprint 140 should deliver the M1 Pilot Demo-to-Build Transition Closeout Packet, still preview-only unless "
    "the operator explicitly authorizes runtime work."
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _field_group_payloads() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, (name, purpose, criteria) in enumerate(_PILOT_OPERATIONS_READINESS_FIELD_GROUP_ROWS, start=1):
        out.append(
            {
                "priority": i,
                "name": name,
                "purpose": purpose,
                "acceptance_criteria": list(criteria),
            }
        )
    return out


def _foundation_payloads() -> list[dict[str, str]]:
    return [
        {"foundation_area": a, "operator_focus": b} for a, b in _M1_PILOT_OPERATIONS_SUPPORT_READINESS_FOUNDATIONS
    ]


def _status_payloads() -> list[dict[str, str]]:
    return [{"status": s, "definition": d} for s, d in _PILOT_OPERATIONS_READINESS_STATUS_ROWS]


def _support_area_payloads() -> list[dict[str, str]]:
    return [
        {"support_area": a, "pilot_operations_support_readiness_preview": b}
        for a, b in _PILOT_OPERATIONS_READINESS_BY_SUPPORT_AREA
    ]


def _risk_payloads() -> list[dict[str, str]]:
    return [{"risk": r, "mitigation": m} for r, m in _RISK_MITIGATIONS]


def build_active_source_activation_m1_pilot_operations_support_controlled_build_readiness_packet() -> (
    dict[str, Any]
):
    """Return the Sprint 139 M1 pilot operations and support controlled build readiness packet (deterministic)."""
    proof = {
        "sprint_139_m1_pilot_operations_support_controlled_build_readiness_packet_is_stateless": True,
        "sprint_139_m1_pilot_operations_support_controlled_build_readiness_packet_is_side_effect_free": True,
        "sprint_139_m1_pilot_operations_support_controlled_build_readiness_packet_is_preview_only": True,
        "sprint_139_m1_pilot_operations_support_controlled_build_readiness_packet_performs_no_runtime_work": True,
        "sprint_139_m1_pilot_operations_support_controlled_build_readiness_packet_emits_operator_planning_only": (
            True
        ),
    }
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 139,
        "packet_name": "NativeForge M1 Pilot Operations and Support Controlled Build Readiness Packet",
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_define_pilot_operations_readiness": True,
        "may_define_support_workflow_prerequisites": True,
        "may_define_success_evidence_requirements": True,
        "may_define_acceptance_criteria": True,
        "may_define_guardrails": True,
        "actual_external_calls": 0,
        "actual_source_ingestions": 0,
        "actual_api_calls": 0,
        "actual_scrapes": 0,
        "actual_ai_generations": 0,
        "actual_form_submissions": 0,
        "actual_customer_data_access": 0,
        "actual_runtime_writes": 0,
        "actual_pilot_accounts_created": 0,
        "actual_support_workflows_activated": 0,
        "actual_customer_records_created": 0,
        "m1_pilot_operations_support_controlled_build_readiness_foundations": _foundation_payloads(),
        "pilot_operations_readiness_field_groups": _field_group_payloads(),
        "pilot_operations_readiness_statuses": _status_payloads(),
        "pilot_operations_readiness_status_universal_disclaimer": _STATUS_DISCLAIMER,
        "preview_only_pilot_operations_rules": list(_PREVIEW_ONLY_PILOT_OPERATIONS_RULES),
        "pilot_operations_readiness_by_support_area": _support_area_payloads(),
        "support_workflow_prerequisite_rules": list(_SUPPORT_WORKFLOW_PREREQUISITE_RULES),
        "success_evidence_feedback_and_escalation_rules": list(_SUCCESS_EVIDENCE_FEEDBACK_AND_ESCALATION_RULES),
        "sovereignty_and_trust_requirements": list(_SOVEREIGNTY_AND_TRUST_REQUIREMENTS),
        "sprint_139_does_not_build": list(_SPRINT139_DOES_NOT_BUILD),
        "m1_pilot_operations_support_readiness_exit_criteria": list(
            _M1_PILOT_OPERATIONS_SUPPORT_READINESS_EXIT_CRITERIA
        ),
        "risks_and_mitigations": _risk_payloads(),
        "sprint_140_recommended_next_step": _SPRINT140_RECOMMENDED_NEXT_STEP,
        "sprint_139_m1_pilot_operations_support_controlled_build_readiness_packet_proof": proof,
    }
    return _json_safe(out)


def _ordered_field_groups(pkt: dict[str, Any]) -> list[dict[str, Any]]:
    raw = pkt.get("pilot_operations_readiness_field_groups")
    if isinstance(raw, list):
        groups = [g for g in raw if isinstance(g, dict)]
        groups.sort(key=lambda g: g.get("priority") if isinstance(g.get("priority"), int) else 0)
        return groups
    return _field_group_payloads()


def render_active_source_activation_m1_pilot_operations_support_controlled_build_readiness_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render the operator-facing markdown packet (deterministic; uses ``packet`` when provided)."""
    pkt = packet if isinstance(packet, dict) else (
        build_active_source_activation_m1_pilot_operations_support_controlled_build_readiness_packet()
    )
    groups = _ordered_field_groups(pkt)
    lines: list[str] = [
        "# NativeForge M1 Pilot Operations and Support Controlled Build Readiness Packet v1",
        "",
        "## 1. Purpose",
        "",
        "This packet defines the M1 planning layer for pilot operations and support controlled build readiness. "
        "It is preview-only: it structures pilot operations scope, support intake, operator handoff, buyer "
        "follow-up, success evidence, escalation paths, support boundaries, training and documentation, customer "
        "feedback, pilot risk tracking, data sovereignty and security, pilot closeout fields, and acceptance "
        "criteria for operators without pilot onboarding, support workflow activation, customer record creation, "
        "external calls, scraping, form submission, AI generation, or customer data access.",
        "",
        "## 2. Why This Comes After Audit Export and Sovereignty Readiness",
        "",
        "Sprint 138 defined audit export and sovereignty readiness so trust, exportability, access, retention, "
        "provenance, consent, and sovereignty boundaries stay visible before operations language hardens. Sprint "
        "139 applies controlled build discipline to pilot operations and support only after those boundaries are "
        "visible—still without pilot account creation, support workflow activation, customer record creation, or "
        "runtime activation in this sprint.",
        "",
        "## 3. M1 Pilot Operations and Support Readiness Objective",
        "",
        "Deliver a preview-only readiness framework that prevents pilot operations implementation before support "
        "owners, intake rules, escalation paths, success evidence, feedback capture, training, sovereignty and "
        "security dependencies, and blockers are visible—without runnable support promises, pilot account creation, "
        "support workflow activation, customer record creation, customer data access, or external calls in this "
        "sprint.",
        "",
        "M1 pilot operations and support controlled build readiness foundations:",
        "",
    ]
    foundations = pkt.get("m1_pilot_operations_support_controlled_build_readiness_foundations")
    if not isinstance(foundations, list):
        foundations = _foundation_payloads()
    for row in foundations:
        if not isinstance(row, dict):
            continue
        area = row.get("foundation_area")
        focus = row.get("operator_focus")
        if isinstance(area, str) and isinstance(focus, str):
            lines.append(f"- **{area}**: {focus}")
    lines.extend(
        [
            "",
            "## 4. Preview-Only Pilot Operations Rules",
            "",
        ]
    )
    for rule in pkt.get("preview_only_pilot_operations_rules") or list(_PREVIEW_ONLY_PILOT_OPERATIONS_RULES):
        if isinstance(rule, str) and rule.strip():
            lines.append(f"- {rule}")
    lines.extend(
        [
            "",
            "Preview-only pilot operations rules restated: seeded or demo-safe records only; no real customer "
            "data; no pilot account creation; no support workflow activation; no customer record creation; no "
            "external calls.",
            "",
            "## 5. Required Pilot Operations Readiness Field Groups",
            "",
            "Eighteen field groups structure every pilot operations readiness row:",
            "",
        ]
    )
    for g in groups:
        if not isinstance(g, dict):
            continue
        name = g.get("name")
        purpose = g.get("purpose")
        if isinstance(name, str) and isinstance(purpose, str):
            lines.append(f"- **{name}**: {purpose}")
    lines.extend(
        [
            "",
            "## 6. Pilot Operations Readiness Status Definitions",
            "",
            "Eight preview-only pilot operations readiness statuses apply. Each status explicitly disclaims not "
            "pilot onboarding, not support workflow activation, and not customer record creation:",
            "",
        ]
    )
    statuses = pkt.get("pilot_operations_readiness_statuses")
    if not isinstance(statuses, list):
        statuses = _status_payloads()
    for row in statuses:
        if not isinstance(row, dict):
            continue
        st = row.get("status")
        df = row.get("definition")
        if isinstance(st, str) and isinstance(df, str):
            lines.append(f"### {st}")
            lines.append("")
            lines.append(df)
            lines.append("")
    lines.extend(["", "## 7. Field-Level Acceptance Criteria", ""])
    for g in groups:
        if not isinstance(g, dict):
            continue
        name = g.get("name")
        if not isinstance(name, str):
            continue
        lines.append(f"### {g.get('priority', '')}. {name}")
        lines.append("")
        crit = g.get("acceptance_criteria")
        if isinstance(crit, list):
            for c in crit:
                if isinstance(c, str) and c.strip():
                    lines.append(f"- {c}")
        lines.append("")
    lines.extend(["", "## 8. Pilot Operations Readiness by Support Area", ""])
    mapping = pkt.get("pilot_operations_readiness_by_support_area")
    if not isinstance(mapping, list):
        mapping = _support_area_payloads()
    for row in mapping:
        if not isinstance(row, dict):
            continue
        ar = row.get("support_area")
        preview = row.get("pilot_operations_support_readiness_preview")
        if isinstance(ar, str) and isinstance(preview, str):
            lines.append(f"- **{ar}**: {preview}")
    lines.extend(["", "## 9. Support Workflow Prerequisite Rules", ""])
    for item in pkt.get("support_workflow_prerequisite_rules") or list(_SUPPORT_WORKFLOW_PREREQUISITE_RULES):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 10. Success Evidence, Feedback, and Escalation Rules", ""])
    for item in pkt.get("success_evidence_feedback_and_escalation_rules") or list(
        _SUCCESS_EVIDENCE_FEEDBACK_AND_ESCALATION_RULES
    ):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 11. Sovereignty and Trust Requirements", ""])
    for item in pkt.get("sovereignty_and_trust_requirements") or list(_SOVEREIGNTY_AND_TRUST_REQUIREMENTS):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 12. What Sprint 139 Does Not Build", "", "Sprint 139 explicitly does not build:", ""])
    for item in pkt.get("sprint_139_does_not_build") or list(_SPRINT139_DOES_NOT_BUILD):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 13. M1 Pilot Operations and Support Readiness Exit Criteria",
            "",
        ]
    )
    for c in pkt.get("m1_pilot_operations_support_readiness_exit_criteria") or list(
        _M1_PILOT_OPERATIONS_SUPPORT_READINESS_EXIT_CRITERIA
    ):
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
            "## 15. Sprint 140 Recommended Next Step",
            "",
            pkt.get("sprint_140_recommended_next_step") or _SPRINT140_RECOMMENDED_NEXT_STEP,
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
