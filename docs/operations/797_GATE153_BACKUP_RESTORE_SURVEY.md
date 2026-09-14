# 797 — Gate 153: the backup and restore gap, surveyed

Read-only. Nothing was exported, restored, or written.

## A harness already exists, and it is a different harness

`scripts/verify_nativeforge_backup_restore.sh` was built for Gate 61/65. It is a
`pg_dump` / `pg_restore` proof for a managed PostgreSQL instance, with real
safety rules — the URL is never echoed, and a restore refuses to target the
source database.

It returns `RESULT=SKIP` today and has since it was written:

```text
database_url_present            SKIP  unset outside a provisioned environment
backup_automation_configured    SKIP  no backup automation exists
pitr_enabled                    SKIP  no provider
restore_test_executed           SKIP  no restore has ever been executed
restore_artifact_recorded       SKIP  no restore artifact exists
```

That is honest and it is stuck. Nothing in it can run until somebody provisions
a managed instance, which is a procurement decision rather than engineering.

**So Gate 153 must not rebuild it, and must not claim to have unblocked it.**

```text
Gate 61/65 harness   the INFRASTRUCTURE path: can the provider dump and
                     restore a database? Unrunnable, SKIP, waiting on hardware.

Gate 153             the DATA path: can this system export its own controlled
                     dev/demo operational state, load it into an isolated
                     database, and still pass the Gate 152 replay? Runnable
                     today, on the dev SQLite database, with no provider.
```

The second is worth having on its own. A provider dump proves bytes survive a
round trip; it proves nothing about whether a digest still hashes, an intent
still resolves, or an archived row still reads. That is what a restore has to be
good for.

## The tables, measured

41 tables. Classified by whether they are org-partitioned and whether any column
could carry something that must never be exported:

```text
org-partitioned, no unsafe column      32
carrying an unsafe column               3
no organization_id at all               6
```

## My own classifier reproduced this campaign's favourite defect

A first pass matched column *names* against a list of unsafe words and flagged
three tables. Two of the three were false positives:

```text
nf_org_memberships.state            VARCHAR(32), value 'active'
nf_authority_proof_records.state    VARCHAR(32), Gate 52 lifecycle
```

Both are **row lifecycle states**. The word `state` also names an OAuth state,
and a name-matching scan cannot tell them apart. Excluding membership rows from
a backup because a column is called `state` would be the substring-versus-meaning
mistake this campaign has now hit about eighteen times, committed by the tool
built to prevent an information leak.

**The manifest must classify by meaning, with a declared reason per table**, not
by scanning column names. A name-matcher is fine as a *review aid* and must not
be the gate.

## What genuinely must not be exported

```text
nf_identities                 email (a real address), subject (a provider
                              subject). The two values this campaign has spent
                              fifteen gates keeping out of logs and artifacts.

nf_auth_redirect_states       state_hash, pkce_verifier_hash,
                              pkce_verifier_encrypted, code_challenge. No
                              organization_id either, so it is unscopeable as
                              well as unsafe.

nf_auth_validation_events     auth-flow evidence, no org partition

alembic_version               schema state, not data; recorded as metadata
                              instead

organizations                 the org rows themselves, including the real one.
                              Recorded as a restore precondition rather than
                              exported.
```

## What the backup should cover

Not all 32 eligible tables. The durability block's subject is the evidence chain
Gate 152 replays, so the manifest covers the operational state a restore must
preserve for that replay to still work:

```text
nf_tenant_digest_records            Gate 151   the digest and its hash
nf_digest_delivery_intents          Gate 142   the intent and its linkage
nf_audit_events                     the third link in the chain
nf_source_watchlist_entries         Gate 140
nf_tenant_pursuit_suppressions      Gate 140
nf_awarded_grants                   Gate 139/124
nf_award_requirements               Gate 125
nf_award_requirement_proof_events   Gate 126
nf_award_documents                  Gate 127   metadata only; no body column
nf_tenant_beta_profiles             Gate 123
nf_tenant_customer_org_bindings     Gate 113/137
```

Eleven tables, every one org-partitioned, every one carrying `is_demo` or
`fact_status` so a restore can refuse anything that is not a fixture.

## Does restore tooling exist for this?

No. The Gate 65 harness shells out to `pg_dump`, which cannot run against the
SQLite dev database and would produce a physical dump rather than the
org-scoped, field-filtered logical export this needs.

## Can restored state be re-verified?

Yes, and this is the reason the gate is worth doing now rather than after a
provider exists:

```text
restored digest hash        recompute over the restored payload and compare
restored intent linkage     does the digest the intent names exist here?
restored audit replay       Gate 152's replay, run against the restored session
archived row readability    archive is a state; the row must still read by id
cross-org refusal           the partition must survive the round trip
legacy gaps                 must still be legacy_gap, not filled by restore
```

Every one of those is a local read. No provider, no network, no object store.

## What must remain false or UNKNOWN

```text
production_backup_ready       false. No managed instance, no automation, no
                              PITR, no executed restore test. The Gate 65
                              verifier already says so and continues to.
customer_data_backup          not applicable; no customer data exists
object_store_backup           not applicable; no object store is configured
RPO / RTO in force            documented, not enforced by anything
```

## Exact blockers remaining after this gate

```text
a managed database instance   procurement; unblocks the Gate 65 harness
backup automation             needs the instance first
PITR                          needs a provider that supports it
an executed provider restore  needs all three
```

None of those is what Gate 153 builds, and the docs must not let a reader
conflate `backup_restore_ready` with any of them.

## What Gate 153 builds

A manifest classified by meaning, an org-scoped logical export, a restore that
refuses anything but an isolated target, a verification that re-runs the Gate
152 replay against restored state, routes, a verifier, artifacts and docs. It
exports no customer data, touches no real organization, and claims no production
backup readiness.
