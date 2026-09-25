# Tranche 2C — Indian Health Service

**What IHS actually contributes to NativeForge:** it is a **discovery and
document surface whose eligibility prose is the product**. Grants.gov owns
every IHS opportunity record. IHS's own funding index links **26 opportunities
and every single one is closed.**

The thing IHS adds that nothing else does is the sentence that says who may
apply — because for a wholly Native-serving agency, that sentence is the only
thing standing between a Tribe and $11.3M it cannot have.

---

## 1. The headline: Native-serving is not Tribe-eligible

Four of IHS's 18 current opportunities are invisible to Tribal applicant-type
codes 07/08/11. They do not fail the same way:

| Opportunity | Eligibility prose | Funding | Tribe named? |
|---|---|---|---|
| Tribal Epidemiology Centers | "Tribes, Tribal Organizations, Urban Organizations" | **$7,000,000** | **YES** |
| Urban Indian Health 4-in-1 | "IHS contracted UIOs" | $9,707,858 | no |
| Urban Indian Educ. & Research | "AIAN National organization" | $1,450,000 | no |
| National Urban Indian Behavioral Health | "must be a 501(c)(3) organization" | $200,000 | **NO** |

All four are published by an agency whose entire mission is Native health.
Collapsing them to `tribal = true` would show a Tribe **$11.36M it cannot
apply for** while looking like coverage — and would still be wrong about the
$7M it genuinely can.

So entity classes are kept as the legal classes Congress wrote:
**Tribe**, **Tribal Organization**, **Urban Indian Organization**, **AIAN
National Organization**, **Tribal Epidemiology Center**, **501(c)(3)**.
An Urban Indian Organization is not a kind of Tribe.

Across all 18 current IHS opportunities: **14 name a Tribe, 3 UNKNOWN, 1 NO.**
Only **8 of 18** state a federal-recognition requirement — so recognition is
reported as a separate field, and never inferred in either direction.

---

## 2. IHS contradicts HUD, which is why it was measured separately

Tranche 2B's answer was "the assistance listing rescues what the eligibility
facet drops". That is **not** the IHS answer.

| | HUD ONAP | IHS |
|---|---|---|
| Current opportunities found by eligibility facet | missed 1 of 1 | **found 18 of 18** |
| ALN present in the search index | yes | **0 of 245 records** |
| Rescue path | assistance listing | eligibility facet is sufficient |

**Eligibility-facet discovery misses zero IHS opportunities.** The brief's
instruction not to generalise from HUD was correct: the same blind spot exists
(code 25 sits on 16 of 18 records) but here it is fully covered by 07/11.

The ALN filter still *works* for IHS — `cfda=93.933` returns 70 records — even
though the search response omits `alnist` on all 245. "The response omits the
field" and "the filter does not work" are different claims, and conflating
them would have produced a false architectural conclusion.

---

## 3. Stale links: worse than HUD, and unambiguous

Every Grants.gov deep link on the IHS DGM funding index — **26 of 26** —
points to a closed round. The newest closed 2025-04-28; most are 2021–2022.

Meanwhile **17 live FY2027 forecasts and 1 posted FY2026 opportunity** exist
on Grants.gov, and **not one of them is linked from the page.**

Treating the IHS funding index as an opportunity source would show a Tribe 26
dead competitions, some five years old, and zero of the 18 live ones. HUD's
version of this failure was 3 stale links; IHS's is total.

The index also uses **two Grants.gov URL formats** — modern
`search-results-detail/{id}` and legacy `view-opportunity.html?oppId={id}` —
which is itself a age signal worth reading rather than normalising away.

---

## 4. Access posture — the most cooperative publisher yet

```
User-agent: *
Disallow:
SITEMAP: https://www.ihs.gov/sitemap.xml
```

Everything permitted, and a declared sitemap. All 14 probed surfaces returned
**LIVE_HTML or LIVE_STRUCTURED**: no empty shells, no blocks, no
UA-conditional refusals. Platform is ColdFusion (`.cfm`); there is no JSON
API and no RSS.

`/dgm/funding/` and `/dgm/funding/index.cfm` are **byte-identical** — the two
registry rows for them describe one surface.

One real source-health signal: the site carries a banner stating that, owing
to the federal funding situation, **its own information may not be up to date**
— a publisher declaring its content possibly stale while serving HTTP 200.

---

## 5. Money that is not a grant opportunity

**IHS Scholarship and IHS Loan Repayment are live surfaces with zero
Grants.gov records** — exactly as HUD's Section 184 and Title VI loan
guarantees were. A clinician applies, not a Tribe.

This is a different reason for exclusion than formula money, so it gets its
own vehicle and its own lane: formula money has an organisational recipient
and no competition; a scholarship has a competition and **no organisational
applicant at all**.

Cooperative agreements go the other way. IHS's portfolio is largely
cooperative agreements (Self-Governance Planning, Negotiation, Public Health
Nursing), they are applied for and won like grants, and excluding them on a
technicality would drop most of a health agency's money.

---

## 6. Implementation

No new adapter. No new collection framework. **No migration.**

