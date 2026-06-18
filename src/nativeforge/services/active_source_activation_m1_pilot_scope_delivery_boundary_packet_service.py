"""Sprint 131: M1 pilot scope and delivery boundary packet (preview-only).

Deterministic operator packet that defines M1 paid pilot scope boundaries, included and excluded
capabilities, dependencies, guardrails, and acceptance criteria without pilot execution, activation,
external calls, or customer data access.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = "nf_active_source_activation_m1_pilot_scope_delivery_boundary_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

_STATUS_DISCLAIMER = (
    "This status is not production activation, is not customer onboarding, and is not a delivery "
    "commitment."
)

_M1_SCOPE_DELIVERY_FOUNDATIONS: tuple[tuple[str, str], ...] = (
    (
        "Pilot scope definition",
        "Names the M1 paid pilot boundary in operator language so scope cannot expand silently beyond "
        "validated buyer needs and delivery capacity.",
    ),
    (
        "Included M1 capabilities",
        "Lists capabilities explicitly in M1 pilot scope with preview-only posture and no activation "
        "claims.",
    ),
    (
        "Excluded M1 capabilities",
        "Lists capabilities deferred or forbidden for M1 with rationale tied to risk and sovereignty "
        "notes.",
    ),
    (
        "Pilot success criteria",
        "Defines measurable preview outcomes for the pilot packet without implying production certification.",
    ),
    (
        "Buyer dependency tracking",
        "Captures buyer decisions, data posture questions, and approvals needed before implementation work.",
    ),
    (
        "Operator dependency tracking",
        "Captures operator staffing, review cadence, and governance gates without routing live workflows.",
    ),
    (
        "Data sovereignty boundary",
        "Documents residency, export, minimization, and consent boundaries for M1 planning rows only.",
    ),
    (
        "Security/access boundary",
        "Documents identity, access control, logging, and integration limits as planning assumptions.",
    ),
    (
        "Human review boundary",
        "States where human judgment is mandatory and how review differs from automated suggestions.",
    ),
    (
        "Source ingestion boundary",
        "Separates seeded or demo fixtures from live Grants.gov or partner feed requirements for M1.",
    ),
    (
        "Form package boundary",
        "Clarifies SF-424 preview, autofill, signing, and non-submission posture for the pilot packet.",
    ),
    (
        "Support and delivery boundary",
        "Defines support expectations and delivery capacity limits without operational commitments.",
    ),
)

_PILOT_SCOPE_FIELD_GROUP_ROWS: tuple[tuple[str, str, tuple[str, str]], ...] = (
    (
        "Scope item identity",
        "Stable id, title, and version for each pilot scope row across operator artifacts.",
        (
            "Identity strings remain identical across repeated packet generations.",
            "Each scope row exposes a single primary identity key for traceability.",
        ),
    ),
    (
        "Pilot capability area",
        "Maps the row to a product area such as ingestion, NOFO parsing, or form preview for M1 planning.",
        (
            "Capability areas align to the M1 pilot scope by product area map in this packet.",
            "Each row lists exactly one primary capability area to avoid ambiguous scope merges.",
        ),
    ),
    (
        "Included in M1 flag",
        "Boolean or enum-style signal that the capability is explicitly in M1 pilot scope when true.",
        (
            "Included flags require linked acceptance criteria before marking in scope.",
            "Included flags never imply runtime activation or customer onboarding by themselves.",
        ),
    ),
    (
        "Excluded from M1 flag",
        "Boolean or enum-style signal that the capability is explicitly out of M1 pilot scope when true.",
        (
            "Excluded flags require an out-of-scope note referencing delivery or trust boundaries.",
            "Excluded flags must not silently flip without operator approval and rationale.",
        ),
    ),
    (
        "Delivery boundary",
        "Describes what engineering and operations may deliver versus what remains preview-only in M1.",
        (
            "Boundaries use planning verbs such as document or scope, not deploy or activate.",
            "Boundaries repeat that this packet is not a delivery commitment.",
        ),
    ),
    (
        "Buyer dependency",
        "Lists approvals, data access decisions, or policy inputs only the buyer can provide.",
        (
            "Open buyer dependencies block In M1 pilot scope until resolved or deferred with rationale.",
            "Dependencies avoid CRM automation and signed commitment language.",
        ),
    ),
    (
        "Operator dependency",
        "Lists staffing, review capacity, tooling, or governance steps only operators control.",
        (
            "Operator dependencies must name an accountable role or team without implying go-live.",
            "Dependencies pair with operator decision statuses when ownership is unclear.",
        ),
    ),
    (
        "Technical dependency",
        "Captures engineering unknowns, integration limits, or discovery work before implementation.",
        (
            "Technical unknowns route to Needs technical discovery until designs exist.",
            "Dependencies forbid database migrations or API routes from this sprint packet.",
        ),
    ),
    (
        "Sovereignty dependency",
        "Lists residency, export, retention, and consent questions that affect M1 data handling.",
        (
            "Open sovereignty questions block In M1 pilot scope until resolved or deferred with rationale.",
            "Dependencies never assert private deployment unless separately approved in writing.",
        ),
    ),
    (
        "Security/access dependency",
        "Captures authentication, authorization, secrets, and threat-model gaps for M1 scope.",
        (
            "Open security questions block In M1 pilot scope until resolved or deferred with rationale.",
            "Dependencies forbid implying certifications not evidenced elsewhere.",
        ),
    ),
    (
        "Human review dependency",
        "Defines mandatory human checkpoints for eligibility, forms, or narrative outputs in M1.",
        (
            "Submission-adjacent capabilities require visible human review dependency notes.",
            "Dependencies distinguish scoped review from routed production workflows.",
        ),
    ),
    (
        "Source ingestion dependency",
        "States live feed requirements, keying, rate limits, and what seeded data proves today.",
        (
            "Live ingestion must not be assumed ready without a written plan beyond demo fixtures.",
            "Dependencies separate preview fixtures from production ingestion requirements.",
        ),
    ),
    (
        "Form package dependency",
        "Captures SF-424 field coverage, signing boundaries, and non-submission safeguards for M1.",
        (
            "Form dependencies restate preview-only posture for autofill and signing.",
            "Submission pathways must not be implied by planning language in this packet.",
        ),
    ),
    (
        "Acceptance criteria",
        "Field-level pass or fail checks operators use before assigning a pilot scope status.",
        (
            "Each scope row carries at least two criteria tied to evidence or explicit gap labels.",
            "Criteria reinforce preview-only posture and non-commitment language.",
        ),
    ),
    (
        "Risk note",
        "Captures misunderstanding, scope creep, and trust risks visible to buyers and operators.",
        (
            "Risks call out confusion between planning packets and production readiness.",
            "Risks reference mitigations listed in the risks and mitigations section.",
        ),
    ),
    (
        "Out-of-scope note",
        "Explains why deferred capabilities stay visible without entering M1 silently.",
        (
            "Notes reference excluded flags and delivery boundaries explicitly.",
            "Notes remind readers this is not customer onboarding or activation.",
        ),
    ),
    (
        "Non-production disclaimer",
        "Restates preview-only posture and lack of onboarding, activation, runtime authority, or commitment.",
        (
            "Disclaimers repeat not customer onboarding, not production activation, and not a delivery "
            "commitment.",
            "Disclaimers appear wherever status language could be misread as go-live approval.",
        ),
    ),
    (
        "Next sprint recommendation",
        "Points operators to Sprint 132 dependency mapping in preview-only language without runtime work.",
        (
            "Recommendations name Sprint 132 as the M1 Pilot Implementation Dependency Map Packet.",
            "Recommendations forbid silent expansion into runtime work without explicit authorization.",
        ),
    ),
)

_PILOT_SCOPE_STATUS_ROWS: tuple[tuple[str, str], ...] = (
    (
        "In M1 pilot scope",
        "Capability is explicitly included for M1 paid pilot planning with documented acceptance criteria. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Out of M1 pilot scope",
        "Capability is explicitly excluded from M1 with visible rationale and out-of-scope notes. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Needs buyer decision",
        "Buyer approval, data posture choice, or policy input is required before tightening scope. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Needs operator decision",
        "Operator staffing, governance, or capacity decision is required before tightening scope. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Needs technical discovery",
        "Engineering or integration unknowns must be resolved before scope can be marked in or out. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Needs sovereignty review",
        "Residency, export, retention, or consent questions remain open for policy review. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Needs security review",
        "Access, secrets, or threat-model questions remain open for security review. " + _STATUS_DISCLAIMER,
    ),
    (
        "Deferred beyond M1",
        "Capability is intentionally deferred past M1 with explicit rationale while remaining visible. "
        + _STATUS_DISCLAIMER,
    ),
)

_PREVIEW_ONLY_PILOT_SCOPE_RULES: tuple[str, ...] = (
    "Require seeded or demo-safe records only; never import production customer extracts into pilot scope "
    "planning.",
    "Do not access real customer data while building or reviewing this pilot scope packet.",
    "Do not create pilot accounts, tenant records, or customer onboarding flows from this sprint packet.",
    "Do not activate M1 features, runtime flags, or production environments from this sprint packet.",
    "Do not treat this packet as a delivery commitment; it defines preview boundaries only.",
    "Do not place external API calls, scrapes, live ingestions, or live AI generations while using this "
    "packet.",
    "Do not submit applications, forms, or e-signatures while using this packet.",
    "Keep human judgment, provenance visibility, sovereignty boundaries, and missing-data disclosure "
    "explicit.",
)

_M1_PILOT_SCOPE_BY_PRODUCT_AREA: tuple[tuple[str, str], ...] = (
    (
        "organizational entity profile",
        "Scope boundary for tribal context fields, mission alignment inputs, and profile data handling in M1.",
    ),
    (
        "live Grants.gov/source ingestion",
        "Scope boundary for live feeds, credentials, rate limits, and monitoring distinct from demo fixtures.",
    ),
    (
        "manual NOFO upload",
        "Scope boundary for operator or buyer supplied documents versus automated acquisition paths.",
    ),
    (
        "NOFO extraction and requirement parsing",
        "Scope boundary for parser coverage, clause traceability, confidence labeling, and review hooks.",
    ),
    (
        "tribal eligibility and scoring",
        "Scope boundary for non-final scoring posture, policy review, and buyer-visible caveats in M1.",
    ),
    (
        "pursuit pipeline",
        "Scope boundary for pipeline stages, owners, deadlines, and reporting without assuming production "
        "writes.",
    ),
    (
        "SF-424/form package preview",
        "Scope boundary for autofill mapping, signing limits, and submission-adjacent safeguards.",
    ),
    (
        "human review workflow",
        "Scope boundary for reviewer roles, SLAs, escalations, and audit expectations as planning only.",
    ),
    (
        "data sovereignty and export",
        "Scope boundary for residency, export controls, consent tracking, and customer-owned data handling.",
    ),
    (
        "audit logs and access control",
        "Scope boundary for logging expectations, access reviews, and least-privilege design for M1.",
    ),
    (
        "pilot support and delivery operations",
        "Scope boundary for support channels, runbooks, and delivery capacity without operational promises.",
    ),
)

_INCLUDED_M1_CAPABILITY_BOUNDARY: tuple[str, ...] = (
    "Live Grants.gov/source ingestion may be planned but not activated by this sprint.",
    "Manual NOFO upload may be planned but not implemented by this sprint.",
    "Structured extraction may be planned but not executed by this sprint.",
    "Form package preview may be planned but not submitted by this sprint.",
    "Human review workflow may be scoped but not routed by this sprint.",
    "Export/audit readiness may be scoped but not executed by this sprint.",
)

_EXCLUDED_DEFERRED_CAPABILITY_BOUNDARY: tuple[str, ...] = (
    "No production submission within M1 pilot scope unless separately authorized in writing.",
    "No autonomous eligibility determination; human judgment remains authoritative.",
    "No unmanaged AI drafting of applications or eligibility conclusions.",
    "No customer data migration as part of this planning packet.",
    "No CRM automation driven by this sprint packet.",
    "No billing automation driven by this sprint packet.",
    "No private deployment commitment unless separately approved.",
    "No integration beyond the approved M1 pilot scope boundary.",
)

_SOVEREIGNTY_AND_TRUST_REQUIREMENTS: tuple[str, ...] = (
    "Customer owns its data.",
    "No customer data is required for this planning sprint.",
    "No customer data leaves the product during seeded demos.",
    "No model training on customer data without explicit written consent.",
    "Human judgment remains final.",
    "Source provenance remains visible.",
    "M1 pilot scope must not overpromise production readiness.",
)

_SPRINT131_DOES_NOT_BUILD: tuple[str, ...] = (
    "no pilot account creation",
    "no customer onboarding",
    "no M1 feature activation",
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

_M1_PILOT_SCOPE_EXIT_CRITERIA: tuple[str, ...] = (
    "All eighteen pilot scope field groups are documented with purposes and acceptance criteria.",
    "All eight pilot scope statuses include explicit non-onboarding, non-activation, and non-delivery "
    "commitment disclaimers.",
    "All twelve scope and delivery boundary foundations include operator focus statements without runtime "
    "execution.",
    "All eleven M1 pilot scope by product area mappings include boundary and caveat expectations.",
    "Included and excluded capability boundaries, sovereignty requirements, and preview rules are listed.",
    "Risks and mitigations are recorded with operator go or no-go discipline expectations.",
    "Sprint 132 recommendation is captured as the next preview-only implementation dependency mapping step.",
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "Pilot scope expands without operator approval",
        "Log every scope change with rationale and require explicit operator approval before expanding "
        "delivery promises.",
    ),
    (
        "Buyer assumes delivery commitment",
        "Repeat that this packet is preview-only, label planning artifacts separately from legal agreements, and "
        "use statuses that disclaim delivery commitments.",
    ),
    (
        "M1 scope implies production readiness",
        "Tie claims to Sprint 129 through Sprint 131 evidence language and forbid certification language in "
        "this packet.",
    ),
    (
        "Sovereignty review is skipped",
        "Force Needs sovereignty review until residency, export, retention, and consent questions are "
        "documented or deferred with rationale.",
    ),
    (
        "Security review is skipped",
        "Force Needs security review when authentication, secrets handling, or integrations are unclear.",
    ),
    (
        "Live ingestion readiness is assumed",
        "Block live ingestion claims until a written plan exists beyond seeded or demo-safe fixtures.",
    ),
    (
        "Form submission capability is implied",
        "Restate non-submission posture in form package boundaries and human review dependencies.",
    ),
    (
        "Human review dependency is ignored",
        "Block submission-adjacent language until reviewer roles, cadence, and escalations are defined.",
    ),
    (
        "Out-of-scope work enters the pilot silently",
        "Require excluded flags, out-of-scope notes, and operator approval before hidden scope enters M1.",
    ),
)

_SPRINT132_RECOMMENDED_NEXT_STEP = (
    "Sprint 132 should deliver the M1 Pilot Implementation Dependency Map Packet, still preview-only unless "
    "the operator explicitly authorizes runtime work."
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _field_group_payloads() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, (name, purpose, criteria) in enumerate(_PILOT_SCOPE_FIELD_GROUP_ROWS, start=1):
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
    return [{"foundation_area": a, "operator_focus": b} for a, b in _M1_SCOPE_DELIVERY_FOUNDATIONS]


def _status_payloads() -> list[dict[str, str]]:
    return [{"status": s, "definition": d} for s, d in _PILOT_SCOPE_STATUS_ROWS]


def _product_area_payloads() -> list[dict[str, str]]:
    return [
        {"product_area": a, "scope_boundary_preview": b} for a, b in _M1_PILOT_SCOPE_BY_PRODUCT_AREA
    ]


def _risk_payloads() -> list[dict[str, str]]:
    return [{"risk": r, "mitigation": m} for r, m in _RISK_MITIGATIONS]


def build_active_source_activation_m1_pilot_scope_delivery_boundary_packet() -> dict[str, Any]:
    """Return the Sprint 131 M1 pilot scope and delivery boundary packet (deterministic)."""
    proof = {
        "sprint_131_m1_pilot_scope_delivery_boundary_packet_is_stateless": True,
        "sprint_131_m1_pilot_scope_delivery_boundary_packet_is_side_effect_free": True,
        "sprint_131_m1_pilot_scope_delivery_boundary_packet_is_preview_only": True,
        "sprint_131_m1_pilot_scope_delivery_boundary_packet_performs_no_runtime_work": True,
        "sprint_131_m1_pilot_scope_delivery_boundary_packet_emits_operator_planning_only": True,
    }
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 131,
        "packet_name": "NativeForge M1 Pilot Scope and Delivery Boundary Packet",
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_define_m1_pilot_scope": True,
        "may_define_delivery_boundaries": True,
        "may_define_pilot_acceptance_criteria": True,
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
        "actual_m1_features_activated": 0,
        "m1_pilot_scope_delivery_boundary_foundations": _foundation_payloads(),
        "pilot_scope_field_groups": _field_group_payloads(),
        "pilot_scope_statuses": _status_payloads(),
        "pilot_scope_status_universal_disclaimer": _STATUS_DISCLAIMER,
        "preview_only_pilot_scope_rules": list(_PREVIEW_ONLY_PILOT_SCOPE_RULES),
        "m1_pilot_scope_by_product_area": _product_area_payloads(),
        "included_m1_capability_boundary": list(_INCLUDED_M1_CAPABILITY_BOUNDARY),
        "excluded_and_deferred_capability_boundary": list(_EXCLUDED_DEFERRED_CAPABILITY_BOUNDARY),
        "sovereignty_and_trust_requirements": list(_SOVEREIGNTY_AND_TRUST_REQUIREMENTS),
        "sprint_131_does_not_build": list(_SPRINT131_DOES_NOT_BUILD),
        "m1_pilot_scope_exit_criteria": list(_M1_PILOT_SCOPE_EXIT_CRITERIA),
        "risks_and_mitigations": _risk_payloads(),
        "sprint_132_recommended_next_step": _SPRINT132_RECOMMENDED_NEXT_STEP,
        "sprint_131_m1_pilot_scope_delivery_boundary_packet_proof": proof,
    }
    return _json_safe(out)


def _ordered_field_groups(pkt: dict[str, Any]) -> list[dict[str, Any]]:
    raw = pkt.get("pilot_scope_field_groups")
    if isinstance(raw, list):
        groups = [g for g in raw if isinstance(g, dict)]
        groups.sort(key=lambda g: g.get("priority") if isinstance(g.get("priority"), int) else 0)
        return groups
    return _field_group_payloads()


def render_active_source_activation_m1_pilot_scope_delivery_boundary_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render the operator-facing markdown packet (deterministic; uses ``packet`` when provided)."""
    pkt = packet if isinstance(packet, dict) else (
        build_active_source_activation_m1_pilot_scope_delivery_boundary_packet()
    )
    groups = _ordered_field_groups(pkt)
    lines: list[str] = [
        "# NativeForge M1 Pilot Scope and Delivery Boundary Packet v1",
        "",
        "## 1. Purpose",
        "",
        "This packet defines the M1 paid pilot scope and delivery boundaries after M0 demo readiness and "
        "pilot transition planning. It is preview-only: it structures scope items, dependencies, trust "
        "boundaries, and acceptance criteria for operators without creating pilot accounts, onboarding "
        "customers, activating M1 features, calling external services, or accessing customer data.",
        "",
        "## 2. Why This Comes After M0 Pilot Transition Planning",
        "",
        "Sprint 130 converted M0 evidence and buyer follow-up questions into M1 readiness planning inputs "
        "with explicit field groups and statuses. Sprint 131 turns that readiness into a clear M1 pilot "
        "scope and delivery boundary so M1 cannot expand silently beyond validated buyer needs and "
        "operator delivery capacity.",
        "",
        "## 3. M1 Pilot Scope Objective",
        "",
        "Deliver a preview-only scope boundary that names what is in M1, what is excluded, which "
        "dependencies must close, and which human and trust gates apply—without runtime execution, pilot "
        "account creation, customer onboarding, M1 feature activation, or delivery commitments.",
        "",
        "M1 pilot scope and delivery boundary foundations:",
        "",
    ]
    foundations = pkt.get("m1_pilot_scope_delivery_boundary_foundations")
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
            "## 4. Preview-Only Pilot Scope Rules",
            "",
        ]
    )
    for rule in pkt.get("preview_only_pilot_scope_rules") or list(_PREVIEW_ONLY_PILOT_SCOPE_RULES):
        if isinstance(rule, str) and rule.strip():
            lines.append(f"- {rule}")
    lines.extend(
        [
            "",
            "Preview-only pilot scope rules restated: seeded or demo-safe records only; no real customer "
            "data; no pilot account creation; no customer onboarding; no M1 feature activation; no "
            "delivery commitment; no external calls.",
            "",
            "## 5. Required Pilot Scope Field Groups",
            "",
            "Eighteen field groups structure every pilot scope row:",
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
            "## 6. Pilot Scope Status Definitions",
            "",
            "Eight preview-only pilot scope statuses apply. Each status explicitly disclaims production "
            "activation, customer onboarding, and delivery commitments:",
            "",
        ]
    )
    statuses = pkt.get("pilot_scope_statuses")
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
    lines.extend(["", "## 8. M1 Pilot Scope by Product Area", ""])
    mapping = pkt.get("m1_pilot_scope_by_product_area")
    if not isinstance(mapping, list):
        mapping = _product_area_payloads()
    for row in mapping:
        if not isinstance(row, dict):
            continue
        feat = row.get("product_area")
        focus = row.get("scope_boundary_preview")
        if isinstance(feat, str) and isinstance(focus, str):
            lines.append(f"- **{feat}**: {focus}")
    lines.extend(["", "## 9. Included M1 Capability Boundary", ""])
    for item in pkt.get("included_m1_capability_boundary") or list(_INCLUDED_M1_CAPABILITY_BOUNDARY):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 10. Excluded and Deferred Capability Boundary", ""])
    for item in pkt.get("excluded_and_deferred_capability_boundary") or list(
        _EXCLUDED_DEFERRED_CAPABILITY_BOUNDARY
    ):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 11. Sovereignty and Trust Requirements", ""])
    for item in pkt.get("sovereignty_and_trust_requirements") or list(_SOVEREIGNTY_AND_TRUST_REQUIREMENTS):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 12. What Sprint 131 Does Not Build", "", "Sprint 131 explicitly does not build:", ""])
    for item in pkt.get("sprint_131_does_not_build") or list(_SPRINT131_DOES_NOT_BUILD):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 13. M1 Pilot Scope Exit Criteria",
            "",
        ]
    )
    for c in pkt.get("m1_pilot_scope_exit_criteria") or list(_M1_PILOT_SCOPE_EXIT_CRITERIA):
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
            "## 15. Sprint 132 Recommended Next Step",
            "",
            pkt.get("sprint_132_recommended_next_step") or _SPRINT132_RECOMMENDED_NEXT_STEP,
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
