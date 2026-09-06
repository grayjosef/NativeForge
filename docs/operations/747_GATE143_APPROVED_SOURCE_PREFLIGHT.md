# 747 — Gate 143: the approved-source allowlist

## Six states, because "blocked" hides five situations

```text
registry_known        in the 177 seed rows. Says nothing about permission.
fixture_allowed       an nf-fixture- id, hermetic tests only, never a host.
terms_blocked         TERMS_REVIEW_REQUIRED or UNKNOWN
human_review_blocked  HUMAN_REVIEW_ONLY — a person must look first
api_key_missing       a credential nobody has
activation_approved   the only state in which monitoring could begin
```

An operator asking "why can't we monitor this" gets a different answer for each,
and each has a different owner and a different fix. "47 blocked" tells nobody
what to do next.

## Deny by default falls out of the data

The registry has **no terms column**. `NF_SOURCE_SEED_2026.csv` carries:

```text
seed_id  canonical_source_id  source_name  source_url  tier  adapter_key
access_posture_hint  source_health_status  catalog_accounting_bucket
resolver_url_status  health_evidence
```

and nothing about what any publisher's terms of use say. So an unreviewed row is
`UNKNOWN`, and `live_network_guard_service` already puts `UNKNOWN` in
`TERMS_BLOCKING`.

Deny by default is not a rule imposed on top of the registry here. It is what
the registry actually supports. A future gate that adds a terms column has to
fill it in per source, reviewed, before anything changes.

## Where the 177 rows land

```text
terms_blocked           171
human_review_blocked      6
api_key_missing           0    no SAM.gov row exists in the registry
activation_approved       0
monitorable               0
```

## Matched by domain, not by exact host

The first version used an exact-match host set and missed four grants.gov rows:

```text
simpler.grants.gov      4 rows
www.grants.gov          more rows
grants.gov              one publisher
```

The registry has **128 distinct hosts across 177 rows**. Reporting on a name
instead of the thing the name refers to is the defect this campaign keeps
finding, and this was the twelfth instance. `_matches_domain` tests the label
boundary too, so `evilgrants.gov` does not match `grants.gov` — and a test
asserts it.

## The permitted branch is reachable, and needs two things

```text
a recorded terms review alone      -> registry_known, no approval
an activation approval alone       -> terms_blocked, still
both                               -> activation_approved, monitorable
a review that came back
  TERMS_REVIEW_REQUIRED + approval -> terms_blocked
```

`terms_statuses` is injectable because that is the shape the real process has: a
human reviews a source's terms and records the result. Runtime supplies none, so
runtime gets `UNKNOWN` for all 177 rows.

An approval **never clears a blocker**. Both the state machine and an invariant
say so, and the artifact records it as a measured fact rather than a promise.

## ATTRIBUTION_REQUIRED permits collection, and moves the duty

`live_network_guard_service` puts `ATTRIBUTION_REQUIRED` in
`TERMS_NON_BLOCKING`, so a review that comes back with it permits collection —
and the obligation moves to the fetch, where the collector preflight requires
verbatim attribution text before a live fetch is allowed. Intending to attribute
is not attributing.

## A fixture is never monitorable

```text
nf-fixture-*  outside a test   -> unknown_source, refused
nf-fixture-*  in a test        -> fixture_allowed, monitorable: FALSE
```

The fixture branch proves the evaluation path and is never a real host. An
invariant fails if a fixture is ever marked monitorable.

## SAM.gov

Zero rows in the shipped registry, and a test asserts that. The only SAM entry
anywhere is the terms review queue's `SAM-CREDENTIAL-ROLE` item, which records
that scraping is prohibited and that both an API key and a role approval are
needed.

The credential rule is exercised through a probe row supplied to a single call —
adding a SAM row to the registry to test the rule would be fabricating a source.
A test then proves the rule holds even with a recorded terms review AND an
activation approval: `api_key_missing` outranks both.

## Nothing is fetched

```text
fetch_performed   false
robots_fetched    false
dns_resolved      false
network_calls     0
```

The url is parsed for a **host** and otherwise carried as text. A reader needs
it to go and read the terms themselves; returning it is not fetching it.
