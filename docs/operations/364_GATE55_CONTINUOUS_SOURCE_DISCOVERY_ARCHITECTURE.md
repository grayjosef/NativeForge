# 364 — Gate 55: Continuous source discovery + scraping safety

Status: contracts implemented and tested. **No network I/O is performed.**
Service: `src/nativeforge/services/continuous_source_discovery_service.py`
Tests: `tests/test_tenant_authority_discovery_gate51_57.py`

## Scope

This is the contract layer that decides what *may* be monitored and how a
source's freshness may be described. It performs no fetching. Live ingestion
remains **not claimed** — every record carries `live_ingest_claimed=false`.

Two rules do most of the work:

1. a source cannot reach `monitoring` without human review
2. freshness is only ever reported from a recorded timestamp, never inferred

## Candidate lifecycle

`discovered` → `triaged` → `approved_for_monitoring` → `monitoring`
→ `stale` / `retired`

Terminal-block states: `blocked_terms`, `blocked_low_quality`, `retired`.
Plus `unknown`, which is never promotable.

Only `triaged` and `approved_for_monitoring` are promotable. A `discovered`
candidate must be triaged first — arriving in the system is not a
qualification.

## Promotion gate

`evaluate_source_promotion` denies unless **all** hold:

- state is promotable (not `discovered`, `unknown`, or blocked)
- terms review is not `not_reviewed`, `unknown`, or `prohibited`
- `robots_allows` is not `False`
- provenance is complete (publisher + url + extraction timestamp)
- an `approver_id` is present — **human review is mandatory**

Denial emits `source_candidate_blocked` with reasons; success emits
`source_candidate_promoted`. There is no automatic path to `monitoring`.

## Scraping safety

- **Prefer APIs, RSS and public feeds.** `access_method_preferred` is computed
  so html scraping is visibly the fallback, not the default.
- **Rate limit** — `rate_limit_per_min` defaults to 10 per source.
- **Terms and robots** — `prohibited` terms or `robots_allows=False` force the
  candidate into `blocked_terms` at construction time, not at promotion time.
  An invariant additionally fails any record that is somehow `monitoring` while
  prohibited or robots-disallowed.
- **Provenance recorded** — publisher, source url, source timestamp, extraction
  timestamp.
- **Extraction confidence** clamped to 0.0–1.0.
- **Never authoritative without metadata** —
  `authoritative_without_metadata=false`.

## Freshness

`evaluate_source_freshness` takes explicit integer day counts rather than
reading the clock, so results are deterministic and cannot silently drift in
tests. With either timestamp missing it returns `unknown` with
`counted_as_fresh=false` — it never guesses. Crossing `stale_after_days`
(default 30) returns `stale` and emits `opportunity_source_stale`.

A stale source stays visible as stale. It is not hidden and it is not quietly
refreshed.

## Dedupe

`dedupe_candidates` fingerprints on normalised title + url. Duplicates are
**flagged with `opportunity_duplicate_flagged`, not silently dropped**, so the
duplicate rate stays measurable for Gate 54 rather than being hidden by the
dedupe step itself.

## Proven by test

- unknown source cannot be promoted without review
- terms-prohibited source is forced to `blocked_terms` and cannot promote
- robots disallow blocks promotion
- promotion requires both complete provenance and a human approver
- stale stays stale; missing timestamps yield `unknown`, never fresh
- duplicates are flagged and counted, not dropped

## Not done

No scheduler, no fetcher, no live probes. Those need the storage and security
gates that remain NO_GO. What exists is the safety contract they would have to
pass through.
