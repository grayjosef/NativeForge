# 733 — Gate 140: the tenant source watchlist, operational

## What was there before

Nothing. Doc 732 recorded the finding:

```text
tenant_source_watchlist_service        ABSENT
nf_source_watchlist_entries            NO TABLE
source_watchlist_persistence lane      0 of 9 columns true
```

`nf_tenant_beta_profiles.source_watchlist_preferences` existed — a JSON column
on the profile — and nothing read it as a watchlist. Gate 138's capability
matrix reported the lane absent on every count, and it was right.

## What exists now

Migration `0040` adds `nf_source_watchlist_entries`:

```text
id                        uuid, primary key
organization_id           uuid, FK organizations.id ON DELETE CASCADE
is_demo                   boolean
tenant_id_label           text, a LABEL and never authority
source_id                 text
source_name               text
jurisdiction              text
program_area              text
watchlist_state           text, CHECK
watchlist_source          text, CHECK
fact_status               text
human_review_required     boolean
blocked_reasons           text
created_by_identity_id    uuid
created_at / updated_at   timestamp
archived_at               timestamp, null while live
```

Plus a partial unique index on `(organization_id, source_id) WHERE archived_at
IS NULL` — one live entry per organization and source — and, on PostgreSQL, the
row-level-security policy the rest of this campaign uses:

```sql
organization_id = current_setting('app.current_org_id', true)::uuid
AND is_demo = current_setting('app.current_org_is_demo', true)::boolean
```

`tenant_id_label` is a label. `organization_id` is the only authority, which is
the rule Gates 110–113 settled and the reason the column is named the way it is.

## The routes

`src/nativeforge/api/tenant_watchlist_routes.py`, demo organizations only:

```text
POST   /v1/nf/demo/orgs/{org}/source-watchlist                      add
GET    /v1/nf/demo/orgs/{org}/source-watchlist                      list
GET    /v1/nf/demo/orgs/{org}/source-watchlist/{entry_id}           read one
POST   /v1/nf/demo/orgs/{org}/source-watchlist/{entry_id}/archive   stop watching
```

No real-organization router was built. One would create a route to
`aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee` that nobody has authorized — the same
reason Gate 139 gave for the four post-award lanes.

Every route depends on `require_demo_org_session`. The dev header is not a
parameter on any of them, and a forged `X-NF-Org-Id` returns 401.

## Watching is not monitoring

This is the claim the gate is forbidden from making, and it is enforced in three
places rather than asserted once:

```text
every response                 source_monitoring_live: false
                               live_source_called: false
every entry in every response   source_monitoring_live: false
                               last_checked_at: null
the service result              network_calls: 0
```

A watchlist entry is a statement of interest. Nothing in this lane opens a
socket, activates a collector, or fetches a notice. `last_checked_at` is `null`
because nothing has ever checked, and it is reported rather than omitted so a
reader of one entry does not have to find the header to learn it.

## A registry claim is checked

`watchlist_source` is one of:

```text
registry_entry        checked against the shipped source catalogue
controlled_fixture    must carry the `nf-fixture-` prefix
tenant_requested      stored with human_review_required: true
```

`known_registry_source_ids()` reads the seed CSV this repository ships — **177
source ids** — and a `registry_entry` claim for an id that is not there is
refused by name:

```text
source_id_is_not_in_the_source_registry
```

That check was broken when it was first written. It called `load_seed_rows`,
which does not exist in `source_ingestion_seed_schema_service`, and a bare
`except Exception: return frozenset()` swallowed the `AttributeError` — so the
registry read as empty and **every** `registry_entry` claim would have been
refused while looking like a working guard. That is the eleventh time this
campaign has found a probe reporting on a name rather than a capability. A test
now asserts the registry has more than a hundred ids in it, so an empty read
cannot hide as a strict-looking refusal again.

`tenant_requested` is allowed on purpose. A source nobody has vetted is exactly
the thing a human has to look at, and refusing it outright would push tenants
into mislabelling their own requests as registry entries.

## Archiving keeps the row

`POST .../archive` sets `archived_at`. It is an UPDATE, never a DELETE:

```text
rows_deleted           0
history_preserved      true
list (default)         the entry is gone
list?include_archived  the entry is there
```

The partial unique index stops treating an archived entry as the live one, so a
tenant can stop watching a source and start again later without the first
decision disappearing.

## What a caller may not do

```text
set is_demo or fact_status          400, named
claim a registry id nobody issued   400, named
label a fixture without the prefix  400, named
watch the same source twice         400, this_organization_already_watches_this_source
read another organization's list    403/404 — which does not confirm a row exists
archive another organization's entry refused; the row stays live for its owner
```

`WatchlistEntryBody` declares `extra="allow"` so `refuse_caller_supplied` can
**see** a field a caller should not set. Pydantic drops an unknown field
silently, which is how Gate 139 found `is_demo: false` being ignored rather than
refused.

## What this lane is now worth on the capability matrix

Gate 138 reported `source_watchlist_persistence` false on every count. It is now:

```text
schema_available                  true
organization_id_anchor_available  true
rls_backed                        true
repository_available              true
service_contract_available        true
write_path_available              true
read_path_available               true
controlled_dev_persistence        true
production_operational            false — customer auth still owns that
```

`controlled_dev_persistence_available_count` went from 6 to 7.

Finding that out required fixing the probe. `detect_schema_facts` resolved a
migration's table name only through three blessed constant names — `TABLE`,
`table`, `TABLE_NAME` — and `0040` names its tables `WATCHLIST` and
`SUPPRESSIONS`, so both read as absent while both existed. The same held for
the RLS detection, which read `ALTER TABLE {TABLE}` and not a loop over two
constants. It now parses each migration's module-level string constants with
`ast` and resolves whatever name `op.create_table` was handed. Twelfth instance
of the same defect class; same fix as every other time — derive it.
