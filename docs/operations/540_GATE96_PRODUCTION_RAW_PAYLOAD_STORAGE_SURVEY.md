# 540 — Gate 96A: production raw payload storage survey

## The decisive finding

**There is no object store client anywhere in this project.**

```text
grep -iE "s3|boto3|blob_store|object_store|minio|gcs|azure_blob" src/nativeforge/
  -> nothing

grep -iE "boto3|minio|google-cloud-storage|azure-storage|s3fs" pyproject.toml uv.lock
  -> nothing

src/nativeforge/storage/
  -> does not exist

Settings fields: app_name, app_env, database_url, nf_demo_org_ids,
                 nf_dev_org_headers
  -> no bucket, no endpoint, no credential, no storage prefix
```

So `body_store_configured` is **false**, and no honest reading of this codebase
produces any other answer. Gate 96 adds a metadata table and a body-store
*contract*; it does not and cannot configure a body store, because there is
nothing to configure it against.

That is the whole shape of this gate: **adding a table is not the same as
production storage being live.**

## Alembic

```text
head before Gate 96   0027_rls_membership_authority
migration 0028        does not exist
revision style        plain string ids, "0027" -> "0026"
```

The 0026/0027 idiom is `op.create_table` with explicit `sa.Column`s,
`sa.CheckConstraint` built from a Python tuple joined into SQL, and
`op.create_index` calls after. Gate 96's `0028` follows it exactly.

`0027` carries an approval token in its docstring
(`MAYHEM_APPROVES_NATIVEFORGE_PROD_STORAGE_GATE61`) and the line *"Approved
environment: staging/dev proof first. No production customer claim."* — the
precedent that a migration existing is not a production claim, established
before this gate needed it.

## Existing tables

```text
nf_opportunity_sources        the source registry. org-scoped
                              (organization_id nullable), 8 check constraints,
                              carries the scheduling columns
nf_active_opportunity_sources file-generation lane
nf_source_check_runs          what a check DID: counts, statuses, timings.
                              No body, no hash, no headers.
nf_evidence_intake_records    CUSTOMER APPLICATION evidence
```

`nf_evidence_intake_records` is **not** reused, per instruction and for the
reason doc 534 already gave: its rows are checklist items, binder items and
forms attachments belonging to a Tribe's application. Putting agency HTTP
responses in the same table would give them one retention policy, one review
workflow and one access model, when they need different answers to all three.

## Where the body belongs

**Metadata in Postgres, body in an object store.** Not in the database.

```text
Grants.gov daily XML extract   ~78 MB compressed, once per day
Grants.gov description field   18,000 chars per opportunity
Additional eligibility text     4,000 chars per opportunity
```

A 78 MB row is not a row. Multiply by daily retention across five Phase 1
sources and the database becomes a filesystem with a query planner attached —
backups get slower, replication lags, and the thing you actually query
(metadata) is buried behind blobs nobody reads in a `SELECT`.

So `nf_raw_source_payloads` stores `raw_payload_ref` — a content-addressed
pointer — plus the hashes needed to verify whatever it points at. The body
lives wherever the body store contract says, and today that is nowhere.

The one exception the contract allows is `database_small_payload_only`, for
tests and tiny fixtures. It is explicitly **not** permitted for production
source ingestion, because "small" is not a property of a source response — it is
a property of the responses you happened to have seen.

## How metadata relates to the source registry

`source_id` on `nf_raw_source_payloads` is the **v2 registry's string id**
(`GRANTS-GOV-EXTRACT`, `DOI-BIA-GRANTS`), not a foreign key to
`nf_opportunity_sources.id`.

That is deliberate. The v2 registry is a 381-row CSV import that has never been
loaded into `nf_opportunity_sources`, and a foreign key would make it impossible
to store a payload from a source that has not been promoted into the DB
registry yet — which is every source. A FK would also make the evidence table
depend on a registry row that can be deleted, and evidence outliving its
registry entry is the point.

`collector_id` is indexed for the same reason: it answers "what did this
collector run produce", which is the question during an incident.

## SQLite

The migration uses only portable constructs:

```text
sa.Uuid(as_uuid=True)    sa.String    sa.Integer    sa.Boolean
sa.DateTime(timezone=True)             sa.JSON
sa.CheckConstraint       op.create_index       unique constraint
```

All supported by SQLite, and the local suite runs SQLite by default
(`database_url` defaults to `sqlite+pysqlite:///:memory:`). No Postgres-specific
types, no partial indexes, no `JSONB`.

**Postgres-specific features that come later, not now:** RLS policies on this
table (the 0027 pattern) once it holds anything org-scoped, and possibly `JSONB`
with a GIN index if `metadata_json` ever needs to be queried rather than read.
Neither is needed while the table is empty.

## How production storage stays NOT LIVE

Three separate facts, and the third requires the second:

```text
metadata_table_available              true after 0028
body_store_configured                 false — nothing to configure against
production_raw_payload_store_available  false — requires BOTH
```

`production_raw_payload_store_available` is derived from the other two, never
set beside them. Since `body_store_configured` cannot become true without a
client, a bucket and a credential — none of which exist — the derived flag
cannot become true by accident.

The readiness service detects the body store the same way Gate 95's preflight
detects the metadata store: by looking, not by reading a flag someone set.

## What cannot be built in this gate

```text
- an actual object store integration (no client, no bucket, no credential)
- retention expiry (nothing to expire; nothing durable to expire it from)
- RLS on nf_raw_source_payloads (nothing org-scoped in it yet)
- cross-process body retrieval (the local store is per-checkout)
- the Grants.gov 7-day window, which needs durable storage to mean anything
```
