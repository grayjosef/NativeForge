# Tranche 2 — Integrated Close

Five federal publishers, measured live. The headline is not how many sources
were added. It is that **the same question got five different answers**, and
the architecture now holds all five without collapsing them.

---

## 1. Evidence grading

Everything below is graded. The grades are the point.

| Grade | Meaning |
|---|---|
| **REAL** | measured against the live publisher in this campaign |
| **FIXTURE** | proven offline against recorded/constructed data |
| **BUILT** | code exists and is tested; not exercised in production |
| **NOT ACTIVATED** | no collector runs; no scheduled collection |
| **UNKNOWN** | genuinely undetermined; recorded as such |
| **BLOCKED** | prevented by an external dependency |

**Every source in Tranche 2 is NOT ACTIVATED.** All 381 registry rows remain
`registry_status=seed_imported`, `monitoring_status=not_started`, and the
committed artifact records `collector_activated: false`. Contract proof is not
activation, and nothing here crossed that line.

---

## 2. What each publisher actually is

### 2A — Federal Register · commit `62a71b3` · REAL

**Role: early signal, policy, consultation and intelligence — not an
opportunity feed.**

The adapter already existed and its own descriptor said
`"PROPOSED_NOT_VERIFIED_BY_THIS_REPOSITORY"`. It was verified live; no second
adapter was written.

`count` is **capped at 10000** — an unfiltered query returns exactly 10000 and
an absurd term returns 0, so any measurement equal to the cap is a floor.
**No capped number is quoted as a population.** Bounded to 2026-07-01..09-25
the real figures are 6,295 documents, 989 matching *tribal*, 461
funding-opportunity, 305 repatriation.

100 real tribal-matching documents classified:

```
47  POLICY_RULEMAKING     -> early signal
22  ADMINISTRATIVE        -> not routed
18  OTHER                 -> not routed
10  REPATRIATION_NOTICE   -> intelligence only
 2  FUNDING_NOTICE        -> opportunity graph
 1  CONSULTATION          -> intelligence only
```

**98 of 100 do not become opportunities.** Classification is what stopped
Paperwork Reduction Act filings and NAGPRA inventory-completion notices from
polluting the opportunity graph — a naive keyword pass had called four of them
"funding-shaped". Both genuine funding notices carry *no* Native evidence, so
the Federal Register's additive value for opportunities is near zero and its
value as intelligence is not.

### 2B — HUD ONAP · commit `8b49182` · REAL

**Role: programme roster and discovery surface. Grants.gov owns the records.**

Grants.gov exposes ONAP only as `agencyCode: HUD` — there is no ONAP filter,
so *"show me ONAP's opportunities"* is a question the canonical source cannot
answer about itself. The assistance listing can.

**The finding that justified the tranche:** `FR-6900-N-74`, ICDBG Imminent
Threat — **$5,000,000 estimated, $1,500,000 ceiling**, no cost share, closing
2026-09-30, whose eligibility text reads *"Eligible applicants are Tribes and
Tribal organizations as described in the ICDBG regulations at 24 CFR
§1003.5"* — declares applicant type **25 only**. Codes 07, 08 and 11 return it
**zero times out of three**; ALN 14.862 returns it immediately.

```
found by eligibility        : 106   (floor: first page of each code)
found by assistance listing : 1
found by both               : 0
```

Stale links: the IHBG-COMP page links FY2025 (closed) and FY2024 (closed); the
ICDBG page links FY2025 (closed). The live FY2026 forecasts — **$125M and
$90M** — are linked from neither. **3 of 3 stale.**

**HUD Exchange returns 404 to this user agent and 200 to a browser one** — a
refusal disguised as absence. A browser string was sent **once, as a
diagnostic**, never to collect. HUD Exchange is out of scope; its five
registry rows describe a source that is neither live nor dead.

### 2C — IHS · commit `5f423d3` · REAL

**Role: eligibility prose and documents. Grants.gov owns the records.**

Complete corpus pulled uncapped: **245 records**. **18 current opportunities,
and the eligibility facet found all 18** — the exact opposite of HUD, which is
why the brief forbade generalising.

Four are missed by codes 07/08/11, and they do **not** fail the same way:

