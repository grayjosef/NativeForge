# NativeForge M1 NOFO Extraction Controlled Build Readiness Packet v1

This document is the product-facing companion to Sprint 135. It mirrors the deterministic operator packet
implemented in
`src/nativeforge/services/active_source_activation_m1_nofo_extraction_controlled_build_readiness_packet_service.py`.
The packet is preview-only: it defines NOFO extraction and requirement parsing readiness before controlled
build planning; it does not execute NOFO extraction, parse requirements, process documents, invoke AI
generation, create extraction jobs, activate sources, perform live ingestion, call external services, scrape
websites, or access customer data.

## 1. Purpose

This packet defines the M1 planning layer for NOFO extraction and requirement parsing controlled build
readiness. Operators use it to reference NOFO documents in a fixture-safe way, bound extraction targets,
document provenance and confidence expectations, route human gates for sensitive fields, and record sovereignty
and security guardrails—without extraction execution, requirement parsing, document processing, AI generation,
external calls, scraping, or customer data handling in this sprint.

## 2. Why This Comes After Source Ingestion Readiness

Sprint 134 defined source ingestion readiness so candidate sources, trust, provenance, credentials, and
sovereignty dependencies stay visible before live ingestion language appears. Sprint 135 applies controlled
build discipline to extracting requirements from NOFO documents only after sources and provenance are visible,
so extraction scope, confidence rules, human gates, and blockers remain honest while staying non-executing.

## 3. M1 NOFO Extraction Readiness Objective

The goal is a preview-only readiness framework that prevents extraction work from starting before documents,
extraction targets, provenance, confidence thresholds, human gates, sovereignty and security dependencies, and
blockers are visible—without runnable extraction promises, runtime execution, AI generation, or document
processing in this sprint.

Foundations the packet anchors:

1. NOFO document readiness
2. Extraction scope readiness
3. Requirement parsing readiness
4. Source provenance readiness
5. Confidence scoring readiness
6. Human review gate readiness
7. Eligibility extraction readiness
8. Deadline extraction readiness
9. Attachment requirement extraction readiness
10. Narrative requirement extraction readiness
11. Budget/match extraction readiness
12. Reporting burden extraction readiness
13. Data sovereignty and security readiness

## 4. Preview-Only NOFO Readiness Rules

Operators must treat this packet as planning-only discipline:

- Require seeded or demo-safe records only; never import production customer extracts into NOFO readiness rows.
- Do not access real customer data while building or reviewing this NOFO readiness packet.
- Do not execute NOFO extraction, parse requirements, or process documents from this sprint packet.
- Do not invoke AI generation, model calls, or automated summarization while using this packet.
- Do not place external API calls, scrapes, live ingestions, or live AI generations while using this packet.
- Do not submit applications, forms, or e-signatures while using this packet.
- Keep human judgment, provenance visibility, sovereignty boundaries, and missing-data disclosure explicit.

Restated: seeded or demo-safe records only; no real customer data; no NOFO extraction execution; no requirement
parsing; no document processing; no AI generation; no external calls; no scraping.

## 5. Required NOFO Readiness Field Groups

Eighteen field groups structure every NOFO readiness row:

1. **NOFO readiness item identity** — Stable id, title, and version for cross-artifact references.
2. **NOFO source reference** — Fixture or demo-safe pointer to the NOFO without ingestion or execution here.
3. **Document type** — Solicitation, amendment, FAQ, or attachment packet classification without file IO.
4. **Extraction target** — Structured slice such as eligibility, deadlines, attachments, or budgets in scope.
5. **Requirement category** — Mandatory, scored, narrative, financial, or compliance grouping for prerequisites.
6. **Provenance requirement** — Publisher attestation, fixture labels, amendment lineage, and traceability needs.
7. **Confidence threshold** — Minimum confidence for auto carry-forward versus forced human review later.
8. **Human review prerequisite** — Checkpoints for low confidence, eligibility, deadlines, or submission-adjacent
   fields.
9. **Eligibility extraction expectation** — Cues and jurisdiction sensitivity without final determinations.
10. **Deadline extraction expectation** — Cutoffs, channels, timezone, and grace-period assumptions with review.
11. **Attachment extraction expectation** — Required file families and optional versus mandatory signals without
    processing files.
12. **Narrative extraction expectation** — Essays, equity statements, and community narratives scoped separately.
13. **Budget or match extraction expectation** — Match ratios, allowability, indirects, and budget forms as
    planning notes only.
14. **Reporting burden extraction expectation** — Cadence, metrics, audits, and compliance clauses without job
    creation.
15. **Extraction blocker status** — Whether documents, provenance, confidence, or scope issues block readiness.
16. **Acceptance criteria** — Field-level pass or fail checks before assigning a status.
17. **Non-production disclaimer** — Restates preview-only posture and lack of extraction, AI, or document
    processing.
18. **Next sprint recommendation** — Points to Sprint 136 form package readiness in preview-only language.

## 6. NOFO Readiness Status Definitions

Eight preview-only statuses apply. Each explicitly disclaims extraction execution, AI generation, and document
processing:

1. **Not assessed** — Minimum field coverage is missing; must be assessed before planning improves.
2. **Ready for controlled build planning** — Sufficient field coverage for operator-controlled extraction build
   planning without execution promises.
3. **Needs document verification** — Publisher, version, or amendment lineage requires verification.
4. **Needs extraction scope review** — Targets, exclusions, or attachment scope remain ambiguous.
5. **Needs confidence rule review** — Thresholds, scoring rubrics, or confidence labels need operator review.
6. **Needs human review gate** — Low confidence, eligibility, deadline, or submission-adjacent fields need
   checkpoints.
