# NativeForge M1 Pilot Scope and Delivery Boundary Packet v1

This document is the product-facing companion to Sprint 131. It mirrors the deterministic operator packet
implemented in
`src/nativeforge/services/active_source_activation_m1_pilot_scope_delivery_boundary_packet_service.py`.
The packet is preview-only: it defines M1 paid pilot scope boundaries, delivery limits, included and
excluded capabilities, dependencies, and acceptance criteria; it does not create pilot accounts, onboard
customers, activate M1 features, call external services, or access customer data.

## 1. Purpose

This packet defines the M1 paid pilot scope and delivery boundaries after M0 demo readiness and Sprint 130
pilot transition planning. Operators use it to prevent M1 from expanding silently beyond validated buyer
needs and delivery capacity—without runtime execution, onboarding, activation, or contractual delivery
commitments.

## 2. Why This Comes After M0 Pilot Transition Planning

Sprint 130 converted M0 evidence and buyer follow-up questions into M1 readiness planning with structured
field groups and statuses. Sprint 131 turns that readiness into an explicit M1 pilot scope and delivery
boundary packet so buyers and operators share the same in-scope, out-of-scope, and dependency language
before any implementation dependency mapping.

## 3. M1 Pilot Scope Objective

The goal is a preview-only scope boundary that names what belongs in the M1 paid pilot, what is excluded
or deferred, which buyer and operator dependencies must close, and which sovereignty, security, human
review, ingestion, form, and support boundaries apply—without pilot account creation, customer onboarding,
M1 feature activation, or delivery promises.

Foundations the packet anchors:

1. Pilot scope definition
2. Included M1 capabilities
3. Excluded M1 capabilities
4. Pilot success criteria
5. Buyer dependency tracking
6. Operator dependency tracking
7. Data sovereignty boundary
8. Security/access boundary
9. Human review boundary
10. Source ingestion boundary
11. Form package boundary
12. Support and delivery boundary

## 4. Preview-Only Pilot Scope Rules

Operators must treat this packet as planning-only discipline:

- Require seeded or demo-safe records only; never import production customer extracts into pilot scope
  planning.
- Do not access real customer data while building or reviewing this pilot scope packet.
- Do not create pilot accounts, tenant records, or customer onboarding flows from this sprint packet.
- Do not activate M1 features, runtime flags, or production environments from this sprint packet.
- Do not treat this packet as a delivery commitment; it defines preview boundaries only.
- Do not place external API calls, scrapes, live ingestions, or live AI generations while using this
  packet.
- Do not submit applications, forms, or e-signatures while using this packet.
- Keep human judgment, provenance visibility, sovereignty boundaries, and missing-data disclosure explicit.

Restated: seeded or demo-safe records only; no real customer data; no pilot account creation; no customer
onboarding; no M1 feature activation; no delivery commitment; no external calls.

## 5. Required Pilot Scope Field Groups

Eighteen field groups structure every pilot scope row:

1. **Scope item identity** — Stable id, title, and version for cross-artifact references.
2. **Pilot capability area** — Maps the row to a product area in the M1 pilot scope map.
3. **Included in M1 flag** — Explicit in-scope signal with acceptance criteria.
4. **Excluded from M1 flag** — Explicit out-of-scope signal with out-of-scope notes.
5. **Delivery boundary** — What may be delivered versus what remains preview-only in M1 planning.
6. **Buyer dependency** — Approvals and policy inputs only the buyer can provide.
7. **Operator dependency** — Staffing, governance, and capacity inputs only operators control.
8. **Technical dependency** — Engineering and integration unknowns before implementation.
9. **Sovereignty dependency** — Residency, export, retention, and consent questions.
10. **Security/access dependency** — Authentication, authorization, secrets, and threat-model gaps.
11. **Human review dependency** — Mandatory human checkpoints for eligibility, forms, or narratives.
12. **Source ingestion dependency** — Live feed requirements versus seeded or demo-safe proofs.
13. **Form package dependency** — SF-424 coverage, signing limits, and non-submission posture.
14. **Acceptance criteria** — Field-level pass or fail checks before assigning a status.
15. **Risk note** — Misunderstanding, scope creep, and trust risks for operators and buyers.
16. **Out-of-scope note** — Why deferred capabilities stay visible without entering M1 silently.
17. **Non-production disclaimer** — Preview-only posture; not onboarding, activation, or commitment.
18. **Next sprint recommendation** — Points to Sprint 132 without silent runtime expansion.

## 6. Pilot Scope Status Definitions

Eight preview-only statuses apply. **Every status explicitly disclaims production activation, customer
onboarding, and delivery commitments** (see the repeated disclaimer in the sprint service output).

| Status | Intent |
| --- | --- |
| In M1 pilot scope | Included for M1 planning with documented acceptance criteria. |
| Out of M1 pilot scope | Explicitly excluded with visible rationale. |
| Needs buyer decision | Buyer approval or policy input required before tightening scope. |
| Needs operator decision | Operator staffing or governance decision required before tightening scope. |
| Needs technical discovery | Engineering or integration unknowns must be resolved first. |
| Needs sovereignty review | Residency, export, retention, or consent questions remain open. |
| Needs security review | Access, secrets, or threat-model questions remain open. |
| Deferred beyond M1 | Deferred past M1 with explicit rationale while remaining visible. |

