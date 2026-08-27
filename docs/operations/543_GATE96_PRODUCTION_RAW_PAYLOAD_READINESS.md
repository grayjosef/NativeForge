# 543 — Gate 96C/E: repository and production readiness

**Migration 0028 adds a metadata table only. The production body store remains
unconfigured, so the production raw payload store remains unavailable.**
Collectors remain inactive, no live fetch occurred, no source monitoring
started, no live source coverage claimed. The local store and the production
store are different things.

## The derivation

```text
metadata_table_available      true    Alembic 0028
secret_scan_available         true    Gate 95D
promotion_gate_available      true    Gate 95E
body_store_configured         FALSE   no client, no bucket, no credential

production_raw_payload_store_available = all four
                                       = false
production_storage_live                = available AND collectors_active > 0
                                       = false
```

Both verdicts are **derived from the component set**, never set beside it. A
test fakes `production_raw_payload_store_available: True` and the invariants
report three separate failures, including
`local_store_counted_toward_production_availability` — because the only way that
flag could go true today is by miscounting the local store.

`production_storage_live` is deliberately stricter than `available`. A store can
be ready and not running, and collapsing the two is how "we built it" becomes
"it is running".

## Each component is established by looking

```text
metadata_table_available   migration file present, or SQLAlchemy inspection
                           when a session is supplied
body_store_configured      importlib.util.find_spec for four client libraries
                           AND three settings on the Settings model
secret_scan_available      the module imports and the callable exists
promotion_gate_available   the module imports and the callable exists
```

Nothing accepts a caller saying a component exists. That is the Gates 87–89
lesson applied to infrastructure instead of to records.

## The repository writes metadata only

`production_raw_payload_repository_service` is the seam between an evidence
record and `nf_raw_source_payloads`.

`body_write_allowed` is `False` unconditionally, and `store_body=True` **raises**
rather than being ignored — a caller asking this repository to hold a body has
misunderstood which layer they are at, and a silent no-op would let them keep
believing it.

It does not decide whether a payload is evidence. It calls Gate 95's
`evaluate_payload_promotion` and refuses whatever that refuses: findings_blocked,
unresolved redaction, `TERMS_REVIEW_REQUIRED`, `HUMAN_REVIEW_ONLY`, a failed
parse, a live payload with no preflight.

Two gates agreeing is not redundancy. The promotion gate answers *"is this
evidence?"*; the repository answers *"may I persist it?"*, and the second fails
for reasons the first never sees.

## evidence_ready needs somewhere for the body to be

A row marked `evidence_ready` asserts the bytes are retrievable. With no body
store they are not, so the assertion would be false the moment it was written.

```text
promotion_allowed = promotion_gate_says_yes AND body_store_configured
                  = false, today, for every payload
```

**Quarantined metadata may still be written.** Recording that a payload exists
and is not yet usable is exactly what quarantine is for, and a test writes one
and asserts the stored `promotion_status` reads `quarantine` — the repository's
resolved status, not the payload's optimism.

## dry_run is the default

`persist_payload_metadata(dry_run=True)` returns the decision without touching a
session. Persisting requires **both** a session and `dry_run=False`, so
forgetting an argument produces "nothing happened" rather than "something
happened in production".

## Collection intent

Gate 96 adds a `collection_intent` to the activation preflight:

```text
dry_run           accepts local_only or production   (scaffolding)
live_collection   accepts production only            (real collection)
```

A live collection on a local-only store is refused, and an invariant fails any
result that allows one. An unrecognised intent falls back to `dry_run` — the
*lesser* capability, which is the safe direction for a fallback.

Today `detect_store_implementation()` returns `local_only`, so every
`live_collection` preflight blocks on `store_supports_collection_intent`.

## next_required_actions

Ordered by what blocks first, and naming the decision rather than the gap:

```text
1  choose an object store, add its client to the dependency set, and add
   endpoint/bucket/credential settings
2  implement the body store against the four required guarantees
```

"Body store missing" is not actionable. "Choose an object store and add a
client" is.
