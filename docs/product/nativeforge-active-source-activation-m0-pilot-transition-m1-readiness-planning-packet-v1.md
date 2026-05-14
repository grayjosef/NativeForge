# NativeForge M0 Pilot Transition and M1 Readiness Planning Packet v1

This document is the product-facing companion to Sprint 130. It mirrors the deterministic operator packet
implemented in
`src/nativeforge/services/active_source_activation_m0_pilot_transition_m1_readiness_planning_packet_service.py`.
The packet is preview-only: it defines M0-to-M1 transition planning, pilot readiness fields, buyer
follow-ups, and dependency guardrails; it does not create pilot accounts, onboard customers, activate M1
workflows, call external services, or access customer data.

## 1. Purpose

This packet defines the M0 planning layer for transitioning from demo readiness to M1 paid pilot
planning. It converts buyer questions, Sprint 129 evidence references, sovereignty and security signals,
and implementation unknowns into structured readiness rows with explicit acceptance criteria and
go/no-go discipline—without runtime execution, onboarding, activation, or contractual commitments.

## 2. Why This Comes After Demo Readiness Evidence Planning

Sprint 129 defined the evidence pack and operator checklist that anchored buyer-visible claims to
artifacts, caveats, provenance, and sovereignty statements. Sprint 130 defines how buyer feedback,
evidence gaps, sovereignty concerns, and implementation dependencies become M1 readiness planning inputs
while remaining demo-safe and non-executing.

## 3. M0-to-M1 Transition Objective

The goal is a demo-safe transition framework that converts buyer questions and M0 evidence into M1 pilot
readiness planning without triggering production onboarding, pilot account creation, or runtime activation.
Outcomes inform later M1 scope packets; they do not execute engineering work.

Transition foundations operators cover:

1. M0 demo outcome review
2. Buyer discovery follow-up capture
3. Pilot fit assessment
4. M1 scope boundary definition
5. Data sovereignty readiness
6. Security and access readiness
7. Source ingestion readiness
8. NOFO extraction readiness
9. Form package readiness
10. Human review workflow readiness
11. Export and audit readiness
12. M1 implementation dependency tracking

## 4. Demo-Safe Pilot Transition Rules

Operators must treat this packet as planning-only discipline:

- Require seeded or demo-safe records only; never import production customer extracts into transition
  planning.
- Do not access real customer data while building or reviewing this transition packet.
- Do not create pilot accounts, tenant records, or customer onboarding flows from this sprint packet.
- Do not activate M1 workflows, runtime flags, or production environments from this sprint packet.
- Do not imply signed pilot commitments; capture buyer interest as planning signals only.
- Do not place external API calls, scrapes, live ingestions, or live AI generations while using this packet.
- Do not submit applications, forms, or e-signatures while using this packet.
- Keep human judgment, provenance visibility, sovereignty boundaries, and missing-data disclosure explicit.

Restated: seeded or demo-safe records only; no real customer data; no pilot account creation; no customer
onboarding; no M1 workflow activation; no signed pilot commitment; no external calls.

## 5. Required Pilot Readiness Field Groups

Eighteen field groups structure every pilot readiness row:

1. **Pilot readiness item identity** — Stable id, title, and version for cross-artifact references.
2. **Source M0 evidence reference** — Sprint 129 evidence rows, fixtures, or sprint packet lineage.
3. **Buyer follow-up question** — Faithful buyer prompts mapped to M1 dependencies.
4. **Buyer concern category** — Sovereignty, security, import, eligibility, scope, or operations tags.
5. **M1 feature dependency** — Primary product surface impacted by the readiness row.
6. **Pilot fit signal** — Qualitative urgency, capacity, or sponsorship signal without contracts.
7. **Data sovereignty dependency** — Residency, export, and consent questions blocking pilot-ready language.
8. **Security/access dependency** — Authn, authz, secrets, and integration security gaps.
9. **Source ingestion dependency** — Live feed requirements versus seeded fixture proofs.
10. **NOFO extraction dependency** — Parser coverage, clause linkage, and human review needs.
11. **Form package dependency** — SF-424 coverage, signing boundaries, submission-adjacent risks.
12. **Human review dependency** — Reviewer roles, cadence, and escalation assumptions (planning only).
13. **Export/audit dependency** — Export previews, logging visibility, retention expectations.
14. **Implementation risk note** — Delivery, scope creep, and misunderstanding risks.
15. **Operator action required** — Next planning step such as schedule sovereignty review.
16. **Go/no-go recommendation** — Operator recommendation using demo-safe statuses only.
17. **Non-production disclaimer** — Preview-only posture; not onboarding, activation, or commitment language.
18. **Next sprint recommendation** — Points to Sprint 131 without silent runtime expansion.

## 6. Pilot Readiness Status Definitions

Eight demo-safe statuses apply. **Every status explicitly disclaims customer onboarding, production
activation, and signed pilot commitments** (see the repeated disclaimer in the sprint service output).

| Status | Intent |
| --- | --- |
| Not assessed | Default before operator review. |
| Ready for M1 planning | Dependencies, evidence links, and disclaimers satisfy acceptance criteria for planning. |
| Needs buyer clarification | Ambiguous buyer questions need follow-up before scope tightens. |
| Needs technical discovery | Engineering or integration unknowns block crisp dependency statements. |
| Needs sovereignty review | Residency, export, or consent questions remain open. |
| Needs security review | Access, secrets, or threat-model questions remain open. |
| Blocked for pilot | Critical gaps block pilot planning until resolved or explicitly deferred. |
| Deferred beyond M1 | Deferred past M1 with explicit rationale while remaining visible. |