| Opportunity | Prose | Funding | Tribe named? |
|---|---|---|---|
| Tribal Epidemiology Centers | "Tribes, Tribal Organizations, Urban Organizations" | **$7,000,000** | **YES** |
| Urban Indian 4-in-1 | "IHS contracted UIOs" | $9,707,858 | no |
| Urban Indian Educ. & Research | "AIAN National organization" | $1,450,000 | no |
| National Urban Indian BH | "must be a 501(c)(3)" | $200,000 | **NO** |

**Code 25 contains both Tribe-eligible and Tribe-ineligible Native-serving
money.** Collapsing them to `tribal = true` would show a Tribe **$11.36M it
cannot apply for** and still be wrong about the $7M it can.

Across all 18: 14 name a Tribe, 3 UNKNOWN, 1 NO — and only **8 of 18** state a
federal-recognition requirement, so **recognition is a separate field from
entity class** and is never inferred in either direction.

**26 of 26** first-party Grants.gov links are closed rounds while 17 live
FY2027 forecasts go unlinked. ALN alphabetic suffixes (`93.00K`, `93.00E`,
`93.00F`, `93.00G`, `93.00L`, `93.00P`) were real listings the Tranche 2B
validation regex refused outright — fixed.

### 2D — EPA · commit `3221b36` · REAL

*Facts below read from the committed report at `3221b36`, not from memory.*

**Role: enrichment and channel intelligence. Its structured records contain no
eligibility at all.**

| | HUD ONAP | IHS | EPA |
|---|---|---|---|
| Found by codes 07/08/11 | missed 1 of 1 | 18 of 18 | **0 of 4** |
| Rescue path | assistance listing | none needed | **code 25 only** |
| Eligibility prose in record | stated | stated | **deferred 100%** |
| First-party links stale | 3 of 3 | 26 of 26 | **0 of 1** |

Complete corpus: **1,491 records**. Measured deferral across the complete
current-and-closed set:

```
EPA   sampled 5    defers to document 5   states 0    100%
IHS   sampled 32   defers to document 0   states 30     0%
HUD   sampled 40   defers to document 0   states 40     0%
```

Flagship: `EPA-OW-OWOW-26-01` (id 363611), ALN 66.460, **$3,500,000 /
$175,000 ceiling / cost share true**, closing 2026-11-09, one attachment —
*its only machine-readable Native evidence is its title.*

**The channel question, which no previous tranche asked.** The wastewater
set-aside reads *"Tribes must identify their wastewater needs to the IHS
Sanitation Deficiency System"* — **EPA holds the money; another agency holds
the queue.** **2 of 5 measured programmes are directly applicable; 3 are real
money nobody applies for at EPA.**

EPA is the **only** publisher in the campaign whose first-party Grants.gov
link is current (1 link, 0 stale — the complete set, stated as such), and the
**inverse of IHS**: its own DWIG-TSA page supplies *"Any federally recognized
Tribe is eligible"*, the eligibility Grants.gov omits.

### 2E — CDFI Fund · commit `3deb1f7` · REAL

**Role: early signal and programme intelligence. Zero open opportunities —
and that is the correct answer.**

Complete corpus: **63 records, every one archived**, 2007→2026 continuous
including FY2026 opened 2026-06-30. Negative control `USDOT-NONSENSE` returns
0, so the zero is real. **No false source-health failure**: a quiet publisher
is not a broken one.

**Certification is not identity.** NACA's gate is *"Certified CDFIs, Emerging
CDFIs, and Sponsoring Entities"* — three certification states, **zero**
statutory Native entity classes. The 2C entity reader returns `[]` here, which
is correct and incomplete; certification is now an orthogonal axis
(`CERTIFICATION_HELD_REQUIRED` / `EMERGING_CERTIFICATION_PATH` /
`SPONSORING_ENTITY` / `NOT_MENTIONED`), verified orthogonal on live prose.

**NACA recurrence is IRREGULAR, not annual.** Seven real rounds with no FY2023
round and a 344-day spread. I read them as "annual, December–February"; the
existing `program_recurrence_service` graded IRREGULAR with no expected
window. **The detector was right and the eyeball was wrong.** A title-only
identity basis correctly returns UNKNOWN with `review_required`.

