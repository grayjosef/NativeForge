# 438 — Gate 78I: Production readiness delta

Gate 78 built the South Carolina state source lane and closed the fixture
write-back carry-forward. It identified no SC source, fetched nothing, and
monitored nothing.

## SC lane: now

| | Before | After |
| --- | --- | --- |
| An SC source record type | no | yes, 10 families |
| SC state vs federal ownership enforced | no | **yes — a federal agency blocks the record** |
| Agency-specific source must name its state agency | no | yes, or it is incomplete |
| Recognition relevance as an independent set | no | yes, no inference between tiers |
| SC routing that keeps lanes distinct but joinable | no | yes |

## Live SC coverage: now

```text
Live SC source coverage:   NONE
SC sources monitored:      0
SC sources identified:     0
SC seed entries:           7 (categories only)
Seed entries monitorable:  0
Seed entries with a URL:   0
SC coverage complete:      NOT CLAIMED
65% improvement:           NOT CLAIMED
```

**No SC seed carries a URL, and that is the honest state.** The federal lane
could name grants.gov, federalregister.gov and sam.gov because those are
canonical public entry points and a matter of public record. There is no
equivalent South Carolina address this repo can assert without research.

Writing a plausible-looking state portal URL would fabricate a source, and
`source_seed_real_url_guard_service` exists because that has been a problem here
before. A catalog of invented URLs would look like progress and would send a
tribal grant office to pages that do not exist.

`native_relevance_expected` is `False` on every seed for the same reason:
whether an SC source tends to carry Native-relevant opportunities is a finding,
not an assumption, and nothing has been examined.

## Federal / SC split: now

The rule is **SC-specific is not SC-only**, already stated in
`sc_state_source_adapter_config_service` as
`organization_geography_must_not_filter_federal`. Gate 78 enforces it at record
and routing level:

- An SC state source that names a federal agency is **blocked**, and the value
  is recorded as `rejected_federal_agency` rather than carried.
- `funding_lane` separates `sc_state` from `federal_sc_relevant`; the two lane
  sets are disjoint and an invariant fails an opportunity claiming both.
- A federal opportunity relevant to SC keeps `funding_lane="federal_sc_relevant"`,
  keeps its federal agency, and still sets `sc_relevant=True` so it joins the
  customer's SC view.

That last point is the design: **the customer sees one list; the counts stay
honest.** Collapsing federal into state would undercount federal and overcount
state coverage — and for a tribal organization in a state with few
state-administered Native programs, that would understate their real options.

## Recognition routing: now

Inherited, not restated. `recognition_routing_contract_service` (Block 27)
already says *"State-recognized status is never treated as federally
recognized"*. Gate 78 makes it operational for SC, where it is the local case
rather than an abstraction: South Carolina has state-recognized tribes.

- `state_recognized_relevant` never implies `federally_recognized_relevant`,
  and vice versa. Both directions tested.
- Both may be held together when both are supplied.
- Absent tags stay `unknown`.
- Each tier is credited only by evidence mapped to that tier.

Vocabularies bridge onto the existing Gate 56 `RECOGNITION_ROUTES` and
`SC_CATEGORIES` rather than forking them; tests assert every value projects into
the existing sets.

## Eligibility boundary

Two facts this lane is good at establishing are explicitly **not** eligibility:

- **SC location relevance.** A grant located in South Carolina may restrict
  applicants to state agencies.
- **Native relevance.** A grant can be unmistakably about Native communities and
  still be closed to Native organizations.

Both are accepted as inputs so they can be recorded as refused, and eligibility
stays `unknown` unless evidence names an applicant type. Telling a tribal
organization they are eligible for something they are not costs them weeks of
unpaid work.

## Fixture mutation status

```text
Committed corpus fixtures mutated:  NONE
Latent write paths remaining:       0
Guarded write paths:                6 across 4 services
```

### Correction to Gate 77B

Gate 77B reported **two** latent persist services. **There are three.** My 77B
survey piped its grep through `head -20` and I reported the truncated list as
complete.

| Service | Committed fixtures | Status |
| --- | --- | --- |
| `tribal_grant_eligibility_reingest_service` | `nf15_eligibility_reingest_pulls.json` | guarded in 77B |
| `scaled_federal_corpus_persist_service` | `la_scaled_federal_grants.json` | **guarded now** |
| `tier2_state_corpus_persist_service` | `ta_tier2_state_grants.json`, `ta_mixed_tier13_grants.json` | **guarded now** |
| `tier3_foundation_corpus_persist_service` | `ta_tier3_foundation_grants.json`, `ta_mixed_tier13_grants.json` | **guarded now** |

**Five committed fixtures, not three.** `ta_mixed_tier13_grants.json` is written
by *two* services and is also one of the five files carrying the
`nf13-real-fed-021` SAMHSA record — so the record Gate 77 nearly lost had two
more unguarded write paths than Gate 77B identified.

All six write sites now route through `resolve_writeback_path`.

### The outer guard

`scripts/verify_nativeforge_fixture_cleanliness.sh` checks the class rather than
each instance. The per-service guards protect known paths; a future service, or
one nobody surveyed, would slip past them. The script does not care *how* a
fixture changed, only that none did — and it additionally checks the SAMHSA
record by content, so the corruption is caught even if someone commits it.

Run with `--run-suite` to execute the discovery/corpus suite first.

## Owner-blocked

- **Identifying actual SC sources** — research work: does SC have a central
  grant portal, which agencies publish opportunities, which regional funders
  serve Native organizations. Until this happens the SC lane has a contract and
  no contents.
- Robots/terms review per source, once sources exist.
- External verification of SAMHSA `SM-26-024`.
- Real `OIDC_*` credentials, managed Postgres, migration 0028, backup/restore,
  pen test, Slack webhook.

## Engineering-blocked

- Auditing the five demo/artifact fixture writers surfaced in doc 433
  (`nm_wa_*`, `nofo_showcase_intelligence_pack`, `sc_monday_curated_pack`) —
  they write under `fixtures/` but to demo paths rather than corpus evidence.
- Wiring the cleanliness script into a pre-push or CI step.
- SC source persistence and RLS; gates 80–86.

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

What genuinely changed: the SC lane can express what a South Carolina source is
and what it is not, federal opportunities cannot be relabelled as state ones,
state recognition cannot be mistaken for federal recognition, and no committed
corpus fixture can be rewritten by running the suite.

What did not change: zero SC sources are identified, so the SC lane is a
contract with nothing in it. That is the next real piece of work, and it is
research rather than engineering.
