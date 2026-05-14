"""Sprint 119: M0 Grants.gov seeded opportunity ingestion interface planning packet (preview-only).

Deterministic operator packet that defines the M0 planning layer for a demo-safe Grants.gov-style opportunity
interface using seeded data only. Does not call Grants.gov, SAM.gov, agency sites, LLMs, or production runtimes.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = (
    "nf_active_source_activation_m0_grants_gov_seeded_opportunity_ingestion_interface_planning_packet_v1"
)
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

M0_SEEDED_OPPORTUNITY_FOUNDATIONS: tuple[str, ...] = (
    "Demo-safe Grants.gov-style opportunity discovery",
    "Tribal eligibility tagging previews",
    "Mission fit scoring previews",
    "NOFO summary preview readiness",
    "Requirement extraction checklist preview readiness",
    "Pursuit pipeline handoff",
    "Deadline and status display",
    "Source provenance display",
    "Human review of eligibility and recommendation logic",
    "Future live ingestion readiness without activating live ingestion",
)

_FIELD_GROUP_ROWS: tuple[tuple[str, str, tuple[str, str]], ...] = (
    (
        "Opportunity identity",
        "Stable identifiers, opportunity numbers, titles, and synopsis text suitable for seeded fixtures.",
        (
            "Every seeded opportunity exposes a stable internal key and a human-readable title.",
            "Synopsis text is clearly labeled as demo-safe and never copied from live Grants.gov payloads.",
        ),
    ),
    (
        "Source metadata",
        "Catalog keys, fixture labels, and provenance stamps tying each row to its demo source basis.",
        (
            "Each record names the demo catalog or fixture pack that produced the row.",
            "Source metadata never implies a live connection to Grants.gov or agency systems.",
        ),
    ),
    (
        "Agency and sub-agency data",
        "Owning agency, sub-agency, office, and contact channel placeholders for operator walkthroughs.",
        (
            "Agency hierarchy fields support federal, pass-through, and tribal operator narratives.",
            "Contact placeholders are synthetic and marked non-authoritative in M0.",
        ),
    ),
    (
        "Assistance listing / CFDA data",
        "CFDA or assistance listing numbers and program titles for checklist previews only.",
        (
            "CFDA numbers are optional strings with explicit demo fixture provenance.",
            "Program titles remain editable and never imply automatic eligibility outcomes.",
        ),
    ),
    (
        "Eligibility data",
        "Structured eligibility snippets, applicant types, and geography hints for preview rules.",
        (
            "Eligibility snippets are advisory previews until human review completes.",
            "Applicant type enumerations include tribal government and Native nonprofit paths.",
        ),
    ),
    (
        "Tribal relevance tags",
        "Rules-based tags describing tribal relevance without asserting legal determinations.",
        (
            "Tags reference explainable inputs such as eligibility text and mission taxonomy.",
            "Tag sets remain overrideable by reviewers in demo scripts.",
        ),
    ),
    (
        "Funding amount data",
        "Award ceilings, floors, and narrative funding bands for preview math only.",
        (
            "Funding numbers are bounded demo inputs with non-production labeling.",
            "No wire instructions or banking data appear in M0 fixtures.",
        ),
    ),
    (
        "Deadline and timeline data",
        "Key dates, time zones, and status labels powering calendar previews and pursuit gates.",
        (
            "Deadlines store explicit time zone metadata or unknown placeholders when absent.",
            "Missing deadlines block pursuit-ready status per human review gates.",
        ),
    ),
    (
        "NOFO attachment metadata",
        "Attachment inventory, checksum placeholders, and download URLs that are synthetic only.",
        (
            "Attachment rows reference template filenames, not production binaries.",
            "URLs point to demo-safe static assets or are explicitly empty in fixtures.",
        ),
    ),
    (
        "Requirement preview metadata",
        "Checklist-ready requirement bullets derived from seeded text, not live parsers.",
        (
            "Requirement bullets are authored in fixtures and versioned for reviewers.",
            "No LLM extraction from real NOFOs occurs in this planning packet.",
        ),
    ),
    (
        "Match and cost-share metadata",
        "Match percentages, in-kind expectations, and waiver flags for workload previews.",
        (
            "Match assumptions are bounded demo values with reviewer override hooks.",
            "Cost-share rules never auto-submit applications in M0.",
        ),
    ),
    (
        "Reporting burden metadata",
        "Reporting cadence, indicator counts, and narrative burden hints for pursuit planning.",
        (
            "Reporting counts are illustrative and labeled as demo estimates.",
            "Burden metadata links to human review before any implementation sprint.",
        ),
    ),
    (
        "Mission fit taxonomy tags",
        "Program area tags, strategic themes, and alignment notes for scoring previews.",
        (
            "Taxonomy tags map to explainable scoring inputs with operator-visible rationale.",
            "Mission fit scores remain advisory and never finalize pursuit decisions alone.",
        ),
    ),
    (
        "Pursuit recommendation preview data",
        "Ranked recommendations, confidence bands, and rationale text for operator demos.",
        (
            "Recommendations are preview-only until reviewers acknowledge demo posture.",
            "Confidence bands are deterministic fixture values, not model outputs.",
        ),
    ),
    (
        "Human review and override metadata",
        "Reviewer identity placeholders, decision states, and override reasons for auditability.",
        (
            "Every recommendation records whether a human has reviewed or overridden it.",
            "Overrides require a documented reason string in demo fixtures.",
        ),
    ),
)

_SEEDED_OPPORTUNITY_TO_M0_FEATURES: tuple[tuple[str, str], ...] = (
    (
        "Tribal eligibility tagging preview",
        "Uses eligibility data, tribal relevance tags, and opportunity identity for rules-based previews.",
    ),
    (
        "Mission fit scoring preview",
        "Uses mission fit taxonomy tags, funding amount data, and agency metadata for explainable scores.",
    ),
    (
        "NOFO summary preview",
        "Uses opportunity identity, NOFO attachment metadata, and requirement preview metadata for summaries.",
    ),
    (
        "Requirement checklist preview",
        "Uses requirement preview metadata, match and cost-share metadata, and reporting burden metadata.",
    ),
    (
        "Deadline calendar preview",
        "Uses deadline and timeline data with explicit time zone handling or unknown placeholders.",
    ),
    (
        "Pursuit pipeline handoff",
        "Uses pursuit recommendation preview data, human review metadata, and funding amount signals.",
    ),
    (
        "Source provenance display",
        "Uses source metadata, agency data, and fixture_version or seeded_at fields on every record.",
    ),
    (
        "Human review and override workflow",
        "Uses human review and override metadata with eligibility and recommendation previews.",
    ),
)

_HUMAN_REVIEW_GATES: tuple[str, ...] = (
    "Eligibility preview cannot be treated as confirmed without human review.",
    "Pursuit recommendation must be reviewable and overrideable.",
    "Missing or ambiguous eligibility must be flagged.",
    "Missing deadline data must block pursuit-ready status.",
    "Seeded source provenance must be visible in every opportunity detail view.",
)

_SOURCE_PROVENANCE_AND_FRESHNESS: tuple[str, ...] = (
    "Every seeded record must identify its demo source basis.",
    "Every seeded record must include seeded_at or fixture_version metadata.",
    "Every displayed opportunity must clearly indicate demo-safe seeded data.",
    "Future live ingestion must preserve source URLs, timestamps, and amendment/version tracking.",
    "No live freshness monitoring occurs in M0 planning.",
)

_SOVEREIGNTY_AND_TRUST: tuple[str, ...] = (
    "No customer data required to view seeded opportunities.",
    "No customer data leaves the product during seeded demos.",
    "No model training on customer data without explicit written consent.",
    "Future live ingestion must preserve auditability.",
    "Opportunity recommendations must never override human judgment.",
)

_SPRINT119_DOES_NOT_BUILD: tuple[str, ...] = (
    "No live Grants.gov ingestion.",
    "No Grants.gov API call.",
    "No SAM.gov integration.",
    "No agency scraping.",
    "No real NOFO parsing.",
    "No LLM extraction.",
    "No database migration.",
    "No frontend UI.",
    "No runtime ingestion worker.",
    "No production source activation.",
)

_M0_EXIT_CRITERIA: tuple[str, ...] = (
    "All fifteen seeded opportunity field groups are defined with documented intent and demo-safe boundaries.",
    "Acceptance criteria exist for every field group and are reviewable by operators.",
    "Seeded opportunity to M0 feature mapping covers previews, deadlines, pursuit handoff, provenance, and review.",
    "Human review gates, source provenance rules, and sovereignty requirements are written for operator scripts.",
    "Risks and mitigations are recorded for demo confusion, provenance weakness, authority signals, tribal coverage, "
    "time zones, Grants.gov assumptions, non-federal sources, and premature live ingestion.",
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "Confusing seeded demo data with live ingestion",
        "Stamp fixtures, repeat demo-safe labeling in UI copy, and block pursuit-ready without reviewer ack.",
    ),
    (
        "Weak source provenance",
        "Require demo source basis, seeded_at or fixture_version, and visible provenance panels in specs.",
    ),
    (
        "Eligibility preview appearing too authoritative",
        "Use advisory language, human review gates, and explicit non-confirmation rules in operator scripts.",
    ),
    (
        "Missing tribal entity types",
        "Model tribal governments, Native nonprofits, and Native Hawaiian org paths with fixture test cases.",
    ),
    (
        "Deadlines without timezone clarity",
        "Require explicit IANA zones or unknown placeholders and block pursuit-ready when absent.",
    ),
    (
        "Hardcoded Grants.gov assumptions that do not generalize to agency-specific sources",
        "Keep schemas source-agnostic with extension hooks for agency-specific catalogs.",
    ),
    (
        "Underrepresenting non-federal and tribal-specific sources",
        "Document tribal-specific catalogs alongside federal seeds and test mixed-source demos.",
    ),
    (
        "Building live ingestion before validation",
        "Sequence preview-only planning packets through Sprint 120 before any runtime authorization.",
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


def build_active_source_activation_m0_grants_gov_seeded_opportunity_ingestion_interface_planning_packet() -> (
    dict[str, Any]
):
    """Return the Sprint 119 M0 seeded opportunity interface planning packet (deterministic, no side effects)."""
    proof = {
        "sprint_119_m0_seeded_opportunity_planning_packet_is_stateless": True,
        "sprint_119_m0_seeded_opportunity_planning_packet_is_side_effect_free": True,
        "sprint_119_m0_seeded_opportunity_planning_packet_is_preview_only": True,
        "sprint_119_m0_seeded_opportunity_planning_packet_performs_no_runtime_work": True,
        "sprint_119_m0_seeded_opportunity_planning_packet_emits_operator_planning_only": True,
    }
    mapping_payload = [{"m0_feature": t, "opportunity_field_use": d} for t, d in _SEEDED_OPPORTUNITY_TO_M0_FEATURES]
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 119,
        "packet_name": "NativeForge M0 Grants.gov Seeded Opportunity Ingestion Interface Planning Packet",
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_define_seeded_ingestion_scope": True,
        "may_define_demo_safe_opportunity_contract": True,
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
        "m0_seeded_opportunity_foundations": list(M0_SEEDED_OPPORTUNITY_FOUNDATIONS),
        "seeded_opportunity_field_groups": _field_group_payloads(),
        "seeded_opportunity_to_m0_feature_mapping": mapping_payload,
        "human_review_gates": list(_HUMAN_REVIEW_GATES),
        "source_provenance_and_freshness_requirements": list(_SOURCE_PROVENANCE_AND_FRESHNESS),
        "sovereignty_and_trust_requirements": list(_SOVEREIGNTY_AND_TRUST),
        "sprint_119_does_not_build": list(_SPRINT119_DOES_NOT_BUILD),
        "m0_seeded_opportunity_planning_exit_criteria": list(_M0_EXIT_CRITERIA),
        "risks_and_mitigations": _risk_payloads(),
        "sprint_119_m0_seeded_opportunity_planning_packet_proof": proof,
    }
    return _json_safe(out)


def _ordered_field_groups(pkt: dict[str, Any]) -> list[dict[str, Any]]:
    raw = pkt.get("seeded_opportunity_field_groups")
    if isinstance(raw, list):
        groups = [g for g in raw if isinstance(g, dict)]
        groups.sort(key=lambda g: g.get("priority") if isinstance(g.get("priority"), int) else 0)
        return groups
    return _field_group_payloads()


def render_active_source_activation_m0_grants_gov_seeded_opportunity_ingestion_interface_planning_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render the operator-facing markdown packet (deterministic; uses ``packet`` when provided)."""
    pkt = packet if isinstance(packet, dict) else (
        build_active_source_activation_m0_grants_gov_seeded_opportunity_ingestion_interface_planning_packet()
    )
    groups = _ordered_field_groups(pkt)
    lines: list[str] = [
        "# NativeForge M0 Grants.gov Seeded Opportunity Ingestion Interface Planning Packet v1",
        "",
        "## 1. Purpose",
        "",
        "This packet defines the M0 planning layer for demo-safe Grants.gov-style opportunity ingestion using seeded "
        "data only. It is preview-only documentation and structured planning output for operators and engineers; it "
        "does not execute workflows, activate sources, call external systems, or ingest live opportunities.",
        "",
        "## 2. Why This Comes After Entity Profile",
        "",
        "The entity profile from Sprint 118 provides the matching context for eligibility, mission fit, contacts, "
        "capacity, and form preview readiness. Seeded opportunities need that profile context so previews stay "
        "coherent, explainable, and sovereignty-respecting during demos.",
        "",
        "## 3. M0 Seeded Opportunity Objective",
        "",
        "Deliver a demo-safe opportunity interface that can show grant discovery, tribal relevance, eligibility "
        "preview, deadlines, and pursuit handoff without live API calls, scrapes, or production ingestion workers.",
        "",
        "## 4. Demo-Safe Source Rules",
        "",
        "M0 requires seeded or demo-safe opportunity records only. Operators must not call Grants.gov, SAM.gov, "
        "agency scrapers, production source polling, real customer datasets, or AI extraction pipelines against real "
        "NOFOs while presenting this planning posture.",
        "",
        "Restrictions restated: no live Grants.gov ingestion; no Grants.gov API call; no SAM.gov integration; no "
        "agency scraping; no production source polling; no real customer data; no AI-generated extraction from real "
        "NOFOs.",
        "",
        "## 5. Required Seeded Opportunity Field Groups",
        "",
        "Fifteen field groups structure seeded opportunities:",
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
            "## 7. Seeded Opportunity to M0 Feature Mapping",
            "",
        ]
    )
    mapping = pkt.get("seeded_opportunity_to_m0_feature_mapping")
    if not isinstance(mapping, list):
        mapping = [{"m0_feature": t, "opportunity_field_use": d} for t, d in _SEEDED_OPPORTUNITY_TO_M0_FEATURES]
    for row in mapping:
        if not isinstance(row, dict):
            continue
        feat = row.get("m0_feature")
        use = row.get("opportunity_field_use")
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
            "## 9. Source Provenance and Freshness Requirements",
            "",
        ]
    )
    for req in pkt.get("source_provenance_and_freshness_requirements") or list(_SOURCE_PROVENANCE_AND_FRESHNESS):
        if isinstance(req, str) and req.strip():
            lines.append(f"- {req}")
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
            "## 11. What Sprint 119 Does Not Build",
            "",
            "Sprint 119 explicitly does not build:",
            "",
        ]
    )
    for item in pkt.get("sprint_119_does_not_build") or list(_SPRINT119_DOES_NOT_BUILD):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 12. M0 Exit Criteria for Seeded Opportunity Planning",
            "",
        ]
    )
    for c in pkt.get("m0_seeded_opportunity_planning_exit_criteria") or list(_M0_EXIT_CRITERIA):
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
            "## 14. Sprint 120 Recommended Next Step",
            "",
            "Sprint 120 should deliver the M0 Tribal Eligibility Tagging and Mission Fit Scoring Preview Planning "
            "Packet, still preview-only and demo-safe unless the operator explicitly authorizes runtime work.",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
