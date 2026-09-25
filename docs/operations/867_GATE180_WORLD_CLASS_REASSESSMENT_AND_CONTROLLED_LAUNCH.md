# Gate 180 — World-Class Reassessment and Controlled Customer Launch

**This is not a celebration gate.** Gates 176–179 added early signals, Tribal authority,
commercial entitlements and the customer surface. This gate asks what the system
actually does, what it cannot do, and whether a real Tribal government should be
onboarded to it yet.

The answer to the last question is **no**, and the reason is not readiness theatre.

---

## The one-sentence reassessment

> **NativeForge has built a rigorous funding-intelligence fabric and has not yet
> pointed it at the world.**

The machinery is real: 13 gate verifiers pass, 13,695 tests pass, and in several places
the system refuses to state a number it cannot justify. The operation is near zero:
**three active sources, all scoped to the protected demo organisation, with live
collection deactivated.**

Both halves are evidenced below. Neither cancels the other, and this gate is written to
stop the first half from being mistaken for the second.

---

## 180A — Capability scorecard

Scored on **proven behaviour**, not code volume. Service counts are deliberately not
used: a capability with eighty-four files and no real input is not an eighty-four.

| State | Meaning |
| --- | --- |
| **PROVEN** | exercised by a passing verifier against the real service |
| **BUILT-UNPROVEN** | implemented and tested, never run against real-world input |
| **DEMO-ONLY** | operates exclusively on fixtures |
| **ABSENT** | not built |

| # | Capability | State | Evidence |
| --- | --- | --- | --- |
| 1 | Source authorization | **PROVEN** | DISCOVERED ≠ AUTHORIZED ≠ APPROVED ≠ LIVE enforced; `collector_activated: false` |
| 2 | Source breadth architecture | BUILT-UNPROVEN | registry supports breadth; **40 rows, all `source_type='federal'`** |
| 3 | Fleet health | BUILT-UNPROVEN | Gate 172 passes; three demo sources is not a fleet |
| 4 | Freshness | BUILT-UNPROVEN | modelled; no real cadence baseline exists |
| 5 | Canonical opportunity graph | **PROVEN** | Gates 167/168; 10,022-row scale run |
| 6 | Provenance | **PROVEN** | evidence attribution enforced end to end |
| 7 | Zero-network replay | **PROVEN** | `network_requests=0` asserted per gate, self-checked |
| 8 | Identity / deduplication | **PROVEN** | Gate 169 cross-source identity |
| 9 | Change intelligence | **PROVEN** | Gate 170 — see the caveat below |
| 10 | Native relevance | BUILT-UNPROVEN | Gate 173 passes on fixtures; **fed by a keyword-built catalogue** |
| 11 | Eligibility | **PROVEN** | Gate 174; typed requirements, deny-by-default, legal classes kept distinct |
| 12 | Document intelligence | BUILT-UNPROVEN | Gate 175 passes; no real NOFO corpus ingested |
| 13 | Early signals | **DEMO-ONLY** | Gate 176; thirteen signal types, near-zero real input |
| 14 | Award / miss detection | **DEMO-ONLY** | `real_award_evidence_available_for_miss_detection` is **false**; all **2,757** award rows are Gate 138 demo fixtures, none carrying `source_opportunity_id` |
| 15 | Recurrence | **DEMO-ONLY** | `MINIMUM_CYCLES_FOR_CADENCE = 3`; no real cycles observed |
| 16 | Coverage gaps | **PROVEN, as honesty** | the scorecard **refuses to report a percentage** — the denominator is unknown and this system has no way to learn it |
| 17 | Authority verification | **PROVEN** | Gate 177; identity/affiliation/authority as three columns, CHECK-constrained |
| 18 | Organization onboarding | **PROVEN** | Gate 177; RECOGNIZED / AMBIGUOUS / LOOKUP_MISS / EXPLICITLY_EMPTY |
| 19 | Commercial entitlements | **PROVEN** | Gate 178; consortium refuses to compute a price it cannot justify |
| 20 | Tenant isolation | **PROVEN** | Gate 179; whole payload walked, capability sets disjoint |
| 21 | Customer workflow | PROVEN **on demo data** | Gate 179; feed refuses a recommendation with no `canonical_id` |
| 22 | Tenant customization | **PROVEN** | Gate 177; personal override deep-copies, org default unchanged |
| 23 | Scale | PROVEN **synthetically** | 10,022 canonical / 111,144 change events / 1,200-source rehearsal |
| 24 | Operational readiness | BUILT-UNPROVEN | artifacts exist; no production run |
| 25 | Security | BUILT-UNPROVEN | hermetic network enforcement proven; no production auth in use |
| 26 | Observability | BUILT-UNPROVEN | readiness artifacts; no live telemetry |
| 27 | Supportability | **ABSENT** | no support runbook for a real customer; no incident owner named |

