"""Sprint 126: M0 data sovereignty policy and export preview planning packet (preview-only).

Deterministic operator packet for demo-safe sovereignty and export readiness previews. No real export,
no customer data access, no policy or retention changes, no legal advice, and no production governance.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = "nf_active_source_activation_m0_data_sovereignty_policy_export_preview_planning_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

M0_SOVEREIGNTY_AND_EXPORT_PREVIEW_FOUNDATIONS: tuple[str, ...] = (
    "Tribe/customer-owned data policy preview",
    "No-training-without-consent policy preview",
    "Export readiness preview",
    "Audit log readiness preview",
    "Retention policy preview",
    "Human review and approval workflow",
    "Data provenance visibility",
    "Sensitive identifier handling preview",
    "Future tenant data governance readiness",
    "Future private deployment readiness",
)

_FIELD_GROUP_ROWS: tuple[tuple[str, str, tuple[str, str]], ...] = (
    (
        "Customer data ownership statement",
        "Buyer-visible statement that the tribe or customer owns its data and NativeForge acts as a "
        "processor or operator only within agreed boundaries in future runtime designs.",
        (
            "Ownership language must name the customer or tribe as the data owner without implying "
            "NativeForge ownership of customer records.",
            "Seeded demo copies must watermark preview-only posture and forbid production data extracts.",
        ),
    ),
    (
        "No model training without explicit written consent",
        "Clear preview field stating that customer or tribal data must not train models without separate "
        "written consent in future runtime contracts.",
        (
            "Consent language must be visible in operator packets and future buyer-facing surfaces.",
            "M0 demos must repeat that no training occurs from customer data without explicit written consent.",
        ),
    ),
    (
        "Export availability statement",
        "Planning statement describing that future runtime export may exist without claiming current "
        "export buttons or file generation in M0.",
        (
            "Statements must distinguish future capability from today's preview-only posture.",
            "Export availability copy must never imply a downloadable file is produced in this sprint.",
        ),
    ),
    (
        "Export content categories",
        "Enumerated demo-safe categories such as entity profile, opportunity summaries, checklist rows, "
        "pipeline cards, and audit metadata placeholders.",
        (
            "Categories are visible in previews without creating files or touching production stores.",
            "Category lists must label seeded or demo data separately from production data.",
        ),
    ),
    (
        "Audit log availability statement",
        "Forward-looking description that future runtime actions should be auditable without asserting "
        "live audit streams today.",
        (
            "Statements pair with zero actual runtime writes and zero actual customer data access in M0.",
            "Audit language must not claim SOC2 or legal compliance solely from planning artifacts.",
        ),
    ),
    (
        "Data retention policy preview",
        "Demo-safe narrative of how retention might be described to buyers without changing retention "
        "settings or timers.",
        (
            "Retention previews must state that settings are unchanged during M0 planning demos.",
            "Ambiguous retention seeds route to human review before buyer-ready language ships.",
        ),
    ),
    (
        "Deletion request policy preview",
        "Planning copy for how deletion requests could be honored in future runtime without executing "
        "deletions in M0.",
        (
            "Deletion previews forbid destructive verbs against production databases in this sprint.",
            "Deletion language must align with customer-owned data statements and correction notes.",
        ),
    ),
    (
        "Sensitive identifier handling",
        "Rules for masking, segregating, or omitting sensitive identifiers in demos and future designs.",
        (
            "Handling rules require human review before any production identifier processing ships.",
            "Demo fixtures must avoid real government IDs, bank tokens, or personal health data.",
        ),
    ),
    (
        "User role and access preview",
        "Lightweight RBAC storytelling for buyers without provisioning real tenants or directories.",
        (
            "Role previews use seeded labels only and must not sync HRIS or production IAM.",
            "Elevated access stories require dual-control and human review in specifications.",
        ),
    ),
    (
        "Human review requirement",
        "Mandatory gate that policy and export previews require human approval before runtime claims.",
        (
            "Generated or templated policy language must route through human review in future designs.",
            "Operators cannot skip human review gates when ambiguity exists in seeded policy content.",
        ),
    ),
    (
        "AI disclosure statement",
        "Visible disclosure that AI may assist in future runtime and that M0 emits no AI generations.",
        (
            "Disclosures must appear wherever AI assistance is contemplated in roadmap language.",
            "This sprint performs zero actual AI generations and the packet must restate that fact.",
        ),
    ),
    (
        "Source provenance retention",
        "Requirement that source lineage for summaries and previews remains visible to users in designs.",
        (
            "Provenance metadata must survive export planning discussions without implying live exports.",
            "Loss of provenance blocks preview-ready claims until human correction notes document recovery.",
        ),
    ),
    (
        "Customer data boundary statement",
        "Description of logical and physical boundaries between NativeForge operator data and customer "
        "data in future architectures.",
        (
            "Boundary statements must not access real customer partitions during M0 demos.",
            "Cross-boundary flows require explicit future authorization and audit design.",
        ),
    ),
    (
        "Private deployment future option",
        "Roadmap language that larger customers may need private deployment without promising dates or "
        "SLAs in M0.",
        (
            "Private deployment copy must avoid overpromising timelines, regions, or certifications.",
            "Optionality remains clearly separated from current shared-environment M0 demos.",
        ),
    ),
    (
        "Third-party data sharing restriction",
        "Restriction preview that customer data must not be sold or shared with third parties without "
        "contractual gates.",
        (
            "Restrictions are planning statements only and do not configure enforcement in this sprint.",
            "Planned integrations list must avoid silent data resale language.",
        ),
    ),
    (
        "Security and access control preview",
        "High-level security posture storytelling without implying penetration test results or live SOC "
        "reports.",
        (
            "Security previews reference principles like least privilege without binding legal warranties.",
            "Access control previews cannot enable production tenant administration from this packet.",
        ),
    ),
    (
        "Policy acceptance notes",
        "Structured notes capturing that buyers must formally accept future policies outside this "
        "planning artifact.",
        (
            "Notes must state this packet is not a clickwrap or legal acceptance instrument.",
            "Acceptance pathways defer to future legal and product workflows beyond Sprint 126.",
        ),
    ),
    (
        "Human correction notes",
        "Operator and reviewer annotations preserved alongside policy preview fields for auditability.",
        (
            "Correction notes must be preserved in future runtime governance designs.",
            "Notes cannot erase underlying seeded provenance or consent disclosure requirements.",
        ),
    ),
)

_SOVEREIGNTY_PREVIEW_TO_M0_FEATURES: tuple[tuple[str, str], ...] = (
    (
        "Organizational entity profile",
        "Ownership and boundary statements attach to seeded entity profiles without accessing production "
        "directories.",
    ),
    (
        "Seeded opportunity records",
        "Export category previews and retention language reference demo opportunities only.",
    ),
    (
        "SF-424 preview",
        "Consent, disclosure, and sensitive handling previews align with autofill preview posture from "
        "prior sprints.",
    ),
    (
        "Requirement checklist preview",
        "Checklist rows inherit provenance visibility and human review requirements from Sprint 125 "
        "planning.",
    ),
    (
        "Pursuit pipeline preview",
        "Pipeline cards show audit and export readiness hooks without creating tasks or exports.",
    ),
    (
        "Audit and export readiness",
        "Forward-looking auditability and export category visibility without runtime export engines.",
    ),
    (
        "Source provenance display",
        "Provenance retention fields ensure summaries remain traceable in buyer education flows.",
    ),
    (
        "Human review workflow",
        "Human review requirement and correction notes bind policy previews to approval paths.",
    ),
    (
        "Future tenant governance",
        "Tenant RBAC, retention, and deletion previews inform later governance engines without building "
        "them now.",
    ),
)

_EXPORT_PREVIEW_RULES: tuple[str, ...] = (
    "Export preview must be demo-safe and use seeded or synthetic policy content only.",
    "Export categories must be visible to buyers without implying a file was created.",
    "Export preview must not create a file on disk or in object storage during M0 planning.",
    "Export preview must not access customer data or production partitions.",
    "Export readiness must distinguish seeded or demo data from production data with explicit labels.",
    "No external storage integration occurs in M0 planning for export previews.",
)

_AI_USAGE_AND_CONSENT_RULES: tuple[str, ...] = (
    "No model training on customer data without explicit written consent in future contracts.",
    "AI disclosure must be visible wherever AI assistance is referenced in roadmap language.",
    "Generated content in future runtime must require human review before buyer reliance.",
    "Customer data cannot be hidden behind opaque AI workflows in future designs.",
    "Future runtime AI usage must be auditable and attributable in planning commitments.",
    "No AI generation occurs in this sprint; actual_ai_generations remains zero.",
)

_HUMAN_REVIEW_GATES: tuple[str, ...] = (
    "Policy preview cannot be treated as legal advice; counsel must review buyer-facing contracts.",
    "Export preview cannot be treated as an actual export or compliance deliverable.",
    "Retention preview cannot change retention settings or imply timers were modified.",
    "Sensitive identifier handling must be reviewed before production engineering proceeds.",
    "Human correction notes must be preserved in future runtime governance and export designs.",
    "Buyer-facing policy language must remain reviewable and editable after Sprint 126 planning.",
)

_SOVEREIGNTY_AND_TRUST: tuple[str, ...] = (
    "The customer or tribe owns its data; NativeForge surfaces are planning-only in M0.",
    "No customer data is required for seeded sovereignty and export policy demos.",
    "No customer data leaves the product during seeded demos for this planning layer.",
    "No model training on customer data without explicit written consent remains a hard planning rule.",
    "Future runtime export must be auditable and repeatable per export readiness commitments.",
    "Source provenance must remain visible to the user across summaries, checklists, and previews.",
    "A future private deployment option should remain on the roadmap for larger customers without "
    "promising delivery dates.",
)

_SPRINT126_DOES_NOT_BUILD: tuple[str, ...] = (
    "No real data export",
    "No customer data access",
    "No policy setting change",
    "No retention setting change",
    "No database migration",
    "No frontend UI",
    "No API route",
    "No tenant administration",
    "No legal advice",
    "No external storage integration",
    "No runtime governance engine",
    "No production data governance change",
)

_M0_EXIT_CRITERIA: tuple[str, ...] = (
    "All eighteen policy field groups are defined with purposes and at least two acceptance criteria each.",
    "Demo-safe sovereignty rules, export preview rules, AI usage rules, and human review gates are "
    "documented in markdown and JSON.",
    "Sovereignty preview to M0 feature mapping covers entity profile through future tenant governance.",
    "Risks and mitigations are enumerated for operator review before implementation sprints.",
    "Sprint 127 next step is recorded as the M0 Human Review Gates and Demo Closeout Planning Packet.",
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "Policy preview is mistaken for legal advice",
        "Banner preview-only language, defer to counsel, and separate planning artifacts from contracts.",
    ),
    (
        "Export preview is mistaken for actual export",
        "Label previews as non-file-generating, repeat no real data export, and show category lists only.",
    ),
    (
        "Customer data ownership is not explicit enough",
        "Lead with customer data ownership statement field group and seeded watermark copy.",
    ),
    (
        "AI training consent is buried or unclear",
        "Surface explicit written consent language in field groups, markdown, and buyer education scripts.",
    ),
    (
        "Source provenance is not retained",
        "Bind provenance retention field group to checklist and summary previews with human review gates.",
    ),
    (
        "Retention preview implies settings changed",
        "Pair retention previews with explicit no retention setting change statements and planning verbs.",
    ),
    (
        "Sensitive identifiers are handled too casually",
        "Require human review gate and masking rules before any identifier engineering proceeds.",
    ),
    (
        "Seeded data is confused with customer data",
        "Label fixtures as seeded or demo, segregate environments, and forbid production extracts in M0.",
    ),
    (
        "Private deployment expectations are overpromised",
        "Keep private deployment language optional, non-binding, and separated from current shared demos.",
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


def _mapping_payloads() -> list[dict[str, str]]:
    return [
        {"m0_surface_area": a, "sovereignty_policy_preview_use": u} for a, u in _SOVEREIGNTY_PREVIEW_TO_M0_FEATURES
    ]


def _risk_payloads() -> list[dict[str, str]]:
    return [{"risk": r, "mitigation": m} for r, m in _RISK_MITIGATIONS]


def build_active_source_activation_m0_data_sovereignty_policy_export_preview_planning_packet() -> (
    dict[str, Any]
):
    """Return the Sprint 126 M0 data sovereignty and export preview planning packet (deterministic)."""
    proof = {
        "sprint_126_m0_data_sovereignty_export_preview_planning_packet_is_stateless": True,
        "sprint_126_m0_data_sovereignty_export_preview_planning_packet_is_side_effect_free": True,
        "sprint_126_m0_data_sovereignty_export_preview_planning_packet_is_preview_only": True,
        "sprint_126_m0_data_sovereignty_export_preview_planning_packet_performs_no_runtime_work": True,
        "sprint_126_m0_data_sovereignty_export_preview_planning_packet_emits_operator_planning_only": True,
    }
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 126,
        "packet_name": "NativeForge M0 Data Sovereignty Policy and Export Preview Planning Packet",
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_define_sovereignty_policy_scope": True,
        "may_define_demo_safe_export_fields": True,
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
        "actual_policy_changes": 0,
        "actual_retention_changes": 0,
        "m0_sovereignty_and_export_preview_foundations": list(M0_SOVEREIGNTY_AND_EXPORT_PREVIEW_FOUNDATIONS),
        "policy_field_groups": _field_group_payloads(),
        "sovereignty_preview_to_m0_feature_mapping": _mapping_payloads(),
        "export_preview_rules": list(_EXPORT_PREVIEW_RULES),
        "ai_usage_and_consent_rules": list(_AI_USAGE_AND_CONSENT_RULES),
        "human_review_gates": list(_HUMAN_REVIEW_GATES),
        "sovereignty_and_trust_requirements": list(_SOVEREIGNTY_AND_TRUST),
        "sprint_126_does_not_build": list(_SPRINT126_DOES_NOT_BUILD),
        "m0_sovereignty_export_planning_exit_criteria": list(_M0_EXIT_CRITERIA),
        "risks_and_mitigations": _risk_payloads(),
        "sprint_126_m0_data_sovereignty_export_preview_planning_packet_proof": proof,
    }
    return _json_safe(out)


def _ordered_field_groups(pkt: dict[str, Any]) -> list[dict[str, Any]]:
    raw = pkt.get("policy_field_groups")
    if isinstance(raw, list):
        groups = [g for g in raw if isinstance(g, dict)]
        groups.sort(key=lambda g: g.get("priority") if isinstance(g.get("priority"), int) else 0)
        return groups
    return _field_group_payloads()


def render_active_source_activation_m0_data_sovereignty_policy_export_preview_planning_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render the operator-facing markdown packet (deterministic; uses ``packet`` when provided)."""
    pkt = packet if isinstance(packet, dict) else (
        build_active_source_activation_m0_data_sovereignty_policy_export_preview_planning_packet()
    )
    groups = _ordered_field_groups(pkt)
    lines: list[str] = [
        "# NativeForge M0 Data Sovereignty Policy and Export Preview Planning Packet v1",
        "",
        "## 1. Purpose",
        "",
        "This packet defines the M0 planning layer for demo-safe data sovereignty policy and export "
        "readiness previews. It helps buyers understand ownership, consent, exportability, auditability, "
        "retention, sensitive data handling, and human review expectations without exporting real data, "
        "accessing customer data, changing policies, providing legal advice, or operating production "
        "tenant controls.",
        "",
        "## 2. Why This Comes After Requirement Checklist Planning",
        "",
        "Sprint 125 defined requirement checklist preview readiness from seeded summaries and opportunities "
        "without real NOFO parsing or production tasks. Sprint 126 defines the trust layer that must be "
        "visible before NativeForge can credibly demo buyer-owned data, exportability, provenance, and AI "
        "usage boundaries alongside those previews.",
        "",
        "## 3. M0 Sovereignty Preview Objective",
        "",
        "Deliver a demo-safe policy preview that helps a buyer understand ownership, consent, "
        "exportability, auditability, retention, sensitive data handling, and human review expectations "
        "while keeping all content seeded or synthetic and all actions preview-only.",
        "",
        "## 4. Demo-Safe Sovereignty Rules",
        "",
        "M0 sovereignty and export previews require seeded or demo-safe policy content only. Previews "
        "must include no real customer data, generate no exports, change no policies or retention, provide "
        "no legal advice, open no production tenant controls, and perform no external calls while "
        "presenting this posture.",
        "",
        "Demo-safe sovereignty restrictions restated: no real customer data; no export generation; no "
        "policy changes; no legal advice; no production tenant controls; no external calls.",
        "",
        "## 5. Required Policy Field Groups",
        "",
        "Eighteen field groups structure sovereignty and export preview planning:",
        "",
    ]
    for g in groups:
        if not isinstance(g, dict):
            continue
        name = g.get("name")
        purpose = g.get("purpose")
        if isinstance(name, str) and isinstance(purpose, str):
            lines.append(f"- **{name}**: {purpose}")
    lines.extend(["", "## 6. Field-Level Acceptance Criteria", ""])
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
    lines.extend(["", "## 7. Sovereignty Preview to M0 Feature Mapping", ""])
    mapping = pkt.get("sovereignty_preview_to_m0_feature_mapping")
    if not isinstance(mapping, list):
        mapping = _mapping_payloads()
    for row in mapping:
        if not isinstance(row, dict):
            continue
        area = row.get("m0_surface_area")
        use = row.get("sovereignty_policy_preview_use")
        if isinstance(area, str) and isinstance(use, str):
            lines.append(f"- **{area}**: {use}")
    lines.extend(["", "## 8. Export Preview Rules", ""])
    for item in pkt.get("export_preview_rules") or list(_EXPORT_PREVIEW_RULES):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 9. AI Usage and Consent Rules", ""])
    for item in pkt.get("ai_usage_and_consent_rules") or list(_AI_USAGE_AND_CONSENT_RULES):
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
    lines.extend(["", "## 12. What Sprint 126 Does Not Build", "", "Sprint 126 explicitly does not build:", ""])
    for item in pkt.get("sprint_126_does_not_build") or list(_SPRINT126_DOES_NOT_BUILD):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 13. M0 Exit Criteria for Sovereignty and Export Planning",
            "",
        ]
    )
    for c in pkt.get("m0_sovereignty_export_planning_exit_criteria") or list(_M0_EXIT_CRITERIA):
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
            "## 15. Sprint 127 Recommended Next Step",
            "",
            "Sprint 127 should deliver the M0 Human Review Gates and Demo Closeout Planning Packet, still "
            "preview-only and demo-safe unless the operator explicitly authorizes runtime work.",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
