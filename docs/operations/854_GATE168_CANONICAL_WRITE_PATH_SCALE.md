# Gate 168 — Canonical Graph High-Throughput Write Path

**Verifier:** `scripts/verify_nativeforge_canonical_write_scale.sh` → `RESULT=PASS`, `gate168_ready=true`
**Network requests during Gate 168: 0** (measured) · **fixture residue: 0** · live Gate 163 evidence byte-identical
**No schema change.** Alembic head remains `0053`.

---

## 1. The 49 statements, attributed

Gate 167 measured 49 SQL statements per observation and stopped there. "49" is
a number; this is the finding:

| class | first write | replay |
|---|---|---|
| CONFLICT_LOOKUP | **20** | 0 |
| IDEMPOTENCY_CHECK | **11** | 12 |
| PROVENANCE_INSERT | **10** | 0 |
| CURRENT_VERSION_UPDATE | 3 | 3 |
| identity / lineage / observation / version / canonical | 5 | 2 |

**41 of 49 were provenance work — 4.1 statements per field.** Per field, per
observation: a probe, a demote, a conflict read, an insert.

## 2. What replaced it

```text
per field, before          per BATCH, after
  SELECT provenance_id       SELECT every provenance row the chunk may touch
  UPDATE demote own          UPDATE demote, one per (source, canonical) set
  SELECT current rows        (answered from the prefetched map)
  INSERT one row             INSERT every new row in one executemany
```

Three phases: **RESOLVE** (set queries for everything the chunk could collide
with) → **DECIDE** (pure, in memory, in deterministic order) → **APPLY** (bulk
inserts, a bounded number of updates).

The middle phase is sequential on purpose. Two observations of one opportunity
in a chunk form a version chain, and a set operation cannot order a chain — so
decisions are made in memory, bounded by the batch size rather than the table
size, and only the resulting rows are written.

`record_observation` now delegates to this path with a batch of one. **One
write path, not two encodings of the same rules** — the one that drifted would
not announce itself.

| | before | after |
|---|---|---|
| first observation | 49 | **11** |
| idempotent replay | 17 | **4** |
| amended observation | 50 | **13** |
| statements per field | 4.1 | **0.3** |

## 3. Scale

Same fixture generator, same machine, same schema. Only the call shape differs.

| run | obs/sec | stmt/obs | txns | DB growth | peak memory |
|---|---|---|---|---|---|
| Gate 167 baseline | 14.7 | 49 | — | — | — |
| single-record (now) | 22.8 | 11.47 | — | — | — |
| batched 1,000 | **1,267** | 1.56 | 3 | 14 MB | 71.9 MB |
| batched 10,000 | 817 | 1.20 | 30 | 148 MB | 88.3 MB |
| batched 50,000 | **559** | **1.16** | 150 | 745 MB | **103.6 MB** |

**~86× over the Gate 167 baseline.** Statements per observation are
essentially constant across a 50× population change — the O(observations)
target, measured rather than asserted. Lookups stay index-backed at 50k:
identity 0.098 ms, current version 0.094 ms, provenance 0.107 ms.

Two honest notes: **throughput degrades with table size** (1,267 → 559) as
index maintenance grows over 750,000 provenance rows, and **storage is
9.9 KB per observation**, dominated by ten indexed provenance rows each.

## 4. Memory is bounded by the batch, not the input

The first measurement said 713 MB at 50,000 — a true number about the wrong
thing. Two causes, both mine:

- the fixture built the whole stream as a list;
- the API did `list(observations)` and accumulated a result dict per record.

Fixed by consuming an **iterable** and making per-record reporting opt-out
(`collect_results=False` keeps only the refused and the failed — bounded for a
healthy ingest, and still exact about what went wrong). **713 MB → 103.6 MB**,
now flat across scales.

Per-record detail and bounded memory are genuinely in tension; the caller
chooses rather than the library guessing.

## 5. Atomicity — six failure shapes