7. **Blocked before extraction** — Unresolved documents, provenance, confidence, sovereignty, or scope issues
   block readiness in planning.
8. **Deferred beyond M1** — Intentionally deferred past M1 while remaining visible in the inventory.

## 7. Field-Level Acceptance Criteria

For every field group, operators record at least two acceptance criteria (implemented as deterministic strings
in the Sprint 135 service) so readiness cannot collapse to a single checkbox. Criteria reinforce preview-only
language, traceability, explicit gap labels, and separation from extraction execution, AI generation, and
document processing.

## 8. NOFO Readiness by Extraction Target

Readiness items map to these extraction targets for controlled build planning previews:

- **eligibility criteria** — Identity, provenance, confidence thresholds, and mandatory human review before
  eligibility extraction language is treated as informed.
- **application deadlines** — Channel-specific cutoff assumptions, timezone risk, and human review before
  deadline extraction is trusted.
- **attachment requirements** — Expected attachment families, optional versus mandatory cues, and provenance
  without file execution.
- **narrative requirements** — Essay prompts, page limits, and equity narrative expectations with human review
  for sensitive topics.
- **budget and match requirements** — Match ratios, allowability tables, and form families as planning expectations
  without calculations.
- **reporting burden requirements** — Cadence, metrics, audits, and compliance clauses with reviewer ownership.
- **submission method requirements** — Electronic portal, email, or mail paths with submission-adjacent human
  review gates.
- **evaluation criteria** — Scoring rubrics, weighting, and reviewer notes aligned to confidence thresholds.
- **award terms and restrictions** — Post-award restrictions, fund uses, and continuation expectations without
  contract execution.
- **compliance and assurance requirements** — Assurance, audit, civil rights, and data handling clauses with
  sovereignty prerequisites.

## 9. Extraction Prerequisite Rules

- Every extraction target must have a source document reference recorded before extraction planning proceeds.
- Every extracted field must preserve provenance in downstream designs even though this sprint performs no
  extraction.
- Confidence thresholds must be visible before controlled build planning treats outputs as informed.
- Human review gates must exist for low-confidence extraction targets before automation is assumed.
- Eligibility and deadline extraction require explicit human review in planning artifacts.
- Unresolved provenance issues block extraction readiness until mitigated, deferred with rationale, or rejected.

## 10. Human Gate and Review Rules

- Low-confidence extracted fields require human review in future builds; this sprint defines the gate only.
- Eligibility determinations require human review and must not be treated as final from extraction outputs.
- Deadline extraction requires human review before operators rely on extracted calendar values.
- Submission-adjacent requirements require human review because channels and cutoffs shift frequently.
- Extraction activation decisions require explicit operator approval outside this planning packet.
- No extraction job is created in this sprint.
- No runtime activation occurs in this sprint.

## 11. Sovereignty and Trust Requirements

- Customer owns its data.
- No customer data is required for this planning sprint.
- No customer data leaves the product during seeded demos.
- No model training on customer data without explicit written consent.
- Human judgment remains final.
- Source provenance remains visible.
- NOFO extraction readiness must not overpromise implementation readiness.

## 12. What Sprint 135 Does Not Build

Sprint 135 explicitly does not build:

- no NOFO extraction execution
- no requirement parsing
- no document processing
- no AI generation
- no extraction job creation
- no source activation
- no live ingestion
- no customer data access
- no real application submission
- no production readiness certification
- no external service call
- no database migration
- no frontend UI
- no API route
- no production workflow change

## 13. M1 NOFO Extraction Readiness Exit Criteria

The M1 NOFO extraction readiness packet is complete for informing controlled NOFO extraction build planning
when:

- All eighteen NOFO readiness field groups are documented with purposes and acceptance criteria.
- All eight NOFO readiness statuses include explicit non-extraction, non-AI-generation, and non-document-processing
  disclaimers.
- All thirteen foundations, ten extraction-target mappings, prerequisite rules, human gate rules, and
  sovereignty requirements are present for operator review.
- Risks and mitigations are recorded with operator discipline expectations.
- Sprint 136 is captured as the recommended next preview-only step.

## 14. Risks and Mitigations

At least eight risks are tracked in the deterministic service (excerpt):

- **Extraction execution is implied by planning language** — Ban extract, parse, or run verbs except inside
  explicit not-extraction-execution disclaimers.
- **Provenance requirements are skipped** — Block extraction readiness until provenance fields are documented or
  deferred with rationale.
- **Low-confidence fields are treated as final** — Force human review prerequisites and confidence thresholds
  before auto carry-forward language.
- **Eligibility extraction becomes final eligibility determination** — Require human review labels and forbid
  go or no-go eligibility language without operator sign-off.
- **Deadline extraction is not human-reviewed** — Mandate human review gates for deadlines and channel-specific
  cutoff assumptions.
- **Document processing is implied too early** — Disallow file open, parse, or OCR language unless framed as
  future build scope with explicit authorization.
- **Customer data handling is implied too early** — Sequence sovereignty prerequisites before any
  customer-specific data language.
- **AI generation is implied without approval** — Disallow model, LLM, or auto-summarize language unless a
  documented human approval path exists as planning-only notes.
- **Extraction readiness becomes theater instead of control** — Tie statuses to explicit field coverage, blockers,
  and acceptance criteria reviewers can audit.

## 15. Sprint 136 Recommended Next Step

Sprint 136 should deliver the **M1 Form Package Controlled Build Readiness Packet**, still preview-only unless
the operator explicitly authorizes runtime work.
