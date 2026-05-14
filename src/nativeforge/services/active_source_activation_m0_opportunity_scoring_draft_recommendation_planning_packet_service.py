"""Sprint 122: M0 opportunity scoring and draft recommendation planning packet (preview-only).

Deterministic operator packet for demo-safe recommendation preview scope, factor groups, tiers,
guardrails, and acceptance criteria. Does not score real opportunities, call external systems,
invoke LLMs, or run production recommendation engines.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = (
    "nf_active_source_activation_m0_opportunity_scoring_draft_recommendation_planning_packet_v1"
)
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

M0_RECOMMENDATION_PREVIEW_FOUNDATIONS: tuple[str, ...] = (
    "Opportunity pursuit recommendation preview",
    "Draft recommendation summary preview",
    "Scoring factor rollup",
    "Eligibility confidence display",
    "Mission fit rationale display",
    "Capacity and deadline risk display",
    "Funding and match risk display",
    "Reporting burden warning display",
    "Human review and override workflow",
    "Future pursuit pipeline handoff readiness",
)

_FIELD_GROUP_ROWS: tuple[tuple[str, str, tuple[str, str]], ...] = (
    (
        "Eligibility preview result",
        "Captures seeded eligibility preview labels and advisory outcomes for rollup narratives only.",
        (
            "Every value cites seeded eligibility preview fields with explicit preview-only labeling.",
            "Conflicting seeded labels increment human-review routing without automated adjudication.",
        ),
    ),
    (
        "Eligibility confidence",
        "Expresses bounded demo numerics or qualitative confidence on seeded previews, not determinations.",
        (
            "Confidence strings never replace legal eligibility findings in operator scripts.",
            "Low confidence must appear beside recommendation preview output in specifications.",
        ),
    ),
    (
        "Mission fit score",
        "Holds deterministic fixture mission fit scores aligned to organizational profile seeds.",
        (
            "Scores are illustrative with demo watermarks and bounded ranges from fixtures only.",
            "Missing mission context blocks strong pursue preview tiers until operators add seeds.",
        ),
    ),
    (
        "Tribal relevance score",
        "Surfaces tribal pathway relevance from seeded taxonomies without implying federal recognition.",
        (
            "Scores require explicit tribal relevance fixture coverage with reviewer-visible gaps.",
            "Absence of a path cannot hide the opportunity from human review queues in M0.",
        ),
    ),
    (
        "Funding priority alignment",
        "Maps seeded funding priorities to organizational appetite fields for demo rollup only.",
        (
            "Alignment uses fixture dictionaries with no live agency budget verification.",
            "Misaligned priorities downgrade preview tiers with visible rationale text, not auto-hides.",
        ),
    ),
    (
        "Deadline feasibility",
        "Compares seeded deadlines to seeded capacity calendars without live calendar integration.",
        (
            "All date math is deterministic on fixtures with explicit time zone or placeholder rules.",
            "Ambiguous deadlines route to human review before any pursue-with-conditions preview claims.",
        ),
    ),
    (
        "Staff capacity fit",
        "Estimates seeded staffing envelopes against pursuit effort placeholders for demos only.",
        (
            "Capacity figures are synthetic or fixture-backed with non-production labeling.",
            "Capacity shortfalls pair with visible risk callouts, not silent suppression of review.",
        ),
    ),
    (
        "Match and cost-share risk",
        "Rolls up seeded match percentages, waivers, and in-kind burdens into advisory risk bands.",
        (
            "Risk bands include reviewer override hooks in demo walkthrough specifications.",
            "High match risk cannot trigger automated do-not-pursue finalization in M0 planning.",
        ),
    ),
    (
        "Reporting burden risk",
        "Quantifies seeded reporting cadence and indicator counts as illustrative burden preview only.",
        (
            "Burden integers are demo-labeled and never imply compliance certification.",
            "High burden must surface reporting burden warning display copy in planning artifacts.",
        ),
    ),
    (
        "Source confidence",
        "Propagates fixture provenance strength for opportunity and profile seed lineage.",
        (
            "Low source confidence caps recommendation preview strength with visible warnings.",
            "Provenance never implies live Grants.gov validation or external freshness.",
        ),
    ),
    (
        "NOFO summary confidence",
        "Reflects confidence in seeded NOFO summary preview text assembled without live parsing.",
        (
            "Summary confidence is separate from eligibility confidence in all operator narratives.",
            "Low summary confidence requires citation of seeded summary fields only in scripts.",
        ),
    ),
    (
        "Required attachment readiness",
        "Tracks checklist placeholders for attachments implied by seeded requirement metadata.",
        (
            "Readiness states are fixture-only with no uploads or customer document storage in M0.",
            "Missing attachments block strong pursue preview tiers until seeds or notes are supplied.",
        ),
    ),
    (
        "Authorized representative readiness",
        "Captures signer and delegation placeholders for demo SF-424 readiness storylines.",
        (
            "Readiness flags are synthetic and must not impersonate live SAM.gov entity data.",
            "Unknown signer posture routes previews to needs human review tiers deterministically.",
        ),
    ),
    (
        "SF-424 preview readiness",
        "Aggregates seeded SF-424 field coverage for preview panels without form submission.",
        (
            "Readiness scores enumerate fixture fields only with explicit non-submission posture.",
            "Partial readiness pairs with pursue-with-conditions preview language, not hidden waivers.",
        ),
    ),
    (
        "Pursuit effort estimate",
        "Provides bounded demo effort bands from seeded complexity metadata for buyer education.",
        (
            "Estimates are not staffing contracts and exclude billing or procurement language.",
            "Effort bands align to deterministic lookup tables from fixture complexity codes.",
        ),
    ),
    (
        "Pursuit recommendation tier",
        "Assigns demo-safe preview tier labels with mandatory non-final disclaimers in all outputs.",
        (
            "Tier labels always ship with not a final pursuit decision and not a final eligibility "
            "determination language in markdown and UI specifications.",
            "Tier changes require visible factor citations from seeded fields only.",
        ),
    ),
    (
        "Human override reason",
        "Stores structured reason codes when reviewers supersede deterministic preview tier assembly.",
        (
            "Override reasons persist in planning artifacts for future auditable runtime designs.",
            "Overrides cannot delete underlying seeded factors from audit trails in specifications.",
        ),
    ),
    (
        "Draft recommendation narrative constraints",
        "Defines deterministic narrative rules so previews explain factors without inventing facts.",
        (
            "Constraints forbid culturally generic or pan-Indian language in demo copy templates.",
            "Constraints require user editability and human review before any use outside demo.",
        ),
    ),
)

_RECOMMENDATION_PREVIEW_TO_M0_FEATURES: tuple[tuple[str, str], ...] = (
    (
        "pursuit recommendation preview",
        "Uses eligibility preview result, eligibility confidence, mission fit score, tribal relevance score, "
        "funding priority alignment, pursuit recommendation tier, pursuit effort estimate, and draft "
        "recommendation narrative constraints.",
    ),
    (
        "pipeline kanban handoff",
        "Uses pursuit recommendation tier, deadline feasibility, pursuit effort estimate, staff capacity fit, "
        "and human override reason for future column definitions without live workflow execution.",
    ),
    (
        "deadline calendar preview",
        "Uses deadline feasibility, NOFO summary confidence, reporting burden risk, and source confidence "
        "for deterministic demo calendar narratives.",
    ),
    (
        "SF-424 preview readiness",
        "Uses SF-424 preview readiness, authorized representative readiness, required attachment readiness, "
        "and eligibility preview result for checklist-style readiness panels.",
    ),
    (
        "requirement checklist preview",
        "Uses required attachment readiness, reporting burden risk, match and cost-share risk, mission fit "
        "score, and eligibility preview result for seeded checklist rows.",
    ),
    (
        "human review and override workflow",
        "Uses human override reason, eligibility confidence, eligibility preview result, pursuit "
        "recommendation tier, and draft recommendation narrative constraints for gated review paths.",
    ),
    (
        "source provenance display",
        "Uses source confidence, NOFO summary confidence, pursuit recommendation tier, and reporting burden "
        "risk to surface provenance beside preview outputs.",
    ),
    (
        "sovereignty trust explainer",
        "Uses tribal relevance score, draft recommendation narrative constraints, mission fit score, human "
        "override reason, and eligibility confidence to keep sovereignty-respecting explanations visible.",
    ),
)

_RECOMMENDATION_PREVIEW_TIERS: tuple[tuple[str, str], ...] = (
    (
        "Strong pursue preview",
        "Demo-only tier for well-supported seeded factors; this is not a final pursuit decision and is not a "
        "final eligibility determination.",
    ),
    (
        "Pursue preview",
        "Demo-only tier for generally favorable seeded rollups; this is not a final pursuit decision and is "
        "not a final eligibility determination.",
    ),
    (
        "Pursue with conditions preview",
        "Demo-only tier when seeded risks require explicit conditions; this is not a final pursuit decision "
        "and is not a final eligibility determination.",
    ),
    (
        "Needs human review",
        "Demo-only tier when ambiguity or low confidence requires reviewer routing; this is not a final "
        "pursuit decision and is not a final eligibility determination.",
    ),
    (
        "Hold for clarification",
        "Demo-only tier when seeded data gaps block confident previews; this is not a final pursuit decision "
        "and is not a final eligibility determination.",
    ),
    (
        "Do not pursue preview",
        "Demo-only advisory tier that must not block users from reviewing the opportunity; this is not a "
        "final pursuit decision and is not a final eligibility determination.",
    ),
)

_DRAFT_NARRATIVE_CONSTRAINTS: tuple[str, ...] = (
    "Narrative must explain factors, not invent facts.",
    "Narrative must cite seeded or demo-safe source fields only.",
    "Narrative must distinguish eligibility confidence from eligibility determination.",
    "Narrative must avoid culturally generic or pan-Indian language.",
    "Narrative must remain editable by the user.",
    "Narrative must be human-reviewed before any use outside demo.",
)

_HUMAN_REVIEW_GATES: tuple[str, ...] = (
    "Recommendation preview cannot be treated as final without human review.",
    "Do-not-pursue preview cannot block a user from reviewing the opportunity.",
    "Ambiguous eligibility must always route to human review.",
    "Low source confidence must be visible beside recommendation output.",
    "Draft recommendation narrative must be editable.",
    "Human override reason must be preserved in future runtime design.",
)

_SOVEREIGNTY_AND_TRUST: tuple[str, ...] = (
    "No customer data required for seeded recommendation demos.",
    "No customer data leaves the product during seeded demos.",
    "No model training on customer data without explicit written consent.",
    "Recommendation previews never override human judgment.",
    "Future runtime recommendation logic must be auditable and explainable.",
    "Recommendation rationale must be visible to the user.",
)

_SPRINT122_DOES_NOT_BUILD: tuple[str, ...] = (
    "No real opportunity scoring.",
    "No final pursuit recommendation.",
    "No final eligibility determination.",
    "No live Grants.gov ingestion.",
    "No Grants.gov API call.",
    "No SAM.gov integration.",
    "No agency scraping.",
    "No real NOFO parsing.",
    "No LLM recommendation generation.",
    "No database migration.",
    "No frontend UI.",
    "No runtime recommendation engine.",
    "No production pursuit engine changes.",
)

_M0_EXIT_CRITERIA: tuple[str, ...] = (
    "All eighteen recommendation factor groups are defined with purposes and acceptance criteria.",
    "M0 recommendation preview foundations cover pursuit preview, draft summary, rollup, displays, risks, "
    "human review, and pipeline handoff readiness.",
    "Recommendation preview tiers each restate non-final pursuit and non-final eligibility posture.",
    "Human review gates, sovereignty requirements, narrative constraints, and explicit exclusions are "
    "documented.",
    "Risks and mitigations address authority, confidence confusion, hallucination, language, provenance, "
    "suppression, fixture confusion, and sovereignty.",
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "Recommendation preview appears too authoritative",
        "Watermark tiers as preview-only, repeat non-final language, and show factor citations from seeds.",
    ),
    (
        "Eligibility confidence is confused with eligibility determination",
        "Pair confidence with explicit determination disclaimers and human review gates in all scripts.",
    ),
    (
        "Generated narrative invents facts",
        "Bind narratives to seeded fields only, block strong tiers on missing citations, forbid LLM output.",
    ),
    (
        "Pan-Indian or culturally generic language slips into recommendation narrative",
        "Enforce narrative constraints, reviewer checklists, and sovereignty trust explainer tie-ins.",
    ),
    (
        "Source confidence is hidden",
        "Require low-confidence warnings beside recommendation output and provenance panels.",
    ),
    (
        "Deadline or capacity risk is understated",
        "Surface capacity and deadline risk displays with visible risk bands and needs-review tiers.",
    ),
    (
        "Do-not-pursue tier suppresses human review",
        "Gate language mandates users can still open opportunities and overrides preserve audit trails.",
    ),
    (
        "Seeded recommendation is confused with production recommendation",
        "Document zero actual scoring counts, preview-only flags, and explicit Sprint 122 exclusions.",
    ),
    (
        "Recommendation language undermines tribal sovereignty or human judgment",
        "Center sovereignty trust requirements, tribal relevance scores, and non-override clauses for humans.",
    ),
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


def _tier_payloads() -> list[dict[str, str]]:
    return [{"tier_name": n, "tier_description": d} for n, d in _RECOMMENDATION_PREVIEW_TIERS]


def _risk_payloads() -> list[dict[str, str]]:
    return [{"risk": r, "mitigation": m} for r, m in _RISK_MITIGATIONS]


def build_active_source_activation_m0_opportunity_scoring_draft_recommendation_planning_packet() -> (
    dict[str, Any]
):
    """Return the Sprint 122 M0 recommendation planning packet (deterministic, no side effects)."""
    proof = {
        "sprint_122_m0_opportunity_scoring_draft_recommendation_planning_packet_is_stateless": True,
        "sprint_122_m0_opportunity_scoring_draft_recommendation_planning_packet_is_side_effect_free": True,
        "sprint_122_m0_opportunity_scoring_draft_recommendation_planning_packet_is_preview_only": True,
        "sprint_122_m0_opportunity_scoring_draft_recommendation_planning_packet_performs_no_runtime_work": True,
        "sprint_122_m0_opportunity_scoring_draft_recommendation_planning_packet_emits_operator_planning_only": True,
    }
    mapping_payload = [
        {"m0_surface_area": a, "recommendation_factor_use": u} for a, u in _RECOMMENDATION_PREVIEW_TO_M0_FEATURES
    ]
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 122,
        "packet_name": "NativeForge M0 Opportunity Scoring and Draft Recommendation Planning Packet",
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_define_recommendation_preview_scope": True,
        "may_define_demo_safe_recommendation_factors": True,
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
        "actual_eligibility_adjudications": 0,
        "actual_submission_recommendations": 0,
        "actual_draft_generations": 0,
        "m0_recommendation_preview_foundations": list(M0_RECOMMENDATION_PREVIEW_FOUNDATIONS),
        "recommendation_factor_groups": _field_group_payloads(),
        "recommendation_preview_to_m0_feature_mapping": mapping_payload,
        "recommendation_preview_tiers": _tier_payloads(),
        "draft_recommendation_narrative_constraints": list(_DRAFT_NARRATIVE_CONSTRAINTS),
        "human_review_gates": list(_HUMAN_REVIEW_GATES),
        "sovereignty_and_trust_requirements": list(_SOVEREIGNTY_AND_TRUST),
        "sprint_122_does_not_build": list(_SPRINT122_DOES_NOT_BUILD),
        "m0_recommendation_planning_exit_criteria": list(_M0_EXIT_CRITERIA),
        "risks_and_mitigations": _risk_payloads(),
        "sprint_122_m0_opportunity_scoring_draft_recommendation_planning_packet_proof": proof,
    }
    return _json_safe(out)


def _ordered_factor_groups(pkt: dict[str, Any]) -> list[dict[str, Any]]:
    raw = pkt.get("recommendation_factor_groups")
    if isinstance(raw, list):
        groups = [g for g in raw if isinstance(g, dict)]
        groups.sort(key=lambda g: g.get("priority") if isinstance(g.get("priority"), int) else 0)
        return groups
    return _field_group_payloads()


def render_active_source_activation_m0_opportunity_scoring_draft_recommendation_planning_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render the operator-facing markdown packet (deterministic; uses ``packet`` when provided)."""
    pkt = packet if isinstance(packet, dict) else (
        build_active_source_activation_m0_opportunity_scoring_draft_recommendation_planning_packet()
    )
    groups = _ordered_factor_groups(pkt)
    lines: list[str] = [
        "# NativeForge M0 Opportunity Scoring and Draft Recommendation Planning Packet v1",
        "",
        "## 1. Purpose",
        "",
        "This packet defines the M0 planning layer for demo-safe opportunity scoring rollup and draft pursuit "
        "recommendation previews. It is preview-only documentation and structured planning output for operators "
        "and engineers; it does not perform runtime scoring, production recommendations, live eligibility "
        "adjudication, AI drafting, Grants.gov or SAM.gov calls, agency scraping, real NOFO parsing, database "
        "migrations, frontend UI, or runtime recommendation engines.",
        "",
        "## 2. Why This Comes After NOFO Summary Preview",
        "",
        "Sprints 118 through 121 defined organizational entity profile context, seeded opportunity interfaces, "
        "tribal eligibility scoring preview, mission fit preview, and NOFO summary preview. Sprint 122 defines "
        "how those planning layers roll up into a pursuit recommendation preview that remains demo-safe and "
        "non-final.",
        "",
        "## 3. M0 Recommendation Preview Objective",
        "",
        "Deliver a demo-safe recommendation preview that helps a buyer understand why an opportunity may be "
        "worth pursuing using deterministic seeded signals only, without claiming final eligibility, final "
        "scoring, or final grant strategy.",
        "",
        "## 4. Demo-Safe Recommendation Rules",
        "",
        "M0 recommendation previews require seeded or demo-safe profile data, seeded or demo-safe opportunity "
        "records, and seeded or demo-safe NOFO summary text only. Operators must not call live Grants.gov, "
        "SAM.gov, agency scrapers, production customer datasets, LLM recommendation pipelines, or runtime "
        "scoring engines while presenting this planning posture.",
        "",
        "Restrictions restated: no live Grants.gov calls; no SAM.gov calls; no agency scraping; no real NOFO "
        "parsing; no real customer data; no LLM-generated recommendation; no final submission recommendation.",
        "",
        "## 5. Required Recommendation Factor Groups",
        "",
        "Eighteen factor groups structure recommendation previews:",
        "",
    ]
    for g in groups:
        if not isinstance(g, dict):
            continue
        name = g.get("name")
        purpose = g.get("purpose")
        if isinstance(name, str) and isinstance(purpose, str):
            lines.append(f"- **{name}**: {purpose}")
    lines.extend(["", "## 6. Factor-Level Acceptance Criteria", ""])
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
    lines.extend(["", "## 7. Recommendation Preview to M0 Feature Mapping", ""])
    mapping = pkt.get("recommendation_preview_to_m0_feature_mapping")
    if not isinstance(mapping, list):
        mapping = [
            {"m0_surface_area": a, "recommendation_factor_use": u}
            for a, u in _RECOMMENDATION_PREVIEW_TO_M0_FEATURES
        ]
    for row in mapping:
        if not isinstance(row, dict):
            continue
        area = row.get("m0_surface_area")
        use = row.get("recommendation_factor_use")
        if isinstance(area, str) and isinstance(use, str):
            lines.append(f"- **{area}**: {use}")
    lines.extend(["", "## 8. Recommendation Preview Tiers", "", "Demo-safe tiers (each advisory only):", ""])
    tiers = pkt.get("recommendation_preview_tiers") or _tier_payloads()
    for row in tiers:
        if not isinstance(row, dict):
            continue
        tn = row.get("tier_name")
        td = row.get("tier_description")
        if isinstance(tn, str) and isinstance(td, str):
            lines.append(f"- **{tn}**: {td}")
    lines.extend(
        [
            "",
            "Every tier above is not a final pursuit decision and not a final eligibility determination.",
            "",
            "## 9. Draft Recommendation Narrative Constraints",
            "",
        ]
    )
    for c in pkt.get("draft_recommendation_narrative_constraints") or list(_DRAFT_NARRATIVE_CONSTRAINTS):
        if isinstance(c, str) and c.strip():
            lines.append(f"- {c}")
    lines.extend(["", "## 10. Human Review Gates", "", "Mandatory gates:", ""])
    for gate in pkt.get("human_review_gates") or list(_HUMAN_REVIEW_GATES):
        if isinstance(gate, str) and gate.strip():
            lines.append(f"- {gate}")
    lines.extend(["", "## 11. Sovereignty and Trust Requirements", ""])
    for req in pkt.get("sovereignty_and_trust_requirements") or list(_SOVEREIGNTY_AND_TRUST):
        if isinstance(req, str) and req.strip():
            lines.append(f"- {req}")
    lines.extend(["", "## 12. What Sprint 122 Does Not Build", "", "Sprint 122 explicitly does not build:", ""])
    for item in pkt.get("sprint_122_does_not_build") or list(_SPRINT122_DOES_NOT_BUILD):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 13. M0 Exit Criteria for Recommendation Planning",
            "",
        ]
    )
    for c in pkt.get("m0_recommendation_planning_exit_criteria") or list(_M0_EXIT_CRITERIA):
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
            "## 15. Sprint 123 Recommended Next Step",
            "",
            "Sprint 123 should deliver the M0 Pursuit Pipeline Kanban and Deadline Tracking Planning Packet, still "
            "preview-only and demo-safe unless the operator explicitly authorizes runtime work.",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
