# Gate 167 — Canonical Opportunity Store / Evidence-Backed Write Path

**Verifier:** `scripts/verify_nativeforge_canonical_opportunity_store.sh` → `RESULT=PASS`, `gate167_ready=true`
**Network requests during Gate 167: 0** (measured — every phase replaces `socket.socket` with one that raises and counts)
**Migration:** `0053_canonical_opportunity_graph` · **fixture residue: 0** · live Gate 163 evidence byte-identical

---

## 1. The gap this closes

Gates 156–166 built a substrate that can prove where a byte came from. It ended
at `nf_source_collection_raw_payloads`. Every customer-facing capability —
matching, deadlines, amendments, relevance, alerts — was blocked behind one
missing store.

Gate 165 found the design work already done and disconnected:
`opportunity_identity_versioning_service` (Gate 92E) had **zero production
callers**. Gate 167 wires it in.

## 2. Four tables, because these are four different things

```text
CanonicalOpportunity   the thing that exists in the world
SourceObservation      one source saying it saw that thing, once
OpportunityVersion     what the fields were, at one observation
FieldProvenance        which evidence supports each canonical value
```

`nf_grant_sparks` (0 rows) is what collapsing them looks like: 50 columns
mixing canonical facts, tenant pipeline state and raw NOFO text, per
organization. A schema in that shape cannot say which source asserted a value,
cannot hold two sources disagreeing, and multiplies the world by the customer
count.

## 3. Rules enforced by the schema, not by convention

```sql
CHECK (length(raw_payload_sha256) = 64)          -- observations
CHECK (length(raw_payload_sha256) = 64)          -- field provenance
CHECK (identity_layer <> 'L4' OR is_provisional = 1)
UNIQUE (normalized_opportunity_number, doc_type)
UNIQUE (source_id, source_record_id, raw_payload_sha256)
UNIQUE (canonical_id, content_fingerprint)
```

An observation naming no bytes, or a canonical field value tracing to nothing,
has **no representation at rest**. Gate 164 established that this is stronger
than detecting bad state afterwards. The L4 constraint makes fuzzy identity
unable to present itself as settled.

## 4. No `organization_id`. Anywhere.

All **fifteen** other opportunity-shaped tables in this database carry it. The
canonical graph carries none, and the verifier reads that from the live schema
rather than trusting a comment.

| | |
|---|---|
| organizations present | 3 |
| canonical rows for the real opportunity | **1** |
| tenant columns found in the graph | **none** |
| tenant tables referencing an opportunity | `nf_tenant_pursuit_suppressions` |

Tenant state points *at* the graph instead of copying it — the pattern
`nf_tenant_pursuit_suppressions.opportunity_id` already used.

## 5. The first real canonical opportunity

Written from stored Gate 163 evidence. No fetch.

```text
canonical_id     L1:OBJA2026172662|synopsis
source_id        nf-seed-2026-api-grants-gov-search2
source_record_id 363308
raw payload      eb4cc7cb…1712, 11,131 bytes, hash verified on replay
version_id       8759648b…7970
provenance       10 rows, every one naming that sha256
http_status      NULL — still UNKNOWN, still not backfilled
```

**Fields absent: none. Fields the source cannot supply, named and not
invented:** `eligibility_text`, `funding_amount_min`, `funding_amount_max`,
`source_url`. A search result is not a detail record; those arrive from
`fetchOpportunity`, which Gate 163 was forbidden to call.

The normalizer has three outcomes, never two — *supported and present*,
*supported but absent*, *not supported by this source*. Collapsing the last two
is how a Tribe ends up reading a funding ceiling nobody published.

## 6. Identity, replay, conflict

| property | result |
|---|---|
| replay identical evidence | **nothing written**; identical canonical / version / observation ids |
| title change | new version, same canonical, **not material** |
| deadline change | new version, **material** |
| 4 versions | lineage is a chain, previous retained, current pointer is newest |
| two sources, one opportunity | 1 canonical, 2 sources, distinct evidence refs, record ids kept separately |
| two sources disagree on a deadline | both retained, one conflict group, **no winner picked** |
| disputed value | did **not** become canonical by arriving second |
| forecast vs synopsis | distinct canonical rows, joined by `opportunity_number_group` |

