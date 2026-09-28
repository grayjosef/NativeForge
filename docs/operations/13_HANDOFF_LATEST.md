# NativeForge Handoff — Individual pursuit command center

**Date:** 2026-09-28
**Path:** `/home/josefgray/projects/nativeforge`
**Live:** `https://nativeforge.mayhem-nc.dev`
**Protected stash:** `stash@{0}: wip-sprint8-ui-redesign-do-not-commit` — never drop
**Push policy:** commits and pushes allowed after tests; never force-push; never prune

## Operating objective

Finish NativeForge as a product. Demo is a live checkpoint, not a freeze line.
Controlled-customer launch is the finish line. Collectors stay off unless Mayhem authorizes activation. Do not touch real tenants / Carolina Fire Protection Microsoft / Auth0.

## This run — flagship individual pursuit workspace

The individual grant page is now a pursuit command center, not an information display.

- **Canonical reuse:** opportunity = `nf_grant_sparks`; pursuit = `nf_grant_pursuits` (1:1 per spark, org-scoped). Workflow stages are derived from the same persisted objects as Workspace Guided Pursuit (profile → opportunity → requirements → eligibility → pursuit → package → trust). No second stage column.
- **Discovered vs pursuing:** an opportunity without a pursuit row shows "Opportunity discovered" and does not present chase progress. Starting a pursuit initializes the same workflow for uploaded (`source=manual`) and discovered (`source=grants_gov`) records.
- **Contacts:** 0068 `nf_opportunity_contacts` via the apply-path service, with provenance. Missing names are not invented.
- **New durable entity (0069):** `nf_funder_interactions` — tenant-private questions, calls, clarifications, webinars, follow-ups. RLS FORCE + WITH CHECK. Agency matching for institutional memory is exact normalized string; people are never fuzzy-merged.
- **UX:** command center sits at the top of Documents and Pursuits. Workspace Guided Pursuit remains and is now clickable into real destinations.

Alembic head is **0069**. Head pins updated in Gate 63 doctrine and the membership-directory expected head.

## Tests this run

- `ruff check` on sprint files: pass. `ruff format --check` on sprint files: pass.
- `pytest -q` command-center + apply-path + Sprint 5 pursuit + Sprint 20 discovery + Gates 60/118/132 + identity presentation + Microsoft login: **194 passed**.
- Frontend: `vitest` `PursuitCommandCenter.test.tsx` **4 passed**; App + Add Opportunity + Stage 12 smoke also green in the same run (29 passed / 1 later-fixed command-center assertion).
- Stash `stash@{0}` still present.

## Remaining launch-critical

- Microsoft Entra app + Railway `NF_OIDC_MICROSOFT_*` (demo blocker if Microsoft is required). Code already refuses to send Microsoft starts to Google.
- No first-class funder *entity* table: agency is still a string on the spark. Institutional memory is same-tenant exact-agency continuity, which is enough to start a future Funder Profile without a second contact system.
- Question dates/methods only when notice text matches; no mailbox ingestion.
- Apply-path `extraction_performed` is true only when a contact or submission row exists, so a notice that was read and named nobody is indistinguishable from unread unless a submission path was stored.
- Real non-demo observations in customer UX (blocked on authorized collector activation).
- Discover remains empty by design until activation.
- Pre-existing: `tests/test_sprint0_naming_guard.py::test_nf_sources_avoid_contractforge_table_names` (false positives from `FROM contracts` prose).

## Proposed next

1. Open two demo pursuits on live after deploy and confirm independent workflow, contacts, and a recorded interaction survive reload.
2. Set Railway `NF_OIDC_MICROSOFT_*` when Microsoft sign-in is required.
3. Do not activate collectors without explicit authorization.
4. Do not add a separate funder CRM; the next safe expansion is a read-model Funder Profile over exact-agency memory already stored.
