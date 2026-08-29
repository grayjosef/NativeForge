# 639 — Gate 117D: state and PKCE

`src/nativeforge/services/customer_auth_state_pkce_service.py`

## What each one stops

```text
state           the browser that started the flow is the browser that finished
                it. Without it, an attacker completes a flow in your browser
                with their authorization code, and you are logged in as them.

PKCE verifier   the client that started the flow is the client that redeems the
                code. Without it, an intercepted code can be exchanged by
                whoever captured it.
```

Gate 117A found neither existed anywhere in NativeForge: zero occurrences of
`code_verifier`, `code_challenge`, `token_urlsafe` or `urandom`.

### A false positive worth recording

A naive search for `S256` returns four hits. All four are **RS256**, the JWT
signing algorithm (`ALLOWED_ALGORITHMS = frozenset({"RS256"})`). PKCE's S256
code-challenge method shares three characters with it and is a different thing
entirely.

That is the third substring-versus-meaning false positive this campaign has
found, after Gate 116's `api/auth.py` being counted as a dev-header dependant
for explaining why it does not use one.

## The contract

```text
state           32 bytes from secrets.token_urlsafe, minimum 32 characters
verifier        64 bytes, RFC 7636 range 43-128
challenge       BASE64URL(SHA256(ASCII(verifier))), unpadded
method          S256 only; plain is absent from the vocabulary
comparison      hmac.compare_digest
```

`plain` sends the verifier as the challenge, so an interceptor of the
authorization request learns the value that redeems the code. It is refused with
a named reason rather than merely unsupported.

Comparison is constant-time. A state comparison returning early on the first
differing byte leaks the prefix to anyone who can time it, and the whole point
of state is that an attacker cannot produce it.

## Determinism is a test tool and a production hazard

The generator is injectable, and `deterministic_generator_used` travels with
every result. A result produced by an injected generator says so, and an
invariant refuses to call one production-safe. Supplying one with
`production_mode=True` is blocked with its own reason.

## Fixture values can never pass for real ones

`build_fixture_state_pkce` produces values prefixed `nf-demo-fixture-`, short
enough to fail their own entropy checks, and labelled. Those are what reach the
artifacts.

A real generated state has no business in a committed file. It is not a secret,
but a file full of plausible-looking states is a file somebody eventually copies
into a config — and it would make the artifact churn on every regeneration,
which a test would then report as non-determinism.
