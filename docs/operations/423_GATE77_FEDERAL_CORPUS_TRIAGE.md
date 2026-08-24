# 423 — Gate 77A: Federal corpus defect triage

## Classification

**5 — UNKNOWN, needs external verification.** With a more specific root cause
than the category name suggests:

> **The test performs live HTTP requests to `api.grants.gov` at test time.** It
> is non-deterministic, and today the live search for a SAMHSA seed returns an
> IHS opportunity.

Not classification 1 (corpus agency wrong), 2 (source agency wrong), 3 (stale
fixture) or 4 (needs a parent/subagency model — one already exists in the guard
and it is correct).

## Evidence

### The corpus agency is right, and consistent

`nf13-real-fed-021` appears in five fixtures. **Every one says
`"agency": "SAMHSA / HHS"`**:

```text
fixtures/real_grants_corpus/nf13_real_ingested_grants.json
fixtures/real_grants_corpus/nf14_mixed_corpus.json
fixtures/real_grants_corpus/la_scaled_federal_grants.json
fixtures/real_grants_corpus/ta_mixed_tier13_grants.json
fixtures/recognition_requirement_regression_snapshot.json
```

Recorded values: opportunity number `SM-26-024`, title "Tribal Behavioral
Health: Suicide Prevention", grants.gov id `361976`.

The recorded re-ingest pull (`nf15_eligibility_reingest_pulls.json`) also shows
`agency: "SAMHSA / HHS"`, `diagnosis: refined_hit_matched`, and
`no_proxy_substitution: true`.

### The source agency is right

```text
seed nf-seed-2026-fed-021
source_name: "SAMHSA / HHS — AI/AN Zero Suicide & Suicide Prevention"
```

### The string `HHS-IHS` exists nowhere in the repo

`grep -rn "HHS-IHS" --include=*.json --include=*.py fixtures/ src/ tests/`
returns **nothing**. It is constructed at runtime from a live API response.

### What the live API returns today

```text
seed:                  SAMHSA / HHS — AI/AN Zero Suicide & Suicide Prevention
diagnosis:             refined_hit_matched
chosen_opportunity_id: 363496
payload agency:        'HHS-IHS'
payload number:        'HHS-2027-IHS-SPIP-0001'
payload title:         'Suicide Prevention, Intervention, and Postvention'
```

Different agency, different opportunity number, different fiscal year from the
recorded `SM-26-024` / `361976`.

### The call path is live and un-injected

```text
classify_nf15_corrected_corpus
  → build_nf15_corrected_corpus
    → reingest_nf13_placeholder_grants
      → reingest_tribal_grant_eligibility
        → fetch_refined_grants_gov_for_seed(source)        # no http_post injected
          → fetch_grants_gov_opportunity_detail(...)        # http_post=None
            → default_grants_gov_http_post
              → httpx → https://api.grants.gov/v1/api/search2
```

`fetch_mode` defaults to `FETCH_MODE_LIVE`.

### The decisive experiment

| Condition | `test_reingest_fixes_placeholder_grants` | `test_corrected_corpus_no_tribal_federal_irrelevant` |
| --- | --- | --- |
| **Online** | FAIL (`CrossProgramProxyError`) | FAIL (`CrossProgramProxyError`) |
| **Offline** (proxy blackholed) | FAIL (`assert fed021["reingested"] is True`) | **PASS** |

The corpus test passes offline only because an empty payload list routes through
`build_no_live_nofo_grant`, and `assert_source_program_ownership` returns early
on `no_live_nofo`. **Passing offline is an artifact of that bypass, not evidence
of correctness.**

## Two failures, not one

The Gate 76 broad run reported only the corpus test.
`test_reingest_fixes_placeholder_grants` **also fails, in both network states**,
and was invisible to every `-k` expression used across Gates 63–77 — none of
their terms match its name. It has presumably been red for some time with nobody
seeing it.

## The guard is correct and was not weakened