| scenario | result |
|---|---|
| all valid | all landed |
| one duplicate | idempotent, **not** an error; only the new record wrote |
| invalid provenance hash | rejected pre-flight; **the valid records beside it still committed** |
| identity conflict (L4 denying it is provisional) | rejected pre-flight; batch survived |
| real constraint violation | whole chunk rolled back, **nothing half-written** |
| interruption mid-chunk | whole chunk rolled back, every record reported |

Validation runs **before** the database, so one malformed record cannot poison
the valid ones. A constraint violation nobody could foresee rolls back the
chunk — the batch is the unit of atomicity, and that is stated rather than
discovered.

## 6. Concurrency — and its honest limit

Five concurrent writers against one database: same evidence, a new version, a
second source on the same identity, and unrelated opportunities.

No duplicate canonical rows · no duplicate observations · no duplicate
provenance · no dangling current-version pointer · no orphan versions · no
errors · no retry hidden as success.

**SQLite serializes writers with a database-level lock.** So what is proven is
that the writer is correct under *interleaving and retry* — **not** that it is
correct under real row-level concurrency. That needs a server engine and is
reported as UNKNOWN, not extrapolated.

## 7. Portability

Every technique classified **DATABASE_AGNOSTIC**; zero dialect markers in the
writer.

| technique | why it carries over |
|---|---|
| executemany bulk insert | SQLAlchemy Core compiles per dialect |
| set-oriented `IN` | standard SQL |
| bounded `IN` chunking (400) | guards SQLite's 999-parameter limit; harmless on Postgres |
| **derived primary keys** | no sequence, no `RETURNING`, no round trip to learn a key — this is what makes bulk insert possible at all |
| prefetch-then-decide | idempotency decided by this code, not by an engine's upsert clause |

No `PRAGMA`, no `ON CONFLICT`, no `RETURNING`. The one SQLite-specific thing —
`busy_timeout` — is in the concurrency *fixture*, not the writer.

**UNKNOWN:** Postgres throughput (the statement *count* carries over; latency
and planner behaviour do not); real row-level concurrency; whether `ON
CONFLICT` would beat prefetch — not measured, and deliberately not adopted,
because it would move idempotency from a decision this code makes into one the
engine makes silently.

## 8. Gate 167 semantics, re-proven after the rewrite

Nothing in the evidence model changed. Re-verified end to end: raw evidence
linked · field provenance complete · identity stable · replay idempotent ·
multi-source identity · conflicts representable with no automatic winner ·
version lineage a chain · forecast→posted · tenant duplication absent · rebuild
from evidence reproducing identical ids · unsupported fields not invented.

One clarification was needed. `fields_with_multiple_current_values` counted
current *rows*; two sources asserting the **same** value is corroboration, not
ambiguity, and the more sources agree the better. It now counts distinct
current **values**.

## 9. Defects found in my own instruments

1. **The interruption test never interrupted.** It patched `_materiality`,
   which only runs when a previous version exists — all six fixture records
   were new, so nothing raised and the test reported a clean rollback of
   nothing. Now patches a function on the path, and asserts the hook fired.
2. **Peak memory measured the harness**, not the writer (§4).
3. **`VERSIONED` landed in no metric bucket**, so the accounting reconciliation
   was checking a sum that could not fail.
4. **The verifier used `require_false` on a numeric zero.**
5. **The semantics phase is not self-normalizing** — leftover fixture rows from
   a hand-run phase make its writes no-ops, and it then reports that versioning
   and conflict detection stopped working. A stale fixture and a regression
   must not look alike, so the verifier now clears fixture state before
   measuring as well as after.

## 10. What Gate 168 deliberately did not do

No Redis, Kafka or queue · no database migration · no production DB dependency
· no reduction in provenance · no weakening of evidence linkage · no collapsing
of the observation/version/canonical layers · no SQLite-only optimization · no
schema change · no network request.
