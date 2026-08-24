# 444 — Gate 79G: Production readiness delta

Gate 79 corrected two contract defects the Gate 78R research exposed. It
identified no new source, fetched nothing, and monitored nothing.

## Funding-lane correction: now

| | Before | After |
| --- | --- | --- |
| Opportunity lane derived from evidence | **no** — inherited from source | **yes** |
| `federal_pass_through` expressible | **no** | yes |
| SC agency + federal money | filed as **pure `sc_state`** | `federal_pass_through` |
| `.sc.gov` URL determines lane | effectively yes | **no**, and recorded as refused |
| Mixed funding representable | no | yes, and forced to human review |
| `sc_state` inferable without a citation | yes | **no** |

The five Gate 78R sources now classify correctly:

```text
SCEMD    + FEMA HMGP        → federal_pass_through
SCOR     + HUD CDBG-MIT     → federal_pass_through
SCDES    + EPA §319         → federal_pass_through
SC Housing + LIHTC          → federal_pass_through
SCDE     mixed listing      → unknown + human_review_required
SC Housing Trust Fund       → sc_state  (only with a cited reference)
```

**Why this mattered.** Gate 78 stopped federal opportunities being relabelled as
state ones by *geography*. Nothing stopped it happening by *administration* — and
`sc_native_routing_service` actively **rejected** an `sc_state` record naming a
federal agency, so the honest representation was invalid. A customer would have
been shown federal money, with federal strings and often federal-recognition
eligibility rules, described as a state programme, and both coverage counts would
have been wrong.

**A larger defect found in passing.** Doc 440 found the codebase already had
**three** disagreeing lane vocabularies: hardcoded source-level strings,
`sc_native_routing_service.FUNDING_LANES` (5 values, no plain `federal`), and
`native_opportunity_discovery_service.LANES` (5 different values). Gate 79 added
the canonical opportunity-level set and **bridges both existing ones** rather
than adding a fourth. A test asserts every canonical lane projects into both
older vocabularies.

One projection is lossy and recorded as such: `federal_pass_through` maps to
`federal_sc_relevant` in the SC routing vocabulary, because that set's only
federal member is the SC-relevant one. It never lands on a state value.

## Eligibility-exclusion model: now

| | Before | After |
| --- | --- | --- |
| Express "evidence excludes this class" | **no** | yes, `excluded_by_evidence` |
| Applicant-class granularity | 3 tiers | **8 classes** |
| Exclusion requires a citation | n/a | yes |
| Silence treated as exclusion | n/a | **no** |
| Restrictions distinguished from exclusions | no | yes |
| Universal `not_eligible` assertable | no | **still no** |

The NACTEP case, which is the reason this exists:

```text
"Eligibility is limited to Federally recognized Indian tribes, tribal
 organizations, Alaska Native entities, and eligible BIE-funded schools"

federally_recognized_tribe  → eligible
tribal_organization         → eligible
bie_funded_school           → eligible
state_recognized_tribe      → excluded_by_evidence
native_nonprofit            → excluded_by_evidence
```

South Carolina has one federally recognized tribe and ten state-recognized ones.
The product could previously only answer `unknown` for those ten. Saying "we
don't know" when the notice plainly excludes them wastes the scarcest thing a
tribal grant office has, which is staff time.

Four refusals keep it honest:

- **Silence is not exclusion.** A notice that does not mention state-recognized
  tribes yields `not_supported_by_evidence`. Only an *exclusive* list — a marker
  such as "limited to" plus a named class — excludes.
- **A narrow grant is not a broad one.** "BIE-funded schools only" makes schools
  eligible; it does not make tribal governments eligible.
- **A restriction is not an exclusion.** "On Federal Trust land" narrows how an
  award may be used; the class survives.
- **Exclusion is per class.** Excluding state-recognized tribes says nothing
  about Native nonprofits.

**The Gate 77 boundary is untouched.** `excluded_by_evidence` is narrower than
`not_eligible`: it says *this programme's cited text* excludes *this class*, not
that an organization is ineligible for anything in general.
`federal_native_eligibility_service` still hardcodes
`not_eligible_asserted: False` with its invariant, and a Gate 79 test asserts
that guard is intact.

## SC source coverage: now

**Unchanged.**

```text
Live SC source coverage:   NONE
SC sources monitored:      0
SC sources identified:     0 seeded
Federal sources monitored: 0
SC coverage complete:      NOT CLAIMED
65% improvement:           NOT CLAIMED
```

Gate 78R produced research, not coverage. Gate 79 produced contracts, not
coverage. No source from the research pack has been seeded, because robots/terms
review has not happened for any of them.

## Live coverage status

Nothing fetched. Nothing monitored. The Gate 77B hermetic guard and the Gate
78E write-back guards are untouched — `git status` on `fixtures/` is clean after
the suite, and the cleanliness script passes.

## Native customer value

The concrete gain for an SC tribal organization is a **negative result they can
act on**: "this programme requires federal recognition, which you do not have,
and here is the sentence that says so."

For nine of SC's eleven recognized tribal entities that is the accurate answer to
most Native-specific federal programmes, and it is more useful than a longer list
with an ambiguous verdict. It also costs them nothing to read, whereas an
`unknown` invites a week of investigation that ends the same way.

What this does **not** do is tell them what they *are* eligible for. That needs
sources, and sources need robots/terms review.

## Owner-blocked

- **Robots/terms review** for the Gate 78R sources — the gate between research
  and any fetching. A legal/policy judgement.
- **Primary-source verification** of the eligibility strings captured in Gate
  78R. The fixture marks every one `eligibility_verified: false`; no customer-
  facing exclusion should be published on a summarised read of an index page.
- Real `OIDC_*` credentials, managed Postgres, migration 0028, backup/restore,
  pen test, Slack webhook.

## Engineering-blocked

- Wiring the new lane classifier into `sc_native_routing_service` and
  `native_opportunity_discovery_service`, retiring their local lane vocabularies
  in favour of the bridged canonical set.
- Surfacing `excluded_by_evidence` in the discovery record and the Gate 54
  quality scorer — an excluded opportunity should not count as coverage for the
  excluded class.
- NOFO parsing (Gate 81) to extract eligibility text rather than accept it.
- Scheduler (Gate 80) — still correctly blocked; zero sources are terms-cleared.

## Controlled customer pilot delta

**None.**

```text
Controlled customer pilot: NO_GO
Production rollout:        NO_GO
Customer login live:       NO
Production storage live:   NO
Customer persistence:      NO
Pen-test passed:           NO
```

What genuinely changed: federal money administered by a South Carolina agency can
no longer be counted as South Carolina state funding, and the product can now
tell a state-recognized tribe that a programme excludes them and cite the
sentence. Both were wrong before, and both were wrong in the direction of
sounding more useful than the evidence supported.
