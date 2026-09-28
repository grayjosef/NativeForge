# NativeForge Handoff — Mission Control + Microsoft auth precheck

**Date:** 2026-09-28
**Path:** `/home/josefgray/projects/nativeforge`
**Live:** `https://nativeforge.mayhem-nc.dev`
**Protected stash:** `stash@{0}: wip-sprint8-ui-redesign-do-not-commit` — never drop
**Push policy:** commits and pushes allowed after tests; never force-push; never prune

## Operating objective

Finish NativeForge as a product. Demo is a live checkpoint, not a freeze line.
Controlled-customer launch is the finish line. Collectors stay off unless Mayhem authorizes activation. Do not touch real tenants / Carolina Fire Protection Microsoft / Auth0.

## This run

### Microsoft auth

Live production still reports `microsoft.configured=false`. Login `?provider=microsoft` returns HTTP 200 `auth_not_configured` (not a 302 to Google). This is **deployment configuration**, not a code regression. Tests were green because they mock dispatch/callback and never talk to Entra.

Code this run:

- Prefixed Microsoft config must include all five keys, including `NF_OIDC_MICROSOFT_AUDIENCE` (token verify refuses empty audience; borrowing Google's audience would 302 then fail at callback).
- `/api/auth/providers` now lists `missing_env` names only (no values).
- Entra v2 conventional endpoints when discovery is off: `{tenant}/oauth2/v2.0/authorize` not `{issuer}/authorize`.

Exact production callback from code + live origin:

`https://nativeforge.mayhem-nc.dev/api/auth/callback/microsoft`

Human action remaining: create/register the Entra Web redirect URI and paste the five Railway variables, then sign in. Do not paste secrets into chat.

### Mission Control

Workspace now aggregates canonical org state into one read model (`GET /{org_id}/mission-control`). No second task table. Nullable `nf_pursuit_tasks.owner_membership_id` (Alembic **0070**) is the smallest org-scoped assignment. Workflow stages stay derived via `build_pursuit_stages` shared with Pursuit Command Center.

## Tests this run

- `ruff check src tests`: pass
- pytest subset (mission control, command center, Sprint 5, Sprint 20 head pin, Gates 60/118/132, identity presentation, Microsoft dispatch, Gate 130 Entra paths, auth registry): **248 passed**
- Frontend vitest MissionControl + PursuitCommandCenter: **8 passed**
- Stash `stash@{0}` still present

## Remaining launch-critical

- Microsoft Entra app + Railway `NF_OIDC_MICROSOFT_*` — **HUMAN ACTION REQUIRED** (copy/paste in the completion report).
- Discover remains empty until collector activation.
- Pre-existing: `tests/test_sprint0_naming_guard.py::test_nf_sources_avoid_contractforge_table_names`.

## Proposed next

1. Operator: complete Entra + Railway Microsoft variables, then open live sign-in and report the landing page.
2. After deploy, confirm Workspace Mission Control on two demo pursuits.
3. Do not activate collectors without authorization.
