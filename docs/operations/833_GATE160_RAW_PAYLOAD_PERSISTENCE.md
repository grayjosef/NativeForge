# 833 — Gate 160: the raw payload persistence spine

There is now somewhere for a collector's response bytes to land, and it has been
proven with bytes that never came from anywhere.

```text
raw_payload_persistence_ready           true
storage_mode                            controlled_dev_demo_database
max_payload_size_bytes                  1048576  (1 MiB)
object_store_configured                 FALSE
production_raw_payload_store_available  FALSE
collectors_invoked                      0
live_source_calls                       0
source_monitoring_live                  false
```

## The gap this closed

`nf_raw_source_payloads` (migration 0028) already held response METADATA — 32
columns, 0 rows. It holds no bodies, and `raw_payload_ref` is a `VARCHAR(1024)`
pointer to an object store that has no bucket:

```text
raw_payload_object_store_bucket          ''
build_client_config(...).configured      False
body_store_configured                    FALSE
production_raw_payload_store_available   False
```

Gate 96C's repository **rejects `store_body=True` outright**, and says why:

> A 78 MB Grants.gov extract is not a database row, and a table that sometimes
> holds bodies is a table whose size nobody can predict.

That argument is correct. Gate 160 does not overturn it by widening the same
table — it adds a separate, size-capped, controlled-dev-demo landing zone and
leaves 0028's metadata-only contract untouched. A test asserts the migration
creates only its own table.

## The storage decision

```text
A  controlled_dev_demo DB-backed body, explicit size limit   <- chosen
B  metadata-only DB + object-store body                      already built
                                                             (Gate 97C),
                                                             unconfigured
```

Option B is **already implemented** and blocked on a credential nobody has.
Building a second object-store abstraction would have produced two stores, one
of them fake — which this gate's own rules forbid. `object_store_configured` is
read from Gate 97C's `build_client_config`, so it flips by itself the day
somebody configures one.

**1 MiB.** Gate 141's object adapter allows 16 MiB, but that is an *object*
adapter's limit and a database row is not an object. Large enough for a
synthetic fixture or a realistic API page; small enough that nobody mistakes it
for the production path. Refused above it by the service **and** by a database
CHECK.

## What a write goes through

```text
1  validate the attempt identity        160B
2  filter the response metadata         160F, allowlist by header name
3  hash the EXACT bytes                 160E, composing Gate 97C
4  persist                              160D
5  re-read through the store
6  verify the readback hash
```

Step 6 is what makes it an envelope. A path that persists and returns is
reporting an intention; one that reads back and re-hashes is reporting a fact.

## Attempt identity

Digested over `(attempt_version, job_id, source_id, attempt_number,
collector_version)` — and never over a random UUID, a PID, a worker id or a
clock.

```text
a job          one slot of work for one source     Gate 158
an ATTEMPT     one TRY at that work                here
a cycle        one pass of the orchestration loop  Gate 159
```

A job retried three times is one job and three attempts. If the ids collided,
attempt 2 would overwrite attempt 1's evidence — and the whole point of a raw
payload spine is that the bytes from two attempts are separately inspectable
when they disagree.

`collector_version` is in the digest because when a collector changes, the bytes
it produces for the same slot may legitimately differ. Without it the store
would have to choose between refusing the new bytes and silently overwriting the
old.

## Conflict semantics

```text
same attempt, same bytes       idempotent - the existing row is returned
same attempt, DIFFERENT bytes  REFUSED, with both hashes named
different attempts, same bytes allowed; the hash index shows the pair
```

The middle case matters most. Two byte strings claiming to be one attempt is a
contradiction: overwriting destroys the evidence they disagreed, and skipping
silently keeps whichever arrived first.

The third is deliberately allowed — a source that has not changed is normal, and
refusing it would make an unchanged source indistinguishable from a failed one.

## What the table refuses to hold

```text
no Authorization    no Cookie / Set-Cookie   no API key
no bearer token     no OAuth state           no PKCE verifier
no provider subject no customer data         no recipient address
no request URL      - a sha256 FINGERPRINT instead
```

Measured: a URL of
`https://example.gov/api/grants?api_key=SUPERSECRET123` produced a row in which
the string `SUPERSECRET123` appears nowhere, and a 64-character fingerprint.

And three columns the database refuses to let grow:

```sql
CHECK (collector_invoked = 0)
CHECK (live_fetch_performed = 0)
CHECK (payload_size_bytes >= 0 AND payload_size_bytes <= 1048576)
```

Each verified by going *around* the repository with a raw `UPDATE`, which raises
`IntegrityError`.

## Replay

```text
read the row
re-hash the stored bytes
compare with the recorded hash
   match     -> return the bytes
   mismatch  -> return NOTHING, and say why
```

A tampered payload comes back with **no body at all**. Returning bytes beside a
`hash_verified: false` would put the caller in the position of noticing.

Provenance — `attempt -> job -> source` — is resolved by **looking**, in Gate
158's job store and in the source registry, so a payload pointing at a job
nobody created is reported as such rather than passing because a column was
populated.

Cross-organization access is refused by **scoping**, not by comparing: another
organization's payload is not found rather than found-and-refused.

## Retention

```text
retention_unknown   the DEFAULT
retain_7_days       composed from raw_payload_store_contract_service
retain_90_days
retain_1_year
retain_indefinite
```

`retention_unknown` is the default because nobody has approved a retention
policy for source evidence, and defaulting to `retain_90_days` would be
inventing one. **UNKNOWN stays UNKNOWN.**

Archive is a lifecycle state, not a deletion. An archived payload still
replays, and an AST parse proves no `delete` call exists anywhere in the
repository module.

## What this is not

```text
a source was contacted        no
a collector ran               no - none exists; that is Gate 161
these bytes came from anywhere no. Every one was handed in by a caller.
an execution proof            NO. Gate 158's `completed` stays unreachable.
production storage            no. object_store_configured is false.
```

**A stored payload is not a fetched payload.** When Gate 161 builds a collector,
it will hand its response bytes to this same door, and the door will not be able
to tell the difference — which is the point of proving the landing zone before
anything lands in it.
