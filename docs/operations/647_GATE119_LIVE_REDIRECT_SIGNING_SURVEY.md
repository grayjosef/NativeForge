# 647 — Gate 119A: live redirect flow and signing key survey

Read before implementing. Every answer below was measured, not recalled.

No secret value appears in this document. Where a value would be the answer,
the answer is a boolean and the name of where the value would live.

## The ten questions

```text
1  redirect state DB table exists?              no
2  redirect state repository exists?            no
3  signing key env/config exists?               partly - an env name, no setting
4  provider config env/config exists?           yes, and every key is absent
5  authorization URL buildable offline?         no code exists to build one
6  token exchange no-network by default?        yes, and nothing raises the flag
7  /login can issue state + PKCE offline?       yes - generator exists, unused
8  /callback can consume state safely?          yes for the contract, no store
9  migration required for DB-backed state?      yes, if the store is to persist
10 production session creation still blocked?   yes, on two independent counts
```

## 1–2. No table, no repository

```text
ORM tables declared                23
migration-created tables           28
matching redirect / auth_state / pkce   0
repositories                       18
matching redirect / auth state     activation_state.py only, unrelated
```

`activation_state.py` is Gate 63's operator activation record. It is not a
redirect state store and shares nothing with one but a word.

Gate 118 deliberately added no table, and 645 gives the reason: a table nothing
writes to. That reasoning was correct for Gate 118 and does not survive this
gate — Gate 119D builds an authorization URL, which means `/login` has something
to issue, which means there is something to remember.

## 3. A signing key name exists; a signing key setting does not

```text
NF_SESSION_SIGNING_KEY        named by Gate 118B, read via os.environ
signing_key_present()         False
Settings fields               11, none of them a signing key
```

The eleven are `app_env, app_name, database_url, nf_demo_org_ids,
nf_dev_org_headers` and six `raw_payload_object_store_*` fields. Two of those
six are S3 credentials, which is what Gate 118 found when it searched for
"signing-ish" settings and why 643 records that they are not one.

So the key is read directly from the environment by one service, with no
`Settings` field, no source attribution, no length contract and no rotation
story. That is the gap 119B fills: **presence is known, readiness is not.**

## 4. Provider config exists as a checklist, entirely unpopulated

```text
issuer_url_present         False
client_id_present          False
client_secret_present      False
audience_present           False
callback_url_present       False
allowed_origin_present     False
validation_possible        False
missing_config             7 keys
```

`build_oidc_config_schema()` carries a callback URL and a logout URL as
*local-dev checklist defaults*, `environment_scope: local_dev_checklist`, with
`configured_status: False` and `human_review_required: True`. It has no
`authorization_endpoint` field at all — the schema describes an issuer and a
JWKS URL, not an authorize endpoint.

`client_secret_value` is `None` and `secrets_in_repo` is `False`.

## 5. Nothing can build an authorization URL

Searched every service for the parts:

```text
authorization_endpoint      0 files
response_type               0 files
urlencode                   0 files
quote_plus                  0 files
/authorize                  0 files
urlparse                   11 files   all HTML scrapers, unrelated
urljoin                     3 files   all HTML scrapers, unrelated
```

The eleven `urlparse` and three `urljoin` hits are listing adapters and
extractors resolving relative hrefs on grant pages. **None is auth code.** This
is the fifth substring-versus-meaning check this campaign has had to make, and
the first to come back with a clean zero for the terms that matter.

119D therefore writes the first URL builder in the repository. It builds a
string; it does not fetch one.

## 6. Token exchange is no-network and stays that way

```text
network_call_allowed      False
token_exchange_allowed    False
provider_contacted        False
```

Gate 117E's boundary defaults `network_call_allowed` to False and **nothing in
the codebase raises it**. Gate 119 changes none of this. Building an
authorization URL is string construction; it is the browser that would visit it,
and no browser is involved in a test.

## 7. `/login` could issue state and PKCE today, and does not