**`native_entity_class_service.py`** (new, generic) — statutory entity-class
extraction, three-valued `tribe_named_as_eligible_class`, and federal
recognition as a separate field. `publisher_is_native_serving` is accepted and
deliberately **does not move the answer**, so agency focus cannot be smuggled
in as eligibility evidence.

**`program_office_roster_service.py`** (extended) — `COOPERATIVE_AGREEMENT`
(opportunity-bearing) and `SCHOLARSHIP_OR_LOAN_REPAYMENT` (individual-directed,
its own lane).

**`grants_gov_search_api_adapter_service.py`** (fixed) — see below.

### The Tranche 2B defect IHS exposed

`_ASSISTANCE_LISTING_RE` was `^\d{2}\.\d{3}$`, written against one agency's
listings. IHS listings include **93.00K, 93.00E, 93.00F, 93.00G, 93.00L and
93.00P** — the last character is a letter. The stricter pattern raised
`ValueError` on all of them, so those programmes could not even be *asked*
about. Six of 18 current IHS opportunities carry such a listing.

A validation rule tuned on one publisher and shipped as universal. Now
`^\d{2}\.\d{2}[0-9A-Za-z]$`, with both forms tested.

### The plural bug, refusing to recur

`\bnofo\b` could not match "NOFOs"; before that a closing `\b` on the Federal
Register funding pattern classified two real notices as OTHER. The brief named
this a regression class rather than a typo, so **every** entity-class pattern
here is a prefix and **fifteen singular/plural pairs are parametrised** —
Tribe/Tribes, Organization/Organizations, UIO/UIOs, Center/Centers.

### A false negative the live run caught

The first version required "federally recognized" or "Indian Tribe" to
recognise a Tribe. Most of IHS's portfolio reads simply **"Tribes/Tribal
Organizations"**, so **9 of 18 live opportunities returned UNKNOWN** — a false
negative pointing away from money Tribes can apply for. A Tribe *is* named
there; what is unknown is the recognition requirement. Two fields, not one.

---

## 7. False positive / false negative review

**Referred to opportunity graph from IHS first-party pages: 0.** Every
Grants.gov link on the funding index resolves to a closed round, so nothing
first-party is referable as current. **False positives: 0.**

**False negatives:** all 18 current IHS opportunities were checked against
eligibility-facet discovery; **0 missed**. The denominator is known because
the full IHS corpus was pulled uncapped — 245 records, `complete=True`.

**UNKNOWN cases: 3** — the two Urban Indian programmes and one further record
whose prose names classes without exclusive language. UNKNOWN is the correct
answer there and is not counted as coverage.

---

## 8. Verification

```
45   new tests (gate 182D), plus 12 added to 182B/182C
141  passed across gates 182B/C/D
1186 passed across gates 77, 169, 171-176, 179, 181, 182,
     source registry and seed corpus
~200 real network requests, bounded
0    migrations, 0 new adapters
```

**One known failure, pre-existing and deferred:**
`test_gate143_source_monitoring_preflight.py::test_the_committed_artifacts_match_what_the_service_builds`.
Artifact pins `files_scanned: 1281`; actual is now **1284** (2A→1282,
2B→1283, 2C→1284). Regenerated once at tranche-set close, not per tranche.

---

## 9. Registry findings — reported, not mutated

Ten IHS rows exist. All terms flags left untouched.

- `IHS-DGM-FUNDING-OPPORTUNITIE-5927B7` and `HHS-IHS` point at the **same
  byte-identical page** (`/dgm/funding/index.cfm` vs `/dgm/funding/`).
  Duplicate surface, two rows.
- Prior research recorded "publication policy CHANGED" on the DGM index. The
  live page confirms it: pre-2024 sections read "as Published in the Federal
  Register", later ones do not. That is why the page carries 50 Federal
  Register links.
- `IHS-HEALTH-IT-MODERNIZATION-35151C` is correctly Tier 4: agency-side IT
  procurement, not grantee funding.

The row notes on self-governance ("compacted, not competitive") and urban
Indian organizations ("a distinct applicant class... must be modeled
separately") were both **confirmed by live evidence** and are now enforced in
code rather than recorded in prose.

---

## 10. Activation decision

**CONTRACT_PROVEN: yes.** **COLLECTOR_ACTIVATED: no.**

**Final state: ACTIVATE AS DISCOVERY / DOCUMENT SOURCE — pending.**
Registry rows unchanged at `seed_imported` / `not_started`.

IHS must **never** be activated as an opportunity source: 26 of 26 of its
opportunity links are closed rounds. Its value is the NOFO PDFs, the Dear
Tribal Leader letters that surface facilities programmes absent from the
grants index, and above all the eligibility prose that decides who may apply.

---

## 11. The durable lesson

2A: source trust and record routing are separate decisions.
2B: a source can be worth activating precisely for what it is *not*.
2C:

> An agency existing entirely to serve Native people still publishes
> programmes Tribes cannot apply for. Institutional mission is not eligibility
> evidence, and the sentence naming the applicant class is the product.

And the methodological one, which cost a defect each time it was ignored:

> A rule tuned on one publisher is a hypothesis about the next one. `^\d{2}\.
> \d{3}$` fit one agency perfectly and refused six live programmes at the
> second. Measure the second publisher before believing the first.
