"""Sprint 130: M0 pilot transition and M1 readiness planning packet (preview-only).

Deterministic operator packet that defines M0-to-M1 transition criteria, pilot readiness fields,
buyer discovery follow-ups, implementation dependencies, guardrails, and acceptance criteria without
pilot onboarding, runtime activation, external calls, or customer data access.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = "nf_active_source_activation_m0_pilot_transition_m1_readiness_planning_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

_STATUS_DISCLAIMER = (
    "This status is not customer onboarding, is not production activation, and is not a signed pilot "
    "commitment."
)

_M0_TO_M1_FOUNDATIONS: tuple[tuple[str, str], ...] = (
    (
        "M0 demo outcome review",
        "Summarize what the demo proved, what was preview-only, and which evidence gaps remain before "
        "M1 planning.",
    ),
    (
        "Buyer discovery follow-up capture",
        "Record buyer questions, concerns, and interest signals as planning inputs without CRM automation "
        "or commitments.",
    ),
    (
        "Pilot fit assessment",
        "Score organizational readiness, urgency, data posture, and review capacity as qualitative "
        "signals only.",
    ),
    (
        "M1 scope boundary definition",
        "Translate M0 evidence and buyer feedback into explicit in-scope and out-of-scope M1 planning "
        "lines.",
    ),
    (
        "Data sovereignty readiness",
        "Document residency, export, consent, and boundary questions that must close before pilot-ready "
        "language is used.",
    ),
    (
        "Security and access readiness",
        "List identity, access control, logging, and integration security questions for later technical "
        "discovery.",
    ),
    (
        "Source ingestion readiness",
        "Clarify whether live Grants.gov or other sources are required and what seeded coverage proves "
        "today.",
    ),
    (
        "NOFO extraction readiness",
        "Map extraction confidence, human review needs, and parsing gaps without running extractors.",
    ),
    (
        "Form package readiness",
        "Capture SF-424 and form package expectations, preview limits, and signing boundaries as "
        "planning notes.",
    ),
    (
        "Human review workflow readiness",
        "Define review roles, SLAs, and escalation paths as planning assumptions, not activated "
        "workflows.",
    ),
    (
        "Export and audit readiness",
        "Describe export previews, audit log expectations, and evidence retention without moving "
        "customer data.",
    ),
    (
        "M1 implementation dependency tracking",
        "Maintain a dependency register linking buyer questions to engineering, policy, and operations "
        "follow-ups.",
    ),
)

_PILOT_READINESS_FIELD_GROUP_ROWS: tuple[tuple[str, str, tuple[str, str]], ...] = (
    (
        "Pilot readiness item identity",
        "Stable id, title, and version for each readiness row across operator artifacts.",
        (
            "Identity strings remain identical across repeated packet generations.",
            "Each readiness row exposes a single primary identity key for accountability.",
        ),
    ),
    (
        "Source M0 evidence reference",
        "Pointer to Sprint 129 evidence rows, fixtures, or sprint packets supporting the readiness claim.",
        (
            "References use in-repo sprint numbers, packet names, or labeled seeds only.",
            "Missing evidence references force explicit gap labels before pilot-ready language.",
        ),
    ),
    (
        "Buyer follow-up question",
        "Verbatim or faithful paraphrase of buyer questions tied to M1 dependencies.",
        (
            "Questions map to at least one M1 feature dependency field.",
            "Questions avoid implying signed pilot commitments or production activation.",
        ),
    ),
    (
        "Buyer concern category",
        "Tags such as sovereignty, security, data import, eligibility, scope, or operations concern.",
        (
            "Categories route to the review tracks defined in buyer follow-up capture rules.",
            "Ambiguous categories default to Needs buyer clarification until clarified.",
        ),
    ),
    (
        "M1 feature dependency",
        "Names the M1 product surface impacted such as live ingestion, NOFO parsing, or review workflow.",
        (
            "Dependencies align to the M1 readiness by product area map in this packet.",
            "Each row lists exactly one primary dependency to preserve traceability.",
        ),
    ),
    (
        "Pilot fit signal",
        "Qualitative signal about urgency, capacity, sponsor strength, or data maturity without scoring "
        "contracts.",
        (
            "Signals are labeled preview-only and non-commitment.",
            "Signals reference evidence or buyer notes rather than hidden intuition.",
        ),
    ),
    (
        "Data sovereignty dependency",
        "Lists sovereignty questions, residency needs, or export constraints blocking pilot-ready status.",
        (
            "Open sovereignty questions block Ready for M1 planning until resolved or deferred with "
            "rationale.",
            "Dependencies never assert private deployment unless contractually documented elsewhere.",
        ),
    ),
    (
        "Security/access dependency",
        "Captures authn, authz, secrets handling, and integration security gaps for technical discovery.",
        (
            "Open security questions block Ready for M1 planning until resolved or deferred with rationale.",
            "Dependencies forbid implying SOC2 or other certifications from this planning packet.",
        ),
    ),
    (
        "Source ingestion dependency",
        "States whether live Grants.gov or partner feeds are required and what is proven by seeds only.",
        (
            "Missing ingestion plans block live discovery readiness statements.",
            "Plans distinguish preview fixtures from production ingestion requirements.",
        ),
    ),
    (
        "NOFO extraction dependency",
        "Documents parser coverage, human review needs, and clause linkage gaps for M1 extraction work.",
        (
            "Low-confidence extraction requires visible human review dependency notes.",
            "Dependencies tie to provenance expectations for extracted fields.",
        ),
    ),
    (
        "Form package dependency",
        "Lists SF-424 field coverage, signing boundaries, and submission-adjacent risks as planning notes.",
        (
            "Dependencies restate preview-only posture for autofill and signing.",
            "Submission pathways must not be implied by planning language.",
        ),
    ),
    (
        "Human review dependency",
        "Defines reviewers, cadence assumptions, and escalation needs without activating workflows.",
        (
            "Missing review workflow blocks submission-adjacent readiness claims.",
            "Dependencies reference Sprint 127 planning gates without simulating approvals.",
        ),
    ),
    (
        "Export/audit dependency",
        "Tracks export previews, audit visibility, and retention expectations without exporting data here.",
        (
            "Dependencies pair export claims with data boundary notes.",
            "Customer data movement is forbidden in this sprint; note expectations only.",
        ),
    ),
    (
        "Implementation risk note",
        "Captures delivery, scope creep, resourcing, and misunderstanding risks for operators.",
        (
            "Risks call out confusion between buyer interest and signed commitments.",
            "Risks distinguish M0 demo evidence from production readiness.",
        ),
    ),
    (
        "Operator action required",
        "Concrete next planning steps such as schedule sovereignty review or document data boundaries.",
        (
            "Actions use planning verbs such as document or schedule, not activate or onboard.",
            "Actions remind operators that statuses are not customer onboarding or production activation.",
        ),
    ),
    (
        "Go/no-go recommendation",
        "Operator recommendation for pilot planning progression using the demo-safe statuses in this "
        "packet.",
        (
            "Recommendations apply to planning readiness only, not production launch.",
            "Recommendations repeat that they are not signed pilot commitments.",
        ),
    ),
    (
        "Non-production disclaimer",
        "Restates preview-only posture and lack of onboarding, activation, or runtime authority.",
        (
            "Disclaimers repeat no customer onboarding, no production activation, and no signed pilot "
            "commitment language.",
            "Disclaimers appear wherever status language could be misread as go-live approval.",
        ),
    ),
    (
        "Next sprint recommendation",
        "Points operators to Sprint 131 scope in preview-only language without executing runtime work.",
        (
            "Recommendations name Sprint 131 as the M1 Pilot Scope and Delivery Boundary Packet.",
            "Recommendations forbid silent expansion into runtime work without explicit authorization.",
        ),
    ),
)

_PILOT_READINESS_STATUS_ROWS: tuple[tuple[str, str], ...] = (
    (
        "Not assessed",
        "Default state before an operator scores the readiness row. " + _STATUS_DISCLAIMER,
    ),
    (
        "Ready for M1 planning",
        "Evidence, buyer notes, dependencies, and disclaimers satisfy field acceptance criteria for "
        "planning. " + _STATUS_DISCLAIMER,
    ),
    (
        "Needs buyer clarification",
        "Buyer questions or signals are ambiguous and need faithful follow-up before scope tightens. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Needs technical discovery",
        "Engineering or integration unknowns block crisp dependency statements. " + _STATUS_DISCLAIMER,
    ),
    (
        "Needs sovereignty review",
        "Data residency, export, or consent questions remain open for policy review. " + _STATUS_DISCLAIMER,
    ),
    (
        "Needs security review",
        "Access, secrets, or threat-model questions remain open for security review. " + _STATUS_DISCLAIMER,
    ),
    (
        "Blocked for pilot",
        "Critical gaps in sovereignty, security, data boundaries, ingestion, or review workflows block "
        "pilot planning. " + _STATUS_DISCLAIMER,
    ),
    (
        "Deferred beyond M1",
        "Item intentionally deferred past M1 with explicit rationale while remaining visible. "
        + _STATUS_DISCLAIMER,
    ),
)

_DEMO_SAFE_PILOT_TRANSITION_RULES: tuple[str, ...] = (
    "Require seeded or demo-safe records only; never import production customer extracts into transition "
    "planning.",
    "Do not access real customer data while building or reviewing this transition packet.",
    "Do not create pilot accounts, tenant records, or customer onboarding flows from this sprint packet.",
    "Do not activate M1 workflows, runtime flags, or production environments from this sprint packet.",
    "Do not imply signed pilot commitments; capture buyer interest as planning signals only.",
    "Do not place external API calls, scrapes, live ingestions, or live AI generations while using this "
    "packet.",
    "Do not submit applications, forms, or e-signatures while using this packet.",
    "Keep human judgment, provenance visibility, sovereignty boundaries, and missing-data disclosure "
    "explicit.",
)

_M1_READINESS_BY_PRODUCT_AREA: tuple[tuple[str, str], ...] = (
    (
        "organizational entity profile",
        "Readiness for tribal context fields, mission alignment inputs, and profile data boundaries before "
        "M1 configuration work.",
    ),
    (
        "live Grants.gov/source ingestion",
        "Readiness for live feeds, rate limits, keys, and operational monitoring distinct from seeded "
        "fixtures.",
    ),
    (
        "NOFO extraction and requirement parsing",
        "Readiness for parser coverage, clause traceability, confidence labeling, and human review hooks.",
    ),
    (
        "tribal eligibility and scoring",
        "Readiness for non-final scoring posture, policy review, and buyer-visible caveats in M1 scope.",
    ),
    (
        "pursuit pipeline",
        "Readiness for pipeline stages, owners, deadlines, and reporting without assuming production "
        "writes.",
    ),
    (
        "SF-424/form package preview",
        "Readiness for autofill mapping, signing boundaries, and submission-adjacent safeguards.",
    ),
    (
        "human review workflow",
        "Readiness for reviewer roles, SLAs, escalations, and audit expectations as planning assumptions.",
    ),
    (
        "data sovereignty and export",
        "Readiness for residency, export controls, consent tracking, and customer-owned data commitments.",
    ),
    (
        "audit logs and access control",
        "Readiness for tamper-evident logging expectations, access reviews, and least-privilege design.",
    ),
    (
        "pilot support and implementation operations",
        "Readiness for support channels, onboarding playbooks, and operator runbooks without executing "
        "them.",
    ),
)

_BUYER_FOLLOW_UP_CAPTURE: tuple[str, ...] = (
    "Buyer questions must map to M1 feature dependencies listed in pilot readiness rows.",
    "Sovereignty concerns must route to sovereignty review and data sovereignty dependency fields.",
    "Security concerns must route to security review and security/access dependency fields.",
    "Data import concerns must route to technical discovery and source ingestion dependency fields.",
    "Eligibility concerns must route to human review and policy review with non-final scoring caveats.",
    "Buyer interest does not create a pilot commitment; record interest separately from contractual "
    "status.",
)

_M1_IMPLEMENTATION_DEPENDENCY_RULES: tuple[str, ...] = (
    "Unresolved sovereignty questions block pilot-ready status until resolved or explicitly deferred.",
    "Unresolved security questions block pilot-ready status until resolved or explicitly deferred.",
    "Unresolved customer data boundaries block pilot-ready status until documented with operator sign-off.",
    "Missing source ingestion plan blocks live discovery readiness statements.",
    "Missing human review workflow blocks submission-adjacent readiness statements.",
    "No runtime activation occurs in this sprint; dependency tracking remains planning-only.",
)

_SOVEREIGNTY_AND_TRUST_REQUIREMENTS: tuple[str, ...] = (
    "customer owns its data",
    "no customer data required for seeded transition planning",
    "no customer data leaves the product during seeded demos",
    "no model training on customer data without explicit written consent",
    "human judgment remains final",
    "source provenance remains visible",
    "M1 pilot planning must not overpromise production readiness",
)

_SPRINT130_DOES_NOT_BUILD: tuple[str, ...] = (
    "no pilot account creation",
    "no customer onboarding",
    "no M1 workflow activation",
    "no customer data access",
    "no real application submission",
    "no production readiness certification",
    "no signed pilot commitment",
    "no external service call",
    "no database migration",
    "no frontend UI",
    "no API route",
    "no production workflow change",
)

_M0_EXIT_CRITERIA: tuple[str, ...] = (
    "All eighteen pilot readiness field groups are documented with purposes and acceptance criteria.",
    "All eight pilot readiness statuses include explicit non-onboarding, non-activation, and "
    "non-commitment disclaimers.",
    "All twelve M0-to-M1 foundation areas include operator focus statements without runtime execution.",
    "All ten M1 product area readiness mappings include dependency and caveat expectations.",
    "Buyer follow-up capture, implementation dependency rules, sovereignty requirements, and scope limits "
    "are listed.",
    "Risks and mitigations are recorded with go/no-go discipline expectations for operators.",
    "Sprint 131 recommendation is captured as the next preview-only M1 scope boundary planning step.",
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "buyer interest is mistaken for signed pilot commitment",
        "Label interest separately from contracts and repeat non-commitment disclaimers in statuses and "
        "notes.",
    ),
    (
        "M0 demo evidence is overstated as production readiness",
        "Cross-check every claim against Sprint 129 evidence references and preview-only language.",
    ),
    (
        "sovereignty concerns are under-scoped",
        "Force Needs sovereignty review until residency, export, and consent questions are documented.",
    ),
    (
        "security discovery is skipped",
        "Require Needs security review when authn, secrets, or integrations are unclear.",
    ),
    (
        "live source ingestion is assumed ready",
        "Block live discovery readiness until a written ingestion plan exists beyond seeded fixtures.",
    ),
    (
        "human review dependencies are ignored",
        "Block submission-adjacent readiness until reviewer roles, cadence, and escalations are defined.",
    ),
    (
        "customer data boundaries are unclear",
        "Block pilot-ready status until data inventory, minimization, and retention expectations are written.",
    ),
    (
        "M1 scope expands without operator approval",
        "Log scope changes with rationale and require explicit operator approval before expanding delivery.",
    ),
    (
        "readiness checklist becomes theater instead of go/no-go discipline",
        "Require explicit go/no-go rationale, risk notes, and blocked statuses instead of silent passes.",
    ),
)

_SPRINT131_RECOMMENDED_NEXT_STEP = (
    "Sprint 131 should deliver the M1 Pilot Scope and Delivery Boundary Packet, still preview-only and "
    "demo-safe unless the operator explicitly authorizes runtime work."
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _field_group_payloads() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, (name, purpose, criteria) in enumerate(_PILOT_READINESS_FIELD_GROUP_ROWS, start=1):
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
    return [{"foundation_area": a, "operator_focus": b} for a, b in _M0_TO_M1_FOUNDATIONS]


def _status_payloads() -> list[dict[str, str]]:
    return [{"status": s, "definition": d} for s, d in _PILOT_READINESS_STATUS_ROWS]


def _product_area_payloads() -> list[dict[str, str]]:
    return [{"product_area": a, "readiness_planning_focus": b} for a, b in _M1_READINESS_BY_PRODUCT_AREA]


def _risk_payloads() -> list[dict[str, str]]:
    return [{"risk": r, "mitigation": m} for r, m in _RISK_MITIGATIONS]


def build_active_source_activation_m0_pilot_transition_m1_readiness_planning_packet() -> dict[str, Any]:
    """Return the Sprint 130 M0 pilot transition and M1 readiness planning packet (deterministic)."""
    proof = {
        "sprint_130_m0_pilot_transition_m1_readiness_planning_packet_is_stateless": True,
        "sprint_130_m0_pilot_transition_m1_readiness_planning_packet_is_side_effect_free": True,
        "sprint_130_m0_pilot_transition_m1_readiness_planning_packet_is_preview_only": True,
        "sprint_130_m0_pilot_transition_m1_readiness_planning_packet_performs_no_runtime_work": True,
        "sprint_130_m0_pilot_transition_m1_readiness_planning_packet_emits_operator_planning_only": True,
    }
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 130,
        "packet_name": "NativeForge M0 Pilot Transition and M1 Readiness Planning Packet",
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_define_m0_to_m1_transition_scope": True,
        "may_define_pilot_readiness_fields": True,
        "may_define_buyer_followup_questions": True,
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
        "actual_customer_onboarding_started": 0,
        "actual_m1_workflows_activated": 0,
        "m0_to_m1_transition_foundations": _foundation_payloads(),
        "pilot_readiness_field_groups": _field_group_payloads(),
        "pilot_readiness_statuses": _status_payloads(),
        "pilot_readiness_status_universal_disclaimer": _STATUS_DISCLAIMER,
        "demo_safe_pilot_transition_rules": list(_DEMO_SAFE_PILOT_TRANSITION_RULES),
        "m1_readiness_by_product_area": _product_area_payloads(),
        "buyer_follow_up_question_capture": list(_BUYER_FOLLOW_UP_CAPTURE),
        "m1_implementation_dependency_rules": list(_M1_IMPLEMENTATION_DEPENDENCY_RULES),
        "sovereignty_and_trust_requirements": list(_SOVEREIGNTY_AND_TRUST_REQUIREMENTS),
        "sprint_130_does_not_build": list(_SPRINT130_DOES_NOT_BUILD),
        "m0_exit_criteria_for_pilot_transition_planning": list(_M0_EXIT_CRITERIA),
        "risks_and_mitigations": _risk_payloads(),
        "sprint_131_recommended_next_step": _SPRINT131_RECOMMENDED_NEXT_STEP,
        "sprint_130_m0_pilot_transition_m1_readiness_planning_packet_proof": proof,
    }
    return _json_safe(out)


def _ordered_field_groups(pkt: dict[str, Any]) -> list[dict[str, Any]]:
    raw = pkt.get("pilot_readiness_field_groups")
    if isinstance(raw, list):
        groups = [g for g in raw if isinstance(g, dict)]
        groups.sort(key=lambda g: g.get("priority") if isinstance(g.get("priority"), int) else 0)
        return groups
    return _field_group_payloads()


def render_active_source_activation_m0_pilot_transition_m1_readiness_planning_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render the operator-facing markdown packet (deterministic; uses ``packet`` when provided)."""
    pkt = packet if isinstance(packet, dict) else (
        build_active_source_activation_m0_pilot_transition_m1_readiness_planning_packet()
    )
    groups = _ordered_field_groups(pkt)
    lines: list[str] = [
        "# NativeForge M0 Pilot Transition and M1 Readiness Planning Packet v1",
        "",
        "## 1. Purpose",
        "",
        "This packet defines the M0 planning layer for transitioning from demo readiness to M1 paid "
        "pilot planning. It structures buyer feedback, evidence references, sovereignty and security "
        "questions, and implementation dependencies as operator-controlled readiness rows without pilot "
        "accounts, customer onboarding, workflow activation, external calls, or customer data access.",
        "",
        "## 2. Why This Comes After Demo Readiness Evidence Planning",
        "",
        "Sprint 129 defined the demo readiness evidence pack and operator checklist that anchored buyer "
        "claims to artifacts, caveats, provenance, and sovereignty statements. Sprint 130 defines how "
        "buyer feedback, evidence gaps, sovereignty concerns, and implementation dependencies become M1 "
        "readiness planning inputs while remaining preview-only and non-executing.",
        "",
        "## 3. M0-to-M1 Transition Objective",
        "",
        "Deliver a demo-safe transition framework that converts buyer questions and M0 evidence into M1 "
        "pilot readiness planning without triggering production onboarding, pilot account creation, or "
        "runtime activation. Outcomes inform M1 scope packets; they do not execute engineering work.",
        "",
        "M0-to-M1 transition foundations:",
        "",
    ]
    foundations = pkt.get("m0_to_m1_transition_foundations")
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
            "## 4. Demo-Safe Pilot Transition Rules",
            "",
        ]
    )
    for rule in pkt.get("demo_safe_pilot_transition_rules") or list(_DEMO_SAFE_PILOT_TRANSITION_RULES):
        if isinstance(rule, str) and rule.strip():
            lines.append(f"- {rule}")
    lines.extend(
        [
            "",
            "Demo-safe pilot transition rules restated: seeded or demo-safe records only; no real customer "
            "data; no pilot account creation; no customer onboarding; no M1 workflow activation; no "
            "signed pilot commitment; no external calls.",
            "",
            "## 5. Required Pilot Readiness Field Groups",
            "",
            "Eighteen field groups structure every pilot readiness row:",
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
            "## 6. Pilot Readiness Status Definitions",
            "",
            "Eight demo-safe pilot readiness statuses apply. Each status explicitly disclaims customer "
            "onboarding, production activation, and signed pilot commitments:",
            "",
        ]
    )
    statuses = pkt.get("pilot_readiness_statuses")
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
    lines.extend(["", "## 8. M1 Readiness by Product Area", ""])
    mapping = pkt.get("m1_readiness_by_product_area")
    if not isinstance(mapping, list):
        mapping = _product_area_payloads()
    for row in mapping:
        if not isinstance(row, dict):
            continue
        feat = row.get("product_area")
        focus = row.get("readiness_planning_focus")
        if isinstance(feat, str) and isinstance(focus, str):
            lines.append(f"- **{feat}**: {focus}")
    lines.extend(["", "## 9. Buyer Follow-Up Question Capture", ""])
    for item in pkt.get("buyer_follow_up_question_capture") or list(_BUYER_FOLLOW_UP_CAPTURE):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 10. M1 Implementation Dependency Rules", ""])
    for item in pkt.get("m1_implementation_dependency_rules") or list(_M1_IMPLEMENTATION_DEPENDENCY_RULES):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 11. Sovereignty and Trust Requirements", ""])
    for item in pkt.get("sovereignty_and_trust_requirements") or list(_SOVEREIGNTY_AND_TRUST_REQUIREMENTS):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 12. What Sprint 130 Does Not Build", "", "Sprint 130 explicitly does not build:", ""])
    for item in pkt.get("sprint_130_does_not_build") or list(_SPRINT130_DOES_NOT_BUILD):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 13. M0 Exit Criteria for Pilot Transition Planning",
            "",
        ]
    )
    for c in pkt.get("m0_exit_criteria_for_pilot_transition_planning") or list(_M0_EXIT_CRITERIA):
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
            "## 15. Sprint 131 Recommended Next Step",
            "",
            pkt.get("sprint_131_recommended_next_step") or _SPRINT131_RECOMMENDED_NEXT_STEP,
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
