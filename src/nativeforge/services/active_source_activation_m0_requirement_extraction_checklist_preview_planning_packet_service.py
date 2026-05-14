"""Sprint 125: M0 requirement extraction checklist preview planning packet (preview-only).

Deterministic operator packet for demo-safe requirement checklist preview planning from seeded
NOFO summary content and seeded opportunities. No real NOFO parsing, LLM extraction, runtime checklist
generation, or production task creation.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = "nf_active_source_activation_m0_requirement_extraction_checklist_preview_planning_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

M0_REQUIREMENT_CHECKLIST_PREVIEW_FOUNDATIONS: tuple[str, ...] = (
    "NOFO requirement checklist preview",
    "Required attachment preview",
    "Required form preview",
    "Eligibility documentation preview",
    "Match/cost-share documentation preview",
    "Narrative section preview",
    "Deadline-linked requirement preview",
    "Owner/reviewer readiness preview",
    "Human review and correction workflow",
    "Future runtime checklist readiness",
)

_FIELD_GROUP_ROWS: tuple[tuple[str, str, tuple[str, str]], ...] = (
    (
        "Requirement identity",
        "Stable demo identifier tying each checklist row to a seeded requirement key without implying "
        "live extraction.",
        (
            "Identity values come from seeded NOFO summary fixtures or synthetic demo keys only.",
            "Identity must not claim linkage to Grants.gov or agency systems in M0 planning posture.",
        ),
    ),
    (
        "Requirement category",
        "Demo-safe category label routing buyers to eligibility, narrative, budget, attachment, form, "
        "match, resolution, reporting, deadline, or human-review buckets.",
        (
            "Categories use the bounded Sprint 125 vocabulary with explicit preview-only watermarking.",
            "Ambiguous category seeds must route to human review before preview-ready claims.",
        ),
    ),
    (
        "Requirement source section",
        "Human-readable reference to which seeded summary section inspired the preview row without "
        "parsing real NOFOs.",
        (
            "Source sections map to demo NOFO summary headings or fixture placeholders only.",
            "Missing source section must route to human review in all operator scripts.",
        ),
    ),
    (
        "Requirement plain-language label",
        "Short buyer-facing label summarizing the requirement without LLM-generated prose.",
        (
            "Labels are authored or seeded strings with documented provenance in the packet.",
            "Low-confidence labels must be visibly marked and editable in specifications.",
        ),
    ),
    (
        "Requirement detail",
        "Expanded seeded explanation of what the requirement asks for in demo-safe language.",
        (
            "Details never substitute for legal NOFO text and repeat preview-only posture.",
            "Conflicting detail seeds downgrade readiness until human correction notes land.",
        ),
    ),
    (
        "Required attachment flag",
        "Boolean-style preview signal for attachment expectations without file ingestion.",
        (
            "Flags are fixture-backed with visible absent states when unknown.",
            "Required attachments missed in seeds must surface missing-data flags, not silent drops.",
        ),
    ),
    (
        "Required form flag",
        "Preview signal that a form package element may be needed without SF-424 generation.",
        (
            "Form flags align to Sprint 124 SF-424 preview readiness stories as planning links only.",
            "Form flags cannot trigger Grants.gov Workspace or submission verbs in M0.",
        ),
    ),
    (
        "Eligibility documentation flag",
        "Indicates eligibility-adjacent documentation expectations for tribal buyer narratives.",
        (
            "Flags document demo posture only and forbid automated eligibility determinations.",
            "Eligibility gaps pair with visible missing-data language and human review routing.",
        ),
    ),
    (
        "Match/cost-share documentation flag",
        "Preview posture for match or cost-share evidence without financial validation.",
        (
            "Match language uses seeded amounts or qualitative demo tokens without bank or agency calls.",
            "Ambiguous match seeds require human review before deadline-ready language.",
        ),
    ),
    (
        "Narrative response flag",
        "Signals that a narrative section response may be required without generating narrative text.",
        (
            "Narrative flags forbid LLM drafting in M0 and reference seeded outline bullets only.",
            "Narrative scope disputes route to human correction notes preserved for future runtime.",
        ),
    ),
    (
        "Due date relationship",
        "Structured relationship between a requirement and seeded deadline metadata.",
        (
            "Missing due-date relationship must block deadline-ready status in specifications.",
            "Deadline links reference Sprint 123 calendar preview fixtures without live calendars.",
        ),
    ),
    (
        "Pipeline status relationship",
        "Lightweight linkage to pursuit pipeline card states without workflow execution.",
        (
            "Statuses mirror seeded pipeline fixtures from Sprint 123 with no production tasks.",
            "Pipeline transitions cannot be triggered from checklist preview planning artifacts.",
        ),
    ),
    (
        "Owner preview",
        "Placeholder owner label for readiness storytelling without assigning real users.",
        (
            "Owner previews must not assign real users or imply HRIS or directory synchronization.",
            "Owner gaps surface missing-data flags rather than silent defaults.",
        ),
    ),
    (
        "Reviewer preview",
        "Placeholder reviewer label for dual-control demos without identity resolution.",
        (
            "Reviewer previews must not assign real users or send notifications from this sprint.",
            "Reviewer ambiguity routes to human review with preserved correction notes.",
        ),
    ),
    (
        "Missing data flag",
        "Aggregated signal that seeded data is incomplete for a requirement row.",
        (
            "Missing data flags must be visible on every checklist preview surface in M0 specs.",
            "Flags cannot auto-close without documented human review outcomes.",
        ),
    ),
    (
        "Source provenance and confidence",
        "Lineage and confidence for each previewed requirement without external scoring APIs.",
        (
            "Low confidence requirements must be visibly marked in JSON and markdown packets.",
            "Provenance never claims real NOFO parsing or external validation occurred in M0.",
        ),
    ),
    (
        "Human correction notes",
        "Structured operator and reviewer notes carried beside requirement rows for auditability.",
        (
            "Human correction notes must be preserved in future runtime checklist designs.",
            "Notes cannot erase underlying seeded provenance or confidence metadata.",
        ),
    ),
    (
        "Audit and export readiness",
        "Forward-looking hooks describing auditable and exportable future runtime checklist activity.",
        (
            "Future runtime checklist activity must be auditable and exportable per planning commitments.",
            "Export readiness language is planning-only and forbids production exports today.",
        ),
    ),
)

_REQUIREMENT_CATEGORY_ROWS: tuple[tuple[str, str], ...] = (
    (
        "Eligibility requirement",
        "Seeded eligibility-adjacent obligations shown for buyer education without automated eligibility "
        "decisions.",
    ),
    (
        "Narrative requirement",
        "Narrative scope expectations tied to seeded section outlines without generated narrative bodies.",
    ),
    (
        "Budget requirement",
        "Budget-related obligations described with fixture numbers or qualitative demo tokens only.",
    ),
    (
        "Attachment requirement",
        "Attachment expectations flagged for attachment readiness previews without file uploads.",
    ),
    (
        "Form requirement",
        "Form-adjacent obligations cross-referenced to SF-424 preview readiness without form generation.",
    ),
    (
        "Match/cost-share requirement",
        "Match or cost-share documentation expectations without financial institution or agency validation.",
    ),
    (
        "Resolution or authorization requirement",
        "Tribal council or authorizing body expectations described as planning placeholders only.",
    ),
    (
        "Reporting requirement",
        "Post-award reporting expectations referenced as demo bullets without compliance automation.",
    ),
    (
        "Deadline requirement",
        "Deadline-linked obligations aligned to seeded calendar fixtures without live clock sync.",
    ),
    (
        "Human review required",
        "Explicit bucket for ambiguous or sensitive requirements that always need human judgment.",
    ),
)

_CHECKLIST_PREVIEW_TO_M0_FEATURES: tuple[tuple[str, str], ...] = (
    (
        "NOFO summary preview",
        "Supplies plain-language requirement seeds, source section references, and provenance for "
        "checklist rows without parsing real NOFOs.",
    ),
    (
        "SF-424 preview readiness",
        "Aligns form and attachment flags with Sprint 124 SF-424 autofill preview planning without "
        "generating forms.",
    ),
    (
        "pursuit pipeline card",
        "Anchors checklist rows to Sprint 123 pipeline context for readiness demos without workflow "
        "execution.",
    ),
    (
        "deadline calendar preview",
        "Uses due-date relationship fields with seeded deadline metadata for calendar storytelling only.",
    ),
    (
        "attachment readiness preview",
        "Surfaces required attachment flags alongside missing-data signals without ingesting files.",
    ),
    (
        "human review workflow",
        "Requires editable requirements, correction notes, routing for ambiguity, and explicit no-task "
        "posture.",
    ),
    (
        "source provenance display",
        "Shows provenance and confidence for every requirement row without hiding low-confidence data.",
    ),
    (
        "sovereignty trust explainer",
        "Reinforces human judgment, seeded datasets, consent boundaries, and auditability commitments.",
    ),
    (
        "future export readiness",
        "Documents audit and export hooks for later runtime checklist engines without exporting today.",
    ),
)

_MISSING_DATA_AND_CONFIDENCE_RULES: tuple[str, ...] = (
    "Missing source section must route to human review.",
    "Low confidence requirements must be visibly marked.",
    "Ambiguous requirement category must route to human review.",
    "Missing due-date relationship must block deadline-ready status.",
    "Owner/reviewer previews must not assign real users.",
    "No external validation occurs in M0 planning.",
)

_HUMAN_REVIEW_GATES: tuple[str, ...] = (
    "The checklist preview cannot be treated as a final submission checklist.",
    "Every requirement must remain editable.",
    "Source provenance must be visible.",
    "Ambiguous requirements must route to human review.",
    "Human correction notes must be preserved in future runtime design.",
    "No production task creation occurs in M0 preview.",
)

_SOVEREIGNTY_AND_TRUST: tuple[str, ...] = (
    "No customer data is required for seeded checklist demos; fixtures must stand alone.",
    "No customer data leaves the product during seeded demos beyond intentional operator narration.",
    "No model training on customer data without explicit written consent and governance review.",
    "The checklist preview never overrides human judgment; it surfaces signals, gaps, and provenance.",
    "Future runtime checklist activity must be auditable and exportable per planning commitments.",
    "Source provenance must remain visible to the user.",
)

_SPRINT125_DOES_NOT_BUILD: tuple[str, ...] = (
    "No real NOFO parsing",
    "No LLM extraction",
    "No Grants.gov API call",
    "No SAM.gov integration",
    "No agency scraping",
    "No real customer data",
    "No database migration",
    "No frontend UI",
    "No runtime checklist engine",
    "No production task creation",
    "No real user assignment",
    "No external validation",
)

_M0_EXIT_CRITERIA: tuple[str, ...] = (
    "All eighteen checklist field groups have documented purposes and at least two acceptance criteria.",
    "All ten demo-safe requirement categories have definitions aligned to seeded summary posture.",
    "Demo-safe requirement rules, missing-data and confidence rules, and human review gates are "
    "operator-visible.",
    "Checklist preview to M0 feature mapping covers summary, SF-424 readiness, pipeline, deadlines, "
    "attachments, review, provenance, sovereignty explainer, and export readiness.",
    "Sovereignty and trust requirements address seeded demos, consent, human judgment, auditability, "
    "and provenance visibility.",
    "Risks and mitigations address preview versus production misreads for checklists, deadlines, owners, "
    "and tasks.",
    "Sprint 126 next step records the M0 Data Sovereignty Policy and Export Preview Planning Packet.",
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "Preview checklist is mistaken for final submission checklist",
        "Banner preview-only headers, forbid final-checklist verbs, and restate human review gates in "
        "every operator packet.",
    ),
    (
        "Ambiguous requirements are treated as confirmed",
        "Route ambiguous categories to human review, block preview-ready language, and require correction "
        "notes.",
    ),
    (
        "Low-confidence source data is hidden",
        "Mandate visible confidence markers in JSON and markdown and ban suppression defaults.",
    ),
    (
        "Required attachments are missed",
        "Pair attachment flags with missing-data signals and explicit attachment readiness preview links.",
    ),
    (
        "Due-date relationships are unclear",
        "Block deadline-ready status when due-date relationships are absent and surface calendar gaps.",
    ),
    (
        "Owner/reviewer preview implies real assignment",
        "Use placeholder labels, ban directory sync language, and document no real user assignment.",
    ),
    (
        "Seeded data is confused with customer data",
        "Label seeds, segregate fixtures, and ban production extracts from demo environments.",
    ),
    (
        "Checklist language implies production task creation",
        "Use planning-only verbs, list no production task creation gates, and cross-link does-not-build "
        "items.",
    ),
    (
        "Human review is bypassed",
        "Require routing for ambiguity, visible provenance, and preserved correction notes before "
        "preview-ready claims.",
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


def _category_payloads() -> list[dict[str, str]]:
    return [{"name": n, "definition": d} for n, d in _REQUIREMENT_CATEGORY_ROWS]


def _mapping_payloads() -> list[dict[str, str]]:
    return [
        {"m0_surface_area": a, "checklist_preview_field_use": u} for a, u in _CHECKLIST_PREVIEW_TO_M0_FEATURES
    ]


def _risk_payloads() -> list[dict[str, str]]:
    return [{"risk": r, "mitigation": m} for r, m in _RISK_MITIGATIONS]


def build_active_source_activation_m0_requirement_extraction_checklist_preview_planning_packet() -> (
    dict[str, Any]
):
    """Return the Sprint 125 M0 requirement checklist preview planning packet (deterministic)."""
    proof = {
        "sprint_125_m0_requirement_checklist_preview_planning_packet_is_stateless": True,
        "sprint_125_m0_requirement_checklist_preview_planning_packet_is_side_effect_free": True,
        "sprint_125_m0_requirement_checklist_preview_planning_packet_is_preview_only": True,
        "sprint_125_m0_requirement_checklist_preview_planning_packet_performs_no_runtime_work": True,
        "sprint_125_m0_requirement_checklist_preview_planning_packet_emits_operator_planning_only": True,
    }
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 125,
        "packet_name": "NativeForge M0 Requirement Extraction Checklist Preview Planning Packet",
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_define_requirement_checklist_scope": True,
        "may_define_demo_safe_requirement_fields": True,
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
        "actual_requirement_extractions": 0,
        "actual_checklist_creations": 0,
        "actual_task_creations": 0,
        "m0_requirement_checklist_preview_foundations": list(M0_REQUIREMENT_CHECKLIST_PREVIEW_FOUNDATIONS),
        "checklist_field_groups": _field_group_payloads(),
        "requirement_categories": _category_payloads(),
        "checklist_preview_to_m0_feature_mapping": _mapping_payloads(),
        "missing_data_and_confidence_rules": list(_MISSING_DATA_AND_CONFIDENCE_RULES),
        "human_review_gates": list(_HUMAN_REVIEW_GATES),
        "sovereignty_and_trust_requirements": list(_SOVEREIGNTY_AND_TRUST),
        "sprint_125_does_not_build": list(_SPRINT125_DOES_NOT_BUILD),
        "m0_checklist_preview_planning_exit_criteria": list(_M0_EXIT_CRITERIA),
        "risks_and_mitigations": _risk_payloads(),
        "sprint_125_m0_requirement_checklist_preview_planning_packet_proof": proof,
    }
    return _json_safe(out)


def _ordered_field_groups(pkt: dict[str, Any]) -> list[dict[str, Any]]:
    raw = pkt.get("checklist_field_groups")
    if isinstance(raw, list):
        groups = [g for g in raw if isinstance(g, dict)]
        groups.sort(key=lambda g: g.get("priority") if isinstance(g.get("priority"), int) else 0)
        return groups
    return _field_group_payloads()


def render_active_source_activation_m0_requirement_extraction_checklist_preview_planning_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render the operator-facing markdown packet (deterministic; uses ``packet`` when provided)."""
    pkt = packet if isinstance(packet, dict) else (
        build_active_source_activation_m0_requirement_extraction_checklist_preview_planning_packet()
    )
    groups = _ordered_field_groups(pkt)
    lines: list[str] = [
        "# NativeForge M0 Requirement Extraction Checklist Preview Planning Packet v1",
        "",
        "## 1. Purpose",
        "",
        "This packet defines the M0 planning layer for demo-safe requirement checklist previews built from "
        "seeded NOFO summary content and seeded opportunity records. It is preview-only operator "
        "documentation and structured planning output; it does not parse real NOFOs, call LLMs, generate "
        "runtime checklists, create production tasks, or access production customer records.",
        "",
        "## 2. Why This Comes After SF-424 Preview Planning",
        "",
        "Sprint 124 defined SF-424 autofill preview readiness from seeded entity and opportunity data "
        "without form generation or submission. Sprint 125 defines how opportunity requirements can become "
        "a visible checklist preview without parsing real NOFOs, without LLM extraction, and without "
        "creating production tasks.",
        "",
        "## 3. M0 Checklist Preview Objective",
        "",
        "Deliver a demo-safe checklist preview that helps a buyer understand requirements, attachments, "
        "forms, narrative work, deadlines, missing data, and human review needs while keeping every row "
        "editable and provenance-visible.",
        "",
        "## 4. Demo-Safe Requirement Rules",
        "",
        "M0 requirement checklist previews require seeded or demo-safe NOFO summary content and seeded or "
        "demo-safe opportunity records only. Operators must not parse real NOFOs, call LLMs, use real "
        "customer data, create production tasks, or invoke external validation APIs while presenting this "
        "posture.",
        "",
        "Demo-safe requirement restrictions restated: no real NOFO parsing; no LLM extraction; no real "
        "customer data; no production task creation; no external validation calls.",
        "",
        "## 5. Required Checklist Field Groups",
        "",
        "Eighteen field groups structure requirement checklist preview planning:",
        "",
    ]
    for g in groups:
        if not isinstance(g, dict):
            continue
        name = g.get("name")
        purpose = g.get("purpose")
        if isinstance(name, str) and isinstance(purpose, str):
            lines.append(f"- **{name}**: {purpose}")
    lines.extend(["", "## 6. Requirement Category Definitions", ""])
    cats = pkt.get("requirement_categories")
    if not isinstance(cats, list):
        cats = _category_payloads()
    for row in cats:
        if isinstance(row, dict):
            n = row.get("name")
            d = row.get("definition")
            if isinstance(n, str) and isinstance(d, str):
                lines.append(f"- **{n}**: {d}")
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
    lines.extend(["", "## 8. Checklist Preview to M0 Feature Mapping", ""])
    mapping = pkt.get("checklist_preview_to_m0_feature_mapping")
    if not isinstance(mapping, list):
        mapping = _mapping_payloads()
    for row in mapping:
        if not isinstance(row, dict):
            continue
        area = row.get("m0_surface_area")
        use = row.get("checklist_preview_field_use")
        if isinstance(area, str) and isinstance(use, str):
            lines.append(f"- **{area}**: {use}")
    lines.extend(["", "## 9. Missing Data and Confidence Rules", ""])
    for item in pkt.get("missing_data_and_confidence_rules") or list(_MISSING_DATA_AND_CONFIDENCE_RULES):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 10. Human Review Gates", "", "Mandatory gates:", ""])
    for gate in pkt.get("human_review_gates") or list(_HUMAN_REVIEW_GATES):
        if isinstance(gate, str) and gate.strip():
            lines.append(f"- {gate}")
    lines.extend(["", "## 11. Sovereignty and Trust Requirements", ""])
    for req in pkt.get("sovereignty_and_trust_requirements") or list(_SOVEREIGNTY_AND_TRUST):
        if isinstance(req, str) and req.strip():
            lines.append(f"- {req}")
    lines.extend(["", "## 12. What Sprint 125 Does Not Build", "", "Sprint 125 explicitly does not build:", ""])
    for item in pkt.get("sprint_125_does_not_build") or list(_SPRINT125_DOES_NOT_BUILD):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 13. M0 Exit Criteria for Checklist Planning",
            "",
        ]
    )
    for c in pkt.get("m0_checklist_preview_planning_exit_criteria") or list(_M0_EXIT_CRITERIA):
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
            "## 15. Sprint 126 Recommended Next Step",
            "",
            "Sprint 126 should deliver the M0 Data Sovereignty Policy and Export Preview Planning Packet, "
            "still preview-only and demo-safe unless the operator explicitly authorizes runtime work.",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
