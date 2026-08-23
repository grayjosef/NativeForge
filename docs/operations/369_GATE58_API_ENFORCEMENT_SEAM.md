# 369 — Gate 58B: API enforcement seam

Service: `src/nativeforge/services/api_enforcement_service.py`
Adapter: `src/nativeforge/api/tenant_guard.py`
Tests: `tests/test_gate58_api_tenant_authority_enforcement.py`

## Shape

The seam is **framework-agnostic**: every function returns a decision and never
raises an HTTP error. That keeps it unit-testable without a request, and lets the
FastAPI adapter map a denial onto whichever status code the call site already
returns.

```text
build_request_enforcement_context(...)   -> normalized context
enforce_tenant_access(...)               -> tenant-scoped read/write
enforce_capability(...)                  -> role capability (+ authority gate)
enforce_authority_sensitive_action(...)  -> verified authority required
enforce_seat_invite(...)                 -> seat cap + manage_seats capability
enforce_source_promotion(...)            -> review before monitoring
enforcement_decision_invariant_failures(...)
```

Each returns `{allowed, blocked_reasons, audit_events, ...}`.

## Deny by default

`build_request_enforcement_context` normalizes anything absent or unrecognized
to a **denying** value, not a permissive one:

- missing/blank org → `has_tenant=false` → `missing_tenant`
- missing/blank actor → `missing_actor`
- role not in `ALL_ROLES` → `unknown` → `missing_or_unknown_role`
- membership not in `MEMBERSHIP_STATES`, or not `active` → `membership_not_active`
- absent authority proof → `authority_proof_absent`

Tenant access requires tenant + actor. Capability, authority, seat and source
operations additionally require a known role and an active membership.

## Composition, not duplication

The seam calls the Gate 51-57 contracts rather than restating their rules:

| Seam function | Delegates to |
| --- | --- |
| `enforce_tenant_access` | `evaluate_tenant_scoped_access` → `assert_tenant_access` (Block 31) |
| `enforce_capability` | `evaluate_capability` → `evaluate_authority_sensitive_action` |
| `enforce_authority_sensitive_action` | `evaluate_authority_sensitive_action` |
| `enforce_seat_invite` | `enforce_capability` + `evaluate_seat_invite` |
| `enforce_source_promotion` | `evaluate_source_promotion` |

So a rule change lands in one place. There is no second copy of the seat cap or
the authority state machine.

Two guards are applied at the seam itself rather than inherited:

- `PERMANENTLY_BLOCKED_CAPABILITIES` is checked **before** the role lookup, so a
  production gate is unreachable regardless of context.
- `is_internal_role` blocks authority-sensitive actions outright, so
  `operator_internal` cannot hold customer authority even if handed a verified
  proof belonging to someone else.

## Audit behaviour

Every denial produces at least one modeled audit event. The invariant
`denial_without_audit_event` fails a decision that denies silently — a denial
nobody can see is close to useless in an incident.

Every event carries `persisted: false`, and
`audit_event_claims_persistence` fails any that does not. These are **modeled
events, not an audit log.** Customer persistence is not live.

`tenant_guard` additionally keeps a bounded in-process ring buffer
(`recent_denials()`, 200 max) for tests and operator inspection. That is not
storage either, and is documented as such in the module.

## The adapter preserves behaviour exactly

`tenant_guard` exposes two guards because the pre-existing copies had drifted:

```text
guard_same_org_403  -> 403 "path org_id does not match authenticated org"   (11 modules)
guard_same_org_404  -> 404 "organization not found"                          (3 modules)
```

Both route through the same decision path and record the same audit event; only
the raised response differs. A test asserts both status codes and both detail
strings, so a future tidy-up cannot silently change an API response.

## Invariants

`enforcement_decision_invariant_failures` fails on:

- `allowed_with_blocked_reasons` — allowed while carrying denial reasons
- `denied_without_reason` — denied with no explanation
- `denial_without_audit_event` — denial that produced no event
- `audit_event_claims_persistence` — any event not marked `persisted: false`
