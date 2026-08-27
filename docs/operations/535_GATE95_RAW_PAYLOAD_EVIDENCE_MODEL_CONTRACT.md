# 535 — Gate 95B: raw payload evidence model contract

**A local raw payload store now exists. A production one does not.** No
collectors were activated, no live fetch occurred, and source monitoring remains
zero. This does not change Baseline X live coverage, which is still 0.

## The number this exists to fix

Gates 87 through 89 measured the corpus from three angles and arrived at the
same place: **185 records, 18 with independent transport evidence.** The other
167 were parsed, the parse was persisted, and the bytes were thrown away. Their
origin can only be believed.

Every flag that appeared to say otherwise turned out to be a hardcoded literal,
and the Sprint 313 guard checking those flags compared flags to flags.

The fix is not another flag. **Raw payload evidence is required before parsed
opportunity data can be trusted as collected** — keep the response, hash it, and
refuse to promote a parse that has no retrievable bytes behind it.

## Deterministic identity

```text
payload_id = SHA-256(source_id | request_fingerprint | response_body_hash)
```

The same response fetched twice yields the same id, so a re-fetch is
recognisable as a re-fetch rather than becoming a second record. A caller may
supply an explicit id; one is generated only when it does not.

A different body yields a different id — an amended response is a new payload,
not an overwrite of the old one.

## Four fields are evidence-critical

```text
source_id  retrieved_at  response_body_hash  raw_payload_ref
```

Missing any one raises `RawPayloadEvidenceError` at construction rather than
producing a record that is 90% evidence. `response_body_hash` must be SHA-256
hex — `deadbeef` is rejected, because a hash that cannot be re-derived is a
label.

## Statuses, and which permit anything

```text
secret_scan_status   pending | clean | findings_blocked | failed
                     only `clean` permits promotion
redaction_status     not_required | pending | completed | failed
parser_status        not_started | parsed | parse_failed |
                     parser_unavailable | human_review_required
promotion_status     quarantine | evidence_ready | rejected | superseded
```

`pending` is not a pass. Gate 89 found a committed JWT precisely because nothing
was ever affirmatively checked, and "not yet found to be dirty" is not "clean".

An unrecognised value resolves to the **blocking** member of its vocabulary, so
a typo blocks.

A parse failure does not invalidate the evidence — the bytes are still the
bytes — but it does stop the record being promoted on the strength of a parse
that did not happen.

## Everything starts in quarantine

`build_payload_evidence` always constructs at `quarantine`. Promotion is a
separate decision made by a separate service (doc 538), so a record cannot
arrive already trusted. That is the structural difference from the corpus flags
that were set at construction and then checked against themselves.

## Provenance is exclusive, and silence is not a third option

`created_from_live_fetch` and `created_from_fixture` cannot both be true — that
raises. Both false is permitted but produces `provenance_unstated` in
`blocked_reasons`, so a record that never said where it came from cannot be
promoted.

This is Gate 88's finding encoded: the corpus contained records whose "recorded"
flag described the flag rather than the fetch.

## What evidence is not

`implies_live_coverage` and `implies_monitoring_active` are `False` on every
record, checked by invariants. A store full of fixture payloads is a store full
of fixture payloads.
