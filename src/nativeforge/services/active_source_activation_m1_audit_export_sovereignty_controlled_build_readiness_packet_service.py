"""Sprint 138: M1 audit export and sovereignty controlled build readiness packet (preview-only).

Deterministic operator packet that defines audit/export readiness fields, sovereignty controls,
retention and export prerequisites, access and audit expectations, human gates, security guardrails,
and acceptance criteria—without export execution, audit record creation, retention policy change,
external calls, customer data access, or runtime activation.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = "nf_active_source_activation_m1_audit_export_sovereignty_controlled_build_readiness_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

_STATUS_DISCLAIMER = (
    "This status is not export execution, is not audit record creation, and is not retention policy change."
)

_M1_AUDIT_EXPORT_SOVEREIGNTY_READINESS_FOUNDATIONS: tuple[tuple[str, str], ...] = (
    (
        "Audit event scope readiness",
        "Names audit event categories, boundaries, and evidence expectations without creating audit records.",
    ),
    (
        "Export package readiness",
        "Defines package composition, format expectations, and provenance hooks without creating exports.",
    ),
    (
        "Data ownership statement readiness",
        "Captures customer data ownership language for planning without implying live ownership workflows.",
    ),
    (
        "Data retention readiness",
        "Surfaces retention expectations and visibility requirements without changing retention policies.",
    ),
    (
        "Access control readiness",
        "Documents least-privilege and review prerequisites before customer data handling is contemplated.",
    ),
    (
        "Customer export request readiness",
        "States request intake, verification, and human gate expectations without executing export requests.",
    ),
    (
        "Source provenance export readiness",
        "Keeps lineage and fixture labels visible for export planning without performing ingest or export.",
    ),
    (
        "Human review audit readiness",
        "Aligns audit/export planning with human review gates from Sprint 137 without activating workflows.",
    ),
    (
        "AI usage disclosure readiness",
        "Requires disclosure fields wherever AI-adjacent processing is planned without AI generation here.",
    ),
    (
        "No-training consent readiness",
        "Makes no-training consent expectations explicit before AI-adjacent build planning proceeds.",
    ),
    (
        "Security review readiness",
        "Captures security prerequisites and review checkpoints without external security calls.",
    ),
    (
        "Sovereignty trust proof readiness",
        "Records sovereignty proof expectations as operator controls, not marketing claims.",
    ),
)

_AUDIT_SOVEREIGNTY_READINESS_FIELD_GROUP_ROWS: tuple[tuple[str, str, tuple[str, str]], ...] = (
    (
        "Audit sovereignty readiness item identity",
        "Stable id, title, and version for each readiness row across operator artifacts.",
        (
            "Identity strings remain identical across repeated packet generations.",
            "Each readiness item exposes a single primary identity key for traceability.",
        ),
    ),
    (
        "Product area",
        "Maps the readiness item to ingestion, NOFO, eligibility, pursuit, forms, review, export, or access.",
        (
            "Every row lists exactly one primary product area before readiness is treated as informed.",
            "Product area labels stay preview-only and forbid silent promotion to runtime execution.",
        ),
    ),
    (
        "Audit event type",
        "Names the audit event category for scope planning without implying audit records exist.",
        (
            "Audit event types are enumerated before audit scope readiness improves.",
            "Audit event language disclaims audit record creation and export execution.",
        ),
    ),
    (
        "Export package area",
        "States which export package slice the row covers without creating an export package.",
        (
            "Export package areas are named or explicitly marked as undecided before planning closes.",
            "Export package language disclaims export creation and customer data access.",
        ),
    ),
    (
        "Data owner statement",
        "Records who owns the data and required attestations in planning-only language.",
        (
            "Data owner statements appear before sovereignty trust proof readiness improves.",
            "Owner statements never require production customer extracts in this sprint.",
        ),
    ),
    (
        "Data retention expectation",
        "Documents visibility and handling expectations without changing retention policies.",
        (
            "Retention expectations are visible before retention readiness is treated as informed.",
            "Retention language disclaims retention policy change and export execution.",
        ),
    ),
    (
        "Access control prerequisite",
        "Lists access reviews, roles, and least-privilege gates before customer data handling.",
        (
            "Access prerequisites are populated or explicitly marked as needed before access review closes.",
            "Access language disclaims runtime permission changes and customer data access here.",
        ),
    ),
    (
        "Export format expectation",
        "Captures format, schema, and redaction expectations for future export builds only.",
        (
            "Export formats are named or flagged as undecided before export package readiness improves.",
            "Format expectations disclaim export creation and audit record creation.",
        ),
    ),
    (
        "Source provenance requirement",
        "Requires lineage, fixture labels, and provenance visibility for export planning.",
        (
            "Provenance requirements are visible before source provenance export readiness improves.",
            "Provenance rules forbid losing lineage in export planning narratives.",
        ),
    ),
    (
        "AI usage disclosure requirement",
        "Defines disclosure obligations for AI-adjacent flows without AI generation in this sprint.",
        (
            "Disclosure requirements appear before AI-adjacent build language hardens.",
            "Disclosure fields disclaim AI generation and export execution from this sprint.",
        ),
    ),
    (
        "No-training consent requirement",
        "States explicit written consent expectations before model training language appears.",
        (
            "No-training consent expectations are visible before AI-adjacent build planning proceeds.",
            "Consent language disclaims consent capture execution and customer data access here.",
        ),
    ),
    (
        "Human review prerequisite",
        "Ties audit/export planning to human gates without implying human workflows are active.",
        (
            "Human review prerequisites reference Sprint 137 posture without workflow activation.",
            "Human gate language disclaims audit record creation and export execution.",
        ),
    ),
    (
        "Security prerequisite",
        "Captures least privilege, sensitive-field handling, and security review expectations.",
        (
            "Security prerequisites are visible before sovereignty blocker status clears.",
            "Security language disclaims external calls and runtime security configuration changes.",
        ),
    ),
    (
        "Sovereignty blocker status",
        "Signals residency, consent, export, or channel gaps that block audit/export build readiness.",
        (
            "Blocker status stays preview-only and does not enqueue exports or policy changes.",
            "Blocker notes repeat not export execution, not audit record creation, not retention policy change.",
        ),
    ),
    (
        "Acceptance criteria",
        "Field-level pass or fail checks operators use before assigning an audit/sovereignty readiness status.",
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
            "Restates preview-only posture and lack of export execution, audit record creation, retention policy "
            "change, and live calls."
        ),
        (
            "Disclaimers repeat not export execution, not audit record creation, and not retention policy change.",
            "Disclaimers appear wherever status language could be misread as go-live export or audit work.",
        ),
    ),
    (
        "Next sprint recommendation",
        "Points operators to Sprint 139 pilot operations and support readiness in preview-only language.",
        (
            "Recommendations name Sprint 139 as the M1 Pilot Operations and Support Controlled Build Readiness "
            "Packet.",
            "Recommendations forbid silent expansion into runtime work without explicit authorization.",
        ),
    ),
)

_AUDIT_SOVEREIGNTY_READINESS_STATUS_ROWS: tuple[tuple[str, str], ...] = (
    (
        "Not assessed",
        "Readiness row exists but lacks minimum field coverage; must be assessed before planning improves. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Ready for controlled build planning",
        "Field groups are sufficient for operator-controlled audit and sovereignty build planning without "
        "execution promises. " + _STATUS_DISCLAIMER,
    ),
    (
        "Needs ownership review",
        "Data owner statements or buyer versus operator ownership clarity need operator review. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Needs retention review",
        "Retention expectations, visibility, or handling assumptions need operator review. " + _STATUS_DISCLAIMER,
    ),
    (
        "Needs access review",
        "Access control prerequisites, roles, or least-privilege assumptions need operator review. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Needs sovereignty review",
        "Residency, consent, export channel, or trust proof language needs operator review. " + _STATUS_DISCLAIMER,
    ),
    (
        "Blocked before audit/export build",
        "Unresolved ownership, retention, access, provenance, consent, security, or sovereignty issues block "
        "readiness in planning. " + _STATUS_DISCLAIMER,
    ),
    (
        "Deferred beyond M1",
        "Product area or readiness row is intentionally deferred past M1 while remaining visible in the "
        "inventory. " + _STATUS_DISCLAIMER,
    ),
)

_PREVIEW_ONLY_AUDIT_EXPORT_AND_SOVEREIGNTY_RULES: tuple[str, ...] = (
    "Require seeded or demo-safe records only; never import production customer extracts into audit or "
    "sovereignty readiness rows.",
    "Do not access real customer data while building or reviewing this audit export and sovereignty readiness "
    "packet.",
    "Do not create exports, audit records, or change retention policies from this sprint packet.",
    "Do not place external API calls, scrapes, live ingestions, or live AI generations while using this packet.",
    "Do not submit forms, invoke AI generation, or perform runtime writes while using this packet.",
    "Do not activate sources, perform live ingestion, or change production workflows while using this packet.",
    "Keep human judgment, sovereignty boundaries, provenance visibility, and non-execution disclaimers explicit.",
)

_AUDIT_EXPORT_READINESS_BY_PRODUCT_AREA: tuple[tuple[str, str], ...] = (
    (
        "source ingestion events",
        "Readiness tracks publisher lineage and ingestion checkpoints for future audit events without ingestion "
        "execution.",
    ),
    (
        "NOFO extraction events",
        "Readiness ties extraction outputs to audit scope without performing extraction here.",
    ),
    (
        "eligibility scoring events",
        "Readiness documents scoring inputs, thresholds, and human review touchpoints without runtime scoring.",
    ),
    (
        "pursuit pipeline events",
        "Readiness maps pipeline stage transitions to audit event expectations without activating pipelines.",
    ),
    (
        "form autofill preview events",
        "Readiness connects autofill previews to disclosure and human gate expectations without autofill "
        "execution.",
    ),
    (
        "human review events",
        "Readiness aligns audit/export fields with Sprint 137 human gates without workflow activation.",
    ),
    (
        "override events",
        "Readiness requires override visibility for audit planning without executing overrides.",
    ),
    (
        "export package events",
        "Readiness defines package boundaries and provenance for export planning without export creation.",
    ),
    (
        "access control events",
        "Readiness lists access reviews and prerequisites without changing permissions or accessing customer data.",
    ),
    (
        "data retention events",
        "Readiness surfaces retention visibility expectations without retention policy change.",
    ),
    (
        "AI usage disclosure events",
        "Readiness mandates disclosure checkpoints for AI-adjacent flows without AI generation here.",
    ),
)

_SOVEREIGNTY_CONTROL_PREREQUISITE_RULES: tuple[str, ...] = (
    "Every sovereignty control must preserve customer data ownership in planning language.",
    "Retention expectations must be visible before audit or export build planning proceeds.",
    "Export expectations must be visible before audit or export build planning proceeds.",
    "No-training consent expectations must be visible before AI-adjacent build planning proceeds.",
    "Access control prerequisites must be reviewed before customer data handling is contemplated.",
    "Unresolved sovereignty blockers prevent audit and export build readiness until cleared in planning.",
)

_ACCESS_RETENTION_AND_EXPORT_RULES: tuple[str, ...] = (
    "Export readiness must not imply export creation.",
    "Retention readiness must not imply retention policy change.",
    "Audit readiness must not imply audit record creation.",
    "Access review must precede any customer data handling.",
    "Export package planning must preserve source provenance.",
    "No runtime activation occurs in this sprint.",
)

_SOVEREIGNTY_AND_TRUST_REQUIREMENTS: tuple[str, ...] = (
    "Customer owns its data.",
    "No customer data is required for this planning sprint.",
    "No customer data leaves the product during seeded demos.",
    "No model training on customer data without explicit written consent.",
    "Human judgment remains final.",
    "Source provenance remains visible.",
    "Audit and export readiness must not overpromise implementation readiness.",
)

_SPRINT138_DOES_NOT_BUILD: tuple[str, ...] = (
    "no export creation",
    "no audit record creation",
    "no retention policy change",
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

_M1_AUDIT_EXPORT_SOVEREIGNTY_READINESS_EXIT_CRITERIA: tuple[str, ...] = (
    "All eighteen audit and sovereignty readiness field groups are documented with purposes and acceptance "
    "criteria.",
    "All eight audit and sovereignty readiness statuses include explicit not export execution, not audit record "
    "creation, and not retention policy change disclaimers.",
    "All twelve M1 audit export and sovereignty readiness foundations include operator focus statements without "
    "runtime execution.",
    "All eleven audit export readiness by product area rows include preview mapping language and caveat "
    "expectations.",
    "Sovereignty control prerequisite rules, access and export rules, sovereignty and trust requirements, and "
    "preview-only rules are listed.",
    "Risks and mitigations are recorded with operator discipline expectations for controlled build planning.",
    "Sprint 139 recommendation is captured as the next preview-only pilot operations and support readiness step.",
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "Export creation is implied by planning language",
        "Pair export language with explicit no export creation statements until a later authorized sprint.",
    ),
    (
        "Audit record creation is implied too early",
        "Repeat not audit record creation beside every audit readiness status and in non-production disclaimers.",
    ),
    (
        "Retention policy change is implied too early",
        "Keep retention readiness descriptive and restate not retention policy change in operator rules.",
    ),
    (
        "Customer data access is implied too early",
        "Sequence access review prerequisites before any customer-specific handling language in readiness rows.",
    ),
    (
        "No-training consent is missing",
        "Require no-training consent fields before AI-adjacent build planning language hardens.",
    ),
    (
        "Access controls are under-scoped",
        "Block readiness improvements until access control prerequisites name roles and review checkpoints.",
    ),
    (
        "Source provenance is lost in export planning",
        "Mandate provenance requirements on every export package row and in export format expectations.",
    ),
    (
        "Sovereignty language becomes marketing instead of control",
        "Bind sovereignty statements to verifiable prerequisites, blockers, and evidence expectations only.",
    ),
    (
        "Audit and export readiness becomes theater instead of control",
        "Require traceable identities, explicit blockers, risk notes, and acceptance criteria alongside every status.",
    ),
)

_SPRINT139_RECOMMENDED_NEXT_STEP = (
    "Sprint 139 should deliver the M1 Pilot Operations and Support Controlled Build Readiness Packet, still "
    "preview-only unless the operator explicitly authorizes runtime work."
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _field_group_payloads() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, (name, purpose, criteria) in enumerate(_AUDIT_SOVEREIGNTY_READINESS_FIELD_GROUP_ROWS, start=1):
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
        {"foundation_area": a, "operator_focus": b} for a, b in _M1_AUDIT_EXPORT_SOVEREIGNTY_READINESS_FOUNDATIONS
    ]


def _status_payloads() -> list[dict[str, str]]:
    return [{"status": s, "definition": d} for s, d in _AUDIT_SOVEREIGNTY_READINESS_STATUS_ROWS]


def _product_area_payloads() -> list[dict[str, str]]:
    return [
        {"product_area": a, "audit_export_readiness_preview": b} for a, b in _AUDIT_EXPORT_READINESS_BY_PRODUCT_AREA
    ]


def _risk_payloads() -> list[dict[str, str]]:
    return [{"risk": r, "mitigation": m} for r, m in _RISK_MITIGATIONS]


def build_active_source_activation_m1_audit_export_sovereignty_controlled_build_readiness_packet() -> (
    dict[str, Any]
):
    """Return the Sprint 138 M1 audit export and sovereignty controlled build readiness packet (deterministic)."""
    proof = {
        "sprint_138_m1_audit_export_sovereignty_controlled_build_readiness_packet_is_stateless": True,
        "sprint_138_m1_audit_export_sovereignty_controlled_build_readiness_packet_is_side_effect_free": True,
        "sprint_138_m1_audit_export_sovereignty_controlled_build_readiness_packet_is_preview_only": True,
        "sprint_138_m1_audit_export_sovereignty_controlled_build_readiness_packet_performs_no_runtime_work": True,
        "sprint_138_m1_audit_export_sovereignty_controlled_build_readiness_packet_emits_operator_planning_only": True,
    }
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 138,
        "packet_name": "NativeForge M1 Audit Export and Sovereignty Controlled Build Readiness Packet",
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_define_audit_export_readiness": True,
        "may_define_sovereignty_control_prerequisites": True,
        "may_define_access_and_retention_requirements": True,
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
        "actual_exports_created": 0,
        "actual_audit_records_created": 0,
        "actual_retention_policies_changed": 0,
        "m1_audit_export_sovereignty_controlled_build_readiness_foundations": _foundation_payloads(),
        "audit_sovereignty_readiness_field_groups": _field_group_payloads(),
        "audit_sovereignty_readiness_statuses": _status_payloads(),
        "audit_sovereignty_readiness_status_universal_disclaimer": _STATUS_DISCLAIMER,
        "preview_only_audit_export_and_sovereignty_rules": list(_PREVIEW_ONLY_AUDIT_EXPORT_AND_SOVEREIGNTY_RULES),
        "audit_export_readiness_by_product_area": _product_area_payloads(),
        "sovereignty_control_prerequisite_rules": list(_SOVEREIGNTY_CONTROL_PREREQUISITE_RULES),
        "access_retention_and_export_rules": list(_ACCESS_RETENTION_AND_EXPORT_RULES),
        "sovereignty_and_trust_requirements": list(_SOVEREIGNTY_AND_TRUST_REQUIREMENTS),
        "sprint_138_does_not_build": list(_SPRINT138_DOES_NOT_BUILD),
        "m1_audit_export_sovereignty_readiness_exit_criteria": list(_M1_AUDIT_EXPORT_SOVEREIGNTY_READINESS_EXIT_CRITERIA),
        "risks_and_mitigations": _risk_payloads(),
        "sprint_139_recommended_next_step": _SPRINT139_RECOMMENDED_NEXT_STEP,
        "sprint_138_m1_audit_export_sovereignty_controlled_build_readiness_packet_proof": proof,
    }
    return _json_safe(out)


def _ordered_field_groups(pkt: dict[str, Any]) -> list[dict[str, Any]]:
    raw = pkt.get("audit_sovereignty_readiness_field_groups")
    if isinstance(raw, list):
        groups = [g for g in raw if isinstance(g, dict)]
        groups.sort(key=lambda g: g.get("priority") if isinstance(g.get("priority"), int) else 0)
        return groups
    return _field_group_payloads()


def render_active_source_activation_m1_audit_export_sovereignty_controlled_build_readiness_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render the operator-facing markdown packet (deterministic; uses ``packet`` when provided)."""
    pkt = packet if isinstance(packet, dict) else (
        build_active_source_activation_m1_audit_export_sovereignty_controlled_build_readiness_packet()
    )
    groups = _ordered_field_groups(pkt)
    lines: list[str] = [
        "# NativeForge M1 Audit Export and Sovereignty Controlled Build Readiness Packet v1",
        "",
        "## 1. Purpose",
        "",
        "This packet defines the M1 planning layer for audit export and sovereignty controlled build readiness. It "
        "is preview-only: it structures audit event scope, export package expectations, data ownership statements, "
        "retention and access prerequisites, provenance, AI disclosure, no-training consent, human gates, "
        "security and sovereignty proof points, and acceptance criteria for operators without export execution, "
        "audit record creation, retention policy change, external calls, scraping, form submission, or customer "
        "data access.",
        "",
        "## 2. Why This Comes After Human Review Workflow Readiness",
        "",
        "Sprint 137 defined human review workflow readiness so reviewers, routing, evidence, override rules, audit "
        "expectations, sovereignty, and security dependencies stay visible before submission-adjacent language "
        "hardens. Sprint 138 applies controlled build discipline to the trust, auditability, exportability, and "
        "sovereignty proof layer so audit and export work cannot be trusted until ownership, retention, access, "
        "provenance, AI disclosure, no-training consent, human gates, sovereignty and security dependencies, and "
        "blockers are visible—still without export execution, audit record creation, retention policy change, or "
        "runtime activation in this sprint.",
        "",
        "## 3. M1 Audit Export and Sovereignty Readiness Objective",
        "",
        "Deliver a preview-only readiness framework that prevents audit and export implementation before ownership, "
        "retention, access, provenance, AI disclosure, no-training consent, human gates, sovereignty and security "
        "dependencies, and blockers are visible—without runnable export promises, export creation, audit record "
        "creation, retention policy change, customer data access, or external calls in this sprint.",
        "",
        "M1 audit export and sovereignty controlled build readiness foundations:",
        "",
    ]
    foundations = pkt.get("m1_audit_export_sovereignty_controlled_build_readiness_foundations")
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
            "## 4. Preview-Only Audit Export and Sovereignty Rules",
            "",
        ]
    )
    for rule in pkt.get("preview_only_audit_export_and_sovereignty_rules") or list(
        _PREVIEW_ONLY_AUDIT_EXPORT_AND_SOVEREIGNTY_RULES
    ):
        if isinstance(rule, str) and rule.strip():
            lines.append(f"- {rule}")
    lines.extend(
        [
            "",
            "Preview-only audit export and sovereignty rules restated: seeded or demo-safe records only; no real "
            "customer data; no export creation; no audit record creation; no retention policy change; no external "
            "calls.",
            "",
            "## 5. Required Audit/Sovereignty Readiness Field Groups",
            "",
            "Eighteen field groups structure every audit and sovereignty readiness row:",
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
            "## 6. Audit/Sovereignty Readiness Status Definitions",
            "",
            "Eight preview-only audit and sovereignty readiness statuses apply. Each status explicitly disclaims "
            "export execution, audit record creation, and retention policy change:",
            "",
        ]
    )
    statuses = pkt.get("audit_sovereignty_readiness_statuses")
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
    lines.extend(["", "## 8. Audit Export Readiness by Product Area", ""])
    mapping = pkt.get("audit_export_readiness_by_product_area")
    if not isinstance(mapping, list):
        mapping = _product_area_payloads()
    for row in mapping:
        if not isinstance(row, dict):
            continue
        ar = row.get("product_area")
        preview = row.get("audit_export_readiness_preview")
        if isinstance(ar, str) and isinstance(preview, str):
            lines.append(f"- **{ar}**: {preview}")
    lines.extend(["", "## 9. Sovereignty Control Prerequisite Rules", ""])
    for item in pkt.get("sovereignty_control_prerequisite_rules") or list(_SOVEREIGNTY_CONTROL_PREREQUISITE_RULES):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 10. Access, Retention, and Export Rules", ""])
    for item in pkt.get("access_retention_and_export_rules") or list(_ACCESS_RETENTION_AND_EXPORT_RULES):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 11. Sovereignty and Trust Requirements", ""])
    for item in pkt.get("sovereignty_and_trust_requirements") or list(_SOVEREIGNTY_AND_TRUST_REQUIREMENTS):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 12. What Sprint 138 Does Not Build", "", "Sprint 138 explicitly does not build:", ""])
    for item in pkt.get("sprint_138_does_not_build") or list(_SPRINT138_DOES_NOT_BUILD):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 13. M1 Audit Export and Sovereignty Readiness Exit Criteria",
            "",
        ]
    )
    for c in pkt.get("m1_audit_export_sovereignty_readiness_exit_criteria") or list(
        _M1_AUDIT_EXPORT_SOVEREIGNTY_READINESS_EXIT_CRITERIA
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
            "## 15. Sprint 139 Recommended Next Step",
            "",
            pkt.get("sprint_139_recommended_next_step") or _SPRINT139_RECOMMENDED_NEXT_STEP,
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
