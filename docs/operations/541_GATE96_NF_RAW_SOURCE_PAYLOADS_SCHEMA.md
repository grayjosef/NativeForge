# 541 — Gate 96B: nf_raw_source_payloads schema

**Migration 0028 adds a metadata table only.** The production body store remains
unconfigured. Collectors remain inactive, no live fetch occurred, no source
monitoring started, and no live source coverage is claimed.

**Adding a table is not the same as production storage being live.**

## The migration

```text
alembic/versions/0028_nf_raw_source_payloads.py
revision      0028
down_revision 0027
```

31 columns, 5 indexes, 1 unique constraint, 7 check constraints. It applies
cleanly on SQLite — the local suite's default backend — using only portable
constructs: `sa.Uuid`, `sa.String`, `sa.Integer`, `sa.Boolean`,
`sa.DateTime(timezone=True)`, `sa.JSON`, `sa.CheckConstraint`,
`op.create_index`. No `JSONB`, no partial indexes, no Postgres-only types.

The precedent for a migration that is not a production claim is migration 0027,
whose docstring already reads *"Approved environment: staging/dev proof first.
No production customer claim."*

## The documented head moves 0027 → 0028

Gate 63 replaced a brittle "no revision beyond 0019" freeze guard with a
doctrine that pins the head as a **single constant**, on the stated reasoning
that *"when a migration is approved and added, exactly one constant here
changes, and the change is deliberate rather than collateral damage."*

**Three** constants moved, each with the re-pin recorded beside it:

```text
tests/test_gate63_migration_doctrine.py            CURRENT_HEAD = "0028"
tests/test_sprint20_discovery_engine_closeout.py     "0028 (head)"
src/nativeforge/services/
  postgres_membership_directory_service.py         EXPECTED_MIGRATION_HEAD
```

The third is not a test constant, and it is not a formality. Its comment reads:
*"The migration head this adapter was written against. A runtime database at a
different revision has a schema this code was never reviewed for, so the adapter
declines rather than guessing."*

Moving it is therefore a claim that the adapter **was** reviewed against the new
schema. The review, recorded in the code: `0028`'s `upgrade()` performs exactly
one `create_table` (`nf_raw_source_payloads`) and five `create_index` calls on
that same table. It touches neither `nf_identities` nor `nf_org_memberships` —
the only two tables the adapter reads — nor `organizations`. The adapter's
schema is unchanged, so the claim is true.

Bumping that constant to unblock a failing test, without doing the review it
asserts, would have been exactly the unearned claim this campaign exists to
prevent.

## How this was found

Gate 96's scoped regression list covered 25 suites and included none of these
three files. The full suite surfaced the first two, and after fixing them a
second full run surfaced the third — `test_gate62_..._matches_gate63_doctrine`,
which cross-checks the service constant against the doctrine constant, and only
fails once the doctrine constant has moved.

That ordering is the argument for the full suite over a curated subset: the
third failure was structurally invisible until the first two were fixed.

This document is the `docs/operations` entry the doctrine's comment asks for.

## Metadata, not bodies

There is no body column and a test asserts it: `response_body`, `raw_body`,
`body`, `payload_body` and `content` are all absent. What the table holds is
`raw_payload_ref` — a content-addressed pointer — plus the hashes needed to
verify whatever it points at.

The Grants.gov daily extract is ~78 MB compressed. A 78 MB row is not a row.
Multiply that by daily retention across five Phase 1 sources and the database
becomes a filesystem with a query planner attached: backups slow, replication
lags, and the metadata anyone actually queries sits behind blobs nobody reads.

## Not foreign-keyed to the source registry

`source_id` is the **v2 registry's string id** (`GRANTS-GOV-EXTRACT`,
`DOI-BIA-GRANTS`), not a FK to `nf_opportunity_sources.id`.

None of the 381 v2 rows has been promoted into the DB registry. A foreign key
would make it impossible to store evidence from a source that has not been
promoted — which is every source — and would let a deleted registry row take its
evidence with it. Evidence outliving its registry entry is the point of having
evidence.

A test asserts no FK to `nf_opportunity_sources` exists.

## Constraints that make bad rows unrepresentable

```text
uq_..._payload_id                  payload_id unique
ck_..._provenance_exclusive        NOT (live AND fixture)
ck_..._redaction_status            vocabulary
ck_..._secret_scan_status          vocabulary
ck_..._parser_status               vocabulary
ck_..._promotion_status            vocabulary
ck_..._retention_policy            vocabulary
ck_..._promoted_scan_clean         promotion_status <> 'evidence_ready'
                                   OR secret_scan_status = 'clean'
```

Two of these deserve their reasons stated.

**`provenance_exclusive`** is Gate 88's finding made unrepresentable. The corpus
contained records whose "recorded" flag described the flag rather than the
fetch; a row claiming both provenances is claiming its own origin is unknown,
and the database now refuses it outright.

**`promoted_scan_clean`** duplicates a rule the promotion gate already enforces,
in SQL. That is deliberate: a row written around the service — by a script, a
migration, a future repository nobody reviewed — is exactly the case a database
constraint exists for. Every one of these is exercised by a test that attempts
the bad insert and asserts it raises.

## Indexes, and what each answers

```text
source_id            "what has this source produced"
collector_id         "what did this collector run produce"   <- incident question
retrieved_at         "what arrived in this window"
response_body_hash   "have we seen these exact bytes before"
promotion_status     "what is stuck in quarantine"
```

`collector_id` is indexed because the question that gets asked during an
incident is which run produced a bad batch, and answering it with a table scan
during an incident is answering it slowly.

## The schema artifact is parsed, not transcribed

`artifacts/raw_payload_production_readiness/nf_raw_source_payloads_schema.json`
is generated by `ast`-parsing the migration file and reading its actual
`sa.Column`, `sa.CheckConstraint` and `op.create_index` calls. A hand-copied
schema drifts from the migration the first time someone edits one and not the
other; this one cannot.
