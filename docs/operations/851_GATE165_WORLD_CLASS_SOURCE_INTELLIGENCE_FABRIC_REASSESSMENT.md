# Gate 165 — World-Class Source Intelligence Fabric Reassessment

**Type:** reassessment. No production code changed. No funding source contacted.
**Baseline:** `8a52310`. **Network requests during Gate 165: 0.**
**Diagnostic artifact:** `scripts/_g165_scale_probe.py` (reads only).

---

## 1. Current platform substrate

Gates 156–164 built a **collection and evidence substrate**, and it is the
strongest part of the system:

| Layer | Module | State |
|---|---|---|
| Registry | `source_monitoring_approved_source_service` | CSV, 178 rows, uncached |
| Authorization | `source_live_authorization_service` + `source_authorization_fact_resolver_service` | 11 resolved facts |
| Warrant | `source_live_warrant_service` | hardcoded `frozenset` |
| Capability | `source_collector_capability_service` | 6 checks, per-adapter |
| Scheduling | `source_collection_scheduler_loop_service` | leases, retry, circuit |
| Transport | `source_collection_transport_service` | method + robots enforcement |
| Persistence | `source_collection_raw_payload_persistence_service` | sha256-addressed |
| Replay | `source_collection_raw_payload_replay_service` | byte-exact |
| Audit | `live_collection_audit_service` | composes, does not duplicate |
| Health | `live_evidence_health_service` | 6 statuses, gaps NAMED |
| Provenance | `live_collection_customer_provenance_service` | allowlist DTO |
| Build context | `canonical_artifact_build_context_service` | `ContextVar`, refuses ambient |

Proven end-to-end exactly once: one POST to `api.grants.gov/v1/api/search2`,
11,131 bytes, sha256 `eb4cc7cb…1712`, replayable, attributable, HTTP status
honestly `UNKNOWN`.

**What the substrate is:** a defensible chain of custody from a byte on the
wire to a customer-facing provenance record.
**What the substrate is not:** anything that turns those bytes into an
opportunity.

---

## 2. Generic vs source-specific classification

**Genuinely generic (survives to 1,000 sources unchanged):**
transport boundary · robots evidence · payload persistence · replay ·
attempt/job/lease repositories · scheduler loop · circuit breaker ·
audit composition · evidence health · build context · provenance DTO.

**Generic but wrongly parameterized:** authorization fact resolution
(§4) — org-wide work invoked per source.

**Source-specific by necessity:** adapter capability descriptors, request
shape, response parsing. These *should* be per-source; the question is
whether they live behind a contract (they do not yet — §6).

**Source-specific by accident:** `AUTHORIZED_SOURCE_IDS`, `POST_BASELINE_SEED_IDS`.

---

## 3. Source-specific leakage into generic layers

Measured by scanning the generic collection path for `grants.gov` /
`search2` / `tribal`:

| Module | Hits | Verdict |
|---|---|---|
| request_builder, execution_policy, scheduler_loop, raw_payload_persistence, raw_payload_replay, job_repository, raw_payload_repository, execution_attempt_repository, live_collection_audit, live_evidence_health | **0** | clean |
| `source_collection_transport_service` | 3 | DOC_ONLY — docstring, a comment above a generic `ALLOWED_METHODS`, one legacy-transport record |
| `source_collection_worker_runtime_service` | 1 | DOC_ONLY — names a fixture |

**The collection path is clean.** The leak is not in the plumbing; it is in
the gate:

```python
# source_live_warrant_service.py:73
AUTHORIZED_SOURCE_IDS: frozenset[str] = frozenset(
    {"nf-seed-2026-api-grants-gov-search2"}
)
```

This was the right Gate 163 decision and is the wrong Gate 166 one. The
authorization it encodes **already exists as data** — a signed row in
`nf_source_authorization_decisions` (3 rows) and an activation row in
`nf_active_opportunity_sources` (1 row). The frozenset duplicates an
accountable record as an unaccountable constant, and makes every future
activation a code change plus a deploy.

---

## 4. Scale analysis — measured, not estimated

`scripts/_g165_scale_probe.py`, 178-row registry, 2 payloads, 1 attempt:

```
one authorization            332.3 ms
registry parses per auth     5
CSV share of that cost       3.14 ms  (0.9%)
```

**The CSV is not the problem.** Profiling the same call attributes the cost:

| Frame | Cumulative | Takes `source_id`? |
|---|---|---|
| `resolve_source_authorization_facts` | 160 ms | yes |
| ↳ `_resolve_runtime` → `build_runtime_readiness_facts` | 102 ms | **no** |
| ↳ ↳ `build_scheduler_readiness` | 51 ms | **no** (repo-wide) |
| ↳ ↳ `build_execution_health` ×2 | 99 ms | **no** (org-wide) |
| ↳ `_resolve_collector` → `measure_collector_capability` | 49 ms | **yes** |

**~70% of per-source authorization cost is fleet-wide work with no
`source_id` parameter.** A 1,000-source sweep recomputes the same answer
about scheduler readiness and execution health 1,000 times.

Projected full-fleet authorization sweep:

| Sources | Today | After hoisting fleet facts |
|---|---|---|
| 10 | 3.3 s | ~1 s |
| 100 | 33 s | ~10 s |
| 1,000 | **361 s** | **~110 s** |
| 5,000 | **2,512 s (42 min)** | **~550 s** |

*Correction on the record:* an earlier projection reported 45,652 s (12.7 h)
at 5,000 sources. That model multiplied the **whole** per-source cost by
registry growth. Only the 0.9% CSV component grows with the registry. The
corrected figure is 2,512 s.

**UNKNOWN:** fact-resolution cost as payloads/attempts reach millions;
concurrent worker contention; write-lock behaviour under parallel
collection; any production database engine. No load test exists.

---

## 5. Source factory readiness

Adding source #2 today requires: a CSV row, an adapter capability
descriptor, **an edit to `AUTHORIZED_SOURCE_IDS`**, an edit to
`POST_BASELINE_SEED_IDS`, an `EXPECTED_ROW_COUNT` bump, regenerated
artifacts, and a deploy.

That is **not a factory**. It is six coordinated edits per source, with a
full-suite risk surface each time (Gates 163 and 164 both proved that).

Three disjoint registries compound it:

| Store | Rows | Holds |
|---|---|---|
| seed CSV | 178 | adapter keys, endpoints |
| `nf_opportunity_sources` | 40 | health, scheduling, coverage, relevance |
| `nf_active_opportunity_sources` | 1 | live activation |

The richest source metadata in the system — `check_interval_days`,
`consecutive_failure_count`, `source_health_status`,
`covered_tribal_groups_json`, `native_relevance_notes` — lives in
`nf_opportunity_sources`, which the Gate 156–164 path **does not read**
(only five unrelated artifact/health services do).

---

## 6. Proposed source adapter contract

```python
class SourceAdapter(Protocol):
    source_id: str
    transport: TransportSpec        # method, auth, rate, robots authority
    request: RequestSpec            # pagination, cursor, bounded params
    def parse(payload: bytes) -> Iterable[CanonicalOpportunity]: ...
    def identity(record) -> OpportunityIdentity   # delegates to 92E
    capability: CapabilityDescriptor
```

Authorization derives from **records**, never from a module constant.
Everything source-specific lives behind `parse` and the two specs;
everything else is already generic today.

---

## 7. Canonical opportunity graph — the decisive gap

**There is no opportunity table.** Zero tables match `opportunit*`,
`notice*`, or `discover*`. The collection path ends at
`nf_source_collection_raw_payloads` (2 rows). Normalization is derived at
read time from bytes and never persisted.

But the model is **not missing — it is unwired.** Gates 82/92 already built
it, well:

- `opportunity_identity_versioning_service` — layered identity (L1
  normalized `opportunityNumber`, numeric surrogate, version key, fuzzy
  fallback), because "federal grant data has no single global identifier."
  **Production callers: zero.** One test file imports it.
- `opportunity_deadline_and_amendment_model_service` — five verified
  deadline shapes (dual DOJ/JustGrants, per-region EPA GAP, revised HUD),
  amendment materiality classification. Called only by the tenant digest
  services, never by collection.
- `notice_ingestion_pipeline_service` — artifact → text → eligibility with
  refusal semantics. Called by document extraction, never by collection.
- `discovery_intake_dedupe_fingerprint_service` — explicitly "advisory only."

**This is the single most important finding of Gate 165.** The hard design
work — the research that knows a single-date model is wrong for nine EPA
regions — is already done, tested, and disconnected. The system has a
world-class evidence substrate and a well-researched opportunity model, and
**they have never been introduced to each other.**

---

## 8. Dedupe / entity resolution