**PROVEN 12 · BUILT-UNPROVEN 10 · DEMO-ONLY 3 · ABSENT 1 · PROVEN-as-honesty 1.**

Every capability that has never met real-world input is marked so, including ones with
extensive test coverage. A verifier passing against fixtures proves the mechanism, not
the capability in the world.

### The Gate 170 caveat

Gate 170 failed once inside a battery run on `j_reopened_seen`, then passed **eight
consecutive times**: standalone, after 167→169, four repeat phase runs, a 13/13 battery
with its input snapshotted, and the post-commit battery. Cross-gate ordering, seed
collision and phase nondeterminism were each tested and eliminated; the snapshot showed
gate 170's input identical to the passing runs.

**The single failure is unexplained.** Its input state was not captured at the time and
is gone. Change intelligence is scored PROVEN on eight passes and one unreproducible
failure, and that failure is recorded here so that a recurrence reads as a pattern
rather than a first.

---

## 180B — World-class questions

### What can still make us miss important Native funding?

This has a **measured** answer, and it is the most serious finding in this gate.

Parallel source-expansion research measured Grants.gov on 2026-09-24:

| Measure | Count |
| --- | --- |
| Posted opportunities | 946 |
| Open to federally recognized Tribal governments (eligibility `07`) | **464 (49%)** |
| Open to tribal organizations, other (`11`) | 418 |
| Open to Indian housing authorities (`08`) | 379 |
| Keyword `tribal` finds | 276 |
| **Of the first 100 elig-07 titles, containing trib/indian/native/alaska** | **4** |

> **Roughly 96% of the federal opportunities a Tribe is eligible for do not announce
> themselves as Native programmes.** The 40-row catalogue was assembled by Native-keyword
> programme search and structurally cannot see them.

Second measured answer: **375 of the 464 (81%) are HHS/health.** Housing 2,
Transportation 3, Energy 3. Infrastructure money reaches Tribes through formula funds,
set-asides, state revolving-fund pass-through and regional commissions — none of which
is represented. Corroborated: a Grants.gov keyword search for `denali` returns **zero**,
so an entire federal agency funding Alaska Native village infrastructure publishes
nothing there. *(One keyword query; it establishes non-discoverability by agency name,
not complete non-overlap.)*

Third: **zero** state, philanthropy, regional-authority or utility coverage.

### What evidence can still become stale silently?

Demonstrated during this gate, twice. Two committed artifacts drifted for the entire
176–179 block — a migration head pin (`0061` against a real head of `0065`) and a file
count (1250 against 1276) — and **both the focused verifiers and the 13/13 sequential
battery passed while they were wrong.** Only the three-hour authoritative suite caught
them, about three hours in.

Rebuilding those two artifacts and diffing takes seconds. That cheap check is worth more
than the fix was.

Also stale by construction: at least five registry rows point at single-opportunity
detail URLs that will rot, and one of the three active sources is
*"BIA / Interior — Tribal Tourism Grant Program"* — **a programme stored as a source**.

### What eligibility cases remain dangerous?

Codes `07`, `11` and `08` name three distinct legal classes, and the publisher's own
facet labels distinguish them. The danger is any downstream code that collapses "Native"
into one bucket. Gate 174's deny-by-default and `ELIGIBILITY_TRANSFERS` hold today;
ingesting broad-eligibility sources at volume is what will pressure them.

**Newly surfaced:** moving discovery from keyword to eligibility facet moves trust from
*our* heuristic to *the publisher's* coding. That is a better place for trust — it is the
publisher's own assertion about who may apply — but a programme miscoded by its agency
is invisible to eligibility filtering exactly as it is to keyword search. Spot-audit it;
do not assume it.

### What document formats remain unsupported?

UNKNOWN. No real NOFO corpus has been ingested. Federal Register **document hosts**
redirect to an anti-automation interstitial, so that corpus is unavailable without
publisher contact — distinct from the Federal Register **JSON API**, which is public and
usable.

### What source families remain unknown?

Measured as absent: state portals, philanthropy, regional authorities, utilities, state
revolving funds, Tribal enterprises, Native Hawaiian organisations. Fourteen states had
no first-party funding surface discoverable by the methods used.

### What customer workflow is still awkward?

UNKNOWN in the only sense that matters — no real customer has used it. Gate 179's UX
smoke checklist is a self-assessment, not an observation of a person.

### What production dependency is unproven?

All of them: production database, object storage, secrets management, email provider,
auth provider, domain and TLS, monitoring.

### What can still leak across tenants?

Gate 179 proved isolation on the paths it walked. No adversarial penetration testing has
been done and no real second tenant exists.

