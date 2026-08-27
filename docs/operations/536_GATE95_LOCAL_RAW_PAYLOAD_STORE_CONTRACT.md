# 536 — Gate 95C: local raw payload store contract

**A local raw payload store now exists. A production one does not.** No
collectors were activated, no live fetch occurred, no source monitoring started.
This does not change Baseline X live coverage.

## What it is for

Tests, fixtures, and future collector dry-runs. It is deliberately local and the
module says so in every result: `storage_mode: local_dev_only`,
`production_raw_payload_store_available: False`, with an invariant that fails any
result claiming otherwise.

## Refuses by default, twice

```text
local_storage_enabled   defaults False -> a write raises
customer_data_allowed   defaults False -> a customer-data payload raises
```

Two switches because they are two different mistakes. Writing when you meant to
dry-run is not the same as writing customer data into a developer's checkout,
and one opt-in should not grant the other.

It **raises** rather than returning a sentinel, following Gate 77B: a silent
no-op is indistinguishable from a successful write, which is how a corpus
fixture got overwritten with a placeholder.

## Content-addressed

```text
bodies/<hash[:2]>/<hash>.bin
metadata/<payload_id>.json
```

The same bytes stored twice land in the same path, so a re-fetch does not
duplicate storage and the second write reports `deduplicated`. A corrupted file
is detectable by re-hashing it against its own path —
`verify_stored_payload` does exactly that, and a test tampers with a stored body
to prove the check is not vacuous.

## The caller supplies retrieved_at

The store never calls `now()`. A timestamp the store invents describes the
store, not the fetch, and it would make the same payload write differently on
every run — which the determinism tests would then have to be loosened to
tolerate. A test parses the module and asserts no `now()` or `utcnow()` call
exists.

## Secrets never reach disk unredacted

Every write scans first. Findings block the write unless a redacted body is
supplied, and then the **redacted** body is what gets stored, under the redacted
hash. The store re-scans the redacted body and refuses if anything survives —
it does not take the caller's word that redaction worked.

## Live payloads need a passed preflight

A `created_from_live_fetch` payload with no activation preflight raises; one
with a failed preflight raises. A **fixture** payload needs neither: no source
was contacted, so there is no activation to have. Requiring one would make it
impossible to build test evidence without pretending a collector is live, and
that pretence is what this campaign spends its time removing.

## Headers are hashed, never stored

`Authorization` and `Set-Cookie` live in headers. The store keeps
`response_headers_hash` and nothing else, and a test asserts the metadata file
contains no `response_headers` key.

## Not in git — and this needed a change

`artifacts/` is **not** gitignored in this repo. A dozen artifact directories are
committed deliberately, so a payload store written under `artifacts/` would have
been one `git add artifacts/...` away from putting agency response bodies, and
any credentials inside them, into history.

That is the Gate 89 JWT finding with a new directory name. Gate 95 adds:

```gitignore
artifacts/raw_payload_store/
```

The readiness artifacts live in `artifacts/raw_payload_store_readiness/` —
a **different** directory — precisely so one is committable and the other is
not. A test asserts the store root is an actual ignore rule and the readiness
directory is not, parsing rules rather than matching substrings (the readiness
name appears in the rule's explanatory comment, which a substring check reads as
an ignore).

## Nothing here fetches

No HTTP client, no transport, no URL retrieval. The store takes bytes the caller
already has, and a test parses the module to confirm no network library is
imported.
