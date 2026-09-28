# NativeForge Handoff — customer-launch completion, slice 1

**Date:** 2026-09-28
**Path:** `/home/josefgray/projects/nativeforge`
**Live before this slice:** `https://nativeforge.mayhem-nc.dev`
**HEAD at start:** `1a534f1245e255cb9352ed8b232f4fd824536ddc`
**Protected stash:** `stash@{0}: wip-sprint8-ui-redesign-do-not-commit` — never drop

## Baseline re-established

- `main` and `origin/main` were `1a534f12` (EmptyState import). Worktree clean of that fix.
- Live root HTTP 200 and rendered the workspace, including the deadlines empty state that previously crashed.
- `/backend/health` status `ok`, `git_sha` `unknown`, `production_ready` false.
- `/backend/readiness`: `database_ready` true, `persistent_backend_live` false, `customer_auth_live` false, `controlled_customer_pilot` false.
- `/api/auth/providers`: Google and Microsoft `configured: true`. `login_live` false. `customer_auth_live` false.
- Login GETs 302 to accounts.google.com and login.microsoftonline.com.
- Unauthenticated `/api/auth/session` is `unauthenticated`. Activation blockers include callback session, dev-header gate, invite binding, org binding, role mapping, and owner approval.
- Repo Alembic head `0070` (`0070_pursuit_task_owner`). Local sqlite current `0068`. Production revision not exposed by health.

## This slice

Unsigned visitors were painting the full workspace (demo chrome, empty organization) until the session request returned. Customer workflow copy still said “Grant Spark”.

- Hold on “Opening NativeForge” until the session is known. Unsigned customer surfaces render the sign-in page. Bundled demo surfaces stay public.
- Guided-workflow and opportunity-card copy say Opportunity / Opportunities.

## Tests

- `npx vitest run src/App.test.tsx src/pages/WorkspacePage.test.tsx src/pages/SignInPage.test.tsx` — 16 passed.

## Customer-launch status

NOT READY. Auth activation is still false, live sign-in was not completed, discovery collectors are not switched on, invitations are not a customer flow, and no second-organization boundary was exercised this run.
