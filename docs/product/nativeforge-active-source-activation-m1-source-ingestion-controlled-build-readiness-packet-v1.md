# NativeForge M1 Source Ingestion Controlled Build Readiness Packet v1

This document is the product-facing companion to Sprint 134. It mirrors the deterministic operator packet
implemented in
`src/nativeforge/services/active_source_activation_m1_source_ingestion_controlled_build_readiness_packet_service.py`.
The packet is preview-only: it defines source ingestion readiness before controlled build planning; it does
not activate sources, perform live ingestion, create ingestion jobs, configure credentials, call external
services, scrape websites, or access customer data.

## 1. Purpose

This packet defines the M1 planning layer for source ingestion controlled build readiness. Operators use it
to inventory candidate sources, classify source types, document trust and provenance expectations, capture
activation prerequisites, route human gates, and record sovereignty and security guardrails—without source
activation, live ingestion, credential configuration, external calls, scraping, or customer data handling in
this sprint.

## 2. Why This Comes After Controlled Build Sequencing

Sprint 133 defined controlled build sequencing and human gates across product areas. Sprint 134 applies that
control discipline to source ingestion readiness so sources, trust, provenance, credentials, sovereignty and
security dependencies, and blockers stay visible before live ingestion language appears in planning artifacts.

## 3. M1 Source Ingestion Readiness Objective

The goal is a preview-only readiness framework that prevents live ingestion from starting before sources,
trust, provenance, credentials, sovereignty and security dependencies, and blockers are visible—without
runnable ingestion promises, runtime execution, source activation, or credential handling in this sprint.

Foundations the packet anchors:

1. Source inventory readiness
2. Source type classification
3. Source trust and provenance readiness
4. Grants.gov readiness
5. State/local source readiness
6. Tribal/federal source readiness
7. Foundation/philanthropic source readiness
8. Corporate/private source readiness
9. Manual upload readiness
10. Activation prerequisite tracking
11. Human review gates
12. Security/credential readiness
13. Data sovereignty readiness

## 4. Preview-Only Source Readiness Rules

Operators must treat this packet as planning-only discipline:

- Require seeded or demo-safe records only; never import production customer extracts into source readiness
  rows.
- Do not access real customer data while building or reviewing this source readiness packet.
- Do not activate sources, enable live feeds, or flip runtime flags from this sprint packet.
- Do not create ingestion jobs, queues, or schedulers from this sprint packet.
- Do not configure credentials, secrets stores, or vault entries from this sprint packet.
- Do not place external API calls, scrapes, live ingestions, or live AI generations while using this packet.
- Do not submit applications, forms, or e-signatures while using this packet.
- Keep human judgment, provenance visibility, sovereignty boundaries, and missing-data disclosure explicit.

Restated: seeded or demo-safe records only; no real customer data; no source activation; no live ingestion; no
credential configuration; no external calls; no scraping.

## 5. Required Source Readiness Field Groups

Eighteen field groups structure every source readiness row:

1. **Source readiness item identity** — Stable id, title, and version for cross-artifact references.
2. **Source name** — Human readable label without implying activation.
3. **Source type** — Channel classification aligned to the source readiness by source type section.
4. **Source owner or maintainer** — Buyer, operator, vendor, or owner-needed accountability.
5. **Source access method** — API, portal login, bulk file, email intake, or manual upload without live access
   claims.
6. **Source trust level** — Trust posture and reviewer visibility for low-trust human gates.
7. **Source provenance requirement** — Lineage, fixture labels, publisher attestation, and traceability
   expectations.
8. **Native relevance rationale** — Tribal mission alignment and Native-serving eligibility scope.
9. **Eligibility signal expectation** — Cues the source should expose and how confidence will be labeled later.
10. **Freshness expectation** — Staleness bounds, cadence, and monitoring assumptions before scheduling language.
11. **Credential or access requirement** — Secrets, accounts, attestations, or contracts for live connection
    planning only after review.
12. **Security prerequisite** — Least privilege, logging, threat-model gaps, and integration safeguards.
13. **Sovereignty prerequisite** — Residency, export, retention, consent, and customer-data-touch questions.
14. **Human review prerequisite** — Mandatory checkpoints for trust, credentials, sovereignty, or activation
    decisions.
15. **Activation blocker status** — Whether trust, access, credential, sovereignty, or relevance issues block
    activation readiness in planning.
16. **Acceptance criteria** — Field-level pass or fail checks before assigning a status.
17. **Non-production disclaimer** — Restates preview-only posture and lack of activation, ingestion, or live
    calls.
18. **Next sprint recommendation** — Points to Sprint 135 NOFO extraction readiness in preview-only language.

## 6. Source Readiness Status Definitions

Eight preview-only statuses apply. Each explicitly disclaims source activation, live ingestion, and credential
configuration:

1. **Not assessed** — Minimum field coverage is missing; must be assessed before planning improves.
2. **Ready for controlled build planning** — Sufficient field coverage for operator-controlled build planning
   without live ingestion promises.
3. **Needs source verification** — Publisher, scope, or provenance claims require verification.
4. **Needs access decision** — Legal, policy, or partnership posture for the access method remains open.
5. **Needs credential review** — Secrets, accounts, or contractual access need security review.
6. **Needs sovereignty review** — Residency, export, retention, consent, or customer-data-touch questions are
   open.
