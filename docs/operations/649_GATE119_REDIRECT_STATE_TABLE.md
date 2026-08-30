# 649 — Gate 119C: the redirect state table

```text
alembic/versions/0030_nf_auth_redirect_states.py
src/nativeforge/services/customer_auth_redirect_state_repository_service.py
```

## Why the table exists now and did not at Gate 118

645 declined to add one, and gave a good reason: it would be a table nothing
writes to. That held while `/login` had nowhere to send a browser.

Gate 119D builds an authorization URL. So `/login` has something to issue, and
something issued across a redirect has to be remembered until the browser comes
back — possibly on a different worker, possibly after a restart. The in-memory
store Gate 118 shipped is a per-process dict, which is why it is named
`in_memory_test`.

Alembic head moves **0029 → 0030**.

## Hashes, not values

```text
state_hash            sha256 of the state
pkce_verifier_hash    sha256 of the verifier
code_challenge        stored raw
```

The callback never needs the state's value — it needs to know whether what it
was handed matches what was issued, and a digest answers that exactly. A
database holding live PKCE verifiers is a database whose backups, replicas, and
slow-query logs hold live PKCE verifiers.

`code_challenge` is stored raw because it is already the public half of the
pair: it travelled to the provider in the authorization URL, in a query string,
through the user's browser.

Comparison uses `hmac.compare_digest` on the digests. A timing oracle on a
32-byte random value is close to worthless, and using the constant-time compare
anyway costs nothing and removes the question.

## Why there is no organization_id and no RLS

Every org-scoped table in this database carries the same predicate:

```sql
organization_id = current_setting('app.current_org_id', true)::uuid
AND is_demo = current_setting('app.current_org_is_demo', true)::boolean
```

A redirect state is created **before anybody is authenticated**. When `/login`
issues one there is no identity, no organization, and nothing to put in
`app.current_org_id` — the row exists precisely so that an organization can be
resolved later. Giving it an `organization_id` would mean inventing one at issue
time, and a fabricated RLS anchor is worse than no anchor at all. Gates 109–113
exist to prevent exactly that species of mistake.

There is precedent, and it is the closest neighbour:

```text
0023 nf_identities            no organization_id, no RLS   pre-organization
0024 nf_org_memberships       no RLS                       defines the mapping
0026 nf_authority_proof_records
0019 0020 0022 0028           operational / ingest tables
```

Seven of twenty-eight tables have no RLS. `nf_identities` is the model: a
verified OIDC subject exists before it belongs to anything.

What protects the row instead is that it is **useless**. Two digests, single
use, expiring in at most fifteen minutes, with no customer data, no email, no
token, and nothing reversible. A test asserts the column set contains no
`email`, `name`, `subject`, `organization_id` or `tenant_id`.

`consumed_by_identity_id` references `nf_identities(id)` and is nullable,
because who consumed a state is only knowable after the callback resolves an
identity — and today no callback can.

## What the database enforces rather than trusting the application to

```text
uq_nf_auth_redirect_state_hash            a repeated state is a bug or a replay
ck_nf_auth_redirect_expiry_after_creation a state that never expires is a
                                          credential
ck_nf_auth_redirect_consumer_needs_consumption
                                          an identity cannot have consumed a
                                          state that was never consumed
ck_nf_auth_redirect_challenge_method      S256 only; `plain` defeats PKCE
ck_nf_auth_redirect_storage_scope         Gate 118D's four scopes
```

The expiry check is in the database because an application bug that omitted the
expiry would otherwise produce a row nothing ever invalidates.

## A defect this gate found in itself

The Core `sa.Table` the repository uses declared the columns and **none of the
constraints**. A test that created a table from that definition would exercise a
*weaker* table than production has, and would pass on writes the real database
refuses — including the one asserting that a never-expiring state is rejected,
which did not raise.

The constraints are now restated on the Core table, and a test compares the two
constraint sets by name so they cannot drift apart again. A second test compares
the column sets. A third asserts the migration's `STORAGE_SCOPES` tuple matches
the service's frozenset exactly, because a CHECK constraint cannot import
Python.

## Expired and replayed are different answers

```text
expired    the state stopped being usable
replayed   the state was already used, and this is a second attempt
```

A consumed state presented again is the signature of somebody resubmitting a
captured callback URL. `replay_detected` is reported separately *and* written to
the row, so the evidence outlives the request. A store that called both
"invalid" would lose the one worth waking somebody up for.

Consumption is one-way: nothing clears `consumed_at`, and an invariant refuses
any result permitting the consumption of a consumed state.

## No ORM model, and no rows

`nf_auth_redirect_states` is reached through SQLAlchemy Core, matching
`nf_identities`, `nf_raw_source_payloads` and `nf_tenant_customer_org_bindings`
— none of the three has an ORM model either. A model would be a mapped class
nothing constructs.

The `database` scope works and is exercised against a real database in tests. It
is reached by nothing in the running application: `/login` still refuses while
no provider is configured, and this gate configures none.

```text
rows written in the application database    0
```
