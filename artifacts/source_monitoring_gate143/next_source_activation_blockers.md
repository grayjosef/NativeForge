# Gate 143 — what live source monitoring still does not reach

## Where this stands

```text
source_monitoring_preflight_ready   TRUE
source_monitoring_live              FALSE
scope                               controlled_dev_demo
registry rows classified            177
sources cleared for collection      0
```

Every one of the 177 registry rows can be evaluated, and the system can say
exactly what blocks each. **None of them was fetched.**

## Preflight is not monitoring

```text
source_monitoring_preflight_ready   can this system evaluate every source and
                                    prove no live call path is active?   TRUE
source_monitoring_live              is anything actually being checked?  FALSE
```

`source_monitoring_live` is not answered by this gate at all. It is read from
`source_scheduler_readiness_service`, which derives it from four conjuncts and
reports false because five components are absent. An invariant fails if a
passing preflight ever sets it.

## Why every source is blocked

```text
terms_blocked            171
human_review_blocked       6
api_key_missing            0
registry_known             0
activation_approved        0
```

The registry has **no terms column**. It carries a url, a tier, an adapter key,
an access posture, a health status and a resolver status — and nothing about
what any publisher's terms of use say. So an unreviewed row is `UNKNOWN`, and
`live_network_guard_service` already puts `UNKNOWN` in `TERMS_BLOCKING`.

Deny by default is not a rule imposed on the registry here. It is what the
registry actually supports.

## The terms review queue

```text
  SAM-CREDENTIAL-ROLE          credential_and_role_required
  SPA-TERMS-GRANTS-GOV         terms_text_unretrievable
  SPA-TERMS-REGULATIONS-GOV    terms_text_unretrievable
  SPA-TERMS-REPORTER-NIH       terms_text_unretrievable
  SPA-TERMS-USASPENDING        terms_text_unretrievable
```

The four SPA items are worth reading carefully: those terms pages are
client-rendered and served **no policy text**. That is not "the terms allow
this" and not "the terms forbid this" — nobody could read them, which is
precisely why a human has to.

## What a completed review would change

The permitted branch is reachable and was exercised:

```text
a recorded terms review alone      -> registry_known, no approval
an activation approval alone       -> terms_blocked, still
both                               -> activation_approved, monitorable
a review that came back
  TERMS_REVIEW_REQUIRED + approval -> terms_blocked. An approval never
                                      clears a blocker.
```

## What activation would still require

```text
a terms review per source
  terms_review_incomplete x171
  human_review_only_sources x6

a scheduler that can run something:
  background_worker
  periodic_trigger
  persistent_backend
  production_raw_payload_store
  scheduler_runtime

and per source, at fetch time, everything live_network_guard_service already
requires: robots status, credential status, rate limit policy, the canonical
user agent, and verbatim attribution where the publisher requires it.
```

## What is NOT the blocker

```text
the registry            177 rows load and every one is classified
the allowlist           six states, each with a different owner and fix
the collector preflight seven declared policies, each checked
the choke point         1095 files scanned, 0 unapproved call sites
the watchlist           can name a registry source, since Gate 140
a network library       not needed to prove any of it, and not imported
```

## Nothing was called and nothing started

```text
live source calls                 0
robots.txt fetches                0
DNS resolutions                   0
collectors activated              0
sources cleared for collection    0
network calls by the evaluation   0
scheduler runtime mode            dry_run_in_process
runtime executes jobs             false
```

## Still false, and not touched

```text
source_monitoring_live         false
live_source_coverage           false
production_source_monitoring   false
email_delivery                 false
object_store_configured        false
document_body_storage_ready    false
customer_auth_live             false
verified_operational_binding   false
production_rollout             false
controlled_customer_pilot      false
```