7. **Blocked before activation** — Unresolved trust, access, credential, sovereignty, or relevance issues block
   activation readiness in planning.
8. **Deferred beyond M1** — Intentionally deferred past M1 while remaining visible in the inventory.

## 7. Field-Level Acceptance Criteria

For every field group, operators record at least two acceptance criteria (implemented as deterministic strings
in the Sprint 134 service) so readiness cannot collapse to a single checkbox. Criteria reinforce preview-only
language, traceability, explicit gap labels, and separation from runtime work.

## 8. Source Readiness by Source Type

Readiness items map to these source types for controlled build planning previews:

- **Grants.gov** — Federal catalog assumptions, fixture posture, credential review gates, and provenance for
  opportunity rows.
- **federal agency grant portals** — Agency-specific formats, authentication variance, and provenance per portal
  family.
- **state grant portals** — Jurisdictional diversity, eligibility nuance, and changing NOFO layouts without live
  portal promises.
- **local government grant portals** — Municipal fragmentation, access friction, and manual fallback paths.
- **tribal/federal Native-specific sources** — Native relevance rationale with sovereignty, trust, and human
  review prerequisites.
- **Native-serving nonprofit sources** — Mission alignment evidence, disclosure limits, and eligibility signal
  expectations.
- **foundation and philanthropy sources** — Private catalog rules, geographic scope, and restricted eligibility
  language.
- **corporate/private grant sources** — Competitive sensitivity, contractual gates, and least-privilege access
  reviews.
- **university/research grant sources** — Indirect cost rules, compliance-heavy clauses, and IP or data-use
  constraints.
- **manual NOFO upload sources** — Buyer or operator supplied documents, labeling, fixture boundaries, and
  review hooks.

## 9. Source Activation Prerequisite Rules

- Every source must have source readiness item identity and source access method recorded before activation
  planning proceeds.
- Trust level and source provenance requirement fields must be visible before activation planning treats a path
  as informed.
- Credential or access requirement entries must undergo security review before any live connection is planned.
- Native relevance rationale must be documented before a source is treated as inclusion-ready in planning.
- Freshness expectation must be documented before any ingestion schedule language is used.
- Unresolved source trust issues block activation readiness until mitigated, deferred with rationale, or
  rejected.

## 10. Human Gate and Review Rules

- Sources with low trust require human review before readiness can improve or activation planning proceeds.
- Sources requiring credentials require security review before live connection planning is allowed.
- Sources involving customer-specific data require sovereignty review before data handling is implied.
- Source activation decisions require explicit operator approval outside this planning packet.
- No ingestion job is created in this sprint.
- No runtime activation occurs in this sprint.

## 11. Sovereignty and Trust Requirements

- Customer owns its data.
- No customer data is required for this planning sprint.
- No customer data leaves the product during seeded demos.
- No model training on customer data without explicit written consent.
- Human judgment remains final.
- Source provenance remains visible.
- Source ingestion readiness must not overpromise implementation readiness.

## 12. What Sprint 134 Does Not Build

Sprint 134 explicitly does not build:

- no source activation
- no live ingestion
- no ingestion job creation
- no credential configuration
- no scraping
- no API call
- no customer data access
- no real application submission
- no production readiness certification
- no external service call
- no database migration
- no frontend UI
- no API route
- no production workflow change

## 13. M1 Source Ingestion Readiness Exit Criteria

The M1 source ingestion readiness packet is complete for informing controlled source ingestion build planning
when:

- All eighteen source readiness field groups are documented with purposes and acceptance criteria.
- All eight source readiness statuses include explicit non-activation, non-live-ingestion, and
  non-credential-configuration disclaimers.
- All thirteen foundations, ten source-type mappings, prerequisite rules, human gate rules, and sovereignty
  requirements are present for operator review.
- Risks and mitigations are recorded with operator discipline expectations.
- Sprint 135 is captured as the recommended next preview-only step.

## 14. Risks and Mitigations

At least eight risks are tracked in the deterministic service (excerpt):

- **Source activation is implied by planning language** — Ban activate, enable live, or connect verbs except
  inside explicit not-source-activation disclaimers.
- **Low-trust source enters build queue** — Force human review prerequisites and blocked statuses when trust
  stays below thresholds.
- **Provenance requirements are skipped** — Block activation readiness until provenance fields are documented or
  deferred with rationale.
- **Credential requirements are under-scoped** — Require security review rows and explicit secrets-handling
  notes before live connection planning.
- **Source freshness expectations are missing** — Block scheduling language until freshness expectation is
  documented.
- **Native relevance is too generic** — Require concrete Native relevance rationale tied to eligibility
  signals.
- **Scraping is implied without approval** — Disallow scrape language unless a documented human approval path
  exists as planning-only notes.
- **Customer data handling is implied too early** — Sequence sovereignty prerequisites before any
  customer-specific data language.
- **Source readiness becomes theater instead of control** — Tie statuses to explicit field coverage, blockers,
  and acceptance criteria reviewers can audit.

## 15. Sprint 135 Recommended Next Step

Sprint 135 should deliver the **M1 NOFO Extraction Controlled Build Readiness Packet**, still preview-only
unless the operator explicitly authorizes runtime work.
