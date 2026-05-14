"""Sprint 137: M1 human review workflow controlled build readiness packet (preview-only).

Deterministic operator packet that defines human review workflow readiness fields, review gate scope,
reviewer roles, routing prerequisites, override rules, audit expectations, sovereignty and security
guardrails, and acceptance criteria—without review route creation, approval record creation, workflow
activation, external calls, form submission, or customer data access.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = "nf_active_source_activation_m1_human_review_workflow_controlled_build_readiness_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

_STATUS_DISCLAIMER = (
    "This status is not workflow activation, is not approval record creation, and is not customer approval."
)

_M1_HUMAN_REVIEW_WORKFLOW_READINESS_FOUNDATIONS: tuple[tuple[str, str], ...] = (
    (
        "Review gate scope readiness",
        "Names each gate, its product area, and submission-adjacent posture without implying routes exist.",
    ),
    (
        "Reviewer role readiness",
        "Assigns named reviewer roles or reviewer-needed placeholders before routing language hardens.",
    ),
    (
        "Review routing readiness",
        "Documents buyer-owned versus operator-owned paths and prerequisites without creating routes.",
    ),
    (
        "Approval decision readiness",
        "States required decisions and evidence expectations without creating approval records.",
    ),
    (
        "Override reason readiness",
        "Requires override reason capture and visibility for audit planning before later activation.",
    ),
    (
        "Audit trail readiness",
        "Makes audit expectations visible for every gate before controlled build planning proceeds.",
    ),
    (
        "Eligibility review readiness",
        "Keeps eligibility interpretation human-reviewed with explicit evidence and escalation hooks.",
    ),
    (
        "Deadline review readiness",
        "Surfaces cutoff, amendment, and clock dependencies as human-reviewed planning fields only.",
    ),
    (
        "Form autofill review readiness",
        "Connects low-confidence autofill targets to human gates without executing autofill here.",
    ),
    (
        "Submission-adjacent review readiness",
        "Treats final submission paths as explicit human approval gates in planning-only language.",
    ),
    (
        "Data sovereignty and security readiness",
        "Records residency, export, retention, and least-privilege prerequisites for future builds.",
    ),
    (
        "Buyer/operator ownership readiness",
        "Clarifies buyer-owned versus operator-owned decisions so internal review is not confused with "
        "buyer approval.",
    ),
)

_HUMAN_REVIEW_READINESS_FIELD_GROUP_ROWS: tuple[tuple[str, str, tuple[str, str]], ...] = (
    (
        "Human review readiness item identity",
        "Stable id, title, and version for each readiness row across operator artifacts.",
        (
            "Identity strings remain identical across repeated packet generations.",
            "Each readiness item exposes a single primary identity key for traceability.",
        ),
    ),
    (
        "Review gate name",
        "Human-readable gate label that operators can reference without implying a live route exists.",
        (
            "Gate names are unique within a planning scope or carry explicit disambiguation notes.",
            "Gate names never imply workflow activation or approval record creation from this sprint.",
        ),
    ),
    (
        "Review gate product area",
        "Maps the gate to ingestion, NOFO, eligibility, deadlines, forms, attachments, signatures, "
        "submission, sovereignty, security, or audit previews.",
        (
            "Every gate lists exactly one primary product area before readiness improves.",
            "Product area labels stay preview-only and forbid silent promotion to runtime routes.",
        ),
    ),
    (
        "Reviewer role",
        "Named accountable reviewer role or explicit reviewer-needed status for the gate.",
        (
            "Reviewer role is populated or explicitly marked as needed before routing review completes.",
            "Reviewer role language disclaims workflow activation and customer approval.",
        ),
    ),
    (
        "Buyer-owned or operator-owned flag",
        "States whether the buyer or the operator owns the decision for the gate to prevent confusion.",
        (
            "Ownership is recorded before approval decision readiness is treated as informed.",
            "Buyer-owned gates never silently inherit operator sign-off as buyer approval.",
        ),
    ),
    (
        "Required review decision",
        "Documents the decision type such as approve, reject, request changes, or defer in planning only.",
        (
            "Required decisions are visible before operators treat the gate as ready for build planning.",
            "Decision fields forbid implying recorded customer approvals or live workflow activation.",
        ),
    ),
    (
        "Required evidence",
        "Lists artifacts, extracts, or attestations reviewers must see without accessing customer data here.",
        (
            "Evidence expectations are named before audit or routing readiness improves.",
            "Evidence lists stay seeded or demo-safe and never require production customer extracts here.",
        ),
    ),
    (
        "Override reason requirement",
        "Captures whether overrides need reasons, templates, and visibility for audit planning.",
        (
            "Override reason rules are visible before any later workflow activation is contemplated.",
            "Override fields stay planning-only and do not execute runtime overrides from this sprint.",
        ),
    ),
    (
        "Audit trail requirement",
        "Defines what must be logged, retained, and exportable in future builds for the gate.",
        (
            "Audit expectations are visible before controlled build planning treats the gate as informed.",
            "Audit language stays descriptive and does not create audit records or routes here.",
        ),
    ),
    (
        "Routing prerequisite",
        "Documents sequencing, dependencies, and ownership prerequisites before routes are built later.",
        (
            "Routing prerequisites distinguish buyer-owned and operator-owned paths explicitly.",
            "Prerequisites forbid implying that review routes were created in this sprint.",
        ),
    ),
    (
        "Sovereignty prerequisite",
        "States residency, consent, export, and data-handling prerequisites for the gate in preview form.",
        (
            "Sovereignty prerequisites appear before readiness moves past sovereignty review needs.",
            "Sovereignty fields never require customer production data in this planning sprint.",
        ),
    ),
    (
        "Security prerequisite",
        "Captures least privilege, access reviews, and sensitive-field handling expectations for the gate.",
        (
            "Security prerequisites are visible before submission-adjacent readiness improves.",
            "Security language does not perform access changes or external security calls here.",
        ),
    ),
    (
        "Submission-adjacent blocker status",
        "Signals whether portal, certification, signature, or channel gaps block readiness in planning.",
        (
            "Submission-adjacent gates require explicit human approval language in planning rows.",
            "Blocker status stays preview-only and does not enqueue submissions or approvals.",
        ),
    ),
    (
        "Escalation rule",
        "Defines when and how unresolved gates escalate without executing escalations in this sprint.",
        (
            "Escalation paths name accountable roles or reviewer-needed states.",
            "Escalation rules disclaim workflow activation and customer approval.",
        ),
    ),
    (
        "Acceptance criteria",
        "Field-level pass or fail checks operators use before assigning a human review readiness status.",
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
        "Restates preview-only posture and lack of workflow activation, approvals, routes, or live calls.",
        (
            "Disclaimers repeat not workflow activation, not approval record creation, and not customer "
            "approval.",
            "Disclaimers appear wherever status language could be misread as go-live automation.",
        ),
    ),
    (
        "Next sprint recommendation",
        "Points operators to Sprint 138 audit export and sovereignty readiness in preview-only language.",
        (
            "Recommendations name Sprint 138 as the M1 Audit Export and Sovereignty Controlled Build "
            "Readiness Packet.",
            "Recommendations forbid silent expansion into runtime work without explicit authorization.",
        ),
    ),
)

_HUMAN_REVIEW_READINESS_STATUS_ROWS: tuple[tuple[str, str], ...] = (
    (
        "Not assessed",
        "Readiness row exists but lacks minimum field coverage; must be assessed before planning improves. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Ready for controlled build planning",
        "Field groups are sufficient for operator-controlled human review workflow build planning without "
        "execution promises. " + _STATUS_DISCLAIMER,
    ),
    (
        "Needs reviewer assignment",
        "Named reviewer role or reviewer-needed resolution is missing before routing review can complete. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Needs routing review",
        "Buyer versus operator ownership, prerequisites, or sequencing need operator review. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Needs audit rule review",
        "Audit trail expectations, logging, or export assumptions need clarification. " + _STATUS_DISCLAIMER,
    ),
    (
        "Needs sovereignty review",
        "Residency, consent, export, or data-handling prerequisites need operator review. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Blocked before workflow activation",
        "Unresolved gates, ownership, evidence, sovereignty, security, or submission-adjacent issues block "
        "readiness in planning. " + _STATUS_DISCLAIMER,
    ),
    (
        "Deferred beyond M1",
        "Gate or product area is intentionally deferred past M1 while remaining visible in the inventory. "
        + _STATUS_DISCLAIMER,
    ),
)

_PREVIEW_ONLY_HUMAN_REVIEW_READINESS_RULES: tuple[str, ...] = (
    "Require seeded or demo-safe records only; never import production customer extracts into human review "
    "readiness rows.",
    "Do not access real customer data while building or reviewing this human review readiness packet.",
    "Do not create review routes, approval records, or activate workflows from this sprint packet.",
    "Do not imply customer approval; buyer decisions stay distinct from internal operator review.",
    "Do not place external API calls, scrapes, live ingestions, or live AI generations while using this packet.",
    "Do not submit forms, invoke AI generation, or perform runtime writes while using this packet.",
    "Do not activate sources, perform live ingestion, or change production workflows while using this packet.",
    "Keep human judgment, audit expectations, sovereignty boundaries, and ownership visibility explicit.",
)

_HUMAN_REVIEW_READINESS_BY_PRODUCT_AREA: tuple[tuple[str, str], ...] = (
    (
        "source ingestion review",
        "Readiness tracks publisher lineage, fixture labels, and ingestion checkpoints with reviewer roles "
        "before ingestion automation is assumed.",
    ),
    (
        "NOFO extraction review",
        "Readiness ties extracted requirements to named gates, evidence, and human interpretation without "
        "implying extraction execution here.",
    ),
    (
        "eligibility interpretation review",
        "Readiness mandates human review for eligibility decisions with explicit evidence and escalation.",
    ),
    (
        "deadline review",
        "Readiness surfaces amendments, clocks, and cutoffs as human-reviewed planning fields only.",
    ),
    (
        "form autofill review",
        "Readiness maps low-confidence autofill targets to human gates without autofill execution language.",
    ),
    (
        "attachment package review",
        "Readiness lists attachment expectations, signatures, and cross-package dependencies as review-first.",
    ),
    (
        "signature and authorization review",
        "Readiness requires explicit human approval language for signature and authorization pathways.",
    ),
    (
        "final submission-adjacent review",
        "Readiness treats portal paths and certifications as explicit human approval gates in planning only.",
    ),
    (
        "data sovereignty review",
        "Readiness records residency, export, retention, and consent prerequisites without customer data access.",
    ),
    (
        "security/access review",
        "Readiness documents least privilege and sensitive-field handling without runtime access changes.",
    ),
    (
        "audit/export review",
        "Readiness defines audit visibility and export expectations without creating audit routes here.",
    ),
)

_REVIEW_GATE_PREREQUISITE_RULES: tuple[str, ...] = (
    "Every review gate must have a named reviewer role or reviewer-needed status before readiness improves.",
    "Every review gate must define required evidence before routing or audit readiness is treated as informed.",
    "Override reasons must be captured before any later workflow activation is contemplated.",
    "Audit trail expectations must be visible before controlled human review workflow build planning proceeds.",
    "Submission-adjacent gates require explicit human approval language in planning rows.",
    "Unresolved review gate ownership blocks workflow readiness until buyer or operator ownership is clear.",
)

_ROUTING_OVERRIDE_AND_AUDIT_RULES: tuple[str, ...] = (
    "Routing must distinguish buyer-owned gates from operator-owned gates in every planning row.",
    "Low-confidence fields require human review before operators treat automation assumptions as informed.",
    "Eligibility and deadline decisions require human review with visible evidence expectations.",
    "Signature and authorization review requires human approval language distinct from internal notes only.",
    "Override reasons must be visible in audit planning artifacts before activation language appears.",
    "No review route is created in this sprint.",
    "No runtime activation occurs in this sprint.",
)

_SOVEREIGNTY_AND_TRUST_REQUIREMENTS: tuple[str, ...] = (
    "Customer owns its data.",
    "No customer data is required for this planning sprint.",
    "No customer data leaves the product during seeded demos.",
    "No model training on customer data without explicit written consent.",
    "Human judgment remains final.",
    "Review provenance remains visible.",
    "Human review workflow readiness must not overpromise implementation readiness.",
)

_SPRINT137_DOES_NOT_BUILD: tuple[str, ...] = (
    "no review route creation",
    "no approval record creation",
    "no workflow activation",
    "no customer approval",
    "no form submission",
    "no customer data access",
    "no AI generation",
    "no source activation",
    "no live ingestion",
    "no real application submission",
    "no production readiness certification",
    "no external service call",
    "no database migration",
    "no frontend UI",
    "no API route",
    "no production workflow change",
)

_M1_HUMAN_REVIEW_WORKFLOW_READINESS_EXIT_CRITERIA: tuple[str, ...] = (
    "All eighteen human review readiness field groups are documented with purposes and acceptance criteria.",
    "All eight human review readiness statuses include explicit not workflow activation, not approval record "
    "creation, and not customer approval disclaimers.",
    "All twelve M1 human review workflow readiness foundations include operator focus statements without "
    "runtime execution.",
    "All eleven human review readiness by product area rows include preview mapping language and caveat "
    "expectations.",
    "Review gate prerequisite rules, routing and audit rules, sovereignty requirements, and preview-only rules "
    "are listed.",
    "Risks and mitigations are recorded with operator discipline expectations for controlled build planning.",
    "Sprint 138 recommendation is captured as the next preview-only audit export and sovereignty readiness step.",
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "Workflow activation is implied by planning language",
        "Ban activate, deploy, or go-live verbs except inside explicit not-workflow-activation disclaimers.",
    ),
    (
        "Approval route creation is implied too early",
        "Pair every gate with explicit no review route creation language until a later authorized sprint.",
    ),
    (
        "Reviewer ownership is missing",
        "Require reviewer role or reviewer-needed status before routing review can complete.",
    ),
    (
        "Buyer approval is confused with internal review",
        "Keep buyer-owned versus operator-owned flags visible on every gate with distinct language.",
    ),
    (
        "Low-confidence fields bypass human review",
        "Force human review prerequisites for low-confidence targets before readiness improves.",
    ),
    (
        "Submission-adjacent work proceeds without gates",
        "Mandate explicit human approval language for submission-adjacent gates in planning rows.",
    ),
    (
        "Customer data handling is implied too early",
        "Sequence sovereignty prerequisites before any customer-specific data language in readiness rows.",
    ),
    (
        "Audit requirements are under-scoped",
        "Block audit readiness improvements until audit trail requirements and export expectations are named.",
    ),
    (
        "Human review readiness becomes theater instead of control",
        "Require traceable identities, evidence lists, ownership flags, and risk notes alongside every status.",
    ),
)

_SPRINT138_RECOMMENDED_NEXT_STEP = (
    "Sprint 138 should deliver the M1 Audit Export and Sovereignty Controlled Build Readiness Packet, still "
    "preview-only unless the operator explicitly authorizes runtime work."
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _field_group_payloads() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, (name, purpose, criteria) in enumerate(_HUMAN_REVIEW_READINESS_FIELD_GROUP_ROWS, start=1):
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
        {"foundation_area": a, "operator_focus": b} for a, b in _M1_HUMAN_REVIEW_WORKFLOW_READINESS_FOUNDATIONS
    ]


def _status_payloads() -> list[dict[str, str]]:
    return [{"status": s, "definition": d} for s, d in _HUMAN_REVIEW_READINESS_STATUS_ROWS]


def _product_area_payloads() -> list[dict[str, str]]:
    return [
        {"product_area": a, "human_review_readiness_preview": b} for a, b in _HUMAN_REVIEW_READINESS_BY_PRODUCT_AREA
    ]


def _risk_payloads() -> list[dict[str, str]]:
    return [{"risk": r, "mitigation": m} for r, m in _RISK_MITIGATIONS]


def build_active_source_activation_m1_human_review_workflow_controlled_build_readiness_packet() -> (
    dict[str, Any]
):
    """Return the Sprint 137 M1 human review workflow controlled build readiness packet (deterministic)."""
    proof = {
        "sprint_137_m1_human_review_workflow_controlled_build_readiness_packet_is_stateless": True,
        "sprint_137_m1_human_review_workflow_controlled_build_readiness_packet_is_side_effect_free": True,
        "sprint_137_m1_human_review_workflow_controlled_build_readiness_packet_is_preview_only": True,
        "sprint_137_m1_human_review_workflow_controlled_build_readiness_packet_performs_no_runtime_work": True,
        "sprint_137_m1_human_review_workflow_controlled_build_readiness_packet_emits_operator_planning_only": True,
    }
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 137,
        "packet_name": "NativeForge M1 Human Review Workflow Controlled Build Readiness Packet",
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_define_human_review_workflow_readiness": True,
        "may_define_review_gate_prerequisites": True,
        "may_define_audit_and_override_requirements": True,
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
        "actual_workflows_activated": 0,
        "m1_human_review_workflow_controlled_build_readiness_foundations": _foundation_payloads(),
        "human_review_readiness_field_groups": _field_group_payloads(),
        "human_review_readiness_statuses": _status_payloads(),
        "human_review_readiness_status_universal_disclaimer": _STATUS_DISCLAIMER,
        "preview_only_human_review_readiness_rules": list(_PREVIEW_ONLY_HUMAN_REVIEW_READINESS_RULES),
        "human_review_readiness_by_product_area": _product_area_payloads(),
        "review_gate_prerequisite_rules": list(_REVIEW_GATE_PREREQUISITE_RULES),
        "routing_override_and_audit_rules": list(_ROUTING_OVERRIDE_AND_AUDIT_RULES),
        "sovereignty_and_trust_requirements": list(_SOVEREIGNTY_AND_TRUST_REQUIREMENTS),
        "sprint_137_does_not_build": list(_SPRINT137_DOES_NOT_BUILD),
        "m1_human_review_workflow_readiness_exit_criteria": list(_M1_HUMAN_REVIEW_WORKFLOW_READINESS_EXIT_CRITERIA),
        "risks_and_mitigations": _risk_payloads(),
        "sprint_138_recommended_next_step": _SPRINT138_RECOMMENDED_NEXT_STEP,
        "sprint_137_m1_human_review_workflow_controlled_build_readiness_packet_proof": proof,
    }
    return _json_safe(out)


def _ordered_field_groups(pkt: dict[str, Any]) -> list[dict[str, Any]]:
    raw = pkt.get("human_review_readiness_field_groups")
    if isinstance(raw, list):
        groups = [g for g in raw if isinstance(g, dict)]
        groups.sort(key=lambda g: g.get("priority") if isinstance(g.get("priority"), int) else 0)
        return groups
    return _field_group_payloads()


def render_active_source_activation_m1_human_review_workflow_controlled_build_readiness_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render the operator-facing markdown packet (deterministic; uses ``packet`` when provided)."""
    pkt = packet if isinstance(packet, dict) else (
        build_active_source_activation_m1_human_review_workflow_controlled_build_readiness_packet()
    )
    groups = _ordered_field_groups(pkt)
    lines: list[str] = [
        "# NativeForge M1 Human Review Workflow Controlled Build Readiness Packet v1",
        "",
        "## 1. Purpose",
        "",
        "This packet defines the M1 planning layer for human review workflow controlled build readiness. It is "
        "preview-only: it structures review gate scope, reviewer roles, routing prerequisites, evidence and "
        "override rules, audit expectations, sovereignty and security guardrails, and acceptance criteria for "
        "operators without review route creation, approval record creation, workflow activation, customer "
        "approval, external calls, scraping, form submission, or customer data access.",
        "",
        "## 2. Why This Comes After Form Package Readiness",
        "",
        "Sprint 136 defined form package readiness so forms, mappings, provenance, confidence thresholds, and "
        "human gates stay visible before autofill language hardens. Sprint 137 applies controlled build "
        "discipline to human review workflows so submission-adjacent review cannot be trusted until reviewers, "
        "routing, evidence, override rules, audit requirements, sovereignty and security dependencies, and "
        "blockers are visible—still without workflow activation or runtime execution in this sprint.",
        "",
        "## 3. M1 Human Review Workflow Readiness Objective",
        "",
        "Deliver a preview-only readiness framework that prevents review workflow activation before reviewers, "
        "routing, evidence, override rules, audit requirements, sovereignty and security dependencies, and "
        "blockers are visible—without runnable workflow promises, review route creation, approval record "
        "creation, customer approval, or external calls in this sprint.",
        "",
        "M1 human review workflow controlled build readiness foundations:",
        "",
    ]
    foundations = pkt.get("m1_human_review_workflow_controlled_build_readiness_foundations")
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
            "## 4. Preview-Only Human Review Readiness Rules",
            "",
        ]
    )
    for rule in pkt.get("preview_only_human_review_readiness_rules") or list(
        _PREVIEW_ONLY_HUMAN_REVIEW_READINESS_RULES
    ):
        if isinstance(rule, str) and rule.strip():
            lines.append(f"- {rule}")
    lines.extend(
        [
            "",
            "Preview-only human review readiness rules restated: seeded or demo-safe records only; no real "
            "customer data; no review route creation; no approval record creation; no workflow activation; no "
            "customer approval; no external calls.",
            "",
            "## 5. Required Human Review Readiness Field Groups",
            "",
            "Eighteen field groups structure every human review readiness row:",
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
            "## 6. Human Review Readiness Status Definitions",
            "",
            "Eight preview-only human review readiness statuses apply. Each status explicitly disclaims "
            "workflow activation, approval record creation, and customer approval:",
            "",
        ]
    )
    statuses = pkt.get("human_review_readiness_statuses")
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
    lines.extend(["", "## 8. Human Review Readiness by Product Area", ""])
    mapping = pkt.get("human_review_readiness_by_product_area")
    if not isinstance(mapping, list):
        mapping = _product_area_payloads()
    for row in mapping:
        if not isinstance(row, dict):
            continue
        ar = row.get("product_area")
        preview = row.get("human_review_readiness_preview")
        if isinstance(ar, str) and isinstance(preview, str):
            lines.append(f"- **{ar}**: {preview}")
    lines.extend(["", "## 9. Review Gate Prerequisite Rules", ""])
    for item in pkt.get("review_gate_prerequisite_rules") or list(_REVIEW_GATE_PREREQUISITE_RULES):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 10. Routing, Override, and Audit Rules", ""])
    for item in pkt.get("routing_override_and_audit_rules") or list(_ROUTING_OVERRIDE_AND_AUDIT_RULES):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 11. Sovereignty and Trust Requirements", ""])
    for item in pkt.get("sovereignty_and_trust_requirements") or list(_SOVEREIGNTY_AND_TRUST_REQUIREMENTS):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 12. What Sprint 137 Does Not Build", "", "Sprint 137 explicitly does not build:", ""])
    for item in pkt.get("sprint_137_does_not_build") or list(_SPRINT137_DOES_NOT_BUILD):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 13. M1 Human Review Workflow Readiness Exit Criteria",
            "",
        ]
    )
    for c in pkt.get("m1_human_review_workflow_readiness_exit_criteria") or list(
        _M1_HUMAN_REVIEW_WORKFLOW_READINESS_EXIT_CRITERIA
    ):
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
            "## 15. Sprint 138 Recommended Next Step",
            "",
            pkt.get("sprint_138_recommended_next_step") or _SPRINT138_RECOMMENDED_NEXT_STEP,
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
