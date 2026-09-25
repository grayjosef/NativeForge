# Tranche 2D — EPA

**What EPA actually contributes to NativeForge:** it is the publisher that
proves **"there is money for this" and "apply here" are different claims**.

EPA's Tribal money is real, large and mostly **not applied for at EPA**. Its
structured opportunity records contain **no eligibility at all**. And its
first-party pages carry the eligibility that Grants.gov omits — the exact
inverse of IHS.

---

## 1. Three publishers, three incompatible answers

The campaign has now measured the same question three times and got three
different answers. This is why the brief forbade generalising.

| | HUD ONAP | IHS | **EPA** |
|---|---|---|---|
| Current opportunities found by codes 07/08/11 | missed 1 of 1 | **18 of 18** | **0 of 4** |
| Rescue path | assistance listing | none needed | **code 25 only** |
| Eligibility prose in the record | stated | stated | **deferred 100%** |
| First-party links stale | 3 of 3 | 26 of 26 | **0 of 1** |

**Codes 07, 08 and 11 return zero EPA opportunities.** All four current EPA
records — including one titled *"Funding Opportunity for Indian Tribes and
Intertribal Consortia"* and one on *Contaminated Alaska Native Claims
Settlement Act Lands* — declare applicant type **25, "Others"**, and nothing
else.

A system that discovers Tribal opportunities by applicant-type code finds
**none of EPA**. Code 25 is not an edge case; for this agency it is the whole
publication model.

---

## 2. EPA publishes no machine-readable eligibility

Measured across the complete current-and-closed EPA set:

```
EPA   sampled 5    defers to document 5    states eligibility 0    100%
IHS   sampled 32   defers to document 0    states eligibility 30     0%
HUD   sampled 40   defers to document 0    states eligibility 40     0%
```

Every EPA record says some version of *"See Section 2 of the full announcement
for eligibility information."*

For EPA the attached notice is **not enrichment — it is the only place
eligibility exists.** A reader of structured fields alone knows nothing about
who may apply. Gate 175 becomes load-bearing for this publisher in a way it is
not for the other two.

So `eligibility_deferred_to_document` is now a distinct state: not "absent",
not "unreadable", but **present, readable, and deliberately pointing
somewhere** — which makes it actionable, because it names where to look.

The flagship case: `EPA-OW-OWOW-26-01` (id 363611), *"FY 2026 Funding
Opportunity for Indian Tribes and Intertribal Consortia for Nonpoint Source
Management Grants Under Clean Water Act Section 319"*, ALN 66.460,
**$3,500,000 / $175,000 ceiling / cost share true**, closing 2026-11-09, with
**one attachment**. Its only machine-readable Native evidence is its title.
(Prior research recorded "$175k cap; ~$3.5M/yr" — confirmed live.)

---

## 3. The channel question, which no previous tranche asked

EPA's Tribal programmes are funded by EPA and **applied for somewhere else**:

| Programme | What the page actually says | Channel | Honest action |
|---|---|---|---|
| Wastewater set-aside | *"Tribes must identify their wastewater needs to the IHS Sanitation Deficiency System. EPA uses the … priority lists"* | **EXTERNAL_AGENCY_QUEUE** | enter another agency's system |
| Drinking water set-aside | *"uses formulas to allocate … among the EPA Regional Offices annually"* | FORMULA_ALLOCATION | await allocation |
| CWA §319 Tribal | *"applicants must submit applications via grants.gov"* **and** base grants whose *"deadlines vary by EPA Region"* | DIRECT + FORMULA | apply |
| GAP | direct | DIRECT | apply |

**EPA holds the money; another agency holds the queue.** A customer told
"APPLY NOW" for the wastewater set-aside would wait for a competition that
does not exist while never entering the queue that actually allocates the
money. That is not a display bug — it is a Tribe missing a funding cycle.

**2 of 5 measured programmes are directly applicable. 3 are real money nobody
applies for at EPA.**

Hence `funding_channel_service`, which answers *through what channel, and to
whom* — and `customer_action` ∈ {APPLY, CONTACT_ADMINISTRATOR,
ENTER_EXTERNAL_QUEUE, AWAIT_ALLOCATION, MONITOR, UNKNOWN}.
`application_authority` is **never inferred from the funder**, because the
measured counter-example disproves that assumption outright.

---

## 4. The inversion: first-party pages carry what Grants.gov lacks

IHS's value was its eligibility prose and its links were all stale.
EPA is the mirror image:

