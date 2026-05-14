"""Sprint 140: M1 pilot demo-to-build transition closeout packet (preview-only).

Deterministic operator packet that closes the M1 controlled build readiness sequence with a
demo-to-build transition summary—evidence, blockers, approvals, deferred items, sovereignty and
security guardrails, and build authorization gates—without pilot launch, customer onboarding,
production activation, external calls, or runtime side effects.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = "nf_active_source_activation_m1_pilot_demo_to_build_transition_closeout_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

_STATUS_DISCLAIMER = (
    "This status is not pilot launch, is not customer onboarding, and is not production activation."
)

_M1_DEMO_TO_BUILD_TRANSITION_CLOSEOUT_PREVIEW_FOUNDATIONS: tuple[tuple[str, str], ...] = (
    (
        "M1 evidence summary readiness",
        "Consolidates traceable evidence pointers and sprint references without claiming runtime outcomes.",
    ),
    (
        "M1 feature area closeout readiness",
        "Maps each M1 feature slice to closeout field coverage without implying implementation completion.",
    ),
    (
        "Outstanding blocker readiness",
        "Keeps blockers visible with owners or explicit owner-needed labels before build transition review.",
    ),
    (
        "Human approval gate readiness",
        "States where human judgment is mandatory versus informational preview-only planning.",
    ),
    (
        "Deferred item readiness",
        "Ensures deferred work stays on the roadmap and in the closeout inventory beyond M1.",
    ),
    (
        "Pilot readiness narrative",
        "Frames pilot language as planning narrative only without launching a pilot.",
    ),
    (
        "Buyer follow-up readiness",
        "Plans buyer-visible notes that preserve trust boundaries and avoid overpromising pilot readiness.",
    ),
    (
        "Controlled build authorization readiness",
        "Separates controlled build authorization review from pilot launch and production activation.",
    ),
    (
        "Risk transfer readiness",
        "Documents risk transfer notes without executing risk acceptance or production changes.",
    ),
    (
        "Data sovereignty and security readiness",
        "Aligns sovereignty and security prerequisites with transition closeout before authorization review.",
    ),
    (
        "Support readiness closeout",
        "Summarizes support boundary closeout after Sprint 139 without activating support workflows.",
    ),
    (
        "Sprint 141 transition readiness",
        "Positions Sprint 141 as the controlled build authorization review packet in preview-only terms.",
    ),
)

_TRANSITION_CLOSEOUT_FIELD_GROUP_ROWS: tuple[tuple[str, str, tuple[str, str]], ...] = (
    (
        "Transition closeout item identity",
        "Stable id, title, and version for each closeout row across operator artifacts.",
        (
            "Identity strings remain identical across repeated packet generations.",
            "Each closeout item exposes a single primary identity key for traceability.",
        ),
    ),
    (
        "M1 readiness area",
        "Maps the row to evidence, feature closeout, blockers, approvals, deferrals, or authorization.",
        (
            "Every row lists exactly one primary M1 readiness area before closeout review proceeds.",
            "Readiness area labels stay preview-only and forbid silent promotion to runtime execution.",
        ),
    ),
    (
        "Source sprint reference",
        "Ties evidence and decisions to originating sprint artifacts without mutating them.",
        (
            "Source sprint references are explicit or marked unknown before evidence is treated as informed.",
            "References remain read-only pointers with no external calls or runtime writes.",
        ),
    ),
    (
        "Evidence summary",
        "Summarizes what evidence exists, what is missing, and what is demo-seeded only.",
        (
            "Evidence summaries distinguish demo-seeded artifacts from unresolved production claims.",
            "Evidence language disclaims pilot launch, customer onboarding, and production activation.",
        ),
    ),
    (
        "Closeout status",
        "Applies a preview-only transition closeout status with universal disclaimers.",
        (
            "Closeout statuses always include not pilot launch, not customer onboarding, and not production "
            "activation language in their definitions.",
            "Closeout status must not imply implementation completion or runtime go-live.",
        ),
    ),
    (
        "Blocker status",
        "Signals whether blockers are open, owned, or need resolution before build transition.",
        (
            "Every blocker row names an owner or explicit owner-needed status before transition review.",
            "Blocker notes repeat not pilot launch, not customer onboarding, not production activation.",
        ),
    ),
    (
        "Human approval requirement",
        "States whether operator human approval is required before later authorized engineering.",
        (
            "Each build transition item states whether human approval is required or explicitly not required.",
            "Approval fields never substitute for controlled build authorization review in later sprints.",
        ),
    ),
    (
        "Deferred item flag",
        "Marks intentional deferrals so deferred items remain visible in the closeout packet.",
        (
            "Deferred items must remain visible in the closeout packet and roadmap views.",
            "Deferral language disclaims hiding work behind vague later buckets.",
        ),
    ),
    (
        "Buyer-facing note",
        "Captures buyer-visible language with trust boundaries and non-overpromising posture.",
        (
            "Buyer-facing notes must not overpromise pilot readiness or imply customer onboarding.",
            "Buyer notes pair with operator-only detail where ambiguity could confuse stakeholders.",
        ),
    ),
    (
        "Operator-facing note",
        "Captures operator-only context, caveats, and execution risks without buyer overreach.",
        (
            "Operator notes document assumptions, unknowns, and dependencies for internal review.",
            "Operator notes avoid implying production activation from planning-only closeout rows.",
        ),
    ),
    (
        "Risk transfer note",
        "Documents how residual risk is acknowledged without executing formal risk transfer.",
        (
            "Risk transfer notes pair with mitigations when residual acceptance is still pending.",
            "Risk transfer language disclaims pilot launch and production activation from this sprint.",
        ),
    ),
    (
        "Sovereignty prerequisite",
        "Records residency, export, consent, and data ownership expectations as planning controls.",
        (
            "Sovereignty prerequisites are visible before data sovereignty readiness is treated as informed.",
            "Unresolved sovereignty blockers prevent build transition readiness statements from clearing.",
        ),
    ),
    (
        "Security prerequisite",
        "Captures least privilege, secrets handling, and review expectations without runtime changes.",
        (
            "Security prerequisites are visible before security readiness is treated as informed.",
            "Security language disclaims API routes, production workflow change, and runtime activation.",
        ),
    ),
    (
        "Controlled build authorization requirement",
        "States what operator authorization is needed separately from pilot launch decisions.",
        (
            "Controlled build authorization requires explicit operator approval distinct from this packet.",
            "Authorization fields keep pilot launch and production activation out of Sprint 140 scope.",
        ),
    ),
    (
        "Acceptance criteria",
        "Field-level pass or fail checks operators use before assigning a transition closeout status.",
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
            "Restates preview-only posture and lack of pilot launch, customer onboarding, production activation, "
            "and live calls."
        ),
        (
            "Disclaimers repeat not pilot launch, not customer onboarding, and not production activation.",
            "Disclaimers appear wherever status language could be misread as go-live authorization.",
        ),
    ),
    (
        "Next sprint recommendation",
        "Points operators to Sprint 141 controlled build authorization review in preview-only language.",
        (
            "Recommendations name Sprint 141 as the M1 Controlled Build Authorization Review Packet.",
            "Recommendations forbid silent expansion into runtime work without explicit authorization.",
        ),
    ),
)

_TRANSITION_CLOSEOUT_STATUS_ROWS: tuple[tuple[str, str], ...] = (
    (
        "Not assessed",
        "Closeout row exists but lacks minimum field coverage; must be assessed before review improves. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Ready for closeout review",
        "Field groups are sufficient for operator demo-to-build transition closeout review without execution "
        "promises. " + _STATUS_DISCLAIMER,
    ),
    (
        "Ready for controlled build authorization review",
        "Closeout evidence and gates are ready to inform a later authorization review packet only. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Needs human approval",
        "Operator human judgment is required before treating the row as ready for later build planning. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Needs blocker resolution",
        "Open blockers or missing owners prevent the row from advancing until planning resolves them. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Deferred beyond M1",
        "Work is intentionally deferred past M1 while remaining visible in the closeout inventory. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Blocked before build transition",
        "Unresolved sovereignty, security, evidence, or approval gaps block demo-to-build transition readiness. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Closed for planning only",
        "Planning fields are complete for this sprint while runtime execution remains explicitly out of scope. "
        + _STATUS_DISCLAIMER,
    ),
)

_PREVIEW_ONLY_TRANSITION_CLOSEOUT_RULES: tuple[str, ...] = (
    "Require seeded or demo-safe records only; never import production customer extracts into closeout rows.",
    "Do not access real customer data while building or reviewing this demo-to-build transition closeout packet.",
    "Do not launch pilots, onboard customers, or activate production systems from this sprint packet.",
    "Do not place external API calls, scrapes, live ingestions, or live AI generations while using this packet.",
    "Do not submit forms, invoke AI generation, or perform runtime writes while using this packet.",
    "Do not activate sources, perform live ingestion, or change production workflows while using this packet.",
    "Keep human judgment, sovereignty boundaries, provenance visibility, and non-execution disclaimers explicit.",
)

_M1_READINESS_EVIDENCE_BY_PRODUCT_AREA: tuple[tuple[str, str], ...] = (
    (
        "source ingestion readiness",
        "Evidence ties ingestion planning to prior sprint artifacts without live ingestion execution.",
    ),
    (
        "NOFO extraction readiness",
        "Evidence summarizes extraction planning boundaries without implying automated extraction go-live.",
    ),
    (
        "form package readiness",
        "Evidence covers form package planning outputs without form submission or workflow activation.",
    ),
    (
        "human review readiness",
        "Evidence lists review gate coverage from M0/M1 planning packets without production approval routes.",
    ),
    (
        "audit/export sovereignty readiness",
        "Evidence references audit and export sovereignty readiness packets without exporting customer data.",
    ),
    (
        "pilot operations support readiness",
        "Evidence summarizes Sprint 139 pilot operations and support planning without pilot launch.",
    ),
    (
        "buyer follow-up readiness",
        "Evidence captures buyer follow-up planning without customer onboarding or record creation.",
    ),
    (
        "support boundary readiness",
        "Evidence states support boundaries without activating support workflows or production changes.",
    ),
    (
        "data sovereignty readiness",
        "Evidence lists sovereignty prerequisites and gaps without moving customer data out of trust boundaries.",
    ),
    (
        "security readiness",
        "Evidence lists security prerequisites and gaps without changing production security posture.",
    ),
    (
        "controlled build authorization readiness",
        "Evidence frames what operators must authorize later without conflating authorization with pilot launch.",
    ),
)

_BLOCKER_AND_APPROVAL_GATE_RULES: tuple[str, ...] = (
    "Every blocker must have an owner or explicit owner-needed status.",
    "Every build transition item must state whether human approval is required.",
    "Deferred items must remain visible in the closeout packet.",
    "Buyer-facing notes must not overpromise pilot readiness.",
    "Unresolved sovereignty or security blockers prevent build transition readiness from clearing.",
    "Controlled build authorization requires explicit operator approval distinct from this closeout packet.",
)

_DEMO_TO_BUILD_TRANSITION_RULES: tuple[str, ...] = (
    "Readiness evidence must be traceable to source sprint references.",
    "Closeout status must not imply implementation completion.",
    "Controlled build authorization must remain separate from pilot launch.",
    "Buyer follow-up must preserve trust boundaries.",
    "Deferred items must not disappear from the roadmap.",
    "No pilot is launched in this sprint.",
    "No runtime activation occurs in this sprint.",
)

_SOVEREIGNTY_AND_TRUST_REQUIREMENTS: tuple[str, ...] = (
    "Customer owns its data.",
    "No customer data is required for this planning sprint.",
    "No customer data leaves the product during seeded demos.",
    "No model training on customer data without explicit written consent.",
    "Human judgment remains final.",
    "Source provenance remains visible.",
    "Transition closeout readiness must not overpromise implementation readiness.",
)

_SPRINT140_DOES_NOT_BUILD: tuple[str, ...] = (
    "no pilot launch",
    "no customer onboarding",
    "no production activation",
    "no customer record creation",
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

_M1_TRANSITION_CLOSEOUT_EXIT_CRITERIA: tuple[str, ...] = (
    "All eighteen transition closeout field groups are documented with purposes and acceptance criteria.",
    "All eight transition closeout statuses include explicit not pilot launch, not customer onboarding, and not "
    "production activation disclaimers.",
    "All twelve demo-to-build transition closeout preview foundations include operator focus statements without "
    "runtime execution.",
    "All eleven M1 readiness evidence by product area rows include preview mapping language and caveat "
    "expectations.",
    "Blocker and approval gate rules, demo-to-build transition rules, sovereignty and trust requirements, and "
    "preview-only rules are listed.",
    "Risks and mitigations are recorded with operator discipline expectations before Sprint 141 authorization "
    "review.",
    "Sprint 141 recommendation is captured as the next preview-only controlled build authorization review step.",
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "Pilot launch is implied by closeout language",
        "Pair closeout language with explicit not pilot launch statements until a later authorized sprint.",
    ),
    (
        "Customer onboarding is implied too early",
        "Repeat not customer onboarding beside every readiness status and in non-production disclaimers.",
    ),
    (
        "Production activation is implied too early",
        "Restate not production activation wherever authorization or readiness language appears.",
    ),
    (
        "Unresolved blockers are hidden",
        "Require visible blocker status, owners, and operator notes before clearing closeout statuses.",
    ),
    (
        "Human approval gates are skipped",
        "Bind human approval requirement fields to controlled build authorization expectations for Sprint 141.",
    ),
    (
        "Deferred items disappear from roadmap",
        "Keep deferred item flags and buyer or operator notes synchronized with visible deferral lists.",
    ),
    (
        "Buyer-facing notes overpromise readiness",
        "Review buyer-facing notes against trust boundaries and explicit non-go-live disclaimers.",
    ),
    (
        "Sovereignty or security blockers are under-scoped",
        "Expand sovereignty and security prerequisites until unresolved items are visible or explicitly deferred.",
    ),
    (
        "Transition closeout becomes theater instead of control",
        "Require traceable identities, evidence summaries, risk notes, and acceptance criteria alongside every "
        "status.",
    ),
)

_SPRINT141_RECOMMENDED_NEXT_STEP = (
    "Sprint 141 should deliver the M1 Controlled Build Authorization Review Packet, still preview-only unless the "
    "operator explicitly authorizes runtime work."
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _field_group_payloads() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, (name, purpose, criteria) in enumerate(_TRANSITION_CLOSEOUT_FIELD_GROUP_ROWS, start=1):
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
        {"foundation_area": a, "operator_focus": b}
        for a, b in _M1_DEMO_TO_BUILD_TRANSITION_CLOSEOUT_PREVIEW_FOUNDATIONS
    ]


def _status_payloads() -> list[dict[str, str]]:
    return [{"status": s, "definition": d} for s, d in _TRANSITION_CLOSEOUT_STATUS_ROWS]


def _product_area_payloads() -> list[dict[str, str]]:
    return [
        {"product_area": a, "m1_readiness_evidence_preview": b} for a, b in _M1_READINESS_EVIDENCE_BY_PRODUCT_AREA
    ]


def _risk_payloads() -> list[dict[str, str]]:
    return [{"risk": r, "mitigation": m} for r, m in _RISK_MITIGATIONS]


def build_active_source_activation_m1_pilot_demo_to_build_transition_closeout_packet() -> dict[str, Any]:
    """Return the Sprint 140 M1 pilot demo-to-build transition closeout packet (deterministic)."""
    proof = {
        "sprint_140_m1_pilot_demo_to_build_transition_closeout_packet_is_stateless": True,
        "sprint_140_m1_pilot_demo_to_build_transition_closeout_packet_is_side_effect_free": True,
        "sprint_140_m1_pilot_demo_to_build_transition_closeout_packet_is_preview_only": True,
        "sprint_140_m1_pilot_demo_to_build_transition_closeout_packet_performs_no_runtime_work": True,
        "sprint_140_m1_pilot_demo_to_build_transition_closeout_packet_emits_operator_planning_only": True,
    }
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 140,
        "packet_name": "NativeForge M1 Pilot Demo-to-Build Transition Closeout Packet",
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_define_transition_closeout_readiness": True,
        "may_define_m1_evidence_summary": True,
        "may_define_blockers_and_approvals": True,
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
        "actual_pilots_launched": 0,
        "actual_customer_onboarding_started": 0,
        "actual_production_systems_activated": 0,
        "m1_demo_to_build_transition_closeout_preview_foundations": _foundation_payloads(),
        "transition_closeout_field_groups": _field_group_payloads(),
        "transition_closeout_statuses": _status_payloads(),
        "transition_closeout_status_universal_disclaimer": _STATUS_DISCLAIMER,
        "preview_only_transition_closeout_rules": list(_PREVIEW_ONLY_TRANSITION_CLOSEOUT_RULES),
        "m1_readiness_evidence_by_product_area": _product_area_payloads(),
        "blocker_and_approval_gate_rules": list(_BLOCKER_AND_APPROVAL_GATE_RULES),
        "demo_to_build_transition_rules": list(_DEMO_TO_BUILD_TRANSITION_RULES),
        "sovereignty_and_trust_requirements": list(_SOVEREIGNTY_AND_TRUST_REQUIREMENTS),
        "sprint_140_does_not_build": list(_SPRINT140_DOES_NOT_BUILD),
        "m1_transition_closeout_exit_criteria": list(_M1_TRANSITION_CLOSEOUT_EXIT_CRITERIA),
        "risks_and_mitigations": _risk_payloads(),
        "sprint_141_recommended_next_step": _SPRINT141_RECOMMENDED_NEXT_STEP,
        "sprint_140_m1_pilot_demo_to_build_transition_closeout_packet_proof": proof,
    }
    return _json_safe(out)


def _ordered_field_groups(pkt: dict[str, Any]) -> list[dict[str, Any]]:
    raw = pkt.get("transition_closeout_field_groups")
    if isinstance(raw, list):
        groups = [g for g in raw if isinstance(g, dict)]
        groups.sort(key=lambda g: g.get("priority") if isinstance(g.get("priority"), int) else 0)
        return groups
    return _field_group_payloads()


def render_active_source_activation_m1_pilot_demo_to_build_transition_closeout_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render the operator-facing markdown packet (deterministic; uses ``packet`` when provided)."""
    pkt = (
        packet
        if isinstance(packet, dict)
        else build_active_source_activation_m1_pilot_demo_to_build_transition_closeout_packet()
    )
    groups = _ordered_field_groups(pkt)
    lines: list[str] = [
        "# NativeForge M1 Pilot Demo-to-Build Transition Closeout Packet v1",
        "",
        "## 1. Purpose",
        "",
        "This packet closes the M1 controlled build readiness sequence and prepares a preview-only demo-to-build "
        "transition summary. It consolidates evidence summaries, feature-area closeout views, blockers, human "
        "approval gates, deferred items, sovereignty and security prerequisites, controlled build authorization "
        "expectations, and acceptance criteria for operators without pilot launch, customer onboarding, production "
        "activation, external calls, scraping, form submission, AI generation, customer data access, database "
        "migrations, frontend UI, API routes, or runtime activation.",
        "",
        "## 2. Why This Comes After Pilot Operations and Support Readiness",
        "",
        "Sprint 139 defined pilot operations and support readiness so intake, escalation, evidence, feedback, and "
        "support boundaries stay visible before the M1 chain closes. Sprint 140 consolidates the M1 readiness chain "
        "into a demo-to-build transition closeout packet before any later authorized build or pilot launch "
        "work—still without pilot launch, customer onboarding, production activation, or runtime side effects in "
        "this sprint.",
        "",
        "## 3. M1 Demo-to-Build Transition Objective",
        "",
        "Deliver a preview-only closeout framework that summarizes evidence, blockers, approvals, deferred items, "
        "sovereignty and security dependencies, and build authorization gates without launching a pilot, onboarding "
        "customers, activating production systems, performing live ingestion, or placing external calls in this "
        "sprint.",
        "",
        "M1 demo-to-build transition closeout preview foundations:",
        "",
    ]
    foundations = pkt.get("m1_demo_to_build_transition_closeout_preview_foundations")
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
            "## 4. Preview-Only Transition Closeout Rules",
            "",
        ]
    )
    for rule in pkt.get("preview_only_transition_closeout_rules") or list(
        _PREVIEW_ONLY_TRANSITION_CLOSEOUT_RULES
    ):
        if isinstance(rule, str) and rule.strip():
            lines.append(f"- {rule}")
    lines.extend(
        [
            "",
            "Preview-only transition closeout rules restated: seeded or demo-safe records only; no real customer "
            "data; no pilot launch; no customer onboarding; no production activation; no external calls; no "
            "runtime activation.",
            "",
            "## 5. Required Transition Closeout Field Groups",
            "",
            "Eighteen field groups structure every transition closeout row:",
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
            "## 6. Transition Closeout Status Definitions",
            "",
            "Eight preview-only transition closeout statuses apply. Each status explicitly disclaims not pilot "
            "launch, not customer onboarding, and not production activation:",
            "",
        ]
    )
    statuses = pkt.get("transition_closeout_statuses")
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
    lines.extend(["", "## 8. M1 Readiness Evidence by Product Area", ""])
    mapping = pkt.get("m1_readiness_evidence_by_product_area")
    if not isinstance(mapping, list):
        mapping = _product_area_payloads()
    for row in mapping:
        if not isinstance(row, dict):
            continue
        ar = row.get("product_area")
        preview = row.get("m1_readiness_evidence_preview")
        if isinstance(ar, str) and isinstance(preview, str):
            lines.append(f"- **{ar}**: {preview}")
    lines.extend(["", "## 9. Blocker and Approval Gate Rules", ""])
    for item in pkt.get("blocker_and_approval_gate_rules") or list(_BLOCKER_AND_APPROVAL_GATE_RULES):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 10. Demo-to-Build Transition Rules", ""])
    for item in pkt.get("demo_to_build_transition_rules") or list(_DEMO_TO_BUILD_TRANSITION_RULES):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 11. Sovereignty and Trust Requirements", ""])
    for item in pkt.get("sovereignty_and_trust_requirements") or list(_SOVEREIGNTY_AND_TRUST_REQUIREMENTS):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 12. What Sprint 140 Does Not Build", "", "Sprint 140 explicitly does not build:", ""])
    for item in pkt.get("sprint_140_does_not_build") or list(_SPRINT140_DOES_NOT_BUILD):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 13. M1 Transition Closeout Exit Criteria",
            "",
        ]
    )
    for c in pkt.get("m1_transition_closeout_exit_criteria") or list(_M1_TRANSITION_CLOSEOUT_EXIT_CRITERIA):
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
            "## 15. Sprint 141 Recommended Next Step",
            "",
            pkt.get("sprint_141_recommended_next_step") or _SPRINT141_RECOMMENDED_NEXT_STEP,
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
