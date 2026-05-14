# NativeForge M1 Pilot Implementation Dependency Map Packet v1

This document is the product-facing companion to Sprint 132. It mirrors the deterministic operator packet
implemented in
`src/nativeforge/services/active_source_activation_m1_pilot_implementation_dependency_map_packet_service.py`.
The packet is preview-only: it maps implementation dependencies, ownership, sequencing, blockers, and
acceptance criteria before controlled build planning; it does not install dependencies, activate workflows,
create customer configurations, call external services, or access customer data.

## 1. Purpose

This packet defines the M1 planning layer for implementation dependency mapping after pilot scope boundaries
are defined. Operators use it to inventory dependencies, assign ownership, sequence prerequisites, surface
blockers, and document guardrails—without runtime execution, dependency installation, workflow activation, or
customer configuration.

## 2. Why This Comes After M1 Pilot Scope Boundary Planning

Sprint 131 defined what is in and out of the M1 pilot scope with explicit delivery boundaries. Sprint 132 maps
the implementation dependencies required before controlled build planning can begin so engineering work cannot
start quietly while ownership, sovereignty, security, ingestion, extraction, review, and export prerequisites
remain invisible.

## 3. M1 Implementation Dependency Objective

The goal is a preview-only dependency map that prevents implementation from starting before owners,
prerequisites, sequencing, blockers, and sovereignty or security dependencies are visible—without runnable
build promises, external calls, or customer data handling in this sprint.

Foundations the packet anchors:

1. Dependency inventory
2. Dependency ownership
3. Dependency sequencing
4. Build readiness signals
5. Blocker tracking
6. Source ingestion dependencies
7. NOFO extraction dependencies
8. Form package dependencies
9. Human review workflow dependencies
10. Data sovereignty dependencies
11. Security/access dependencies
12. Export/audit dependencies

## 4. Preview-Only Dependency Mapping Rules

Operators must treat this packet as planning-only discipline:

- Require seeded or demo-safe records only; never import production customer extracts into dependency mapping.
- Do not access real customer data while building or reviewing this dependency map packet.
- Do not install software dependencies, language runtimes, or packages from this sprint packet.
- Do not activate workflows, runtime flags, or production environments from this sprint packet.
- Do not create customer configurations, tenant records, or onboarding flows from this sprint packet.
- Do not place external API calls, scrapes, live ingestions, or live AI generations while using this packet.
- Do not submit applications, forms, or e-signatures while using this packet.
- Keep human judgment, provenance visibility, sovereignty boundaries, and missing-data disclosure explicit.

Restated: seeded or demo-safe records only; no real customer data; no dependency installation; no workflow
activation; no customer configuration; no external calls.

## 5. Required Dependency Field Groups

Eighteen field groups structure every dependency map row:

1. **Dependency item identity** — Stable id, title, and version for cross-artifact references.
2. **Product area** — Maps the dependency to a product area in the dependency map by product area section.
3. **Dependency category** — Technical, data, sovereignty, security, review, or external-system planning.
4. **Dependency owner** — Buyer-owned, operator-owned, or owner-needed accountability.
5. **Required input** — Documents, fixtures, policies, or demo data required to advance mapping.
6. **Required decision** — Approvals or governance decisions that precede build sequencing.
7. **Technical prerequisite** — Engineering and integration unknowns before implementation.
8. **Data prerequisite** — Schemas, minimization, retention, and fixture assumptions for honest mapping.
9. **Security prerequisite** — Identity, least privilege, secrets, and threat-model gaps.
10. **Sovereignty prerequisite** — Residency, export, retention, and consent questions affecting sequencing.
11. **Human review prerequisite** — Mandatory human checkpoints for eligibility, forms, or narratives.
12. **External system dependency** — Partner systems and feeds documented as preview-only mapping here.
13. **Sequencing position** — Relative order constraints without runtime activation in this sprint.
14. **Blocker status** — Whether the row blocks controlled build planning until resolved or deferred.
15. **Acceptance criteria** — Field-level pass or fail checks before assigning a dependency status.
16. **Risk note** — Misunderstanding, scope creep, sequencing theater, and trust risks.
17. **Non-production disclaimer** — Preview-only posture; not activation, installation, or configuration.
18. **Next sprint recommendation** — Points to Sprint 133 without silent runtime expansion.

## 6. Dependency Status Definitions

Eight preview-only statuses apply. **Every status explicitly disclaims runtime activation, dependency
installation, and customer configuration** (see the repeated disclaimer in the sprint service output).

| Status | Intent |
| --- | --- |
| Not mapped | Gap visible; must be inventoried before sequencing claims. |
| Mapped for planning | Documented with sufficient field groups for operator review. |
| Needs owner assignment | Buyer or operator owner missing and must be named. |
| Needs technical discovery | Engineering or integration unknowns remain open. |
| Needs buyer input | Policy, data posture, or procurement input remains open. |
| Needs sovereignty review | Residency, export, retention, or consent questions remain open. |
| Blocked before build | Explicit blocker prevents treating the row as build-ready. |
| Deferred beyond pilot | Deferred past the pilot while remaining visible in the map. |