- Grants.gov record: *"See Section 2."* — no entity classes at all.
- EPA's own DWIG-TSA page: *"Any federally recognized Tribe is eligible to
  receive a grant."* → `TRIBE_FEDERALLY_RECOGNIZED`,
  `FEDERAL_RECOGNITION_STATED`.
- EPA's own §319 page → `INTERTRIBAL_CONSORTIUM` +
  `TRIBE_RECOGNITION_UNSPECIFIED`.

**For EPA, first-party enrichment is not a nicety; it is the only structured
eligibility available.**

And EPA is the **only publisher in the campaign whose first-party Grants.gov
link is current** — 1 link, 0 stale (HUD 3 of 3 stale, IHS 26 of 26). Small
denominator, stated as such: it is the complete set, not a sample.

---

## 5. Implementation

No new adapter. No new collection framework. **No migration.**

**`funding_channel_service.py`** (new, generic) — channel detection,
`customer_action`, multi-channel flagging, and the refusal to infer the
application authority from the funder.

**`native_entity_class_service.py`** (extended) — `INTERTRIBAL_CONSORTIUM` as
its own class, and `eligibility_deferred_to_document` /
`document_retrieval_required`.

### Bugs caught

**A mention of a mechanism is not that mechanism.** DWIG-TSA was classified
`REVOLVING_LOAN_FUND` because the page says the Act *"authorized EPA to
set-aside up to 1.5% of the DWSRF"* — the statutory parent, not the channel.
Ranking the fund above formula told a Tribe to go and talk to a loan
programme. This is the fifth costume of "a notice about a programme is not
that programme".

**The plural class, still held shut.** `consortia` shares no stem ending with
`consortium`, so both are spelled out and parametrised, alongside
application/applications, allocation/allocations and NOFO/NOFOs.

### A usage boundary, stated rather than coded around

The tribal water *hub* page classifies as `EXTERNAL_AGENCY_QUEUE` because it
mentions one programme's queue. A hub is a roster, not a programme — it
belongs to `program_office_roster_service`, not the channel classifier.
Recorded as a known boundary; feeding a roster to a per-programme classifier
is a caller error.

---

## 6. Registry findings — reported, not mutated

22 EPA rows exist. Two probed URLs are **hard 404s**:

- `EPA-TRIBAL` → `epa.gov/tribal/tribal-grants` — **Tier 1,
  `NO_REVIEW_REQUIRED`**, i.e. the most activation-ready state, pointing at a
  dead URL. Same governance hazard as HUD's `HUD-ONAP`.
- `EPA-ENVIRONMENTAL-JUSTICE-GR-0380CA` → `epa.gov/environmentaljustice` —
  prior research recorded "verified-terminated-or-removed"; it is now a hard
  404. **Confirmed.**

Prior research also recorded that EPA **retired** its Tribal Waste Management
Funding Directory and redirects to a BIA clearinghouse, and that the tribal-air
announcements page is "a year stale" and still links the dead EJ page. Both
remain true. Terms flags untouched.

---

## 7. Verification

```
38   new tests (gate 182E) + 25 added to 182D
101  passed across 182D/182E
1789 passed across gates 77, 169, 171-176, 179, 181, 182, award linkage,
     source registry and seed corpus
~110 real network requests, bounded
0    migrations, 0 new adapters
EPA corpus pulled complete: 1491 records, complete=True
referred to opportunity graph: 0   false positives: 0
```

**Known failure, pre-existing and deferred:** gate 143's artifact pins
`files_scanned: 1281`; actual is now **1285** (2A→1282, 2B→1283, 2C→1284,
2D→1285). Regenerated once at tranche-set close.

---

## 8. Activation decision

**CONTRACT_PROVEN: yes. COLLECTOR_ACTIVATED: no.**

**Final state: ACTIVATE AS ENRICHMENT / CHANNEL-INTELLIGENCE SOURCE —
pending.** Registry rows unchanged.

EPA is the first publisher in this campaign whose first-party pages should be
read **because the canonical record is deficient**, not merely to add context.

---

## 9. The durable lesson

2A: source trust and record routing are separate decisions.
2B: a source can be worth activating precisely for what it is *not*.
2C: institutional mission is not eligibility evidence.
2D:

> Money, eligibility and channel are three independent facts. A record can
> carry a real deadline and a real dollar figure and still have no application
> behind it. "Who funds this" does not answer "who takes the application", and
> assuming it does costs a Tribe a funding cycle.
