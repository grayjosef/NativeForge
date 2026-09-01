# 694 — Gate 131: OAuth state persistence and session minting survey

Measured before anything was implemented.

## First, the brief's file list

Five of the modules named in the survey list do not exist:

```text
customer_session_state_service                ABSENT
live_redirect_signing_boundary_service        ABSENT
oidc_claim_organization_resolution_service    ABSENT
customer_auth_verified_binder_service         ABSENT
```

The real modules with those responsibilities:

```text
customer_session_format_service            session encoding and signing
customer_session_verifier_service          session decoding and verification
customer_session_cookie_policy_service     cookie flags
customer_auth_live_redirect_*              the Gate 119 redirect boundary
oidc_organization_id_resolution_service    claim -> organization_id
verified_binder_authorization_service      who may bind
verified_binding_workflow_service          the binding workflow
```

Worth recording rather than quietly substituting: Gates 124 and 126 each lost
time to a capability probe naming a module nobody built, and a brief that names
one is the same hazard pointed at a person.

## The short answer

Three of the four things this gate needs already exist and are complete. One
does not exist at all, and one is prevented by the schema.

```text
durable state repository   COMPLETE - real inserts, hashed values, expiry,
                           one-time consumption, replay detection
ID token validation        COMPLETE - jwt/PyJWK, real signature verification
session encode/verify      COMPLETE
token exchange             DOES NOT EXIST - only a boundary evaluator
PKCE verifier retrieval    IMPOSSIBLE with the current schema
```

## Current login route behaviour

`GET /api/auth/login` generates a real state and a real PKCE pair — local work,
no provider involved — and then:

```python
stored = store_state(..., storage_scope=STATE_STORE_SCOPE)   # "contract_only"
```

`contract_only` is a scope that stores nothing and says so
(`contract_only_scope_stores_nothing`). The route returns a structured refusal
and `authorization_redirect_issued` is a hardcoded `False`.

Since Gate 130 the route reads the configured callback and discovers Google's
real authorization endpoint, so `provider_configured: True` and
`authorization_url_available: True`. It builds a correct URL and returns it to
nobody.

## Current callback route behaviour

`GET /api/auth/callback` returns a controlled envelope,
`callback_validation_not_passed`, with every downstream gate false:

```text
state_validated            False
pkce_verified              False
token_exchange_allowed     False
token_exchange_performed   False
session_created            False
organization_id_resolved   False
membership_verified        False
```

It never had a state to validate, because nothing stored one.

## Where state should be persisted

`nf_auth_redirect_states`, migration 0030, present in the runtime database at
head 0035. `customer_auth_redirect_state_repository_service` owns it and is
**complete**:

```text
persist_redirect_state(connection=...)   sa.insert, real row
consume_redirect_state(connection=...)   digest lookup, expiry, replay,
                                         one-time consumption in the same call
hash_secret_value()                      values stored as digests
```

It refuses the database scope without a connection, by name. The consume path
marks `consumed_at` in the same call that finds the row, so there is no window
in which a caller holds a valid unconsumed match, and a second presentation
sets `replay_detected`.

This is good code. Nothing calls it except a demo fixture.

## Why the route does not use it

Two reasons, both deliberate.

**The route imports the wrong service.** It takes `TABLE_NAME` from the
repository and `store_state`/`consume_state` from
`customer_auth_redirect_state_store_service`, which is the *contract* — a
different module that models the decision and keeps nothing. Two services, one
name-shaped like the other, and the route wired to the one that stores nothing.

**The route has no database connection.** Sixteen route modules obtain one
through `deps_db`; these five deliberately do not, because they are the
eventual replacement for the dev header and must not consume the RLS context it
sets. So persisting state needs a connection the route was designed not to
have.

Separately, `customer_auth_redirect_state_store_service.store_state` accepts
`database` as a valid scope, implements no branch for it, and returns
`stored: False` with **no blocked reason**. A silent no-op for the one scope
that would matter.

## The blocker that stops this gate short

PKCE cannot be completed with the current schema.

```python
sa.Column("pkce_verifier_hash", sa.Text(), nullable=False)
```

The verifier is stored as a SHA-256 digest. PKCE requires the client to send
the **raw** `code_verifier` to the token endpoint, where the provider hashes it
and compares against the `code_challenge` it already holds. A digest does not
reverse, so the raw verifier is unrecoverable by design.

That design is defensible for a table that only ever *validated* state. It is
fatal for a table that must also *complete* an exchange.

```text
code_challenge        stored, and public - it is sent to Google in the auth URL
pkce_verifier_hash    stored, and useless for exchange
raw code_verifier     generated at /login, never persisted, lost on return
```

Three ways out:

```text
1  a new column holding the verifier retrievably, encrypted at rest with the
   session signing key. Needs migration 0036.
2  an in-memory cache keyed by state. Defeats the point of durable state - it
   does not survive a restart or a second worker, which is exactly what
   `PRODUCTION_SCOPES = {"database"}` exists to guarantee.
3  drop PKCE. Refused: the table CHECK constrains code_challenge_method to
   S256, and dropping PKCE means an intercepted code is exchangeable by
   whoever intercepted it.
```

Option 1 is correct and is a schema change.

## Token exchange does not exist

`customer_auth_token_exchange_boundary_service` is an evaluator, not a client.
It decides whether an exchange would be permitted and performs no HTTP. There
is no code anywhere that posts to a token endpoint.

Building it means new network egress carrying the client secret, which must be
registered at Gate 94's chokepoint alongside the JWKS retrieval and the
discovery document.

## What does exist and works

```text
oidc_token_verification_service   real jwt/PyJWK verification, JWKS selection
                                  by kid, issuer and audience checks
customer_session_format_service   session encoding, HMAC signing, signing key
                                  read from the environment (ready: True)
customer_session_verifier_service session decode and signature verification
customer_session_cookie_policy_service   cookie flags
```

Identity validation and session mechanics are built. What is missing between
them is the exchange that turns a code into an ID token.

## Org binding after identity

`oidc_organization_id_resolution_service` resolves a verified claim to an
`organization_id` and requires a membership record — Gate 112's contract, with
both halves. `nf_tenant_customer_org_bindings` exists at migration 0029.
Nothing has ever run it against a real identity, because no real identity has
existed.

## Exact remaining blockers

```text
1  the login route persists nothing            wiring, plus a DB connection the
                                               route deliberately does not take
2  the login route refuses to redirect         one hardcoded False
3  the PKCE verifier is unrecoverable          migration 0036
4  no token exchange client exists             new egress, chokepoint-registered
5  session minting is not wired to a callback  wiring, once 3 and 4 land
6  no org binding has ever been attempted      Gate 132
```

Items 1 and 2 are this gate's work and are safe. Item 3 is a schema change with
a clear design. Item 4 is the one that carries real risk: a client secret over
the network, on a route reachable from the public internet.

## What this gate will and will not claim

`customer_auth_live` and `login_live` stay false unless a browser proves
otherwise. A session that no `current-user` call has verified is not a login,
and an identity without an organization binding is not a customer.
