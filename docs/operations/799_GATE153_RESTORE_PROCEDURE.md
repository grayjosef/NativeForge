# 799 — Gate 153: the restore procedure, and what it refuses

This is the controlled dev/demo restore. It is not the production restore, and
there is no production restore: `scripts/verify_nativeforge_backup_restore.sh`
still returns `RESULT=SKIP`.

## The procedure

```text
1  export      build_backup_export(connection, organization_id)
               reads one organization, filters forbidden values, hashes each
               table, writes nothing

2  target      create an EMPTY database and migrate it to head (0042)
               it must not be the source, and it must be declared
               target_kind="isolated_temporary_database"

3  precondition insert the organizations row into the target
               the backup never carries it — see doc 798

4  restore     restore_backup(target_connection, export, target_kind,
                              source_url, target_url)
               checks every hash BEFORE writing a row, then loads

5  verify      verify_restored_state(source_connection, restored_connection,
                                     organization_id, export, restore)
               runs the Gate 152 replay on both sides and compares

6  destroy     delete the temporary database
```

The verifier does all six and deletes the target before it exits.

## Running it

```bash
bash scripts/verify_nativeforge_backup_restore_readiness.sh
```

It needs the backend running on `127.0.0.1:8000` and nothing else. No provider,
no network, no credentials.

## What a restore refuses, and why

```text
restore_target_is_not_isolated        the target was not declared isolated
restore_target_is_the_source_database the target URL equals the source URL
payload_hash_mismatch                 a table does not hash to what it claims
payload_contains_a_forbidden_field    a field arrived that no manifest table has
payload_contains_a_non_fixture_row    refused as a WHOLE, never filtered
real_organization_refused_by_name     the payload names the real organization
migration_head_mismatch               payload and target disagree on schema
export_payload_was_not_exported       the payload is a refusal, not an export
no_target_connection_supplied         there is nowhere to restore to
```

Two of those are the point of the whole thing. The Gate 65 harness put it
plainly: a restore proof that overwrites the live database is an outage, not a
proof. This enforces the same rule one layer down.

**Both target refusals are RUN, not asserted.** The verifier calls
`restore_backup` with the source as the target, and again with
`target_kind="live_database"`, and each must refuse *and* write zero rows. A
permitted branch nobody can reach makes a refusal unfalsifiable — Gate 134F's
lesson — so neither is left as a claim.

## Hashes are checked before rows are written

A restore that wrote first and checked afterwards has already done the damage
by the time it tells you. Every table's `payload_sha256` is recomputed over the
rows in the payload before a single insert, and a mismatch refuses the whole
restore. The verifier corrupts a hash deliberately and asserts zero rows were
written.

## Nothing is invented

A row whose link points at something the payload does not contain is restored
with the dangling link intact. A restore that filled in the missing end would
be manufacturing evidence. The verification reports the gap; the restore does
not close it.

This is most visible in the legacy delivery intents whose digest predates
persistence. There are 93 of them in the dev database, and there are still 93
after a restore. **A fall in that number fails the lane** rather than passing
it, because the only way to reduce it is to invent a digest for an intent that
never had one.

## Rows are written back the way they were read

The export reads through `sa.text` and serialises to JSON, so a timestamp
leaves as an ISO string. Writing that back through a typed `sa.Table` fails on
SQLite — *"only accepts Python datetime"* — and succeeding would have been
worse: SQLite stores a coerced datetime as `2026-01-02 03:04:05.000000` where
the export held `2026-01-02T03:04:05`, and the verification rehashes the
restored rows. A restore that re-rendered the value would report a hash
mismatch against a database holding exactly the right data.

So the insert goes back through `sa.text` with bound parameters. This is a
stated limitation, carried in `RESTORE_LIMITATIONS` and returned in every
restore report: a PostgreSQL target would need per-type coercion this does not
do, which is one of the things a provider-level restore does for itself.

## What a restore cannot do

```text
- restore into the live database, under any flag
- restore the organizations table
- restore identities, redirect states or validation events
- restore a payload that is not entirely fixture data
- restore for the real organization
- close a legacy gap
- contact a provider, a source, an object store or a mail server
```
