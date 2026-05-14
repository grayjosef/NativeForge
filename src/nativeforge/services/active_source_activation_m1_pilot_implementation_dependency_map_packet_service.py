"""Sprint 132: M1 pilot implementation dependency map packet (preview-only).

Deterministic operator packet that maps implementation dependencies, ownership, sequencing, blockers,
guardrails, and acceptance criteria before controlled build planning—without dependency installation,
workflow activation, external calls, or customer data access.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = "nf_active_source_activation_m1_pilot_implementation_dependency_map_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

_STATUS_DISCLAIMER = (
    "This status is not runtime activation, is not dependency installation, and is not customer "
    "configuration."
)

_M1_IMPLEMENTATION_DEPENDENCY_MAP_FOUNDATIONS: tuple[tuple[str, str], ...] = (
    (
        "Dependency inventory",
        "Lists every implementation dependency row with identity, category, and preview-only evidence "
        "labels before build work is sequenced.",
    ),
    (
        "Dependency ownership",
        "Assigns buyer-owned versus operator-owned accountability so unresolved ownership surfaces as a "
        "build blocker.",
    ),
    (
        "Dependency sequencing",
        "Orders prerequisites so sovereignty, security, ingestion, extraction, review, and export work "
        "stay visible before dependent steps.",
    ),
    (
        "Build readiness signals",
        "Defines operator-visible signals for when mapping is sufficient to inform controlled build "
        "planning without implying go-live.",
    ),
    (
        "Blocker tracking",
        "Captures explicit blockers, deferrals, and rationale so hidden dependencies cannot enter the "
        "pilot silently.",
    ),
    (
        "Source ingestion dependencies",
        "Separates live Grants.gov or partner feed requirements from seeded or demo-safe fixtures for M1.",
    ),
    (
        "NOFO extraction dependencies",
        "Documents parser coverage, traceability, confidence labeling, and review hooks required before "
        "form automation assumptions.",
    ),
    (
        "Form package dependencies",
        "Captures SF-424 field coverage, signing boundaries, and non-submission posture as planning-only "
        "inputs.",
    ),
    (
        "Human review workflow dependencies",
        "States reviewer roles, cadence, escalations, and audit expectations before submission-adjacent "
        "work is sequenced.",
    ),
    (
        "Data sovereignty dependencies",
        "Records residency, export, retention, and consent prerequisites so data handling cannot be "
        "assumed ready.",
    ),
    (
        "Security/access dependencies",
        "Captures identity, least privilege, secrets handling, and logging prerequisites without implying "
        "certification.",
    ),
    (
        "Export/audit dependencies",
        "Maps export controls, audit log expectations, and access reviews before pilot closeout planning.",
    ),
)

_DEPENDENCY_FIELD_GROUP_ROWS: tuple[tuple[str, str, tuple[str, str]], ...] = (
    (
        "Dependency item identity",
        "Stable id, title, and version for each dependency row across operator artifacts.",
        (
            "Identity strings remain identical across repeated packet generations.",
            "Each dependency row exposes a single primary identity key for traceability.",
        ),
    ),
    (
        "Product area",
        "Maps the dependency to a product area such as ingestion, NOFO parsing, or form preview for M1.",
        (
            "Product areas align to the dependency map by product area section in this packet.",
            "Each row lists exactly one primary product area to avoid ambiguous merges.",
        ),
    ),
    (
        "Dependency category",
        "Classifies the dependency as technical, data, sovereignty, security, review, or external-system "
        "planning.",
        (
            "Categories use planning language and never imply runtime activation or installation.",
            "External system categories remain preview-only in this sprint.",
        ),
    ),
    (
        "Dependency owner",
        "Names buyer-owned, operator-owned, or owner-needed accountability for the dependency row.",
        (
            "Unresolved ownership maps to Needs owner assignment or an explicit owner-needed label.",
            "Buyer-owned rows are visibly distinct from operator-owned rows.",
        ),
    ),
    (
        "Required input",
        "Lists documents, fixtures, policies, or demo data required before the dependency can advance.",
        (
            "Inputs reference seeded or demo-safe sources only in this sprint.",
            "Inputs never require production customer extracts for planning.",
        ),
    ),
    (
        "Required decision",
        "Captures approvals, policy choices, or governance decisions that must precede build sequencing.",
        (
            "Decisions use preview-only verbs such as document or map, not deploy or activate.",
            "Decisions pair with blocker status when work cannot proceed.",
        ),
    ),
    (
        "Technical prerequisite",
        "Captures engineering unknowns, integration limits, or discovery work before implementation.",
        (
            "Technical prerequisites must not hide sovereignty or security prerequisites.",
            "Technical rows forbid database migrations, API routes, or UI build claims from this sprint.",
        ),
    ),
    (
        "Data prerequisite",
        "States schemas, minimization, retention, and fixture assumptions required for honest mapping.",
        (
            "Data prerequisites repeat that no real customer data is required for this sprint.",
            "Prerequisites distinguish demo fixtures from future production data handling.",
        ),
    ),
    (
        "Security prerequisite",
        "Captures authentication, authorization, secrets, and threat-model gaps before build planning.",
        (
            "Open security prerequisites block build readiness until resolved or deferred with rationale.",
            "Prerequisites forbid implying certifications not evidenced elsewhere.",
        ),
    ),
    (
        "Sovereignty prerequisite",
        "Lists residency, export, retention, and consent questions that affect sequencing and trust.",
        (
            "Sovereignty prerequisites remain visible before any customer data handling is sequenced.",
            "Prerequisites never assert private deployment unless separately approved in writing.",
        ),
    ),
    (
        "Human review prerequisite",
        "Defines mandatory human checkpoints for eligibility, forms, or narrative outputs in M1 mapping.",
        (
            "Submission-adjacent dependencies require visible human review prerequisites.",
            "Prerequisites distinguish scoped review from routed production workflows.",
        ),
    ),
    (
        "External system dependency",
        "Documents partner systems, feeds, or credentials needed later while staying preview-only here.",
        (
            "External dependencies remain mapping-only with zero external calls from this sprint.",
            "Dependencies avoid overpromising integration timelines or guarantees.",
        ),
    ),
    (
        "Sequencing position",
        "States relative order constraints so sovereignty, ingestion, extraction, and review stay honest.",
        (
            "Sequencing repeats that no runtime activation occurs in this sprint.",
            "Positions surface conflicts when downstream work assumes hidden upstream readiness.",
        ),
    ),
    (
        "Blocker status",
        "Signals whether the dependency blocks controlled build planning until resolved or deferred.",
        (
            "Blocker language stays preview-only and does not install packages or activate workflows.",
            "Blocked rows require explicit rationale and ownership visibility.",
        ),
    ),
    (
        "Acceptance criteria",
        "Field-level pass or fail checks operators use before assigning a dependency status.",
        (
            "Each dependency row carries at least two criteria tied to evidence or explicit gap labels.",
            "Criteria reinforce preview-only posture and non-commitment language.",
        ),
    ),
    (
        "Risk note",
        "Captures misunderstanding, scope creep, sequencing theater, and trust risks for operators.",
        (
            "Risks call out confusion between planning packets and production readiness.",
            "Risks reference mitigations listed in the risks and mitigations section.",
        ),
    ),
    (
        "Non-production disclaimer",
        "Restates preview-only posture and lack of installation, activation, runtime authority, or config.",
        (
            "Disclaimers repeat not runtime activation, not dependency installation, and not customer "
            "configuration.",
            "Disclaimers appear wherever status language could be misread as go-live approval.",
        ),
    ),
    (
        "Next sprint recommendation",
        "Points operators to Sprint 133 controlled build sequencing in preview-only language.",
        (
            "Recommendations name Sprint 133 as the M1 Controlled Build Sequencing and Human Gate Packet.",
            "Recommendations forbid silent expansion into runtime work without explicit authorization.",
        ),
    ),
)

_DEPENDENCY_STATUS_ROWS: tuple[tuple[str, str], ...] = (
    (
        "Not mapped",
        "Dependency is visible as a gap and must be inventoried before sequencing claims. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Mapped for planning",
        "Dependency is documented with field groups sufficient for operator review without build promises. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Needs owner assignment",
        "Accountable buyer or operator owner is missing and must be named before build readiness improves. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Needs technical discovery",
        "Engineering or integration unknowns must be resolved before the dependency can sequence safely. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Needs buyer input",
        "Policy, data posture, or procurement input only the buyer can provide remains open. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Needs sovereignty review",
        "Residency, export, retention, or consent questions remain open for policy review. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Blocked before build",
        "Explicit blocker prevents controlled build planning from treating the row as ready. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Deferred beyond pilot",
        "Dependency is intentionally deferred past the pilot while remaining visible in the map. "
        + _STATUS_DISCLAIMER,
    ),
)

_PREVIEW_ONLY_DEPENDENCY_MAPPING_RULES: tuple[str, ...] = (
    "Require seeded or demo-safe records only; never import production customer extracts into dependency "
    "mapping.",
    "Do not access real customer data while building or reviewing this dependency map packet.",
    "Do not install software dependencies, language runtimes, or packages from this sprint packet.",
    "Do not activate workflows, runtime flags, or production environments from this sprint packet.",
    "Do not create customer configurations, tenant records, or onboarding flows from this sprint packet.",
    "Do not place external API calls, scrapes, live ingestions, or live AI generations while using this "
    "packet.",
    "Do not submit applications, forms, or e-signatures while using this packet.",
    "Keep human judgment, provenance visibility, sovereignty boundaries, and missing-data disclosure "
    "explicit.",
)

_M1_DEPENDENCY_MAP_BY_PRODUCT_AREA: tuple[tuple[str, str], ...] = (
    (
        "organizational entity profile",
        "Dependency map for tribal context fields, mission alignment inputs, and profile data handling "
        "before build sequencing.",
    ),
    (
        "live Grants.gov/source ingestion",
        "Dependency map for credentials, rate limits, monitoring, and live feed readiness versus demo "
        "fixtures.",
    ),
    (
        "manual NOFO upload",
        "Dependency map for buyer or operator supplied documents versus automated acquisition paths.",
    ),
    (
        "NOFO extraction and requirement parsing",
        "Dependency map for parser coverage, clause traceability, confidence labeling, and review hooks.",
    ),
    (
        "tribal eligibility and scoring",
        "Dependency map for non-final scoring posture, policy review, and buyer-visible caveats in M1.",
    ),
    (
        "pursuit pipeline",
        "Dependency map for pipeline stages, owners, deadlines, and reporting without assumed production "
        "writes.",
    ),
    (
        "SF-424/form package preview",
        "Dependency map for autofill mapping, signing limits, and submission-adjacent safeguards.",
    ),
    (
        "human review workflow",
        "Dependency map for reviewer roles, SLAs, escalations, and audit expectations as planning only.",
    ),
    (
        "data sovereignty and export",
        "Dependency map for residency, export controls, consent tracking, and customer-owned data handling.",
    ),
    (
        "audit logs and access control",
        "Dependency map for logging expectations, access reviews, and least-privilege design for M1.",
    ),
    (
        "pilot support and implementation operations",
        "Dependency map for support channels, runbooks, and implementation capacity without operational "
        "promises.",
    ),
)

_DEPENDENCY_OWNERSHIP_RULES: tuple[str, ...] = (
    "Every dependency must have an owner or an explicit owner-needed status; anonymous rows block build "
    "readiness.",
    "Buyer-owned dependencies must be labeled separately from operator-owned dependencies in the map.",
    "Technical dependencies must not hide sovereignty or security dependencies; all three remain visible.",
    "Unresolved ownership blocks build readiness until assigned or deferred with visible rationale.",
    "External system dependencies remain preview-only in this sprint with no outbound integration calls.",
)

_DEPENDENCY_SEQUENCING_RULES: tuple[str, ...] = (
    "Sovereignty and security dependencies must be visible before customer data handling is sequenced.",
    "Source ingestion dependencies must precede live discovery work in the documented order.",
    "NOFO extraction dependencies must precede form package automation assumptions in the map.",
    "Human review dependencies must precede submission-adjacent work in the documented order.",
    "Export and audit dependencies must be mapped before pilot closeout planning assumes readiness.",
    "No runtime activation occurs in this sprint; sequencing is documentation and operator discipline only.",
)

_SOVEREIGNTY_AND_TRUST_REQUIREMENTS: tuple[str, ...] = (
    "Customer owns its data.",
    "No customer data is required for this planning sprint.",
    "No customer data leaves the product during seeded demos.",
    "No model training on customer data without explicit written consent.",
    "Human judgment remains final.",
    "Source provenance remains visible.",
    "Dependency planning must not overpromise implementation readiness.",
)

_SPRINT132_DOES_NOT_BUILD: tuple[str, ...] = (
    "no dependency installation",
    "no workflow activation",
    "no customer configuration creation",
    "no pilot account creation",
    "no customer onboarding",
    "no customer data access",
    "no real application submission",
    "no production readiness certification",
    "no external service call",
    "no database migration",
    "no frontend UI",
    "no API route",
    "no production workflow change",
)

_M1_DEPENDENCY_MAP_EXIT_CRITERIA: tuple[str, ...] = (
    "All eighteen dependency field groups are documented with purposes and acceptance criteria.",
    "All eight dependency statuses include explicit non-activation, non-installation, and non-configuration "
    "disclaimers.",
    "All twelve implementation dependency map foundations include operator focus statements without "
    "runtime execution.",
    "All eleven dependency map by product area rows include mapping previews and caveat expectations.",
    "Ownership rules, sequencing rules, sovereignty requirements, and preview mapping rules are listed.",
    "Risks and mitigations are recorded with operator discipline expectations for controlled build planning.",
    "Sprint 133 recommendation is captured as the next preview-only controlled build sequencing step.",
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "Implementation begins without dependency ownership",
        "Force Needs owner assignment until buyer-owned and operator-owned labels exist with named "
        "accountability.",
    ),
    (
        "Technical dependencies hide sovereignty requirements",
        "Require parallel sovereignty and security field groups for any row touching data or residency.",
    ),
    (
        "Security review is skipped",
        "Block build readiness when authentication, secrets handling, or integrations lack documented "
        "prerequisites.",
    ),
    (
        "Source ingestion dependencies are assumed ready",
        "Keep live feed prerequisites visible and pair them with demo fixture limits until a written plan "
        "exists.",
    ),
    (
        "Human review dependency is ignored",
        "Insert human review prerequisites before any submission-adjacent sequencing claims in the map.",
    ),
    (
        "Customer configuration is implied",
        "Ban silent configuration language; restate preview-only posture in disclaimers and does-not-build "
        "lists.",
    ),
    (
        "External system integration is overpromised",
        "Label external system dependencies as preview-only mapping with no outbound calls from this "
        "sprint.",
    ),
    (
        "Build sequencing becomes theater instead of control",
        "Tie sequencing positions to explicit prerequisites, blockers, and acceptance criteria reviewers "
        "can audit.",
    ),
    (
        "Out-of-scope work enters pilot implementation silently",
        "Use Deferred beyond pilot and Blocked before build with rationale instead of hiding scope.",
    ),
)

_SPRINT133_RECOMMENDED_NEXT_STEP = (
    "Sprint 133 should deliver the M1 Controlled Build Sequencing and Human Gate Packet, still "
    "preview-only unless the operator explicitly authorizes runtime work."
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _field_group_payloads() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, (name, purpose, criteria) in enumerate(_DEPENDENCY_FIELD_GROUP_ROWS, start=1):
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
    return [{"foundation_area": a, "operator_focus": b} for a, b in _M1_IMPLEMENTATION_DEPENDENCY_MAP_FOUNDATIONS]


def _status_payloads() -> list[dict[str, str]]:
    return [{"status": s, "definition": d} for s, d in _DEPENDENCY_STATUS_ROWS]


def _product_area_payloads() -> list[dict[str, str]]:
    return [
        {"product_area": a, "dependency_map_preview": b} for a, b in _M1_DEPENDENCY_MAP_BY_PRODUCT_AREA
    ]


def _risk_payloads() -> list[dict[str, str]]:
    return [{"risk": r, "mitigation": m} for r, m in _RISK_MITIGATIONS]


def build_active_source_activation_m1_pilot_implementation_dependency_map_packet() -> dict[str, Any]:
    """Return the Sprint 132 M1 pilot implementation dependency map packet (deterministic)."""
    proof = {
        "sprint_132_m1_pilot_implementation_dependency_map_packet_is_stateless": True,
        "sprint_132_m1_pilot_implementation_dependency_map_packet_is_side_effect_free": True,
        "sprint_132_m1_pilot_implementation_dependency_map_packet_is_preview_only": True,
        "sprint_132_m1_pilot_implementation_dependency_map_packet_performs_no_runtime_work": True,
        "sprint_132_m1_pilot_implementation_dependency_map_packet_emits_operator_planning_only": True,
    }
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 132,
        "packet_name": "NativeForge M1 Pilot Implementation Dependency Map Packet",
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_define_implementation_dependency_map": True,
        "may_define_dependency_ownership": True,
        "may_define_dependency_sequencing": True,
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
        "actual_dependencies_installed": 0,
        "actual_workflows_activated": 0,
        "actual_customer_configurations_created": 0,
        "m1_implementation_dependency_map_foundations": _foundation_payloads(),
        "dependency_field_groups": _field_group_payloads(),
        "dependency_statuses": _status_payloads(),
        "dependency_status_universal_disclaimer": _STATUS_DISCLAIMER,
        "preview_only_dependency_mapping_rules": list(_PREVIEW_ONLY_DEPENDENCY_MAPPING_RULES),
        "m1_dependency_map_by_product_area": _product_area_payloads(),
        "dependency_ownership_rules": list(_DEPENDENCY_OWNERSHIP_RULES),
        "dependency_sequencing_rules": list(_DEPENDENCY_SEQUENCING_RULES),
        "sovereignty_and_trust_requirements": list(_SOVEREIGNTY_AND_TRUST_REQUIREMENTS),
        "sprint_132_does_not_build": list(_SPRINT132_DOES_NOT_BUILD),
        "m1_dependency_map_exit_criteria": list(_M1_DEPENDENCY_MAP_EXIT_CRITERIA),
        "risks_and_mitigations": _risk_payloads(),
        "sprint_133_recommended_next_step": _SPRINT133_RECOMMENDED_NEXT_STEP,
        "sprint_132_m1_pilot_implementation_dependency_map_packet_proof": proof,
    }
    return _json_safe(out)


def _ordered_field_groups(pkt: dict[str, Any]) -> list[dict[str, Any]]:
    raw = pkt.get("dependency_field_groups")
    if isinstance(raw, list):
        groups = [g for g in raw if isinstance(g, dict)]
        groups.sort(key=lambda g: g.get("priority") if isinstance(g.get("priority"), int) else 0)
        return groups
    return _field_group_payloads()


def render_active_source_activation_m1_pilot_implementation_dependency_map_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render the operator-facing markdown packet (deterministic; uses ``packet`` when provided)."""
    pkt = packet if isinstance(packet, dict) else (
        build_active_source_activation_m1_pilot_implementation_dependency_map_packet()
    )
    groups = _ordered_field_groups(pkt)
    lines: list[str] = [
        "# NativeForge M1 Pilot Implementation Dependency Map Packet v1",
        "",
        "## 1. Purpose",
        "",
        "This packet defines the M1 planning layer for implementation dependency mapping after pilot scope "
        "boundaries are defined. It is preview-only: it structures dependency inventory, ownership, "
        "sequencing, blockers, guardrails, and acceptance criteria for operators without installing "
        "dependencies, activating workflows, creating customer configurations, calling external services, or "
        "accessing customer data.",
        "",
        "## 2. Why This Comes After M1 Pilot Scope Boundary Planning",
        "",
        "Sprint 131 defined what is in and out of the M1 pilot scope with explicit delivery boundaries. "
        "Sprint 132 maps the implementation dependencies required before controlled build planning can begin, "
        "so owners, prerequisites, sequencing, blockers, and sovereignty or security dependencies stay visible "
        "before engineering work is implied.",
        "",
        "## 3. M1 Implementation Dependency Objective",
        "",
        "Deliver a preview-only dependency map that prevents implementation from starting before owners, "
        "prerequisites, sequencing, blockers, and sovereignty or security dependencies are visible—without "
        "runtime execution, dependency installation, workflow activation, customer configuration, or "
        "runnable build promises.",
        "",
        "M1 implementation dependency map foundations:",
        "",
    ]
    foundations = pkt.get("m1_implementation_dependency_map_foundations")
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
            "## 4. Preview-Only Dependency Mapping Rules",
            "",
        ]
    )
    for rule in pkt.get("preview_only_dependency_mapping_rules") or list(
        _PREVIEW_ONLY_DEPENDENCY_MAPPING_RULES
    ):
        if isinstance(rule, str) and rule.strip():
            lines.append(f"- {rule}")
    lines.extend(
        [
            "",
            "Preview-only dependency mapping rules restated: seeded or demo-safe records only; no real "
            "customer data; no dependency installation; no workflow activation; no customer configuration; "
            "no external calls.",
            "",
            "## 5. Required Dependency Field Groups",
            "",
            "Eighteen field groups structure every dependency map row:",
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
            "## 6. Dependency Status Definitions",
            "",
            "Eight preview-only dependency statuses apply. Each status explicitly disclaims runtime "
            "activation, dependency installation, and customer configuration:",
            "",
        ]
    )
    statuses = pkt.get("dependency_statuses")
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
    lines.extend(["", "## 8. Dependency Map by Product Area", ""])
    mapping = pkt.get("m1_dependency_map_by_product_area")
    if not isinstance(mapping, list):
        mapping = _product_area_payloads()
    for row in mapping:
        if not isinstance(row, dict):
            continue
        feat = row.get("product_area")
        focus = row.get("dependency_map_preview")
        if isinstance(feat, str) and isinstance(focus, str):
            lines.append(f"- **{feat}**: {focus}")
    lines.extend(["", "## 9. Dependency Ownership Rules", ""])
    for item in pkt.get("dependency_ownership_rules") or list(_DEPENDENCY_OWNERSHIP_RULES):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 10. Dependency Sequencing Rules", ""])
    for item in pkt.get("dependency_sequencing_rules") or list(_DEPENDENCY_SEQUENCING_RULES):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 11. Sovereignty and Trust Requirements", ""])
    for item in pkt.get("sovereignty_and_trust_requirements") or list(_SOVEREIGNTY_AND_TRUST_REQUIREMENTS):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 12. What Sprint 132 Does Not Build", "", "Sprint 132 explicitly does not build:", ""])
    for item in pkt.get("sprint_132_does_not_build") or list(_SPRINT132_DOES_NOT_BUILD):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 13. M1 Dependency Map Exit Criteria",
            "",
        ]
    )
    for c in pkt.get("m1_dependency_map_exit_criteria") or list(_M1_DEPENDENCY_MAP_EXIT_CRITERIA):
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
            "## 15. Sprint 133 Recommended Next Step",
            "",
            pkt.get("sprint_133_recommended_next_step") or _SPRINT133_RECOMMENDED_NEXT_STEP,
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
