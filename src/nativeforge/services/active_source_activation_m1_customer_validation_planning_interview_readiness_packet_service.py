"""Sprint 148: M1 customer validation planning and interview readiness packet (preview-only).

Deterministic operator artifact that defines the customer-validation planning model after Sprint 147
documentation consolidation and operator roadmap packet, preparing NativeForge for future tribal and
customer discovery conversations without contacting customers, collecting customer data, scheduling
interviews, activating a pilot, or authorizing runtime work. Preserves roadmap state as a safe
validation-planning lane only—without runtime execution, live customer data, customer outreach,
interview scheduling, customer onboarding, source activation, pilot launch, production activation,
external calls, database migrations, real metric collection, real pilot closeout, optimization
execution, runtime authorization, or runnable implementation workflows. Depends on Sprint 147 as
mandatory prerequisite context after documentation consolidation and operator roadmap preservation.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_customer_validation_planning_interview_readiness_packet_v1"
)
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

_PREREQUISITE_SPRINT147_ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_documentation_consolidation_operator_roadmap_packet_v1"
)
_VERIFICATION_SPRINT146_ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_readiness_rollup_next_phase_decision_boundary_packet_v1"
)
_VERIFICATION_SPRINT147_ARTIFACT_TYPE = (
    "nf_active_source_activation_m1_documentation_consolidation_operator_roadmap_packet_v1"
)

_VALIDATION_AUDIENCE_MAP: tuple[tuple[str, str], ...] = (
    (
        "Tribal government grant staff",
        "Operators who steward tribal grant programs, NOFO intake, and council reporting "
        "obligations; validation should clarify discovery pain and consent boundaries before any "
        "runtime expansion.",
    ),
    (
        "Native-serving nonprofit operators",
        "Leaders balancing mission delivery, fundraising, and compliance; validation should test "
        "support burden, pricing sensitivity, and human review gate acceptability in preview-only "
        "posture.",
    ),
    (
        "Tribal college or university grant staff",
        "TCU teams managing federal education and research opportunities; validation should probe "
        "NOFO complexity, extraction usefulness, and audit or export expectations without live data.",
    ),
    (
        "Alaska Native entity stakeholders",
        "Representatives of Alaska Native corporations, villages, or consortia; validation must "
        "foreground sovereignty, residency, and trust topics without implying outreach execution "
        "from this sprint.",
    ),
    (
        "Native Hawaiian organization stakeholders",
        "Community and organizational leaders in the Hawaiian Islands; validation should respect "
        "distinct governance and data expectations while remaining planning-only here.",
    ),
    (
        "Philanthropic or foundation grant partners",
        "Funders coordinating with Native communities; validation should align on non-extractive "
        "research posture and evidence capture limits before any pilot readiness claims.",
    ),
    (
        "Compliance or finance stakeholders",
        "Roles accountable for SF-424 accuracy, audit trails, and financial controls; validation "
        "should test autofill usefulness versus human review requirements without authorizing forms.",
    ),
    (
        "Executive or council-facing decision makers",
        "Approvers who authorize pilots and partnerships; validation should separate roadmap "
        "preservation from any runtime authorization boundary this packet does not grant.",
    ),
)

_INTERVIEW_READINESS_MODEL: tuple[tuple[str, str], ...] = (
    (
        "Interview goals",
        "Future interviews (not scheduled by this sprint) should aim to validate assumptions listed "
        "in this packet, map product risk questions, and record sovereignty and trust expectations "
        "without extracting sensitive operational data in preview lanes.",
    ),
    (
        "Consent expectations",
        "Any future outreach requires explicit, documented consent from each community or "
        "organization; this packet performs no outreach and collects no customer data.",
    ),
    (
        "Non-extractive research posture",
        "Operators should prioritize community benefit, avoid data hoarding, and treat narratives as "
        "owned by participants; planning text here is template-only until human-approved "
        "protocols exist.",
    ),
    (
        "Question categories",
        "Group future inquiry into discovery pain, NOFO handling, eligibility scoring, forms and "
        "review gates, sovereignty and export posture, operations and pricing, and pilot readiness "
        "without prescribing live scripts in this artifact.",
    ),
    (
        "Evidence capture limits",
        "Future evidence capture must stay within consent scope, avoid copying regulated payloads "
        "into unapproved stores, and default to operator-held notes outside NativeForge until "
        "authorized.",
    ),
    (
        "Data handling limits",
        "No live customer data ingestion, no database migration, and no production activation are "
        "implied; all actual customer data access counters remain zero in this builder output.",
    ),
    (
        "Follow-up boundaries",
        "This sprint does not schedule interviews, onboard customers, or authorize follow-up "
        "automation; follow-up requires separate human approvals and governance records.",
    ),
    (
        "Human review requirements",
        "Recorded human operator approval is required before any interview protocol, outreach list, "
        "or customer validation activity is treated as authorized; software output cannot substitute.",
    ),
)

_ASSUMPTIONS_TO_VALIDATE: tuple[str, ...] = (
    "Native-relevant opportunity discovery pain: whether operators experience findability and "
    "signal-to-noise issues that NativeForge-style discovery would relieve without harmful "
    "automation.",
    "NOFO complexity and extraction usefulness: whether structured extraction materially reduces "
    "burden versus risks of misinterpretation absent strong human review.",
    "Eligibility and mission-fit scoring usefulness: whether transparent scoring aids triage without "
    "eroding trust when missions are nuanced or multi-sovereign.",
    "SF-424 autofill usefulness: whether draft autofill accelerates compliant drafts versus "
    "creating hidden liability if council or finance review is skipped.",
    "Human review gate acceptability: whether mandatory human review gates match stakeholder "
    "expectations for accountability and sovereignty.",
    "Data sovereignty expectations: where data may reside, who may access it, and what deletion or "
    "export guarantees communities require before any runtime expansion.",
    "Audit and export expectations: what audit trails, exports, and evidence formats compliance and "
    "tribal finance stakeholders need for defensible submissions.",
    "Support burden and pricing sensitivity: what service levels and pricing models are viable for "
    "Native-serving organizations with constrained operations staff.",
    "Pilot readiness requirements: what prerequisites communities define before any pilot launch, "
    "distinct from this preview-only planning packet.",
)

_PRODUCT_RISK_QUESTIONS: tuple[str, ...] = (
    "Does automated opportunity surfacing risk surfacing ineligible or culturally mismatched "
    "opportunities that damage trust if not tightly bounded by human review?",
    "Could eligibility or mission-fit scoring be misread as a guarantee of award success or "
    "eligibility, creating liability for NativeForge or partners?",
    "Does SF-424 autofill tempt skipping legal, finance, or council review in ways that violate "
    "organizational policy or tribal law?",
    "Are audit and export features sufficient for tribal and nonprofit compliance regimes without "
    "over-collecting sensitive metadata?",
    "Does pricing or packaging assume staffing levels that Native-serving nonprofits cannot meet, "
    "undermining adoption even if the product is technically sound?",
)

_SOVEREIGNTY_TRUST_VALIDATION_TOPICS: tuple[str, ...] = (
    "Data residency and cross-border handling expectations for tribal, Alaska Native, and Native "
    "Hawaiian contexts.",
    "Community data ownership, deletion timelines, and portability commitments required before trust "
    "increases.",
    "Consent and governance models for sharing narratives or lessons learned outside originating "
    "communities.",
    "Alignment between product audit logs and tribal or organizational records retention rules.",
    "How human review gates intersect with sovereign decision-making bodies versus vendor defaults.",
)

_OUTREACH_BOUNDARY_AND_CONSENT_RULES: tuple[str, ...] = (
    "Outreach boundary: Sprint 148 performs no customer outreach, no contact initiation, and no "
    "marketing or research recruitment; all outreach remains explicitly out of scope until "
    "separately human-approved protocols exist.",
    "Outreach boundary: no interview scheduling, calendar integration, or meeting automation is "
    "authorized or implemented by this sprint or its builders.",
    "Consent rules: future outreach must be opt-in, documented, and revocable; this packet only "
    "defines planning templates and does not capture consent signals.",
    "Consent rules: operators must not treat deterministic preview text as permission to message "
    "communities or import contact lists into production systems.",
    "Customer data boundary: no live customer data access, no customer onboarding, and no pilot "
    "launch are permitted from this artifact; all actual customer data access counters remain zero.",
)

_HUMAN_APPROVAL_REQUIREMENTS: tuple[str, ...] = (
    "Human operator approval is required before any customer validation protocol, outreach plan, or "
    "interview guide derived from this packet is treated as authorized; software rendering cannot "
    "substitute for human operator approval.",
    "Human-authored sign-off must name approvers, dates, jurisdiction, and scope before any future "
    "customer discovery conversation is scheduled or resourced.",
    "Separate explicit human operator approvals remain required before pilot launch, customer "
    "onboarding, source activation, production activation, database migration, real metric "
    "collection, real pilot closeout, optimization execution, runtime authorization, customer "
    "outreach execution, interview scheduling, or any runnable implementation workflow.",
)

_RUNTIME_AUTHORIZATION_BOUNDARY: tuple[str, ...] = (
    "Runtime authorization boundary: Sprint 148 does not authorize runtime work, runtime execution, "
    "live system changes, pilot launch, customer outreach, interview scheduling, or binding go-live "
    "decisions.",
    "Runtime authorization boundary: no software-generated artifact from this builder grants "
    "runtime authorization; authorization remains a human governance act outside this packet.",
    "Runtime authorization boundary: preserving Sprint 147 roadmap consolidation in this packet "
    "must not be read as activating sources, pilots, production systems, or customer data planes.",
    "Runtime authorization boundary: validation planning completeness does not substitute for "
    "recorded approvals required for any future runtime expansion.",
)

_SPRINT148_DOES_NOT_BUILD: tuple[str, ...] = (
    "no pilot launch",
    "no customer outreach",
    "no interview scheduling",
    "no customer onboarding",
    "no customer data access",
    "no database migration",
    "no source activation",
    "no production activation",
    "no real metric collection",
    "no real pilot closeout",
    "no optimization execution",
    "no runtime authorization",
    "no runnable implementation workflow",
    "no runtime execution",
    "no live customer data",
    "no external service call",
    "no AI generation",
    "no API route",
    "no frontend UI",
    "no workflow activation",
    "no form submission",
    "no implicit authorization from this packet",
)

_PACKET_EXIT_CRITERIA: tuple[str, ...] = (
    "Sprint 147 prerequisite is named with artifact type as mandatory documentation consolidation "
    "and operator roadmap packet after consolidation and roadmap preservation.",
    "Sprint 146 readiness rollup and next-phase decision boundary artifact type remains in the "
    "verification path alongside Sprint 147 for regression continuity.",
    "Validation audience map lists all required audiences without implying outreach execution.",
    "Interview readiness model lists all required components in structured output and markdown.",
    "Assumptions to validate include all required topics; product risk and sovereignty validation "
    "sections are present without contradicting preview-only posture.",
    "Outreach boundary and consent rules, human approval requirements, runtime authorization "
    "boundary, sprint 148 does not build list, exit criteria, risks, mitigations, and recommended "
    "next safe action are present with zero actual counters.",
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "Operators confuse planning with permission to outreach",
        "Keep explicit outreach boundary bullets, zero outreach counters, and no interview "
        "scheduling language in both structured output and markdown.",
    ),
    (
        "Sprint 147 prerequisite skipped",
        "Bind prerequisite evidence to the Sprint 147 documentation consolidation artifact type "
        "and section two sequencing rationale.",
    ),
    (
        "Sprint 146 or Sprint 147 verification path dropped",
        "Keep both artifact types in verification path keys and regression tests importing Sprint "
        "146 and Sprint 147 builders.",
    ),
    (
        "Sovereignty expectations oversimplified",
        "List dedicated sovereignty and trust validation topics and forbid treating templates as "
        "community consent.",
    ),
    (
        "Autofill or scoring oversold",
        "Anchor assumptions to validate and product risk questions on human review gates and "
        "non-guarantee language.",
    ),
)

_RECOMMENDED_NEXT_SAFE_ACTION = (
    "The recommended next safe action is recommendation-only: operators should keep Sprint 147 "
    "documentation consolidation and operator roadmap packets and Sprint 146 readiness rollup "
    "artifacts in the verification path, reconcile this validation planning model with human "
    "governance, and obtain explicit human operator approval before any customer outreach, interview "
    "scheduling, customer onboarding, pilot launch, source activation, production activation, "
    "database migration, real metric collection, real pilot closeout, optimization execution, "
    "runtime authorization, or runnable implementation workflow. No such work should begin from "
    "Sprint 148 output alone."
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _audience_payloads() -> list[dict[str, str]]:
    return [{"audience": a, "planning_note": n} for a, n in _VALIDATION_AUDIENCE_MAP]


def _interview_readiness_payloads() -> list[dict[str, str]]:
    return [{"component": c, "guidance": g} for c, g in _INTERVIEW_READINESS_MODEL]


def _risk_payloads() -> list[dict[str, str]]:
    return [{"risk": r, "mitigation": m} for r, m in _RISK_MITIGATIONS]


def build_active_source_activation_m1_customer_validation_planning_interview_readiness_packet() -> (
    dict[str, Any]
):
    """Return the Sprint 148 M1 customer validation planning and interview readiness packet."""
    proof = {
        "sprint_148_m1_customer_validation_planning_interview_readiness_packet_is_stateless": True,
        "sprint_148_m1_customer_validation_planning_interview_readiness_packet_is_side_effect_free": (
            True
        ),
        "sprint_148_m1_customer_validation_planning_interview_readiness_packet_is_preview_only": (
            True
        ),
        (
            "sprint_148_m1_customer_validation_planning_interview_readiness_packet_performs_no_"
            "runtime_work"
        ): True,
        (
            "sprint_148_m1_customer_validation_planning_interview_readiness_packet_emits_operator_"
            "templates_only"
        ): True,
    }
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 148,
        "packet_name": (
            "NativeForge M1 Customer Validation Planning & Interview Readiness Packet"
        ),
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_present_customer_validation_planning_preview_only": True,
        "may_present_interview_readiness_templates_preview_only": True,
        "may_reference_m1_evidence_base_preview_only": True,
        "prerequisite_documentation_consolidation_operator_roadmap_sprint": 147,
        "prerequisite_documentation_consolidation_operator_roadmap_artifact_type": (
            _PREREQUISITE_SPRINT147_ARTIFACT_TYPE
        ),
        "verification_path_readiness_rollup_next_phase_decision_boundary_sprint": 146,
        "verification_path_readiness_rollup_next_phase_decision_boundary_artifact_type": (
            _VERIFICATION_SPRINT146_ARTIFACT_TYPE
        ),
        "verification_path_documentation_consolidation_operator_roadmap_sprint": 147,
        "verification_path_documentation_consolidation_operator_roadmap_artifact_type": (
            _VERIFICATION_SPRINT147_ARTIFACT_TYPE
        ),
        "actual_external_calls": 0,
        "actual_source_ingestions": 0,
        "actual_api_calls": 0,
        "actual_scrapes": 0,
        "actual_ai_generations": 0,
        "actual_form_submissions": 0,
        "actual_customer_data_access": 0,
        "actual_runtime_writes": 0,
        "actual_pilots_launched": 0,
        "actual_customer_onboarding_started": 0,
        "actual_production_systems_activated": 0,
        "actual_source_activations": 0,
        "actual_implementation_slices_executed": 0,
        "actual_customer_outreach_attempts": 0,
        "actual_interviews_scheduled": 0,
        "validation_audience_map": _audience_payloads(),
        "interview_readiness_model": _interview_readiness_payloads(),
        "assumptions_to_validate": list(_ASSUMPTIONS_TO_VALIDATE),
        "product_risk_questions": list(_PRODUCT_RISK_QUESTIONS),
        "sovereignty_trust_validation_topics": list(_SOVEREIGNTY_TRUST_VALIDATION_TOPICS),
        "outreach_boundary_and_consent_rules": list(_OUTREACH_BOUNDARY_AND_CONSENT_RULES),
        "human_approval_requirements": list(_HUMAN_APPROVAL_REQUIREMENTS),
        "runtime_authorization_boundary": list(_RUNTIME_AUTHORIZATION_BOUNDARY),
        "sprint_148_does_not_build": list(_SPRINT148_DOES_NOT_BUILD),
        "packet_exit_criteria": list(_PACKET_EXIT_CRITERIA),
        "risks_and_mitigations": _risk_payloads(),
        "recommended_next_safe_action": _RECOMMENDED_NEXT_SAFE_ACTION,
        "sprint_148_m1_customer_validation_planning_interview_readiness_packet_proof": proof,
    }
    return _json_safe(out)


def render_active_source_activation_m1_customer_validation_planning_interview_readiness_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render the operator-facing markdown packet (deterministic; uses ``packet`` when provided)."""
    pkt = (
        packet
        if isinstance(packet, dict)
        else build_active_source_activation_m1_customer_validation_planning_interview_readiness_packet()
    )
    lines: list[str] = [
        "# NativeForge M1 Customer Validation Planning & Interview Readiness Packet v1",
        "",
        "## 1. Purpose",
        "",
        "This packet is a deterministic, preview-only operator artifact that defines the "
        "customer-validation planning model after Sprint 147 documentation consolidation and "
        "operator roadmap preservation. It prepares NativeForge for future tribal, Native-serving, "
        "tribal college, nonprofit, and partner discovery conversations without contacting "
        "customers, collecting customer data, scheduling interviews, activating sources, launching "
        "pilots, onboarding customers, authorizing production systems, performing external calls, "
        "running database migrations, collecting real metrics, executing real pilot closeout, "
        "running optimization, granting runtime authorization, or emitting runnable implementation "
        "workflows.",
        "",
        "## 2. Why This Comes After Sprint 147",
        "",
        "Sprint 147 delivered the documentation consolidation and operator roadmap packet that "
        "maps M1 packet families, preserves roadmap authorization posture, and anchors evidence "
        "reference rules after Sprint 146 readiness rollup. Sprint 148 is sequential because "
        "operators need that consolidated documentation and preserved roadmap state before layering "
        "customer validation planning and interview readiness templates; otherwise discovery framing "
        "could drift from the documented M1 evidence base. Sprint 148 does not replace Sprint 147; "
        "it depends on Sprint 147 as prerequisite documentation consolidation and operator roadmap "
        "context, then adds a safe validation-planning lane only—still without outreach, "
        "scheduling, activation, launch, onboarding, or runtime authorization.",
        "",
        "## 3. Customer Validation Planning Objective",
        "",
        "Provide deterministic planning scaffolding that names validation audiences, interview "
        "readiness components, assumptions to test with future communities, product risk questions, "
        "and sovereignty and trust validation topics so operators know what should be validated "
        "before any runtime expansion—while keeping all execution, outreach, and measurement lanes "
        "closed in this sprint.",
        "",
        "## 4. Validation Audience Map",
        "",
        "The following audiences inform what NativeForge should validate in future, separately "
        "authorized discovery; this list is planning-only and does not initiate contact:",
        "",
    ]
    for row in pkt.get("validation_audience_map") or _audience_payloads():
        if isinstance(row, dict):
            aud = row.get("audience")
            note = row.get("planning_note")
            if isinstance(aud, str) and isinstance(note, str):
                lines.append(f"- **{aud}**: {note}")
    lines.extend(["", "## 5. Interview Readiness Model", ""])
    for row in pkt.get("interview_readiness_model") or _interview_readiness_payloads():
        if isinstance(row, dict):
            comp = row.get("component")
            g = row.get("guidance")
            if isinstance(comp, str) and isinstance(g, str):
                lines.append(f"- **{comp}**: {g}")
    lines.extend(["", "## 6. Assumptions to Validate", ""])
    for item in pkt.get("assumptions_to_validate") or list(_ASSUMPTIONS_TO_VALIDATE):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 7. Product Risk Questions", ""])
    for item in pkt.get("product_risk_questions") or list(_PRODUCT_RISK_QUESTIONS):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 8. Sovereignty and Trust Validation Topics", ""])
    for item in pkt.get("sovereignty_trust_validation_topics") or list(
        _SOVEREIGNTY_TRUST_VALIDATION_TOPICS
    ):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 9. Outreach Boundary and Consent Rules", ""])
    for item in pkt.get("outreach_boundary_and_consent_rules") or list(
        _OUTREACH_BOUNDARY_AND_CONSENT_RULES
    ):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 10. Human Approval Requirements", ""])
    for item in pkt.get("human_approval_requirements") or list(_HUMAN_APPROVAL_REQUIREMENTS):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 11. Runtime Authorization Boundary", ""])
    for item in pkt.get("runtime_authorization_boundary") or list(_RUNTIME_AUTHORIZATION_BOUNDARY):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 12. What Sprint 148 Does Not Build", "", "Sprint 148 explicitly does not build:", ""])
    for item in pkt.get("sprint_148_does_not_build") or list(_SPRINT148_DOES_NOT_BUILD):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 13. Exit Criteria", ""])
    for c in pkt.get("packet_exit_criteria") or list(_PACKET_EXIT_CRITERIA):
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
            "## 15. Recommended Next Safe Action",
            "",
            pkt.get("recommended_next_safe_action") or _RECOMMENDED_NEXT_SAFE_ACTION,
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
