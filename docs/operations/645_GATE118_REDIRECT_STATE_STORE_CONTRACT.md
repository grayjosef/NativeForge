# 645 — Gate 118D: the redirect state and PKCE store

`src/nativeforge/services/customer_auth_redirect_state_store_service.py`

## Why a store is needed

Gate 117 can generate a state and a verifier, and can validate a pair handed to
it. What it cannot do is *remember* one across the redirect — and the redirect
is the whole point. The browser leaves, visits the provider, and comes back with
a state that has to be compared against one the server issued minutes earlier.

## Single-use, and why that is the interesting rule

```text
expired    the state stopped being usable
consumed   the state was already used, and this is a second attempt
```

They look similar and mean different things. A consumed state presented again is
the signature of somebody resubmitting a captured callback URL, so
`replay_detected` is reported separately from `expired` — a store that called
both "invalid" would lose the one worth alerting on.

Consumption is one-way. A consumed state cannot be un-consumed, and an invariant
refuses any result that permits consuming one.

## Storage scopes

```text
contract_only    this gate. Nothing is stored anywhere.
in_memory_test   a dict, for tests. Dies with the process.
database         does not exist, and this gate adds none.
unknown          refuses.
```

`production_store` is true only for `database`, and an invariant enforces it in
both directions — a non-database scope may not claim it, and a database scope
may not deny it.

An in-memory store is disqualifying for anything real: a state that vanishes on
restart cannot survive a redirect in a deployment with more than one worker.
That is why `in_memory_test` is named for what it is.

## No table was added

Gate 118A concluded one was not required, and the reasoning holds: a
`nf_customer_sessions` or `nf_auth_state` table would be a table nothing writes
to. No session can be created — no provider is configured, no signing key
exists, and the token exchange sits behind a network flag nothing raises.

Alembic head remains **0029**.

## The verifier never reaches an artifact

`pkce_verifier_present` is a boolean. `store_state` accepts a verifier and
records only that it had one. An invariant refuses any result carrying
`state_value`, `state`, `code_verifier`, `pkce_verifier`, `verifier` or
`code_challenge`, and the artifact writer scans for the same names *and* for the
fixture values by content.

That second scan is stricter than it needs to be for values that sign nothing —
and deliberately so. A rule that depended on remembering which values were fake
would eventually meet one that was not.

## A defect this gate found in itself

Both operations returned the same shape, and the invariants judged a successful
*store* by whether *consumption* was allowed. A store legitimately reports
`consume_allowed: False` with no blocked reasons, and that was being flagged as
an unexplained refusal.

An `operation` field now names which call produced a result, and the
refusal invariant applies only to `consume`. A second invariant fires if a store
result ever claims a consumption.
