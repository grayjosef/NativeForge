"""Sprint 128: M0 demo narrative and buyer walkthrough packet (preview-only).

Deterministic operator packet that defines demo narrative structure and buyer walkthrough steps for M0.
No live sales scripts, no buyer records, no external calls, and no customer data access.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = "nf_active_source_activation_m0_demo_narrative_buyer_walkthrough_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

_STAGE_MANDATORY_BOUNDARY = (
    "This stage uses seeded or demo-safe data only. The demo does not submit applications, does "
    "not make final eligibility determinations, and does not access real customer data."
)

M0_DEMO_NARRATIVE_CHAPTERS: tuple[str, ...] = (
    "Buyer problem framing",
    "NativeForge product promise",
    "Entity profile walkthrough",
    "Seeded opportunity discovery walkthrough",
    "Tribal eligibility and mission fit walkthrough",
    "NOFO summary walkthrough",
    "Recommendation preview walkthrough",
    "Pursuit pipeline walkthrough",
    "SF-424 autofill preview walkthrough",
    "Requirement checklist walkthrough",
    "Data sovereignty and export walkthrough",
    "Human review and demo closeout walkthrough",
)

_WALKTHROUGH_STAGE_ROWS: tuple[tuple[str, str], ...] = (
    (
        "Opening problem frame",
        "Anchor the buyer pain narrative with grant pursuit friction and trust concerns before "
        "showing product surfaces.",
    ),
    (
        "Entity profile setup",
        "Walk through organizational entity profile fields as planning context for seeded demos.",
    ),
    (
        "Opportunity discovery preview",
        "Show seeded Grants.gov-style opportunity discovery without live ingestion.",
    ),
    (
        "Eligibility and mission fit preview",
        "Preview tribal eligibility and mission fit signals as non-final planning aids.",
    ),
    (
        "NOFO summary preview",
        "Present plain-language NOFO summary text with visible provenance and caveats.",
    ),
    (
        "Recommendation preview",
        "Explain draft opportunity recommendations as human-reviewable previews only.",
    ),
    (
        "Pipeline and deadline preview",
        "Show pursuit pipeline and deadline visibility using demo-safe timelines.",
    ),
    (
        "SF-424 autofill preview",
        "Demonstrate SF-424 autofill preview fields without submission or signing.",
    ),
    (
        "Requirement checklist preview",
        "Walk requirement checklist preview items tied to extracted NOFO language.",
    ),
    (
        "Sovereignty and export preview",
        "Explain sovereignty policy and export preview posture without production data movement.",
    ),
    (
        "Human review closeout",
        "Close with human review gates, evidence notes, and explicit non-final disclaimers.",
    ),
    (
        "Buyer next-step discussion",
        "Transition to follow-up discovery questions and Sprint 129 evidence planning only.",
    ),
)

_FIELD_GROUP_ROWS: tuple[tuple[str, str, tuple[str, str]], ...] = (
    (
        "Walkthrough step identity",
        "Stable id and title so operators reference the same demo beat across artifacts.",
        (
            "Each step exposes a stable name and ordering index in planning packets only.",
            "Identity strings remain identical across repeated packet generations.",
        ),
    ),
    (
        "Buyer pain point",
        "States the friction or risk the step addresses without implying production outcomes.",
        (
            "Pain points reference generic grant pursuit themes unless tied to seeded examples.",
            "Pain language avoids guarantees of funding or eligibility.",
        ),
    ),
    (
        "Demo feature shown",
        "Names the M0 surface demonstrated in the step such as profile, NOFO summary, or pipeline.",
        (
            "Feature names map to M0 planning-layer surfaces, not production endpoints.",
            "Each step lists exactly one primary feature to keep accountability clear.",
        ),
    ),
    (
        "Source data used",
        "Declares whether content is seeded, synthetic, or sprint packet lineage for provenance.",
        (
            "Source categories are limited to demo-safe labels such as seed or template.",
            "Missing lineage forces an explicit gap label before any buyer-facing narrative.",
        ),
    ),
    (
        "Demo-safe caveat",
        "Short buyer-heard caveat that outputs are preview-only and non-final.",
        (
            "Caveats repeat no submission, no final eligibility, and no customer data for the step.",
            "Caveats appear adjacent to any AI-adjacent or form-adjacent claims.",
        ),
    ),
    (
        "Buyer value proof point",
        "Explains the buyer-visible value without overstating automation or coverage.",
        (
            "Proof points tie to observable UI or artifact examples in planning language.",
            "Proof points avoid implying live integrations beyond M0 scope.",
        ),
    ),
    (
        "Sovereignty/trust proof point",
        "Reinforces data ownership, provenance visibility, and consent boundaries.",
        (
            "Trust proof points never assert private cloud deployment unless contractually true later.",
            "Trust notes pair with visible provenance expectations for the step.",
        ),
    ),
    (
        "Human review proof point",
        "Shows where human judgment, review gates, or overrides remain authoritative.",
        (
            "Review proof points cite Sprint 127 planning gates without simulating approvals.",
            "Overrides are described as human-led, not silent model edits.",
        ),
    ),
    (
        "Risk or limitation note",
        "Captures buyer misunderstanding risks and product limits for the step.",
        (
            "Risks default to visible disclosure rather than silent omission.",
            "Limitation notes distinguish preview scaffolding from production readiness.",
        ),
    ),
    (
        "Transition to next step",
        "Defines how operators move the narrative forward without executing workflows.",
        (
            "Transitions use planning verbs such as navigate or summarize, not submit or approve.",
            "Transitions include an explicit reminder of demo-safe data posture.",
        ),
    ),
    (
        "Operator talking point",
        "Concise script-adjacent guidance that is not a generated live sales script.",
        (
            "Talking points are bullet guidance constants, not CRM-automated outreach.",
            "Talking points include at least one non-production disclaimer hook.",
        ),
    ),
    (
        "Evidence artifact reference",
        "Points to sprint packets, seeds, or fixtures that evidence the demo claim.",
        (
            "References use in-repo artifact names rather than live ticket systems.",
            "Missing artifacts block claims of completeness in the narrative plan.",
        ),
    ),
    (
        "Field provenance visibility",
        "Ensures lineage from seed or upstream sprint artifacts stays visible to buyers.",
        (
            "Every buyer-visible field lists provenance category in the planning model.",
            "Hidden provenance is treated as a narrative defect to correct before demos.",
        ),
    ),
    (
        "Non-production disclaimer",
        "Restates preview-only posture and lack of production legal or submission authority.",
        (
            "Disclaimers repeat preview-only and no runtime execution for the step.",
            "Disclaimers appear wherever status language could be misread as go-live approval.",
        ),
    ),
    (
        "Buyer question prompt",
        "Suggests respectful discovery prompts buyers may ask without scripting coercion.",
        (
            "Prompts invite clarification rather than leading to a false production promise.",
            "Prompts include space for tribal context and mission nuance.",
        ),
    ),
    (
        "Follow-up discovery question",
        "Captures operator questions to log after the walkthrough for honest scoping.",
        (
            "Follow-ups are planning prompts, not CRM tasks created by this sprint.",
            "Follow-ups reference sovereignty, eligibility, or deadline concerns explicitly.",
        ),
    ),
    (
        "Closeout evidence",
        "Lists evidence operators should retain after the demo narrative rehearsal.",
        (
            "Closeout evidence references review checklists without persisting databases here.",
            "Evidence lists include provenance and caveat confirmations.",
        ),
    ),
    (
        "Next sprint recommendation",
        "Points operators to Sprint 129 evidence pack planning without executing it.",
        (
            "Recommendations name Sprint 129 scope in preview-only language.",
            "Recommendations forbid silent expansion into runtime engineering.",
        ),
    ),
)

_BUYER_WALKTHROUGH_BY_M0_FEATURE: tuple[tuple[str, str], ...] = (
    (
        "organizational entity profile",
        "Entity fields, tribal context, and mission alignment inputs shown as seeded planning data.",
    ),
    (
        "seeded opportunity ingestion",
        "Seeded Grants.gov-style opportunities surfaced without live ingestion or scraping.",
    ),
    (
        "tribal eligibility and mission fit scoring",
        "Preview scores and rationales labeled non-final with visible confidence and caveats.",
    ),
    (
        "NOFO plain-language summary",
        "Summary bullets traced to seeded NOFO excerpts with extraction provenance called out.",
    ),
    (
        "opportunity recommendation preview",
        "Ranked or tagged recommendations shown as drafts pending human review.",
    ),
    (
        "pursuit pipeline and deadline tracking",
        "Kanban-style stages and deadlines illustrated with demo-safe dates and owners.",
    ),
    (
        "SF-424 autofill preview",
        "Form field previews mapped from entity profile without submission or e-sign.",
    ),
    (
        "requirement checklist preview",
        "Checklist rows tied to NOFO clauses with explicit completeness gaps allowed.",
    ),
    (
        "data sovereignty policy and export preview",
        "Policy statements and export posture explained without moving real customer data.",
    ),
    (
        "human review closeout",
        "Review statuses, override reasons, and closeout evidence described per Sprint 127 planning.",
    ),
)

_DEMO_SAFE_NARRATIVE_RULES: tuple[str, ...] = (
    "Require seeded or demo-safe records only; never load production customer extracts into demo "
    "narratives.",
    "Do not access real customer data during walkthrough planning or presentation rehearsals.",
    "Do not submit applications, forms, or e-signatures from demo surfaces.",
    "Do not present final eligibility determinations; label all eligibility signals as preview-only.",
    "Do not imply live sales automation, CRM writes, or buyer record creation from this packet.",
    "Do not place external API calls, scrapes, or live AI generations while rehearsing this packet.",
    "Keep human judgment, provenance, and review boundaries visible in every step.",
)

_BUYER_PROOF_POINTS: tuple[str, ...] = (
    "fewer repeated fields",
    "faster opportunity understanding",
    "clearer tribal eligibility relevance",
    "better deadline visibility",
    "human-reviewed recommendations",
    "visible source provenance",
    "sovereignty-first data handling",
    "export and audit readiness",
)

_DEMO_CAVEATS_AND_BOUNDARIES: tuple[str, ...] = (
    "seeded/demo-safe data only",
    "no real application submission",
    "no final eligibility decision",
    "no final legal or compliance advice",
    "no customer data access",
    "no production workflow execution",
    "no hidden AI decision-making",
    "no model training on customer data without explicit written consent",
)

_SOVEREIGNTY_AND_TRUST_REQUIREMENTS: tuple[str, ...] = (
    "customer owns its data",
    "no customer data required for seeded demos",
    "no customer data leaves the product during seeded demos",
    "no model training on customer data without explicit written consent",
    "human judgment remains final",
    "source provenance remains visible",
    "demo narrative must not overpromise private deployment or production readiness",
)

_SPRINT128_DOES_NOT_BUILD: tuple[str, ...] = (
    "no live sales script generation",
    "no buyer record creation",
    "no CRM automation",
    "no customer data access",
    "no real application submission",
    "no final eligibility determination",
    "no external service call",
    "no database migration",
    "no frontend UI",
    "no API route",
    "no production workflow change",
)

_M0_EXIT_CRITERIA: tuple[str, ...] = (
    "All twelve narrative chapters are documented with matching walkthrough field group coverage.",
    "All twelve walkthrough stages include explicit seeded-data and non-submission boundary text.",
    "Buyer proof points, caveats, sovereignty requirements, and Sprint 128 scope limits are listed.",
    "Risks and mitigations are recorded with artifact-linked proof expectations for operators.",
    "Sprint 129 recommendation is captured as the next preview-only evidence planning step.",
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "buyer mistakes seeded demo for production readiness",
        "Open every stage with preview-only language and cite M0 planning artifacts, not SLAs.",
    ),
    (
        "buyer assumes final eligibility determinations",
        "Repeat non-final eligibility labels and show human review gates before recommendations.",
    ),
    (
        "demo implies application submission capability",
        "Disable submission verbs in talking points and show explicit no-submit disclaimers.",
    ),
    (
        "data sovereignty claims are overstated",
        "Pair sovereignty statements with provenance, export limits, and consent boundaries.",
    ),
    (
        "AI decision-making appears hidden",
        "Surface model roles as assistive, cite confidence, and require human review proof points.",
    ),
    (
        "human review boundaries are unclear",
        "Map each feature to review gate language from Sprint 127 planning without simulating routes.",
    ),
    (
        "demo narrative becomes too generic for Native buyers",
        "Anchor prompts on tribal mission context, sovereignty, and community outcomes in field groups.",
    ),
    (
        "buyer value proof points are not tied to artifacts",
        "Require evidence artifact references for every proof point in operator planning tables.",
    ),
    (
        "follow-up discovery questions are not captured",
        "Mandate follow-up discovery question fields per stage and log them outside this packet.",
    ),
)

_SPRINT129_RECOMMENDED_NEXT_STEP = (
    "Sprint 129 should deliver the M0 Demo Readiness Evidence Pack and Operator Checklist Packet, "
    "still preview-only and demo-safe unless the operator explicitly authorizes runtime work."
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _field_group_payloads() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, (name, purpose, criteria) in enumerate(_FIELD_GROUP_ROWS, start=1):
        out.append(
            {
                "priority": i,
                "name": name,
                "purpose": purpose,
                "acceptance_criteria": list(criteria),
            }
        )
    return out


def _stage_payloads() -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for i, (stage, purpose) in enumerate(_WALKTHROUGH_STAGE_ROWS, start=1):
        out.append(
            {
                "priority": str(i),
                "stage": stage,
                "purpose": purpose,
                "mandatory_demo_boundary_statement": _STAGE_MANDATORY_BOUNDARY,
            }
        )
    return out


def _feature_mapping_payloads() -> list[dict[str, str]]:
    return [
        {"m0_feature": a, "buyer_walkthrough_planning_focus": b} for a, b in _BUYER_WALKTHROUGH_BY_M0_FEATURE
    ]


def _risk_payloads() -> list[dict[str, str]]:
    return [{"risk": r, "mitigation": m} for r, m in _RISK_MITIGATIONS]


def build_active_source_activation_m0_demo_narrative_buyer_walkthrough_packet() -> dict[str, Any]:
    """Return the Sprint 128 M0 demo narrative and buyer walkthrough packet (deterministic)."""
    proof = {
        "sprint_128_m0_demo_narrative_buyer_walkthrough_packet_is_stateless": True,
        "sprint_128_m0_demo_narrative_buyer_walkthrough_packet_is_side_effect_free": True,
        "sprint_128_m0_demo_narrative_buyer_walkthrough_packet_is_preview_only": True,
        "sprint_128_m0_demo_narrative_buyer_walkthrough_packet_performs_no_runtime_work": True,
        "sprint_128_m0_demo_narrative_buyer_walkthrough_packet_emits_operator_planning_only": True,
    }
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 128,
        "packet_name": "NativeForge M0 Demo Narrative and Buyer Walkthrough Packet",
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_define_demo_narrative_scope": True,
        "may_define_buyer_walkthrough_steps": True,
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
        "actual_demo_scripts_generated": 0,
        "actual_buyer_records_created": 0,
        "actual_sales_automation_runs": 0,
        "m0_demo_narrative_chapters": list(M0_DEMO_NARRATIVE_CHAPTERS),
        "walkthrough_field_groups": _field_group_payloads(),
        "walkthrough_stages": _stage_payloads(),
        "demo_safe_narrative_rules": list(_DEMO_SAFE_NARRATIVE_RULES),
        "buyer_walkthrough_by_m0_feature": _feature_mapping_payloads(),
        "buyer_proof_points": list(_BUYER_PROOF_POINTS),
        "demo_caveats_and_boundaries": list(_DEMO_CAVEATS_AND_BOUNDARIES),
        "sovereignty_and_trust_requirements": list(_SOVEREIGNTY_AND_TRUST_REQUIREMENTS),
        "sprint_128_does_not_build": list(_SPRINT128_DOES_NOT_BUILD),
        "m0_demo_narrative_planning_exit_criteria": list(_M0_EXIT_CRITERIA),
        "risks_and_mitigations": _risk_payloads(),
        "sprint_129_recommended_next_step": _SPRINT129_RECOMMENDED_NEXT_STEP,
        "sprint_128_m0_demo_narrative_buyer_walkthrough_packet_proof": proof,
    }
    return _json_safe(out)


def _ordered_field_groups(pkt: dict[str, Any]) -> list[dict[str, Any]]:
    raw = pkt.get("walkthrough_field_groups")
    if isinstance(raw, list):
        groups = [g for g in raw if isinstance(g, dict)]
        groups.sort(key=lambda g: g.get("priority") if isinstance(g.get("priority"), int) else 0)
        return groups
    return _field_group_payloads()


def render_active_source_activation_m0_demo_narrative_buyer_walkthrough_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render the operator-facing markdown packet (deterministic; uses ``packet`` when provided)."""
    pkt = packet if isinstance(packet, dict) else (
        build_active_source_activation_m0_demo_narrative_buyer_walkthrough_packet()
    )
    groups = _ordered_field_groups(pkt)
    lines: list[str] = [
        "# NativeForge M0 Demo Narrative and Buyer Walkthrough Packet v1",
        "",
        "## 1. Purpose",
        "",
        "This packet defines the M0 planning layer for a demo-safe buyer narrative and walkthrough. "
        "It structures operator guidance, proof points, caveats, guardrails, acceptance criteria, and "
        "forward-only Sprint 129 guidance without generating live sales scripts, creating buyer "
        "records, executing workflows, or accessing customer data.",
        "",
        "## 2. Why This Comes After Human Review Closeout",
        "",
        "Sprint 127 defined the review gates and demo closeout criteria that keep M0 outputs honest "
        "and buyer-safe. Sprint 128 packages the full buyer-facing story across those gates—mapping "
        "narrative chapters, walkthrough stages, and field-level acceptance criteria—while preserving "
        "the same caveats, provenance visibility, and human review boundaries.",
        "",
        "## 3. M0 Demo Narrative Objective",
        "",
        "Deliver a clear buyer walkthrough that proves NativeForge can reduce grant pursuit friction "
        "while protecting sovereignty, explainability, and human control. The narrative stays "
        "preview-only: it informs later demo scripts or implementation plans rather than executing them.",
        "",
        "Narrative chapters sequenced for M0 planning:",
        "",
    ]
    for ch in pkt.get("m0_demo_narrative_chapters") or list(M0_DEMO_NARRATIVE_CHAPTERS):
        if isinstance(ch, str) and ch.strip():
            lines.append(f"- {ch}")
    lines.extend(
        [
            "",
            "## 4. Demo-Safe Narrative Rules",
            "",
        ]
    )
    for rule in pkt.get("demo_safe_narrative_rules") or list(_DEMO_SAFE_NARRATIVE_RULES):
        if isinstance(rule, str) and rule.strip():
            lines.append(f"- {rule}")
    lines.extend(
        [
            "",
            "Demo-safe narrative rules restated: seeded or demo-safe records only; no real customer "
            "data; no live application submission; no final eligibility determination; no generated "
            "sales automation; no buyer record creation; no external calls.",
            "",
            "## 5. Required Walkthrough Field Groups",
            "",
            "Eighteen field groups structure every buyer walkthrough step in M0 planning:",
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
    lines.extend(["", "## 6. Walkthrough Stage Definitions", "", "Twelve demo-safe stages apply:", ""])
    stages = pkt.get("walkthrough_stages")
    if not isinstance(stages, list):
        stages = _stage_payloads()
    for row in stages:
        if not isinstance(row, dict):
            continue
        st = row.get("stage")
        if not isinstance(st, str):
            continue
        lines.append(f"### {st}")
        lines.append("")
        pur = row.get("purpose")
        if isinstance(pur, str):
            lines.append(pur)
            lines.append("")
        bnd = row.get("mandatory_demo_boundary_statement")
        if isinstance(bnd, str):
            lines.append(bnd)
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
    lines.extend(["", "## 8. Buyer Walkthrough by M0 Feature", ""])
    mapping = pkt.get("buyer_walkthrough_by_m0_feature")
    if not isinstance(mapping, list):
        mapping = _feature_mapping_payloads()
    for row in mapping:
        if not isinstance(row, dict):
            continue
        feat = row.get("m0_feature")
        focus = row.get("buyer_walkthrough_planning_focus")
        if isinstance(feat, str) and isinstance(focus, str):
            lines.append(f"- **{feat}**: {focus}")
    lines.extend(["", "## 9. Buyer Proof Points", ""])
    for item in pkt.get("buyer_proof_points") or list(_BUYER_PROOF_POINTS):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 10. Demo Caveats and Boundaries", ""])
    for item in pkt.get("demo_caveats_and_boundaries") or list(_DEMO_CAVEATS_AND_BOUNDARIES):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 11. Sovereignty and Trust Requirements", ""])
    for item in pkt.get("sovereignty_and_trust_requirements") or list(_SOVEREIGNTY_AND_TRUST_REQUIREMENTS):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 12. What Sprint 128 Does Not Build", "", "Sprint 128 explicitly does not build:", ""])
    for item in pkt.get("sprint_128_does_not_build") or list(_SPRINT128_DOES_NOT_BUILD):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 13. M0 Exit Criteria for Demo Narrative Planning",
            "",
        ]
    )
    for c in pkt.get("m0_demo_narrative_planning_exit_criteria") or list(_M0_EXIT_CRITERIA):
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
            "## 15. Sprint 129 Recommended Next Step",
            "",
            pkt.get("sprint_129_recommended_next_step") or _SPRINT129_RECOMMENDED_NEXT_STEP,
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