## 7. Field-Level Acceptance Criteria

Each field group in the sprint service carries at least two acceptance criteria. Operators use those
criteria as pass/fail planning checks before assigning a pilot readiness status. Criteria reinforce
preview-only posture, provenance visibility, honest missing-data handling, and non-commitment language.

## 8. M1 Readiness by Product Area

Readiness planning maps to these M1 product areas:

- **organizational entity profile** — Profile completeness, tribal context, and data boundary notes.
- **live Grants.gov/source ingestion** — Live feed readiness distinct from seeded fixtures.
- **NOFO extraction and requirement parsing** — Parser coverage, clause traceability, confidence labeling.
- **tribal eligibility and scoring** — Non-final scoring posture with policy and human review hooks.
- **pursuit pipeline** — Stages, owners, deadlines, and reporting assumptions without production writes.
- **SF-424/form package preview** — Autofill mapping, signing boundaries, submission-adjacent safeguards.
- **human review workflow** — Reviewer roles, SLAs, escalations as planning assumptions only.
- **data sovereignty and export** — Residency, export controls, consent, customer-owned data commitments.
- **audit logs and access control** — Logging expectations, access reviews, least-privilege design notes.
- **pilot support and implementation operations** — Support channels and runbooks as planning references only.

## 9. Buyer Follow-Up Question Capture

Operators capture buyer questions and route concerns without automating CRM or commitments:

- Buyer questions must map to M1 feature dependencies listed in pilot readiness rows.
- Sovereignty concerns must route to sovereignty review and data sovereignty dependency fields.
- Security concerns must route to security review and security/access dependency fields.
- Data import concerns must route to technical discovery and source ingestion dependency fields.
- Eligibility concerns must route to human review and policy review with non-final scoring caveats.
- **Buyer interest does not create a pilot commitment**; record interest separately from contractual status.

## 10. M1 Implementation Dependency Rules

- Unresolved sovereignty questions block pilot-ready status until resolved or explicitly deferred.
- Unresolved security questions block pilot-ready status until resolved or explicitly deferred.
- Unresolved customer data boundaries block pilot-ready status until documented with operator sign-off.
- Missing source ingestion plan blocks live discovery readiness statements.
- Missing human review workflow blocks submission-adjacent readiness statements.
- **No runtime activation occurs in this sprint**; dependency tracking remains planning-only.

## 11. Sovereignty and Trust Requirements

- customer owns its data
- no customer data required for seeded transition planning
- no customer data leaves the product during seeded demos
- no model training on customer data without explicit written consent
- human judgment remains final
- source provenance remains visible
- M1 pilot planning must not overpromise production readiness

## 12. What Sprint 130 Does Not Build

Sprint 130 explicitly does not build:

- no pilot account creation
- no customer onboarding
- no M1 workflow activation
- no customer data access
- no real application submission
- no production readiness certification
- no signed pilot commitment
- no external service call
- no database migration
- no frontend UI
- no API route
- no production workflow change

## 13. M0 Exit Criteria for Pilot Transition Planning

The M0-to-M1 transition planning packet is complete when:

- All eighteen pilot readiness field groups are documented with purposes and acceptance criteria.
- All eight pilot readiness statuses include explicit non-onboarding, non-activation, and non-commitment
  disclaimers.
- All twelve transition foundations include operator focus statements without runtime execution.
- All ten M1 product area readiness mappings include dependency and caveat expectations.
- Buyer follow-up capture, implementation dependency rules, sovereignty requirements, and scope limits are listed.
- Risks and mitigations are recorded with go/no-go discipline expectations for operators.
- Sprint 131 recommendation is captured as the next preview-only M1 scope boundary planning step.

## 14. Risks and Mitigations

1. **buyer interest is mistaken for signed pilot commitment** — Label interest separately from contracts and
   repeat non-commitment disclaimers.
2. **M0 demo evidence is overstated as production readiness** — Cross-check claims against Sprint 129 evidence
   references and preview-only language.
3. **sovereignty concerns are under-scoped** — Force Needs sovereignty review until residency, export, and
   consent questions are documented.
4. **security discovery is skipped** — Require Needs security review when authn, secrets, or integrations are
   unclear.
5. **live source ingestion is assumed ready** — Block live discovery readiness until a written ingestion plan
   exists beyond seeded fixtures.
6. **human review dependencies are ignored** — Block submission-adjacent readiness until reviewer roles,
   cadence, and escalations are defined.
7. **customer data boundaries are unclear** — Block pilot-ready status until minimization and retention
   expectations are written.
8. **M1 scope expands without operator approval** — Log scope changes with rationale and require explicit
   operator approval before expanding delivery.
9. **readiness checklist becomes theater instead of go/no-go discipline** — Require explicit rationale, risk
   notes, and blocked statuses instead of silent passes.

## 15. Sprint 131 Recommended Next Step

Sprint 131 should deliver the **M1 Pilot Scope and Delivery Boundary Packet**, still preview-only and
demo-safe unless the operator explicitly authorizes runtime work.