### What operational state can become inconsistent?

Source health baselines (none real), freshness expectations (none measured), scheduler
and lease state (never run continuously).

**Unmodelled risk:** vendor concentration. Euna absorbed eCivis (2023) and AmpliFund
(2025), making many state, county and tribal portal instances a **correlated failure
domain**. Gate 172 models per-source health and does not represent correlated failure.

### What is still demo-only?

Early signals; award and miss detection (2,757 fixtures, zero real); recurrence; every
customer workflow; all three active sources.

### What remains impossible to prove locally?

Production authentication with a real second identity; email delivery; live source
collection under publisher terms; sustained scheduler operation; any claim about real
customer behaviour.

---

## 180C — Controlled customer launch checklist

**Verdict: not ready for a first real customer.**

| Area | Item | State |
| --- | --- | --- |
| Customer org | real org created intentionally | NOT DONE — real org is no-touch without authorization |
| | authority verified | mechanism PROVEN; never exercised on a real Tribe |
| | responsible customer admin · support contact | UNKNOWN |
| Identity / auth | production authentication exists | **NO** — `customer_auth_live: false` |
| | second real identity tested | NO |
| | MFA / provider policy | UNKNOWN |
| | role boundaries tested | PROVEN on demo data |
| Commercial | signed / approved terms | NOT DONE — exact wording remains with counsel |
| | licence recorded · maintenance period | mechanism PROVEN; no real licence |
| | extension authority limited | PROVEN — extension changes benefit only |
| Consent / beta | customer understands controlled beta | NOT DONE |
| | limitations stated | **this document is the first complete statement** |
| | escalation path · rollback owner | ABSENT |
| Data | tenant isolation tested | PROVEN |
| | export capability | PROVEN |
| | retention expectations | UNKNOWN |
| | no demo data leakage | PROVEN — enforced in schema |
| Source / intelligence | active sources explicitly approved | three, all demo-org scoped |
| | source health visible | mechanism PROVEN; no real baselines |
| | coverage UNKNOWNs disclosed | **PROVEN** — refuses to state a percentage |
| | no false comprehensive claim | **PROVEN** |
| Operations | backup / restore | artifacts exist; never exercised in production |
| | monitoring · scheduler · workers · leases · alerts | BUILT-UNPROVEN |
| | support runbook · incident owner | ABSENT |
| Production infra | DB · PITR · storage · secrets · email · auth · TLS · logs | ALL UNKNOWN or UNPROVEN |

### The launch recommendation

**Do not launch to a real Tribal government yet. The blocker is coverage, not
readiness.**

A Tribe onboarded today would receive intelligence drawn from three demo-scoped sources
over a catalogue that measurably misses roughly 96% of the federal opportunities they
are eligible for, with no state, philanthropy or infrastructure coverage at all. The
system would not lie to them — it is carefully built not to, and it would correctly
decline to claim comprehensiveness. It would simply be close to empty, and a sovereign
government evaluating it would reasonably conclude the product does not work.

**The correct next action is Wave 1 source expansion**, whose highest-value item is a
single query-parameter change: filtering Grants.gov on the eligibility facet instead of
title keywords, worth 464 measured Tribal-eligible postings plus 431 forecasted early
signals, from a public API that needs no authorization.

**What this gate certifies:** the fabric is trustworthy enough to carry real data.
**What it refuses to certify:** that there is yet enough real data for it to carry.

---

## Verification record

| Step | Result |
| --- | --- |
| Artifact repair | 4 lines; targeted regeneration; `network_attempts=0`; idempotent on re-run |
| Focused gate121 + gate143 | 134 passed |
| Sequential battery, pre-freeze | **13/13 GREEN** |
| Authoritative full suite | **13,695 passed, 50 skipped, 0 failed — 2:49:02** |
| Commit | `840b2ee` |
| Post-commit battery | **13/13 GREEN** |
| Push | **withheld pending human authorization** |

Gate 180 is documentation only. It adds no file under `src/nativeforge/` and regenerates
no artifact, so the authoritative suite above remains valid rather than stale.

---

## What must not be weakened

Carried forward as standing constraints:

- No source activates without a human authorization decision.
- Public ≠ authorized. Awards ≠ opportunities. Forecasts ≠ open funding.
  Programme ≠ opportunity. Source count ≠ coverage.
- `CANDIDATE_UNVERIFIED` never reaches a customer surface as fact.
- Tribal legal classes stay distinct; no flattening into "Native".
- UNKNOWN stays UNKNOWN. The coverage scorecard continues to refuse a percentage.
- `award_is_demo_fixture` and `counts_toward_real_metrics` cannot both be true.
- A 403 with a tiny body, or a redirect named `unblock.`, is an access control and is
  contacted, never circumvented.
