"""Sprint 129: M0 demo readiness evidence pack and operator checklist packet (preview-only).

Deterministic operator packet that defines demo evidence artifacts, checklist steps, readiness checks,
guardrails, and acceptance criteria before buyer presentation. No demo execution, no evidence files,
no buyer sessions, no external calls, and no customer data access.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = "nf_active_source_activation_m0_demo_readiness_evidence_pack_operator_checklist_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

_STATUS_DISCLAIMER = (
    "This checklist status is not production readiness certification, is not legal approval, and is "
    "not submission authorization."
)

_DEMO_READINESS_FOUNDATION_AREAS: tuple[tuple[str, str], ...] = (
    (
        "Demo artifact inventory",
        "Catalog every demo-visible artifact, fixture, sprint packet, and seed label before narrative use.",
    ),
    (
        "Seeded data confirmation",
        "Verify all records are explicitly demo-safe or synthetic with visible labels and no customer extracts.",
    ),
    (
        "Buyer narrative readiness",
        "Confirm Sprint 128 narrative beats map to evidence-backed proof points and visible caveats.",
    ),
    (
        "M0 feature coverage checklist",
        "Trace each M0 feature surface to evidence items, provenance, and human review expectations.",
    ),
    (
        "Human review gate confirmation",
        "Record that Sprint 127 review gate planning is reflected in evidence without simulating approvals.",
    ),
    (
        "Caveat and boundary confirmation",
        "Ensure preview-only, non-submission, and non-final eligibility boundaries appear where buyers look.",
    ),
    (
        "Sovereignty and trust evidence confirmation",
        "Pair sovereignty statements with export limits, consent boundaries, and preview-only posture.",
    ),
    (
        "Source provenance evidence confirmation",
        "Show lineage from seeds, fixtures, or sprint packets for every buyer-visible claim.",
    ),
    (
        "Demo risk review",
        "Log misunderstanding risks, low-confidence outputs, and missing data before any walkthrough.",
    ),
    (
        "Operator go/no-go readiness",
        "Aggregate checklist outcomes as demo discipline only—never production, legal, or submission authority.",
    ),
)

_EVIDENCE_FIELD_GROUP_ROWS: tuple[tuple[str, str, tuple[str, str]], ...] = (
    (
        "Evidence item identity",
        "Stable id, title, and version so operators reference the same evidence row across artifacts.",
        (
            "Identity strings remain identical across repeated packet generations.",
            "Each evidence row exposes a single primary identity key for accountability.",
        ),
    ),
    (
        "Evidence item source sprint",
        "Declares which sprint packet or planning artifact produced or owns the evidence lineage.",
        (
            "Source sprint references use in-repo sprint numbers and packet names only.",
            "Missing sprint lineage forces an explicit gap label before buyer-facing use.",
        ),
    ),
    (
        "M0 feature covered",
        "Names the M0 surface the evidence supports such as profile, NOFO summary, or pipeline preview.",
        (
            "Feature names align to the M0 evidence pack feature map in this packet.",
            "Each row lists exactly one primary M0 feature to keep traceability clear.",
        ),
    ),
    (
        "Buyer proof point",
        "States the buyer-visible claim the evidence must support without overstating automation.",
        (
            "Proof points tie to observable artifacts or fixtures in planning language.",
            "Proof points avoid implying live integrations beyond M0 scope.",
        ),
    ),
    (
        "Demo-safe data confirmation",
        "Confirms seeded or synthetic data posture and rejects production customer extracts.",
        (
            "Operators record explicit demo-safe labels for every referenced record.",
            "Any unknown data class blocks Ready for demo until corrected.",
        ),
    ),
    (
        "Human review status",
        "Captures whether human review expectations are documented for the evidence item.",
        (
            "Review status references Sprint 127 planning gates without simulating API approvals.",
            "Overrides are described as human-led, not silent model edits.",
        ),
    ),
    (
        "Source provenance status",
        "Shows whether provenance is visible, partial, or missing for buyer-visible fields.",
        (
            "Hidden provenance is treated as a defect to correct before demos.",
            "Provenance notes distinguish seed, fixture, and sprint packet lineage.",
        ),
    ),
    (
        "Sovereignty/trust status",
        "Tracks alignment with sovereignty statements, export limits, and consent boundaries.",
        (
            "Trust status never asserts private deployment unless contractually true later.",
            "Trust notes pair with visible provenance expectations for the evidence item.",
        ),
    ),
    (
        "Caveat visibility status",
        "Ensures preview-only, non-submission, and non-final eligibility caveats are buyer-visible.",
        (
            "Caveats appear adjacent to any AI-adjacent or form-adjacent claims.",
            "Missing caveat visibility forces Needs operator review or Blocked by unclear caveat.",
        ),
    ),
    (
        "Missing data status",
        "Declares known gaps, placeholders, or incomplete checklist rows without hiding them.",
        (
            "Missing data defaults to visible disclosure rather than silent omission.",
            "Gaps include explicit operator actions to resolve or defer with rationale.",
        ),
    ),
    (
        "Risk note",
        "Captures demo misunderstanding risks and product limits tied to the evidence item.",
        (
            "Risks reference buyer confusion patterns such as production readiness assumptions.",
            "Risk notes distinguish preview scaffolding from production readiness.",
        ),
    ),
    (
        "Operator action required",
        "Lists the next concrete operator step such as re-label seeds or attach fixture paths.",
        (
            "Actions use planning verbs such as document or label, not submit or approve production.",
            "Actions include reminder that checklist discipline is not legal or submission authority.",
        ),
    ),
    (
        "Go/no-go status",
        "Records operator checklist outcome using the demo-safe statuses defined in this packet.",
        (
            "Go/no-go applies to demo presentation readiness only, not production launch.",
            "Statuses repeat that they are not legal approval or submission authorization.",
        ),
    ),
    (
        "Closeout note",
        "Summarizes evidence closure expectations after demo rehearsal planning.",
        (
            "Closeout references caveat, provenance, and sovereignty confirmations.",
            "Closeout forbids implying evidence files were generated by this sprint.",
        ),
    ),
    (
        "Artifact path or reference",
        "Points to repo paths, fixtures, or sprint packets that evidence the claim.",
        (
            "References use in-repo artifact names rather than live external systems.",
            "Missing artifact references block claims of completeness.",
        ),
    ),
    (
        "Non-production disclaimer",
        "Restates preview-only posture and lack of production legal or submission authority.",
        (
            "Disclaimers repeat preview-only and no runtime execution for the evidence item.",
            "Disclaimers appear wherever status language could be misread as go-live approval.",
        ),
    ),
    (
        "Buyer question linkage",
        "Maps likely buyer questions to evidence rows and follow-up discovery prompts.",
        (
            "Questions invite clarification rather than leading to false production promises.",
            "Linkage includes sovereignty, eligibility, and export concern tags when relevant.",
        ),
    ),
    (
        "Next sprint recommendation",
        "Points operators to Sprint 130 planning without executing runtime engineering.",
        (
            "Recommendations name Sprint 130 scope in preview-only language.",
            "Recommendations forbid silent expansion into runtime work without explicit authorization.",
        ),
    ),
)

_OPERATOR_CHECKLIST_STATUS_ROWS: tuple[tuple[str, str], ...] = (
    (
        "Not checked",
        "Default state before an operator reviews the evidence row. " + _STATUS_DISCLAIMER,
    ),
    (
        "Ready for demo",
        "Evidence, caveats, provenance, and demo-safe labels satisfy the field acceptance criteria. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Needs operator review",
        "Ambiguity, partial provenance, or weak proof mapping requires human operator judgment. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Needs seeded data correction",
        "Labels, fixtures, or synthetic records need correction before the evidence can support the demo. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Blocked by missing evidence",
        "Required artifact, fixture, or sprint packet reference is absent or unverifiable. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Blocked by unclear caveat",
        "Buyer-visible caveat language is missing, buried, or inconsistent with preview-only posture. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Excluded from buyer walkthrough",
        "Item intentionally omitted from buyer-facing narrative while remaining tracked internally. "
        + _STATUS_DISCLAIMER,
    ),
    (
        "Deferred to later sprint",
        "Evidence deferred with explicit rationale; not hidden as complete. " + _STATUS_DISCLAIMER,
    ),
)

_DEMO_SAFE_READINESS_RULES: tuple[str, ...] = (
    "Require seeded or demo-safe records only; never load production customer extracts into demo readiness "
    "planning.",
    "Do not access real customer data while building or reviewing this evidence pack.",
    "Do not run a real demo execution, runtime workflow, or live rehearsal automation from this sprint packet.",
    "Do not create evidence files, buyer sessions, or CRM records from this sprint packet.",
    "Do not submit applications, forms, or e-signatures while using this checklist.",
    "Do not present final eligibility determinations; label all eligibility signals as preview-only.",
    "Do not certify production readiness, grant legal approval, or authorize submissions from checklist "
    "statuses.",
    "Do not place external API calls, scrapes, live ingestions, or live AI generations while using this "
    "packet.",
    "Keep human judgment, provenance, sovereignty boundaries, and missing-data visibility explicit.",
)

_EVIDENCE_PACK_BY_M0_FEATURE: tuple[tuple[str, str], ...] = (
    (
        "organizational entity profile",
        "Evidence for entity fields, tribal context, and mission alignment inputs as labeled seeds only.",
    ),
    (
        "seeded opportunity ingestion",
        "Evidence that opportunities are fixtures or seeds without live Grants.gov ingestion or scraping.",
    ),
    (
        "tribal eligibility and mission fit scoring",
        "Evidence for preview scores, confidence labels, and non-final eligibility caveats.",
    ),
    (
        "NOFO plain-language summary",
        "Evidence tying summary bullets to seeded NOFO excerpts with extraction provenance notes.",
    ),
    (
        "opportunity recommendation preview",
        "Evidence that recommendations are drafts with human review expectations visible.",
    ),
    (
        "pursuit pipeline and deadline tracking",
        "Evidence for demo-safe timelines, owners, and pipeline stages without production writes.",
    ),
    (
        "SF-424 autofill preview",
        "Evidence mapping autofill fields to profile seeds without submission or signing pathways.",
    ),
    (
        "requirement checklist preview",
        "Evidence linking checklist rows to NOFO clauses with explicit completeness gaps allowed.",
    ),
    (
        "data sovereignty policy and export preview",
        "Evidence for policy statements and export preview posture without moving real customer data.",
    ),
    (
        "human review closeout",
        "Evidence aligning with Sprint 127 human review gate planning and closeout expectations.",
    ),
    (
        "demo narrative and buyer walkthrough",
        "Evidence backing Sprint 128 narrative beats, proof points, caveats, and walkthrough boundaries.",
    ),
)

_OPERATOR_GO_NO_GO_CHECKLIST: tuple[str, ...] = (
    "All demo-visible artifacts exist and are referenced with artifact paths or sprint packet lineage.",
    "All seeded records are labeled as demo-safe or synthetic with no customer extracts.",
    "All buyer proof points map to artifacts, fixtures, or sprint planning evidence rows.",
    "All caveats are visible where buyers encounter AI-adjacent, eligibility, or form-adjacent claims.",
    "All low-confidence outputs are marked with visible confidence or review language.",
    "All missing data is visible with explicit gaps rather than silent omission.",
    "All sovereignty claims are preview-only and paired with provenance and export boundary notes.",
    "No submission pathway is implied by screenshots, copy, or checklist language.",
    "No customer data is used in seeded demo readiness planning or referenced artifacts.",
    "No production readiness is implied by demo go/no-go outcomes or checklist statuses.",
)

_BUYER_QUESTION_AND_FOLLOW_UP_CAPTURE: tuple[str, ...] = (
    "Operators capture buyer questions verbatim or in faithful paraphrase outside this sprint packet.",
    "Follow-up discovery questions map to M1 pilot planning topics without CRM automation from Sprint 129.",
    "Buyer concerns about sovereignty are marked for review with provenance and export evidence links.",
    "Buyer concerns about eligibility are marked for review with non-final scoring caveats repeated.",
    "Buyer concerns about export or auditability are marked for review with policy and preview evidence.",
    "No buyer record is created in this sprint; capture stays in operator-controlled notes only.",
)

_SOVEREIGNTY_AND_TRUST_REQUIREMENTS: tuple[str, ...] = (
    "customer owns its data",
    "no customer data required for seeded demos",
    "no customer data leaves the product during seeded demos",
    "no model training on customer data without explicit written consent",
    "human judgment remains final",
    "source provenance remains visible",
    "evidence pack must not overpromise production readiness",
)

_SPRINT129_DOES_NOT_BUILD: tuple[str, ...] = (
    "no real demo execution",
    "no evidence file creation",
    "no buyer session creation",
    "no CRM automation",
    "no customer data access",
    "no real application submission",
    "no production readiness certification",
    "no legal approval",
    "no external service call",
    "no database migration",
    "no frontend UI",
    "no API route",
    "no production workflow change",
)

_M0_EXIT_CRITERIA: tuple[str, ...] = (
    "All eighteen evidence field groups are documented with purposes and acceptance criteria.",
    "All eight checklist statuses include explicit non-production, non-legal, non-submission disclaimers.",
    "All eleven M0 feature evidence mappings include buyer proof, caveat, and provenance expectations.",
    "Operator go/no-go checklist, buyer question capture, sovereignty requirements, and scope limits are listed.",
    "Risks and mitigations are recorded with demo discipline expectations for operators.",
    "Sprint 130 recommendation is captured as the next preview-only pilot transition planning step.",
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "operator runs demo without evidence",
        "Block Ready for demo until artifact paths, sprint references, and caveat visibility are recorded.",
    ),
    (
        "buyer proof points are not artifact-backed",
        "Map every proof point to evidence rows and require missing-data labels when gaps exist.",
    ),
    (
        "caveats are skipped during demo",
        "Mandate caveat visibility checks per feature and use Blocked by unclear caveat when buried.",
    ),
    (
        "seeded records are confused with customer records",
        "Require demo-safe labels on every record reference and reject ambiguous extracts.",
    ),
    (
        "buyer assumes production readiness",
        "Repeat preview-only language, non-production disclaimers, and operator status disclaimers aloud.",
    ),
    (
        "sovereignty claims are overstated",
        "Pair sovereignty statements with provenance, export limits, and consent boundaries in evidence rows.",
    ),
    (
        "low-confidence outputs are hidden",
        "Force visible confidence or review markers before any demo go recommendation.",
    ),
    (
        "follow-up questions are not captured",
        "Use buyer question linkage fields and operator notes with M1 pilot mapping prompts.",
    ),
    (
        "checklist becomes theater instead of real go/no-go discipline",
        "Require explicit go/no-go rationale, risk notes, and blocked statuses instead of silent passes.",
    ),
)

_SPRINT130_RECOMMENDED_NEXT_STEP = (
    "Sprint 130 should deliver the M0 Pilot Transition and M1 Readiness Planning Packet, still "
    "preview-only and demo-safe unless the operator explicitly authorizes runtime work."
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _field_group_payloads() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, (name, purpose, criteria) in enumerate(_EVIDENCE_FIELD_GROUP_ROWS, start=1):
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
    return [{"foundation_area": a, "operator_focus": b} for a, b in _DEMO_READINESS_FOUNDATION_AREAS]


def _checklist_status_payloads() -> list[dict[str, str]]:
    return [{"status": s, "definition": d} for s, d in _OPERATOR_CHECKLIST_STATUS_ROWS]


def _feature_mapping_payloads() -> list[dict[str, str]]:
    return [{"m0_feature": a, "evidence_pack_planning_focus": b} for a, b in _EVIDENCE_PACK_BY_M0_FEATURE]


def _risk_payloads() -> list[dict[str, str]]:
    return [{"risk": r, "mitigation": m} for r, m in _RISK_MITIGATIONS]


def build_active_source_activation_m0_demo_readiness_evidence_pack_operator_checklist_packet() -> (
    dict[str, Any]
):
    """Return the Sprint 129 M0 demo readiness evidence pack and operator checklist packet (deterministic)."""
    proof = {
        "sprint_129_m0_demo_readiness_evidence_pack_operator_checklist_packet_is_stateless": True,
        "sprint_129_m0_demo_readiness_evidence_pack_operator_checklist_packet_is_side_effect_free": True,
        "sprint_129_m0_demo_readiness_evidence_pack_operator_checklist_packet_is_preview_only": True,
        "sprint_129_m0_demo_readiness_evidence_pack_operator_checklist_packet_performs_no_runtime_work": True,
        "sprint_129_m0_demo_readiness_evidence_pack_operator_checklist_packet_emits_operator_planning_only": True,
    }
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 129,
        "packet_name": "NativeForge M0 Demo Readiness Evidence Pack and Operator Checklist Packet",
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_define_demo_readiness_scope": True,
        "may_define_evidence_pack_items": True,
        "may_define_operator_checklist": True,
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
        "actual_demo_runs": 0,
        "actual_evidence_files_created": 0,
        "actual_buyer_sessions_created": 0,
        "demo_readiness_foundation_areas": _foundation_payloads(),
        "evidence_field_groups": _field_group_payloads(),
        "operator_checklist_statuses": _checklist_status_payloads(),
        "checklist_status_universal_disclaimer": _STATUS_DISCLAIMER,
        "demo_safe_readiness_rules": list(_DEMO_SAFE_READINESS_RULES),
        "evidence_pack_by_m0_feature": _feature_mapping_payloads(),
        "operator_go_no_go_checklist": list(_OPERATOR_GO_NO_GO_CHECKLIST),
        "buyer_question_and_follow_up_capture": list(_BUYER_QUESTION_AND_FOLLOW_UP_CAPTURE),
        "sovereignty_and_trust_requirements": list(_SOVEREIGNTY_AND_TRUST_REQUIREMENTS),
        "sprint_129_does_not_build": list(_SPRINT129_DOES_NOT_BUILD),
        "m0_demo_readiness_planning_exit_criteria": list(_M0_EXIT_CRITERIA),
        "risks_and_mitigations": _risk_payloads(),
        "sprint_130_recommended_next_step": _SPRINT130_RECOMMENDED_NEXT_STEP,
        "sprint_129_m0_demo_readiness_evidence_pack_operator_checklist_packet_proof": proof,
    }
    return _json_safe(out)


def _ordered_field_groups(pkt: dict[str, Any]) -> list[dict[str, Any]]:
    raw = pkt.get("evidence_field_groups")
    if isinstance(raw, list):
        groups = [g for g in raw if isinstance(g, dict)]
        groups.sort(key=lambda g: g.get("priority") if isinstance(g.get("priority"), int) else 0)
        return groups
    return _field_group_payloads()


def render_active_source_activation_m0_demo_readiness_evidence_pack_operator_checklist_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render the operator-facing markdown packet (deterministic; uses ``packet`` when provided)."""
    pkt = packet if isinstance(packet, dict) else (
        build_active_source_activation_m0_demo_readiness_evidence_pack_operator_checklist_packet()
    )
    groups = _ordered_field_groups(pkt)
    lines: list[str] = [
        "# NativeForge M0 Demo Readiness Evidence Pack and Operator Checklist Packet v1",
        "",
        "## 1. Purpose",
        "",
        "This packet defines the M0 planning layer for demo readiness evidence and operator go/no-go "
        "checks before buyer presentation. It inventories artifacts, confirms seeded data posture, maps "
        "proof points, surfaces caveats, and records review gates without running demos, creating evidence "
        "files, opening buyer sessions, or accessing customer data.",
        "",
        "## 2. Why This Comes After Demo Narrative Planning",
        "",
        "Sprint 128 defined the buyer walkthrough narrative and demo-safe storytelling beats. Sprint 129 "
        "defines the evidence pack and operator checklist that keep those beats honest—preventing the "
        "narrative from becoming unsupported sales theater by forcing artifact linkage, caveat visibility, "
        "provenance, sovereignty alignment, and explicit missing-data disclosure.",
        "",
        "## 3. M0 Demo Readiness Objective",
        "",
        "Deliver a demo-safe readiness checklist that confirms artifacts, caveats, proof points, seeded "
        "data, provenance, sovereignty claims, and human review gates before any buyer presentation. "
        "Outcomes inform later demo rehearsals or implementation plans; they do not execute runtime work.",
        "",
        "Demo readiness foundation areas:",
        "",
    ]
    foundations = pkt.get("demo_readiness_foundation_areas")
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
            "## 4. Demo-Safe Readiness Rules",
            "",
        ]
    )
    for rule in pkt.get("demo_safe_readiness_rules") or list(_DEMO_SAFE_READINESS_RULES):
        if isinstance(rule, str) and rule.strip():
            lines.append(f"- {rule}")
    lines.extend(
        [
            "",
            "Demo-safe readiness rules restated: seeded or demo-safe records only; no real customer data; "
            "no real demo execution; no production readiness certification; no legal approval; no submission "
            "authorization; no external calls.",
            "",
            "## 5. Required Evidence Field Groups",
            "",
            "Eighteen field groups structure every evidence item in M0 demo readiness planning:",
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
            "## 6. Operator Checklist Status Definitions",
            "",
            "Eight demo-safe checklist statuses apply. Each status explicitly disclaims production readiness "
            "certification, legal approval, and submission authorization:",
            "",
        ]
    )
    statuses = pkt.get("operator_checklist_statuses")
    if not isinstance(statuses, list):
        statuses = _checklist_status_payloads()
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
    lines.extend(["", "## 8. Evidence Pack by M0 Feature", ""])
    mapping = pkt.get("evidence_pack_by_m0_feature")
    if not isinstance(mapping, list):
        mapping = _feature_mapping_payloads()
    for row in mapping:
        if not isinstance(row, dict):
            continue
        feat = row.get("m0_feature")
        focus = row.get("evidence_pack_planning_focus")
        if isinstance(feat, str) and isinstance(focus, str):
            lines.append(f"- **{feat}**: {focus}")
    lines.extend(["", "## 9. Operator Go/No-Go Checklist", ""])
    for item in pkt.get("operator_go_no_go_checklist") or list(_OPERATOR_GO_NO_GO_CHECKLIST):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 10. Buyer Question and Follow-Up Capture", ""])
    for item in pkt.get("buyer_question_and_follow_up_capture") or list(_BUYER_QUESTION_AND_FOLLOW_UP_CAPTURE):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 11. Sovereignty and Trust Requirements", ""])
    for item in pkt.get("sovereignty_and_trust_requirements") or list(_SOVEREIGNTY_AND_TRUST_REQUIREMENTS):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(["", "## 12. What Sprint 129 Does Not Build", "", "Sprint 129 explicitly does not build:", ""])
    for item in pkt.get("sprint_129_does_not_build") or list(_SPRINT129_DOES_NOT_BUILD):
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 13. M0 Exit Criteria for Demo Readiness Planning",
            "",
        ]
    )
    for c in pkt.get("m0_demo_readiness_planning_exit_criteria") or list(_M0_EXIT_CRITERIA):
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
            "## 15. Sprint 130 Recommended Next Step",
            "",
            pkt.get("sprint_130_recommended_next_step") or _SPRINT130_RECOMMENDED_NEXT_STEP,
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