## 7. Field-Level Acceptance Criteria

Each field group in the sprint service carries at least two acceptance criteria. Operators use those
criteria as pass or fail planning checks before assigning a pilot scope status. Criteria reinforce
preview-only posture, provenance visibility, honest missing-data handling, and non-commitment language.

## 8. M1 Pilot Scope by Product Area

Pilot scope maps to these product areas:

- **organizational entity profile** — Tribal context, mission alignment, and profile data boundaries.
- **live Grants.gov/source ingestion** — Live feed scope versus demo fixtures.
- **manual NOFO upload** — Buyer or operator supplied documents versus automated acquisition.
- **NOFO extraction and requirement parsing** — Parser coverage, traceability, and review hooks.
- **tribal eligibility and scoring** — Non-final scoring posture with policy and human review hooks.
- **pursuit pipeline** — Stages, owners, deadlines, and reporting without assumed production writes.
- **SF-424/form package preview** — Autofill mapping, signing limits, and submission-adjacent safeguards.
- **human review workflow** — Reviewer roles, SLAs, and escalations as planning assumptions only.
- **data sovereignty and export** — Residency, export controls, consent, and customer-owned data handling.
- **audit logs and access control** — Logging expectations, access reviews, and least-privilege design.
- **pilot support and delivery operations** — Support channels, runbooks, and delivery capacity limits.

## 9. Included M1 Capability Boundary

Included capabilities remain planning- and preview-oriented in this sprint:

- Live Grants.gov/source ingestion may be planned but not activated by this sprint.
- Manual NOFO upload may be planned but not implemented by this sprint.
- Structured extraction may be planned but not executed by this sprint.
- Form package preview may be planned but not submitted by this sprint.
- Human review workflow may be scoped but not routed by this sprint.
- Export/audit readiness may be scoped but not executed by this sprint.

## 10. Excluded and Deferred Capability Boundary

Explicit exclusions and deferrals include:

- No production submission within M1 pilot scope unless separately authorized in writing.
- No autonomous eligibility determination; human judgment remains authoritative.
- No unmanaged AI drafting of applications or eligibility conclusions.
- No customer data migration as part of this planning packet.
- No CRM automation driven by this sprint packet.
- No billing automation driven by this sprint packet.
- No private deployment commitment unless separately approved.
- No integration beyond the approved M1 pilot scope boundary.

## 11. Sovereignty and Trust Requirements

- Customer owns its data.
- No customer data is required for this planning sprint.
- No customer data leaves the product during seeded demos.
- No model training on customer data without explicit written consent.
- Human judgment remains final.
- Source provenance remains visible.
- M1 pilot scope must not overpromise production readiness.

## 12. What Sprint 131 Does Not Build

Sprint 131 explicitly does not build:

- no pilot account creation
- no customer onboarding
- no M1 feature activation
- no customer data access
- no real application submission
- no production readiness certification
- no signed pilot commitment
- no external service call
- no database migration
- no frontend UI
- no API route
- no production workflow change

## 13. M1 Pilot Scope Exit Criteria

The M1 pilot scope and delivery boundary packet is complete when:

- All eighteen pilot scope field groups are documented with purposes and acceptance criteria.
- All eight pilot scope statuses include explicit non-onboarding, non-activation, and non-delivery-commitment
  disclaimers.
- All twelve scope and delivery boundary foundations include operator focus statements without runtime
  execution.
- All eleven product area mappings include boundary and caveat expectations.
- Included and excluded capability boundaries, sovereignty requirements, and preview rules are listed.
- Risks and mitigations are recorded with operator discipline expectations.
- Sprint 132 recommendation is captured as the next preview-only implementation dependency mapping step.

## 14. Risks and Mitigations

1. **Pilot scope expands without operator approval** — Log scope changes with rationale and require explicit
   operator approval before expanding delivery language.
2. **Buyer assumes delivery commitment** — Repeat preview-only posture and separate planning artifacts from
   contracts.
3. **M1 scope implies production readiness** — Tie claims to prior sprint evidence and forbid certification
   language here.
4. **Sovereignty review is skipped** — Force Needs sovereignty review until residency, export, retention, and
   consent questions close or defer with rationale.
5. **Security review is skipped** — Force Needs security review when authentication, secrets, or integrations
   are unclear.
6. **Live ingestion readiness is assumed** — Block live ingestion claims until a written plan exists beyond
   demo fixtures.
7. **Form submission capability is implied** — Restate non-submission posture in form package boundaries.
8. **Human review dependency is ignored** — Block submission-adjacent language until reviewer roles and
   cadence are defined.
9. **Out-of-scope work enters the pilot silently** — Require excluded flags, out-of-scope notes, and
   operator approval before hidden scope enters M1.

## 15. Sprint 132 Recommended Next Step

Sprint 132 should deliver the **M1 Pilot Implementation Dependency Map Packet**, still preview-only unless
the operator explicitly authorizes runtime work.
