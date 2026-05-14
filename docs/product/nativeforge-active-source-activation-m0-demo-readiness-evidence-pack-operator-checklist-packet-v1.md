# NativeForge M0 Demo Readiness Evidence Pack and Operator Checklist Packet v1

This document is the product-facing companion to Sprint 129. It mirrors the deterministic operator packet
implemented in
`src/nativeforge/services/active_source_activation_m0_demo_readiness_evidence_pack_operator_checklist_packet_service.py`.
The packet is preview-only: it defines planning artifacts and checklist discipline; it does not execute
demos, create evidence files, open buyer sessions, call external services, or access customer data.

## 1. Purpose

This packet defines the M0 planning layer for demo readiness evidence and operator go/no-go checks before
buyer presentation. It specifies how operators inventory demo-visible artifacts, confirm seeded data,
align buyer proof points with evidence, surface caveats and missing data, validate provenance and
sovereignty claims, and record human review expectations—all without running a real demo or implying
production, legal, or submission authority.

## 2. Why This Comes After Demo Narrative Planning

Sprint 128 defined the buyer walkthrough narrative and demo-safe storytelling beats. Sprint 129 defines
the evidence pack and operator checklist that prevent the narrative from becoming unsupported sales
theater. Evidence rows, field groups, and checklist statuses force explicit linkage between buyer-visible
claims and in-repo artifacts, sprint packets, fixtures, and labeled seeds.

## 3. M0 Demo Readiness Objective

The goal is a demo-safe readiness checklist that confirms artifacts, caveats, proof points, seeded data,
provenance, sovereignty claims, and review gates before buyer presentation. Outcomes inform later demo
rehearsals or implementation plans; they do not execute runtime workflows.

Foundation areas operators cover in this planning layer:

1. Demo artifact inventory
2. Seeded data confirmation
3. Buyer narrative readiness
4. M0 feature coverage checklist
5. Human review gate confirmation
6. Caveat and boundary confirmation
7. Sovereignty and trust evidence confirmation
8. Source provenance evidence confirmation
9. Demo risk review
10. Operator go/no-go readiness

## 4. Demo-Safe Readiness Rules

Operators must treat this packet as planning-only discipline:

- Require seeded or demo-safe records only; never load production customer extracts into demo readiness
  planning.
- Do not access real customer data while building or reviewing this evidence pack.
- Do not run a real demo execution, runtime workflow, or live rehearsal automation from this sprint packet.
- Do not create evidence files, buyer sessions, or CRM records from this sprint packet.
- Do not submit applications, forms, or e-signatures while using this checklist.
- Do not present final eligibility determinations; label all eligibility signals as preview-only.
- Do not certify production readiness, grant legal approval, or authorize submissions from checklist
  statuses.
- Do not place external API calls, scrapes, live ingestions, or live AI generations while using this packet.
- Keep human judgment, provenance, sovereignty boundaries, and missing-data visibility explicit.

Restated: seeded or demo-safe records only; no real customer data; no real demo execution; no production
readiness certification; no legal approval; no submission authorization; no external calls.

## 5. Required Evidence Field Groups

Eighteen field groups structure every evidence item:

1. **Evidence item identity** — Stable id, title, and version for cross-artifact references.
2. **Evidence item source sprint** — Sprint packet or planning artifact that owns lineage.
3. **M0 feature covered** — M0 surface the evidence supports (profile, NOFO summary, pipeline, and so on).
4. **Buyer proof point** — Buyer-visible claim the evidence must support without overstating automation.
5. **Demo-safe data confirmation** — Explicit demo-safe or synthetic labels; no customer extracts.
6. **Human review status** — Human review expectations documented without simulating approvals.
7. **Source provenance status** — Visible, partial, or missing provenance for buyer-visible fields.
8. **Sovereignty/trust status** — Alignment with sovereignty statements, export limits, and consent
   boundaries.
9. **Caveat visibility status** — Preview-only, non-submission, and non-final eligibility caveats visible.
10. **Missing data status** — Known gaps disclosed with operator actions or deferrals.
11. **Risk note** — Demo misunderstanding risks and product limits tied to the evidence item.
12. **Operator action required** — Next concrete planning step such as re-label seeds or attach paths.
13. **Go/no-go status** — Operator checklist outcome using demo-safe statuses only.
14. **Closeout note** — Closure expectations referencing caveat, provenance, and sovereignty confirmations.
15. **Artifact path or reference** — Repo paths, fixtures, or sprint packets evidencing the claim.
16. **Non-production disclaimer** — Preview-only posture; not go-live approval language.
17. **Buyer question linkage** — Maps buyer questions and sovereignty, eligibility, or export concerns.
18. **Next sprint recommendation** — Points to Sprint 130 planning without silent runtime expansion.

## 6. Operator Checklist Status Definitions

Eight demo-safe statuses apply. **Every status explicitly disclaims production readiness certification,
legal approval, and submission authorization** (see the repeated disclaimer in the sprint service output).

| Status | Intent |
| --- | --- |
| Not checked | Default before operator review. |
| Ready for demo | Evidence, caveats, provenance, and demo-safe labels satisfy acceptance criteria. |
| Needs operator review | Ambiguity, partial provenance, or weak proof mapping needs human judgment. |
| Needs seeded data correction | Labels, fixtures, or synthetic records need correction. |
| Blocked by missing evidence | Required artifact or reference is absent or unverifiable. |
| Blocked by unclear caveat | Caveat language missing, buried, or inconsistent with preview-only posture. |
| Excluded from buyer walkthrough | Tracked internally but omitted from buyer-facing narrative. |
| Deferred to later sprint | Deferred with explicit rationale; not hidden as complete. |

