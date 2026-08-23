# 370 — Gate 58C: Handler wiring

Honest status per target. "Live route enforced" means a real FastAPI route in
this repo runs the check on every request.

## Live routes enforced

**Tenant access on all 205 org-scoped handlers.** All 14 copies of
`same_org` / `_same_org` now delegate to `nativeforge.api.tenant_guard`, which
routes the decision through `api_enforcement_service.enforce_tenant_access` and
records a modeled audit event on denial.

| Target | Route module | Status |
| --- | --- | --- |
| Workspace access | `sprint0_routes`, `tribal_profile_routes` | live route enforced |
| Evidence access | `opportunity_discovery_routes` (12 evidence-pack endpoints via the shared helper), `source_ingestion_routes` | live route enforced |
| Feedback access | `operator_workbench_advisory_routes`, `trust_routes` | live route enforced |
| Package / export access | `form_package_routes`, `pursuit_routes`, `pursuit_brief_routes` | live route enforced |
| Discovery / sources | `opportunity_discovery_routes`, `spark_scoring_routes`, `grant_spark_routes`, `nofo_extraction_routes` | live route enforced |
| Activation | `activation_routes` | live route enforced |
| Guided demo | `stage12_guided_demo_routes` | live route enforced |

Diff footprint: 14 files, +42/−62 lines. No handler signature changed, no status
code changed, no detail string changed. Verified by running the existing API
suite: **108 route/HTTP tests pass**.

What this bought: audit-on-denial across every org-scoped endpoint, and one
implementation instead of fourteen drifting copies.

## Modeled handler enforced (NOT live production enforcement)

These have **no live routes in this repo**, so the seam is exercised through
contract tests rather than HTTP:

| Target | Status | Why not live |
| --- | --- | --- |
| Invite / role actions | modeled handler enforced | no seat/invite routes exist; seats are a Gate 51 contract |
| Authority-sensitive package approval | modeled handler enforced | no authority-proof routes exist; requires identity |
| Source promotion / monitoring approval | modeled handler enforced | promotion is contract-only; no scheduler or fetcher exists |

`enforce_seat_invite`, `enforce_authority_sensitive_action` and
`enforce_source_promotion` are real and tested, but nothing in the HTTP layer
calls them yet. **Do not read these as live production enforcement.**

## Not yet wired

- **Role resolution.** No role exists in request context. `OrgContext` carries
  `org_id` and `org_type` only. Until authentication lands, `enforce_capability`
  cannot be wired to a live route without inventing a role — which would be
  worse than not wiring it.
- **Membership resolution.** No membership lookup exists.
- **Authority proof lookup.** No store to read a proof from.
- **Audit persistence.** Denials are modeled and held in a bounded in-process
  buffer. `audit_repo.append_org_audit_event` exists and is used in two
  discovery routes, but denial events are not written to it in this gate —
  writing security events to a dev SQLite path would misrepresent durability.

## The dependency that blocks the rest

Capability, authority and seat enforcement are all blocked on the same thing:
**there is no authenticated identity.** `isolation_deps.py` resolves org from an
`X-NF-Org-Id` header against a dev allowlist, and its own docstring says
production must replace it with JWT plus an org lookup.

Wiring `enforce_capability` into a live route today would mean either trusting a
client-supplied role header — strictly worse than no check, because it would look
like enforcement — or hardcoding a role. Neither is acceptable, so role-dependent
enforcement stays modeled until Auth0/OIDC Mode B lands.

## What stops the gap reopening

`tests/test_gate58_api_tenant_authority_enforcement.py` adds three structural tests:

1. `test_every_org_scoped_route_handler_reaches_tenant_enforcement` — fails if
   any handler with an org path param does not transitively reach a tenant
   primitive. **Negative-tested:** a deliberately unsafe handler was added to
   `trust_routes.py` and the test failed by name
   (`trust_routes.py::gate58_negative_test_leaky_handler`), then the file was
   restored. A test that has never failed proves nothing.
2. `test_tenant_guard_is_the_single_enforcement_point` — fails if a `same_org`
   helper re-implements the check instead of delegating, preventing copy fifteen.
3. `test_guard_records_denial_and_preserves_status_codes` — pins both the 403
   and 404 response shapes and asserts recorded events carry `persisted: false`.
