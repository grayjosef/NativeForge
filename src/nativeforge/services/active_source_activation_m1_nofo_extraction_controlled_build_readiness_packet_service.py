"""Sprint 135: M1 NOFO extraction controlled build readiness packet (preview-only).

Deterministic operator packet that defines NOFO extraction readiness fields, extraction scope,
provenance requirements, confidence rules, human gates, sovereignty and security guardrails, and
acceptance criteria before any NOFO extraction or requirement parsing—without extraction execution,
AI generation, document processing, external calls, scraping, or customer data access.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = "nf_active_source_activation_m1_nofo_extraction_controlled_build_readiness_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

_STATUS_DISCLAIMER = (
    "This status is not extraction execution, is not AI generation, and is not document processing."
)

_M1_NOFO_EXTRACTION_READINESS_FOUNDATIONS: tuple[tuple[str, str], ...] = (
    (
        "NOFO document readiness",
        "Ensures each candidate NOFO has identity, document type, and fixture-safe references before "
        "extraction planning language appears.",
    ),
    (
        "Extraction scope readiness",
        "Bounds which sections, schedules, and attachments are in scope for M1 without implying full "
        "parse coverage.",
    ),
    (
        "Requirement parsing readiness",
        "Separates structured requirement categories from narrative blocks with explicit parsing "
        "prerequisites only.",
    ),
    (
        "Source provenance readiness",
        "Keeps publisher lineage, fixture labels, and traceability visible so extracted fields cannot "
        "detach from sources.",
    ),
    (
        "Confidence scoring readiness",
        "Defines how confidence thresholds will be labeled and reviewed before build planning treats "
        "outputs as informed.",
    ),
    (
        "Human review gate readiness",
        "Requires operator-visible checkpoints for low confidence, eligibility, deadlines, and "
        "submission-adjacent fields.",
    ),
    (
        "Eligibility extraction readiness",
        "Treats eligibility cues as expectations with mandatory human review, not final eligibility "
        "determinations.",
    ),
    (
        "Deadline extraction readiness",
        "Captures calendar ambiguity, timezone, and submission channel nuances with explicit human review "
        "before reliance.",
    ),
    (
        "Attachment requirement extraction readiness",
        "Lists expected attachment labels, formats, and optional versus mandatory signals without "
        "processing files.",
    ),
    (
        "Narrative requirement extraction readiness",
        "Scopes story, methodology, equity, and community narrative prompts separately from tabular "
        "requirements.",
    ),
    (
        "Budget/match extraction readiness",
        "Surfaces match percentages, allowability, indirects, and budget forms as planning expectations "
        "only.",
    ),
    (
        "Reporting burden extraction readiness",
        "Flags cadence, metrics, audits, and compliance reporting clauses without automating reporting.",
    ),
    (
        "Data sovereignty and security readiness",
        "States residency, export, retention, consent, and least-privilege constraints for any future "
        "customer-touch paths.",
    ),
)

_NOFO_READINESS_FIELD_GROUP_ROWS: tuple[tuple[str, str, tuple[str, str]], ...] = (
    (
        "NOFO readiness item identity",
        "Stable id, title, and version for each readiness row across operator artifacts.",
        (
            "Identity strings remain identical across repeated packet generations.",
            "Each readiness item exposes a single primary identity key for traceability.",
        ),
    ),
    (
        "NOFO source reference",
        "Fixture or demo-safe pointer to the NOFO document without ingestion or file execution.",
        (
            "References never imply that the binary was parsed or executed in this sprint.",
            "References pair with provenance requirement fields before extraction planning proceeds.",
        ),
    ),
    (
        "Document type",
        "Classifies solicitation, amendment, FAQ, or attachment packet without opening files here.",
        (
            "Document type is recorded before extraction targets are marked in scope.",
            "Type labels forbid silent promotion to live catalog or production ingestion claims.",
        ),
    ),
    (
        "Extraction target",
        "Names the structured slice such as eligibility, deadlines, attachments, or budgets being planned.",
        (
            "Each row lists exactly one primary extraction target to avoid ambiguous merges.",
            "Targets map to the NOFO readiness by extraction target section in this packet.",
        ),
    ),
    (
        "Requirement category",
        "Groups mandatory, scored, narrative, financial, or compliance clauses for parsing prerequisites.",
        (
            "Categories align to operator-visible requirement parsing prerequisites only.",
            "Categories never assert that parsing has executed or succeeded.",
        ),
    ),
    (
        "Provenance requirement",
        "Documents publisher attestation, fixture labels, amendment lineage, and traceability needs.",
        (
            "Provenance requirements stay visible before extraction readiness improves.",
            "Unresolved provenance maps to blocked or deferred statuses with explicit rationale.",
        ),
    ),
    (
        "Confidence threshold",
        "States minimum confidence for auto carry-forward versus forced human review in later builds.",
        (
            "Thresholds are visible numerically or categorically before controlled build planning proceeds.",
            "Thresholds never authorize extraction execution from this sprint packet.",
        ),
    ),
    (
        "Human review prerequisite",
        "Defines mandatory human checkpoints for low confidence, eligibility, deadlines, or submission "
        "adjacent fields.",
        (
            "Low-confidence extraction targets require explicit human review prerequisites in documented "
            "form.",
            "Prerequisites distinguish scoped review from routed production workflows.",
        ),
    ),
    (
        "Eligibility extraction expectation",
        "Describes cues and jurisdiction sensitivity without turning expectations into determinations.",
        (
            "Expectations require human review before any go or no-go eligibility language is used.",
            "Expectations reference seeded or demo-safe exemplars only.",
        ),
    ),
    (
        "Deadline extraction expectation",
        "Captures due times, grace periods, portal cutoffs, and mail versus electronic ambiguity.",
        (
            "Expectations require human review before operators treat dates as final.",
            "Expectations document timezone and channel assumptions explicitly.",
        ),
    ),
    (
        "Attachment extraction expectation",
        "Lists required file families, naming, signatures, and notarization cues without file IO here.",
        (
            "Expectations stay descriptive and preview-only without attachment processing.",
            "Expectations map optional versus mandatory signals when documented in the NOFO reference.",
        ),
    ),
    (
        "Narrative extraction expectation",
        "Scopes essays, logic models, equity statements, and community narratives separately from tables.",
        (
            "Expectations forbid treating draft narrative extractions as customer-ready prose.",
            "Expectations pair with human review when culturally or jurisdictionally sensitive.",
        ),
    ),
    (
        "Budget or match extraction expectation",
        "States match ratios, allowability tables, indirect rates, and budget form families as planning "
        "notes.",
        (
            "Expectations avoid implying automated financial validation or live calculations.",
            "Expectations require human review when totals or match interact with eligibility.",
        ),
    ),
    (
        "Reporting burden extraction expectation",
        "Flags reporting cadence, metrics, audits, and data retention clauses as extraction planning cues.",
        (
            "Expectations do not create reporting jobs or schedules from this sprint.",
            "Expectations surface reviewer ownership for heavy compliance clauses.",
        ),
    ),
    (
        "Extraction blocker status",
        "Signals whether missing documents, provenance gaps, or confidence issues block extraction readiness.",
        (
            "Blocker language stays preview-only and does not enqueue extraction jobs.",
            "Blocked rows require explicit rationale and ownership visibility.",
        ),
    ),
    (
        "Acceptance criteria",
        "Field-level pass or fail checks operators use before assigning a NOFO readiness status.",
        (
            "Each field group carries at least two criteria tied to evidence or explicit gap labels.",
            "Criteria reinforce preview-only posture and non-commitment language.",
        ),
    ),
    (
        "Non-production disclaimer",
        "Restates preview-only posture and lack of extraction execution, AI generation, document "
        "processing, or live calls.",
        (
            "Disclaimers repeat not extraction execution, not AI generation, and not document processing.",
            "Disclaimers appear wherever status language could be misread as go-live extraction.",
        ),
    ),
    (
        "Next sprint recommendation",
        "Points operators to Sprint 136 form package readiness in preview-only language.",
        (
            "Recommendations name Sprint 136 as the M1 Form Package Controlled Build Readiness Packet.",
            "Recommendations forbid silent expansion into runtime work without explicit authorization.",
        ),
    ),
)

_NOFO_READINESS_STATUS_ROWS: tuple[tuple[str, str], ...] = (
    (
        "Not assessed",
        "Readiness row exists but lacks minimum field coverage; must be assessed before planning improves. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Ready for controlled build planning",
        "Field groups are sufficient for operator-controlled extraction build planning without execution "
        "promises. " + _STATUS_DISCLAIMER,
    ),
    (
        "Needs document verification",
        "Publisher, version, or amendment lineage requires verification before trust improves. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Needs extraction scope review",
        "Targets, exclusions, or attachment scope remain ambiguous for operators to bound explicitly. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Needs confidence rule review",
        "Thresholds, scoring rubrics, or confidence labels need operator review before planning proceeds. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Needs human review gate",
        "Low confidence, eligibility, deadline, or submission-adjacent fields require human checkpoints. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Blocked before extraction",
        "Unresolved documents, provenance, confidence, sovereignty, or scope issues block extraction readiness. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Deferred beyond M1",
        "Extraction target is intentionally deferred past M1 while remaining visible in the inventory. "
        + _STATUS_DISCLAIMER,
    ),
)

_PREVIEW_ONLY_NOFO_READINESS_RULES: tuple[str, ...] = (
    "Require seeded or demo-safe records only; never import production customer extracts into NOFO "
    "readiness rows.",
    "Do not access real customer data while building or reviewing this NOFO readiness packet.",
    "Do not execute NOFO extraction, parse requirements, or process documents from this sprint packet.",
    "Do not invoke AI generation, model calls, or automated summarization while using this packet.",
    "Do not place external API calls, scrapes, live ingestions, or live AI generations while using this "
    "packet.",
    "Do not submit applications, forms, or e-signatures while using this packet.",
    "Keep human judgment, provenance visibility, sovereignty boundaries, and missing-data disclosure "
    "explicit.",
)

_NOFO_READINESS_BY_EXTRACTION_TARGET: tuple[tuple[str, str], ...] = (
    (
        "eligibility criteria",
        "Readiness maps identity, provenance, confidence thresholds, and mandatory human review before any "
        "eligibility extraction language is treated as informed.",
    ),
    (
        "application deadlines",
        "Readiness captures channel-specific cutoff assumptions, timezone risk, and human review before "
        "deadline extraction is trusted.",
    ),
    (
        "attachment requirements",
        "Readiness lists expected attachment families, optional versus mandatory cues, and provenance "
        "without file execution.",
    ),
    (
        "narrative requirements",
        "Readiness scopes essay prompts, page limits, and equity narrative expectations with human review "
        "for sensitive topics.",
    ),
    (
        "budget and match requirements",
        "Readiness records match ratios, allowability tables, and form families as planning expectations "
        "without calculations.",
    ),
    (
        "reporting burden requirements",
        "Readiness surfaces cadence, metrics, audits, and compliance clauses with reviewer ownership.",
    ),
    (
        "submission method requirements",
        "Readiness tracks electronic portal, email, or mail paths with submission-adjacent human review "
        "gates.",
    ),
    (
        "evaluation criteria",
        "Readiness aligns scoring rubrics, weighting, and reviewer notes with confidence thresholds and human "
        "gates.",
    ),
    (
        "award terms and restrictions",
        "Readiness highlights post-award restrictions, fund uses, and continuation expectations without "
        "contract execution.",
    ),
    (
        "compliance and assurance requirements",
        "Readiness lists assurance, audit, civil rights, and data handling clauses with sovereignty and "
        "security prerequisites.",
    ),
)

_EXTRACTION_PREREQUISITE_RULES: tuple[str, ...] = (
    "Every extraction target must have a source document reference recorded before extraction planning "
    "proceeds.",
    "Every extracted field must preserve provenance in downstream designs even though this sprint performs "
    "no extraction.",
    "Confidence thresholds must be visible before controlled build planning treats outputs as informed.",
    "Human review gates must exist for low-confidence extraction targets before automation is assumed.",
    "Eligibility and deadline extraction require explicit human review in planning artifacts.",
    "Unresolved provenance issues block extraction readiness until mitigated, deferred with rationale, or "
    "rejected.",
)

_HUMAN_GATE_AND_REVIEW_RULES: tuple[str, ...] = (
    "Low-confidence extracted fields require human review in future builds; this sprint defines the gate "
    "only.",
    "Eligibility determinations require human review and must not be treated as final from extraction "
    "outputs.",
    "Deadline extraction requires human review before operators rely on extracted calendar values.",
    "Submission-adjacent requirements require human review because channels and cutoffs shift frequently.",
    "Extraction activation decisions require explicit operator approval outside this planning packet.",
    "No extraction job is created in this sprint.",
    "No runtime activation occurs in this sprint.",
)

_SOVEREIGNTY_AND_TRUST_REQUIREMENTS: tuple[str, ...] = (
    "Customer owns its data.",
    "No customer data is required for this planning sprint.",
    "No customer data leaves the product during seeded demos.",
    "No model training on customer data without explicit written consent.",
    "Human judgment remains final.",
    "Source provenance remains visible.",
    "NOFO extraction readiness must not overpromise implementation readiness.",
)

_SPRINT135_DOES_NOT_BUILD: tuple[str, ...] = (
    "no NOFO extraction execution",
    "no requirement parsing",
    "no document processing",
    "no AI generation",
    "no extraction job creation",
    "no source activation",
    "no live ingestion",
    "no customer data access",
    "no real application submission",
    "no production readiness certification",
    "no external service call",
    "no database migration",
    "no frontend UI",
    "no API route",
    "no production workflow change",
)

_M1_NOFO_EXTRACTION_READINESS_EXIT_CRITERIA: tuple[str, ...] = (
    "All eighteen NOFO readiness field groups are documented with purposes and acceptance criteria.",
    "All eight NOFO readiness statuses include explicit non-extraction, non-AI-generation, and "
    "non-document-processing disclaimers.",
    "All thirteen M1 NOFO extraction readiness foundations include operator focus statements without runtime "
    "execution.",
    "All ten NOFO readiness by extraction target rows include preview mapping language and caveat "
    "expectations.",
    "Prerequisite rules, human gate rules, sovereignty requirements, and preview-only rules are listed.",
    "Risks and mitigations are recorded with operator discipline expectations for controlled build planning.",
    "Sprint 136 recommendation is captured as the next preview-only form package readiness step.",
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "Extraction execution is implied by planning language",
        "Ban extract, parse, or run verbs except inside explicit not-extraction-execution disclaimers.",
    ),
    (
        "Provenance requirements are skipped",
        "Block extraction readiness until provenance fields are documented or deferred with rationale.",
    ),
    (
        "Low-confidence fields are treated as final",
        "Force human review prerequisites and confidence thresholds before any auto carry-forward language.",
    ),
    (
        "Eligibility extraction becomes final eligibility determination",
        "Require human review labels and forbid go or no-go eligibility language without operator sign-off.",
    ),
    (
        "Deadline extraction is not human-reviewed",
        "Mandate human review gates for deadlines and channel-specific cutoff assumptions in planning rows.",
    ),
    (
        "Document processing is implied too early",
        "Disallow file open, parse, or OCR language unless framed as future build scope with explicit "
        "authorization.",
    ),
    (
        "Customer data handling is implied too early",
        "Sequence sovereignty prerequisites before any customer-specific data language in readiness rows.",
    ),
    (
        "AI generation is implied without approval",
        "Disallow model, LLM, or auto-summarize language unless a documented human approval path exists as "
        "planning-only notes.",
    ),
    (
        "Extraction readiness becomes theater instead of control",
        "Tie statuses to explicit field coverage, blockers, and acceptance criteria reviewers can audit.",
    ),
)

_SPRINT136_RECOMMENDED_NEXT_STEP = (
    "Sprint 136 should deliver the M1 Form Package Controlled Build Readiness Packet, still preview-only "
    "unless the operator explicitly authorizes runtime work."
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _field_group_payloads() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, (name, purpose, criteria) in enumerate(_NOFO_READINESS_FIELD_GROUP_ROWS, start=1):
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
        {"foundation_area": a, "operator_focus": b} for a, b in _M1_NOFO_EXTRACTION_READINESS_FOUNDATIONS
    ]


def _status_payloads() -> list[dict[str, str]]:
    return [{"status": s, "definition": d} for s, d in _NOFO_READINESS_STATUS_ROWS]


def _extraction_target_payloads() -> list[dict[str, str]]:
    return [
        {"extraction_target": a, "nofo_readiness_preview": b} for a, b in _NOFO_READINESS_BY_EXTRACTION_TARGET
    ]


def _risk_payloads() -> list[dict[str, str]]:
    return [{"risk": r, "mitigation": m} for r, m in _RISK_MITIGATIONS]


def build_active_source_activation_m1_nofo_extraction_controlled_build_readiness_packet() -> dict[str, Any]:
    """Return the Sprint 135 M1 NOFO extraction controlled build readiness packet (deterministic)."""
    proof = {
        "sprint_135_m1_nofo_extraction_controlled_build_readiness_packet_is_stateless": True,
        "sprint_135_m1_nofo_extraction_controlled_build_readiness_packet_is_side_effect_free": True,
        "sprint_135_m1_nofo_extraction_controlled_build_readiness_packet_is_preview_only": True,
        "sprint_135_m1_nofo_extraction_controlled_build_readiness_packet_performs_no_runtime_work": True,
        "sprint_135_m1_nofo_extraction_controlled_build_readiness_packet_emits_operator_planning_only": True,
    }
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 135,
        "packet_name": "NativeForge M1 NOFO Extraction Controlled Build Readiness Packet",
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_define_nofo_extraction_readiness": True,
        "may_define_requirement_parsing_prerequisites": True,
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
        "actual_nofo_extractions_run": 0,
        "actual_requirements_parsed": 0,
        "actual_documents_processed": 0,
        "m1_nofo_extraction_controlled_build_readiness_foundations": _foundation_payloads(),
        "nofo_readiness_field_groups": _field_group_payloads(),
        "nofo_readiness_statuses": _status_payloads(),
        "nofo_readiness_status_universal_disclaimer": _STATUS_DISCLAIMER,
        "preview_only_nofo_readiness_rules": list(_PREVIEW_ONLY_NOFO_READINESS_RULES),
        "nofo_readiness_by_extraction_target": _extraction_target_payloads(),
        "extraction_prerequisite_rules": list(_EXTRACTION_PREREQUISITE_RULES),
        "human_gate_and_review_rules": list(_HUMAN_GATE_AND_REVIEW_RULES),
        "sovereignty_and_trust_requirements": list(_SOVEREIGNTY_AND_TRUST_REQUIREMENTS),
        "sprint_135_does_not_build": list(_SPRINT135_DOES_NOT_BUILD),
        "m1_nofo_extraction_readiness_exit_criteria": list(_M1_NOFO_EXTRACTION_READINESS_EXIT_CRITERIA),
        "risks_and_mitigations": _risk_payloads(),
        "sprint_136_recommended_next_step": _SPRINT136_RECOMMENDED_NEXT_STEP,
        "sprint_135_m1_nofo_extraction_controlled_build_readiness_packet_proof": proof,
    }
    return _json_safe(out)


def _ordered_field_groups(pkt: dict[str, Any]) -> list[dict[str, Any]]:
    raw = pkt.get("nofo_readiness_field_groups")
    if isinstance(raw, list):
        groups = [g for g in raw if isinstance(g, dict)]
        groups.sort(key=lambda g: g.get("priority") if isinstance(g.get("priority"), int) else 0)
        return groups
    return _field_group_payloads()


def render_active_source_activation_m1_nofo_extraction_controlled_build_readiness_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render the operator-facing markdown packet (deterministic; uses ``packet`` when provided)."""
    pkt = packet if isinstance(packet, dict) else (
        build_active_source_activation_m1_nofo_extraction_controlled_build_readiness_packet()
    )
    groups = _ordered_field_groups(pkt)
    lines: list[str] = [
        "# NativeForge M1 NOFO Extraction Controlled Build Readiness Packet v1",
        "",
        "## 1. Purpose",
        "",
        "This packet defines the M1 planning layer for NOFO extraction and requirement parsing controlled build "
        "readiness. It is preview-only: it structures NOFO document references, extraction targets, "
        "provenance and confidence expectations, human gates, sovereignty and security guardrails, and "
        "acceptance criteria for operators without NOFO extraction execution, requirement parsing, document "
        "processing, AI generation, external calls, scraping, or customer data access.",
        "",
        "## 2. Why This Comes After Source Ingestion Readiness",
        "",
        "Sprint 134 defined source ingestion readiness so candidate sources, trust, provenance, credentials, "
        "and sovereignty dependencies stay visible before live ingestion language appears. Sprint 135 applies "
        "the same controlled build discipline to extracting requirements from NOFO documents only after "
        "sources and provenance are visible, keeping extraction scope honest while remaining non-executing.",
        "",
        "## 3. M1 NOFO Extraction Readiness Objective",
        "",
        "Deliver a preview-only readiness framework that prevents extraction work from starting before "
        "documents, extraction targets, provenance, confidence thresholds, human gates, sovereignty and "
        "security dependencies, and blockers are visible—without runnable extraction promises, runtime "
        "execution, AI generation, or document processing in this sprint.",
        "",
        "M1 NOFO extraction controlled build readiness foundations:",
        "",
    ]
    foundations = pkt.get("m1_nofo_extraction_controlled_build_readiness_foundations")
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
            "## 4. Preview-Only NOFO Readiness Rules",
            "",
        ]
    )
    for rule in pkt.get("preview_only_nofo_readiness_rules") or list(_PREVIEW_ONLY_NOFO_READINESS_RULES):
        if isinstance(rule, str) and rule.strip():
            lines.append(f"- {rule}")
    lines.extend(
        [
            "",
            "Preview-only NOFO readiness rules restated: seeded or demo-safe records only; no real customer "
            "data; no NOFO extraction execution; no requirement parsing; no document processing; no AI "
            "generation; no external calls; no scraping.",
            "",
            "## 5. Required NOFO Readiness Field Groups",
            "",
            "Eighteen field groups structure every NOFO readiness row:",
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
            "## 6. NOFO Readiness Status Definitions",
            "",
            "Eight preview-only NOFO readiness statuses apply. Each status explicitly disclaims extraction "
            "execution, AI generation, and document processing:",
            "",
        ]
    )
    statuses = pkt.get("nofo_readiness_statuses")
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
    lines.extend(["", "## 8. NOFO Readiness by Extraction Target", ""])
    mapping = pkt.get("nofo_readiness_by_extraction_target")
    if not isinstance(mapping, list):
        mapping = _extraction_target_payloads()
    for row in mapping:
        if not isinstance(row, dict):
            continue
        et = row.get("extraction_target")
        preview = row.get("nofo_readiness_preview")
        if isinstance(et, str) and isinstance(preview, str):
            lines.append(f"- **{et}**: {preview}")
    lines.extend(["", "## 9. Extraction Prerequisite Rules", ""])
    for item in pkt.get("extraction_prerequisite_rules") or list(_EXTRACTION_PREREQUISITE_RULES):
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
    lines.extend(["", "## 12. What Sprint 135 Does Not Build", "", "Sprint 135 explicitly does not build:", ""])
    for item in pkt.get("sprint_135_does_not_build") or list(_SPRINT135_DOES_NOT_BUILD):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 13. M1 NOFO Extraction Readiness Exit Criteria",
            "",
        ]
    )
    for c in pkt.get("m1_nofo_extraction_readiness_exit_criteria") or list(
        _M1_NOFO_EXTRACTION_READINESS_EXIT_CRITERIA
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
            "## 15. Sprint 136 Recommended Next Step",
            "",
            pkt.get("sprint_136_recommended_next_step") or _SPRINT136_RECOMMENDED_NEXT_STEP,
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
