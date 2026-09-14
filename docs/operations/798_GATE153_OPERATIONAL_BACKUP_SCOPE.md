# 798 — Gate 153: what is backed up, and what is deliberately not

`operational_backup_restore_ready` is true for `controlled_dev_demo`.
`production_backup_ready` is false and nothing in this gate computes it.

## Two harnesses, and they measure different things

```text
scripts/verify_nativeforge_backup_restore.sh            RESULT=SKIP
  Gate 61/65. The INFRASTRUCTURE path: can the provider dump and restore a
  database? Needs a managed instance. Every substantive check is SKIP and has
  been since it was written. Gate 153 did not move it and does not report on it.

scripts/verify_nativeforge_backup_restore_readiness.sh  RESULT=PASS
  Gate 153. The DATA path: can this system export its own controlled dev/demo
  operational state, load it into an isolated database, and still pass the
  Gate 152 replay? Runnable today, with no provider.
```

A provider dump proves bytes survive a round trip. It proves nothing about
whether a digest still hashes, an intent still resolves, or an archived row
still reads — which is what a restore has to be good for.

## The eleven tables that are backed up

Every one is partitioned by `organization_id`, and every one carries `is_demo`
or `fact_status` so a restore can refuse anything that is not a fixture.

```text
nf_tenant_digest_records            151   the digest and the hash that proves it
nf_digest_delivery_intents          142   the intent and its two links
nf_audit_events                      65   the third link in the replay chain
nf_source_watchlist_entries         140   what a tenant asked to watch
nf_tenant_pursuit_suppressions      140   a suppression and its audit trail
nf_awarded_grants                   139   the award a compliance record hangs from
nf_award_requirements               125   what an award obliges
nf_award_requirement_proof_events   126   what was filed against a requirement
nf_award_documents                  127   METADATA only; the table has no body
nf_tenant_beta_profiles             123   how a tenant asked us to behave
nf_tenant_customer_org_bindings     113   which organization a binding names
```

Not all 32 eligible tables. The subject of this block is the evidence chain
Gate 152 replays, so the manifest covers the state a restore must preserve for
that replay to still work.

## The eight that are excluded, each for its own reason

```text
nf_identities              a real address and a provider subject. Fifteen gates
                           have kept both out of logs, artifacts and terminals;
                           a backup is not the place to put them back.

nf_auth_redirect_states    state_hash, pkce_verifier_hash,
                           pkce_verifier_encrypted, code_challenge. No
                           organization_id either, so unscopeable as well as
                           unsafe.

nf_auth_validation_events  auth-flow evidence, no org partition

organizations              includes the real organization. A restore
                           PRECONDITION, not a payload: recreating it from a
                           backup is how the real org would arrive somewhere
                           nobody authorized it.

alembic_version            schema state, not data. Recorded as export metadata
                           and compared on restore.

nf_org_memberships         a membership joins an identity to an organization,
                           and identities are excluded — see below.

nf_raw_source_payloads     source-response evidence; no organization_id

nf_evidence_intake_records no organization_id, so it could not be scoped
```

## The exclusion that is NOT what it looks like

`nf_org_memberships` has a column called `state`. It is excluded anyway, and
**not because of that column**.

A first pass at the manifest matched column *names* against a list of unsafe
words including `state`, and flagged two tables:

```text
nf_org_memberships.state            VARCHAR(32), value 'active'
nf_authority_proof_records.state    VARCHAR(32), Gate 52 lifecycle
```

Both hold a **row lifecycle state**. The same word names an OAuth state, and a
name-matching scan cannot tell the two apart. Excluding membership rows because
a column is called `state` would be the substring-versus-meaning mistake this
campaign has now found about eighteen times — committed by the tool built to
prevent an information leak.

So the manifest classifies **by meaning, with a reason a person wrote per
table**. The name matcher survives only as `review_hint_columns`, documented in
the manifest itself as a review aid and never a gate. A test asserts the
membership exclusion cites identity adjacency and says explicitly that `state`
holds `'active'`.

## What the gate is on export, and what is only a hint

```text
the gate      a VALUE scan of the serialised payload for the shapes that must
              never leave: an address, a provider subject, a bearer token, a
              session cookie, a client secret, a private key, an AWS key

a hint        a column name. `state`, `subject`, `body` and the rest prompt a
              look and decide nothing.
```

An export also requires every row to be a fixture. A row that is neither
`is_demo` nor `demo_fixture` is counted in `skipped_non_fixture_rows` rather
than silently dropped, because a non-fixture row in a controlled export is a
finding.

## What is not applicable rather than blocked

```text
customer data backup    no customer data exists to back up
object store backup     no object store is configured
RPO / RTO in force      documented in doc 400, enforced by nothing
```
