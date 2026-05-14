"""Sprint 127: M0 human review gates and demo closeout planning packet (preview-only).

Deterministic operator packet that defines human review checkpoints and demo closeout criteria for the
full M0 demo flow. No review routes, no approval records, no demo closeout execution, no external calls,
and no customer data access.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = "nf_active_source_activation_m0_human_review_gates_demo_closeout_planning_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

_STATUS_NON_BINDING = (
    "Not a production approval, not a legal approval, and not a submission authorization."
)

M0_HUMAN_REVIEW_AND_DEMO_CLOSEOUT_FOUNDATIONS: tuple[str, ...] = (
    "Entity profile review gate",
    "Seeded opportunity review gate",
    "Tribal eligibility review gate",
    "NOFO summary review gate",
    "Recommendation review gate",
    "Pipeline and deadline review gate",
    "SF-424 autofill review gate",
    "Requirement checklist review gate",
    "Data sovereignty and export review gate",
    "M0 demo closeout readiness",
)

_REVIEW_STATUS_ROWS: tuple[tuple[str, str], ...] = (
    (
        "Not reviewed",
        "Default state before any operator walkthrough; seeded outputs remain visible but lack a "
        "recorded demo review decision. "
        + _STATUS_NON_BINDING,
    ),
    (
        "Review needed",
        "Operator flagged ambiguity, missing provenance, or buyer-risk language that must be triaged "
        "before presentation. "
        + _STATUS_NON_BINDING,
    ),
    (
        "Reviewed for demo",
        "A human confirmed the artifact is acceptable for a scripted demo narrative using seeded data "
        "only. "
        + _STATUS_NON_BINDING,
    ),
    (
        "Needs correction",
        "Content requires edits while preserving provenance and override reasons; blocked fields stay "
        "visible. "
        + _STATUS_NON_BINDING,
    ),
    (
        "Blocked by missing data",
        "Required fields are absent or placeholders are too thin to present without misleading a buyer. "
        + _STATUS_NON_BINDING,
    ),
    (
        "Blocked by low confidence",
        "Source confidence is below the demo threshold; the item must be labeled or withheld from "
        "narrative emphasis. "
        + _STATUS_NON_BINDING,
    ),
    (
        "Approved for demo narrative only",
        "Explicitly scoped to storytelling in a controlled demo; does not authorize production use or "
        "submission. "
        + _STATUS_NON_BINDING,
    ),
    (
        "Excluded from demo",
        "Removed from the walkthrough path while remaining visible to operators for auditability. "
        + _STATUS_NON_BINDING,
    ),
)

_FIELD_GROUP_ROWS: tuple[tuple[str, str, tuple[str, str]], ...] = (
    (
        "Review gate identity",
        "Stable identifier and human-readable title so operators can reference a gate consistently "
        "across artifacts.",
        (
            "Each gate exposes a unique id and display name in planning packets without creating "
            "database rows.",
            "Identity strings remain stable across repeated packet generations for reproducible audits.",
        ),
    ),
    (
        "Review gate source feature",
        "Maps the gate to the M0 product surface such as entity profile, seeded opportunity, or "
        "sovereignty preview.",
        (
            "Mappings reference planning-layer feature names only, not production service endpoints.",
            "Every gate lists exactly one primary source feature to avoid ambiguous accountability.",
        ),
    ),
    (
        "Review trigger",
        "Defines what human-visible condition moves an item into Review needed or Blocked states.",
        (
            "Triggers are described with demo-safe verbs such as seed refresh or copy edit, not runtime "
            "automation.",
            "Ambiguous triggers default to Review needed rather than silent pass.",
        ),
    ),
    (
        "Required reviewer role",
        "Names the accountable role such as operator, product reviewer, or tribal liaison in planning "
        "language only.",
        (
            "Roles are labels for packets, not provisioned IAM identities in this sprint.",
            "Dual-control scenarios are noted where sovereignty or form-adjacent content is involved.",
        ),
    ),
    (
        "Review status",
        "Current demo-safe status selected only from the eight defined values with explicit non-binding "
        "disclaimers.",
        (
            "Statuses always travel with the standard non-production, non-legal, non-submission note.",
            "Transitions are documented narratively without persisting approval records.",
        ),
    ),
    (
        "Human override reason",
        "Captures why a human deviated from automated or seeded defaults while preserving auditability.",
        (
            "Overrides cannot delete underlying provenance or confidence signals in planning designs.",
            "Empty override fields force Review needed when automation disagrees with presented text.",
        ),
    ),
    (
        "Field provenance visibility",
        "Ensures lineage from seed, template, or upstream sprint packet remains visible to reviewers.",
        (
            "Every buyer-visible field lists its provenance source category in the planning model.",
            "Hidden provenance blocks Approved for demo narrative only until corrected.",
        ),
    ),
    (
        "Source confidence visibility",
        "Surfaces qualitative or numeric confidence labels without implying production scoring engines.",
        (
            "Low confidence forces Blocked by low confidence or explicit buyer caveats before demos.",
            "Confidence labels cannot be removed solely to greenlight a narrative.",
        ),
    ),
    (
        "Missing data visibility",
        "Lists absent required fields so buyers never infer completeness from silent omissions.",
        (
            "Missing fields render as explicit gaps rather than blank space in demo scripts.",
            "Blocked by missing data must list the missing keys referenced in closeout criteria.",
        ),
    ),
    (
        "Demo-safe data confirmation",
        "Checkbox-style attestation that only seeded or synthetic records appear in the walkthrough.",
        (
            "Operators must confirm no production extracts are loaded into demo fixtures.",
            "Mixed environments require explicit segregation notes before any demo narrative status.",
        ),
    ),
    (
        "Approval limitation statement",
        "Restates that no gate grants production, legal, or submission authority in M0 planning.",
        (
            "Limitation text appears adjacent to any status that could be misread as sign-off.",
            "Statements repeat preview-only posture from sprint guardrail packets.",
        ),
    ),
    (
        "Buyer-facing caveat",
        "Short language buyers hear that reinforces non-final, editable, preview-only outputs.",
        (
            "Caveats mention non-final recommendations and preview-only sovereignty claims where relevant.",
            "Caveats are present for every AI-adjacent or form-adjacent artifact in the demo path.",
        ),
    ),
    (
        "Audit readiness note",
        "Describes what evidence a future runtime would need without claiming live audit streams today.",
        (
            "Notes pair with zero actual runtime writes in this sprint.",
            "Notes require export-friendly review logs in later implementation designs.",
        ),
    ),
    (
        "Export readiness note",
        "Clarifies what could be exported later versus what is shown on screen only in M0.",
        (
            "Notes never assert that a binary export was generated during planning demos.",
            "Notes tie back to sovereignty and provenance field groups without external calls.",
        ),
    ),
    (
        "Sovereignty trust note",
        "Aligns the gate with customer-owned data, consent, and no-training-without-consent principles.",
        (
            "Notes restate preview-only sovereignty posture from Sprint 126 planning.",
            "Notes forbid implying customer data left the product during seeded demos.",
        ),
    ),
    (
        "Runtime readiness dependency",
        "Lists engineering or policy dependencies before a future runtime review workflow could exist.",
        (
            "Dependencies are planning bullets, not tickets auto-created from this packet.",
            "Each dependency names whether it blocks buyer narrative or internal rehearsal only.",
        ),
    ),
    (
        "Closeout evidence",
        "Checklist references proving the demo path met closeout criteria such as labeled seeds and "
        "caveats.",
        (
            "Evidence items point to packet sections rather than production log URIs.",
            "Incomplete evidence blocks M0 demo closeout readiness until remediated.",
        ),
    ),
    (
        "Next sprint recommendation",
        "Captures the forward-looking operator note, currently Sprint 128 narrative walkthrough packet.",
        (
            "Recommendation text matches the sprint roadmap string without triggering work automatically.",
            "Recommendation reminds operators that runtime work stays off unless explicitly authorized.",
        ),
    ),
)

_REVIEW_GATES_BY_M0_FEATURE: tuple[tuple[str, str], ...] = (
    (
        "organizational entity profile",
        "Entity profile review gate confirms seeded tribal or organization attributes, provenance, and "
        "demo-safe labels before any buyer walkthrough.",
    ),
    (
        "seeded opportunity ingestion",
        "Seeded opportunity review gate validates fixture Grants.gov-style rows, ingestion labels, and "
        "absence of production pulls.",
    ),
    (
        "tribal eligibility and mission fit scoring",
        "Tribal eligibility review gate checks scoring transparency, confidence visibility, and "
        "non-final recommendation caveats.",
    ),
    (
        "NOFO plain-language summary",
        "NOFO summary review gate ensures plain-language text shows provenance, missing sections, and "
        "preview-only posture.",
    ),
    (
        "opportunity recommendation preview",
        "Recommendation review gate enforces non-final language, human override hooks, and buyer "
        "caveats for AI-adjacent outputs.",
    ),
    (
        "pursuit pipeline and deadline tracking",
        "Pipeline and deadline review gate verifies Kanban cards use seeded tasks, visible dates, and "
        "no implied submissions.",
    ),
    (
        "SF-424 autofill preview",
        "SF-424 autofill review gate confirms editable preview fields, sensitive handling notes, and "
        "blockers for incomplete forms.",
    ),
    (
        "requirement checklist preview",
        "Requirement checklist review gate validates checklist rows show provenance, confidence, and "
        "missing-data callouts.",
    ),
    (
        "data sovereignty policy and export preview",
        "Data sovereignty and export review gate ties checklist and summaries to ownership, consent, "
        "and export preview-only statements.",
    ),
)

_DEMO_SAFE_REVIEW_RULES: tuple[str, ...] = (
    "Demo-safe review requires seeded or demo-safe records only; no real customer data may appear in "
    "the walkthrough path.",
    "No production approval may be inferred from any review status in this packet.",
    "No legal approval may be inferred from demo review language; counsel owns contract decisions.",
    "No submission authorization may be inferred; M0 remains preview-only with no submission pathway.",
    "No runtime workflow creation occurs from this planning artifact.",
    "No external calls occur while operators use this packet.",
)

_DEMO_CLOSEOUT_CRITERIA: tuple[str, ...] = (
    "All demo-visible outputs have a documented review status from the eight demo-safe values.",
    "All seeded data is clearly labeled as seeded or synthetic in operator scripts and fixtures.",
    "All low-confidence outputs are marked or excluded from emphasized narrative beats.",
    "All missing required fields are visible to reviewers and buyers without silent gaps.",
    "All form-adjacent outputs remain editable previews without implying filed forms.",
    "All recommendation outputs are marked non-final with buyer-facing caveats.",
    "All sovereignty and export claims are marked preview-only without downloadable production exports.",
    "No submission pathway is implied anywhere in the M0 demo storyline.",
)

_HUMAN_OVERRIDE_AND_CORRECTION_RULES: tuple[str, ...] = (
    "Human override reasons must be preserved alongside the affected fields for future auditability.",
    "Corrections must not hide original provenance; superseded text remains discoverable in planning "
    "designs.",
    "Blocked items must remain visible to operators even when excluded from buyer-facing narration.",
    "Do-not-pursue or Excluded from demo statuses cannot erase operator visibility of the underlying "
    "record.",
    "Review notes must remain export-ready in future runtime designs without executing exports today.",
)

_SOVEREIGNTY_AND_TRUST_REQUIREMENTS: tuple[str, ...] = (
    "The customer owns its data; NativeForge remains a planning-stage guide in M0.",
    "No customer data is required for seeded review demos using this packet.",
    "No customer data leaves the product during seeded demos aligned with this planning layer.",
    "No model training on customer data without explicit written consent remains a hard planning rule.",
    "Future runtime review activity must be auditable and exportable per roadmap commitments.",
    "Human judgment remains final over any automated or seeded suggestion.",
    "Demo closeout must not imply production readiness or deployed governance controls.",
)

_SPRINT127_DOES_NOT_BUILD: tuple[str, ...] = (
    "No real review route creation",
    "No approval record creation",
    "No legal approval",
    "No production approval",
    "No submission authorization",
    "No demo closeout execution",
    "No customer data access",
    "No database migration",
    "No frontend UI",
    "No API route",
    "No runtime approval workflow",
    "No production governance change",
)

_M0_EXIT_CRITERIA: tuple[str, ...] = (
    "All ten M0 human review and demo closeout foundations are enumerated with stable ordering.",
    "All eighteen review gate field groups include purposes and at least two acceptance criteria each.",
    "All eight review statuses include explicit non-production, non-legal, non-submission disclaimers.",
    "Review gates by M0 feature map every sprint 118 through 126 surface to a named review gate.",
    "Demo closeout criteria, override rules, sovereignty requirements, risks, and mitigations are present "
    "in structured data and markdown.",
    "Sprint 128 next step is recorded as the M0 Demo Narrative and Buyer Walkthrough Packet.",
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "Reviewed for demo is mistaken for production approval",
        "Pair statuses with approval limitation statements, buyer caveats, and repeated preview-only "
        "banners in scripts.",
    ),
    (
        "Legal approval is implied",
        "Ban legal verbs from demo statuses, cite counsel ownership, and keep M0 artifacts non-contractual.",
    ),
    (
        "Submission authorization is implied",
        "Remove submission verbs from demos, label SF-424 as preview-only, and block narrative beats that "
        "reference filing.",
    ),
    (
        "Low-confidence outputs are hidden",
        "Require source confidence visibility fields and Blocked by low confidence transitions when "
        "thresholds fail.",
    ),
    (
        "Seeded records are confused with customer records",
        "Mandate demo-safe data confirmation labels, segregate fixtures, and audit fixture provenance.",
    ),
    (
        "Buyer sees preview as production-ready",
        "Use buyer-facing caveats, non-final recommendation language, and explicit no runtime deployment "
        "statements.",
    ),
    (
        "Human override reason is lost",
        "Bind overrides to immutable planning notes and forbid silent deletion in future runtime designs.",
    ),
    (
        "Sovereignty or export claims are overstated",
        "Cross-check sovereignty trust notes with Sprint 126 limits and keep export language preview-only.",
    ),
    (
        "Review gates become theater instead of actual quality control",
        "Require evidence-backed closeout criteria, visible blockers, and operator sign-off on checklists "
        "before demos.",
    ),
)

_SPRINT128_RECOMMENDED_NEXT_STEP = (
    "Sprint 128 should deliver the M0 Demo Narrative and Buyer Walkthrough Packet, still preview-only "
    "and demo-safe unless the operator explicitly authorizes runtime work."
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
    return [
        {
            "status": label,
            "description": desc,
            "not_production_legal_or_submission": _STATUS_NON_BINDING,
        }
        for label, desc in _REVIEW_STATUS_ROWS
    ]


def _mapping_payloads() -> list[dict[str, str]]:
    return [{"m0_feature": a, "review_gate_planning_focus": b} for a, b in _REVIEW_GATES_BY_M0_FEATURE]


def _risk_payloads() -> list[dict[str, str]]:
    return [{"risk": r, "mitigation": m} for r, m in _RISK_MITIGATIONS]


def build_active_source_activation_m0_human_review_gates_demo_closeout_planning_packet() -> dict[str, Any]:
    """Return the Sprint 127 M0 human review gates and demo closeout planning packet (deterministic)."""
    proof = {
        "sprint_127_m0_human_review_demo_closeout_planning_packet_is_stateless": True,
        "sprint_127_m0_human_review_demo_closeout_planning_packet_is_side_effect_free": True,
        "sprint_127_m0_human_review_demo_closeout_planning_packet_is_preview_only": True,
        "sprint_127_m0_human_review_demo_closeout_planning_packet_performs_no_runtime_work": True,
        "sprint_127_m0_human_review_demo_closeout_planning_packet_emits_operator_planning_only": True,
    }
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 127,
        "packet_name": "NativeForge M0 Human Review Gates and Demo Closeout Planning Packet",
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_define_human_review_gate_scope": True,
        "may_define_demo_closeout_criteria": True,
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
        "actual_review_routes_created": 0,
        "actual_approval_records_created": 0,
        "actual_demo_closures_executed": 0,
        "m0_human_review_and_demo_closeout_foundations": list(M0_HUMAN_REVIEW_AND_DEMO_CLOSEOUT_FOUNDATIONS),
        "review_gate_field_groups": _field_group_payloads(),
        "review_status_definitions": _status_payloads(),
        "review_gates_by_m0_feature": _mapping_payloads(),
        "demo_safe_review_rules": list(_DEMO_SAFE_REVIEW_RULES),
        "demo_closeout_criteria": list(_DEMO_CLOSEOUT_CRITERIA),
        "human_override_and_correction_rules": list(_HUMAN_OVERRIDE_AND_CORRECTION_RULES),
        "sovereignty_and_trust_requirements": list(_SOVEREIGNTY_AND_TRUST_REQUIREMENTS),
        "sprint_127_does_not_build": list(_SPRINT127_DOES_NOT_BUILD),
        "m0_human_review_demo_closeout_planning_exit_criteria": list(_M0_EXIT_CRITERIA),
        "risks_and_mitigations": _risk_payloads(),
        "sprint_128_recommended_next_step": _SPRINT128_RECOMMENDED_NEXT_STEP,
        "sprint_127_m0_human_review_demo_closeout_planning_packet_proof": proof,
    }
    return _json_safe(out)


def _ordered_field_groups(pkt: dict[str, Any]) -> list[dict[str, Any]]:
    raw = pkt.get("review_gate_field_groups")
    if isinstance(raw, list):
        groups = [g for g in raw if isinstance(g, dict)]
        groups.sort(key=lambda g: g.get("priority") if isinstance(g.get("priority"), int) else 0)
        return groups
    return _field_group_payloads()


def render_active_source_activation_m0_human_review_gates_demo_closeout_planning_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render the operator-facing markdown packet (deterministic; uses ``packet`` when provided)."""
    pkt = packet if isinstance(packet, dict) else (
        build_active_source_activation_m0_human_review_gates_demo_closeout_planning_packet()
    )
    groups = _ordered_field_groups(pkt)
    lines: list[str] = [
        "# NativeForge M0 Human Review Gates and Demo Closeout Planning Packet v1",
        "",
        "## 1. Purpose",
        "",
        "This packet defines the M0 planning layer for human review gates and demo closeout readiness "
        "across the full M0 demo sequence from organizational entity profile through sovereignty and "
        "export preview. It is an operator-facing artifact only: it does not create review routes, "
        "approval records, runtime workflows, or executable closeout actions.",
        "",
        "## 2. Why This Closes the M0 Planning Sequence",
        "",
        "Sprints 117 through 126 defined the M0 demo build scope, organizational entity profile, seeded "
        "Grants.gov-style opportunity ingestion, tribal eligibility and mission fit scoring, NOFO "
        "plain-language summary, opportunity recommendation preview, pursuit pipeline and deadline "
        "tracking, SF-424 autofill preview, requirement checklist preview, and the data sovereignty "
        "policy and export trust layer. Sprint 127 defines the review gates that keep the demo honest, "
        "buyer-safe, and visibly non-final before any presentation.",
        "",
        "## 3. M0 Human Review Objective",
        "",
        "The goal is a demo-safe human review framework that makes every AI-adjacent, form-adjacent, "
        "eligibility-adjacent, and sovereignty-adjacent output visibly reviewable before buyer "
        "presentation, using seeded data and explicit caveats rather than production controls.",
        "",
        "## 4. Demo-Safe Review Rules",
        "",
    ]
    for rule in pkt.get("demo_safe_review_rules") or list(_DEMO_SAFE_REVIEW_RULES):
        if isinstance(rule, str) and rule.strip():
            lines.append(f"- {rule}")
    lines.extend(
        [
            "",
            "Demo-safe review rules restated: seeded or demo-safe records only; no real customer data; "
            "no production approval; no legal approval; no submission authorization; no runtime workflow "
            "creation; no external calls.",
            "",
            "## 5. Required Review Gate Field Groups",
            "",
            "Eighteen field groups structure every human review gate in M0 planning:",
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
    lines.extend(["", "## 6. Review Status Definitions", "", "Eight demo-safe statuses apply:", ""])
    for row in pkt.get("review_status_definitions") or _status_payloads():
        if not isinstance(row, dict):
            continue
        st = row.get("status")
        desc = row.get("description")
        if isinstance(st, str) and isinstance(desc, str):
            lines.append(f"### {st}")
            lines.append("")
            lines.append(desc)
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
    lines.extend(["", "## 8. Review Gates by M0 Feature", ""])
    mapping = pkt.get("review_gates_by_m0_feature")
    if not isinstance(mapping, list):
        mapping = _mapping_payloads()
    for row in mapping:
        if not isinstance(row, dict):
            continue
        feat = row.get("m0_feature")
        focus = row.get("review_gate_planning_focus")
        if isinstance(feat, str) and isinstance(focus, str):
            lines.append(f"- **{feat}**: {focus}")
    lines.extend(
        [
            "",
            "- **M0 demo closeout readiness**: Cross-cutting gate ensuring every surface above met "
            "closeout criteria, evidence notes, and Sprint 128 narrative guidance before buyers arrive.",
            "",
            "## 9. Demo Closeout Criteria",
            "",
        ]
    )
    for item in pkt.get("demo_closeout_criteria") or list(_DEMO_CLOSEOUT_CRITERIA):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 10. Human Override and Correction Rules", ""])
    for item in pkt.get("human_override_and_correction_rules") or list(_HUMAN_OVERRIDE_AND_CORRECTION_RULES):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 11. Sovereignty and Trust Requirements", ""])
    for item in pkt.get("sovereignty_and_trust_requirements") or list(_SOVEREIGNTY_AND_TRUST_REQUIREMENTS):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 12. What Sprint 127 Does Not Build", "", "Sprint 127 explicitly does not build:", ""])
    for item in pkt.get("sprint_127_does_not_build") or list(_SPRINT127_DOES_NOT_BUILD):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 13. M0 Exit Criteria for Human Review and Demo Closeout Planning",
            "",
        ]
    )
    for c in pkt.get("m0_human_review_demo_closeout_planning_exit_criteria") or list(_M0_EXIT_CRITERIA):
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
            "## 15. Sprint 128 Recommended Next Step",
            "",
            pkt.get("sprint_128_recommended_next_step") or _SPRINT128_RECOMMENDED_NEXT_STEP,
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
