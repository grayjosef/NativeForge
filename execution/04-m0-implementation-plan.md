# 04 — M0 Implementation Plan

This is the engineering plan for M0. It assumes Sprint 0 (`03-demo-isolation-spec.md`) is complete and signed off. If Sprint 0 is not done, stop and finish it.

## What M0 is

M0 is the demo build. The goal: a live walkthrough that proves the wedge — *a tribal grant manager goes from grant discovery to a compliant submission package without leaving NativeForge*. M0 does not need to work for a real tribe at full scale. It needs to be honest enough that a buyer trusts it.

## What M0 is not

- Not a production product.
- Not multi-source ingestion (Grants.gov only).
- Not full AI drafting (outline + summary only).
- Not post-award management.
- Not finance integrations.
- Not private deployment.
- Not multi-tenant consortium licensing.
- Not foundation/philanthropic source ingestion.

## The demo narrative (one screen, one minute)

```
1. Tribal grant manager logs in to demo org.
2. Sees pipeline view with 12 NativeForge-recognized Sparks.
3. One is an IHS behavioral health opportunity. Card shows:
   - Eligibility: likely yes
   - Mission match: strong
   - Reporting burden: moderate
   - Tribal resolution required
   - Due in 38 days
4. Clicks the Spark. NativeForge shows:
   - Plain-language NOFO summary (AI-generated, badge visible)
   - Extracted requirement checklist (forms, attachments, narrative sections)
   - Required forms list with SF-424 preview button
   - Pursuit recommendation with explanation
5. Clicks SF-424 preview. PDF renders pre-filled from tribal profile.
   AI badge on every autofilled field. Reviewer badge required to mark final.
6. Adds Spark to pipeline. Stage moves to "Pursuing."
   Tasks auto-generated from checklist. Deadline calendar updates.
7. Visits Data Sovereignty page. Reads the trust framework. Exports profile data.
```

That's it. M0 ships nothing else.

---

## Build sequence

The order matters. Do not parallelize. Each step assumes the previous one is merged.

### Sprint 0 (prerequisite — see `03-demo-isolation-spec.md`)

Demo isolation, review-gate state machine, all CI tests passing.

### Sprint 1 — Tribal profile + organization scaffold

Goal: a logged-in user in the demo org can view and edit a tribal profile.

- Migration creates `nf_tribal_profiles`.
- Backend: CRUD endpoints under `/api/nativeforge/profile`. Repository-layer enforced.
- Frontend: profile page at `/nativeforge/profile`. Form with all sections (legal identity, location, authorized officials, financial, certifications, narratives).
- Seed: one demo org with a fully populated example tribal profile.
- Tests: profile read/write scoped to org; demo isolation tests still pass.

**Done when:** demo user can view the seeded tribal profile and edit any field. Changes persist. Audit log records each change.

### Sprint 2 — Grant Spark ingestion (Grants.gov)

Goal: NativeForge ingests live opportunities from Grants.gov and stores them as Sparks.

- Migration creates `nf_grant_sparks`.
- Backend: scheduled job pulls Grants.gov REST API, deduplicates by `(source, source_id)`, stores in `nf_grant_sparks`.
- Tribal eligibility tagging: a deterministic rule scans the opportunity's eligible-applicant list against entity types and sets a boolean flag.
- For M0, the scheduled job runs once during seeding and produces ~12 demo Sparks. Live polling is M1.
- Backend: `GET /api/nativeforge/sparks` returns Sparks for the org, scoped.
- Frontend: list view at `/nativeforge/sparks` showing Spark cards.

**Done when:** demo org sees the seeded Sparks. Real org would see zero (no live ingestion in M0). Demo isolation tests still pass.

### Sprint 3 — NOFO summary + requirement extraction (seeded)

Goal: each Spark has a plain-language summary and a structured requirements list.

- Migration creates `nf_spark_requirements`.
- Backend: an extraction pipeline takes the Spark's `raw_nofo_text`, runs an LLM with the schema in `domain/nofo-extraction-schema.md`, stores results in `extracted` (JSONB) and per-row in `nf_spark_requirements`.
- Confidence scoring on every extracted field. Requirements with confidence < threshold flagged for human review.
- For M0, extraction runs during seeding only. M1 adds on-ingestion automation.
- Frontend: Spark detail page at `/nativeforge/sparks/:id` shows AI summary (with badge), structured requirements as a checklist, raw NOFO link.

**Done when:** each demo Spark has a summary and a requirements list. AI badge visible on AI-generated content. Each `ai_runs` entry recorded.

### Sprint 4 — Pursuit scoring (deterministic)

Goal: each Spark gets a six-dimension score and a recommendation tier.

- Backend: `score_spark(spark, profile)` is a pure function. No LLM in the scoring step. Implements the rules in `domain/scoring-model.md`.
- Score outputs are written to the score columns on `nf_grant_sparks`.
- The `recommendation_explanation` is **templated**, not freeform LLM. The template fills slots from rule outputs. The LLM may rephrase the templated explanation but cannot reinterpret the underlying score.
- Frontend: Spark cards show recommendation tier + score badges. Spark detail shows full breakdown.
- Tests: snapshot tests on the scoring function with known profile + known Spark inputs.

