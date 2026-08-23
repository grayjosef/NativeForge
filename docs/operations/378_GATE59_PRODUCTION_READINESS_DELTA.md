# 378 — Gate 59H: Production readiness delta

## Identity path that exists now

```text
request headers
  -> resolve_request_identity()          available; not attached to routes
  -> request identity contract           7 states, trusted/asserted separated
  -> OrgContext (existing)               plane + org routing, unchanged
  -> tenant_guard                        LIVE, now identity-aware
  -> enforce_capability                  implemented, NOT wired (no trusted role)
```

One thing went live: `tenant_guard` records the resolved identity on tenant
denial events across all 205 org-scoped handlers, instead of the previous
`actor_id = org_id` placeholder.

## Is any customer login live?

**No.** `login_live=false`, `customer_login_live=false`.

Every identity currently resolves to `anonymous`, `demo_operator` or
`oidc_configured_unverified`. `role_trusted` is `False` for all of them.

## Is Cloudflare Access being used as customer login?

**No, and the code now says so structurally.**

Cloudflare Access protects the demo URL. It proves someone cleared an operator
gate on `nf-dev.mayhem-nc.dev`. It carries **no organization membership and no
customer role**.

`identity_from_cloudflare_access` therefore returns `demo_operator`, never
`oidc_verified`. `cloudflare_access` is deliberately absent from
`TRUSTED_VERIFICATION_SOURCES`, and two invariants fail any record that treats it
as customer login or as trusted verification. A test asserts a Cloudflare Access
identity cannot hold customer authority.

This is the conflation most likely to cause a real incident here — an operator
session being mistaken for a tribal organization's authority — so it is blocked
in the type, in the invariants, and in tests, not just in prose.

## Is OIDC configured?

**No.** `readiness_state=oidc_unconfigured`; all four required values absent.

And even with complete config, strict readiness still fails:
`token_verification_path_not_implemented`. Config presence is not verification.

## Is capability enforcement live?

**No.** Implemented and tested end to end, wired to zero live routes. Reasoning
in doc 376: with no trusted role, a live capability check would either deny every
request (breaking the demo) or accept a client-supplied role — which is worse
than no check because it would look like enforcement while being header-spoofable.

## Production boundary — unchanged

```text
Controlled customer pilot: NO_GO
Production rollout:        NO_GO
Customer login live:       NO
Production storage:        NO
Customer persistence:      NO
Pen-test passed:           NO
Slack live alert:          NOT PROVEN
```

## What moved this gate

| Area | Before | After |
| --- | --- | --- |
| Request identity | none | 7-state contract, trusted/asserted separated, 3 derived downgrades |
| Cloudflare Access boundary | prose only | enforced by invariant and test |
| Role spoofing | no concept | recorded, never trusted, 400 on assertion headers |
| Org spoofing | dev header only | untrusted membership nulls `verified_org_id` |
| OIDC readiness | scattered across 25 services | one presence-only report, dual env naming, strict mode fails closed |
| Tenant denial audit | actor = org id | actor = resolved identity |
| `uv.lock` drift | recurring, reverted 4x | root-caused and fixed (doc 377) |

## Still blocked

**Owner-blocked** (cannot be resolved by engineering):

1. Real `OIDC_*` values supplied out-of-band
2. Production storage approval / provisioning
3. Independent pen test
4. Live Slack feedback webhook + redaction decision

**Engineering-blocked** (ready once the above land):

5. Token verification path — JWKS fetch with timeout and fail-closed, signature,
   issuer, audience, expiry; then flip `TOKEN_VERIFICATION_IMPLEMENTED`
6. Membership directory so `verified_directory` becomes a real source
7. Capability enforcement on live read routes, then writes
8. Customer persistence and audit persistence (depends on 2)
9. Row-level security (depends on 2)
10. Discovery measurement baseline (depends on 2, 7)
11. Customer pilot runbook

## Critical path

```text
owner supplies OIDC_*  ->  implement verifier  ->  membership directory
  ->  capability on read routes  ->  capability on writes
```

Item 5 is the highest-value engineering task in the repo right now, and it is the
first one that is **not** owner-blocked once credentials arrive. Everything about
role, authority, seats and audit persistence sits behind it.

## Honest summary

Gate 58 closed tenant enforcement. Gate 59 built the identity seam that role and
authority enforcement need, proved its refusal rules with 38 tests, and wired
live only the part that does not depend on trust the system does not have.

The chain `verification → membership → role → capability` is implemented and
tested end to end. It is missing its first link. That link needs credentials from
the owner, not more code.
