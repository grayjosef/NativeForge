"""Sprint 118: M0 Organizational Entity Profile planning packet (preview-only; no runtime).

Deterministic operator packet that defines the first M0 implementation planning layer for NativeForge's reusable
Organizational Entity Profile. Does not migrate databases, expose APIs, render UI, call SAM.gov, ingest customer data,
generate forms, or invoke LLMs.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = "nf_active_source_activation_m0_organizational_entity_profile_planning_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

M0_ENTITY_PROFILE_FOUNDATIONS: tuple[str, ...] = (
    "Tribal eligibility matching",
    "Mission and funding priority matching",
    "SF-424 autofill preview",
    "Key contacts and authorized representative reuse",
    "Indirect cost rate and certification tracking",
    "Demo-safe narrative reuse",
    "Human-reviewed form output",
    "Future audit log and data export readiness",
    "Sovereignty-first data handling",
    "Future M1/M2 expansion without schema chaos",
)

_FIELD_GROUP_ROWS: tuple[tuple[str, str, tuple[str, str]], ...] = (
    (
        "Legal identity",
        "Legal names, EIN or equivalent identifiers, and DUNS where applicable for demo fixtures.",
        (
            "Captures legal entity name and any trade name aliases needed for SF-424 preview labels.",
            "Distinguishes demo placeholder identifiers from any future production-verified values.",
        ),
    ),
    (
        "Entity classification",
        "Tribal government, Native nonprofit, Native Hawaiian organization, consortium, or other Native-serving "
        "entity types without hardcoding a single federal recognition assumption.",
        (
            "Supports federally recognized tribes, state-recognized tribes, and Native nonprofits in the same schema.",
            "Classification labels are editable and never imply automatic legal eligibility outcomes.",
        ),
    ),
    (
        "Location and service area",
        "Headquarters, mailing, and primary service geographies for mission-fit and eligibility preview signals.",
        (
            "Service area polygons or lists are optional and clearly marked as demo-derived when seeded.",
            "Geography fields support multi-jurisdiction Native nations and Pacific contexts.",
        ),
    ),
    (
        "Authorized officials",
        "Authorized representative and signing officials required for SF-424 and assurance previews.",
        (
            "At least one authorized official role is modeled with name, title, and contact channel placeholders.",
            "Missing authorized representative blocks final autofill preview readiness in M0 rules.",
        ),
    ),
    (
        "Grants and finance contacts",
        "Dedicated grants management and finance points of contact for pursuit workflow handoffs.",
        (
            "Contacts are reusable across opportunities without implying automated submission authority.",
            "Contact records carry demo-safe provenance stamps when loaded from fixtures.",
        ),
    ),
    (
        "Financial profile",
        "High-level financial posture fields suitable for previews, excluding sensitive document storage in M0.",
        (
            "Budget scale bands or narrative placeholders replace sensitive statements in demo mode.",
            "No production bank statements or tax returns are modeled as upload targets in M0.",
        ),
    ),
    (
        "Certifications and assurances",
        "Debarment, lobbying, and other assurance flags as non-binding preview checklists.",
        (
            "Certification answers default to unknown until human review in demo scripts.",
            "Assurance text references public boilerplate only, not executed legal instruments.",
        ),
    ),
    (
        "SAM.gov and UEI data",
        "UEI and registration placeholders for autofill preview without live SAM.gov integration.",
        (
            "SAM fields are optional strings with explicit demo fixture labels, never live-validated in M0.",
            "Missing UEI or SAM placeholders blocks final preview readiness until operator acknowledges demo posture.",
        ),
    ),
    (
        "Indirect cost rate data",
        "Negotiated rate identifiers, effective dates, and rate type labels for checklist previews.",
        (
            "Indirect rate fields accept seeded values and disclaim audit or negotiation status.",
            "Rate documents are out of scope for M0 attachment storage; text summaries only when demo-safe.",
        ),
    ),
    (
        "Organizational capacity narratives",
        "Reusable capacity statements for NOFO alignment previews and human-edited reuse.",
        (
            "Narratives ship as editable text blocks, never LLM-generated in this planning packet.",
            "Capacity text is versioned in fixtures with reviewer attribution in demo scripts.",
        ),
    ),
    (
        "Community profile narrative",
        "Community demographics and priorities as sovereignty-respecting narrative placeholders.",
        (
            "Community narrative fields avoid collecting identifiable community member PII in M0 demos.",
            "Narratives remain editable after reuse into pursuit artifacts.",
        ),
    ),
    (
        "Standard attachment inventory",
        "Inventory of expected attachments without storing production files in M0.",
        (
            "Attachment list references template names only, not binary uploads, in M0 scope.",
            "Inventory items map to human review gates before any future upload feature.",
        ),
    ),
    (
        "Funding priorities",
        "Program areas, pass-through preferences, and strategic funding themes for mission fit scoring.",
        (
            "Priorities are rankable and explainable to operators during walkthroughs.",
            "Mission fit scores treat priorities as advisory inputs with override paths.",
        ),
    ),
    (
        "Match capacity and staff capacity",
        "Match share assumptions and staffing capacity signals for deadline and workload logic previews.",
        (
            "Capacity numbers are bounded demo inputs with clear non-production labeling.",
            "Deadline and staffing logic consumes these fields only as deterministic preview calculations.",
        ),
    ),
    (
        "Data sovereignty preferences",
        "Data residency, retention intent, export expectations, and consent boundaries for trust explainers.",
        (
            "Preferences are declarative metadata, not enforced infrastructure controls in M0.",
            "Sovereignty trust explainer surfaces these preferences without implying private cloud delivery in M0.",
        ),
    ),
)

_ENTITY_PROFILE_TO_M0_FEATURES: tuple[tuple[str, str], ...] = (
    (
        "Tribal eligibility tagging",
        "Uses legal identity, entity classification, location and service area, and certifications to drive "
        "rules-based preview tags.",
    ),
    (
        "Mission fit scoring",
        "Uses funding priorities, organizational capacity narratives, and community profile narrative inputs.",
    ),
    (
        "SF-424 autofill preview",
        "Uses legal identity, authorized officials, SAM.gov and UEI placeholders, and financial profile summaries.",
    ),
    (
        "Key contacts reuse",
        "Uses authorized officials and grants and finance contacts across pursuits and preview panels.",
    ),
    (
        "Certification reuse",
        "Uses certifications and assurances plus indirect cost rate data for checklist previews.",
    ),
    (
        "Narrative reuse",
        "Uses organizational capacity narratives and community profile narrative blocks in demo outputs.",
    ),
    (
        "Deadline and staff capacity logic",
        "Uses match capacity and staff capacity alongside funding priorities for workload previews.",
    ),
    (
        "Sovereignty trust explainer",
        "Uses data sovereignty preferences with explicit tribe-owned data framing in operator copy.",
    ),
)

_HUMAN_REVIEW_GATES: tuple[str, ...] = (
    "Profile data cannot be treated as verified unless manually reviewed.",
    "Autofill preview cannot be finalized without human approval.",
    "Narrative reuse must remain editable.",
    "Any missing UEI, SAM, or authorized representative field must block final preview readiness.",
    "Profile-based recommendations must be overrideable.",
)

_SOVEREIGNTY_AND_TRUST: tuple[str, ...] = (
    "Tribe owns its data.",
    "No customer data is used for model training without explicit written consent.",
    "Export path required before paid pilot readiness.",
    "Audit log required before paid pilot readiness.",
    "Configurable retention is a future readiness requirement.",
    "Private deployment remains later-stage, not M0.",
)

_SPRINT118_DOES_NOT_BUILD: tuple[str, ...] = (
    "No database migration.",
    "No API route.",
    "No frontend form.",
    "No SAM.gov integration.",
    "No live validation.",
    "No production customer onboarding.",
    "No real attachment upload.",
    "No LLM narrative generation.",
    "No form generation.",
    "No billing or tenant administration.",
)

_M0_EXIT_CRITERIA: tuple[str, ...] = (
    "All fifteen field groups are defined with documented intent and demo-safe boundaries.",
    "Acceptance criteria exist for every field group and are reviewable by operators.",
    "Entity profile to M0 feature mapping is complete for eligibility, mission fit, SF-424 preview, contacts, "
    "certifications, narratives, capacity logic, and sovereignty explainers.",
    "Human review gates and sovereignty requirements are written, repeatable, and referenced in operator scripts.",
    "Risks and mitigations are recorded with owners for schema depth, sensitivity, demo confusion, Native nonprofit "
    "representation, recognition assumptions, authorized representative coverage, SAM verification posture, and "
    "sovereignty strength.",
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "Schema too shallow for SF-424 reuse",
        "Trace every SF-424 preview field to a field group owner and extend groups before implementation.",
    ),
    (
        "Collecting too much sensitive data too early",
        "Default to narrative summaries and bands; defer document ingestion until post-M0 authorization.",
    ),
    (
        "Confusing demo data with production readiness",
        "Stamp demo fixtures, block final preview without explicit human acknowledgment, and repeat labeling in UI.",
    ),
    (
        "Failing to represent Native nonprofits and Native Hawaiian organizations",
        "Model entity classification explicitly for Native 501(c)(3) and Native Hawaiian org paths with test cases.",
    ),
    (
        "Hardcoding federally recognized tribe assumptions",
        "Support multiple recognition contexts and keep eligibility rules data-driven and overrideable.",
    ),
    (
        "Missing authorized representative requirements",
        "Require authorized official group completeness in exit criteria and preview readiness checks.",
    ),
    (
        "Overpromising SAM.gov verification",
        "Document no live SAM.gov integration in M0 and label all SAM fields as placeholders.",
    ),
    (
        "Weak sovereignty posture",
        "Ship sovereignty preferences, export and audit roadmap requirements, and training consent language now.",
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


def _risk_payloads() -> list[dict[str, str]]:
    return [{"risk": r, "mitigation": m} for r, m in _RISK_MITIGATIONS]


def build_active_source_activation_m0_organizational_entity_profile_planning_packet() -> dict[str, Any]:
    """Return the Sprint 118 M0 Organizational Entity Profile planning packet (deterministic, no side effects)."""
    proof = {
        "sprint_118_m0_entity_profile_planning_packet_is_stateless": True,
        "sprint_118_m0_entity_profile_planning_packet_is_side_effect_free": True,
        "sprint_118_m0_entity_profile_planning_packet_is_preview_only": True,
        "sprint_118_m0_entity_profile_planning_packet_performs_no_runtime_work": True,
        "sprint_118_m0_entity_profile_planning_packet_emits_operator_planning_only": True,
    }
    mapping_payload = [{"m0_feature": t, "profile_field_use": d} for t, d in _ENTITY_PROFILE_TO_M0_FEATURES]
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 118,
        "packet_name": "NativeForge M0 Organizational Entity Profile Planning Packet",
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_define_entity_profile_scope": True,
        "may_define_demo_safe_schema": True,
        "may_define_acceptance_criteria": True,
        "may_define_guardrails": True,
        "actual_external_calls": 0,
        "actual_source_ingestions": 0,
        "actual_ai_generations": 0,
        "actual_form_submissions": 0,
        "actual_customer_data_access": 0,
        "actual_runtime_writes": 0,
        "m0_entity_profile_foundations": list(M0_ENTITY_PROFILE_FOUNDATIONS),
        "entity_profile_field_groups": _field_group_payloads(),
        "entity_profile_to_m0_feature_mapping": mapping_payload,
        "human_review_gates": list(_HUMAN_REVIEW_GATES),
        "sovereignty_and_trust_requirements": list(_SOVEREIGNTY_AND_TRUST),
        "sprint_118_does_not_build": list(_SPRINT118_DOES_NOT_BUILD),
        "m0_entity_profile_planning_exit_criteria": list(_M0_EXIT_CRITERIA),
        "risks_and_mitigations": _risk_payloads(),
        "sprint_118_m0_entity_profile_planning_packet_proof": proof,
    }
    return _json_safe(out)


def _ordered_field_groups(pkt: dict[str, Any]) -> list[dict[str, Any]]:
    raw = pkt.get("entity_profile_field_groups")
    if isinstance(raw, list):
        groups = [g for g in raw if isinstance(g, dict)]
        groups.sort(key=lambda g: g.get("priority") if isinstance(g.get("priority"), int) else 0)
        return groups
    return _field_group_payloads()


def render_active_source_activation_m0_organizational_entity_profile_planning_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render the operator-facing markdown packet (deterministic; uses ``packet`` when provided)."""
    pkt = packet if isinstance(packet, dict) else (
        build_active_source_activation_m0_organizational_entity_profile_planning_packet()
    )
    groups = _ordered_field_groups(pkt)
    lines: list[str] = [
        "# NativeForge M0 Organizational Entity Profile Planning Packet v1",
        "",
        "## 1. Purpose",
        "",
        "This packet defines the first M0 implementation planning layer for NativeForge's reusable Organizational "
        "Entity Profile. It is preview-only documentation and structured planning output for operators and engineers; "
        "it does not execute workflows, activate sources, or touch production systems.",
        "",
        "## 2. Why This Comes First",
        "",
        "The Organizational Entity Profile is the foundation for eligibility scoring, SF-424 autofill preview, "
        "reusable narratives, contacts, certifications, funding priorities, and future audit and export workflows. "
        "Without a deliberate profile schema and guardrails, downstream M0 features fragment and demo narratives "
        "lose credibility.",
        "",
        "## 3. M0 Entity Profile Objective",
        "",
        "Deliver a demo-safe Organizational Entity Profile that can power seeded opportunity matching, SF-424 preview "
        "autofill, and pursuit workflow demonstrations without using real customer data.",
        "",
        "## 4. Demo-Safe Entity Profile Rules",
        "",
        "M0 requires seeded or demo-safe data only. Operators must not load real tribal customer data, perform live "
        "SAM.gov lookups, run external validation calls, store production attachments, or collect sensitive financial "
        "documents in M0 fixtures.",
        "",
        "Restrictions restated: no real tribal customer data; no live SAM.gov lookups; no external validation "
        "calls; no production attachments; no sensitive financial documents.",
        "",
        "## 5. Required Field Groups",
        "",
        "Fifteen field groups structure the profile:",
        "",
    ]
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
            "## 6. Field-Level Acceptance Criteria",
            "",
        ]
    )
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
    lines.extend(
        [
            "## 7. Entity Profile to M0 Feature Mapping",
            "",
        ]
    )
    mapping = pkt.get("entity_profile_to_m0_feature_mapping")
    if not isinstance(mapping, list):
        mapping = [{"m0_feature": t, "profile_field_use": d} for t, d in _ENTITY_PROFILE_TO_M0_FEATURES]
    for row in mapping:
        if not isinstance(row, dict):
            continue
        feat = row.get("m0_feature")
        use = row.get("profile_field_use")
        if isinstance(feat, str) and isinstance(use, str):
            lines.append(f"- **{feat}**: {use}")
    lines.extend(
        [
            "",
            "## 8. Human Review Gates",
            "",
            "Mandatory gates:",
            "",
        ]
    )
    for gate in pkt.get("human_review_gates") or list(_HUMAN_REVIEW_GATES):
        if isinstance(gate, str) and gate.strip():
            lines.append(f"- {gate}")
    lines.extend(
        [
            "",
            "## 9. Sovereignty and Trust Requirements",
            "",
        ]
    )
    for req in pkt.get("sovereignty_and_trust_requirements") or list(_SOVEREIGNTY_AND_TRUST):
        if isinstance(req, str) and req.strip():
            lines.append(f"- {req}")
    lines.extend(
        [
            "",
            "## 10. What Sprint 118 Does Not Build",
            "",
            "Sprint 118 explicitly does not build:",
            "",
        ]
    )
    for item in pkt.get("sprint_118_does_not_build") or list(_SPRINT118_DOES_NOT_BUILD):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 11. M0 Exit Criteria for Entity Profile Planning",
            "",
        ]
    )
    for c in pkt.get("m0_entity_profile_planning_exit_criteria") or list(_M0_EXIT_CRITERIA):
        if isinstance(c, str) and c.strip():
            lines.append(f"- {c}")
    lines.extend(
        [
            "",
            "## 12. Risks and Mitigations",
            "",
        ]
    )
    for row in pkt.get("risks_and_mitigations") or _risk_payloads():
        if isinstance(row, dict):
            r = row.get("risk")
            m = row.get("mitigation")
            if isinstance(r, str) and isinstance(m, str):
                lines.append(f"- **Risk**: {r} — **Mitigation**: {m}")
    lines.extend(
        [
            "",
            "## 13. Sprint 119 Recommended Next Step",
            "",
            "Sprint 119 should deliver the M0 Grants.gov Seeded Opportunity Ingestion Interface Planning Packet, "
            "still preview-only and demo-safe unless the operator explicitly authorizes runtime work.",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
