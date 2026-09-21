# Gate 170 — Amendment / Change Intelligence

**Verifier:** `scripts/verify_nativeforge_change_intelligence.sh` → `RESULT=PASS`, `gate170_ready=true` (90 checks)
**Network requests during Gate 170: 0** (measured) · **fixture residue: 0** · live Gate 163 evidence byte-identical
**Migration:** `0055_change_intelligence` (alembic head `0054` → `0055`)
**Notifications sent: 0** — delivery is explicitly not built in this gate.

---

## 1. Survey first (170A)

| primitive | classification |
|---|---|
| `opportunity_deadline_and_amendment_model_service` | **AUTHORITATIVE** — the deadline shape vocabulary |
| `canonical_opportunity_batch_repository` (Gate 168 DECIDE) | **AUTHORITATIVE** — the only field comparison |
| `opportunity_identity_versioning_service` | **AUTHORITATIVE** — what "same opportunity" means |
| `canonical_opportunity_repository` | REUSABLE — single-observation write path |
| `nf_opportunity_versions` | **AUTHORITATIVE** — the version chain, already durable |
| digest services (Gates 140–151) | REUSABLE, **not wired** — delivery is out of scope |

The decisive finding: **Gate 168's DECIDE phase already computes the field
comparison** and stores the result in `changed_fields_json`. A change-detection
engine that diffed again would be a second comparison with its own bugs and its
own disagreements. So this gate **types what Gate 168 already found** and never
recomputes it — the repository reads `changed_fields_json` and classifies.

## 2. The change model (170B)

Migration 0055 adds two tables and no second diff.

```text
nf_opportunity_change_events      one row per (canonical, prior_version, new_version, field)
nf_opportunity_field_conflicts    one row per contested FIELD, not per poll
```

**25 change types**, every one classified, **zero without a named rule**:

```text
TITLE_CHANGED  STATUS_CHANGED  OPEN_DATE_CHANGED  DEADLINE_CHANGED
DEADLINE_EXTENDED  DEADLINE_SHORTENED  FUNDING_MIN_CHANGED  FUNDING_MAX_CHANGED
ELIGIBILITY_CHANGED  AGENCY_CHANGED  OPPORTUNITY_NUMBER_CHANGED
DOCUMENT_ADDED  DOCUMENT_REMOVED  DOCUMENT_REPLACED  SOURCE_URL_CHANGED
ASSISTANCE_LISTINGS_CHANGED  FORECAST_TO_POSTED  POSTED_TO_CLOSED
REOPENED  CANCELLED  AMENDMENT_PUBLISHED  CONFLICT_INTRODUCED
CONFLICT_RESOLVED  FIRST_OBSERVED  UNKNOWN_CHANGE
```

Event identity is **derived, not allocated**:

```text
change_event_id = sha256(canonical_id | prior_version_id | new_version_id | field_name)
```

so replay collides on the primary key rather than duplicating, and a rebuild
from evidence reproduces the same ids.

### Materiality is rule-backed, and the database enforces it

```sql
CHECK (materiality = 'UNKNOWN'
       OR (materiality_rule IS NOT NULL AND length(materiality_rule) > 0))
```

`CRITICAL` is not reviewable. `CRITICAL because deadline_shortened_reduces_
time_to_apply` is. A severity with no rule name is **unrepresentable**, not
merely discouraged.

| change | materiality | why |
|---|---|---|
| `DEADLINE_SHORTENED` | **CRITICAL** | a Tribe that planned around the old date has lost time |
| `DEADLINE_EXTENDED` | MATERIAL | worth knowing; can wait for a digest |
| `CANCELLED` · `POSTED_TO_CLOSED` · `OPPORTUNITY_NUMBER_CHANGED` | **CRITICAL** | pursuit work is now void or misfiled |
| `DOCUMENT_REMOVED` | **CRITICAL** | something a submission depended on is gone |
| `DOCUMENT_ADDED` | INFORMATIONAL | the asymmetry is deliberate |
| `ELIGIBILITY_CHANGED` · `FORECAST_TO_POSTED` | MATERIAL | |
| `ASSISTANCE_LISTINGS_CHANGED` | INFORMATIONAL | a program code, not an attachment |
| `SOURCE_URL_CHANGED` | INFORMATIONAL | |
| cosmetic `TITLE_CHANGED` (whitespace/punctuation) | NON_MATERIAL | |
| `FIRST_OBSERVED` | **NON_MATERIAL** | discovery is not an amendment |

