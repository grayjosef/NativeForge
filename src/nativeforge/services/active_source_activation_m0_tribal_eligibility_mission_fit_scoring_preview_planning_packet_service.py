"""Sprint 120: M0 tribal eligibility tagging and mission fit scoring preview planning packet (preview-only).

Deterministic operator packet for demo-safe scoring preview scope, factor groups, guardrails, and acceptance
criteria. Does not score real opportunities, call Grants.gov, SAM.gov, agency sites, LLMs, or production runtimes.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = (
    "nf_active_source_activation_m0_tribal_eligibility_mission_fit_scoring_preview_planning_packet_v1"
)
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

M0_SCORING_PREVIEW_FOUNDATIONS: tuple[str, ...] = (
    "Tribal eligibility tagging preview",
    "Entity type compatibility preview",
    "Native-serving organization relevance preview",
    "Mission fit scoring preview",
    "Funding priority alignment preview",
    "Deadline and capacity fit preview",
    "Reporting burden preview",
    "Match and cost-share risk preview",
    "Pursuit recommendation preview",
    "Human review and override workflow",
)

_FIELD_GROUP_ROWS: tuple[tuple[str, str, tuple[str, str]], ...] = (
    (
        "Entity type match",
        "Compares seeded entity classifications to seeded applicant-type and entity rules without legal findings.",
        (
            "Every preview labels entity type signals as fixture-derived, not adjudicated.",
            "Mismatch paths surface as advisory flags with human review routing, not automatic disqualification.",
        ),
    ),
    (
        "Federally recognized tribe eligibility",
        "Previews whether seeded program rules mention federally recognized tribes using demo text only.",
        (
            "Rules cite explainable seeded snippets, never live regulatory interpretation.",
            "Ambiguous mentions always increment eligibility ambiguity and route to human review.",
        ),
    ),
    (
        "Tribal organization eligibility",
        "Covers tribal organization and related corporate structures in seeded eligibility language.",
        (
            "Distinguishes tribal government versus tribal organization fixtures with explicit labels.",
            "No assumption that one eligibility phrase covers all tribal organizational forms.",
        ),
    ),
    (
        "Alaska Native entity eligibility",
        "Surfaces Alaska Native Corporation and village fixture paths referenced in seeded NOFO-style text.",
        (
            "Uses dedicated fixture tags for ANCSA and village contexts when present in seeds.",
            "Missing Alaska Native coverage in seeds is flagged as planning gap, not silent pass.",
        ),
    ),
    (
        "Native Hawaiian organization eligibility",
        "Previews Native Hawaiian organization eligibility cues from seeded narratives and taxonomy tags.",
        (
            "Requires explicit fixture representation; absence triggers underrepresentation warnings in demos.",
            "Preview language names Native Hawaiian pathways alongside other Native entity types.",
        ),
    ),
    (
        "Native nonprofit eligibility",
        "Evaluates Native nonprofit and Native-serving nonprofit fixture signals against seeded opportunity rules.",
        (
            "Nonprofit preview scores never collapse tribal government and Native nonprofit requirements.",
            "Seeded nonprofit missions must map to visible rationale strings for operator walkthroughs.",
        ),
    ),
    (
        "Tribal college eligibility",
        "Checks seeded references to tribal colleges and universities against fixture eligibility tables.",
        (
            "Tribal college fixtures include accreditation placeholders without implying real-time verification.",
            "Conflicts between TCU rules and other entity paths are preview-only and reviewer-led.",
        ),
    ),
    (
        "Mission priority alignment",
        "Scores overlap between seeded organizational mission themes and seeded program mission taxonomies.",
        (
            "Alignment scores are bounded demo numerics with plain-language rationale tied to seed fields.",
            "Low alignment cannot auto-hide an opportunity from the reviewer queue.",
        ),
    ),
    (
        "Geographic service area alignment",
        "Compares seeded service geographies to seeded opportunity geography fields using deterministic rules.",
        (
            "Partial overlaps produce conditional tiers, not silent strong fits.",
            "Unknown geography in seeds blocks strong preview fit until reviewers acknowledge gaps.",
        ),
    ),
    (
        "Funding amount fit",
        "Relates seeded award ranges to seeded organizational funding appetite without financial advice.",
        (
            "All currency values are labeled as demo fixtures with no banking or wire data.",
            "Out-of-range amounts downgrade tiers and cite the seeded numbers used in the comparison.",
        ),
    ),
    (
        "Deadline feasibility",
        "Uses seeded deadlines and seeded staff capacity signals to preview schedule risk only.",
        (
            "Deadlines missing time zones cannot produce pursuit-ready strong tiers.",
            "Feasibility outputs reference deterministic date math on fixtures, not live calendars.",
        ),
    ),
    (
        "Staff capacity fit",
        "Combines seeded FTE placeholders and workload tags to preview capacity strain without HR data.",
        (
            "Capacity inputs are synthetic counts supplied only for demo narratives.",
            "Capacity conflicts always pair with human review language in the preview tier text.",
        ),
    ),
    (
        "Match and cost-share risk",
        "Surfaces seeded match percentages and waiver flags as burden and liquidity preview only.",
        (
            "Risk bands are fixture-defined and never trigger automated pursuit abandonment.",
            "Match assumptions list override hooks for reviewers in operator scripts.",
        ),
    ),
    (
        "Reporting burden",
        "Uses seeded reporting cadence and indicator counts to preview administrative load.",
        (
            "Burden scores are illustrative integers with explicit demo labeling.",
            "High burden routes to conditional tiers or needs human review, not hidden disqualification.",
        ),
    ),
    (
        "Source confidence",
        "Propagates seeded provenance and fixture version metadata into confidence labels beside scores.",
        (
            "Low source confidence caps preview strength and surfaces warnings adjacent to every score.",
            "Confidence never implies live freshness or external validation.",
        ),
    ),
    (
        "Eligibility ambiguity",
        "Counts conflicting or incomplete seeded eligibility snippets to force reviewer routing.",
        (
            "Any unresolved conflict sets ambiguity above zero and blocks strong preview fit.",
            "Ambiguity metrics are deterministic tallies over fixture text, not NLP judgments.",
        ),
    ),
    (
        "Human override reason",
        "Reserves structured reason codes for reviewers to document why preview scores were superseded.",
        (
            "Demo fixtures include sample override reasons with non-production watermarking.",
            "Overrides are advisory in M0 but specify storage expectations for future runtime design.",
        ),
    ),
)

_SCORING_PREVIEW_TO_M0_FEATURES: tuple[tuple[str, str], ...] = (
    (
        "Tribal eligibility tagging preview",
        "Uses entity type match, federally recognized tribe eligibility, tribal organization eligibility, "
        "Alaska Native entity eligibility, Native Hawaiian organization eligibility, Native nonprofit eligibility, "
        "tribal college eligibility, eligibility ambiguity, and source confidence.",
    ),
    (
        "Mission fit scoring preview",
        "Uses mission priority alignment, geographic service area alignment, funding amount fit, and source "
        "confidence.",
    ),
    (
        "Pursuit recommendation preview",
        "Combines mission priority alignment, funding amount fit, deadline feasibility, staff capacity fit, "
        "match and cost-share risk, reporting burden, eligibility ambiguity, source confidence, and human override "
        "reason.",
    ),
    (
        "Deadline calendar preview",
        "Uses deadline feasibility with explicit time zone or unknown placeholders from seeded timelines.",
    ),
    (
        "Requirement checklist preview",
        "Uses reporting burden, match and cost-share risk, entity type match, and eligibility ambiguity to stage "
        "checklist items.",
    ),
    (
        "SF-424 preview readiness",
        "Uses entity type match, federally recognized tribe eligibility, tribal organization eligibility, Alaska "
        "Native entity eligibility, Native Hawaiian organization eligibility, Native nonprofit eligibility, tribal "
        "college eligibility, and reporting burden for form field awareness only.",
    ),
    (
        "Human review and override workflow",
        "Uses human override reason, eligibility ambiguity, pursuit recommendation preview tiers, and all gates "
        "that block authoritative language.",
    ),
    (
        "Source provenance display",
        "Uses source confidence fields and fixture provenance metadata shown beside every scoring output.",
    ),
)

_HUMAN_REVIEW_GATES: tuple[str, ...] = (
    "Eligibility preview cannot be treated as confirmed without human review.",
    "Disqualification preview cannot block a user from reviewing the opportunity.",
    "Pursuit recommendation must be reviewable and overrideable.",
    "Ambiguous eligibility must always route to human review.",
    "Source confidence must be visible beside scoring output.",
    "Human override reason must be stored in future runtime design.",
)

_SOVEREIGNTY_AND_TRUST: tuple[str, ...] = (
    "No customer data required for seeded scoring demos.",
    "No customer data leaves the product during seeded demos.",
    "No model training on customer data without explicit written consent.",
    "Recommendation previews never override human judgment.",
    "Future runtime scoring must be auditable and explainable.",
    "Scoring rationale must be visible to the user.",
)

_SPRINT120_DOES_NOT_BUILD: tuple[str, ...] = (
    "No real eligibility scoring.",
    "No final eligibility determination.",
    "No live Grants.gov ingestion.",
    "No Grants.gov API call.",
    "No SAM.gov integration.",
    "No agency scraping.",
    "No real NOFO parsing.",
    "No LLM scoring.",
    "No database migration.",
    "No frontend UI.",
    "No runtime scoring engine.",
    "No production recommendation engine.",
)

_RECOMMENDATION_PREVIEW_TIERS: tuple[tuple[str, str], ...] = (
    (
        "Strong preview fit",
        "High alignment across mission, eligibility clarity, capacity, and source confidence on seeded data only; "
        "this is not a final eligibility determination.",
    ),
    (
        "Preview fit",
        "Balanced seeded signals with minor gaps; suitable for guided demos with reviewer narration; "
        "this is not a final eligibility determination.",
    ),
    (
        "Preview fit with conditions",
        "Acceptable seeded alignment when documented conditions and mitigations are acknowledged in demo scripts; "
        "this is not a final eligibility determination.",
    ),
    (
        "Needs human review",
        "Ambiguity, conflicts, or low source confidence require reviewer decisions before any pursuit narrative; "
        "this is not a final eligibility determination.",
    ),
    (
        "Preview do not pursue",
        "Seeded signals suggest poor fit for operator storytelling, yet the user may still open and review the "
        "opportunity; this is not a final eligibility determination.",
    ),
    (
        "Preview disqualified",
        "Seeded rules indicate disqualification for demo purposes only; users must retain access to read the "
        "opportunity; this is not a final eligibility determination.",
    ),
)

_M0_EXIT_CRITERIA: tuple[str, ...] = (
    "All seventeen scoring factor groups are defined with purposes, demo-safe boundaries, and acceptance criteria.",
    "M0 scoring preview foundations cover tribal eligibility, mission fit, burden, capacity, pursuit, and review.",
    "Scoring preview to M0 feature mapping ties factors to previews, calendars, checklists, SF-424 awareness, "
    "provenance, and review.",
    "Recommendation preview tiers, human review gates, sovereignty requirements, and explicit exclusions are written.",
    "Risks and mitigations address authority, ambiguity, representation, rationale visibility, and seeded confusion.",
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "Scoring preview appears too authoritative",
        "Use advisory tier names, repeat non-final eligibility language, and pair scores with provenance panels.",
    ),
    (
        "Eligibility ambiguity is hidden",
        "Surface eligibility ambiguity counts, block strong tiers on conflicts, and force human review routing.",
    ),
    (
        "Entity types are over-simplified",
        "Maintain distinct fixture paths for tribal governments, tribal organizations, ANCs, NH orgs, and nonprofits.",
    ),
    (
        "Native nonprofits or Native Hawaiian organizations are underrepresented",
        "Require explicit fixture coverage, demo warnings when seeds omit pathways, and operator test scripts.",
    ),
    (
        "Federally recognized tribe assumptions are hardcoded",
        "Document configurable seed tables, avoid single default narratives, and log assumptions in rationale text.",
    ),
    (
        "Scoring rationale is not visible",
        "Bind every score to seeded field citations and show rationale strings beside outputs in specifications.",
    ),
    (
        "Low-confidence source data produces false confidence",
        "Cap tier strength from source confidence, show warnings adjacent to scores, and default to review tiers.",
    ),
    (
        "Recommendation language undermines human judgment",
        "Ban imperative pursuit commands, require override hooks, and state previews never replace human decisions.",
    ),
    (
        "Seeded scoring is confused with production scoring",
        "Label artifacts as Sprint 120 preview planning, watermark demos, and exclude runtime engines explicitly.",
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


def _risk_payloads() -> list[dict[str, str]]:
    return [{"risk": r, "mitigation": m} for r, m in _RISK_MITIGATIONS]


def build_active_source_activation_m0_tribal_eligibility_mission_fit_scoring_preview_planning_packet() -> (
    dict[str, Any]
):
    """Return the Sprint 120 M0 scoring preview planning packet (deterministic, no side effects)."""
    proof = {
        "sprint_120_m0_scoring_preview_planning_packet_is_stateless": True,
        "sprint_120_m0_scoring_preview_planning_packet_is_side_effect_free": True,
        "sprint_120_m0_scoring_preview_planning_packet_is_preview_only": True,
        "sprint_120_m0_scoring_preview_planning_packet_performs_no_runtime_work": True,
        "sprint_120_m0_scoring_preview_planning_packet_emits_operator_planning_only": True,
    }
    mapping_payload = [
        {"m0_feature": t, "scoring_factor_use": d} for t, d in _SCORING_PREVIEW_TO_M0_FEATURES
    ]
    tier_payload = [{"tier": t, "definition": d} for t, d in _RECOMMENDATION_PREVIEW_TIERS]
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 120,
        "packet_name": (
            "NativeForge M0 Tribal Eligibility Tagging and Mission Fit Scoring Preview Planning Packet"
        ),
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_define_scoring_preview_scope": True,
        "may_define_demo_safe_scoring_factors": True,
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
        "m0_scoring_preview_foundations": list(M0_SCORING_PREVIEW_FOUNDATIONS),
        "scoring_factor_groups": _field_group_payloads(),
        "scoring_preview_to_m0_feature_mapping": mapping_payload,
        "recommendation_preview_tiers": tier_payload,
        "human_review_gates": list(_HUMAN_REVIEW_GATES),
        "sovereignty_and_trust_requirements": list(_SOVEREIGNTY_AND_TRUST),
        "sprint_120_does_not_build": list(_SPRINT120_DOES_NOT_BUILD),
        "m0_scoring_preview_planning_exit_criteria": list(_M0_EXIT_CRITERIA),
        "risks_and_mitigations": _risk_payloads(),
        "sprint_120_m0_scoring_preview_planning_packet_proof": proof,
    }
    return _json_safe(out)


def _ordered_factor_groups(pkt: dict[str, Any]) -> list[dict[str, Any]]:
    raw = pkt.get("scoring_factor_groups")
    if isinstance(raw, list):
        groups = [g for g in raw if isinstance(g, dict)]
        groups.sort(key=lambda g: g.get("priority") if isinstance(g.get("priority"), int) else 0)
        return groups
    return _field_group_payloads()


def render_active_source_activation_m0_tribal_eligibility_mission_fit_scoring_preview_planning_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render the operator-facing markdown packet (deterministic; uses ``packet`` when provided)."""
    pkt = packet if isinstance(packet, dict) else (
        build_active_source_activation_m0_tribal_eligibility_mission_fit_scoring_preview_planning_packet()
    )
    groups = _ordered_factor_groups(pkt)
    lines: list[str] = [
        "# NativeForge M0 Tribal Eligibility Tagging and Mission Fit Scoring Preview Planning Packet v1",
        "",
        "## 1. Purpose",
        "",
        "This packet defines the M0 planning layer for demo-safe tribal eligibility tagging and mission fit scoring "
        "previews. It is preview-only documentation and structured planning output for operators and engineers; it "
        "does not execute workflows, activate sources, adjudicate eligibility, call external systems, or run "
        "production scoring engines.",
        "",
        "## 2. Why This Comes After Seeded Opportunity Planning",
        "",
        "Sprint 118 defined the organizational entity profile context and Sprint 119 defined seeded opportunity "
        "records, so Sprint 120 defines how those demo-safe records can be compared without live adjudication. The "
        "pairing keeps previews explainable, sovereignty-respecting, and bounded to fixtures.",
        "",
        "## 3. M0 Scoring Preview Objective",
        "",
        "Deliver a demo-safe scoring preview that helps a buyer understand eligibility signals, relevance, mission "
        "alignment, administrative burden, and pursuit worthiness without claiming final eligibility or replacing "
        "human judgment.",
        "",
        "## 4. Demo-Safe Scoring Rules",
        "",
        "M0 scoring previews require seeded or demo-safe profile data and seeded or demo-safe opportunity records "
        "only. Operators must not call Grants.gov, SAM.gov, agency scrapers, production datasets, LLM eligibility "
        "pipelines, or real NOFO parsers while presenting this planning posture.",
        "",
        "Restrictions restated: no live Grants.gov ingestion; no Grants.gov API call; no SAM.gov integration; no "
        "agency scraping; no real NOFO parsing; no real customer data; no LLM-generated eligibility conclusions; no "
        "final eligibility determinations.",
        "",
        "## 5. Required Scoring Factor Groups",
        "",
        "Seventeen factor groups structure scoring previews:",
        "",
    ]
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
            "## 6. Factor-Level Acceptance Criteria",
            "",
        ]
    )
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
    lines.extend(
        [
            "## 7. Scoring Preview to M0 Feature Mapping",
            "",
        ]
    )
    mapping = pkt.get("scoring_preview_to_m0_feature_mapping")
    if not isinstance(mapping, list):
        mapping = [
            {"m0_feature": t, "scoring_factor_use": d} for t, d in _SCORING_PREVIEW_TO_M0_FEATURES
        ]
    for row in mapping:
        if not isinstance(row, dict):
            continue
        feat = row.get("m0_feature")
        use = row.get("scoring_factor_use")
        if isinstance(feat, str) and isinstance(use, str):
            lines.append(f"- **{feat}**: {use}")
    lines.extend(
        [
            "",
            "## 8. Recommendation Preview Tiers",
            "",
            "Demo-safe preview tiers for pursuit storytelling. Each tier below explicitly states that it is not a "
            "final eligibility determination.",
            "",
        ]
    )
    tiers = pkt.get("recommendation_preview_tiers")
    if not isinstance(tiers, list):
        tiers = [{"tier": t, "definition": d} for t, d in _RECOMMENDATION_PREVIEW_TIERS]
    for row in tiers:
        if not isinstance(row, dict):
            continue
        tier = row.get("tier")
        definition = row.get("definition")
        if isinstance(tier, str) and isinstance(definition, str):
            lines.append(f"- **{tier}**: {definition}")
    lines.extend(
        [
            "",
            "## 9. Human Review Gates",
            "",
            "Mandatory gates:",
            "",
        ]
    )
    for gate in pkt.get("human_review_gates") or list(_HUMAN_REVIEW_GATES):
        if isinstance(gate, str) and gate.strip():
            lines.append(f"- {gate}")
    lines.extend(
        [
            "",
            "## 10. Sovereignty and Trust Requirements",
            "",
        ]
    )
    for req in pkt.get("sovereignty_and_trust_requirements") or list(_SOVEREIGNTY_AND_TRUST):
        if isinstance(req, str) and req.strip():
            lines.append(f"- {req}")
    lines.extend(
        [
            "",
            "## 11. What Sprint 120 Does Not Build",
            "",
            "Sprint 120 explicitly does not build:",
            "",
        ]
    )
    for item in pkt.get("sprint_120_does_not_build") or list(_SPRINT120_DOES_NOT_BUILD):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 12. M0 Exit Criteria for Scoring Preview Planning",
            "",
        ]
    )
    for c in pkt.get("m0_scoring_preview_planning_exit_criteria") or list(_M0_EXIT_CRITERIA):
        if isinstance(c, str) and c.strip():
            lines.append(f"- {c}")
    lines.extend(
        [
            "",
            "## 13. Risks and Mitigations",
            "",
        ]
    )
    for row in pkt.get("risks_and_mitigations") or _risk_payloads():
        if isinstance(row, dict):
            r = row.get("risk")
            m = row.get("mitigation")
            if isinstance(r, str) and isinstance(m, str):
                lines.append(f"- **Risk**: {r} — **Mitigation**: {m}")
    lines.extend(
        [
            "",
            "## 14. Sprint 121 Recommended Next Step",
            "",
            "Sprint 121 should deliver the M0 NOFO Plain-Language Summary Preview Planning Packet, still "
            "preview-only and demo-safe unless the operator explicitly authorizes runtime work.",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