## 7. Field-Level Acceptance Criteria

Each field group in the sprint service carries at least two acceptance criteria. Operators use those criteria
as pass or fail planning checks before assigning a dependency status. Criteria reinforce preview-only posture,
honest sequencing, provenance visibility, and non-commitment language.

## 8. Dependency Map by Product Area

The dependency map aligns to these product areas:

- **organizational entity profile** — Profile and mission inputs before build sequencing.
- **live Grants.gov/source ingestion** — Live feed readiness versus demo fixtures.
- **manual NOFO upload** — Buyer or operator supplied documents versus automated acquisition.
- **NOFO extraction and requirement parsing** — Parser coverage, traceability, and review hooks.
- **tribal eligibility and scoring** — Non-final scoring posture with policy and human review hooks.
- **pursuit pipeline** — Stages, owners, deadlines, and reporting without assumed production writes.
- **SF-424/form package preview** — Autofill mapping, signing limits, and submission-adjacent safeguards.
- **human review workflow** — Reviewer roles, SLAs, and escalations as planning assumptions only.
- **data sovereignty and export** — Residency, export controls, consent tracking, and customer-owned data.
- **audit logs and access control** — Logging expectations, access reviews, and least privilege for M1.
- **pilot support and implementation operations** — Support channels, runbooks, and capacity without promises.

## 9. Dependency Ownership Rules

- Every dependency must have an owner or an explicit owner-needed status; anonymous rows block build readiness.
- Buyer-owned dependencies must be labeled separately from operator-owned dependencies in the map.
- Technical dependencies must not hide sovereignty or security dependencies; all three remain visible.
- Unresolved ownership blocks build readiness until assigned or deferred with visible rationale.
- External system dependencies remain preview-only in this sprint with no outbound integration calls.

## 10. Dependency Sequencing Rules

- Sovereignty and security dependencies must be visible before customer data handling is sequenced.
- Source ingestion dependencies must precede live discovery work in the documented order.
- NOFO extraction dependencies must precede form package automation assumptions in the map.
- Human review dependencies must precede submission-adjacent work in the documented order.
- Export and audit dependencies must be mapped before pilot closeout planning assumes readiness.
- No runtime activation occurs in this sprint; sequencing is documentation and operator discipline only.

## 11. Sovereignty and Trust Requirements

- Customer owns its data.
- No customer data is required for this planning sprint.
- No customer data leaves the product during seeded demos.
- No model training on customer data without explicit written consent.
- Human judgment remains final.
- Source provenance remains visible.
- Dependency planning must not overpromise implementation readiness.

## 12. What Sprint 132 Does Not Build

Sprint 132 explicitly does not build:

- no dependency installation
- no workflow activation
- no customer configuration creation
- no pilot account creation
- no customer onboarding
- no customer data access
- no real application submission
- no production readiness certification
- no external service call
- no database migration
- no frontend UI
- no API route
- no production workflow change

## 13. M1 Dependency Map Exit Criteria

The M1 implementation dependency map packet is complete when:

- All eighteen dependency field groups are documented with purposes and acceptance criteria.
- All eight dependency statuses include explicit non-activation, non-installation, and non-configuration
  disclaimers.
- All twelve foundations and eleven product area rows are present with operator-visible caveats.
- Ownership rules, sequencing rules, sovereignty requirements, and preview mapping rules are listed.
- Risks and mitigations are recorded for controlled build planning discipline.
- Sprint 133 is recommended as the next preview-only controlled build sequencing step.

## 14. Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Implementation begins without dependency ownership | Force owner assignment before treating rows as build-ready. |
| Technical dependencies hide sovereignty requirements | Require parallel sovereignty and security visibility. |
| Security review is skipped | Block readiness when auth, secrets, or integrations lack prerequisites. |
| Source ingestion dependencies are assumed ready | Pair live feed prerequisites with demo fixture limits. |
| Human review dependency is ignored | Insert review prerequisites before submission-adjacent sequencing. |
| Customer configuration is implied | Ban silent configuration language; restate preview posture. |
| External system integration is overpromised | Keep external rows preview-only with no outbound calls. |
| Build sequencing becomes theater instead of control | Tie positions to prerequisites, blockers, and criteria. |
| Out-of-scope work enters pilot implementation silently | Use deferred and blocked statuses with rationale. |

## 15. Sprint 133 Recommended Next Step

Sprint 133 should deliver the **M1 Controlled Build Sequencing and Human Gate Packet**, still preview-only
unless the operator explicitly authorizes runtime work.