**Direction is the whole point.** A single `DEADLINE_CHANGED` type would force
a shortened and an extended deadline into the same alert and guarantee that one
of the two is wrong.

**No LLM decided anything.** `classify_change` returns
`decided_by: "deterministic_rules"`, `llm_used: false`, and
`change_invariant_failures` refuses a change whose `llm_used` is true.

### Five refusals the invariant enforces

- a shortened deadline that is not CRITICAL
- a cancellation that is not CRITICAL
- a first observation typed as an amendment
- a non-UNKNOWN materiality with no named rule
- any classification an LLM touched

## 3. Deadlines (170C–170F)

The deadline shape vocabulary is Gate 166's, unchanged:
`single · dual · per_region · phased · revised · multi_year · unknown`.

`classify_deadline_move` parses `MM/DD/YYYY`, ISO, and two long forms. **If
either side is unparseable it returns the undirected `DEADLINE_CHANGED`** with
the reason `dates_could_not_be_parsed` — a guessed direction carrying a CRITICAL
alert is worse than an honest "it moved."

When the shape is `dual`, `per_region` or `phased`, the event carries the reason
`one_of_several_deadlines_moved` and the shape travels **on the event row**, not
just on the opportunity. Nothing collapses a regional or staged deadline into a
single fake national date.

The shape is **derived inside `detect_changes_for_version` from the new
fields** — an earlier cut derived it only on the live path, so
`backfill_change_events` wrote deadline events with a NULL shape and the health
phase correctly reported `deadline_change_with_no_recorded_shape: 1`.

## 4. Multi-source (170G–170I)

### Corroboration is agreement, not a repeated transition

The first design keyed corroboration on the version pair. It **could never
fire**. Two sources observing the same opportunity carry different
`source_record_id` values, so their content fingerprints differ, so their
version ids differ — and once they share a canonical version chain, the second
source to report a change produces no diff at all.

So corroboration is scored over a **semantic index**
`(canonical_id, field_name, prior_value, new_value)`, and a source whose
observation carries the **new value** of a recorded change is confirming that
change, whether or not it ever reported the old one.

Measured: the cross-source sweep produced **one event with
`corroborating_source_count = 2`** and the aggregator named in its source list —
one event with a count of two, not two competing alerts. Sequential agreement
(a source arriving later with the value already recorded) created **no new
event**.

```sql
CHECK (corroborating_source_count >= 1)
```

### Conflicts are a row with a duration

```text
UNIQUE (canonical_id, field_name)     -- one row per contested field
first_detected_at                     -- never rewritten
last_observed_at                      -- advanced on each sighting
```

So "these sources have disagreed for eleven days" is answerable. Both sides are
preserved — **nothing collapses a contested field to a winner** — and all four
field-provenance rows survive a conflict.

```sql
CHECK (conflict_state = 'NO_CONFLICT' OR competing_source_count >= 2)
CHECK (conflict_state <> 'RESOLVED_CONFLICT'
       OR (resolved_at IS NOT NULL AND resolved_by IS NOT NULL
           AND resolution_evidence_json IS NOT NULL))
```

A resolution must name **who** and **by what rule** and carry evidence.
`resolve_conflict` raises `ChangeWriteRefused` otherwise. Measured: an unsigned
resolution was refused; resolving one field **closed that field and left the
other contested**.

## 5. Lifecycle (170J–170L)

| transition | event |
|---|---|
| forecasted → posted | `FORECAST_TO_POSTED` |
| posted → closed | `POSTED_TO_CLOSED` |
| closed → posted | `REOPENED` |
| posted → cancelled | `CANCELLED` |
| anything unmodelled | `STATUS_CHANGED` (not a guess) |

