"""Sprint 124: M0 SF-424 autofill preview planning packet (preview-only).

Deterministic operator packet for demo-safe SF-424 autofill preview planning from seeded
entity profiles and seeded opportunities. No form generation, submission, Grants.gov
Workspace, or runtime autofill.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = "nf_active_source_activation_m0_sf424_autofill_preview_planning_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

M0_SF424_PREVIEW_FOUNDATIONS: tuple[str, ...] = (
    "Entity profile to SF-424 mapping preview",
    "Applicant legal name preview",
    "UEI and EIN preview",
    "Applicant address preview",
    "Authorized representative preview",
    "Congressional district preview",
    "Assistance listing/CFDA preview",
    "Opportunity title and number preview",
    "Human review and correction workflow",
    "Future form package readiness",
)

_FIELD_GROUP_ROWS: tuple[tuple[str, str, tuple[str, str]], ...] = (
    (
        "Application type",
        "Demo-safe label for new, continuation, or revision posture without binding submission type.",
        (
            "Application type values are fixture enums with explicit preview-only watermarking.",
            "Type selection never triggers Grants.gov or agency routing in M0 planning artifacts.",
        ),
    ),
    (
        "Applicant legal name",
        "Seeded legal entity name shown for buyer time-savings stories without live directory sync.",
        (
            "Names come from seeded organizational entity profiles or synthetic demo personas only.",
            "Discrepancies route to human correction notes rather than silent overwrites.",
        ),
    ),
    (
        "Employer identification number",
        "High-sensitivity identifier preview from seeds with masking guidance in operator scripts.",
        (
            "Missing EIN must be flagged with visible missing-data language in all preview states.",
            "EIN fields never call IRS, SAM.gov, or external validation services in M0.",
        ),
    ),
    (
        "UEI",
        "Unique Entity Identifier preview from seeded profile data without SAM.gov lookups.",
        (
            "Missing UEI must be flagged with visible missing-data language in all preview states.",
            "UEI preview must not imply live SAM.gov registration or refresh.",
        ),
    ),
    (
        "Applicant address",
        "Structured mailing or physical address blocks sourced from seeded entity profile fields.",
        (
            "Addresses are synthetic or seeded with documented placeholders for tribal lands when needed.",
            "Partial addresses downgrade preview readiness with explicit gap callouts.",
        ),
    ),
    (
        "Applicant type",
        "Applicant category labels for demo narratives without legal entity classification automation.",
        (
            "Applicant type lists are bounded demo vocabularies aligned to seeded profile stories.",
            "Type values cannot auto-lock eligibility determinations in M0 preview language.",
        ),
    ),
    (
        "Congressional district",
        "District strings derived from seeded geography metadata for coverage storytelling only.",
        (
            "Districts are fixture-backed with no live redistricting or census API calls.",
            "Ambiguous district seeds require human review before preview-ready claims.",
        ),
    ),
    (
        "Federal agency",
        "Agency names and codes aligned to seeded opportunity metadata for buyer context.",
        (
            "Agency fields reference seeded opportunity records only in M0 posture.",
            "Agency drift or unknown codes block opportunity-linked preview readiness when ambiguous.",
        ),
    ),
    (
        "Assistance listing / CFDA",
        "Catalog numbers and titles from seeded assistance metadata for form-adjacent previews.",
        (
            "CFDA tuples are demo fixtures with explicit non-production provenance labels.",
            "Missing assistance listing rows surface visible warnings without external catalog fetches.",
        ),
    ),
    (
        "Funding opportunity number",
        "Opportunity identifier tying the preview to a seeded pursuit opportunity record.",
        (
            "Missing opportunity number must block opportunity-linked preview until corrected.",
            "Opportunity numbers never imply live Grants.gov workspace linkage in M0.",
        ),
    ),
    (
        "Funding opportunity title",
        "Human-readable opportunity title from seeds for buyer alignment with pipeline cards.",
        (
            "Titles mirror seeded opportunity records referenced by pursuit pipeline planning.",
            "Title-only seeds without opportunity number cannot claim opportunity-linked preview.",
        ),
    ),
    (
        "Competition identification number",
        "Competition or CFDA-related competition identifiers from seeded opportunity packages.",
        (
            "Competition IDs are optional fixtures with visible absent states when not provided.",
            "Competition identifiers do not trigger competition workspace actions in M0.",
        ),
    ),
    (
        "Authorized representative name",
        "Seeded signer or AOR name fields for human-in-the-loop demo stories.",
        (
            "Missing authorized representative must block preview-ready status in specifications.",
            "Representative names use synthetic personas unless explicitly seeded for demos.",
        ),
    ),
    (
        "Authorized representative title",
        "Title line for the authorized representative aligned to seeded governance metadata.",
        (
            "Titles are editable in preview narratives and preserved with correction notes.",
            "Stale title seeds must surface review prompts rather than silent updates.",
        ),
    ),
    (
        "Authorized representative contact information",
        "Phone, email, and mailing contact blocks from seeds without outbound messaging.",
        (
            "Contact previews must not send email, SMS, or voice calls from this sprint.",
            "Contact gaps pair with visible missing-field flags and human review routing.",
        ),
    ),
    (
        "Certification and signature readiness",
        "Forward-looking readiness flags describing future signature capture without e-sign I/O.",
        (
            "Certification language is planning-only and forbids submission from M0 preview surfaces.",
            "Readiness states document audit expectations for future runtime packages.",
        ),
    ),
    (
        "Human correction notes",
        "Structured operator and reviewer notes carried beside preview fields for auditability.",
        (
            "Human correction notes must be preserved for future runtime autofill designs.",
            "Notes cannot erase underlying seeded provenance or confidence metadata.",
        ),
    ),
    (
        "Field provenance and confidence",
        "Per-field lineage and confidence indicators visible to buyers without external scoring APIs.",
        (
            "Field confidence must be visible on every previewed SF-424 field group in M0 specs.",
            "Provenance never claims external validation occurred in M0 planning posture.",
        ),
    ),
)

_SF424_PREVIEW_TO_M0_FEATURES: tuple[tuple[str, str], ...] = (
    (
        "organizational entity profile",
        "Supplies applicant legal name, address, EIN, UEI, applicant type, and representative seeds "
        "for deterministic preview rows without customer production profiles.",
    ),
    (
        "seeded opportunity record",
        "Supplies funding opportunity number and title, federal agency, assistance listing/CFDA, "
        "and competition identification fields referenced by pursuit previews.",
    ),
    (
        "pursuit pipeline card",
        "Anchors SF-424 preview stories to the Sprint 123 pipeline card context for readiness "
        "and deadline-adjacent demos without workflow execution.",
    ),
    (
        "requirement checklist preview",
        "Surfaces missing-data flags, attachment-adjacent expectations, and checklist language "
        "alongside SF-424 field coverage for buyers.",
    ),
    (
        "human review workflow",
        "Requires editable fields, correction notes, and gates before preview-ready language "
        "with explicit no-submission posture.",
    ),
    (
        "source provenance display",
        "Shows field provenance and confidence for every previewed group without external calls.",
    ),
    (
        "sovereignty trust explainer",
        "Reinforces human judgment, identifier care, consent boundaries, and demo-only datasets "
        "across SF-424 preview narratives.",
    ),
    (
        "future export readiness",
        "Documents certification, signature, and export audit hooks for later runtime form packages "
        "without generating real SF-424 files today.",
    ),
)

_MISSING_DATA_AND_VALIDATION_PREVIEW_RULES: tuple[str, ...] = (
    "Missing UEI must be flagged in every preview state that shows identifier coverage.",
    "Missing EIN must be flagged in every preview state that shows identifier coverage.",
    "Missing authorized representative must block preview-ready status until human corrections land.",
    "Missing opportunity number must block opportunity-linked preview until seeded data is fixed.",
    "Field confidence must be visible beside preview values in operator markdown and JSON.",
    "No external validation occurs in M0 planning; previews must not imply SAM.gov, IRS, or agency "
    "verification.",
)

_HUMAN_REVIEW_GATES: tuple[str, ...] = (
    "The autofill preview cannot be treated as a final form or submission artifact.",
    "Every autofilled field must remain editable in specifications and demo scripts.",
    "Field provenance must be visible for each previewed value.",
    "Missing required fields must block final preview readiness until resolved or waived in review.",
    "Human correction notes must be preserved for future runtime autofill designs.",
    "No submission can occur from the M0 SF-424 autofill preview planning posture.",
)

_SOVEREIGNTY_AND_TRUST: tuple[str, ...] = (
    "No customer data is required for seeded SF-424 demos; fixtures must stand alone.",
    "No customer data leaves the product during seeded demos beyond intentional operator narration.",
    "No model training on customer data without explicit written consent and governance review.",
    "Form preview never overrides human judgment; it surfaces signals, gaps, and provenance only.",
    "Future runtime form packages must be auditable and exportable per planning commitments.",
    "High-sensitivity identifiers such as EIN and UEI must be handled carefully with masking guidance.",
)

_SPRINT124_DOES_NOT_BUILD: tuple[str, ...] = (
    "No real SF-424 generation",
    "No form submission",
    "No Grants.gov Workspace integration",
    "No Grants.gov API call",
    "No SAM.gov integration",
    "No external validation",
    "No real customer data",
    "No database migration",
    "No frontend UI",
    "No runtime autofill engine",
    "No production form package change",
)

_M0_EXIT_CRITERIA: tuple[str, ...] = (
    "All eighteen SF-424 field groups have documented purposes and at least two acceptance criteria.",
    "Demo-safe autofill rules, missing-data preview rules, and human review gates are operator-visible.",
    "SF-424 preview to M0 feature mapping covers profile, opportunity, pipeline, checklist, review, "
    "provenance, sovereignty explainer, and export readiness surfaces.",
    "Sovereignty and trust requirements address seeded demos, identifiers, consent, and auditability.",
    "Risks and mitigations address preview versus production misreads for forms and identifiers.",
    "Sprint 125 next step records the M0 Requirement Extraction Checklist Preview Planning Packet.",
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "Preview is mistaken for a final form",
        "Banner preview-only headers, forbid submission verbs in M0 copy, and pair previews with "
        "human review gate lists.",
    ),
    (
        "Missing required fields are not visible",
        "Require missing-data flags for UEI, EIN, opportunity number, and representative fields with "
        "blocking rules.",
    ),
    (
        "Identifiers are treated casually",
        "Document masking, least-privilege demo datasets, and separate handling notes for EIN and UEI.",
    ),
    (
        "Field provenance is hidden",
        "Mandate provenance and confidence visibility in JSON and markdown for every field group.",
    ),
    (
        "Authorized representative data is stale",
        "Route stale seeds to human review, preserve correction notes, and block preview-ready until "
        "updated.",
    ),
    (
        "External validation is implied but not performed",
        "Repeat explicitly that M0 performs no SAM.gov, Grants.gov, or agency validation calls.",
    ),
    (
        "Seeded data is confused with customer data",
        "Label seeds, segregate fixtures, and ban production extracts from demo environments.",
    ),
    (
        "Form preview language implies submission capability",
        "Use planning-only verbs, list no submission gates, and cross-link Sprint 124 does-not-build "
        "items.",
    ),
    (
        "Human review is bypassed",
        "Block preview-ready language without representative coverage and editable field guarantees.",
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
        {"m0_surface_area": a, "sf424_preview_field_use": u} for a, u in _SF424_PREVIEW_TO_M0_FEATURES
    ]


def _risk_payloads() -> list[dict[str, str]]:
    return [{"risk": r, "mitigation": m} for r, m in _RISK_MITIGATIONS]


def build_active_source_activation_m0_sf424_autofill_preview_planning_packet() -> dict[str, Any]:
    """Return the Sprint 124 M0 SF-424 autofill preview planning packet (deterministic)."""
    proof = {
        "sprint_124_m0_sf424_autofill_preview_planning_packet_is_stateless": True,
        "sprint_124_m0_sf424_autofill_preview_planning_packet_is_side_effect_free": True,
        "sprint_124_m0_sf424_autofill_preview_planning_packet_is_preview_only": True,
        "sprint_124_m0_sf424_autofill_preview_planning_packet_performs_no_runtime_work": True,
        "sprint_124_m0_sf424_autofill_preview_planning_packet_emits_operator_planning_only": True,
    }
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 124,
        "packet_name": "NativeForge M0 SF-424 Autofill Preview Planning Packet",
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_define_sf424_preview_scope": True,
        "may_define_demo_safe_autofill_fields": True,
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
        "actual_form_generations": 0,
        "actual_autofill_writes": 0,
        "actual_grants_workspace_calls": 0,
        "m0_sf424_preview_foundations": list(M0_SF424_PREVIEW_FOUNDATIONS),
        "sf424_field_groups": _field_group_payloads(),
        "sf424_preview_to_m0_feature_mapping": _mapping_payloads(),
        "missing_data_and_validation_preview_rules": list(_MISSING_DATA_AND_VALIDATION_PREVIEW_RULES),
        "human_review_gates": list(_HUMAN_REVIEW_GATES),
        "sovereignty_and_trust_requirements": list(_SOVEREIGNTY_AND_TRUST),
        "sprint_124_does_not_build": list(_SPRINT124_DOES_NOT_BUILD),
        "m0_sf424_preview_planning_exit_criteria": list(_M0_EXIT_CRITERIA),
        "risks_and_mitigations": _risk_payloads(),
        "sprint_124_m0_sf424_autofill_preview_planning_packet_proof": proof,
    }
    return _json_safe(out)


def _ordered_field_groups(pkt: dict[str, Any]) -> list[dict[str, Any]]:
    raw = pkt.get("sf424_field_groups")
    if isinstance(raw, list):
        groups = [g for g in raw if isinstance(g, dict)]
        groups.sort(key=lambda g: g.get("priority") if isinstance(g.get("priority"), int) else 0)
        return groups
    return _field_group_payloads()


def render_active_source_activation_m0_sf424_autofill_preview_planning_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render the operator-facing markdown packet (deterministic; uses ``packet`` when provided)."""
    pkt = packet if isinstance(packet, dict) else (
        build_active_source_activation_m0_sf424_autofill_preview_planning_packet()
    )
    groups = _ordered_field_groups(pkt)
    lines: list[str] = [
        "# NativeForge M0 SF-424 Autofill Preview Planning Packet v1",
        "",
        "## 1. Purpose",
        "",
        "This packet defines the M0 planning layer for demo-safe SF-424 autofill previews built from seeded "
        "organizational entity profile data and seeded opportunity data. It is preview-only operator "
        "documentation and structured planning output; it does not generate real SF-424 forms, submit "
        "applications, call Grants.gov Workspace, perform runtime autofill, or access production customer "
        "records.",
        "",
        "## 2. Why This Comes After Pipeline Planning",
        "",
        "Sprint 123 defined pursuit pipeline and deadline tracking previews that make a pursued opportunity "
        "visible without production tasks. Sprint 124 defines how that pursued opportunity can show SF-424 "
        "form readiness through autofill previews without producing or submitting a real form.",
        "",
        "## 3. M0 SF-424 Preview Objective",
        "",
        "Deliver a demo-safe autofill preview that helps a buyer understand time savings, field reuse from "
        "entity profiles, missing-data flags, provenance and confidence signals, and human review before any "
        "form output exists.",
        "",
        "## 4. Demo-Safe Autofill Rules",
        "",
        "M0 SF-424 autofill previews require seeded or demo-safe organizational entity profiles and seeded or "
        "demo-safe opportunity records only. Operators must not use real customer data, generate real "
        "SF-424 packages, integrate Grants.gov Workspace, submit forms, or invoke external validation APIs "
        "while presenting this posture.",
        "",
        "Demo-safe autofill restrictions restated: no real customer data; no real form generation; no Grants.gov "
        "Workspace integration; no submission; no external validation calls.",
        "",
        "## 5. Required SF-424 Field Groups",
        "",
        "Eighteen field groups structure SF-424 autofill preview planning:",
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
    lines.extend(["", "## 7. SF-424 Preview to M0 Feature Mapping", ""])
    mapping = pkt.get("sf424_preview_to_m0_feature_mapping")
    if not isinstance(mapping, list):
        mapping = _mapping_payloads()
    for row in mapping:
        if not isinstance(row, dict):
            continue
        area = row.get("m0_surface_area")
        use = row.get("sf424_preview_field_use")
        if isinstance(area, str) and isinstance(use, str):
            lines.append(f"- **{area}**: {use}")
    lines.extend(["", "## 8. Missing Data and Validation Preview Rules", ""])
    for item in pkt.get("missing_data_and_validation_preview_rules") or list(
        _MISSING_DATA_AND_VALIDATION_PREVIEW_RULES
    ):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 9. Human Review Gates", "", "Mandatory gates:", ""])
    for gate in pkt.get("human_review_gates") or list(_HUMAN_REVIEW_GATES):
        if isinstance(gate, str) and gate.strip():
            lines.append(f"- {gate}")
    lines.extend(["", "## 10. Sovereignty and Trust Requirements", ""])
    for req in pkt.get("sovereignty_and_trust_requirements") or list(_SOVEREIGNTY_AND_TRUST):
        if isinstance(req, str) and req.strip():
            lines.append(f"- {req}")
    lines.extend(["", "## 11. What Sprint 124 Does Not Build", "", "Sprint 124 explicitly does not build:", ""])
    for item in pkt.get("sprint_124_does_not_build") or list(_SPRINT124_DOES_NOT_BUILD):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 12. M0 Exit Criteria for SF-424 Preview Planning",
            "",
        ]
    )
    for c in pkt.get("m0_sf424_preview_planning_exit_criteria") or list(_M0_EXIT_CRITERIA):
        if isinstance(c, str) and c.strip():
            lines.append(f"- {c}")
    lines.extend(["", "## 13. Risks and Mitigations", ""])
    for row in pkt.get("risks_and_mitigations") or _risk_payloads():
        if isinstance(row, dict):
            r = row.get("risk")
            m = row.get("mitigation")
            if isinstance(r, str) and isinstance(m, str):
                lines.append(f"- **Risk**: {r} — **Mitigation**: {m}")
    lines.extend(
        [
            "",
            "## 14. Sprint 125 Recommended Next Step",
            "",
            "Sprint 125 should deliver the M0 Requirement Extraction Checklist Preview Planning Packet, still "
            "preview-only and demo-safe unless the operator explicitly authorizes runtime work.",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
