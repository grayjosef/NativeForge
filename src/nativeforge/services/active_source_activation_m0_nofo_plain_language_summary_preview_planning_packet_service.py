"""Sprint 121: M0 NOFO plain-language summary preview planning packet (preview-only).

Deterministic operator packet for demo-safe plain-language NOFO summary preview scope, field groups,
guardrails, and acceptance criteria. Does not parse real NOFOs, call Grants.gov, SAM.gov, agency sites,
LLMs, or production runtimes.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = (
    "nf_active_source_activation_m0_nofo_plain_language_summary_preview_planning_packet_v1"
)
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

M0_NOFO_SUMMARY_PREVIEW_FOUNDATIONS: tuple[str, ...] = (
    "Demo-safe NOFO summary generation",
    "Eligibility highlight preview",
    "Mission fit summary preview",
    "Key deadlines preview",
    "Funding priority preview",
    "Match capacity preview",
    "Reporting burden preview",
    "Human review and override workflow",
    "Source provenance display",
    "Future runtime-ready summary generation",
)

_FIELD_GROUP_ROWS: tuple[tuple[str, str, tuple[str, str]], ...] = (
    (
        "NOFO title",
        "Captures the seeded or fixture opportunity title shown in plain-language summary headers.",
        (
            "Title text is labeled as demo or seeded, never as live agency publication.",
            "Missing titles block summary publication tiers until operators supply fixture text.",
        ),
    ),
    (
        "Funding agency",
        "Names the agency or office associated with the seeded opportunity for operator narration.",
        (
            "Agency strings come from fixtures only with explicit non-production watermarking.",
            "Conflicting agency labels in seeds route to human review, not silent resolution.",
        ),
    ),
    (
        "Opportunity number",
        "Holds Grants.gov-style or internal opportunity identifiers for demo cross-references.",
        (
            "Identifiers are synthetic or copied from public demo corpora with no live validation.",
            "Duplicate numbers in fixtures increment ambiguity counters for reviewer routing.",
        ),
    ),
    (
        "Assistance listing/CFDA",
        "Surfaces assistance listing or CFDA placeholders tied to seeded program metadata.",
        (
            "CFDA fields are fixture-backed with no SAM.gov or live catalog verification.",
            "Unknown CFDA values downgrade summary confidence and surface provenance warnings.",
        ),
    ),
    (
        "Eligibility preview",
        "Summarizes seeded eligibility language as advisory highlights without legal findings.",
        (
            "Every eligibility highlight cites seeded snippets and states preview-only posture.",
            "Ambiguous eligibility always routes to human review with visible ambiguity flags.",
        ),
    ),
    (
        "Tribal relevance tags",
        "Applies deterministic fixture tags for tribal government, organization, ANC, NH org, and TCU paths.",
        (
            "Tags require explicit fixture coverage; absence triggers underrepresentation warnings.",
            "Tags never imply federally recognized status without reviewer-visible qualifiers.",
        ),
    ),
    (
        "Mission alignment tags",
        "Maps seeded organizational mission themes to seeded program mission taxonomies for demos.",
        (
            "Alignment language is illustrative with bounded demo numerics when scores appear.",
            "Low alignment cannot hide the opportunity from the reviewer queue or summaries.",
        ),
    ),
    (
        "Key deadlines",
        "Lists seeded due dates, letters of intent, and full application deadlines with placeholders.",
        (
            "Deadlines missing time zones cannot be labeled pursuit-ready in operator scripts.",
            "All date math is deterministic on fixtures, not live calendar integration.",
        ),
    ),
    (
        "Funding amounts",
        "Shows seeded award ranges and ceilings with explicit demo currency labeling.",
        (
            "Amounts are not financial advice and never include banking or wire instructions.",
            "Out-of-range relative to seeded appetite downgrades summary strength with rationale text.",
        ),
    ),
    (
        "Match requirements",
        "Describes seeded match percentages, waivers, and in-kind expectations as burden preview only.",
        (
            "Match language includes override hooks for reviewers in demo walkthroughs.",
            "Match assumptions never trigger automated pursuit abandonment in M0.",
        ),
    ),
    (
        "Reporting burden",
        "Previews administrative cadence and indicator counts from seeded reporting metadata.",
        (
            "Burden scores are illustrative integers with demo-only labeling.",
            "High burden pairs with human review language in summary footers.",
        ),
    ),
    (
        "Human review notes",
        "Reserves structured reviewer commentary slots adjacent to summary panels in specifications.",
        (
            "Notes are optional in fixtures but required before any authoritative language in scripts.",
            "Notes must persist in future runtime designs without mutating customer secrets in M0.",
        ),
    ),
    (
        "Demo-safe sample text",
        "Provides canned plain-language paragraphs for buyer demos with non-production watermarking.",
        (
            "Sample text never claims to summarize a live NOFO the operator has not authorized.",
            "Samples cite fixture provenance and forbid impersonation of agency counsel.",
        ),
    ),
    (
        "Preview generation notes",
        "Documents deterministic rules used to assemble the preview without LLM involvement.",
        (
            "Notes list ordering of fields and truncation rules for consistent artifacts.",
            "Notes state explicitly that no LLM generated the preview in M0.",
        ),
    ),
    (
        "Source provenance",
        "Propagates fixture version identifiers and seed lineage beside every summary block.",
        (
            "Low provenance confidence caps summary strength and shows warnings in markdown specs.",
            "Provenance never implies live freshness or external validation.",
        ),
    ),
    (
        "Field-level acceptance criteria",
        "Mirrors per-field checklist items operators use to certify demo readiness of summaries.",
        (
            "Criteria are machine-readable lists paired one-to-one with field groups.",
            "Failing any criterion blocks demo publication tiers until resolved in planning.",
        ),
    ),
    (
        "Human override reason",
        "Captures structured reason codes when reviewers supersede automated preview assembly.",
        (
            "Demo fixtures include sample override reasons with non-production watermarking.",
            "Overrides are advisory in M0 but specify storage expectations for future runtime design.",
        ),
    ),
)

_SUMMARY_PREVIEW_TO_M0_FEATURES: tuple[tuple[str, str], ...] = (
    (
        "Demo-safe NOFO summary generation",
        "Uses NOFO title, funding agency, opportunity number, demo-safe sample text, preview generation notes, "
        "and source provenance.",
    ),
    (
        "Eligibility highlight preview",
        "Uses eligibility preview, tribal relevance tags, field-level acceptance criteria, and human review notes.",
    ),
    (
        "Mission fit summary preview",
        "Uses mission alignment tags, funding amounts, field-level acceptance criteria, and source provenance.",
    ),
    (
        "Key deadlines preview",
        "Uses key deadlines, preview generation notes, and human review notes for schedule risk narration.",
    ),
    (
        "Funding priority preview",
        "Uses funding amounts, funding agency, mission alignment tags, and reporting burden.",
    ),
    (
        "Match capacity preview",
        "Uses match requirements, funding amounts, human review notes, and field-level acceptance criteria.",
    ),
    (
        "Reporting burden preview",
        "Uses reporting burden, match requirements, key deadlines, and demo-safe sample text.",
    ),
    (
        "Human review and override workflow",
        "Uses human review notes, human override reason, eligibility preview, and preview generation notes.",
    ),
    (
        "Source provenance display",
        "Uses source provenance, opportunity number, assistance listing/CFDA, and field-level acceptance criteria.",
    ),
    (
        "Future runtime-ready summary generation",
        "Uses all seventeen field groups to specify how runtime summaries would remain auditable and gated.",
    ),
)

_HUMAN_REVIEW_GATES: tuple[str, ...] = (
    "Plain-language summaries cannot be treated as legal or eligibility determinations without human review.",
    "Summary previews cannot hide conflicting seeded eligibility language from reviewers.",
    "Every summary block must remain overrideable with documented human override reasons.",
    "Low provenance or confidence must cap summary strength and show warnings beside outputs.",
    "Demo-safe sample text must be labeled and must not impersonate agency counsel.",
    "Ambiguous deadlines or funding figures must route to human review before strong demo claims.",
)

_SOVEREIGNTY_AND_TRUST: tuple[str, ...] = (
    "Summaries use seeded or demo-safe fixtures only until explicit runtime authorization.",
    "No customer data is required to render M0 summary preview planning artifacts.",
    "No customer data leaves the product during seeded summary demos.",
    "No model training on customer data without explicit written consent.",
    "Future runtime summaries must remain auditable, explainable, and sovereignty-respecting.",
    "Preview language must not erode tribal self-determination narratives in operator scripts.",
)

_SPRINT121_DOES_NOT_BUILD: tuple[str, ...] = (
    "No live NOFO parsing.",
    "No real plain-language text generation.",
    "No Grants.gov API call.",
    "No SAM.gov integration.",
    "No agency scraping.",
    "No LLM calls.",
    "No database migration.",
    "No frontend UI.",
    "No live workflow execution.",
    "No runtime summary engine.",
    "No production customer data access for summaries.",
)

_M0_EXIT_CRITERIA: tuple[str, ...] = (
    "All seventeen summary preview field groups are defined with purposes and acceptance criteria.",
    "M0 summary preview foundations cover summaries, highlights, deadlines, funding, match, burden, review, "
    "provenance, and future runtime posture.",
    "Summary preview to M0 feature mapping ties field groups to each foundation statement.",
    "Human review gates, sovereignty requirements, and explicit exclusions are documented.",
    "Risks and mitigations address authority, hallucination, provenance, representation, and fixture confusion.",
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "Summary reads as legal or final eligibility advice",
        "Repeat preview-only language, cite seeded snippets, and pair summaries with human review gates.",
    ),
    (
        "Plain-language text drifts from seeded sources",
        "Bind every paragraph to provenance metadata and block publication tiers on missing citations.",
    ),
    (
        "Tribal pathways are underrepresented in summaries",
        "Require tribal relevance tags, explicit fixture coverage, and operator warnings when seeds omit paths.",
    ),
    (
        "Deadlines or amounts are wrong due to fixture errors",
        "Show fixture version identifiers, cap confidence, and route conflicts to human review.",
    ),
    (
        "Operators confuse preview summaries with production outputs",
        "Watermark demos, ban live NOFO parsing in this sprint, and document zero actual generations.",
    ),
    (
        "LLM hallucination is assumed available",
        "State no LLM calls in M0, document deterministic assembly rules in preview generation notes.",
    ),
    (
        "Provenance is hidden from buyers",
        "Mandate provenance panels adjacent to summaries and include provenance in exit criteria.",
    ),
    (
        "Human overrides are untracked",
        "Require human override reason structures and storage expectations for future runtime design.",
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


def build_active_source_activation_m0_nofo_plain_language_summary_preview_planning_packet() -> dict[str, Any]:
    """Return the Sprint 121 M0 NOFO summary preview planning packet (deterministic, no side effects)."""
    proof = {
        "sprint_121_m0_nofo_summary_preview_planning_packet_is_stateless": True,
        "sprint_121_m0_nofo_summary_preview_planning_packet_is_side_effect_free": True,
        "sprint_121_m0_nofo_summary_preview_planning_packet_is_preview_only": True,
        "sprint_121_m0_nofo_summary_preview_planning_packet_performs_no_runtime_work": True,
        "sprint_121_m0_nofo_summary_preview_planning_packet_emits_operator_planning_only": True,
    }
    mapping_payload = [
        {"m0_feature": t, "summary_field_use": d} for t, d in _SUMMARY_PREVIEW_TO_M0_FEATURES
    ]
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 121,
        "packet_name": "NativeForge M0 NOFO Plain-Language Summary Preview Planning Packet",
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_define_demo_safe_summary_scope": True,
        "may_define_plain_language_mapping_rules": True,
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
        "m0_nofo_summary_preview_foundations": list(M0_NOFO_SUMMARY_PREVIEW_FOUNDATIONS),
        "summary_preview_field_groups": _field_group_payloads(),
        "summary_preview_to_m0_feature_mapping": mapping_payload,
        "human_review_gates": list(_HUMAN_REVIEW_GATES),
        "sovereignty_and_trust_requirements": list(_SOVEREIGNTY_AND_TRUST),
        "sprint_121_does_not_build": list(_SPRINT121_DOES_NOT_BUILD),
        "m0_nofo_summary_preview_planning_exit_criteria": list(_M0_EXIT_CRITERIA),
        "risks_and_mitigations": _risk_payloads(),
        "sprint_121_m0_nofo_summary_preview_planning_packet_proof": proof,
    }
    return _json_safe(out)


def _ordered_field_groups(pkt: dict[str, Any]) -> list[dict[str, Any]]:
    raw = pkt.get("summary_preview_field_groups")
    if isinstance(raw, list):
        groups = [g for g in raw if isinstance(g, dict)]
        groups.sort(key=lambda g: g.get("priority") if isinstance(g.get("priority"), int) else 0)
        return groups
    return _field_group_payloads()


def render_active_source_activation_m0_nofo_plain_language_summary_preview_planning_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render the operator-facing markdown packet (deterministic; uses ``packet`` when provided)."""
    pkt = packet if isinstance(packet, dict) else (
        build_active_source_activation_m0_nofo_plain_language_summary_preview_planning_packet()
    )
    groups = _ordered_field_groups(pkt)
    lines: list[str] = [
        "# NativeForge M0 NOFO Plain-Language Summary Preview Planning Packet v1",
        "",
        "## 1. Purpose",
        "",
        "This packet defines the M0 planning layer for demo-safe plain-language summaries of seeded or fixture "
        "NOFO-style opportunities. It is preview-only documentation and structured planning output for operators and "
        "engineers; it does not parse live NOFOs, execute workflows, activate sources, call Grants.gov or SAM.gov, "
        "scrape agencies, invoke LLMs, generate real summary text from customer data, or run production summary "
        "engines.",
        "",
        "## 2. Why This Comes After Tribal Eligibility Scoring",
        "",
        "Sprint 120 defined tribal eligibility tagging and mission fit scoring previews on seeded records. Sprint "
        "121 defines how plain-language summaries narrate those previews without introducing new adjudication or "
        "live parsing. Sequencing keeps eligibility signals, mission alignment, burden, and match context visible "
        "before buyers read summarized opportunity stories.",
        "",
        "## 3. M0 Summary Preview Objective",
        "",
        "Deliver a demo-safe NOFO summary preview that helps a buyer understand titles, agencies, eligibility "
        "highlights, mission fit, deadlines, funding posture, match expectations, and reporting burden using "
        "deterministic fixture text only, while reserving human review, override, and provenance for trust.",
        "",
        "## 4. Demo-Safe Summary Rules",
        "",
        "M0 summary previews require seeded or demo-safe opportunity records and deterministic assembly rules only. "
        "Operators must not parse live NOFOs, call Grants.gov, SAM.gov, agency scrapers, production datasets, or "
        "LLM summarization pipelines while presenting this planning posture.",
        "",
        "Restrictions restated: no live NOFO parsing; no real plain-language text generation from live sources; no "
        "Grants.gov API call; no SAM.gov integration; no agency scraping; no LLM calls; no database migration; no "
        "frontend UI; no live workflow execution.",
        "",
        "## 5. Required Field Groups",
        "",
        "Seventeen field groups structure summary previews:",
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
            "## 6. Field-Level Acceptance Criteria",
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
            "## 7. Summary Preview to M0 Feature Mapping",
            "",
        ]
    )
    mapping = pkt.get("summary_preview_to_m0_feature_mapping")
    if not isinstance(mapping, list):
        mapping = [
            {"m0_feature": t, "summary_field_use": d} for t, d in _SUMMARY_PREVIEW_TO_M0_FEATURES
        ]
    for row in mapping:
        if not isinstance(row, dict):
            continue
        feat = row.get("m0_feature")
        use = row.get("summary_field_use")
        if isinstance(feat, str) and isinstance(use, str):
            lines.append(f"- **{feat}**: {use}")
    lines.extend(
        [
            "",
            "## 8. Human Review Gates",
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
            "## 9. Sovereignty and Trust Requirements",
            "",
        ]
    )
    for req in pkt.get("sovereignty_and_trust_requirements") or list(_SOVEREIGNTY_AND_TRUST):
        if isinstance(req, str) and req.strip():
            lines.append(f"- {req}")
    lines.extend(
        [
            "",
            "## 10. What Sprint 121 Does Not Build",
            "",
            "Sprint 121 explicitly does not build:",
            "",
        ]
    )
    for item in pkt.get("sprint_121_does_not_build") or list(_SPRINT121_DOES_NOT_BUILD):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 11. M0 Exit Criteria",
            "",
        ]
    )
    for c in pkt.get("m0_nofo_summary_preview_planning_exit_criteria") or list(_M0_EXIT_CRITERIA):
        if isinstance(c, str) and c.strip():
            lines.append(f"- {c}")
    lines.extend(
        [
            "",
            "## 12. Risks and Mitigations",
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
            "## 13. Sprint 122 Recommended Next Step",
            "",
            "Sprint 122 should deliver the M0 Opportunity Scoring & Draft Recommendation Planning Packet, still "
            "preview-only and demo-safe unless the operator explicitly authorizes runtime work.",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