Agency code: `TREAS`, `TREAS-CDFI` and `CDFI` all returned exactly what
`NONSENSE` returned. The real code is `USDOT-CDFI`, found only by reading
records.

---

## 3. What Tranche 2 taught the architecture

**1. Publisher-first is not opportunity-first.** In four of five cases
Grants.gov remained the canonical opportunity owner while the publisher
supplied classification, programme identity, eligibility prose, channel, early
signal or award history. CDFI is the exception only because it has nothing
open.

**2. Eligibility facets are necessary and not sufficient.** HUD proved a real
$5M miss; IHS proved the opposite; EPA proved the extreme (0 of 4). No single
lane works everywhere, so discovery runs complementary lanes and **measures
the gap between them** rather than assuming it.

**3. Code 25 is not noise.** It contains Tribe-eligible money, Native-serving
but Tribe-ineligible money, and irrelevant money. It triggers evidence review;
it never produces a verdict.

**4. Programme identity is not opportunity identity.** Permanent invariant,
met five times. HUD's own competition ran `FR-6800-N-48` → `FR-6900-N-48` →
`PIH-2600-DC-0048` — the numbering *scheme* changed while ALN 14.867 held.

**5. First-party is not current.** HUD 3 of 3 stale, IHS 26 of 26 stale. A
page link is a *reference*, resolved against the canonical source before
anyone may call it current, defaulting to UNKNOWN.

**6. Certification is not identity.** CDFI added an orthogonal eligibility
axis that no entity model could have expressed.

**7. Money, eligibility and channel are three independent facts.** EPA's
contribution: a record can carry a real deadline and a real dollar figure and
still have no application behind it.

**8. Live source truth beats research assumptions.** Corrections made from
live evidence during this tranche, each recorded in its tranche report:

- `^\d{2}\.\d{3}$` was a validation rule tuned on one agency; it refused six
  live IHS programmes outright.
- `\bnofo\b` cannot match "NOFOs" — the third appearance of the trailing
  word-boundary defect, caught before shipping.
- A 700-character truncation in my own probe hid a live $90M forecast at
  character 718. The instrument was the bug.
- `declared_applicant_types` returned `[]` for an absent field, which would
  have recreated the code-25 blind spot inside its own fix.
- DWIG-TSA was classified `REVOLVING_LOAN_FUND` from a statutory parent it
  merely cites.
- I hypothesised CDFI had left Grants.gov because its pages carry no
  Grants.gov links. Pulling the corpus disproved it.
- I read NACA as annual. The recurrence classifier said IRREGULAR and was
  right.

---

## 4. Coverage delta against Gate 180

Assessed separately. Not one score.

| Dimension | Before | After | Grade |
|---|---|---|---|
| Federal publisher breadth | 7 verified sources | +5 publishers measured end-to-end | REAL |
| Native-specific programme context | thin | programme rosters, funding vehicles, channels | REAL / BUILT |
| Eligibility precision | 3 Tribal codes | + entity classes, recognition, consortia, certification, deferral | REAL / BUILT |
| Discovery lanes | eligibility facet | + assistance listing, with a measured coverage gap | REAL |
| Early signals | forecast continuity | + recurrence graded on real history, + regulatory routing | REAL |
| Award evidence | Wave 1C linkage | unchanged; CDFI award history available, not ingested | BUILT |
| Document intelligence | Gate 175 | now **load-bearing** for EPA, which publishes no structured eligibility | REAL finding, BUILT capability |
| Source health | transport health | + stale-reference, UA-conditional refusal, empty shell, legitimate zero | REAL |
| Customer projection | Gate 179 | unchanged — **no Tranche 2 source feeds a customer** | NOT ACTIVATED |
| State coverage | Wave 1E (California) | unchanged in Tranche 2 | — |

**Opportunities added to the customer-visible graph by Tranche 2: zero.**
Every source is contract-proven and unactivated. That is the honest number.

---

## 5. Controlled-live status — separate verdict

Intelligence maturity does not move the deployment verdict.

**CONTROLLED_LIVE = BLOCKED.**