Measured: both `POSTED_TO_CLOSED` and `REOPENED` were observed and **the
opportunity did not fork** — a reopen is a new version of the same canonical
record, not a second opportunity.

Amendment vs recurrence, both confirmed:

- an **amendment** → same `canonical_id`, new version, change events
- an **FY27 recurrence** of the same program → a **different** `canonical_id`

`source_record_id` is in `SOURCE_SCOPED_FIELDS` and is skipped during
classification. It is per-source bookkeeping; left in, it generated
`UNKNOWN_CHANGE` events that reached the customer feed.

## 6. Replay and rebuild (170M)

- **No-op replay:** 4 statements, and **no version, no event, no conflict row**
  written.
- **Rebuild from evidence:** identical event ids, types, materiality, evidence
  hashes and deadline shapes. A second rebuild wrote **nothing** — the derived
  ids collide on the primary key.
- Gate 169's human identity decisions **replay from storage** rather than being
  recomputed, so a rebuild cannot invent a merge nobody approved.

## 7. Scale (170N)

| | |
|---|---|
| opportunities | 10,001 |
| observations | 50,001 |
| change events | 111,010 |
| versions | 31,001 |
| conflicts | 40 |
| DB growth | 459.79 MB |

**The unchanged case is the one that matters at fleet scale** — most polls
change nothing:

| case | statements / observation | rate |
|---|---|---|
| unchanged | **0.016** | **1,740/sec** |
| changed | 2.024 | 294/sec |

a **3.7× separation**, and the unchanged path is effectively free. Every
change-event and conflict lookup is index-backed at **under 0.2 ms**.

Gate 168's profiler is authoritative on the write path and it **failed this
gate three times** for unattributed statements (blocking-key insert, blocking-key
lookup, change-event statements). Each failure was the check working. The
profile now attributes every statement by name:

```text
CHANGE_EVENT_LOOKUP  CHANGE_EVENT_INSERT
CHANGE_EVENT_CORROBORATION  CONFLICT_STATE_WRITE
```

After change events: **first observation 15 statements, idempotent replay 4**,
all classified, zero UNKNOWN.

## 8. Safety and the customer read model (170O–170P)

The customer feed is an **allowlist** of 14 keys. A denylist is a list of the
things somebody remembered. On top of the allowlist a **negative proof** runs
over the serialized output looking for forbidden markers
(`change_event_id`, `new_version_id`, `raw_payload_sha256`,
`materiality_rule`, …).

The read model **withholds the rule name while showing the explanation**. The
rule is engineering vocabulary for arguing about a classification; the
explanation is what a Tribe reads. Materiality is translated out of internal
classes into customer importance — `CRITICAL → act_now`.

`read_model_invariant_failures` refuses a feed that leaks a marker, carries a
key outside the allowlist, or reports `notifications_sent > 0`.

**Health (`build_change_health`)** measures **12 conditions**, six of them
**passed in from the phases that actually measured them** rather than
re-asserted locally. Measured: `change_intelligence_ready: true`, **zero named
gaps**, all 12 conditions met; a forged readiness flag was caught; and a
condition that was never measured is **named rather than assumed true**.

## 9. Validation

| | |
|---|---|
| `scripts/verify_nativeforge_change_intelligence.sh` | `RESULT=PASS`, 90 checks, `gate170_ready=true` |
| `tests/test_gate170_change_intelligence.py` | 61 passed |
| head-pin battery (63, 119, 120, sprint20, 153) | 244 passed |
| full suite | green (see gate report) |
| ruff · `bash -n` · `git diff --check` | clean |
| funding-source network requests | **0** |
| fixture residue | **0** |

Registry lane: `change_intelligence_ready`, blocking, depends on
`canonical_opportunity_store` and `cross_source_identity`.

---

## What this gate did not do

- did not activate another live source, and made **no** funding-source request
- did not refetch Grants.gov
- did not add LLM change judgment
- did not weaken Gate 169 identity semantics
- did not create a second version ledger or a second diff
- did not collapse conflicting source facts
- did not build customer notification delivery — `notifications_sent = 0`
