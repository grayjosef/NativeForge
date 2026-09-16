# 836 — Gate 160 delta: what changed, and what is next

## Lanes

```text
raw_payload_persistence_ready           created, and TRUE
orchestration_runtime_ready             unchanged, true
collection_job_store_ready              unchanged, true
worker_runtime_ready                    unchanged, true
scheduler_runtime_ready                 unchanged, true
object_store_configured                 unchanged, FALSE
production_raw_payload_store_available  unchanged, FALSE
source_monitoring_live                  unchanged, FALSE
approved_source_count                   unchanged, 0
```

One lane was created. None that was false became true.

## What Gate 160 added

```text
migration 0046       nf_source_collection_raw_payloads, bodies for dev/demo
attempt identity     over (job, source, attempt_number, collector_version)
a hash service       composing Gate 97C's bytes-first body_hash
a metadata filter    ALLOWLIST by header name, 18 names
a repository         persist, get, list, archive, count; hash-verified twice
a write envelope     validate -> filter -> hash -> persist -> re-read -> verify
a replay service     hash checked BEFORE bytes are returned; provenance resolved
a health lane        raw_payload_persistence_ready, 11 conditions
4 routes             3 GET, 1 synthetic POST that rolls back
a verifier           50 checks, phases in separate processes
132 tests
10 artifacts
5 docs               832, 833, 834, 835, 836
```

## What it did not add

```text
a collector                     Gate 161
an approved source              Gate 162, and then a human
accepted source terms           a human. 171 sources.
a configured object store       Gate 97C's store exists and has no bucket
production raw payload storage  still unavailable, by derivation
an execution proof              Gate 158's `completed` stays unreachable
a deletion path                 no approved retention policy exists
```

## The survey changed the gate

Gate 160 was written expecting to build a raw payload store. The survey found
most of one already built, by Gates 95 to 97:

```text
nf_raw_source_payloads        exists, 32 columns, 0 rows, NO body column
Gate 96C's repository         rejects store_body=True, with a stated reason
Gate 97C's S3 body store      built, content-addressed, hash-verifying
body_store_configured         FALSE - no bucket, endpoint or credential
```

So the actual gap was narrower and more specific than the gate anticipated:
**there was nowhere to put bytes in `controlled_dev_demo`**, and the production
path was blocked on configuration rather than on code.

That made 160J's decision straightforward and turned it into a constraint rather
than a preference: building a second object-store abstraction would have
produced two stores, one of them fake.

## Five defects found by measuring, all mine

**1. The metadata filter refused everything.** The secret scanner was called
with `payload=` instead of `body=`; every call raised, the exception was caught,
and every allowlisted header was refused with a plausible reason. It would have
refused `Content-Type: application/json` while passing every refusal test. Doc
835 has the detail.

**2. A verified hash and an unusable body.** `get_payload(include_body=True)`
returned the body through `_json_safe`, which turned `bytes` into a lossy Python
repr string. `hash_verified: True` and `bytes identical: False` were both true
at once. Doc 834.

**3. The provenance check always said no.** It compared a *string* organization
id against a typed `sa.Uuid` column, so it reported "no such job" about a job it
had just created. A red check with two causes, where the red one looked like the
honest answer.

**4 and 5. Two test scans that matched prose.** Assertions that a module never
imports `build_job_id` and contains no `hashlib` both matched the docstrings
saying exactly that.

And a sixth, one layer deeper: after switching to an AST parse, I substring-
matched the *unparsed* callee expression, so `str(expected_sha256 or '').strip()`
matched a search for `"sha256"`. The parse was right and the predicate was
wrong. All now resolve dotted name paths.

That is occurrences nine through thirteen of substring-vs-meaning in this
campaign. The running tally is in doc 825; the pattern is stable enough to state
plainly: **every time a check asks "does this text appear" when it means "does
this happen", it eventually matches the sentence explaining why it must not.**

## What still blocks a collection

```text
1  a collector envelope      Gate 161   engineering
2  source allowlist boundary Gate 162   engineering
3  source terms              171 sources — a HUMAN must read them
4  human review              a HUMAN must look at each source
```

Item 1 is the last purely-engineering blocker before the allowlist boundary
decides what approval means. Items 3 and 4 are not engineering, and a working
landing zone does not make them so — it means that when a human finally clears
them, there is somewhere for the first response to land that has already been
proven byte-for-byte.

## Gate 161 carry-forward

```text
- Gate 156 owns schedule evaluation.
- Gate 157 owns worker execution and job leases.
- Gate 158 owns the persistent job lifecycle.
- Gate 159 owns periodic orchestration and cycle ownership.
- Gate 160 owns raw payload persistence, hashing and replay.
- Do not build another payload store, hash function, or header filter.
- A collector hands its bytes to persist_raw_payload. That door already
  validates, filters, hashes, persists, re-reads and verifies.
- The collector must not store a URL. Pass it as `source_url`; the envelope
  fingerprints it and discards it.
- collector_version belongs in the attempt identity. A changed collector
  produces different evidence, not a contradiction.
- A fetched payload IS different from a supplied one, and Gate 161 is the
  first gate with standing to say so. If it defines what an execution proof
  IS, that deserves the whole gate rather than a corner of it - and until it
  does, nothing may set execution_proof_ref and `completed` stays unreachable.
- object_store_configured stays measured from Gate 97C's config. Do not
  declare it.
- Do not approve a source. Do not accept terms. Do not clear human review.
- source_monitoring_live remains false until a gate explicitly, deliberately
  makes it true with approvals in hand.
- Verifier cleanup runs after the FINAL process write.
- Always re-stamp after commit.
```

## The alembic head pins

Migration 0046 moved **ten** real head pins from 0045, found on the first pass
by the unquoted structural sweep — including `== "0045 (head)"`, which no grep
for the bare quoted revision finds. Gates 158, 159 and 160 have each caught that
line first time.

Eight mentions of 0045 were deliberately left as provenance: Gate 159's own
`MIGRATION` constant, its verifier's check that the 0045 *file* exists, and the
`migration_added_by_this_gate` line Gate 158 introduced precisely so it would
not go stale. It has now survived two subsequent migrations without editing.