Primitives exist (`compute_duplicate_key`,
`compute_structural_duplicate_fingerprint`, fuzzy fallback keys) and are
advisory-only with nothing to write to. Cross-source resolution — the same
NOFO on Grants.gov, an agency page, and a Federal Register notice — has no
home because there is no canonical record to resolve *to*. **Not started.**

---

## 9. Fleet health model

Per-source health columns exist and are unused by the live path.
`nf_source_check_runs` and `nf_source_orchestration_cycles` are **empty**.
Health today is org-wide (`build_execution_health`), which is why it is
recomputed per source. A fleet model needs per-source SLO, staleness
budget, and circuit state as first-class rows — the columns are already
designed in `nf_opportunity_sources`.

---

## 10. Early-signal readiness

**1/10.** Nothing forecasts. No Federal Register lane, no forecast-vs-posted
transition tracking, no pre-announcement detection — despite the one live
payload containing a *forecasted* opportunity (`oppStatuses=posted|forecasted`,
O-BJA-2026-172662 opening 07/24/2026). The signal was collected and
discarded.

---

## 11. Native relevance data flow

`covered_tribal_groups_json`, `native_relevance_notes`, `covered_states_json`
sit in `nf_opportunity_sources`, disconnected. `nf_source_watchlist_entries`
holds 457 rows. Relevance is currently a **source** attribute; it must
become an **opportunity** attribute, which requires §7 first.

---

## 12. World-class scorecard

| # | Dimension | Score | Evidence | Gap | +1 requires |
|---|---|---|---|---|---|
| 1 | Evidence integrity & provenance | **9** | sha256 addressing, byte-exact replay, tamper refusal at schema, named gaps | HTTP status UNKNOWN on the one live record | capture the full response envelope at the boundary |
| 2 | Authorization governance | **8** | 11 facts, signed decisions, unfalsifiable-refusal discipline | authority duplicated in a frozenset | derive the warrant from decision rows |
| 3 | Collection transport | **7** | method + robots enforcement, RFC 9309 scoped per authority | one proven source; no pagination, no auth schemes | exercise a second, differently-shaped transport |
| 4 | Source onboarding / factory | **3** | adapter descriptors exist | six coordinated edits + deploy per source | registry-derived authorization |
| 5 | Canonical opportunity graph | **2** | model designed (92E/92G) | no table, zero production callers | the store + the writer |
| 6 | Dedupe / entity resolution | **2** | fingerprint primitives | advisory only, nothing to resolve to | identity applied at write time |
| 7 | Amendment & change detection | **3** | five deadline shapes, materiality classifier | not wired to collection | supersession lineage on canonical records |
| 8 | Fleet health & observability | **5** | rich columns, good indexes | org-wide not per-source; two tables empty | per-source health rows |
| 9 | Scale & concurrency | **4** | org-scoped composite indexes throughout | 70% of auth cost is fleet-wide per source; zero load tests | hoist fleet facts; measure concurrency |
| 10 | Native relevance | **4** | coverage + relevance columns, 457 watchlist rows | attribute of source, not opportunity | relevance on canonical records |
| 11 | Early signal | **1** | forecast data collected once | discarded | a forecast→posted transition lane |
| 12 | Multi-tenancy | **7** | org scoping on every index and query | tenant binding to canonical graph absent | watchlist → opportunity binding |

**As an evidence substrate: 9/10.**
**As a source intelligence system: 4.2/10.**

That gap is not a failure — it is the correct build order. The hard,
unforgiving layer was built first. Most systems in this space do the
reverse and can never retrofit provenance.

---

## 13. Blockers to 9.5+

1. **No canonical opportunity store.** Everything downstream — dedupe,
   amendments, relevance, early signal, tenant matching — is blocked on one
   table and one writer.
2. **Authorization by source code.** Caps the fleet at whatever a reviewer
   will hand-edit.
3. **Fleet facts resolved per source.** 3x cost at every scale.
4. **Three disjoint registries.** The richest metadata is invisible to the
   live path.
5. **Zero load evidence.** Concurrency, contention, and million-row
   behaviour are all UNKNOWN.

---

## 14. Proposed Gate 166–180

Gate numbers are **not** preserved for their own sake; this is a rebuild of
the sequence around dependency order.

**Phase A — unlock the factory (166–169)**
- **166** Derive the live warrant from `nf_source_authorization_decisions` +
  `nf_active_opportunity_sources`. Delete `AUTHORIZED_SOURCE_IDS`. Preserve
  every refusal; change only where authority is *read from*.