`generate_state_and_pkce()` exists (Gate 117D), runs offline on `secrets`, and
derives an S256 challenge with `hashlib`. `/login` currently reports:

```python
"state_issued": False,
"pkce_challenge_issued": False,
```

with a comment saying they are "generated locally at this route once there is
somewhere to send them." There is now somewhere: 119D supplies the URL, 119C
supplies the store. The two `False`s become derived rather than constant.

**Constraint that survives:** issuing state and PKCE must not depend on provider
config. The generator is local. Whether the resulting *URL* can be built does
depend on provider config, and that is a separate boolean.

## 8. `/callback` can consume safely; there is nothing to consume from

`consume_state` distinguishes `expired` from `replay_detected` and refuses to
un-consume. `/callback` already calls it with `state_id=None` and reports the
scope. What it cannot do is find a state, because `contract_only` stores
nothing and `in_memory_test` dies with the process.

The in-memory store also keeps **raw** `state_value` and `code_verifier` in its
dict. That is tolerable for a per-process test double and is not tolerable in a
database, which is why 119C's columns are `state_hash` and
`pkce_verifier_hash`.

## 9. A migration is required, and it is 0030

```text
alembic head          0029_nf_tenant_customer_org_bindings
new revision          0030_nf_auth_redirect_states
```

### Whether organization RLS applies: it does not, and here is why

Every org-scoped table in this repo carries the same policy predicate:

```sql
organization_id = current_setting('app.current_org_id', true)::uuid
AND is_demo = current_setting('app.current_org_is_demo', true)::boolean
```

A redirect state is created **before anybody is authenticated**. At the moment
`/login` issues one there is no identity, no organization, and no
`app.current_org_id` to set — the row exists precisely so that an organization
can be resolved later. Giving it an `organization_id` would mean inventing one
at issue time, and a fabricated RLS anchor is worse than none.

There is precedent, and it is the closest neighbour:

```text
0023_nf_identities        no organization_id, no RLS   pre-organization
0024_nf_org_memberships   no RLS                       defines the mapping
0026_nf_authority_proof_records
0019 0020 0022 0028       operational / ingest tables
```

Seven of twenty-eight tables have no RLS. `nf_identities` is the model to
follow: a verified OIDC subject exists before it belongs to anything.

The row is protected by being **useless**: a state hash and a verifier hash,
single-use, expiring in ten minutes, with no customer data and no reversible
value. `consumed_by_identity_id` is nullable and references `nf_identities(id)`
because it is only knowable after the fact.

Hash-column precedent exists: `0022` stores `hash_or_digest`, `0028` stores
`response_body_hash` and `response_headers_hash`.

## 10. Production sessions remain blocked, on two independent counts

```text
signing key configured        no    -> nothing can be signed
provider configured           no    -> nobody can authenticate
activation gates missing      10 of 15
customer_auth_live            False
login_live                    False
network_call_allowed          False
```

Either one alone is sufficient. Gate 119 removes neither — it makes both
*legible*: 119B says exactly what a signing key would have to satisfy, 119D says
exactly what provider config would have to supply.

## What 119 may and may not conclude

```text
may say   the app can prepare a redirect flow when config and key are present
may say   the state store now has a durable shape
may say   signing readiness is measured rather than assumed

may not say   customer auth is live
may not say   login is live
may not say   a production session can be created
may not say   persistence is live
```

## Implementation constraints carried out of this survey

```text
1  hashes only in the DB - never a raw state, never a raw verifier
2  the URL builder makes no network call and never carries a client secret
3  state and PKCE issuance must not require provider config
4  authorization URL availability must require it
5  local_dev_fixture key source may never permit a production session
6  bridge existing vocabularies - STORAGE_SCOPES, CODE_CHALLENGE_METHOD,
   SIGNING_KEY_ENV - do not restate them
7  every new conjunct must be both derived and injectable, or its permitted
   branch is unreachable (Gates 117 and 118 each learned this once)
8  artifacts carry redacted or fixture URLs only
```
