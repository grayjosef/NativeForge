"""Sprint 134: M1 source ingestion controlled build readiness packet (preview-only).

Deterministic operator packet that defines source ingestion readiness fields, source types, trust
checks, activation prerequisites, human gates, sovereignty and security guardrails, and acceptance
criteria before any live ingestion—without source activation, live ingestion, credential
configuration, external calls, scraping, or customer data access.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = "nf_active_source_activation_m1_source_ingestion_controlled_build_readiness_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

_STATUS_DISCLAIMER = (
    "This status is not source activation, is not live ingestion, and is not credential configuration."
)

_M1_SOURCE_INGESTION_READINESS_FOUNDATIONS: tuple[tuple[str, str], ...] = (
    (
        "Source inventory readiness",
        "Catalogs each candidate source with identity, type, access posture, and preview-only status "
        "before ingestion work is planned.",
    ),
    (
        "Source type classification",
        "Separates Grants.gov, agency, state, local, tribal, nonprofit, foundation, corporate, research, "
        "and manual upload paths so readiness rules stay honest per channel.",
    ),
    (
        "Source trust and provenance readiness",
        "Surfaces trust level, lineage, and provenance requirements so low-trust sources cannot hide in "
        "the queue.",
    ),
    (
        "Grants.gov readiness",
        "Documents fixture versus live assumptions, rate limits, monitoring expectations, and credential "
        "review gates for the federal catalog path.",
    ),
    (
        "State/local source readiness",
        "Captures portal diversity, changing formats, and jurisdictional access decisions without implying "
        "live connections.",
    ),
    (
        "Tribal/federal source readiness",
        "Aligns Native-specific federal and tribal sources with sovereignty, provenance, and human review "
        "expectations.",
    ),
    (
        "Foundation/philanthropic source readiness",
        "Tracks private catalog assumptions, eligibility nuance, and disclosure limits before inclusion.",
    ),
    (
        "Corporate/private source readiness",
        "Flags competitive sensitivity, contractual gates, and least-privilege access reviews.",
    ),
    (
        "Manual upload readiness",
        "Defines buyer or operator supplied NOFO handling, labeling, and fixture boundaries separate from "
        "automated acquisition.",
    ),
    (
        "Activation prerequisite tracking",
        "Lists documented prerequisites versus open gaps so activation readiness cannot be assumed silently.",
    ),
    (
        "Human review gates",
        "Requires operator-visible human checkpoints for low trust, credentials, sovereignty, and activation "
        "decisions.",
    ),
    (
        "Security/credential readiness",
        "Captures authentication, secrets handling, and access reviews before any live connection is "
        "planned.",
    ),
    (
        "Data sovereignty readiness",
        "States residency, export, retention, and consent questions affecting whether customer-specific data "
        "may ever touch a source path.",
    ),
)

_SOURCE_READINESS_FIELD_GROUP_ROWS: tuple[tuple[str, str, tuple[str, str]], ...] = (
    (
        "Source readiness item identity",
        "Stable id, title, and version for each readiness row across operator artifacts.",
        (
            "Identity strings remain identical across repeated packet generations.",
            "Each readiness item exposes a single primary identity key for traceability.",
        ),
    ),
    (
        "Source name",
        "Human readable label aligned to operator inventory language without implying activation.",
        (
            "Names distinguish demo fixtures from future production source labels.",
            "Names never substitute for documented access methods or trust levels.",
        ),
    ),
    (
        "Source type",
        "Classifies the channel such as Grants.gov, state portal, tribal, foundation, or manual upload.",
        (
            "Each row lists exactly one primary source type to avoid ambiguous merges.",
            "Types map to the source readiness by source type section in this packet.",
        ),
    ),
    (
        "Source owner or maintainer",
        "Names accountable buyer, operator, vendor, or owner-needed accountability for the source path.",
        (
            "Unresolved ownership maps to explicit owner-needed labels and blockers.",
            "Owners are distinct from access credentials and from runtime operators.",
        ),
    ),
    (
        "Source access method",
        "States API, portal login, bulk file, email intake, or manual upload without claiming live access.",
        (
            "Access methods are documented before activation planning proceeds.",
            "Access methods never assert configured credentials from this sprint.",
        ),
    ),
    (
        "Source trust level",
        "Captures trust posture and reviewer visibility so low-trust sources surface human gates early.",
        (
            "Trust levels pair with human review prerequisites when below documented thresholds.",
            "Trust levels forbid silent promotion to production-ready language.",
        ),
    ),
    (
        "Source provenance requirement",
        "Documents lineage, fixture labels, publisher attestation, and traceability expectations.",
        (
            "Provenance requirements stay visible before inclusion or activation planning.",
            "Provenance gaps map to Needs source verification or blocked statuses.",
        ),
    ),
    (
        "Native relevance rationale",
        "Explains tribal mission alignment, Native-serving eligibility signals, and scope boundaries.",
        (
            "Rationale rejects generic boilerplate by requiring concrete Native relevance statements.",
            "Rationale is documented before a source is treated as inclusion-ready in planning.",
        ),
    ),
    (
        "Eligibility signal expectation",
        "States which eligibility cues the source should expose and how confidence will be labeled later.",
        (
            "Expectations distinguish demo fixtures from future production parsing claims.",
            "Expectations pair with human review when eligibility is jurisdictionally sensitive.",
        ),
    ),
    (
        "Freshness expectation",
        "Defines acceptable staleness, update cadence, and monitoring assumptions before scheduling talk.",
        (
            "Freshness expectations are documented before any ingestion schedule is implied.",
            "Missing freshness maps to blockers or deferrals with visible rationale.",
        ),
    ),
    (
        "Credential or access requirement",
        "Lists secrets, accounts, attestations, or contracts required before a live connection is planned.",
        (
            "Credential requirements undergo security review before any live connection planning.",
            "This sprint performs no credential configuration and stores no secrets.",
        ),
    ),
    (
        "Security prerequisite",
        "Captures least privilege, logging, threat-model gaps, and integration safeguards for the path.",
        (
            "Open security prerequisites block activation readiness until resolved or deferred with rationale.",
            "Prerequisites forbid implying certifications not evidenced elsewhere.",
        ),
    ),
    (
        "Sovereignty prerequisite",
        "Lists residency, export, retention, consent, and customer-data-touch questions for the path.",
        (
            "Sovereignty prerequisites remain visible before customer-specific data is referenced.",
            "Prerequisites never assert private deployment unless separately approved in writing.",
        ),
    ),
    (
        "Human review prerequisite",
        "Defines mandatory human checkpoints for trust, credentials, sovereignty, or activation decisions.",
        (
            "Low-trust sources require explicit human review prerequisites in documented form.",
            "Prerequisites distinguish scoped review from routed production workflows.",
        ),
    ),
    (
        "Activation blocker status",
        "Signals whether unresolved trust, access, credentials, or sovereignty issues block activation "
        "readiness.",
        (
            "Blocker language stays preview-only and does not activate sources or create ingestion jobs.",
            "Blocked rows require explicit rationale and ownership visibility.",
        ),
    ),
    (
        "Acceptance criteria",
        "Field-level pass or fail checks operators use before assigning a source readiness status.",
        (
            "Each field group carries at least two criteria tied to evidence or explicit gap labels.",
            "Criteria reinforce preview-only posture and non-commitment language.",
        ),
    ),
    (
        "Non-production disclaimer",
        "Restates preview-only posture and lack of activation, ingestion, credentials, runtime authority, "
        "or live calls.",
        (
            "Disclaimers repeat not source activation, not live ingestion, and not credential configuration.",
            "Disclaimers appear wherever status language could be misread as go-live readiness.",
        ),
    ),
    (
        "Next sprint recommendation",
        "Points operators to Sprint 135 NOFO extraction readiness in preview-only language.",
        (
            "Recommendations name Sprint 135 as the M1 NOFO Extraction Controlled Build Readiness Packet.",
            "Recommendations forbid silent expansion into runtime work without explicit authorization.",
        ),
    ),
)

_SOURCE_READINESS_STATUS_ROWS: tuple[tuple[str, str], ...] = (
    (
        "Not assessed",
        "Readiness row exists but lacks minimum field coverage; must be assessed before planning improves. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Ready for controlled build planning",
        "Field groups are sufficient for operator-controlled build planning without live ingestion promises. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Needs source verification",
        "Publisher, scope, or provenance claims require verification before trust improves. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Needs access decision",
        "Legal, policy, or partnership posture for the access method remains undecided for operators. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Needs credential review",
        "Secrets, accounts, or contractual access need security review before live connection planning. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Needs sovereignty review",
        "Residency, export, retention, consent, or customer-data-touch questions remain open for review. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Blocked before activation",
        "Unresolved trust, access, credential, sovereignty, or relevance issues block activation readiness. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Deferred beyond M1",
        "Source path is intentionally deferred past M1 while remaining visible in the inventory. "
        + _STATUS_DISCLAIMER,
    ),
)

_PREVIEW_ONLY_SOURCE_READINESS_RULES: tuple[str, ...] = (
    "Require seeded or demo-safe records only; never import production customer extracts into source "
    "readiness rows.",
    "Do not access real customer data while building or reviewing this source readiness packet.",
    "Do not activate sources, enable live feeds, or flip runtime flags from this sprint packet.",
    "Do not create ingestion jobs, queues, or schedulers from this sprint packet.",
    "Do not configure credentials, secrets stores, or vault entries from this sprint packet.",
    "Do not place external API calls, scrapes, live ingestions, or live AI generations while using this "
    "packet.",
    "Do not submit applications, forms, or e-signatures while using this packet.",
    "Keep human judgment, provenance visibility, sovereignty boundaries, and missing-data disclosure "
    "explicit.",
)

_SOURCE_READINESS_BY_SOURCE_TYPE: tuple[tuple[str, str], ...] = (
    (
        "Grants.gov",
        "Readiness focuses on federal catalog assumptions, fixture posture, credential review gates, and "
        "provenance for opportunity rows.",
    ),
    (
        "federal agency grant portals",
        "Readiness focuses on agency-specific formats, authentication variance, and provenance for each "
        "portal program family.",
    ),
    (
        "state grant portals",
        "Readiness focuses on jurisdictional diversity, eligibility nuance, and changing NOFO layouts "
        "without live portal promises.",
    ),
    (
        "local government grant portals",
        "Readiness focuses on municipal program fragmentation, access friction, and manual fallback paths.",
    ),
    (
        "tribal/federal Native-specific sources",
        "Readiness pairs Native relevance rationale with sovereignty, trust, and human review prerequisites.",
    ),
    (
        "Native-serving nonprofit sources",
        "Readiness highlights mission alignment evidence, disclosure limits, and eligibility signal "
        "expectations.",
    ),
    (
        "foundation and philanthropy sources",
        "Readiness tracks private catalog rules, geographic scope, and restricted eligibility language.",
    ),
    (
        "corporate/private grant sources",
        "Readiness emphasizes competitive sensitivity, contractual gates, and least-privilege access "
        "reviews.",
    ),
    (
        "university/research grant sources",
        "Readiness covers indirect cost rules, compliance-heavy clauses, and IP or data-use constraints.",
    ),
    (
        "manual NOFO upload sources",
        "Readiness defines buyer or operator supplied documents, labeling, fixture boundaries, and review "
        "hooks.",
    ),
)

_SOURCE_ACTIVATION_PREREQUISITE_RULES: tuple[str, ...] = (
    "Every source must have source readiness item identity and source access method recorded before "
    "activation planning proceeds.",
    "Trust level and source provenance requirement fields must be visible before activation planning treats "
    "a path as informed.",
    "Credential or access requirement entries must undergo security review before any live connection is "
    "planned.",
    "Native relevance rationale must be documented before a source is treated as inclusion-ready in "
    "planning.",
    "Freshness expectation must be documented before any ingestion schedule language is used.",
    "Unresolved source trust issues block activation readiness until mitigated, deferred with rationale, "
    "or rejected.",
)

_HUMAN_GATE_AND_REVIEW_RULES: tuple[str, ...] = (
    "Sources with low trust require human review before readiness can improve or activation planning "
    "proceeds.",
    "Sources requiring credentials require security review before live connection planning is allowed.",
    "Sources involving customer-specific data require sovereignty review before data handling is implied.",
    "Source activation decisions require explicit operator approval outside this planning packet.",
    "No ingestion job is created in this sprint.",
    "No runtime activation occurs in this sprint.",
)

_SOVEREIGNTY_AND_TRUST_REQUIREMENTS: tuple[str, ...] = (
    "Customer owns its data.",
    "No customer data is required for this planning sprint.",
    "No customer data leaves the product during seeded demos.",
    "No model training on customer data without explicit written consent.",
    "Human judgment remains final.",
    "Source provenance remains visible.",
    "Source ingestion readiness must not overpromise implementation readiness.",
)

_SPRINT134_DOES_NOT_BUILD: tuple[str, ...] = (
    "no source activation",
    "no live ingestion",
    "no ingestion job creation",
    "no credential configuration",
    "no scraping",
    "no API call",
    "no customer data access",
    "no real application submission",
    "no production readiness certification",
    "no external service call",
    "no database migration",
    "no frontend UI",
    "no API route",
    "no production workflow change",
)

_M1_SOURCE_INGESTION_READINESS_EXIT_CRITERIA: tuple[str, ...] = (
    "All eighteen source readiness field groups are documented with purposes and acceptance criteria.",
    "All eight source readiness statuses include explicit non-activation, non-live-ingestion, and "
    "non-credential-configuration disclaimers.",
    "All thirteen M1 source ingestion readiness foundations include operator focus statements without "
    "runtime execution.",
    "All ten source readiness by source type rows include preview mapping language and caveat expectations.",
    "Prerequisite rules, human gate rules, sovereignty requirements, and preview-only rules are listed.",
    "Risks and mitigations are recorded with operator discipline expectations for controlled build planning.",
    "Sprint 135 recommendation is captured as the next preview-only NOFO extraction readiness step.",
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "Source activation is implied by planning language",
        "Ban activate, enable live, or connect verbs except inside explicit not-source-activation "
        "disclaimers.",
    ),
    (
        "Low-trust source enters build queue",
        "Force human review prerequisites and Blocked before activation when trust stays below thresholds.",
    ),
    (
        "Provenance requirements are skipped",
        "Block activation readiness until provenance fields are documented or deferred with rationale.",
    ),
    (
        "Credential requirements are under-scoped",
        "Require security review rows and explicit secrets-handling notes before live connection planning.",
    ),
    (
        "Source freshness expectations are missing",
        "Block scheduling language until freshness expectation is documented with cadence and staleness "
        "bounds.",
    ),
    (
        "Native relevance is too generic",
        "Reject boilerplate by requiring concrete Native relevance rationale tied to eligibility signals.",
    ),
    (
        "Scraping is implied without approval",
        "Disallow scrape language unless a documented human approval path and legal review exist as "
        "planning-only notes.",
    ),
    (
        "Customer data handling is implied too early",
        "Sequence sovereignty prerequisites before any customer-specific data language in readiness rows.",
    ),
    (
        "Source readiness becomes theater instead of control",
        "Tie statuses to explicit field coverage, blockers, and acceptance criteria reviewers can audit.",
    ),
)

_SPRINT135_RECOMMENDED_NEXT_STEP = (
    "Sprint 135 should deliver the M1 NOFO Extraction Controlled Build Readiness Packet, still "
    "preview-only unless the operator explicitly authorizes runtime work."
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _field_group_payloads() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, (name, purpose, criteria) in enumerate(_SOURCE_READINESS_FIELD_GROUP_ROWS, start=1):
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
        {"foundation_area": a, "operator_focus": b} for a, b in _M1_SOURCE_INGESTION_READINESS_FOUNDATIONS
    ]


def _status_payloads() -> list[dict[str, str]]:
    return [{"status": s, "definition": d} for s, d in _SOURCE_READINESS_STATUS_ROWS]


def _source_type_payloads() -> list[dict[str, str]]:
    return [
        {"source_type": a, "source_readiness_preview": b} for a, b in _SOURCE_READINESS_BY_SOURCE_TYPE
    ]


def _risk_payloads() -> list[dict[str, str]]:
    return [{"risk": r, "mitigation": m} for r, m in _RISK_MITIGATIONS]


def build_active_source_activation_m1_source_ingestion_controlled_build_readiness_packet() -> dict[str, Any]:
    """Return the Sprint 134 M1 source ingestion controlled build readiness packet (deterministic)."""
    proof = {
        "sprint_134_m1_source_ingestion_controlled_build_readiness_packet_is_stateless": True,
        "sprint_134_m1_source_ingestion_controlled_build_readiness_packet_is_side_effect_free": True,
        "sprint_134_m1_source_ingestion_controlled_build_readiness_packet_is_preview_only": True,
        "sprint_134_m1_source_ingestion_controlled_build_readiness_packet_performs_no_runtime_work": True,
        "sprint_134_m1_source_ingestion_controlled_build_readiness_packet_emits_operator_planning_only": True,
    }
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 134,
        "packet_name": "NativeForge M1 Source Ingestion Controlled Build Readiness Packet",
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_define_source_ingestion_readiness": True,
        "may_define_source_activation_prerequisites": True,
        "may_define_human_gate_requirements": True,
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
        "actual_sources_activated": 0,
        "actual_ingestion_jobs_created": 0,
        "actual_credentials_configured": 0,
        "m1_source_ingestion_controlled_build_readiness_foundations": _foundation_payloads(),
        "source_readiness_field_groups": _field_group_payloads(),
        "source_readiness_statuses": _status_payloads(),
        "source_readiness_status_universal_disclaimer": _STATUS_DISCLAIMER,
        "preview_only_source_readiness_rules": list(_PREVIEW_ONLY_SOURCE_READINESS_RULES),
        "source_readiness_by_source_type": _source_type_payloads(),
        "source_activation_prerequisite_rules": list(_SOURCE_ACTIVATION_PREREQUISITE_RULES),
        "human_gate_and_review_rules": list(_HUMAN_GATE_AND_REVIEW_RULES),
        "sovereignty_and_trust_requirements": list(_SOVEREIGNTY_AND_TRUST_REQUIREMENTS),
        "sprint_134_does_not_build": list(_SPRINT134_DOES_NOT_BUILD),
        "m1_source_ingestion_readiness_exit_criteria": list(_M1_SOURCE_INGESTION_READINESS_EXIT_CRITERIA),
        "risks_and_mitigations": _risk_payloads(),
        "sprint_135_recommended_next_step": _SPRINT135_RECOMMENDED_NEXT_STEP,
        "sprint_134_m1_source_ingestion_controlled_build_readiness_packet_proof": proof,
    }
    return _json_safe(out)


def _ordered_field_groups(pkt: dict[str, Any]) -> list[dict[str, Any]]:
    raw = pkt.get("source_readiness_field_groups")
    if isinstance(raw, list):
        groups = [g for g in raw if isinstance(g, dict)]
        groups.sort(key=lambda g: g.get("priority") if isinstance(g.get("priority"), int) else 0)
        return groups
    return _field_group_payloads()


def render_active_source_activation_m1_source_ingestion_controlled_build_readiness_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render the operator-facing markdown packet (deterministic; uses ``packet`` when provided)."""
    pkt = packet if isinstance(packet, dict) else (
        build_active_source_activation_m1_source_ingestion_controlled_build_readiness_packet()
    )
    groups = _ordered_field_groups(pkt)
    lines: list[str] = [
        "# NativeForge M1 Source Ingestion Controlled Build Readiness Packet v1",
        "",
        "## 1. Purpose",
        "",
        "This packet defines the M1 planning layer for source ingestion controlled build readiness. It is "
        "preview-only: it structures source inventory fields, source types, trust and provenance checks, "
        "activation prerequisites, human gates, sovereignty and security guardrails, and acceptance "
        "criteria for operators without source activation, live ingestion, credential configuration, "
        "external calls, scraping, or customer data access.",
        "",
        "## 2. Why This Comes After Controlled Build Sequencing",
        "",
        "Sprint 133 defined controlled build sequencing and human gates across product areas. Sprint 134 "
        "applies the same control discipline to source ingestion readiness so sources, trust, provenance, "
        "credentials, sovereignty and security dependencies, and blockers stay visible before live "
        "ingestion language appears.",
        "",
        "## 3. M1 Source Ingestion Readiness Objective",
        "",
        "Deliver a preview-only readiness framework that prevents live ingestion from starting before "
        "sources, trust, provenance, credentials, sovereignty and security dependencies, and blockers are "
        "visible—without runnable ingestion promises, runtime execution, source activation, or credential "
        "handling.",
        "",
        "M1 source ingestion controlled build readiness foundations:",
        "",
    ]
    foundations = pkt.get("m1_source_ingestion_controlled_build_readiness_foundations")
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
            "## 4. Preview-Only Source Readiness Rules",
            "",
        ]
    )
    for rule in pkt.get("preview_only_source_readiness_rules") or list(
        _PREVIEW_ONLY_SOURCE_READINESS_RULES
    ):
        if isinstance(rule, str) and rule.strip():
            lines.append(f"- {rule}")
    lines.extend(
        [
            "",
            "Preview-only source readiness rules restated: seeded or demo-safe records only; no real "
            "customer data; no source activation; no live ingestion; no credential configuration; no "
            "external calls; no scraping.",
            "",
            "## 5. Required Source Readiness Field Groups",
            "",
            "Eighteen field groups structure every source readiness row:",
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
            "## 6. Source Readiness Status Definitions",
            "",
            "Eight preview-only source readiness statuses apply. Each status explicitly disclaims source "
            "activation, live ingestion, and credential configuration:",
            "",
        ]
    )
    statuses = pkt.get("source_readiness_statuses")
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
    lines.extend(["", "## 8. Source Readiness by Source Type", ""])
    mapping = pkt.get("source_readiness_by_source_type")
    if not isinstance(mapping, list):
        mapping = _source_type_payloads()
    for row in mapping:
        if not isinstance(row, dict):
            continue
        st = row.get("source_type")
        preview = row.get("source_readiness_preview")
        if isinstance(st, str) and isinstance(preview, str):
            lines.append(f"- **{st}**: {preview}")
    lines.extend(["", "## 9. Source Activation Prerequisite Rules", ""])
    for item in pkt.get("source_activation_prerequisite_rules") or list(
        _SOURCE_ACTIVATION_PREREQUISITE_RULES
    ):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 10. Human Gate and Review Rules", ""])
    for item in pkt.get("human_gate_and_review_rules") or list(_HUMAN_GATE_AND_REVIEW_RULES):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 11. Sovereignty and Trust Requirements", ""])
    for item in pkt.get("sovereignty_and_trust_requirements") or list(_SOVEREIGNTY_AND_TRUST_REQUIREMENTS):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 12. What Sprint 134 Does Not Build", "", "Sprint 134 explicitly does not build:", ""])
    for item in pkt.get("sprint_134_does_not_build") or list(_SPRINT134_DOES_NOT_BUILD):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 13. M1 Source Ingestion Readiness Exit Criteria",
            "",
        ]
    )
    for c in pkt.get("m1_source_ingestion_readiness_exit_criteria") or list(
        _M1_SOURCE_INGESTION_READINESS_EXIT_CRITERIA
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
            "## 15. Sprint 135 Recommended Next Step",
            "",
            pkt.get("sprint_135_recommended_next_step") or _SPRINT135_RECOMMENDED_NEXT_STEP,
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