**Blocker 1 — `mayhem-nc.dev` edge TLS. PROVEN_EDGE_TLS_FAILURE.**
HTTP :80 answers at the edge (301); HTTPS fails with **TLS alert 40
handshake_failure**, reproduced by both `openssl s_client` and Chrome;
`cloudflared_tunnel_total_requests` stays **0**; the failing hostname set
**changes between runs** while stable within a run. Universal SSL shows
Active covering `*.mayhem-nc.dev` to 2026-12-03; Authenticated Origin Pulls is
off at global, zone and per-hostname level with no certificates; no CAA
records; the control zone `josef-gray.dev` serves a valid certificate and
returns 200.

Working hypothesis: **partially deployed / inconsistent Universal SSL
availability across Cloudflare edge PoPs.**
`ROOT_CAUSE_BEYOND_EDGE_CERT_DISTRIBUTION = UNKNOWN` — the evidence does not
support a stronger claim. **No zone-wide change was made**, because every
available remedy (toggling Universal SSL, purchasing ACM, support escalation)
either risks `n8n.mayhem-nc.dev` for an uncontrolled interval or requires
authorization.

**Blocker 2 — WSL2 host lifecycle.** `Linger=yes`, `NRestarts=0`, and yet the
tunnel started **10 times in 20 minutes**: the entire user manager is torn
down, consistent with WSL distro auto-termination. **The current workstation
WSL environment is not an acceptable controlled-live host.**

**Google verification.** Search Console shows the onboarding screen, no
verified properties, no pending verification.
`GOOGLE_PRODUCT = UNKNOWN`, `GOOGLE_VERIFICATION = BLOCKED_PENDING_PRODUCT_OR_URL`.
Not guessed.

**Registrar transfer.** `DEFERRED_NOT_DEPLOYMENT_BLOCKING`. DNS authority is
already Cloudflare.

### Unresolved production gates, unchanged

Tenant isolation under a full adversarial campaign · privacy and Indigenous
data governance framework · managed persistent hosting · monitoring ·
backup and recovery · runbooks · source activation · customer launch
threshold.

**Not `PRODUCTION_READY`. Not `CUSTOMER_LAUNCH_READY`.**

---

## 6. Close verification

| Step | Result |
|---|---|
| Artifact regeneration | 3 files, 6 lines, `network_attempts=0`, **1281 → 1285** |
| Idempotence | second run **0 rewrites, 0 lines** |
| Independent file count | **1285** by `find`, `git ls-files` and `pathlib.rglob` — all agree with the artifact |
| Preflight values | `chokepoint_clean: true`, `finding_count: 0`, `invariant_failures: []`, head pin `0065` = repo head |
| Focused verification | **2,440 passed, 0 failed**, exit 0 (27m19s) |
| Sequential battery | gates 167–179, **13 of 13 exit 0**, 670 tests, run one at a time |
| Freeze | `2026-09-25T18:57:21Z`, 5,440 tracked files, tracked digest `a5bef8c7…`, artifact digest `7ae14492…` |
| **Authoritative full suite** | **14,144 passed · 50 skipped · 0 failed · exit 0 · 2:21:16** |
| Tree integrity | tracked files and artifacts **byte-identical** to freeze; `git status` identical |
| Source activation | `collector_activated: false`; all 381 registry rows `not_started` / `seed_imported` |

### Gate 170

Gate 170 **passed** in the sequential battery (61 tests). That is recorded as
another pass. The single historical unexplained failure from the Gate 176–179
block remains **UNKNOWN** and is not relabelled flake, fixed or resolved.

---

## 7. Known unknowns

- Gate 170's historical failure — root cause still UNKNOWN.
- Cloudflare edge TLS — mechanism beyond "inconsistent certificate
  availability across PoPs" is UNKNOWN.
- Which Google product holds the Political Integrity Network property.
- Whether EPA's deferred-eligibility documents parse cleanly — the documents
  were identified, not ingested.
- Real applicant-class coverage for publishers whose eligibility lives only in
  PDFs.

---

## 8. Verdict

Tranche 2 is **done building** and **proven integrated**: one authoritative
suite on a frozen tree, 14,144 passed, 0 failed, tree byte-identical
afterwards.

Five publishers are contract-proven. **None is activated.** No opportunity
reached a customer. The deployment remains BLOCKED on two precisely
identified external causes, and that verdict is deliberately kept apart from
the intelligence result.
