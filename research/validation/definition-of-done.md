# Definition of Done

Every NativeForge M0 unit of work — sprint, ticket, PR — passes this checklist before it counts as done. Cursor checks against it before declaring completion. The human reviews against it before merging.

## Code

- [ ] **Tests added.** Every new behavior has at least one test. Bug fixes include a regression test.
- [ ] **Lint passes.** `ruff` (Python) / equivalent for other languages. No new warnings introduced.
- [ ] **Frontend checks pass.** Type check, build, and unit tests on the frontend layer.
- [ ] **No secrets added.** No API keys, credentials, tokens, or private keys committed. Pre-commit hook or CI grep enforced.
- [ ] **No raw SQL on `nf_*` tables outside the repository module.** CI grep enforced (see `execution/03-demo-isolation-spec.md` Layer 4).

## Demo isolation

- [ ] **All 7 demo isolation CI tests still pass on this branch.**
- [ ] **No demo data is reachable from a real-org context.** New code paths are exercised by the cross-tenant fuzz test.
- [ ] **Any new `nf_*` table has the `is_demo` column, the FK to `organizations`, and the trigger enforcing alignment.**
- [ ] **(Postgres only)** Any new `nf_*` table has RLS enabled with the standard org-scope and demo-scope policies.

## Server-side enforcement

- [ ] **Any new state machine transition is enforced server-side.** UI does not bypass.
- [ ] **Any new AI-generated content has a badge in the UI.**
- [ ] **Any new AI call is recorded in `ai_runs` with input, output, model, cost, user, timestamp.**
- [ ] **API returns expected status codes.** 200/201 on success, 422 on validation, 403 on auth failure, 404 on missing. Tested.
- [ ] **UI does not hide a backend security failure.** A 403 from the API surfaces as a 403 to the user, not a silent empty state.

## ContractForge regression

- [ ] **No ContractForge test breaks.** If a test was failing before this branch, it is documented and unchanged.
- [ ] **No ContractForge route or page changed unless explicitly approved.**
- [ ] **No shared component modified in a way that visually or behaviorally changes ContractForge unless explicitly approved.**

## Cultural and sovereignty guardrails

- [ ] **No pan-Indian generalization in any new template, prompt, default copy, or seed data.**
- [ ] **Any AI prompt that touches cultural content has been written against the rules in `domain/drafting-guardrails.md`.**
- [ ] **Any new data export endpoint returns only the requesting org's data.** Tested.
- [ ] **Any new audit-log-affecting action writes to the audit log.**

## Documentation

- [ ] **PR description references the file paths changed and the test names that prove the behavior.**
- [ ] **Any operating principle relevant to the change is named in the PR description (especially any near-violation that was avoided).**
- [ ] **Open questions are listed in the PR description, not buried in code comments.**

## What "done" never means

- "It works on my machine."
- "Tests are flaky, ignored that one."
- "I'll add the test in a follow-up PR."
- "The frontend will catch it."
- "It's just demo data, it doesn't matter."
- "We can fix that later when we add RBAC."
- "I disabled the lint rule for this file."
- "The audit log entry is good enough; we don't need a test."

If any of these phrases shows up in PR review, the PR is not done.

## Escalation

If a checklist item cannot be satisfied for a legitimate reason (e.g., the test framework doesn't yet support the scenario), the PR explicitly calls it out, the human signs off on the gap, and a follow-up ticket is created and linked. The default is satisfied; documented exceptions are rare.

## HITP Commit Gate

All future NativeForge work requires the hard Human-in-the-Pipeline commit gate defined in `docs/HITP_COMMIT_GATE.md`.

No agent may commit automatically. Backend validation, frontend validation, migration status, diff stat, known risks, and intentionally untested items must be shown before commit approval. The agent must stop and wait for one of the valid approval phrases before running `git commit`.

No commit may be made based only on backend tests.