`assert_source_program_ownership` refuses to attribute an `HHS-IHS` opportunity
to a `SAMHSA / HHS` source. That is precisely what NF-16 ("no-proxy honesty —
kill cross-program substitution") built it to do, and the refusal is the system
working.

Collapsing IHS and SAMHSA because both report to HHS would be wrong on the
merits — they are separate operating divisions with separate appropriations,
separate NOFOs and separate applicant rules — and is explicitly forbidden by
this gate. Gate 77's `federal_agencies_align` encodes the distinction and returns
`different_subagency_same_department` for exactly this pair.

**No corpus agency was changed. No guard logic was touched.** A test asserts the
guard still raises.

## Action taken: quarantine, visibly

Both tests carry `@pytest.mark.skip` with a shared reason naming the cause, the
evidence, and what unquarantines them. Neither test was deleted, following the
retirement pattern in doc 395.

## Why it was not "fixed"

Three options, two rejected:

1. **Change the corpus agency to `HHS-IHS`.** Rejected — it would fabricate
   agency ownership, contradict five fixtures, and make the guard pass by
   corrupting the data it protects.
2. **Relax `_agencies_align` to treat shared departments as aligned.** Rejected —
   weakens the guard, forbidden by the gate, and would silently re-enable the
   substitution class NF-16 eliminated.
3. **Quarantine and document.** Chosen.

Determining whether SAMHSA `SM-26-024` is still posted, and what its current
opportunity id is, requires checking a live external system and making a factual
claim about a real federal NOFO. That is not derivable from repo data.

## What unquarantines these tests

Either of:

- **A recorded transport fixture** for `nf-seed-2026-fed-021` so the re-ingest
  runs hermetically against a captured response. This is the better fix
  regardless of the data question: a unit test should not depend on a third
  party's search ranking. It needs a captured payload, which means one
  deliberate recording run.
- **External verification** of the current SAMHSA NOFO plus a re-tuned
  `SEED_SEARCH_KEYWORD_OVERRIDES` entry, confirmed to retrieve a `SAMHSA / HHS`
  opportunity.

## A third defect, found while triaging

**Running the test suite overwrites a committed corpus fixture.**

`tribal_grant_eligibility_reingest_service` writes its results back to
`fixtures/real_grants_corpus/nf15_eligibility_reingest_pulls.json`. That file is
tracked, and it is the repo's recorded evidence of the SAMHSA opportunity.

During Gate 77's offline experiment the file was rewritten to:

```text
- "reingested": true                          + "reingested": false
- "diagnosis": "refined_hit_matched"          + "diagnosis": "search_api_error: [Errno 111] Connection refused"
- "chosen_opportunity_id": "361976"           + (removed)
- "opportunity_number": "SM-26-024"           + "opportunity_number": "FED-021"
```

So a single test run destroyed the recorded evidence for `SM-26-024` and
replaced it with a connection-error placeholder. An **online** run would have
been worse: it would have written the `HHS-IHS` substitution into the fixture as
though it were recorded fact, which is precisely the fabricated agency ownership
this gate forbids.

The change was reverted with `git checkout --` on that one file; the fixture now
reads `reingested: true`, `chosen_opportunity_id: 361976`,
`agency: "SAMHSA / HHS"`, `opportunity_number: "SM-26-024"`,
`no_proxy_substitution: true`, as committed.

This is a self-corrupting evidence file: the artifact recording what was
observed is rewritten by observing again. Quarantining the two tests stops it
for now — they are the only callers reaching that write — but the write-back
itself should move behind an explicit "record a new pull" flag rather than
happening as a side effect of running tests.

## The wider issue this exposes

The backend suite makes live third-party API calls. Consequences:

- CI results depend on Grants.gov availability and ranking.
- A green run may reflect an offline bypass rather than correct behaviour.
- Repeated suite runs send unthrottled traffic to a public federal API.

Only `tests/test_sprint345_nf15_corrected_corpus.py` reaches this path today, so
the blast radius is contained. Worth a dedicated gate: audit the suite for
network I/O and require injected transports.