Every identifier is **derived** from evidence — `canonical_id` from the L1
composite key, `version_id` from `(canonical_id, content_fingerprint)`,
`provenance_id` from `(version_id, field_name)`. A random UUID would make the
same evidence produce different rows each run. Derivation is what makes replay
idempotent without a single comparison in application code, and what makes §7
possible.

## 7. Rebuild from evidence

Inside a **copy** of the database file, the entire graph was deleted and
rebuilt from the source observations and the payload store — through the same
verified `replay_payload` path the audit uses, not a raw column read.

Identical canonical id · identical version ids · identical observation ids ·
**identical all ten provenance ids** · identical current-version pointer.

The graph is derivable from evidence. The payload store stays authoritative.

## 8. Scale — measured, with the limitation named

5,000 opportunities, 7,508 observations, 75,080 provenance rows, in a throwaway
copy. Nothing written to the real database.

**Reads are good.** Every probed lookup uses an index:

| lookup | ms | plan |
|---|---|---|
| by identity | 0.170 | `USING INDEX uq_…_identity` |
| by source record | 0.148 | `USING INDEX ix_…_source` |
| current version | 0.089 | index join |
| field provenance | 0.096 | `USING INDEX ix_…_current` |
| by deadline | 0.062 | indexed |

**Writes are not.** 14.7 observations/second, 68 ms each, 73.6 MB growth
(10.3 KB per observation). Attributed rather than guessed at, by an A/B against
database copies:

```text
49 SQL statements per observation          <- the dominant cost
commit batching gives only 1.9x            (60ms -> 31ms)
```

So the write path is **query-fan-out bound**, not durability bound: roughly
four statements per field per observation. This is the gate's principal
limitation and it is reported, not dressed up — at millions of observations
14.7/second does not hold. Batching the provenance work is the obvious next
move and is **not** attempted here, because it was not measured as safe.

**UNKNOWN, not extrapolated:** concurrent writers, any engine other than
SQLite, behaviour beyond the fixture size. Environment: Python 3.12.3, WSL2
Linux 6.6.87.2.

## 9. Corrections to the record

**The first live payload did not contain a forecasted opportunity.** My Gate
165 report said it did, and the Gate 167 prompt repeated it from there. The
stored bytes carry one hit: `docType: synopsis`, `oppStatus: posted`. The
*query* asked for `posted|forecasted`; the single returned row is posted. 167J
is proven with synthetic records instead, and the model does represent the
transition.

## 10. Defects found in my own instruments

Five, each of which produced a confident wrong answer:

1. **`is_material: true` on a first sighting** — materiality describes a change
   against a prior version. Firing "the deadline moved" on the day we first saw
   an opportunity is the wrong signal to the wrong audience.
2. **Stale provenance never demoted** — a source that moved its own deadline
   left both dates marked current, so "the current close date" had two answers
   from one source. Not a conflict; a stale row pretending to be a fact.
3. **`source_record_id` counted as a conflict** — two sources' internal keys are
   different namespaces, not a disagreement. Every multi-source opportunity
   would have been permanently contested.
4. **The reset tool keyed on payload hash** — a synthetic fixture's hash is a
   real digest, indistinguishable from any other, so the guard recognised
   nothing, silently refused, and a later run collided with rows it believed it
   had removed.
5. **Two tests matched the sentence explaining the rule** — the writer's
   docstring says it "never updates… never deletes" and names the payload
   table; a literal scan read that as a violation. Fixed with AST docstring
   exclusion, the same instrument Gate 166 needed.

## 11. What Gate 167 deliberately did not do

No relevance scoring · no LLM extraction · no customer matching · no second
evidence ledger · no rewrite of the identity/versioning model · no schema
consolidation of the three source registries · no second source · no network
request of any kind.
