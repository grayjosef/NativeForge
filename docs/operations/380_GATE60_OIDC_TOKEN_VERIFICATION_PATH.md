# 380 — Gate 60: OIDC token verification path

Service: `src/nativeforge/services/oidc_token_verification_service.py`
Tests: `tests/test_gate60_oidc_token_verification.py` (43 tests)

## What is verified now

Local RS256 token verification is **implemented and proven by test**:

| Check | Enforced |
| --- | --- |
| Signature (RS256, RSA public key from JWKS) | yes |
| Algorithm allowlist — `RS256` only | yes |
| `alg: none` rejected | yes |
| HS256 algorithm-confusion rejected | yes |
| `kid` selection; unknown `kid` rejected | yes |
| Ambiguous missing `kid` with multiple keys rejected | yes |
| Issuer match | yes |
| Audience match | yes |
| `exp` required and validated | yes |
| `nbf` validated | yes |
| `iat` sanity (not in the future) | yes |
| `sub` required and non-empty | yes |
| Malformed token rejected | yes |
| Missing token / missing JWKS fail closed | yes |

15 distinct result states, so a caller can audit *why* a token was rejected
without re-parsing it: `verified`, `missing_token`, `malformed_token`,
`unsupported_algorithm`, `missing_kid`, `unknown_kid`, `jwks_unavailable`,
`signature_invalid`, `issuer_invalid`, `audience_invalid`, `expired`,
`not_yet_valid`, `subject_missing`, `verification_error`, `unknown`.

## Implementation notes

**PyJWT + cryptography, not hand-rolled.** Reasoning in doc 379: a hand-written
PKCS#1 v1.5 verifier is the classic place to accidentally accept malformed
padding, and this path will gate customer authority.

**`now` is authoritative.** PyJWT validates time claims against the wall clock
with no injection point, which made the service's `now` parameter meaningless —
caught immediately when the valid-token test failed with `nbf in the future`
because the fixture timestamp sits months ahead of real time. Time validation is
now owned by this service (`verify_exp`/`verify_nbf`/`verify_iat` disabled in
PyJWT, signature/issuer/audience still delegated), so results are deterministic
and the tests will not drift.

**Leeway is 30 seconds by default**, deliberately small: generous leeway
silently extends the life of an expired token. A test asserts a 10-minute-expired
token still fails with 30s leeway.

**Check order.** `exp` is evaluated before `nbf` so an expired token reports
`expired` even when its `nbf` is also historic — the more actionable answer.

**JWKS fetch is opt-in and off by default.** `fetch_jwks(allow_network=False)`
is the default; the verifier never reaches the network implicitly. When enabled
it enforces a hard timeout, caps the response at 1 MB, requires `https://`, and
fails closed on any error. A verification path that silently makes outbound
requests is a surprise in a demo environment and a hang risk in a request path.

## Result hygiene

- The **raw token never appears** in the result. Asserted by test: neither the
  full token nor any long segment of it appears in the serialized output.
- A failed verification returns `subject=None` and `email=None` — a rejected
  token does not leak the identity it claimed.
- `login_live_claimed` and `customer_login_live_claimed` are always `False`.
- `membership_proven`, `role_proven`, `authority_proven` are always `False`, and
  an invariant fails the record if any becomes true.

## Test keypair strategy

The RSA keypair is **generated in-process** by a module-scoped fixture using
`cryptography`. Consequences:

- **No private key is committed** to the repo. None exists on disk.
- No private key material is printed.
- The JWKS document is derived from the generated public key (`n`, `e` as
  base64url).
- A second, unrelated keypair is generated to forge a wrongly-signed token, so
  `signature_invalid` is proven against a real mis-signature rather than
  corrupted bytes.
- **The suite needs no Auth0 credentials.** That was the point of scheduling
  this gate before the owner-blocked items.

The HS256 confusion token is hand-crafted with `hmac`/`hashlib` rather than
`jwt.encode`, because PyJWT refuses to sign HS256 with an asymmetric key. Useful
defence in depth, but the allowlist in this service is what the test exercises.

## What a verified token does NOT establish

This is the load-bearing boundary of the whole gate:

```text
verified signature  ->  we know WHO (sub, optionally email)
                    ->  we do NOT know which organization they may act for
                    ->  we do NOT know their role
                    ->  we do NOT know any authority
```

`identity_from_verified_token` maps a verified result to `oidc_verified` with
`verification_source=oidc_token_signature`. Membership and role must arrive from
a trusted directory: passing `verified_org_id`/`verified_role` with
`membership_source="client_asserted"` leaves both untrusted, and a test asserts
exactly that. `verified_org_id` is nulled when membership is untrusted.

Four tests pin the chain:

- verified token alone -> `membership_trusted=False`, `may_act_as_customer=False`
- verified token + `verified_directory` membership -> membership trusted,
  **role still untrusted** without a role claim
- verified token + trusted membership + role -> `may_act_as_customer=True`, and
  `customer_login_live_claimed` still `False`
- Cloudflare Access -> still `demo_operator`, still not customer login

## What is not live

- **No live Auth0 token has ever been verified.** Local keypair tests prove the
  code, not the integration.
- `login_live` and `customer_login_live` remain false.
- No membership directory exists, so no identity can reach trusted membership in
  production.
- No capability check is wired to a live route (unchanged from Gate 59, doc 376).

See doc 381 for exactly what proof is required before customer login can be
claimed.