**Done when:** every demo Spark has a recommendation and a defensible explanation. Re-running scoring with same inputs produces same output. Score breakdown is visible on detail page.

### Sprint 5 — Pipeline + tasks

Goal: a Spark can be added to the pursuit pipeline. Tasks auto-generate from the requirements checklist.

- Migration creates `nf_pursuit_tasks`.
- Backend: `POST /api/nativeforge/sparks/:id/pipeline/advance` moves a Spark through pipeline stages. Stage changes write to audit log.
- Backend: when a Spark moves from `evaluating` to `pursuing`, `nf_pursuit_tasks` rows are auto-generated from the Spark's requirements.
- Frontend: pipeline kanban view at `/nativeforge/pipeline`. Spark cards drag between columns (or click to advance for keyboard a11y). Task list visible per Spark.
- Frontend: deadline calendar at `/nativeforge/calendar` with all Spark deadlines and task due dates.

**Done when:** demo user can move Sparks through the full pipeline. Tasks appear automatically on the Pursuing transition. Deadline calendar reflects all dates.

### Sprint 6 — SF-424 preview (autofill from profile)

Goal: clicking "SF-424 preview" on a Spark renders a pre-filled SF-424 PDF.

- Migration creates `nf_form_packages`.
- Backend: SF-424 field-to-profile field mapping per `domain/federal-forms.md`.
- Backend: PDF generation using a fillable SF-424 PDF template from GSA. Output stored as a document blob.
- Backend: `POST /api/nativeforge/sparks/:id/forms/sf424` generates the package and returns the blob URL. `review_status` starts at `draft`.
- Frontend: SF-424 preview rendered inline (PDF.js). Every autofilled field has an AI badge. "Mark as ready for review" button transitions to `review_requested`.
- Tests: state machine transitions enforced; cannot jump to `approved` without going through `reviewed`.

**Done when:** demo user can preview a pre-filled SF-424 for any seeded Spark. Reviewer can move to `reviewed`. Admin can approve. The system refuses to skip steps.

### Sprint 7 — Data sovereignty page + export

Goal: the trust framework is visible in the product, not just marketing copy. Profile data is exportable.

- Frontend: `/nativeforge/sovereignty` page. Reads `domain/sovereignty-trust-framework.md` content. Lists what NativeForge does and does not do with tribal data.
- Backend: `GET /api/nativeforge/export/full` returns a ZIP of the org's tribal profile, sparks, requirements, tasks, and form packages, as JSON + CSV.
- Frontend: "Export my data" button on profile page triggers the export.
- Tests: export only includes records for the requesting org. Demo isolation tests still pass on the export endpoint.

**Done when:** demo user can read the sovereignty page and download a complete export of their data.

---

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| NOFO extraction quality is poor on seeded examples and undermines the demo | High | Hand-curate the 12 demo Sparks; verify each extraction by hand before sealing the seed data; flag any low-confidence requirements visibly |
| Score recommendation looks "AI-y" because the templated explanation is wooden | Medium | Iterate the explanation templates with a tribal grant manager review before sealing M0 |
| Demo isolation breaks under a feature added in a later sprint | High | Every PR runs the Sprint 0 CI tests; any failure blocks merge |
| SF-424 PDF rendering pixel-shifts in the demo because GSA template versions change | Medium | Pin the GSA SF-424 PDF version in the repo; treat it as a fixture |
| Cursor or a developer creates demo data on a real org by mistake | Critical | Trigger + RLS rejects it; if either is missing per the audit, fix that before any seed work |
| Audit reveals ContractForge has no tenancy model and we cannot just bolt one on | Critical | Stop and rescope. M0 cannot ship without a tenancy model. This becomes the first feature, not a precondition. |
| AI-drafted summaries leak between orgs because `ai_runs` is not org-scoped | High | Verify `ai_runs` has `organization_id` and is filtered in the audit |
| The demo narrative depends on a feature we cut for time | Medium | Re-read the demo narrative at the end of each sprint; if a step is broken, the sprint is not done |

---

## What gets cut if we run out of time

In order, lowest priority first:

1. Deadline calendar (Sprint 5, secondary feature)
2. Task auto-generation from requirements (Sprint 5, can be manual)
3. Recommendation explanation polish (Sprint 4)
4. AI summary (Sprint 3, can be a fixture string instead of live extraction)

What does NOT get cut: demo isolation, tribal profile, Spark list, Spark detail with requirements, scoring, SF-424 preview, sovereignty page, export.

If we cannot ship those, M0 is not M0. Push the date instead of shipping a wounded demo.

---

## Validation gate before declaring M0 done

- [ ] All seven sprints' acceptance criteria met.
- [ ] Demo narrative walks end-to-end without a broken step.
- [ ] All Sprint 0 CI tests still pass on main.
- [ ] `validation/definition-of-done.md` checklist passes for every merged PR.
- [ ] One internal dry-run demo to a non-engineer who has not seen the product. They can describe what they saw without coaching.
- [ ] One review pass against `context/guardrails-and-risks.md`. No AI-generated content escapes the badge. No demo data anywhere near real org context.
- [ ] One review pass against `context/operating-principles.md`. No commits with secrets, no broad refactors of ContractForge, no skipped review gates.

Only after all eight boxes are checked does M0 ship to a buyer.