## 7. Field-Level Acceptance Criteria

Each field group in the sprint service carries at least two acceptance criteria. Operators use those
criteria as pass/fail planning checks before assigning a checklist status. Criteria deliberately reinforce
preview-only posture, provenance visibility, and honest missing-data handling.

## 8. Evidence Pack by M0 Feature

Evidence planning maps to these M0 features (including the Sprint 128 narrative layer):

- **organizational entity profile** — Entity fields and tribal context as labeled seeds only.
- **seeded opportunity ingestion** — Fixtures or seeds without live ingestion or scraping.
- **tribal eligibility and mission fit scoring** — Preview scores with non-final caveats and confidence.
- **NOFO plain-language summary** — Bullets traced to seeded NOFO excerpts with provenance notes.
- **opportunity recommendation preview** — Draft recommendations with human review expectations visible.
- **pursuit pipeline and deadline tracking** — Demo-safe timelines without production writes.
- **SF-424 autofill preview** — Field mapping without submission or signing pathways.
- **requirement checklist preview** — Rows tied to NOFO clauses with explicit completeness gaps allowed.
- **data sovereignty policy and export preview** — Policy and export posture without moving customer data.
- **human review closeout** — Alignment with Sprint 127 review gate planning.
- **demo narrative and buyer walkthrough** — Evidence backing Sprint 128 beats, proof points, and caveats.

## 9. Operator Go/No-Go Checklist

Before buyer presentation planning sign-off, operators confirm:

- All demo-visible artifacts exist with paths or sprint lineage references.
- All seeded records are labeled demo-safe or synthetic without customer extracts.
- All buyer proof points map to artifacts, fixtures, or sprint planning evidence rows.
- All caveats are visible where buyers encounter AI-adjacent, eligibility, or form-adjacent claims.
- All low-confidence outputs are marked with visible confidence or review language.
- All missing data is visible with explicit gaps rather than silent omission.
- All sovereignty claims are preview-only with provenance and export boundary notes.
- No submission pathway is implied by screenshots, copy, or checklist language.
- No customer data is used in seeded demo readiness planning or referenced artifacts.
- No production readiness is implied by demo go/no-go outcomes or checklist statuses.

## 10. Buyer Question and Follow-Up Capture

Operators capture buyer questions and follow-ups outside this sprint packet:

- Capture buyer questions verbatim or in faithful paraphrase in operator-controlled notes.
- Map follow-up discovery questions to M1 pilot planning topics without CRM automation from Sprint 129.
- Mark sovereignty concerns for review with provenance and export evidence links.
- Mark eligibility concerns for review with non-final scoring caveats repeated.
- Mark export or auditability concerns for review with policy and preview evidence.
- **No buyer record is created in this sprint**; capture stays operator-controlled only.

## 11. Sovereignty and Trust Requirements

- customer owns its data
- no customer data required for seeded demos
- no customer data leaves the product during seeded demos
- no model training on customer data without explicit written consent
- human judgment remains final
- source provenance remains visible
- evidence pack must not overpromise production readiness

## 12. What Sprint 129 Does Not Build

Sprint 129 explicitly does not build:

- no real demo execution
- no evidence file creation
- no buyer session creation
- no CRM automation
- no customer data access
- no real application submission
- no production readiness certification
- no legal approval
- no external service call
- no database migration
- no frontend UI
- no API route
- no production workflow change

## 13. M0 Exit Criteria for Demo Readiness Planning

The demo readiness evidence pack and operator checklist planning packet is complete when:

- All eighteen evidence field groups are documented with purposes and acceptance criteria.
- All eight checklist statuses include explicit non-production, non-legal, non-submission disclaimers.
- All eleven M0 feature evidence mappings include buyer proof, caveat, and provenance expectations.
- Operator go/no-go checklist, buyer question capture, sovereignty requirements, and scope limits are listed.
- Risks and mitigations are recorded with demo discipline expectations for operators.
- Sprint 130 recommendation is captured as the next preview-only pilot transition planning step.

## 14. Risks and Mitigations

1. **operator runs demo without evidence** — Block Ready for demo until artifact paths and caveat
   visibility are recorded.
2. **buyer proof points are not artifact-backed** — Map every proof point to evidence rows; label missing
   data explicitly.
3. **caveats are skipped during demo** — Mandate caveat visibility checks; use Blocked by unclear caveat
   when buried.
4. **seeded records are confused with customer records** — Require demo-safe labels on every reference.
5. **buyer assumes production readiness** — Repeat preview-only language and checklist status disclaimers.
6. **sovereignty claims are overstated** — Pair sovereignty statements with provenance and export limits.
7. **low-confidence outputs are hidden** — Force visible confidence or review markers before go recommendations.
8. **follow-up questions are not captured** — Use buyer question linkage fields and M1 mapping prompts.
9. **checklist becomes theater instead of real go/no-go discipline** — Require explicit rationale and
   blocked statuses instead of silent passes.

## 15. Sprint 130 Recommended Next Step

Sprint 130 should deliver the **M0 Pilot Transition and M1 Readiness Planning Packet**, still preview-only
and demo-safe unless the operator explicitly authorizes runtime work.
