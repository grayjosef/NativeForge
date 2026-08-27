# 542 — Gate 96D: production body store contract

**The production body store remains unconfigured.** Migration 0028 adds a
metadata table only; the production raw payload store remains unavailable until
a body store exists. Collectors remain inactive, no live fetch occurred, no
source monitoring started, no live source coverage claimed.

## Four modes, one production-capable

```text
object_store_required          the only mode a live collector may run on
database_small_payload_only    tests and tiny fixtures. Never production.
local_dev_ignored              Gate 95's per-checkout store. Never production.
unconfigured                   the default, and the current state
```

`PRODUCTION_CAPABLE_MODES` is a named set of one. It is never computed by
removing the modes that do not qualify, so widening it is a visible edit rather
than a side effect.

## Why database_small_payload_only is not a production option

"Small" is not a property of a source response. It is a property of the
responses you happened to have seen so far. The Grants.gov extract is ~78 MB,
its description field runs to 18,000 characters and its eligibility text to
4,000 — and the size of tomorrow's response is not something a schema can
promise.

A mode that works until it does not is worse than one that refuses from the
start, because the failure arrives in production with a full disk rather than in
review with a rejected design.

## Why local_dev_ignored is not production either

It is per-checkout, gitignored, with no durability and no cross-process
retrieval. A payload whose bytes exist only in one developer's working
directory is not evidence anyone else can retrieve, which is the entire property
evidence needs to have.

`local_dev_counts_as_production` is `False` on every contract, checked by an
invariant.

## Detected, never declared

```text
detect_body_store_mode()
  importlib.util.find_spec for boto3 / minio / google.cloud.storage /
                               azure.storage.blob
  AND all three settings present on the Settings model:
      raw_payload_object_store_endpoint
      raw_payload_object_store_bucket
      raw_payload_object_store_credential
  -> "object_store_required"
  otherwise -> "unconfigured"
```

As of Gate 96: **no client installed, zero of three settings present.** The
detector returns `unconfigured` and no argument to any function in this module
can change that.

`build_body_store_contract(declared_mode=...)` accepts what a caller *believes*
is configured. It records it, compares it against what was detected, and reports
`declared_mode_does_not_match_detected` when they disagree. It never lets the
declaration win — a flag saying a component exists is the same shape as the
corpus flags Gates 87–89 unpicked: a claim about a claim.

A test passes `declared_mode="object_store_required"` and asserts
`body_store_configured` is still `False`.

## Four guarantees, all required

```text
content_addressed                     same bytes, same location
hash_preserving                       what you stored re-derives its own hash
secret_scan_clean_before_promotion    Gate 89's JWT arrived inside a response
no_body_values_in_logs                a log line is a copy
```

An implementation satisfying three of four does not qualify. The list is
compared element-wise by an invariant, so shortening it fails rather than
quietly loosening the bar.

## What a future integration must add

```text
1  choose an object store and add its client to the dependency set
2  add endpoint / bucket / credential settings to the Settings model
3  implement against all four guarantees
4  prove it in staging before any production claim
```

Step 4 is the one this campaign keeps having to re-learn: the readiness service
will flip `body_store_configured` to true the moment steps 1–2 are done, and
that is *not* the same as the store working. `production_storage_live` stays
false until a collector is actually active, which is a separate decision with
its own preflight.
