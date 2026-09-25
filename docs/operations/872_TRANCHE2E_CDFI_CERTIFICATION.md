# Tranche 2E — CDFI Fund

**What the CDFI Fund actually contributes to NativeForge:** it is the
publisher that proves **a certification is not an identity**, and that **zero
open opportunities can be the correct answer**.

Its money is Native-designated. Its eligibility gate is not.

---

## 1. The certification finding

NACA's own eligibility prose:

> "Certified CDFIs, Emerging CDFIs, and Sponsoring Entities (organizations
> primarily serving Native Communities that propose to create a separate
> Certified CDFI) are eligible to apply for Technical Assistance."

Three **certification states**, and **not one statutory Native entity class
among them**. The entity-class reader built in Tranche 2C returns `[]` here,
and that is correct — it is also incomplete, because the gate is real and
sits on a different axis.

A Tribe reading "Native-designated federal capital" would reasonably assume it
qualifies. The actual gate is a certification it may not hold. Collapsing the
two would be the Tranche 2C error in a new costume: 2C established that a
Native-serving *agency* does not confer eligibility; 2E establishes that a
Native-serving *programme* does not either.

So certification is now a separate axis:

```
CERTIFICATION_HELD_REQUIRED    certified / accredited / licensed / designated
EMERGING_CERTIFICATION_PATH    not yet certified, on a path to it
SPONSORING_ENTITY              sponsors the creation of a certified body
NOT_MENTIONED                  no certification gate
```

Deliberately generic — certification, accreditation, licensure and formal
designation are one gate wearing different words, so an accredited-institution
programme at another publisher reuses this unchanged.

Verified orthogonal on live prose: the CDFI page yields three certification
states and zero entity classes; "Federally recognized Indian Tribes are
eligible" yields two entity classes and no certification gate.

---

## 2. The legitimate zero

Complete corpus, pulled uncapped: **63 records, every one `archived`.**

```
agencies=USDOT-CDFI       63
agencies=USDOT-NONSENSE    0      (negative control)
```

Records run **2007 → 2026 continuously**, including FY 2026 opened
2026-06-30. The CDFI Fund has not left Grants.gov and is not broken — it
simply **has nothing open today**.

This is the cleanest legitimate zero in the campaign, and it matters because
the two wrong readings are both cheap: report it as breakage and operators
learn to ignore the signal; report it as coverage and it is a lie.

### A correction worth recording

I hypothesised mid-tranche that CDFI had **migrated off Grants.gov** to its
own AMIS portal, because the first-party pages carry **zero** Grants.gov links
and two AMIS links. Pulling the corpus disproved it: annual postings straight
through 2026. The first-party absence of Grants.gov links is real; the
inference drawn from it was wrong.

---

## 3. The agency code nobody would guess

```
TREAS        0
TREAS-CDFI   0
CDFI         0
NONSENSE     0      <- identical to all three guesses
USDOT        2      <- Department of TRANSPORTATION, despite the facet label
USDOT-CDFI  63      <- the real one
```

The facet *labelled* `USDOT` as "Department of the Treasury" with a count of
191, and it returns two transportation records. Three plausible guesses
returned exactly what a nonsense code returns. Only reading real records
surfaced `USDOT-CDFI`.

Keyword search was token soup again, and was discarded:

```
"zzqq CDFI Assistance"   52,006
"Assistance"             51,967
```

The reliable axis was the assistance listing: **21.012 = NACA** (7 rounds),
21.020 CDFI Program (25), 21.021 BEA (16), 21.011 Capital Magnet Fund (8),
with 99.999 and NONSENSE both returning 0.

---

## 4. Recurrence: the detector beat my eyeball

Seven real NACA rounds:

```
2018-01-31  2019-04-04  2020-02-20  2021-02-18  2022-02-10
2023-12-08  2025-01-16          (no FY2023 round)
```

I read that as "annual, December–February". The existing
`program_recurrence_service` graded it **IRREGULAR** — mean interval 423.7
days, spread **344 days** — and produced no expected window.

**The service was right and I was pattern-matching.** A confident "opens in
January" derived from that history is exactly the fabricated certainty the
module was written to refuse.

Also verified, on the same real dates:

- title-only identity basis → `UNKNOWN` + `review_required` (the refusal holds)
- the graded result contains **no opportunity keys** — an expectation never
  becomes an open round
- `recurrence_invariant_failures` → none

**CDFI required no new recurrence architecture**, which is the outcome the
brief anticipated and the one that keeps the source factory generic.

---

## 5. Access

`cdfifund.gov` robots.txt is stock Drupal, permissive outside `/core/` and
`/admin/`. All five probed surfaces **LIVE_HTML**; no shells, no blocks, no
UA-conditional refusals. No API — AMIS is a submission system, not a data
source. The apply-step page carries **19 documents** and **2 AMIS links** and
**zero** Grants.gov links.

---

## 6. Implementation

No new adapter. No new collection framework. **No migration.** One new
function and its constants in an existing service.

`native_entity_class_service.py` — `assess_certification_requirement()`,
reported separately from entity class and never merged into it. Holding a
certification is a tenant fact; Gate 174 still owns it.

---

## 7. Verification

```
24   new tests (gate 182F)
125  passed across 182D/182E/182F
973  passed across gates 172, 173, 174, 176, 181, 182, recurrence,
     source registry and seed corpus
~35  real network requests, bounded
0    migrations, 0 new adapters, 0 new services
CDFI corpus pulled complete: 63 records, complete=True
referred to opportunity graph: 0   false positives: 0
```

`files_scanned` unchanged at **1285** — no new source file.

---

## 8. Activation decision

**CONTRACT_PROVEN: yes. COLLECTOR_ACTIVATED: no.**
**Final state: ACTIVATE AS EARLY-SIGNAL / PROGRAMME-INTELLIGENCE SOURCE —
pending.** Registry rows unchanged.

With zero open rounds, CDFI's present value is entirely recurrence and
programme intelligence — and the recurrence grade is IRREGULAR, so even that
must be stated as a question rather than a date.

---

## 9. The durable lesson

2A: source trust and record routing are separate decisions.
2B: a source can be worth activating precisely for what it is *not*.
2C: institutional mission is not eligibility evidence.
2D: money, eligibility and channel are three independent facts.
2E:

> A certification is not an identity, and an empty result is not a failure.
> The two cheapest mistakes available to a discovery system are calling a
> quiet source broken and calling a Native-designated programme open to
> Natives.
