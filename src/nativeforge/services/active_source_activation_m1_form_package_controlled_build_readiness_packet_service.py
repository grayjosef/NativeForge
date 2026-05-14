"""Sprint 136: M1 form package controlled build readiness packet (preview-only).

Deterministic operator packet that defines form package readiness fields, form scope, autofill
prerequisites, source and provenance requirements, human gates, sovereignty and security guardrails,
and acceptance criteria—without form package creation, autofill execution, form processing, form
submission, external calls, or customer data access.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = "nf_active_source_activation_m1_form_package_controlled_build_readiness_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

_STATUS_DISCLAIMER = (
    "This status is not form processing, is not autofill execution, and is not form submission."
)

_M1_FORM_PACKAGE_READINESS_FOUNDATIONS: tuple[tuple[str, str], ...] = (
    (
        "Form package scope readiness",
        "Bounds which forms, schedules, and attachment families belong to M1 preview planning without "
        "implying full package assembly.",
    ),
    (
        "SF-424 readiness",
        "Covers application cover identifiers, applicant type, program selection, and disclosure fields as "
        "planning expectations only.",
    ),
    (
        "SF-424A/SF-424B readiness",
        "Separates budget information and assurance statements with explicit mapping and review "
        "prerequisites before any autofill language appears.",
    ),
    (
        "Attachment package readiness",
        "Lists attachment labels, formats, signatures, and optional versus mandatory expectations without "
        "file execution.",
    ),
    (
        "Organization profile mapping readiness",
        "Aligns form fields to profile source fields with unresolved mapping visibility before build "
        "planning proceeds.",
    ),
    (
        "Autofill confidence readiness",
        "Defines how confidence thresholds and low-confidence routing stay visible for operators before "
        "controlled build planning.",
    ),
    (
        "Source/provenance readiness",
        "Keeps publisher lineage, fixture labels, and field provenance visible so readiness rows cannot "
        "detach from sources.",
    ),
    (
        "Human review gate readiness",
        "Requires operator-visible checkpoints for low confidence, signatures, authorization, and "
        "submission-adjacent fields.",
    ),
    (
        "Field override readiness",
        "Documents how overrides are proposed, reviewed, and recorded without implying runtime override "
        "execution here.",
    ),
    (
        "Missing data handling readiness",
        "Ensures missing data rules and operator visibility exist before autofill readiness improves.",
    ),
    (
        "Submission-adjacent safety readiness",
        "Treats portal paths, certifications, and submission channels as planning-only blockers until "
        "human review gates are satisfied.",
    ),
    (
        "Data sovereignty and security readiness",
        "States residency, export, retention, consent, and least-privilege constraints for any future "
        "customer-touch paths.",
    ),
)

_FORM_READINESS_FIELD_GROUP_ROWS: tuple[tuple[str, str, tuple[str, str]], ...] = (
    (
        "Form readiness item identity",
        "Stable id, title, and version for each readiness row across operator artifacts.",
        (
            "Identity strings remain identical across repeated packet generations.",
            "Each readiness item exposes a single primary identity key for traceability.",
        ),
    ),
    (
        "Form package reference",
        "Fixture or demo-safe pointer to the intended form package scope without package creation.",
        (
            "References never imply that a form package was built or stored in this sprint.",
            "References pair with provenance requirement fields before readiness improves.",
        ),
    ),
    (
        "Form type",
        "Classifies SF-424, SF-424A, SF-424B, or attachment-adjacent forms without opening files here.",
        (
            "Form type is recorded before field groups are marked in scope.",
            "Type labels forbid silent promotion to live autofill or submission claims.",
        ),
    ),
    (
        "Form field group",
        "Names the logical field cluster such as applicant identity, assurances, or budget tables.",
        (
            "Each row lists exactly one primary field group to avoid ambiguous merges.",
            "Field groups map to the form readiness by form package area section in this packet.",
        ),
    ),
    (
        "Profile source field",
        "Identifies the organization profile field proposed as the autofill source or explicit gap label.",
        (
            "Every autofill-targeted field either names a profile source field or defers with a missing "
            "data rule reference.",
            "Profile references stay seeded or demo-safe without customer production extracts.",
        ),
    ),
    (
        "Autofill mapping expectation",
        "Describes how a form field should map from profile or fixtures as planning language only.",
        (
            "Expectations forbid treating mapped values as executed autofill or final submission data.",
            "Expectations require provenance fields to stay populated in planning rows.",
        ),
    ),
    (
        "Provenance requirement",
        "Documents publisher attestation, fixture labels, amendment lineage, and traceability needs.",
        (
            "Provenance requirements stay visible before autofill readiness improves.",
            "Unresolved provenance maps to blocked or deferred statuses with explicit rationale.",
        ),
    ),
    (
        "Confidence threshold",
        "States minimum confidence for operator carry-forward versus forced human review in later builds.",
        (
            "Thresholds are visible numerically or categorically before controlled build planning proceeds.",
            "Thresholds never authorize autofill execution from this sprint packet.",
        ),
    ),
    (
        "Missing data rule",
        "Defines operator-visible behavior when profile data is absent without hiding gaps.",
        (
            "Missing data rules require explicit labels before autofill readiness is marked ready.",
            "Rules forbid silent defaults on submission-adjacent fields without human review prerequisites.",
        ),
    ),
    (
        "Human review prerequisite",
        "Defines mandatory human checkpoints for low confidence, signatures, authorization, or submission "
        "adjacent fields.",
        (
            "Low-confidence autofill targets require explicit human review prerequisites in documented form.",
            "Prerequisites distinguish scoped review from routed production workflows.",
        ),
    ),
    (
        "Field override rule",
        "Captures how overrides are proposed, who reviews them, and how they remain traceable in planning.",
        (
            "Override rules stay preview-only and do not execute runtime overrides from this sprint.",
            "Overrides on submission-adjacent fields require explicit human review prerequisites.",
        ),
    ),
    (
        "Attachment dependency",
        "Lists required attachment families, naming, signatures, and cross-form dependencies without file "
        "IO here.",
        (
            "Dependencies stay descriptive and preview-only without attachment processing.",
            "Dependencies map optional versus mandatory signals when documented in references.",
        ),
    ),
    (
        "Signature or authorization dependency",
        "Flags authorized representative, AOR, and e-signature pathway assumptions as review-first fields.",
        (
            "Signature and authorization fields always require explicit human review in planning rows.",
            "Dependencies never imply executed signatures or live authorization calls from this sprint.",
        ),
    ),
    (
        "Submission-adjacent blocker status",
        "Signals whether portal path, certification, channel, or assurance gaps block readiness in "
        "planning.",
        (
            "Blocker language stays preview-only and does not enqueue submission or autofill jobs.",
            "Blocked rows require explicit rationale and ownership visibility.",
        ),
    ),
    (
        "Acceptance criteria",
        "Field-level pass or fail checks operators use before assigning a form readiness status.",
        (
            "Each field group carries at least two criteria tied to evidence or explicit gap labels.",
            "Criteria reinforce preview-only posture and non-commitment language.",
        ),
    ),
    (
        "Risk note",
        "Captures residual ambiguity, jurisdiction sensitivity, or dependency risk for operator attention.",
        (
            "Risk notes pair with mitigations listed in the risks and mitigations section when material.",
            "Risk notes never assert that risks were cleared without documented human review.",
        ),
    ),
    (
        "Non-production disclaimer",
        "Restates preview-only posture and lack of form processing, autofill execution, form submission, or "
        "live calls.",
        (
            "Disclaimers repeat not form processing, not autofill execution, and not form submission.",
            "Disclaimers appear wherever status language could be misread as go-live automation.",
        ),
    ),
    (
        "Next sprint recommendation",
        "Points operators to Sprint 137 human review workflow readiness in preview-only language.",
        (
            "Recommendations name Sprint 137 as the M1 Human Review Workflow Controlled Build Readiness "
            "Packet.",
            "Recommendations forbid silent expansion into runtime work without explicit authorization.",
        ),
    ),
)

_FORM_READINESS_STATUS_ROWS: tuple[tuple[str, str], ...] = (
    (
        "Not assessed",
        "Readiness row exists but lacks minimum field coverage; must be assessed before planning improves. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Ready for controlled build planning",
        "Field groups are sufficient for operator-controlled form package build planning without execution "
        "promises. " + _STATUS_DISCLAIMER,
    ),
    (
        "Needs form verification",
        "Form version, publisher lineage, or amendment scope requires verification before trust improves. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Needs profile mapping review",
        "Profile source fields, mapping expectations, or unresolved mapping issues need operator review. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Needs confidence rule review",
        "Thresholds, scoring rubrics, or confidence labels need operator review before planning proceeds. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Needs human review gate",
        "Low confidence, signature, authorization, or submission-adjacent fields require human checkpoints. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Blocked before autofill",
        "Unresolved forms, mappings, provenance, confidence, sovereignty, or scope issues block autofill "
        "readiness in planning. " + _STATUS_DISCLAIMER,
    ),
    (
        "Deferred beyond M1",
        "Form or field group is intentionally deferred past M1 while remaining visible in the inventory. "
        + _STATUS_DISCLAIMER,
    ),
)

_PREVIEW_ONLY_FORM_READINESS_RULES: tuple[str, ...] = (
    "Require seeded or demo-safe records only; never import production customer extracts into form "
    "readiness rows.",
    "Do not access real customer data while building or reviewing this form readiness packet.",
    "Do not create form packages, execute autofill, process forms, or submit forms from this sprint packet.",
    "Do not place external API calls, scrapes, live ingestions, or live AI generations while using this "
    "packet.",
    "Do not invoke AI generation, model calls, or automated form filling while using this packet.",
    "Do not activate sources, perform live ingestion, or change production workflows while using this packet.",
    "Keep human judgment, provenance visibility, sovereignty boundaries, and missing-data disclosure "
    "explicit.",
)

_FORM_READINESS_BY_FORM_PACKAGE_AREA: tuple[tuple[str, str], ...] = (
    (
        "SF-424 application cover form",
        "Readiness maps applicant identity, program selection, disclosure, and cover certifications with "
        "profile sources and human gates before any autofill language is treated as informed.",
    ),
    (
        "SF-424A budget information",
        "Readiness captures budget periods, object classes, and indirect cues as planning expectations "
        "without calculations or autofill execution.",
    ),
    (
        "SF-424B assurances",
        "Readiness lists assurance checkboxes and civil rights attestations with mandatory human review "
        "before submission-adjacent fields improve.",
    ),
    (
        "organization profile field mapping",
        "Readiness aligns each form field to a profile source field or missing data rule with unresolved "
        "mapping visibility.",
    ),
    (
        "authorized representative fields",
        "Readiness tracks AOR name, title, contact, and authority statements with signature and "
        "authorization review prerequisites.",
    ),
    (
        "UEI/SAM.gov fields",
        "Readiness records UEI, cage, and registration assumptions with provenance and verification gates "
        "without live SAM queries here.",
    ),
    (
        "indirect cost rate fields",
        "Readiness surfaces rate type, base, and negotiation status with confidence and human review before "
        "financial fields are trusted.",
    ),
    (
        "attachment package requirements",
        "Readiness lists attachment labels, formats, signatures, and optional versus mandatory signals "
        "without file execution.",
    ),
    (
        "signature/authorization dependencies",
        "Readiness flags wet ink, electronic signature, and notarization pathway assumptions as explicit "
        "human review blockers until cleared in planning.",
    ),
    (
        "review and override controls",
        "Readiness documents reviewer roles, override proposals, and audit visibility without implying "
        "runtime enforcement from this sprint.",
    ),
)

_AUTOFILL_PREREQUISITE_RULES: tuple[str, ...] = (
    "Every autofill field must have a profile source field or missing data rule recorded before autofill "
    "readiness planning proceeds.",
    "Every autofill field must preserve provenance in downstream designs even though this sprint performs "
    "no autofill execution.",
    "Confidence thresholds must be visible before controlled build planning treats outputs as informed.",
    "Human review gates must exist for low-confidence autofill before automation is assumed.",
    "Signature and authorization fields require explicit review in planning artifacts before autofill "
    "readiness improves.",
    "Unresolved mapping issues block autofill readiness until mitigated, deferred with rationale, or "
    "rejected.",
)

_HUMAN_GATE_AND_REVIEW_RULES: tuple[str, ...] = (
    "Low-confidence fields require human review before operators treat autofill expectations as informed.",
    "Signature and authorization fields require human review in planning rows before readiness improves.",
    "Submission-adjacent fields require human review because channels, certifications, and cutoffs shift.",
    "Missing data requires explicit operator visibility with labeled gaps rather than silent blanks.",
    "Autofill activation decisions require explicit operator approval outside this planning packet.",
    "No form package is created in this sprint.",
    "No runtime activation occurs in this sprint.",
)

_SOVEREIGNTY_AND_TRUST_REQUIREMENTS: tuple[str, ...] = (
    "Customer owns its data.",
    "No customer data is required for this planning sprint.",
    "No customer data leaves the product during seeded demos.",
    "No model training on customer data without explicit written consent.",
    "Human judgment remains final.",
    "Field provenance remains visible.",
    "Form package readiness must not overpromise implementation readiness.",
)

_SPRINT136_DOES_NOT_BUILD: tuple[str, ...] = (
    "no form package creation",
    "no autofill execution",
    "no form processing",
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

_M1_FORM_PACKAGE_READINESS_EXIT_CRITERIA: tuple[str, ...] = (
    "All eighteen form readiness field groups are documented with purposes and acceptance criteria.",
    "All eight form readiness statuses include explicit non-form-processing, non-autofill-execution, and "
    "non-form-submission disclaimers.",
    "All twelve M1 form package readiness foundations include operator focus statements without runtime "
    "execution.",
    "All ten form readiness by form package area rows include preview mapping language and caveat "
    "expectations.",
    "Autofill prerequisite rules, human gate rules, sovereignty requirements, and preview-only rules are "
    "listed.",
    "Risks and mitigations are recorded with operator discipline expectations for controlled build planning.",
    "Sprint 137 recommendation is captured as the next preview-only human review workflow readiness step.",
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "Autofill execution is implied by planning language",
        "Ban autofill, fill, or run verbs except inside explicit not-autofill-execution disclaimers.",
    ),
    (
        "Form submission is implied too early",
        "Disallow submit, transmit, or portal-send language unless framed as future build scope with "
        "explicit authorization.",
    ),
    (
        "Low-confidence fields are treated as final",
        "Force human review prerequisites and confidence thresholds before any carry-forward language.",
    ),
    (
        "Signature fields are not human-reviewed",
        "Mandate human review gates for signature and authorization dependencies in every planning row.",
    ),
    (
        "Missing data is hidden from operators",
        "Require missing data rules and visible gap labels before autofill readiness improves.",
    ),
    (
        "Customer data handling is implied too early",
        "Sequence sovereignty prerequisites before any customer-specific data language in readiness rows.",
    ),
    (
        "Provenance requirements are skipped",
        "Block autofill readiness until provenance fields are documented or deferred with rationale.",
    ),
    (
        "Form automation overpromises readiness",
        "Tie statuses to explicit field coverage, blockers, and acceptance criteria reviewers can audit.",
    ),
    (
        "Form readiness becomes theater instead of control",
        "Require traceable identities, mapping states, and risk notes alongside every status movement.",
    ),
)

_SPRINT137_RECOMMENDED_NEXT_STEP = (
    "Sprint 137 should deliver the M1 Human Review Workflow Controlled Build Readiness Packet, still "
    "preview-only unless the operator explicitly authorizes runtime work."
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _field_group_payloads() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, (name, purpose, criteria) in enumerate(_FORM_READINESS_FIELD_GROUP_ROWS, start=1):
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
        {"foundation_area": a, "operator_focus": b} for a, b in _M1_FORM_PACKAGE_READINESS_FOUNDATIONS
    ]


def _status_payloads() -> list[dict[str, str]]:
    return [{"status": s, "definition": d} for s, d in _FORM_READINESS_STATUS_ROWS]


def _form_package_area_payloads() -> list[dict[str, str]]:
    return [
        {"form_package_area": a, "form_readiness_preview": b} for a, b in _FORM_READINESS_BY_FORM_PACKAGE_AREA
    ]


def _risk_payloads() -> list[dict[str, str]]:
    return [{"risk": r, "mitigation": m} for r, m in _RISK_MITIGATIONS]


def build_active_source_activation_m1_form_package_controlled_build_readiness_packet() -> dict[str, Any]:
    """Return the Sprint 136 M1 form package controlled build readiness packet (deterministic)."""
    proof = {
        "sprint_136_m1_form_package_controlled_build_readiness_packet_is_stateless": True,
        "sprint_136_m1_form_package_controlled_build_readiness_packet_is_side_effect_free": True,
        "sprint_136_m1_form_package_controlled_build_readiness_packet_is_preview_only": True,
        "sprint_136_m1_form_package_controlled_build_readiness_packet_performs_no_runtime_work": True,
        "sprint_136_m1_form_package_controlled_build_readiness_packet_emits_operator_planning_only": True,
    }
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 136,
        "packet_name": "NativeForge M1 Form Package Controlled Build Readiness Packet",
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_define_form_package_readiness": True,
        "may_define_autofill_prerequisites": True,
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
        "actual_form_packages_created": 0,
        "actual_autofill_runs": 0,
        "actual_forms_processed": 0,
        "m1_form_package_controlled_build_readiness_foundations": _foundation_payloads(),
        "form_readiness_field_groups": _field_group_payloads(),
        "form_readiness_statuses": _status_payloads(),
        "form_readiness_status_universal_disclaimer": _STATUS_DISCLAIMER,
        "preview_only_form_readiness_rules": list(_PREVIEW_ONLY_FORM_READINESS_RULES),
        "form_readiness_by_form_package_area": _form_package_area_payloads(),
        "autofill_prerequisite_rules": list(_AUTOFILL_PREREQUISITE_RULES),
        "human_gate_and_review_rules": list(_HUMAN_GATE_AND_REVIEW_RULES),
        "sovereignty_and_trust_requirements": list(_SOVEREIGNTY_AND_TRUST_REQUIREMENTS),
        "sprint_136_does_not_build": list(_SPRINT136_DOES_NOT_BUILD),
        "m1_form_package_readiness_exit_criteria": list(_M1_FORM_PACKAGE_READINESS_EXIT_CRITERIA),
        "risks_and_mitigations": _risk_payloads(),
        "sprint_137_recommended_next_step": _SPRINT137_RECOMMENDED_NEXT_STEP,
        "sprint_136_m1_form_package_controlled_build_readiness_packet_proof": proof,
    }
    return _json_safe(out)


def _ordered_field_groups(pkt: dict[str, Any]) -> list[dict[str, Any]]:
    raw = pkt.get("form_readiness_field_groups")
    if isinstance(raw, list):
        groups = [g for g in raw if isinstance(g, dict)]
        groups.sort(key=lambda g: g.get("priority") if isinstance(g.get("priority"), int) else 0)
        return groups
    return _field_group_payloads()


def render_active_source_activation_m1_form_package_controlled_build_readiness_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render the operator-facing markdown packet (deterministic; uses ``packet`` when provided)."""
    pkt = packet if isinstance(packet, dict) else (
        build_active_source_activation_m1_form_package_controlled_build_readiness_packet()
    )
    groups = _ordered_field_groups(pkt)
    lines: list[str] = [
        "# NativeForge M1 Form Package Controlled Build Readiness Packet v1",
        "",
        "## 1. Purpose",
        "",
        "This packet defines the M1 planning layer for form package preview and autofill controlled build "
        "readiness. It is preview-only: it structures form scope, profile mappings, provenance and "
        "confidence expectations, human gates, sovereignty and security guardrails, and acceptance criteria "
        "for operators without form package creation, autofill execution, form processing, form submission, "
        "external calls, scraping, or customer data access.",
        "",
        "## 2. Why This Comes After NOFO Extraction Readiness",
        "",
        "Sprint 135 defined NOFO extraction readiness so extracted requirements stay bounded, provenance "
        "visible, and human-gated before extraction language appears. Sprint 136 applies controlled build "
        "discipline to converting those extracted requirements and organization profile data into form "
        "package readiness without executing autofill or submission.",
        "",
        "## 3. M1 Form Package Readiness Objective",
        "",
        "Deliver a preview-only readiness framework that prevents form automation from starting before forms, "
        "mappings, provenance, confidence thresholds, human gates, sovereignty and security dependencies, "
        "and blockers are visible—without runnable autofill promises, runtime execution, form processing, or "
        "form submission in this sprint.",
        "",
        "M1 form package controlled build readiness foundations:",
        "",
    ]
    foundations = pkt.get("m1_form_package_controlled_build_readiness_foundations")
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
            "## 4. Preview-Only Form Readiness Rules",
            "",
        ]
    )
    for rule in pkt.get("preview_only_form_readiness_rules") or list(_PREVIEW_ONLY_FORM_READINESS_RULES):
        if isinstance(rule, str) and rule.strip():
            lines.append(f"- {rule}")
    lines.extend(
        [
            "",
            "Preview-only form readiness rules restated: seeded or demo-safe records only; no real customer "
            "data; no form package creation; no autofill execution; no form processing; no form submission; "
            "no external calls.",
            "",
            "## 5. Required Form Readiness Field Groups",
            "",
            "Eighteen field groups structure every form readiness row:",
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
            "## 6. Form Readiness Status Definitions",
            "",
            "Eight preview-only form readiness statuses apply. Each status explicitly disclaims form "
            "processing, autofill execution, and form submission:",
            "",
        ]
    )
    statuses = pkt.get("form_readiness_statuses")
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
    lines.extend(["", "## 8. Form Readiness by Form Package Area", ""])
    mapping = pkt.get("form_readiness_by_form_package_area")
    if not isinstance(mapping, list):
        mapping = _form_package_area_payloads()
    for row in mapping:
        if not isinstance(row, dict):
            continue
        ar = row.get("form_package_area")
        preview = row.get("form_readiness_preview")
        if isinstance(ar, str) and isinstance(preview, str):
            lines.append(f"- **{ar}**: {preview}")
    lines.extend(["", "## 9. Autofill Prerequisite Rules", ""])
    for item in pkt.get("autofill_prerequisite_rules") or list(_AUTOFILL_PREREQUISITE_RULES):
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
    lines.extend(["", "## 12. What Sprint 136 Does Not Build", "", "Sprint 136 explicitly does not build:", ""])
    for item in pkt.get("sprint_136_does_not_build") or list(_SPRINT136_DOES_NOT_BUILD):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 13. M1 Form Package Readiness Exit Criteria",
            "",
        ]
    )
    for c in pkt.get("m1_form_package_readiness_exit_criteria") or list(_M1_FORM_PACKAGE_READINESS_EXIT_CRITERIA):
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
            "## 15. Sprint 137 Recommended Next Step",
            "",
            pkt.get("sprint_137_recommended_next_step") or _SPRINT137_RECOMMENDED_NEXT_STEP,
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
