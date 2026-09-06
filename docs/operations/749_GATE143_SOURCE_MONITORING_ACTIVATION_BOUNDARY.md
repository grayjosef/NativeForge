# 749 — Gate 143: the source monitoring activation boundary

## Seven things a collector must declare

`source_collector_configuration_preflight_service`:

```text
source_id                   and it must pass the allowlist
fetch_mode                  dry_run | live_fetch
rate_limit_policy           declared, not "as fast as it goes"
attribution_requirement     verbatim where the publisher requires it
user_agent_policy           the canonical NativeForge UA, identifiable
raw_payload_storage_policy  where the bytes land
activation_approval         somebody decided
```

Any one missing and the collector is refused **by name**. A test drives each
absence individually.

## Configuration is not activation

`fetch_mode: live_fetch` is a **request**. `activation_approval` is the
permission, and this module cannot manufacture one. Same separation Gate 141B
made for object storage and Gate 142B for email: five settings being filled in
and somebody having decided are different facts.

```text
live_fetch + no approval           -> refused
live_fetch + approval + local store -> refused, nowhere for the bytes
live_fetch + approval + s3          -> activation_approved
```

The last line is reachable in a test and unreachable in runtime:
`object_store_configured` is false (Gate 141), so `s3_compatible_configured` is
not this deployment's policy.

## Five states

```text
incomplete_configuration    a required key is missing
source_not_permitted        the collector is fine; the source is not
configured_dry_run_only     everything declared, nothing live requested
configured_but_unapproved   live requested, something still blocks it
activation_approved         the only state that could run live
```

## A perfectly configured collector still cannot run at a blocked source

```text
seven policies declared, approval present, s3 configured
  + a source with UNKNOWN terms          -> source_not_permitted
```

That ordering is the point of the gate. A collector's own configuration can be
flawless while the thing it points at is one nobody has permission to read.

## What the guard still requires at fetch time

Gate 143 does not replace `live_network_guard_service`; it feeds it. At the
moment of a real fetch, that module still requires all of:

```text
terms_status         NO_REVIEW_REQUIRED or ATTRIBUTION_REQUIRED
activation_status    activation_allowed
collector_status     active
robots_status        allowed or absent      — never fetched, so unknown
credential_status    present_and_valid or not_required
rate_limit_status    policy_declared
user_agent_status    the canonical UA
attribution_status   present_and_verbatim or not_required
```

`robots_status` is worth naming: nothing in this gate fetches a robots.txt, so
it is `unknown` for every source, and `unknown` is not in `ROBOTS_SATISFYING`.
That is one more thing activation would have to do, and it has to be done
politely and per-source.

## What activation would require, in order

```text
1. a terms review per source        171 rows are UNKNOWN; 6 need a human
                                    because the terms page served no text
2. an activation approval per source  a decision, per source, not a global flag
3. robots.txt, fetched politely      per source, at activation time
4. a credential where required       SAM.gov needs a key AND a role
5. a raw payload store               Gate 141: object_store_configured is false
6. a scheduler runtime               absent
7. a background worker               absent
8. a periodic trigger                absent
9. a persistent backend              absent
```

Items 5–9 are the scheduler's own missing components, reported by
`source_scheduler_readiness_service` and carried into this gate's activation
blockers with their owner attached.

## Grants.gov attribution is preserved

Six registry rows resolve to a grants.gov host, and all six are
`human_review_blocked` because the terms page is client-rendered and served no
policy text. If a review later returns `ATTRIBUTION_REQUIRED`, the collector
preflight then requires `attribution_text_verbatim` before any live fetch — a
test drives both halves.

Nothing in this gate weakens that, and nothing in it read those terms.

## SAM.gov stays blocked

```text
rows in the shipped registry     0
terms review queue entry         SAM-CREDENTIAL-ROLE
                                 scraping prohibited; API key AND role required
with a recorded terms review     still api_key_missing
with an activation approval too  still api_key_missing
```

## Production stays false

`production_source_monitoring` has no branch that sets it, and an invariant
fails if a passing preflight ever sets `source_monitoring_live`.
