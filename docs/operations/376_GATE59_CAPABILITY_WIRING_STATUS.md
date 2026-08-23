# 376 — Gate 59E: Capability wiring status

Short version: **no capability check is wired to a live route, and that is the
correct outcome for this gate.** The reasoning matters more than the result.

## Live-safe routes wired

| Target | Capability check | Status |
| --- | --- | --- |
| read workspace | `view_workspace` | NOT wired |
| read evidence | `view_workspace` | NOT wired |
| read feedback | `view_workspace` | NOT wired |
| package/export preview | `draft_package` | NOT wired |
| role / invite actions | `manage_seats` | modeled adapter only (no live route exists) |
| authority-sensitive final approval | `approve_package_readiness` | NOT wired — deliberately |
| source promotion | `support_review_access` | modeled adapter only (no live route exists) |

What **is** live from this gate: `tenant_guard` now records the resolved identity
on tenant denial events across all 205 org-scoped handlers (doc 375).

## Why capability is not wired

`enforce_capability` needs a **trusted role**. Trusted requires
`verification_trusted AND membership_trusted`, which requires
`oidc_token_signature` verification and a `verified_directory` membership lookup.
Neither exists.

So today every identity resolves to `anonymous`, `demo_operator` or
`oidc_configured_unverified`, and `role_trusted` is `False` for all of them.
Wiring `enforce_capability` into a live route would produce one of two outcomes:

1. **Deny every request**, including `/?view=sc_customer_demo` — breaking the
   live demo, which is a hard rule.
2. **Accept a role from somewhere untrustworthy** (a header, or a hardcoded
   default) so the check appears to pass.

Option 2 is the dangerous one. A capability check keyed on a client-supplied role
is **worse than no check at all**: it produces audit events that look like
enforcement, it would satisfy a reviewer skimming the code, and it is bypassed by
setting a header. Gate 59 refuses it, and `reject_role_assertion_headers` exists
to make an attempt visible rather than silently effective.

## Modeled adapters

`enforce_seat_invite` and `enforce_source_promotion` are exercised through
contract tests (Gate 58, 51 tests) and Gate 59's chain tests. They have no live
routes because no invite endpoints and no discovery scheduler exist. Doc 370
labels them modeled; that label is unchanged.

## Authority-sensitive approval

Explicitly **not** wired to any route, per the Gate 59 brief and for the reason
above: attaching final package approval to an unverified identity is precisely
the fabrication this campaign has avoided throughout. `require_customer_identity`
would reject every current identity anyway.

## What unblocks this

In order:

1. Owner supplies real `OIDC_*` values out-of-band.
2. Implement token verification (JWKS fetch with timeout and fail-closed,
   signature, issuer, audience, expiry) and flip
   `TOKEN_VERIFICATION_IMPLEMENTED`.
3. Add a membership directory so `verified_directory` can be a real source.
4. Then attach `identity_dependency` + `enforce_capability` to read routes
   first — `view_workspace` on workspace/evidence/feedback — because a read
   denial is recoverable and a write denial is not.
5. Only after reads are proven, attach authority-sensitive writes.

Step 4 is the first point at which any capability check can honestly go live.
Attempting it before step 2 would mean inventing trust.

## Honest summary

This gate built the identity seam and proved its rules with 38 tests. It wired
exactly one thing live — identity-aware audit on tenant denial — because that is
the only part that does not depend on trust the system does not yet have.

Reporting "capability enforcement live" here would be false. The chain
`verification → membership → role → capability` is implemented and tested end to
end; it is missing its first link, and that link is owner-blocked.
