# 382 — Gate 60: Production readiness delta

## What is now a real implementation

**RS256 OIDC token verification.** Not a contract, not a model — working code
that verifies signatures against a JWKS and rejects everything it should.

`src/nativeforge/services/oidc_token_verification_service.py`, built on
PyJWT + cryptography, proven by 43 tests including:

- valid token verifies
- wrong key, wrong issuer, wrong audience, expired, future-`nbf`, missing/empty
  `sub`, unknown `kid`, ambiguous missing `kid`, malformed, missing token,
  missing JWKS — all rejected with distinct states
- `alg: none` rejected
- HS256 algorithm confusion rejected (hand-crafted, since PyJWT refuses to
  produce it)
- raw token never present in the result
- a rejected token leaks neither subject nor email

The first link Gate 59 identified is now built:

```text
verified token  ->  verified identity      [BUILT, Gate 60]
                ->  trusted membership     [NOT BUILT]
                ->  trusted role           [NOT BUILT]
                ->  capability             [implemented, not wired]
```

## What is local / test-only

- The RSA keypair is **generated in-process per test session**. No private key
  exists in the repo, on disk, or in output.
- The JWKS is derived from that generated public key.
- **No live Auth0 token has ever been verified.** Local tests prove the code,
  not the integration. `LIVE_AUTH0_TOKEN_PROVEN = False`.
- JWKS network fetch is implemented but **off by default** and never exercised
  against a real endpoint.

## Dependency change

`pyjwt[crypto]>=2.10` added — 4 new packages, **zero existing versions changed**,
`uv lock --check` exits 0. Justified in doc 379: a hand-rolled PKCS#1 v1.5
verifier is the classic source of signature-forgery bugs, and this path will
gate customer authority. `uv.lock` and `pyproject.toml` are staged deliberately
and reported.

## What remains owner-blocked

1. **Real `OIDC_*` credentials** out-of-band — needed for items 1–9 of doc 381.
2. **Production storage approval / provisioning** — blocks the membership
   directory, and therefore blocks everything above token verification.
3. **Independent pen test.**
4. **Live Slack feedback webhook + redaction decision.**

## What remains engineering-blocked

5. **Trusted membership directory** — the new critical path. Doc 381 item 10.
   Gate 51 modelled memberships over caller-supplied state; nothing populates
   them, and `verified_directory` has no producer. Depends on (2).
6. **Role mapping from that directory.** Depends on (5).
7. **Capability enforcement on live routes.** Depends on (5) and (6); reasoning
   for not wiring it yet is unchanged from doc 376.
8. **Customer persistence and audit persistence.** Depends on (2).
9. **Row-level security.** Depends on (2).
10. **Discovery measurement baseline.** Depends on (2) and (7).
11. **Customer pilot runbook.** Depends on all of the above.

## Why controlled customer pilot remains NO_GO

```text
Controlled customer pilot: NO_GO
Production rollout:        NO_GO
Customer login live:       NO
Production storage:        NO
Customer persistence:      NO
Pen-test passed:           NO
Slack live alert:          NOT PROVEN
```

A customer pilot requires that a named person from a specific tribal
organization can log in and be correctly limited to that organization's data.
Gate 60 delivered the ability to confirm **who** someone is. It delivered nothing
about **which organization they may act for** — and that is the half that
prevents a cross-tenant incident.

Concretely, today a perfectly verified live Auth0 token would still yield
`membership_trusted=False` and `may_act_as_customer=False`. That is correct
behaviour, and it is also why the pilot cannot open.

## The critical path moved

Before Gate 60 the answer to "what is the highest-value non-owner-blocked task"
was token verification. That is done. The answer is now the **membership
directory** — but unlike token verification, it cannot be built and tested
without a store, so it sits behind the storage approval.

That makes the storage approval decision the single highest-leverage item for
the owner right now. Everything in the engineering-blocked list traces back to it.

## Honest summary

Gate 60 built the piece it set out to build, proved it against adversarial inputs
with no owner credentials required, and moved the strict-readiness failure from
"no verifier" to "no live proof". It did not move any production gate, and every
artifact it emits says so in a machine-checkable field.
