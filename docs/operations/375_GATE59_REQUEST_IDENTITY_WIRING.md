# 375 — Gate 59D: Request identity wiring

Contract: `src/nativeforge/services/request_identity_service.py`
Adapter: `src/nativeforge/api/request_identity.py`
Guard integration: `src/nativeforge/api/tenant_guard.py`

## Identity states

`anonymous`, `demo_operator`, `oidc_unconfigured`,
`oidc_configured_unverified`, `oidc_verified`, `invalid`, `unknown`.

Only `oidc_verified` can lead to customer authority.
`DENY_CUSTOMER_ACTION_STATES` is *derived* as everything else, so a state added
later denies by default rather than silently permitting.

## Trusted vs asserted — kept structurally separate

The contract has two parallel sets of fields, and nothing can promote one to the
other:

| Asserted (recorded, never trusted) | Trusted (requires a trusted source) |
| --- | --- |
| `asserted_org_claims` | `verified_org_id` |
| `asserted_role_claims` | `verified_role` |
| `client_asserted_role_trusted` — always `False` | `role_trusted` |
| `client_asserted_org_trusted` — always `False` | `membership_trusted` |

Trust requires a source from an allowlist:

- `TRUSTED_VERIFICATION_SOURCES = {oidc_token_signature}`
- `TRUSTED_MEMBERSHIP_SOURCES = {verified_directory}`

`cloudflare_access`, `dev_header` and `client_asserted` are **not** in either
set. `verified_org_id` is nulled out when membership is untrusted, so an org id
from an untrusted source cannot survive into a field whose name implies it was
verified.

Three derived downgrades run regardless of what the caller passed:

1. `oidc_verified` + untrusted verification source → `oidc_configured_unverified`
2. `oidc_verified` / `oidc_configured_unverified` + OIDC not configured → `oidc_unconfigured`
3. `role_trusted` requires **both** trusted verification and trusted membership

## Header trust table

| Header | Read as | Trust |
| --- | --- | --- |
| `Cf-Access-Authenticated-User-Email` | `demo_operator` identity | operator gate only. No org, no role, **not customer login** |
| `X-NF-Org-Id` | demo/dev routing (existing `isolation_deps`) | never membership, authority or role proof |
| `X-NF-Role`, `X-NF-Roles`, `X-NF-Capability` | `asserted_role_claims` | never trusted; `reject_role_assertion_headers` returns 400 |
| `Authorization: Bearer …` | presence only | **not verified** — no verification path exists |

A bearer token raises the state to `oidc_configured_unverified` at most, and only
when OIDC is configured. It never reaches `oidc_verified`.

## Role spoofing

Blocked two ways. The resolver records the asserted role and leaves
`role_trusted=False`, and `evaluate_customer_action` adds an explicit
`client_asserted_role_ignored` reason so the attempt is visible rather than
quietly dropped. `reject_role_assertion_headers` additionally returns **400** for
any of the three headers — rejecting is preferable to ignoring, because ignoring
lets a caller believe it worked.

## Org spoofing

`X-NF-Org-Id` keeps its existing role as demo/dev routing input and is *not read
by the identity resolver at all*. A client-asserted org yields
`membership_trusted=False` and `verified_org_id=None`.

## Live route wiring

**`tenant_guard` is now identity-aware — this is the one live change.**

Before, the guard recorded `actor_id = str(ctx.org_id)`: a denial event named the
organization, not the actor. It now reads a request-scoped identity when one has
been resolved and records the subject or email instead.

Implementation is a `contextvars.ContextVar` set by `identity_dependency`.
Threading identity through 205 handler call sites would have been a large risky
diff; a contextvar lets the guard enrich its event when identity is present and
fall back to the previous behaviour when it is not. **Nothing depends on it being
set** — the import is local and wrapped, so the guard works unchanged if identity
was never resolved. Gate 58's 51 tests still pass.

## Status per component

| Component | Status |
| --- | --- |
| `resolve_request_identity` | available as a FastAPI dependency; **not attached** to existing routes |
| `identity_dependency` | available; publishes identity to the guard |
| `tenant_guard` identity enrichment | **live route wired** — active on all 205 org-scoped handlers |
| `reject_role_assertion_headers` | available; **not attached** to existing routes |
| `require_customer_identity` | **dry-run only** — see below |

## Why `require_customer_identity` is not attached anywhere

With no verifier, every identity resolves to `anonymous`, `demo_operator` or
`oidc_configured_unverified`. Attaching a customer-identity requirement to a live
route would deny **every** request, including the demo. The function exists,
is tested, and is documented as unattached.

The alternative — accepting a role header so the check appears to work — would be
worse than no check, because it would look like enforcement while being trivially
spoofable. That is the specific mistake this gate refuses to make.

## Blocked on real OIDC config

Everything above the tenant guard needs: owner-supplied `OIDC_*` values, an
implemented token verification path, and a membership directory to resolve
`verified_directory`. Two of the three are owner-blocked.
