# 427 — Gate 77G: Production readiness delta

Gate 77 built the federal source lane and triaged the corpus failure. It fetched
nothing and monitored nothing.

## Federal lane: now

| | Before | After |
| --- | --- | --- |
| A federal source record type | no | yes, 8 families |
| Department vs operating division modelled | **no** | **yes — `agency` + `subagency`** |
| IHS/SAMHSA distinguishable | only inside the NF-16 guard | yes, as a reusable contract |
| Agency-specific source must name its division | no | yes, or it is incomplete |
| Monitoring gated on robots/terms | inherited from Gate 76 | enforced here too |

The load-bearing rule: **a parent department is not a program.** Gate 77's triage
proved it with a live case — a Grants.gov search for a SAMHSA seed returning an
IHS opportunity. `federal_agencies_align` returns
`different_subagency_same_department` for that pair, and a department-level
identifier cannot confirm a program-level one
(`subagency_required_but_only_department_supplied`).

## Live federal source coverage: now

```text
Live federal source coverage: NONE
Federal sources monitored:    0
Federal sources fetched:      0
Federal seed entries:         6 (categories and public entry points)
Seed entries monitorable:     0
Seed entries with a URL:      3 (grants.gov, federalregister.gov, sam.gov)
Federal coverage complete:    NOT CLAIMED
65% improvement:              NOT CLAIMED
```

Three of six seeds have no URL deliberately. Agency NOFO pages, agency program
pages and Native-specific program pages are enumerated as **categories**;
naming a specific one would fabricate a federal source. The Native-specific lane
is the highest-value one and is deliberately the emptiest, because asserting that
a particular program page exists and serves a particular applicant type is a
factual claim about a real federal program that repo data cannot support.

## Native eligibility evidence: now

Per-tier resolution from cited evidence, with three inferences refused:

- **Keyword-only matching.** "Tribal" in a title is not eligibility.
- **Parent-agency mission.** IHS serving Native people does not open every IHS
  opportunity, and says nothing about a SAMHSA one.
- **Unbound applicant codes.** Grants.gov codes and assistance-listing applicant
  types are strong evidence only when tied to a specific opportunity or listing.

Narrative sources need a quoted statement — the document existing proves
nothing.

The three recognition tiers stay independent. Federally recognized tribal
governments, state-recognized tribes and Native nonprofits are different
applicant types; evidence for one credits only that one. Absent evidence yields
`unknown`, never `not_eligible` — asserting ineligibility on no grounds would
discourage a real applicant from a grant they might well be entitled to.

A bound applicant code that names no tier yields `possibly_eligible` across
tiers with human review required. That is the honest middle.

## Corpus status

**Quarantined, visibly. Two tests, not one.**

```text
tests/test_sprint345_nf15_corrected_corpus.py
  test_reingest_fixes_placeholder_grants            SKIPPED (quarantined)
  test_corrected_corpus_no_tribal_federal_irrelevant SKIPPED (quarantined)
```

Root cause: both call `reingest_nf13_placeholder_grants()`, which makes live
HTTP requests to `api.grants.gov` with no injected transport. Online both fail;
offline the first still fails and the second passes only via the `no_live_nofo`
bypass in the ownership guard.

`test_reingest_fixes_placeholder_grants` was failing in **both** network states
and was invisible to every `-k` expression used across Gates 63–77. It has been
red without anyone seeing it.

**No corpus agency was changed and no guard logic was touched.** A Gate 77 test
asserts `CrossProgramProxyError` and `assert_source_program_ownership` still
exist and still raise. Full evidence in doc 423.

## Owner-blocked

- **External verification of SAMHSA `SM-26-024`** — is it still posted, and what
  is its current opportunity id? Needed to unquarantine by the data route.
- **Robots/terms review decisions per federal source** — the gate standing
  between this registry and any fetching at all. A legal/policy judgement.
- Whether to use the Grants.gov public API, a key, or bulk download.
- Real `OIDC_*` credentials (Gate 69), managed Postgres, migration 0028 approval,
  backup/PITR/restore drill, pen test, Slack webhook.

## Engineering-blocked

- **A recorded transport fixture for `nf-seed-2026-fed-021`** — the better
  unquarantine route, and correct regardless of the data question: a unit test
  should not depend on a third party's search ranking.
- **An audit of the suite for live network I/O**, requiring injected transports.
  Only one test file reaches it today, so the blast radius is contained, but the
  pattern should not spread.
- Enumerating real agency NOFO pages and Native-specific program pages.
- Federal source persistence, its migration and RLS policies.
- Scheduler (80), NOFO parser (81), duplicate/spam control (83), correction loop
  (84), measured baseline (85) using the existing Gate 54 scorer, 65% campaign (86).

## Controlled customer pilot delta

**None.**

```text
Controlled customer pilot:    NO_GO
Production rollout:           NO_GO
Customer login live:          NO
Production storage live:      NO
Customer persistence:         NO
Pen-test passed:              NO
```

What genuinely changed: the federal lane can now express the difference between
a department and a program, which is the distinction that a live API was
actively getting wrong. A source cannot be monitored before its terms are read,
an agency-specific source cannot hide behind its department, a keyword cannot
become eligibility, and a recognition tier cannot borrow another's evidence.

What did not change: zero federal sources are monitored, and a discovery engine
with zero monitored sources discovers nothing.
