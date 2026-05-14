"""Sprint 123: M0 pursuit pipeline kanban and deadline tracking planning packet (preview-only).

Deterministic operator packet for demo-safe pursuit pipeline card previews, deadline fields,
guardrails, and acceptance criteria. Does not create production kanban, assign users, write
calendars, or run pursuit automation.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = (
    "nf_active_source_activation_m0_pursuit_pipeline_kanban_deadline_tracking_planning_packet_v1"
)
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

M0_PIPELINE_PREVIEW_FOUNDATIONS: tuple[str, ...] = (
    "Reviewed opportunity handoff",
    "Demo-safe kanban card preview",
    "Deadline tracking preview",
    "Owner and reviewer assignment preview",
    "Required action checklist preview",
    "Form readiness tracking preview",
    "Attachment readiness tracking preview",
    "Human review and override workflow",
    "Source provenance visibility",
    "Future runtime pursuit workflow readiness",
)

_FIELD_GROUP_ROWS: tuple[tuple[str, str, tuple[str, str]], ...] = (
    (
        "Pursuit card identity",
        "Stable demo identifiers linking a pipeline preview card to seeds without implying a production record.",
        (
            "Identifiers are fixture-backed or synthetic with explicit preview-only labeling in all outputs.",
            "Identity fields never reuse live customer record keys or production pursuit identifiers.",
        ),
    ),
    (
        "Opportunity reference",
        "Pointer to the seeded or demo-safe opportunity that the reviewed recommendation referenced.",
        (
            "References resolve only to demo-safe opportunity seeds documented in operator scripts.",
            "Missing opportunity seeds block pursuit-ready preview claims until data is corrected.",
        ),
    ),
    (
        "Entity profile reference",
        "Pointer to the seeded organizational entity profile context used for the handoff story.",
        (
            "Profiles are seeded or synthetic with no SAM.gov or live directory synchronization in M0.",
            "Profile gaps surface visible warnings rather than silent pursuit-ready states.",
        ),
    ),
    (
        "Recommendation reference",
        "Pointer to the reviewed pursuit recommendation preview artifact or tier from Sprint 122 scope.",
        (
            "Recommendation links cite preview tiers only, never final pursuit or eligibility outcomes.",
            "Conflicting recommendation seeds route the card to human review in planning narratives.",
        ),
    ),
    (
        "Pipeline status",
        "Demo-safe column label describing preview posture without executing a workflow engine.",
        (
            "Status transitions are narrative-only in M0 and require explicit operator storytelling.",
            "Every status row carries M0 disclaimers: no application submission, no automated outreach, "
            "no production task creation.",
        ),
    ),
    (
        "Priority level",
        "Relative urgency for demo sequencing of checklist work, not procurement priority.",
        (
            "Priority values are bounded demo enums with no auto-escalation to notifications.",
            "Priority cannot override do-not-pursue human review access in specifications.",
        ),
    ),
    (
        "Deadline date",
        "Seeded or synthetic deadline date for buyer-visible countdown stories without calendar sync.",
        (
            "Dates are deterministic on fixtures with documented placeholder rules when absent.",
            "Live agency deadline scraping or calendar import is forbidden in M0 planning posture.",
        ),
    ),
    (
        "Deadline timezone",
        "Explicit IANA or documented placeholder timezone assumptions paired with deadline dates.",
        (
            "Missing timezone blocks pursuit-ready preview status until operators annotate assumptions.",
            "Timezone labels print beside every rendered deadline in operator-facing markdown.",
        ),
    ),
    (
        "Days remaining",
        "Deterministic integer derived from seeded clocks only for demo countdown displays.",
        (
            "Negative or zero values use fixed demo copy templates, not silent status changes.",
            "Days remaining never triggers notification sends or calendar writes in this sprint.",
        ),
    ),
    (
        "Owner assignment",
        "Preview label for accountable demo persona or role, not a live user or task assignment.",
        (
            "Owner fields use synthetic names or roles with watermarking, never production directory IDs.",
            "Owner assignment preview must not assign real users or create assignable work items.",
        ),
    ),
    (
        "Reviewer assignment",
        "Preview label for secondary human review persona separate from owner for demo clarity.",
        (
            "Reviewer fields remain synthetic with explicit non-binding assignment disclaimers.",
            "Reviewer assignment preview must not grant permissions or create review tickets.",
        ),
    ),
    (
        "Required action checklist",
        "Ordered checklist items for materials, clarifications, and reviews in demo walkthroughs only.",
        (
            "Checklist completion is fixture-driven with no write-back to production task systems.",
            "Each item links to visible rationale text from seeded requirement metadata when present.",
        ),
    ),
    (
        "Form readiness status",
        "Aggregated SF-424-style readiness posture from seeded coverage maps without form submission.",
        (
            "Statuses enumerate fixture fields only with explicit no submission in M0 language.",
            "Partial readiness pairs with visible gap lists, not hidden waiver language.",
        ),
    ),
    (
        "Attachment readiness status",
        "Checklist posture for implied attachments from seeded metadata without uploads or storage.",
        (
            "Attachment states are demo-only with no customer document ingestion in this sprint.",
            "Missing attachments downgrade preview readiness with visible callouts in scripts.",
        ),
    ),
    (
        "Eligibility review status",
        "Advisory posture referencing seeded eligibility previews, not legal determinations.",
        (
            "Statuses repeat that M0 does not adjudicate eligibility or automate outreach.",
            "Ambiguous eligibility routes the preview to human review before pursuit-ready language.",
        ),
    ),
    (
        "Source provenance status",
        "Fixture lineage strength for opportunity, profile, and summary seeds shown to the buyer.",
        (
            "Low provenance caps preview strength with visible warnings in all operator narratives.",
            "Provenance never implies live Grants.gov validation or external freshness checks.",
        ),
    ),
    (
        "Human override reason",
        "Structured reason codes when reviewers supersede deterministic preview assembly in demos.",
        (
            "Override reasons are preserved for future auditable runtime designs in planning artifacts.",
            "Overrides cannot erase underlying seeded factors from audit narratives in specifications.",
        ),
    ),
    (
        "Audit and export readiness",
        "Planning flags for future auditable pipeline activity and exportable history without runtime I/O.",
        (
            "Readiness statements are forward-looking design notes with zero runtime writes today.",
            "Export posture references user-visible provenance retention requirements, not live exports.",
        ),
    ),
)

_M0_STATUS_DISCLAIMER = (
    "M0 does not submit applications, does not automate outreach, and does not create production tasks."
)

_PIPELINE_STATUS_ROWS: tuple[tuple[str, str], ...] = (
    (
        "Review Needed",
        f"Initial human triage column for seeded previews. {_M0_STATUS_DISCLAIMER}",
    ),
    (
        "Pursue Preview",
        f"Positive demo column showing intent to prepare materials only. {_M0_STATUS_DISCLAIMER}",
    ),
    (
        "Preparing Materials",
        f"Checklist-focused column for forms and attachments in demo data only. {_M0_STATUS_DISCLAIMER}",
    ),
    (
        "Waiting on Resolution",
        f"Blocked state for open questions or ambiguous deadlines in fixtures. {_M0_STATUS_DISCLAIMER}",
    ),
    (
        "Ready for Final Review",
        f"Final human storytelling checkpoint before any hypothetical runtime handoff. {_M0_STATUS_DISCLAIMER}",
    ),
    (
        "Submitted Outside System",
        f"Narrative-only label when demos describe external submission without system I/O. {_M0_STATUS_DISCLAIMER}",
    ),
    (
        "Paused",
        f"Temporary hold for operator pacing in demos without mutating production queues. {_M0_STATUS_DISCLAIMER}",
    ),
    (
        "Do Not Pursue",
        f"Negative preview outcome that must remain reviewable and never auto-suppresses human access. "
        f"{_M0_STATUS_DISCLAIMER}",
    ),
)

_PIPELINE_PREVIEW_TO_M0_FEATURES: tuple[tuple[str, str], ...] = (
    (
        "pursuit pipeline kanban preview",
        "Uses pursuit card identity, pipeline status, priority level, owner assignment, reviewer assignment, "
        "and recommendation reference for column stories without live boards.",
    ),
    (
        "deadline calendar preview",
        "Uses deadline date, deadline timezone, days remaining, and waiting on resolution status language "
        "for deterministic countdown demos without calendar writes.",
    ),
    (
        "requirement checklist preview",
        "Uses required action checklist, form readiness status, attachment readiness status, and pipeline "
        "status for materials preparation narratives.",
    ),
    (
        "SF-424 preview readiness",
        "Uses form readiness status, entity profile reference, opportunity reference, and eligibility review "
        "status for seeded SF-424 coverage stories without submission.",
    ),
    (
        "attachment readiness preview",
        "Uses attachment readiness status, required action checklist, and source provenance status for "
        "fixture-only attachment posture.",
    ),
    (
        "human review and override workflow",
        "Uses human override reason, pipeline status, reviewer assignment, eligibility review status, and audit "
        "and export readiness for governance storytelling.",
    ),
    (
        "source provenance display",
        "Uses source provenance status, opportunity reference, entity profile reference, and recommendation "
        "reference for visible lineage in previews.",
    ),
    (
        "sovereignty trust explainer",
        "Uses audit and export readiness, human override reason, source provenance status, and eligibility "
        "review status to reinforce human judgment and consent boundaries.",
    ),
)

_DEADLINE_TRACKING_GUARDRAILS: tuple[str, ...] = (
    "Deadlines must include explicit timezone assumptions or documented placeholders in every preview.",
    "Missing deadline or timezone blocks pursuit-ready preview status until operators resolve ambiguity.",
    "Amendment and version change tracking are documented as future runtime requirements, not M0 behavior.",
    "Deadline reminders are not sent in M0 planning; notification sends remain out of scope.",
    "No calendar writes occur in this sprint; countdowns are narrative and fixture-driven only.",
)

_HUMAN_REVIEW_GATES: tuple[str, ...] = (
    "A pursuit pipeline preview card cannot be treated as a production task or assignable work item.",
    "Do-not-pursue status cannot block a user from reviewing the underlying opportunity and factors.",
    "Deadline ambiguity must route to human review before pursuit-ready preview language is used.",
    "Owner and reviewer assignment previews must not assign real users or alter directory permissions.",
    "Human override reason fields must be preserved for future auditable runtime pipeline designs.",
)

_SOVEREIGNTY_AND_TRUST: tuple[str, ...] = (
    "No customer data required for seeded pipeline demos; fixtures must stand alone for walkthroughs.",
    "No customer data leaves the product during seeded demos beyond what operators intentionally narrate.",
    "No model training on customer data without explicit written consent and governance review.",
    "Pipeline previews never override human judgment; they surface signals and checklists only.",
    "Future runtime pipeline activity must remain auditable and exportable by design per planning commitments.",
    "Source provenance must stay visible to the user across handoffs in specifications and demo scripts.",
)

_SPRINT123_DOES_NOT_BUILD: tuple[str, ...] = (
    "No database migration",
    "No frontend UI",
    "No API route",
    "No production kanban",
    "No production task creation",
    "No real user assignment",
    "No calendar write",
    "No notification send",
    "No application submission",
    "No external service call",
    "No runtime pursuit engine change",
)

_M0_EXIT_CRITERIA: tuple[str, ...] = (
    "All eighteen pipeline field groups have documented purposes and at least two acceptance criteria each.",
    "All eight demo-safe pipeline statuses include explicit M0 non-submission and non-automation disclaimers.",
    "Deadline tracking guardrails and human review gates are operator-reviewable in markdown and JSON.",
    "Pipeline preview to M0 feature mapping rows cover kanban, deadlines, checklists, SF-424, attachments, "
    "human review, provenance, and sovereignty explainer surfaces.",
    "Risks and mitigations are enumerated for buyer and engineering misread of preview versus production.",
    "Sprint 124 next step is recorded as the M0 SF-424 Autofill Preview Planning Packet recommendation.",
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "Preview pipeline is mistaken for production workflow",
        "Watermark all demo artifacts, repeat preview-only language in headers, and ban production IDs in seeds.",
    ),
    (
        "Missing deadlines allow false readiness",
        "Block pursuit-ready language without both deadline date and timezone assumptions documented.",
    ),
    (
        "Timezone ambiguity creates deadline risk",
        "Require explicit IANA or placeholder labels beside dates and route ambiguity to human review gates.",
    ),
    (
        "Do-not-pursue suppresses human review",
        "Mandate visible access paths to opportunity factors and override reasons in all planning narratives.",
    ),
    (
        "Real users appear assigned from preview data",
        "Restrict owner and reviewer fields to synthetic personas and forbid live directory bindings in M0.",
    ),
    (
        "Source provenance disappears after pipeline handoff",
        "Carry provenance fields forward in mapping tables and require persistent user-visible lineage notes.",
    ),
    (
        "Audit and export readiness is deferred too long",
        "Document forward-looking audit and export hooks now even though runtime I/O is out of scope.",
    ),
    (
        "Seeded records are confused with customer records",
        "Label seeds explicitly, segregate datasets in scripts, and avoid importing production extracts.",
    ),
    (
        "Pipeline language implies submission automation",
        "Pair status names with M0 disclaimers: no application submission, no outreach automation, no tasks.",
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


def _status_payloads() -> list[dict[str, str]]:
    return [{"status_name": n, "status_description": d} for n, d in _PIPELINE_STATUS_ROWS]


def _risk_payloads() -> list[dict[str, str]]:
    return [{"risk": r, "mitigation": m} for r, m in _RISK_MITIGATIONS]


def build_active_source_activation_m0_pursuit_pipeline_kanban_deadline_tracking_planning_packet() -> (
    dict[str, Any]
):
    """Return the Sprint 123 M0 pursuit pipeline planning packet (deterministic, no side effects)."""
    proof = {
        "sprint_123_m0_pursuit_pipeline_kanban_deadline_tracking_planning_packet_is_stateless": True,
        "sprint_123_m0_pursuit_pipeline_kanban_deadline_tracking_planning_packet_is_side_effect_free": True,
        "sprint_123_m0_pursuit_pipeline_kanban_deadline_tracking_planning_packet_is_preview_only": True,
        "sprint_123_m0_pursuit_pipeline_kanban_deadline_tracking_planning_packet_performs_no_runtime_work": True,
        "sprint_123_m0_pursuit_pipeline_kanban_deadline_tracking_planning_packet_emits_operator_planning_only": True,
    }
    mapping_payload = [
        {"m0_surface_area": a, "pipeline_preview_field_use": u} for a, u in _PIPELINE_PREVIEW_TO_M0_FEATURES
    ]
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 123,
        "packet_name": (
            "NativeForge M0 Pursuit Pipeline Kanban and Deadline Tracking Planning Packet"
        ),
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_define_pipeline_preview_scope": True,
        "may_define_demo_safe_pipeline_states": True,
        "may_define_deadline_tracking_fields": True,
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
        "actual_pipeline_creations": 0,
        "actual_calendar_writes": 0,
        "actual_task_assignments": 0,
        "m0_pipeline_preview_foundations": list(M0_PIPELINE_PREVIEW_FOUNDATIONS),
        "pipeline_field_groups": _field_group_payloads(),
        "pipeline_statuses": _status_payloads(),
        "pipeline_preview_to_m0_feature_mapping": mapping_payload,
        "deadline_tracking_guardrails": list(_DEADLINE_TRACKING_GUARDRAILS),
        "human_review_gates": list(_HUMAN_REVIEW_GATES),
        "sovereignty_and_trust_requirements": list(_SOVEREIGNTY_AND_TRUST),
        "sprint_123_does_not_build": list(_SPRINT123_DOES_NOT_BUILD),
        "m0_pipeline_planning_exit_criteria": list(_M0_EXIT_CRITERIA),
        "risks_and_mitigations": _risk_payloads(),
        "sprint_123_m0_pursuit_pipeline_kanban_deadline_tracking_planning_packet_proof": proof,
    }
    return _json_safe(out)


def _ordered_field_groups(pkt: dict[str, Any]) -> list[dict[str, Any]]:
    raw = pkt.get("pipeline_field_groups")
    if isinstance(raw, list):
        groups = [g for g in raw if isinstance(g, dict)]
        groups.sort(key=lambda g: g.get("priority") if isinstance(g.get("priority"), int) else 0)
        return groups
    return _field_group_payloads()


def render_active_source_activation_m0_pursuit_pipeline_kanban_deadline_tracking_planning_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render the operator-facing markdown packet (deterministic; uses ``packet`` when provided)."""
    pkt = packet if isinstance(packet, dict) else (
        build_active_source_activation_m0_pursuit_pipeline_kanban_deadline_tracking_planning_packet()
    )
    groups = _ordered_field_groups(pkt)
    lines: list[str] = [
        "# NativeForge M0 Pursuit Pipeline Kanban and Deadline Tracking Planning Packet v1",
        "",
        "## 1. Purpose",
        "",
        "This packet defines the M0 planning layer for demo-safe pursuit pipeline kanban previews and deadline "
        "tracking previews. It is preview-only documentation and structured planning output for operators and "
        "engineers; it does not create production kanban boards, assign real users, write calendars, send "
        "notifications, submit applications, call external services, or execute pursuit automation.",
        "",
        "## 2. Why This Comes After Recommendation Planning",
        "",
        "Sprint 122 defined reviewed pursuit recommendation previews built from seeded scoring and narrative "
        "constraints. Sprint 123 defines how a reviewed opportunity becomes a visible pursuit pipeline card "
        "preview with deadlines, ownership, readiness, and human review gates—still without runtime automation.",
        "",
        "## 3. M0 Pipeline Preview Objective",
        "",
        "Deliver a demo-safe pursuit workflow preview that helps a buyer understand opportunity tracking, "
        "ownership, deadlines, readiness, and human review without creating production tasks, calendar events, "
        "or live workflow engines.",
        "",
        "## 4. Demo-Safe Pipeline Rules",
        "",
        "M0 pursuit pipeline previews require seeded or demo-safe opportunity records, seeded or demo-safe "
        "entity profile references, and seeded or demo-safe recommendation references only. Operators must not "
        "import real customer data, create production tasks, write calendars, send notifications, submit "
        "forms, or instantiate production pursuit records while presenting this posture.",
        "",
        "Demo-safe pipeline restrictions restated: no real customer data; no production task creation; no "
        "calendar writes; no notification sends; no application submissions; no external service calls.",
        "",
        "## 5. Required Pipeline Field Groups",
        "",
        "Eighteen field groups structure pursuit pipeline previews:",
        "",
    ]
    for g in groups:
        if not isinstance(g, dict):
            continue
        name = g.get("name")
        purpose = g.get("purpose")
        if isinstance(name, str) and isinstance(purpose, str):
            lines.append(f"- **{name}**: {purpose}")
    lines.extend(["", "## 6. Pipeline Status Definitions", "", "Demo-safe pipeline statuses:", ""])
    statuses = pkt.get("pipeline_statuses") or _status_payloads()
    for row in statuses:
        if not isinstance(row, dict):
            continue
        sn = row.get("status_name")
        sd = row.get("status_description")
        if isinstance(sn, str) and isinstance(sd, str):
            lines.append(f"- **{sn}**: {sd}")
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
    lines.extend(["", "## 8. Pipeline Preview to M0 Feature Mapping", ""])
    mapping = pkt.get("pipeline_preview_to_m0_feature_mapping")
    if not isinstance(mapping, list):
        mapping = [
            {"m0_surface_area": a, "pipeline_preview_field_use": u}
            for a, u in _PIPELINE_PREVIEW_TO_M0_FEATURES
        ]
    for row in mapping:
        if not isinstance(row, dict):
            continue
        area = row.get("m0_surface_area")
        use = row.get("pipeline_preview_field_use")
        if isinstance(area, str) and isinstance(use, str):
            lines.append(f"- **{area}**: {use}")
    lines.extend(["", "## 9. Deadline Tracking Guardrails", ""])
    for item in pkt.get("deadline_tracking_guardrails") or list(_DEADLINE_TRACKING_GUARDRAILS):
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
    lines.extend(["", "## 12. What Sprint 123 Does Not Build", "", "Sprint 123 explicitly does not build:", ""])
    for item in pkt.get("sprint_123_does_not_build") or list(_SPRINT123_DOES_NOT_BUILD):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 13. M0 Exit Criteria for Pipeline Planning",
            "",
        ]
    )
    for c in pkt.get("m0_pipeline_planning_exit_criteria") or list(_M0_EXIT_CRITERIA):
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
            "## 15. Sprint 124 Recommended Next Step",
            "",
            "Sprint 124 should deliver the M0 SF-424 Autofill Preview Planning Packet, still preview-only and "
            "demo-safe unless the operator explicitly authorizes runtime work.",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
