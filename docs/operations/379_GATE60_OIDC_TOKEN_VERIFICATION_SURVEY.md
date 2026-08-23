# 379 — Gate 60A: OIDC token verification survey

Status: survey complete. **A dependency was added, and it is justified below.**

## Files inspected

- `src/nativeforge/services/request_identity_service.py` (Gate 59)
- `src/nativeforge/services/oidc_readiness_service.py` (Gate 59)
- `src/nativeforge/api/request_identity.py` (Gate 59)
- `src/nativeforge/api/tenant_guard.py` (Gate 58)
- 25 existing Auth0/OIDC services (preflight, mode detector, config schema,
  identity mapper, login-live promotion gate, callback harness, live validation
  runner, mode B execution/unlock)
- `pyproject.toml`, `uv.lock`

## Token/JWKS helpers found

**None.** Despite 25 Auth0/OIDC service modules, there was no token parsing, no
JWKS handling, no signature verification anywhere in the repo. The existing
services model *configuration presence*, *modes*, *promotion gates* and *claim
mapping* — all of which assume a verified token arrives from somewhere. Nothing
produced one.

`login_live_promotion_gate_service` lists `issuer_jwks_validated` as one of its
10 required gates, confirming the gap was known and deliberately deferred.

## Dependency options found

Before this gate:

```text
jwt            -> not available
jose           -> not available
python_jose    -> not available
authlib        -> not available
joserfc        -> not available
cryptography   -> not available
```

`pyproject.toml` had no crypto or JWT dependency at all. Runtime deps were
fastapi, uvicorn, sqlalchemy, alembic, psycopg, pydantic-settings.

## New dependency added — and why

```text
pyjwt[crypto]>=2.10   ->  pyjwt 2.13.0 + cryptography 50.0.0 (+ cffi, pycparser)
```

The standing instruction is not to add a dependency unless necessary and
justified. This is that case, and I want to be explicit about the reasoning
because a stdlib-only alternative did exist.

**The alternative was viable.** RS256 *verification* is implementable in pure
stdlib: base64url-decode the JWKS `n`/`e`, compute `pow(sig, e, n)`, and compare
against the EMSA-PKCS1-v1_5 encoding of the SHA-256 digest. Roughly 40 lines, no
secret material involved so no timing-side-channel exposure, and test signing
would be `pow(m, d, n)` with a committed test key.

**It was rejected anyway.** PKCS#1 v1.5 verification is precisely the code that
historically accepts malformed padding when hand-rolled — the BERserk class of
bug, where a lenient parse of the padded block lets a forged signature through.
The safe construction (build the expected block, compare the whole thing) is not
hard, but this path will eventually gate real customer authority for tribal
organizations. A vetted, widely-audited implementation is the right foundation
for that, and "we wrote our own RSA verifier" is not a sentence that should
appear in a pen-test report.

PyJWT additionally defends against algorithm confusion in both directions — it
refuses to *sign* HS256 with an asymmetric key, which surfaced during testing.

**Scope of the change** — verified, not assumed:

```text
pyproject.toml:  +1 line
uv.lock:         4 packages ADDED (pyjwt, cryptography, cffi, pycparser)
                 0 existing package versions changed
uv lock --check: exit 0
```

## Existing OIDC contracts reused

Gate 60 composes rather than replaces:

| Existing | Role in Gate 60 |
| --- | --- |
| `oidc_readiness_service` | now reports `token_verification_implemented=True` and gates strict mode on `live_auth0_token_proven` instead |
| `request_identity_service` | gains `identity_from_verified_token` |
| `login_live_promotion_gate_service` | unchanged; still the authority on the 10 gates for `login_live` |
| `auth0_preflight_service` | unchanged; `OIDC_*` env presence |

## Implementation seam

```text
Authorization: Bearer <token>
  -> verify_oidc_token(token, jwks, expected_issuer, expected_audience, now)
       -> structured result with a distinct state per failure
  -> identity_from_verified_token(verification=..., membership_source=...)
       -> request identity (oidc_verified only on a trusted signature)
  -> membership / role still required separately
```

The verifier is a pure function: token in, JWKS in, expected issuer/audience in,
`now` in, structured result out. No network access, no global state, no clock
dependency. That makes it testable with a locally generated keypair and no
owner credentials — which was the point of scheduling this gate now.

## One design decision worth recording

PyJWT validates `exp`/`nbf`/`iat` against the **wall clock** and offers no
injection point for a caller-supplied time. Leaving its time checks enabled made
the service's `now` parameter silently meaningless — caught immediately, because
the tests use a fixed future timestamp and the valid-token case failed with
`nbf in the future`.

Time validation is therefore owned by this service (PyJWT keeps signature,
issuer and audience), so `now` is authoritative and the tests do not drift as
real time passes. See doc 380.
