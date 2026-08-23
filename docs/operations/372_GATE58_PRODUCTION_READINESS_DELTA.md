# 372 — Gate 58F: Production readiness delta

## What is now runtime-enforced

**Tenant isolation, on every org-scoped API route.** All 205 org-scoped handlers
(of 208 total) reach a tenant enforcement primitive on every request, now through
a single implementation with audit-on-denial.

Also live:

- plane isolation (demo vs real) via FastAPI dependencies
- both cross-org response shapes preserved (403 on eleven modules, 404 on three)
- a modeled audit event on every tenant denial
- three structural tests that fail if a future handler skips enforcement,
  if a `same_org` copy re-appears, or if either response shape changes

**Correction to doc 366.** The Gate 57 threat model said "none of these
contracts is enforced at an API or storage boundary yet," which read as though
tenant isolation were unenforced. It was not. Tenant isolation was already
enforced on all 205 handlers before this gate; what was missing was a single
enforcement point, audit on denial, and an anti-bypass guard. Doc 368 records
the corrected measurement and the two scanner defects that briefly produced a
false "22 unenforced handlers" reading.

## What is still contract-only

| Capability | State | Blocker |
| --- | --- | --- |
| Role capability (RBAC matrix) | contract + seam, no live route | no role in request context |
| Authority proof enforcement | contract + seam, no live route | no identity, no proof store |
| Seat cap / invites | contract + seam, no live route | no invite routes, no identity |
| Source promotion review | contract + seam, no live route | no scheduler or fetcher |
| Audit persistence | modeled, `persisted: false` | no approved store |

All five are wired into `api_enforcement_service` and covered by tests. None is
called from an HTTP route, and doc 370 labels each as *modeled*, not live.

## The single blocker behind most of the above

**There is no authenticated identity.** `isolation_deps.py` resolves org from an
`X-NF-Org-Id` header against a dev allowlist; its own docstring says production
must replace it with JWT plus an org lookup.

Wiring capability or authority checks to a live route today would require either
trusting a client-supplied role header — strictly worse than no check, because it
would *look* like enforcement — or hardcoding a role. Neither is acceptable. This
is why role-dependent enforcement stays modeled rather than being wired to
something untrustworthy.

## Owner-blocked

Cannot be resolved by engineering alone:

1. **Real Auth0/OIDC customer login** — needs real `OIDC_*` inputs out-of-band.
2. **Production storage approval / provisioning** — needs a storage decision.
3. **Independent pen test** — needs an engagement.
4. **Live Slack feedback proof** — needs a webhook and a redaction decision.

## Engineering-blocked

Ready to build once the above land:

5. **Customer persistence** — depends on (2).
6. **API-layer enforcement coverage beyond adapters** — capability, authority,
   seat and source-promotion checks wired to live routes; depends on (1).
7. **Row-level security or equivalent storage isolation** — depends on (2), so a
   bug in (6) is not a cross-tenant breach.
8. **Source discovery measurement baseline** — Gate 56 `achieved` stays false
   until a real baseline is measured; depends on (2) and (6).
9. **Customer pilot runbook** — depends on all of the above.

## Controlled customer pilot delta

Unchanged by this gate:

```text
Controlled customer pilot: NO_GO
Production rollout:        NO_GO
Customer login live:       NO
Production storage:        NO
Customer persistence:      NO
Pen-test passed:           NO
Slack live alert:          NOT PROVEN
```

## What must be proven before controlled customer pilot

1. A real customer can log in, and the identity is trustworthy.
2. Two organizations provably cannot see each other's data **at the storage
   layer**, not only at the API layer.
3. Authority-sensitive actions are blocked for unverified users on live routes,
   not only in contract tests.
4. Audit events are durably written, not modeled.
5. An independent pen test covers 1-4.
6. Feedback alerts cannot leak one tenant's data into a channel outside the
   product.
7. A discovery baseline exists so quality claims are measured rather than
   asserted.

## Honest summary

This gate closed the smaller half of the model/enforcement gap and, more
usefully, made the closed half **hard to reopen**: one enforcement point instead
of fourteen drifting copies, audit on every denial, and a negative-tested
invariant that fails by name when a handler skips the check.

The larger half — role, authority, seats, source promotion — remains
contract-only and is gated on authentication, not on more modelling. Building
more contracts now would widen the gap this gate exists to narrow.
