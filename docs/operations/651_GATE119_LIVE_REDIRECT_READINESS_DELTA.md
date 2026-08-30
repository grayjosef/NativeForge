# 651 — Gate 119: readiness delta

What changed, what did not, and the sentence to refuse.

## The sentence to refuse

> "NativeForge can build an authorization URL and store a redirect state, so
> login works."

It can build one when an issuer, a client id and a redirect URI are supplied.
None is. The table exists and holds zero rows. And **eleven of sixteen**
activation gates remain unsatisfied whether or not a URL gets built — the URL is
a string, and the browser is what visits it.

## What moved

```text
                                      before        after
signing key                           a boolean     readiness + a named source
authorization URL builder             none          exists, offline
redirect state storage                contract-only a table, migration 0030
/login state issuance                 constant False a generator that runs
/login PKCE issuance                  constant False a generator that runs
authorization_url_available           = provider_configured   derived from 119D
session verification failure          one answer    missing key vs bad signature
activation gates                      15            16
alembic head                          0029          0030
```

## What did not move

```text
session_signing_key_present            false
signing_key_source                     missing
signing_key_rotation_supported         false
provider_configured                    false
authorization_url_available            false
authorization_url_returned             false
redirect state rows written            0
state_store_scope (running app)        contract_only
network_call_allowed                   false
token_exchange_performed               false
production sessions created            0
customer_auth_live                     false
login_live                             false
customer_persistence_live              false
operational_awarded_tracking_ready     false
operational_digest_ready               false
beta_onboarding_ready                  false
dev header production safe             false
source_monitoring_live                 false
source_coverage_claimed                false
```

## The sixteenth gate

`session_signing_key_ready` joins both `REQUIRED_AUTH_GATES` and
`REQUIRED_LOGIN_GATES`. Login *is* the act of issuing a session, so it needs the
key that signs one.

Missing gates go from ten to eleven. That is not a regression — it is a
requirement that was always true and was not being counted.

The fixture set gained a matching case: `signing_key_is_the_local_dev_fixture`
is identical to `all_gates_pass` but for the key's *source*, and neither login
nor customer auth goes live.

## /login now issues something, and discloses nothing

```text
state_issued              true    a generator ran
pkce_challenge_issued     true    a generator ran
state_value_returned      false
pkce_verifier_returned    false
authorization_url_returned false
state_stored              false   contract_only scope stores nothing
```

Two `GET /api/auth/login` calls return **byte-identical bodies**. That is the
proof, asserted as a test: if any issued value varied into the response, the two
would differ.

## A missing key is not a bad signature

Gate 118's verifier reported one failure where there were two:

```text
signature_unverifiable   no key. Nothing is known about this cookie.
signature_invalid        the check ran, and it failed.
```

The first is an operator problem — set the environment variable. The second is a
tampered cookie or one signed under a rotated key. The dependency contract reads
the distinction and names them separately, and an invariant fires if a result
ever claims both.

## Three defects found and fixed during the gate

**A declared fact standing in for a derived one, again.**
`authorization_url_available` was `bool(provider_configured)` and never checked
the redirect URI at all. Now derived from Gate 119D — which promptly made the
`True` branch unreachable until `issuer` and `client_id` became parameters too.
Third gate running for that lesson.

**A Core table weaker than the migrated one.** The `sa.Table` the repository
uses declared every column and none of the constraints. A test creating a table
from it exercised a *weaker* schema than production, and the assertion that a
never-expiring state is rejected did not raise. The constraints are restated on
the Core table and two tests compare the two definitions by name.

**A substring false positive in my own test.** `'"signing_key"' not in text`
matched `"kind": "signing_key"` — a case label, not a credential. Matched as a
JSON key (`"signing_key":`) instead. Fifth instance of this confusion in the
campaign, first one inside a test rather than a scanner.

## No credential, no session, no row

```text
raw state written to a database         no - sha256 only
raw PKCE verifier written to a database no - sha256 only
state value in a response body          no
signing key in any output               no
client secret in any URL                no
production sessions created             0
real users created                      0
rows in the application database        0
provider contacted                      no
network call made                       no
```

The artifact writer refuses on four independent checks: nested credential field
names, fixture values by content, unredacted URL parameters, and every
configured `OIDC_*` environment value. A test plants a secret in the environment
and asserts it reaches no file; another asserts the URL scanner actually fires
on a live URL, because a scanner that cannot fail proves nothing.

## What the next gate needs

```text
1. NF_SESSION_SIGNING_KEY   from an environment or a secret manager, supplied
                            out-of-band. The committed fixture key may never
                            sign a production session.

2. OIDC_ISSUER              the three the URL builder names, plus a redirect
   OIDC_CLIENT_ID           URI. Presence is detected; no value is read into
   a redirect URI           any output.

3. the database scope       /login must write a row and /callback must read it.
                            The table is built and empty.

4. network_call_allowed     raised deliberately, under review. Nothing raises
                            it today.

5. signing key rotation     not implemented anywhere

6. replace the dev header   15 route modules depend on it

7. owner authorization      NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL
```

Items 1 and 2 are the honest next move and they belong together: a key with no
provider signs nothing, and a provider with no key issues nothing.

Item 3 is now a wiring job rather than a schema one, which is the substantive
difference between this gate and the last.
