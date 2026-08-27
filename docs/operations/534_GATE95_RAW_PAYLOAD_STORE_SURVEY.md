# 534 — Gate 95A: raw payload and persistence survey

## Existing raw payload storage: none

There is no table, no directory, and no service that durably retains a source
response body. `grep` for `raw_payload` in `src/` returns six modules, and all
six hold response text in a local dict during a run and persist only the
**parsed** result:

```text
tier1_batch_live_fetch_service          tier2_state_batch_live_fetch_service
tier3_foundation_batch_live_fetch_service
scaled_federal_corpus_persist_service   tier2_state_corpus_persist_service
tier3_foundation_corpus_persist_service
```

This is the mechanism behind the number Gates 87–89 spent four gates measuring:
**185 corpus records, 18 with independent transport evidence.** The bytes were
never kept, so the other 167 cannot be re-derived — only believed.

## Existing source check run storage: shape without evidence

`nf_source_check_runs` (Alembic 0015) records what a check *did*, not what it
*received*:

```text
check_mode  check_status  started_at  completed_at
opportunities_seen_count  new_candidates_count  accepted_count
duplicate_count  rejected_count  review_items_created_count
error_code  error_message  operator_notes  result_summary_json
```

No body, no hash, no response status, no headers, no per-payload
`retrieved_at`, no scan status. A run can report "42 opportunities seen" with
nothing behind it.

`nf_opportunity_sources` carries the scheduling columns (`check_interval_days`,
`next_check_due_at`, `consecutive_failure_count`) — the seam a future scheduler
attaches to, still unused for the v2 registry.

## The one adjacent table, and why it is not the answer

`nf_evidence_intake_records` (Alembic 0022) has an encouraging shape:

```text
storage_mode  storage_reference  hash_or_digest  file_name  mime_type
size_bytes  review_status  human_review_required
```

**It is a different domain.** Its rows are *customer application* evidence —
checklist items, binder items, forms attachment maps, package export previews.
Reusing it for agency HTTP responses would conflate a Tribe's uploaded
authority document with a Grants.gov response body, in one table, under one
retention policy, with one review workflow. Those need different answers.

What it *is* good for is precedent: it stores a **reference plus a digest**, not
a blob in a column. Gate 95's model follows that shape (`raw_payload_ref` +
`response_body_hash`).

## Migration candidates

25 Alembic revisions, latest `0027_rls_membership_authority`. A
`nf_raw_source_payloads` table would be `0028`.

**Gate 95 does not add it.** A migration is a production-storage commitment, and
production storage is not live — adding the table would make
`production_raw_payload_store_available` ambiguous the moment it merged. The
contract and the local store come first; the migration is the next gate's work,
with a real decision behind it.

## Production storage: not live

```text
db/session.py            sqlite by default; postgres path exists
api_enforcement_service  "production_storage_claimed": False
production_storage_owner_decision_service   an owner decision, still open
```

`customer_data_policy_service.STORAGE_MODES` is the existing vocabulary and
Gate 95 bridges onto it rather than inventing a second one:

```text
not_stored  local_dev_only  fixture_only  production_metadata_only
production_object_storage  external_source_reference  blocked  unknown
```

Gate 95's local store operates at `local_dev_only`. Nothing in this gate reaches
`production_object_storage`.

## Secret scan / redaction utilities: none for this purpose

`ls src/nativeforge/services/ | grep -iE 'secret|redact|scrub|sanitiz'` returns
nothing. The nearest thing is `payload_safety_hardening_service`, which escapes
control characters and Slack markup for **user-visible text** — an output-safety
concern, not a credential-detection one. It does not look for tokens.

So the scanner in 95D is new. It is needed because Gate 89 found a committed
143-character HS256 JWT in
`fixtures/source_ingestion/grants_gov_fetch_opportunity_362648.json`, tracked
since 2026-06-20 and not gitignored. That fixture is **still present and still
unmodified** — this gate does not touch it, per instruction. It is used as the
scanner's proving case: a test asserts the scanner finds a JWT in a
locally-constructed copy of that *shape*, without reading or printing the real
file's token.

## Artifact conventions, and a real hazard

```text
committed:  artifacts/discovery_baseline_x/  artifacts/phase1_collector_readiness/
            artifacts/source_registry_external/  artifacts/repo_health/  …
```

Artifacts are written by a single writer module per family, refuse to write when
an input carries a forbidden claim, and are compared against a fresh generation
by a test.

**`artifacts/` is not gitignored.** `.gitignore` mentions it only in a Playwright
comment, and a dozen artifact directories are committed deliberately. So a
payload store written under `artifacts/raw_payload_store/` is one
`git add artifacts/...` away from putting agency response bodies — and whatever
tokens they contain — into git history.

That is the Gate 89 failure mode with a new directory name. **Gate 95 adds an
explicit `.gitignore` rule for the payload store root**, so the default is that
bodies stay out of git and only the readiness artifacts under a separate
directory are committable.

## Where future collectors write

```text
1  guard      live_network_guard_service          may this request go out?
2  fetch      the approved transport for its purpose
3  store      local_raw_payload_store_service     body + metadata, hashed
4  scan       raw_payload_secret_scan_service     clean, or quarantined
5  promote    raw_payload_promotion_gate_service  evidence_ready, or not
6  parse      only now, and only from stored evidence
7  identity   opportunity_identity_versioning_service
```

Step 6 is the point of the whole gate: parsing happens *after* the bytes are
stored and scanned, so a parsed record always has retrievable evidence behind
it. The current order — parse, persist the parse, discard the bytes — is what
produced 167 unverifiable records.

## What cannot be built until production storage exists

```text
- durable cross-process payload retention (local store is per-checkout)
- retention-policy enforcement over time (nothing expires anything yet)
- multi-tenant payload isolation and RLS
- object storage for bodies larger than a repo should hold
- the 7-day Grants.gov extract window, which needs real durability to be
  meaningful at all
```

The local store is honest about being local: it is for tests, fixtures, and
future collector dry-runs. It is not a production store and this gate does not
claim it is one.