- **167** Unify the three registries into one authoritative source table;
  cache the registry; retire `POST_BASELINE_SEED_IDS` / `EXPECTED_ROW_COUNT`
  coupling.
- **168** Sweep-scoped fleet fact resolution (resolve once, pass in). ~3x.
- **169** Formalize the `SourceAdapter` contract (§6).

**Phase B — the canonical graph (170–173)** ← *highest value*
- **170** `nf_opportunities` + the writer. Wire `opportunity_identity_versioning_service` in.
- **171** Payload → canonical record with parse provenance (which payload,
  which parser version, which bytes).
- **172** Identity + dedupe at write time; cross-source resolution.
- **173** Amendment lineage and supersession using `opportunity_deadline_and_amendment_model_service`.

**Phase C — prove genericity (174–176)**
- **174** Activate sources #2 and #3 **through the factory**, differently
  shaped (one HTML, one paginated). No new gate-era scaffolding permitted.
- **175** Per-source fleet health; populate `nf_source_check_runs`.
- **176** Concurrency and load proof — the first real answer to §4's UNKNOWNs.

**Phase D — intelligence (177–180)**
- **177** Native relevance scoring over canonical records.
- **178** Tenant watchlist → canonical graph binding.
- **179** Early-signal lane (forecast → posted transitions).
- **180** 1,000-source scale rehearsal.

---

## 15. What should NOT be built

- **Another hardening gate over the evidence layer.** It is 9/10. Further
  hardening there is the highest-cost, lowest-value work available.
- **Per-source bespoke services.** The leak scan is clean; keep it clean.
- **An LLM extraction layer before the canonical store exists.** It would
  have nowhere to write and no identity to attach to.
- **A second ledger.** Gate 164 explicitly avoided one; keep composing.
- **Any refetch of Grants.gov** to "fix" the UNKNOWN HTTP status.
- **A scheduler rewrite.** Leases, retry, and circuit breaking are sound.

---

## 16. UNKNOWNs

- Fact-resolution cost at millions of payloads/attempts — no load test.
- Concurrent worker behaviour; write-lock contention.
- Production database engine characteristics (measured on SQLite).
- Parse cost for HTML sources (only one JSON API proven).
- Whether `nf_opportunity_sources`' 40 rows are trustworthy or stale.
- Real-world robots/rate-limit posture of the other 177 sources.

---

## 17. Final reassessment

**A. Can this substrate support 1,000+ sources without source-specific
spaghetti?** **Yes** — and that is the real result of Gate 165. The
collection path scored **zero** source-specific hits across ten core
modules. The obstacles are three named, local, fixable items (a frozenset,
an uncached loader, a mis-parameterized resolver), not architectural
contamination. This substrate was built generic and stayed generic under
the pressure of a real activation.

**B. Permanent primitives.** Transport boundary + robots enforcement ·
sha256-addressed payload persistence · byte-exact replay · attempt/job/lease
repositories · scheduler loop · `ContextVar` build context · composed audit ·
named-gap evidence health · allowlist provenance DTO · org-scoped composite
indexes.

**C. Gate-era scaffolding to retire.** `AUTHORIZED_SOURCE_IDS` ·
`POST_BASELINE_SEED_IDS` · `BASELINE_ROW_COUNT`/`EXPECTED_ROW_COUNT`
coupling · per-gate artifact services (156/157/162/164) once a general
fleet report exists · the seed CSV as an authority.

**D. Single highest-leverage next build.** **The canonical opportunity store
(Gate 170), with Gate 166 immediately before it.**

166 is smaller and unblocks the factory. But 170 is where the system stops
being an evidence pipeline and starts being *intelligence*. The strongest
argument for it: the model is already built, researched to a level most
teams never reach — it knows a national deadline is wrong for nine EPA
regions — and **nothing in production calls it.** That is finished work
sitting unused. Wiring it in is the highest value-per-unit-risk change
available.

**E. What prevents 9.5+ today.** The system can prove where a byte came
from and cannot tell you what it means. Every customer-facing capability —
matching, deadlines, amendments, relevance, alerts — is blocked behind one
missing table. Gates 156–164 built the layer that is hardest to add later.
The next four gates must build the layer that makes it worth having.

**Score: 9/10 as an evidence substrate. 4.2/10 as a source intelligence
system. One table and four gates from 8+.**
