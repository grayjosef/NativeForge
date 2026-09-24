# 866 — Gate 179: customer experience, customisation, industrial scale

## What the survey found

```text
buyer_feed_depends_on_hand_made_sparks = true
api_imports_canonical_intelligence     = false
canonical_modules_with_no_importer     = [canonical_opportunity_store_service,
                                          document_fact_extraction_service]
```

Nine gates of intelligence — the canonical graph, Native relevance,
eligibility, document evidence — and **not one of them reached a buyer**.
Seven customer-facing route modules referenced demo fixtures. Gate 167's
opportunity store, the spine of everything built in 167→175, had no importer
at all.

A workspace built on hand-made sparks demonstrates beautifully and tells you
nothing about whether the intelligence works.

Supporting findings:

| | |
|---|---|
| Watch/dismiss/pursue durable? | **No** — 457 + 124 rows recording no actor |
| Source fleet | 40 monitored, 3 active |
| Postgres concurrency | never measured |

## What was built

| Concern | Module |
| --- | --- |
| Recommendations + explanations | `customer_opportunity_feed_service.py` |
| Durable watch/dismiss/pursue | `customer_decision_service.py` |
| Dashboard, capability boundary, trust | `customer_surface_service.py` |
| Deterministic demo story + UX checklist | `customer_demo_story_service.py` |
| Nine detectors and their proofs | `customer_self_health_service.py` |
| Five indexed read paths | `customer_repository_service.py` |
| Durable decisions and history | `alembic/versions/0065_*.py` |

## Every recommendation must explain itself

179C asks four questions of each opportunity. A recommendation that cannot
answer them is a guess with a confident font, and a Tribal government acting
on it spends weeks on an application they were never eligible for.

Refused outright:

- a recommendation with **no canonical opportunity** behind it (two
  independent invariants)
- a decisive relevance claim **citing no evidence**
- `CONDITIONAL` eligibility that does not **name its condition**
- `APPEARS_INELIGIBLE` that does not **name its blocker**
- a document citation **carrying no quote**

### UNKNOWN survives to the surface

`ELIGIBILITY_UNCERTAIN` and `NOT_ASSESSED` are distinct, and uncertainty that
failed to reach `known_unknowns` is itself a failure. The temptation at the
presentation layer is to turn UNKNOWN into a clean answer, because
"eligibility unclear" looks unfinished next to "eligible". A system that
hides its uncertainty is not more useful — it is more confident about the
wrong things.

### Ordering is named, never scored

A feed whose order is a secret number cannot be argued with. The ordering is
one of four named criteria, it is reported, and the customer can change it.

## Dismiss is a tenant preference, not a fact about the world

When one organisation dismisses an opportunity it is still in the canonical
graph, still Native-relevant, still recommended to every other tenant, and
still carries all of its evidence.

The failure this prevents is quiet and severe: a system where dismissing
deletes intelligence lets **one person's tidy-up remove a funding opportunity
from every Tribe in the product**, and nobody finds out until a deadline has
passed.

Every decision names an actor and a time — the survey found 581 rows
recording neither — history is appended rather than overwritten, and every
state is reversible, because a dead end in a workflow about money is a
support ticket.

## The customer/operator boundary

`CUSTOMER_CAPABILITIES` and `OPERATOR_CAPABILITIES` are **disjoint sets**, not
a UI convention. A customer cannot reach source activation, a demo/real plane
toggle, a verifier surface, or an entitlement override.

Those are not merely confusing. `ACTIVATE_SOURCE` is an instruction to start
fetching somebody else's website in NativeForge's name; a plane toggle lets a
customer look at the wrong data and believe it.

The refusal **walks the whole payload**, so an internal field cannot reach a
customer by being nested inside a serialiser somebody forgot to filter —
proven by catching `dashboard.deadlines.lease_id`.

## The 1,000-source rehearsal

1,200 synthetic sources, twelve publisher kinds, nine health states. 666 of
them refused on state. Leases distributed fairly across 24 workers (22–23
each, spread ≤ 1).

### The catastrophe, measured rather than assumed absent

| | |
| --- | --- |
| `opportunity × tenant × document` | **30,000,000** |
| Global relevance (once per opportunity) | 20,000 |
| Document extraction | 60,000 |
| Tenant matching (bounded, capped) | 100,000 |
| **Avoided by** | **166.7×** |

Global intelligence is computed **once per opportunity**, not once per
tenant. At four tenants in development, the naive version looks fine.

## What this gate reports rather than claims

```text
claims_real_thousand_source_coverage = false
postgres_concurrency_status          = UNKNOWN_NOT_MEASURED
```

**The rehearsal is architecture, not coverage.** NativeForge monitors 40 real
sources and 3 active ones. "We rehearsed 1,000 sources" and "we monitor 1,000
sources" are a sentence apart and a company apart.

**SQLite proves** single-writer serialisation, that the schema's constraints
hold under write, and index selection for these query shapes. **It proves
nothing** about Postgres row-level locking, concurrent writer throughput, or
contention under load. No such harness has been run, so 179K's honest value
is the one reported.

## The demo story and the checklist

The story runs **only** on the protected demo organisation and refuses the
real one in every spelling — dashed, undashed, upper-case. It is
byte-deterministic, so a UI change that breaks something is visible.

The UX smoke checklist for Claude Design arrives with every result
`NOT_YET_WALKED` and `customer_ready` unset. Claude Code has not navigated a
UI; a checklist pre-marked PASS would answer the question it exists to ask.

Artifacts: `artifacts/customer_experience_gate179/`

## What the instruments found

**The zero-row rule fired twice.** First on `expiring_maintenance` in Gate
178, then here on `decision_for_opportunity` and `decision_history` — the
scale fixture never produced the org+opportunity pair the read-path contract
names, so both queries returned nothing with a perfect query plan. The sample
parameters are the contract; the fixture was corrected to satisfy it, rather
than the sample edited to match whatever the generator happened to emit.

## Running it

```bash
bash scripts/verify_nativeforge_customer_scale_gate179.sh
```
