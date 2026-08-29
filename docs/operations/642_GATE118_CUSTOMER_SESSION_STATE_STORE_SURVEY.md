# 642 — Gate 118A: customer session and state store survey

Written before any implementation. Every claim was reproduced by reading the
services, the models, the migrations, the repositories and the settings.

**No secret, session, state or PKCE value appears in this document, and none was
printed while producing it.**

## Does a session format exist?

No. Searched every service module:

```text
session_format    0        session_id        0
session_value     0        session_token     0
signing_key       0        cookie_secret     0
SESSION_SIGNING   0        itsdangerous      0
jwt.encode        0
```

## Does anything sign or verify a session?

No. The only `hmac` and `compare_digest` in the repository are in Gate 117D's
state/PKCE service, comparing a state against a returned state.

Two search results need correcting rather than reporting:

* **`sign` returns 212 hits.** All noise — "design", "sign-off", "signal",
  "assign" across the activation-packet domain. Not one is a signature.
* **`SECRET_KEY` returns 5 hits.** Every one is a *redaction regex*:

  ```python
  # gate27_owner_unlock_packet_service.py
  _SECRET_KEY_RE = re.compile(...)
  if _SECRET_KEY_RE.search(str(k)):   # suppress this key
  ```

  Services scanning *for* secret-shaped keys in order to suppress them. The
  opposite of a signing key.

That is the fourth substring-versus-meaning false positive this campaign has
recorded, after Gate 117's `S256`/`RS256` and Gate 116's `api/auth.py` being
counted as a dev-header dependant for documenting why it does not use one.

## Does a state or PKCE store exist?

No.

```text
state_store     0    store_state     0    retrieve_state  0
single_use      0    nonce_store     0    verifier_store  0
```

`consume` returns 70 hits, all from the activation-packet domain — "consumer",
"consumed capacity". `replay` returns 5, one of which is Gate 117D's docstring
explaining what state defends against.

Gate 117 can generate a state and a verifier and can validate a pair handed to
it. What it cannot do is remember one across a redirect, which is the whole
purpose of a store.

## Is there a table or repository?

No.

```text
tables in db/models.py                     23
tables created by migrations               28
session/state-ish table names              nf_activation_state
                                           nf_authority_proof_records
repositories                               18
session/state-ish repository names         activation_state.py
```

Both near-misses are unrelated:

```text
nf_activation_state          "M7: per-workspace durable activation flags
                             (default OFF)" - product feature toggles
nf_authority_proof_records   Gate 52 authority proof lifecycle
```

Neither has anything to do with authentication.

## Is there signing key configuration?

No. `Settings` exposes eleven fields:

```text
app_env  app_name  database_url  nf_demo_org_ids  nf_dev_org_headers
raw_payload_object_store_access_key_id      raw_payload_object_store_bucket
raw_payload_object_store_endpoint           raw_payload_object_store_region
raw_payload_object_store_force_path_style
raw_payload_object_store_secret_access_key
```

The two that match a naive "secret or key" search are S3 object-store
credentials for the raw payload store. There is no session signing key, and no
setting that could be mistaken for one.

## Is there an expiration policy?

Partly. Gate 116B's cookie policy already decides the *cookie's* lifetime:

```text
cookie_name           nf_session
max_age_seconds       28800  (8 hours, ceiling 604800)
rotation_required     true
logout_clears_cookie  true
```

What does not exist is an expiry *inside* the session value. A cookie `Max-Age`
is a request to the browser; a browser that ignores it, or an attacker replaying
a captured cookie, is unaffected. The session value needs its own `expires_at`,
and validating it is server-side work.

## Is there logout invalidation?

Only cookie clearing. `/api/auth/logout` calls `delete_cookie` with an expiry
and an empty value. Nothing is marked invalid server-side, because there is
nothing to mark.

## Can the callback retrieve stored state and PKCE?

No. There is nowhere to retrieve them from.

## How the dependency decides validity today

```python
# api/auth.py::_session_decision
present = bool(cookie)

# No session format exists, so no cookie can be valid. Stated as a
# derivation rather than a constant so it moves when one does.
valid = False
principal_resolved = False
```

Gate 117 wrote that comment expecting this gate. `session_cookie_valid` is a
derived `False` with nothing behind the derivation, and this gate supplies the
something.

The dependency contract already accepts `session_cookie_valid` and
`principal_resolved` as parameters, so a verifier result can be threaded in
without changing its shape.

## Does this gate need a migration?

**No, and it should not add one.**

A `nf_customer_sessions` table would be a table nothing writes to. No session
can be created, because:

```text
provider_configured      false
secret_present           false
customer_auth_live       false
token_exchange_allowed   false (network off)
```

The same reasoning Gate 114 applied to the persistence spine holds here: adding
the store would be building the thing the contract exists to gate. The brief
offers `contract_only` and `in_memory_test` as storage scopes precisely so this
gate can be honest about which it is.

`production_store` stays `False`, and it stays false because it is derived from
whether a database-backed store exists — not because a constant says so.

Alembic head remains **0029**.

## Answers to the specific questions

```text
session format exists?              no
session signing service exists?     no
session verifier exists?            no
state store exists?                 no
PKCE verifier store exists?         no
DB table for sessions/state?        no (two unrelated near-misses)
repository for sessions/state?      no
in-memory/test-only storage?        no
cookie signing secret config?       no
session expiration policy?          cookie-level only; nothing inside the value
logout invalidation?                cookie clearing only
callback can retrieve state/PKCE?   no
migration required?                 no - contract-only, with an in-memory scope
```

## What this gate must not do

```text
create a production session   signing key absent, auth not live
create a user                 no row, anywhere
call a provider               unchanged from Gate 117
commit a session value        artifacts carry the contract, not credentials
commit a state or verifier    fixture values only, labelled, entropy-failing
add a table                   nothing could write to it
claim auth or login live      ten activation gates unsatisfied
```
