# NativeForge Handoff — customer-launch block 2, slice 1

**Date:** 2026-09-28
**Path:** `/home/josefgray/projects/nativeforge`
**Protected stash:** `stash@{0}: wip-sprint8-ui-redesign-do-not-commit` — never drop

## Baseline at start

- HEAD and origin/main: `930a720b8a9cda2bf6aa05d8a3be0cc9dd85f953`
- `/health` already reported that SHA, `source_dirty: false`, `deployment_identity_known: true`
- `/backend/health` reported `git_sha: unknown` because it only asked git, and the container has none
- Google and Microsoft configured. `login_live` false. `customer_auth_live` false
- Alembic head `0070`. Local sqlite `0068`

## This slice

- `/backend/health` uses `NF_GIT_SHA` when git cannot answer, and only when the value is a 40-character commit. An unstamped process still reports `unknown`.
- Card and hover shadows are off. Menus and the mobile drawer keep one shared elevation token.
- Navigation labels a customer can use: Home, Discovery, My Pursuits. No new dead destinations.
- The supplied brand kit is stored at `frontend/public/brand/kit/`. The lockup the app already serves (`frontend/public/brand/nf-lockup.png`) is the same canonical mark and is cleaner than the chat-transcoded copies, whose tagline is damaged. The served artwork was not replaced with the damaged files.

## Tests

- `pytest tests/test_gate101_persistent_backend_process.py -q` — 99 passed
- `npx vitest run src/App.test.tsx src/components/BrandLockup.test.tsx src/pages/SignInPage.test.tsx` — 22 passed

## Still blocking launch

Interactive sign-in, organization binding after callback, live discovery inventory, and a two-organization browser proof were not completed. Readiness still requires `collectors_live` to be 0.
