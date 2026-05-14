"""Sprint 133: M1 controlled build sequencing and human gate packet (preview-only).

Deterministic operator packet that defines controlled build phases, human approval gates, readiness
criteria, sequencing, blockers, guardrails, and acceptance criteria before M1 pilot implementation work—
without build execution, feature activation, human gate record creation, external calls, or customer data
access.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = "nf_active_source_activation_m1_controlled_build_sequencing_human_gate_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

_STATUS_DISCLAIMER = (
    "This status is not runtime execution, is not feature activation, and is not customer approval."
)

_M1_CONTROLLED_BUILD_SEQUENCING_FOUNDATIONS: tuple[tuple[str, str], ...] = (
    (
        "Controlled build phase inventory",
        "Lists each build gate with identity, phase, product area, and preview-only status before any "
        "implementation work is sequenced.",
    ),
    (
        "Human gate ownership",
        "Assigns buyer-owned versus operator-owned human gate owners so unresolved ownership surfaces as a "
        "readiness blocker.",
    ),
    (
        "Human gate approval criteria",
        "Defines required approval decisions and evidence so gate language cannot be mistaken for customer "
        "go-live approval.",
    ),
    (
        "Build readiness checks",
        "Captures operator-visible readiness signals that remain documentation-only in this sprint.",
    ),
    (
        "Build blocker tracking",
        "Records explicit blockers, deferrals, and rationale so hidden gates cannot enter the pilot "
        "silently.",
    ),
    (
        "Dependency sequencing validation",
        "Validates documented order constraints without executing builds or activating features.",
    ),
    (
        "Source ingestion build gate",
        "Gates live Grants.gov or partner ingestion behind prerequisites, credentials, and demo-safe "
        "fixtures.",
    ),
    (
        "NOFO extraction build gate",
        "Gates extraction and requirement parsing before form automation assumptions harden.",
    ),
    (
        "Form package build gate",
        "Gates SF-424 and form package preview work behind signing boundaries and non-submission posture.",
    ),
    (
        "Human review workflow build gate",
        "Gates reviewer roles, cadence, escalations, and audit expectations before submission-adjacent work.",
    ),
    (
        "Data sovereignty build gate",
        "Gates residency, export, retention, and consent prerequisites before customer data handling is "
        "sequenced.",
    ),
    (
        "Security/access build gate",
        "Gates identity, least privilege, secrets handling, and logging prerequisites without certification "
        "claims.",
    ),
    (
        "Export/audit build gate",
        "Maps export controls, audit log expectations, and access reviews before pilot closeout planning.",
    ),
)

_BUILD_GATE_FIELD_GROUP_ROWS: tuple[tuple[str, str, tuple[str, str]], ...] = (
    (
        "Build gate identity",
        "Stable id, title, and version for each build gate row across operator artifacts.",
        (
            "Identity strings remain identical across repeated packet generations.",
            "Each gate exposes a single primary identity key for traceability.",
        ),
    ),
    (
        "Build phase",
        "Places the gate within a controlled build phase such as discovery, extraction, review, or export.",
        (
            "Phases use planning language and never imply executed build steps or activated features.",
            "Phases align to the controlled build phase inventory in this packet.",
        ),
    ),
    (
        "Product area",
        "Maps the gate to a product area such as ingestion, NOFO parsing, or form preview for M1.",
        (
            "Product areas align to the controlled build sequence by product area section.",
            "Each row lists exactly one primary product area to avoid ambiguous merges.",
        ),
    ),
    (
        "Human gate owner",
        "Names buyer-owned, operator-owned, or owner-needed accountability for the human gate.",
        (
            "Unresolved ownership maps to Needs human owner or an explicit owner-needed label.",
            "Buyer-owned gates are visibly distinct from operator-owned gates.",
        ),
    ),
    (
        "Required approval decision",
        "Captures approvals, policy choices, or governance decisions that must precede implementation.",
        (
            "Decisions use preview-only verbs such as document or map, not deploy or activate.",
            "Decisions pair with blocker status when work cannot proceed.",
        ),
    ),
    (
        "Required evidence",
        "Lists documents, fixtures, policies, or demo data required before the gate can advance in "
        "planning.",
        (
            "Evidence references seeded or demo-safe sources only in this sprint.",
            "Evidence never requires production customer extracts for planning.",
        ),
    ),
    (
        "Dependency prerequisite",
        "Captures upstream engineering, integration, or planning dependencies before sequencing claims.",
        (
            "Dependency prerequisites must not hide sovereignty or security prerequisites.",
            "Prerequisites forbid database migrations, API routes, or UI build claims from this sprint.",
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
        "Security prerequisite",
        "Captures authentication, authorization, secrets, and threat-model gaps before build planning.",
        (
            "Open security prerequisites block implementation readiness until resolved or deferred with "
            "rationale.",
            "Prerequisites forbid implying certifications not evidenced elsewhere.",
        ),
    ),
    (
        "Data handling prerequisite",
        "States schemas, minimization, retention, and fixture assumptions required for honest sequencing.",
        (
            "Data handling prerequisites repeat that no real customer data is required for this sprint.",
            "Prerequisites distinguish demo fixtures from future production data handling.",
        ),
    ),
    (
        "Human review prerequisite",
        "Defines mandatory human checkpoints for eligibility, forms, or narrative outputs in M1 sequencing.",
        (
            "Submission-adjacent gates require visible human review prerequisites in the documented order.",
            "Prerequisites distinguish scoped review from routed production workflows.",
        ),
    ),
    (
        "Source provenance prerequisite",
        "Documents source lineage, fixture labels, and traceability expectations before ingestion claims.",
        (
            "Provenance remains visible for every gate touching external or uploaded sources.",
            "Prerequisites pair live source assumptions with explicit demo-safe alternatives.",
        ),
    ),
    (
        "Sequencing position",
        "States relative order constraints so sovereignty, ingestion, extraction, and review stay honest.",
        (
            "Sequencing repeats that no runtime execution occurs in this sprint.",
            "Positions surface conflicts when downstream work assumes hidden upstream readiness.",
        ),
    ),
    (
        "Blocker status",
        "Signals whether the gate blocks implementation readiness until resolved or deferred with rationale.",
        (
            "Blocker language stays preview-only and does not execute builds or create human gate records.",
            "Blocked rows require explicit rationale and ownership visibility.",
        ),
    ),
    (
        "Acceptance criteria",
        "Field-level pass or fail checks operators use before assigning a build gate status.",
        (
            "Each gate carries at least two criteria tied to evidence or explicit gap labels.",
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
        "Restates preview-only posture and lack of build execution, activation, runtime authority, or "
        "records.",
        (
            "Disclaimers repeat not runtime execution, not feature activation, and not customer approval.",
            "Disclaimers appear wherever status language could be misread as go-live approval.",
        ),
    ),
    (
        "Next sprint recommendation",
        "Points operators to Sprint 134 source ingestion readiness in preview-only language.",
        (
            "Recommendations name Sprint 134 as the M1 Source Ingestion Controlled Build Readiness Packet.",
            "Recommendations forbid silent expansion into runtime work without explicit authorization.",
        ),
    ),
)

_BUILD_GATE_STATUS_ROWS: tuple[tuple[str, str], ...] = (
    (
        "Not gated",
        "Gate is visible as a gap and must be mapped before sequencing claims. " + _STATUS_DISCLAIMER,
    ),
    (
        "Gate mapped",
        "Gate is documented with field groups sufficient for operator review without build promises. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Needs human owner",
        "Accountable buyer or operator human gate owner is missing and must be named before readiness "
        "improves. " + _STATUS_DISCLAIMER,
    ),
    (
        "Needs evidence",
        "Required evidence, fixtures, or policy inputs remain open for operator review. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Needs sovereignty review",
        "Residency, export, retention, or consent questions remain open for policy review. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Needs security review",
        "Authentication, secrets handling, or access controls lack documented prerequisites. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Blocked before implementation",
        "Explicit blocker prevents treating the gate as implementation-ready until resolved or deferred. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Deferred beyond pilot",
        "Gate is intentionally deferred past the pilot while remaining visible in the sequence. "
        + _STATUS_DISCLAIMER,
    ),
)

_PREVIEW_ONLY_BUILD_SEQUENCING_RULES: tuple[str, ...] = (
    "Require seeded or demo-safe records only; never import production customer extracts into build gate "
    "sequencing.",
    "Do not access real customer data while building or reviewing this controlled build sequencing packet.",
    "Do not execute build steps, pipelines, or installers from this sprint packet.",
    "Do not activate features, runtime flags, or production environments from this sprint packet.",
    "Do not create human gate records, workflow tickets, or production approvals from this sprint packet.",
    "Do not place external API calls, scrapes, live ingestions, or live AI generations while using this "
    "packet.",
    "Do not submit applications, forms, or e-signatures while using this packet.",
    "Keep human judgment, provenance visibility, sovereignty boundaries, and missing-data disclosure "
    "explicit.",
)

_M1_CONTROLLED_BUILD_SEQUENCE_BY_PRODUCT_AREA: tuple[tuple[str, str], ...] = (
    (
        "organizational entity profile",
        "Build gate mapping for tribal context fields, mission alignment inputs, and profile data handling "
        "before implementation sequencing.",
    ),
    (
        "live Grants.gov/source ingestion",
        "Build gate mapping for credentials, rate limits, monitoring, and live feed readiness versus demo "
        "fixtures.",
    ),
    (
        "manual NOFO upload",
        "Build gate mapping for buyer or operator supplied documents versus automated acquisition paths.",
    ),
    (
        "NOFO extraction and requirement parsing",
        "Build gate mapping for parser coverage, clause traceability, confidence labeling, and review hooks.",
    ),
    (
        "tribal eligibility and scoring",
        "Build gate mapping for non-final scoring posture, policy review, and buyer-visible caveats in M1.",
    ),
    (
        "pursuit pipeline",
        "Build gate mapping for pipeline stages, owners, deadlines, and reporting without assumed production "
        "writes.",
    ),
    (
        "SF-424/form package preview",
        "Build gate mapping for autofill mapping, signing limits, and submission-adjacent safeguards.",
    ),
    (
        "human review workflow",
        "Build gate mapping for reviewer roles, SLAs, escalations, and audit expectations as planning only.",
    ),
    (
        "data sovereignty and export",
        "Build gate mapping for residency, export controls, consent tracking, and customer-owned data "
        "handling.",
    ),
    (
        "audit logs and access control",
        "Build gate mapping for logging expectations, access reviews, and least-privilege design for M1.",
    ),
    (
        "pilot support and implementation operations",
        "Build gate mapping for support channels, runbooks, and implementation capacity without operational "
        "promises.",
    ),
)

_HUMAN_GATE_OWNERSHIP_RULES: tuple[str, ...] = (
    "Every build gate must have a human gate owner or an explicit owner-needed status; anonymous gates block "
    "implementation readiness.",
    "Operator-owned gates must be labeled separately from buyer-owned gates in the controlled build "
    "sequence.",
    "Sovereignty gates must require explicit human review before customer data handling is sequenced.",
    "Security gates must require explicit human review before trust-sensitive implementation is sequenced.",
    "Submission-adjacent gates must require human approval before implementation work is treated as ready.",
    "Unresolved ownership blocks implementation readiness until assigned or deferred with visible rationale.",
)

_CONTROLLED_BUILD_SEQUENCING_RULES: tuple[str, ...] = (
    "Sovereignty and security gates must precede customer data handling in the documented order.",
    "Source ingestion gates must precede live discovery work in the documented order.",
    "NOFO extraction gates must precede form package automation assumptions in the documented order.",
    "Human review gates must precede submission-adjacent work in the documented order.",
    "Export and audit gates must be mapped before pilot closeout planning assumes readiness.",
    "No runtime execution occurs in this sprint; sequencing is documentation and operator discipline only.",
)

_SOVEREIGNTY_AND_TRUST_REQUIREMENTS: tuple[str, ...] = (
    "Customer owns its data.",
    "No customer data is required for this planning sprint.",
    "No customer data leaves the product during seeded demos.",
    "No model training on customer data without explicit written consent.",
    "Human judgment remains final.",
    "Source provenance remains visible.",
    "Build sequencing must not overpromise implementation readiness.",
)

_SPRINT133_DOES_NOT_BUILD: tuple[str, ...] = (
    "no build step execution",
    "no feature activation",
    "no human gate record creation",
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

_M1_CONTROLLED_BUILD_SEQUENCING_EXIT_CRITERIA: tuple[str, ...] = (
    "All eighteen build gate field groups are documented with purposes and acceptance criteria.",
    "All eight build gate statuses include explicit non-execution, non-activation, and non-customer-approval "
    "disclaimers.",
    "All thirteen controlled build sequencing foundations include operator focus statements without runtime "
    "execution.",
    "All eleven controlled build sequence by product area rows include gate mapping previews and caveat "
    "expectations.",
    "Ownership rules, sequencing rules, sovereignty requirements, and preview sequencing rules are listed.",
    "Risks and mitigations are recorded with operator discipline expectations for implementation planning.",
    "Sprint 134 recommendation is captured as the next preview-only source ingestion readiness step.",
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "Build begins without human gate ownership",
        "Force Needs human owner until buyer-owned and operator-owned labels exist with named accountability.",
    ),
    (
        "Gate approval is mistaken for customer approval",
        "Restate disclaimers on every status and ban customer-go-live language from planning-only packets.",
    ),
    (
        "Sovereignty review is skipped",
        "Block implementation readiness when residency, export, retention, or consent prerequisites remain "
        "open.",
    ),
    (
        "Security review is skipped",
        "Block implementation readiness when authentication, secrets handling, or integrations lack "
        "documented prerequisites.",
    ),
    (
        "Source ingestion work starts before prerequisites",
        "Keep ingestion prerequisites and demo fixtures visible before live discovery sequencing claims.",
    ),
    (
        "Submission-adjacent work starts before human review gates",
        "Insert human review prerequisites before any submission-adjacent sequencing claims in the packet.",
    ),
    (
        "Customer data handling is implied too early",
        "Sequence sovereignty and security gates before data handling prerequisites in documented order.",
    ),
    (
        "Feature activation is implied by planning language",
        "Ban activate, deploy, or enable verbs except inside explicit not-feature-activation disclaimers.",
    ),
    (
        "Build sequencing becomes theater instead of actual control",
        "Tie sequencing positions to explicit prerequisites, blockers, and acceptance criteria reviewers can "
        "audit.",
    ),
)

_SPRINT134_RECOMMENDED_NEXT_STEP = (
    "Sprint 134 should deliver the M1 Source Ingestion Controlled Build Readiness Packet, still "
    "preview-only unless the operator explicitly authorizes runtime work."
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _field_group_payloads() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, (name, purpose, criteria) in enumerate(_BUILD_GATE_FIELD_GROUP_ROWS, start=1):
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
        {"foundation_area": a, "operator_focus": b} for a, b in _M1_CONTROLLED_BUILD_SEQUENCING_FOUNDATIONS
    ]


def _status_payloads() -> list[dict[str, str]]:
    return [{"status": s, "definition": d} for s, d in _BUILD_GATE_STATUS_ROWS]


def _product_area_payloads() -> list[dict[str, str]]:
    return [
        {"product_area": a, "controlled_build_sequence_preview": b}
        for a, b in _M1_CONTROLLED_BUILD_SEQUENCE_BY_PRODUCT_AREA
    ]


def _risk_payloads() -> list[dict[str, str]]:
    return [{"risk": r, "mitigation": m} for r, m in _RISK_MITIGATIONS]


def build_active_source_activation_m1_controlled_build_sequencing_human_gate_packet() -> dict[str, Any]:
    """Return the Sprint 133 M1 controlled build sequencing and human gate packet (deterministic)."""
    proof = {
        "sprint_133_m1_controlled_build_sequencing_human_gate_packet_is_stateless": True,
        "sprint_133_m1_controlled_build_sequencing_human_gate_packet_is_side_effect_free": True,
        "sprint_133_m1_controlled_build_sequencing_human_gate_packet_is_preview_only": True,
        "sprint_133_m1_controlled_build_sequencing_human_gate_packet_performs_no_runtime_work": True,
        "sprint_133_m1_controlled_build_sequencing_human_gate_packet_emits_operator_planning_only": True,
    }
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 133,
        "packet_name": "NativeForge M1 Controlled Build Sequencing and Human Gate Packet",
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_define_controlled_build_sequence": True,
        "may_define_human_gate_requirements": True,
        "may_define_build_readiness_criteria": True,
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
        "actual_build_steps_executed": 0,
        "actual_features_activated": 0,
        "actual_human_gate_records_created": 0,
        "m1_controlled_build_sequencing_and_human_gate_foundations": _foundation_payloads(),
        "build_gate_field_groups": _field_group_payloads(),
        "build_gate_statuses": _status_payloads(),
        "build_gate_status_universal_disclaimer": _STATUS_DISCLAIMER,
        "preview_only_build_sequencing_rules": list(_PREVIEW_ONLY_BUILD_SEQUENCING_RULES),
        "m1_controlled_build_sequence_by_product_area": _product_area_payloads(),
        "human_gate_ownership_rules": list(_HUMAN_GATE_OWNERSHIP_RULES),
        "controlled_build_sequencing_rules": list(_CONTROLLED_BUILD_SEQUENCING_RULES),
        "sovereignty_and_trust_requirements": list(_SOVEREIGNTY_AND_TRUST_REQUIREMENTS),
        "sprint_133_does_not_build": list(_SPRINT133_DOES_NOT_BUILD),
        "m1_controlled_build_sequencing_exit_criteria": list(_M1_CONTROLLED_BUILD_SEQUENCING_EXIT_CRITERIA),
        "risks_and_mitigations": _risk_payloads(),
        "sprint_134_recommended_next_step": _SPRINT134_RECOMMENDED_NEXT_STEP,
        "sprint_133_m1_controlled_build_sequencing_human_gate_packet_proof": proof,
    }
    return _json_safe(out)


def _ordered_field_groups(pkt: dict[str, Any]) -> list[dict[str, Any]]:
    raw = pkt.get("build_gate_field_groups")
    if isinstance(raw, list):
        groups = [g for g in raw if isinstance(g, dict)]
        groups.sort(key=lambda g: g.get("priority") if isinstance(g.get("priority"), int) else 0)
        return groups
    return _field_group_payloads()


def render_active_source_activation_m1_controlled_build_sequencing_human_gate_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render the operator-facing markdown packet (deterministic; uses ``packet`` when provided)."""
    pkt = packet if isinstance(packet, dict) else (
        build_active_source_activation_m1_controlled_build_sequencing_human_gate_packet()
    )
    groups = _ordered_field_groups(pkt)
    lines: list[str] = [
        "# NativeForge M1 Controlled Build Sequencing and Human Gate Packet v1",
        "",
        "## 1. Purpose",
        "",
        "This packet defines the M1 planning layer for controlled build sequencing and human approval gates. "
        "It is preview-only: it structures build gate inventory, human gate ownership, approval criteria, "
        "readiness checks, sequencing, blockers, guardrails, and acceptance criteria for operators without "
        "build execution, feature activation, human gate record creation, external calls, or customer data "
        "access.",
        "",
        "## 2. Why This Comes After Implementation Dependency Mapping",
        "",
        "Sprint 132 mapped implementation dependencies, ownership, and prerequisites across product areas. "
        "Sprint 133 defines the controlled sequence and human gates required before M1 pilot implementation "
        "work can safely begin, so owners, evidence, sovereignty and security dependencies, and blockers stay "
        "visible before engineering execution is implied.",
        "",
        "## 3. M1 Controlled Build Objective",
        "",
        "Deliver a preview-only build sequencing and human gate framework that prevents implementation from "
        "starting before owners, evidence, prerequisites, sovereignty and security dependencies, and blockers "
        "are visible—without runnable build promises, runtime execution, feature activation, or customer "
        "approval language.",
        "",
        "M1 controlled build sequencing and human gate foundations:",
        "",
    ]
    foundations = pkt.get("m1_controlled_build_sequencing_and_human_gate_foundations")
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
            "## 4. Preview-Only Build Sequencing Rules",
            "",
        ]
    )
    for rule in pkt.get("preview_only_build_sequencing_rules") or list(_PREVIEW_ONLY_BUILD_SEQUENCING_RULES):
        if isinstance(rule, str) and rule.strip():
            lines.append(f"- {rule}")
    lines.extend(
        [
            "",
            "Preview-only build sequencing rules restated: seeded or demo-safe records only; no real "
            "customer data; no build step execution; no feature activation; no human gate record creation; "
            "no external calls.",
            "",
            "## 5. Required Build Gate Field Groups",
            "",
            "Eighteen field groups structure every build gate row:",
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
            "## 6. Build Gate Status Definitions",
            "",
            "Eight preview-only build gate statuses apply. Each status explicitly disclaims runtime "
            "execution, feature activation, and customer approval:",
            "",
        ]
    )
    statuses = pkt.get("build_gate_statuses")
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
    lines.extend(["", "## 8. Controlled Build Sequence by Product Area", ""])
    mapping = pkt.get("m1_controlled_build_sequence_by_product_area")
    if not isinstance(mapping, list):
        mapping = _product_area_payloads()
    for row in mapping:
        if not isinstance(row, dict):
            continue
        feat = row.get("product_area")
        focus = row.get("controlled_build_sequence_preview")
        if isinstance(feat, str) and isinstance(focus, str):
            lines.append(f"- **{feat}**: {focus}")
    lines.extend(["", "## 9. Human Gate Ownership Rules", ""])
    for item in pkt.get("human_gate_ownership_rules") or list(_HUMAN_GATE_OWNERSHIP_RULES):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 10. Controlled Build Sequencing Rules", ""])
    for item in pkt.get("controlled_build_sequencing_rules") or list(_CONTROLLED_BUILD_SEQUENCING_RULES):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 11. Sovereignty and Trust Requirements", ""])
    for item in pkt.get("sovereignty_and_trust_requirements") or list(_SOVEREIGNTY_AND_TRUST_REQUIREMENTS):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 12. What Sprint 133 Does Not Build", "", "Sprint 133 explicitly does not build:", ""])
    for item in pkt.get("sprint_133_does_not_build") or list(_SPRINT133_DOES_NOT_BUILD):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 13. M1 Controlled Build Sequencing Exit Criteria",
            "",
        ]
    )
    for c in pkt.get("m1_controlled_build_sequencing_exit_criteria") or list(
        _M1_CONTROLLED_BUILD_SEQUENCING_EXIT_CRITERIA
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
            "## 15. Sprint 134 Recommended Next Step",
            "",
            pkt.get("sprint_134_recommended_next_step") or _SPRINT134_RECOMMENDED_NEXT_STEP,
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
