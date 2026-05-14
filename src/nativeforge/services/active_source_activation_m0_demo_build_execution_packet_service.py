"""Sprint 117: M0 demo build execution packet (operator planning only; no runtime).

Emits a deterministic, preview-only packet that converts NativeForge Product Intelligence Report themes into an
executable M0 demo build plan narrative for operators. Does not activate sources, ingest live data, call external
APIs, call LLMs, generate production forms, or author runnable runtime workflows.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = "nf_active_source_activation_m0_demo_build_execution_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

M0_DEMO_BUILD_SEQUENCE_ORDER: tuple[str, ...] = (
    "Organizational entity profile",
    "Grants.gov opportunity ingestion interface using seeded/demo-safe data only",
    "Tribal eligibility tagging",
    "AI NOFO plain-language summary preview",
    "Basic scoring and pursuit recommendation",
    "Pursuit pipeline with deadline tracking",
    "SF-424 autofill preview from entity profile",
    "Requirement extraction checklist preview",
    "Data sovereignty policy page",
    "Human review gates for all AI/form outputs",
)

_M0_ACCEPTANCE: tuple[tuple[str, ...], ...] = (
    (
        "Entity profile captures legal name, entity type, and key tribal org fields needed for demos.",
        "Profile edits are persisted only in demo-safe storage paths configured for M0.",
        "Profile data never leaves the demo boundary without an explicit human export action.",
    ),
    (
        "Opportunity list renders only from bundled or operator-seeded Grants.gov-style fixtures.",
        "UI clearly labels every opportunity row as demo-safe or seeded non-production data.",
        "No network client is invoked for Grants.gov or SAM.gov in M0 demo builds.",
    ),
    (
        "Eligibility tags display provenance as heuristic or rules-based preview, not legal determination.",
        "Tagging rules are inspectable in operator documentation accompanying the demo.",
        "Overrides are possible and audited in the demo script even if stored only in session fixtures.",
    ),
    (
        "NOFO summary panel shows preview watermark and disclaims final reliance.",
        "Summary text is sourced from static demo excerpts, not live LLM calls.",
        "Human reviewer acknowledgment is required before sharing summary externally.",
    ),
    (
        "Scoring outputs present confidence bands and rationale strings tied to demo fixtures.",
        "Recommendations are labeled advisory and non-binding for pursuit decisions.",
        "Disagreement with the score is captured as a demo pathway, not an error state.",
    ),
    (
        "Pipeline stages reflect M0 scope only: discover, qualify, prepare, human gate.",
        "Deadlines are computed deterministically from seeded opportunity close dates.",
        "No automated submission or status transitions occur without human confirmation.",
    ),
    (
        "SF-424 preview maps only non-sensitive fields from the demo entity profile.",
        "Preview PDF or HTML is stamped as non-submittable autofill preview.",
        "Operator script includes explicit pause for tribal counsel review if shown.",
    ),
    (
        "Checklist items trace back to excerpted NOFO paragraphs in demo fixtures.",
        "Checklist completion does not imply compliance sign-off.",
        "Export of checklist is optional and remains within demo-safe artifacts.",
    ),
    (
        "Policy page states data residency, access, and deletion expectations for M0.",
        "Page links to trust explainer covering AI and form preview posture.",
        "Content is reviewable by tribal stakeholders before any external demo.",
    ),
    (
        "Every AI or form surface shows a blocking human review banner by default.",
        "Demo script cannot mark outputs final without capturing a named approver.",
        "Audit stub records reviewer id and timestamp even if stored locally for M0 only.",
    ),
)

_RISK_MITIGATIONS: tuple[tuple[str, str], ...] = (
    (
        "Building without tribal input",
        "Schedule structured listening sessions with grant managers before locking M0 narratives.",
    ),
    (
        "AI hallucination",
        "Keep summaries excerpt-based, require human review, and show source citations in demo fixtures.",
    ),
    (
        "Pan-Indian generalization",
        "Parameterize copy and examples per nation or org demo profile with explicit consent.",
    ),
    (
        "Source ingestion instability",
        "Defer live ingestion entirely; rely on versioned seeded datasets with checksums.",
    ),
    (
        "Underbuilt data sovereignty posture",
        "Ship the sovereignty policy page in M0 and document export plus audit roadmap items.",
    ),
    (
        "Underpricing support assumptions",
        "Document support boundaries in the packet and price pilot support separately from M0.",
    ),
    (
        "Buyer distrust of AI",
        "Lead demos with human gates, preview labels, and offline-first data handling story.",
    ),
    (
        "Confusing demo-safe preview with production readiness",
        "Repeat demo-safe labeling in UI, markdown, and operator scripts; forbid production claims.",
    ),
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _feature_payloads() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, title in enumerate(M0_DEMO_BUILD_SEQUENCE_ORDER, start=1):
        out.append(
            {
                "priority": i,
                "title": title,
                "acceptance_criteria": list(_M0_ACCEPTANCE[i - 1]),
            }
        )
    return out


def _risk_payloads() -> list[dict[str, str]]:
    return [{"risk": r, "mitigation": m} for r, m in _RISK_MITIGATIONS]


def build_active_source_activation_m0_demo_build_execution_packet() -> dict[str, Any]:
    """Return the Sprint 117 M0 demo build execution packet (deterministic, no side effects)."""
    m0_features = _feature_payloads()
    proof = {
        "sprint_117_m0_demo_build_execution_packet_is_stateless": True,
        "sprint_117_m0_demo_build_execution_packet_is_side_effect_free": True,
        "sprint_117_m0_demo_build_execution_packet_is_preview_only": True,
        "sprint_117_m0_demo_build_execution_packet_performs_no_runtime_activation": True,
        "sprint_117_m0_demo_build_execution_packet_performs_no_live_ingestion": True,
        "sprint_117_m0_demo_build_execution_packet_emits_operator_planning_only": True,
    }
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "sprint_number": 117,
        "packet_name": "NativeForge M0 Demo Build Execution Packet",
        "packet_version": "v1",
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "may_generate_operator_packet": True,
        "may_define_m0_demo_scope": True,
        "may_define_acceptance_criteria": True,
        "may_define_guardrails": True,
        "may_define_sequencing": True,
        "actual_external_calls": 0,
        "actual_source_ingestions": 0,
        "actual_ai_generations": 0,
        "actual_form_submissions": 0,
        "actual_customer_data_access": 0,
        "actual_runtime_writes": 0,
        "m0_build_sequence": list(M0_DEMO_BUILD_SEQUENCE_ORDER),
        "m0_demo_features": m0_features,
        "risks_and_mitigations": _risk_payloads(),
        "sprint_117_m0_demo_build_execution_packet_proof": proof,
    }
    return _json_safe(out)


def _ordered_m0_demo_features(pkt: dict[str, Any]) -> list[dict[str, Any]]:
    raw = pkt.get("m0_demo_features")
    feats: list[dict[str, Any]]
    if isinstance(raw, list):
        feats = [f for f in raw if isinstance(f, dict)]
        feats.sort(key=lambda f: f.get("priority") if isinstance(f.get("priority"), int) else 0)
    else:
        feats = _feature_payloads()
    return feats


def render_active_source_activation_m0_demo_build_execution_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    """Render the operator-facing markdown packet (deterministic; uses ``packet`` when provided)."""
    pkt = packet if isinstance(packet, dict) else build_active_source_activation_m0_demo_build_execution_packet()
    ordered_features = _ordered_m0_demo_features(pkt)
    lines: list[str] = [
        "# NativeForge M0 Demo Build Execution Packet v1",
        "",
        "## 1. Purpose",
        "",
        "This packet transitions NativeForge from activation planning into M0 demo build readiness while preserving "
        "the no-live-activation guardrails. It is an operator-facing planning artifact only: it sequences demo "
        "features, acceptance tests, guardrails, and risks without performing runtime activation, live ingestion, or "
        "production customer operations.",
        "",
        "## 2. Source Thesis",
        "",
        "NativeForge is a sovereignty-first grant intelligence and pursuit platform for Native nations and "
        "Native-serving organizations. Its wedge is pre-award grant discovery, tribal eligibility scoring, NOFO "
        "requirement extraction, reusable entity profiles, form autofill previews, culturally guarded AI drafting "
        "previews, and human-reviewed pursuit workflow.",
        "",
        "## 3. M0 Demo Objective",
        "",
        "The demo must impress a buyer in a live walkthrough. It does not need to support a real tribe at full "
        "production scale.",
        "",
        "## 4. M0 Demo Narrative",
        "",
        "Step-by-step buyer demo narrative:",
        "",
        "1. A tribal grant manager opens NativeForge.",
        "2. They review their organizational entity profile.",
        "3. They find a relevant grant from seeded, demo-safe Grants.gov-style data.",
        "4. They see tribal eligibility and mission fit signals presented as preview guidance.",
        "5. They open a plain-language NOFO summary derived from demo fixtures.",
        "6. They review extracted requirements tied to the same demo-safe excerpt.",
        "7. They add the opportunity to the pursuit pipeline with visible deadline tracking.",
        "8. They preview SF-424 autofill fields populated from the entity profile, clearly marked non-submittable.",
        "9. They see human review warnings on AI and form outputs.",
        "10. They confirm no data leaves tribal control without explicit approval pathways described on the "
        "sovereignty policy page.",
        "",
        "## 5. M0 Build Sequence",
        "",
        "Priority order for M0 demo engineering:",
        "",
    ]
    for i, title in enumerate(M0_DEMO_BUILD_SEQUENCE_ORDER, start=1):
        lines.append(f"{i}. {title}")
    lines.extend(
        [
            "",
            "## 6. Feature Acceptance Criteria",
            "",
        ]
    )
    for feat in ordered_features:
        if not isinstance(feat, dict):
            continue
        title = feat.get("title")
        if not isinstance(title, str):
            continue
        lines.append(f"### {feat.get('priority', '')}. {title}")
        lines.append("")
        crit = feat.get("acceptance_criteria")
        if isinstance(crit, list):
            for c in crit:
                if isinstance(c, str) and c.strip():
                    lines.append(f"- {c}")
        lines.append("")
    lines.extend(
        [
            "## 7. Demo-Safe Data Rules",
            "",
            "M0 requires seeded or demo-safe data only. Operators must not load real customer data, perform live API "
            "pulls, use scraped sources, store production tribal data, or invoke AI vendor calls. All Grants.gov-style "
            "surfaces must use fixtures that are clearly labeled and version-controlled.",
            "",
            "Restrictions restated for operators: no real customer data; no live API pulls; no scraped sources; no "
            "production tribal data; no AI vendor calls.",
            "",
            "## 8. Human Review Gates",
            "",
            "Mandatory gates:",
            "",
            "- AI draft preview cannot be marked final without human approval.",
            "- Form autofill preview cannot be marked final without human approval.",
            "- Eligibility recommendation must be reviewable and overrideable.",
            "- Submission status cannot be marked submitted by automation.",
            "- Any ambiguous eligibility must be flagged for human review.",
            "",
            "## 9. Sovereignty Guardrails",
            "",
            "- tribe owns its data",
            "- no model training on customer data without explicit written consent",
            "- full export path required before pilot readiness",
            "- audit logs required before pilot readiness",
            "- private deployment remains future M3, not M0",
            "- M0 must include policy page or trust explainer",
            "",
            "## 10. What Sprint 117 Does Not Build",
            "",
            "Sprint 117 explicitly does not build:",
            "",
            "- No live Grants.gov ingestion.",
            "- No SAM.gov integration.",
            "- No real NOFO parsing.",
            "- No production LLM drafting.",
            "- No live SF-424 generation.",
            "- No customer onboarding.",
            "- No authentication redesign.",
            "- No billing.",
            "- No post-award compliance module.",
            "- No private deployment.",
            "",
            "## 11. M0 Exit Criteria",
            "",
            "NativeForge is M0-demo-ready when:",
            "",
            "- All ten M0 features are demonstrable on seeded data with visible preview labeling.",
            "- Human review gates block finalization for every AI and form preview surface.",
            "- Sovereignty policy or trust explainer content is published inside the demo shell.",
            "- Operator walkthrough script, risks, and mitigations are rehearsed with tribal grant advisor input.",
            "- Export and audit log commitments are documented on the roadmap even if not fully implemented in M0.",
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
            "## 13. Sprint 118 Recommended Next Step",
            "",
            "Sprint 118 should deliver the first concrete M0 implementation planning packet focused on the "
            "Organizational Entity Profile. That packet should remain preview-only and demo-safe unless the operator "
            "explicitly authorizes runtime engineering work.",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
