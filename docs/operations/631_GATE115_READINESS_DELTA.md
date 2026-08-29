# 631 — Gate 115: readiness delta

What changed, what did not, and the sentence to refuse.

## The sentence to refuse

> "NativeForge has a customer auth activation boundary, so authentication is
> ready to turn on."

The first clause is true. The second does not follow and is false. Twelve of
fifteen gates are unsatisfied, and three of them need engineering work rather
than configuration: **there is no login route, no callback route and no session
policy anywhere in the application.**

## What moved

```text
                                        before   after   why
auth activation contract                 none    true    Gate 115B
activation gates measured                11      15      route + contract gates added
gates satisfied                          n/a     3 of 15 all three are contracts
route readiness contract                 none    true    Gate 115C
role mapping contract                    none    true    Gate 115D
dev header shutdown readiness            none    true    Gate 115E
customer_auth_live source                constant one gate
```

## What did not move

```text
customer_auth_live                        false
login_live                                false
provider_configured                       false   seven OIDC env vars absent
secret_present                            false
issuer_jwks_validated                     false   unvalidated, not failed
callback_session_validated                false
org_binding_passed                        false
role_mapping_passed                       false
customer_persistence_live                 false
beta_onboarding_ready                     false
operational_awarded_tracking_ready        false
operational_digest_ready                  false
dev header production safe                false
source_monitoring_live                    false
source_coverage_claimed                   false
```

## One more constant became a measurement

Gate 114 left `customer_auth_live` detected by asking whether a
customer-session module existed. It was one conjunct of seven and could not on
its own make a lane operational, but it was still a module-existence proxy
standing in for a fact nobody could measure yet.

`tenant_beta_readiness_service` had it as a hard-coded `False` — the class Gate
113 removed from `migration_applied`, which would have gone on saying `False`
after auth became real.

Both now read Gate 115's activation gate through a small detector.

### Why a detector rather than the gate directly

The gate reads the application's route table, which imports `nativeforge.main`
and builds the whole application. The capability model is called from three
readiness services and two artifact writers — and `nativeforge.main` imports
those services transitively, so a direct dependency would be a cycle as well as
a cost.

`customer_auth_live_detector_service` short-circuits on the two cheapest
*necessary* conditions — all seven OIDC env vars present, and owner approval —
before paying for the full gate. Either false means auth is not live and no
route table is loaded. That is a short-circuit over necessary conditions, not a
weaker rule: the positive answer still comes from all fifteen gates.

## Secrets

No secret value was printed, stored, committed or echoed. Three independent leak
scans run in the chain — in the preflight service, in the activation gate, and
in the artifact service before anything reaches disk — each searching for any
configured `OIDC_*` value of length ≥ 8.

Two tests plant a value in the environment and assert it reaches neither the
gate output nor any artifact file. A third asserts the scanner reports key
*names* and never values.

The artifact writer raises rather than writing if a value appears. A committed
artifact is the worst place for a client secret: it survives in history after
the file is deleted.

## No live provider call occurred

`run_auth0_preflight` reads environment presence only, with
`jwks_network_check_enabled` defaulting to `False`. The live validation runner
reports `network_calls: False` under an invariant that fails if it is ever true.

No identity provider was contacted. No URL was fetched. No collector ran. No
source was monitored.

## No migration was added

Every fact is observable from environment presence flags, the route table, the
settings and the existing contracts. `nf_identities` and `nf_org_memberships`
already exist for when a real principal appears.

Alembic head remains **0029**.

## What the next gate needs

In order:

```text
1. NativeForge builds the auth routes      login, logout, callback, session,
                                           current-user, plus a session cookie
                                           policy. Engineering work, and the
                                           three gates configuration cannot lift.

2. owner supplies OIDC_* out-of-band       provider_configured, secret_present,
                                           issuer_configured, audience_configured

3. validate a real flow                    issuer_jwks_validated,
                                           callback_session_validated,
                                           invite_binding, org_binding,
                                           role_mapping

4. replace the dev header, then disable it 16 route modules depend on it today

5. owner authorizes activation             NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL
```

Step 1 is the one this gate makes unavoidable. Before Gate 115 it was possible
to read the promotion gates and conclude that customer auth was a configuration
problem. It is not: even with all seven environment variables set and a
validated issuer, there would be nowhere for a customer to log in.

## Claims this gate does not make

```text
customer auth is not live
login is not live
no secret was printed, stored, committed or echoed
no identity provider was called
no network call was made
no real user was created
no real session was created
no customer data was written
no URL was fetched
no collector ran
no scraper was activated
no source was monitored
Cloudflare Access is not customer app auth
the dev org header is not production-safe
customer persistence is not live
Awarded Grants operational tracking is not ready
digest operational is not ready
beta onboarding is not ready
production rollout is not ready
```

## A note on doc 622

Doc 622 (Gate 114B) describes `customer_auth_live` being detected by module
existence, and explains why the obvious alternatives were rejected at the time.
That reasoning was correct for Gate 114 and is now superseded: Gate 115 built
the thing that could not then be measured. The mechanism is documented here and
in doc 627; doc 622 records Gate 114 as it stood.
