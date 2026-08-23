# 374 — Gate 59C: OIDC Mode B readiness

Service: `src/nativeforge/services/oidc_readiness_service.py`
Script: `scripts/verify_nativeforge_oidc_mode_b.sh`
Tests: `tests/test_gate59_request_identity_oidc.py`

## What this reports

Whether real OIDC token verification is **possible**, not whether login works.
It reads environment variable *presence* only, performs no network I/O, and can
never set `login_live`.

## Env var naming

The repo standardised on `OIDC_*` — 19 references across `src/` and `scripts/`,
consumed by `auth0_preflight_service` and `oidc_config_schema_service`. The
Gate 59 brief named `NATIVEFORGE_OIDC_*`.

Both are accepted. `OIDC_*` is canonical and checked first;
`NATIVEFORGE_OIDC_*` is an alias. `config_source_keys` reports which spelling
satisfied each requirement, so whoever supplies the real credentials can see
exactly what was picked up.

| Logical | Canonical | Alias |
| --- | --- | --- |
| issuer | `OIDC_ISSUER` | `NATIVEFORGE_OIDC_ISSUER` |
| audience | `OIDC_AUDIENCE` | `NATIVEFORGE_OIDC_AUDIENCE` |
| jwks_url | `OIDC_JWKS_URL` | `NATIVEFORGE_OIDC_JWKS_URL` |
| client_id | `OIDC_CLIENT_ID` | `NATIVEFORGE_OIDC_CLIENT_ID` |
| client_secret | `OIDC_CLIENT_SECRET` | `NATIVEFORGE_OIDC_CLIENT_SECRET` |

Required before verification could be attempted: issuer, audience, jwks_url,
client_id. `client_secret` presence is reported but is not part of the
verification-possible calculation (a public client does not need one).

## Readiness states

`oidc_unconfigured` → `oidc_partially_configured` → `oidc_configured_unverified`
→ `oidc_verified`

`oidc_verified` is **unreachable today** and an invariant fails the record if it
ever appears, because no verifier exists to produce it.

## The rule that matters most

```python
TOKEN_VERIFICATION_IMPLEMENTED = False
verification_possible = config_complete and TOKEN_VERIFICATION_IMPLEMENTED
```

**Config presence is not verification.** An earlier draft of this gate had strict
mode passing once all four config values were present. That was wrong and was
corrected: "ready for live login" has to mean a token can actually be verified,
not that four strings exist in the environment. Strict mode therefore fails even
with complete config, and says why:
`blocked_reason=token_verification_path_not_implemented`.

When someone implements the verifier, they flip one flag.

## Modes

| Mode | Missing config | Complete config, no verifier |
| --- | --- | --- |
| default (demo) | `RESULT=PASS`, state `oidc_unconfigured` | `RESULT=PASS`, state `oidc_configured_unverified` |
| `--strict` | `RESULT=FAIL`, exit 1 | `RESULT=FAIL`, exit 1 |

Default must pass with no config: the demo runs without OIDC and must keep
running. `--strict` (or `NF_OIDC_STRICT=1`) is the live-readiness gate.

Verified behaviour:

```text
no config,   default  -> RESULT=PASS  exit 0
no config,   --strict -> RESULT=FAIL  exit 1
full config, --strict -> RESULT=FAIL  exit 1  (token_verification_path_not_implemented)
```

## Secret safety

Verified by negative test, not assumed. The script was run with sentinel values
in all five env vars and the output grepped for the sentinel:

```text
PASS: no env var value appears in output
```

The record carries `secret_values_read=false`, `network_access_attempted=false`,
`jwks_fetched=false`, and invariants fail if any becomes true. `config_present`
is asserted to contain booleans only, and a test asserts the config *values* do
not appear anywhere in the serialized record.

## What is NOT claimed

- `login_live_claimed`: false
- `customer_login_live_claimed`: false
- `mode_b_executed`: false
- no JWKS fetched, no token parsed, no signature checked

Login live requires the 10 gates in `login_live_promotion_gate_service`, of
which this reports on the configuration precondition only.

## To move this forward

Owner supplies real `OIDC_*` values out-of-band, then someone implements the
token verification path (JWKS fetch with timeout and fail-closed, signature
check, issuer/audience validation, expiry) and flips
`TOKEN_VERIFICATION_IMPLEMENTED`. Until both happen, `--strict` correctly fails.
