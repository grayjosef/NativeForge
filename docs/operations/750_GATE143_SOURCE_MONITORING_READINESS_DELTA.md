# 750 — Gate 143: the source monitoring readiness delta

## What changed

```text
                                    before Gate 143   after Gate 143
source_monitoring_preflight_ready   did not exist     true, controlled_dev_demo
source_monitoring_live              false             false
approved-source allowlist           did not exist     six states, 177 rows
collector configuration preflight   did not exist     seven declared policies
source monitoring readiness         did not exist     derived, with named blockers
no-live-call verifier               did not exist     1088 files, 0 offenders
readiness routes                    none              3
```

`source_monitoring_live` is unchanged and still false. What is new is that the
system can now say **exactly what blocks live monitoring**, per source and per
component, with an owner attached to each.

## Did `source_monitoring_preflight_ready` become true?

Yes, for `controlled_dev_demo`. It required:

```text
the registry loads                    177 rows
every row is classified               177 of 177
the collector preflight works         seven policies, five states
the choke point scan is clean         1088 files, 0 unapproved call sites
the watchlist can name a source       Gate 140's registry check
tenant_digest_operational             true
no live call was made                 0
```

## Does `source_monitoring_live` remain false?

Yes, and this gate does not answer that question at all. It reads it from
`source_scheduler_readiness_service`, which derives it from four conjuncts and
reports false because five components are absent:

```text
runtime_mode              dry_run_in_process, which is not a live mode
background_worker         absent
periodic_trigger          absent
persistent_backend        absent
production_raw_payload_store  absent
scheduler_runtime         absent
```

An invariant fails if a passing preflight ever sets it.

## Were any live sources called?

**No.**

```text
live source calls                 0
robots.txt fetches                0
DNS resolutions                   0
network calls by the evaluation   0
network calls by either verifier  0
```

And it is a property of the code rather than a claim about one run: three
monitoring modules are parsed with `ast` and assert they import no network
client, and Gate 94's choke point scan reads all 1088 service files and finds
zero unapproved call sites.

## Was any collector activated?

**No.** `collectors_activated: 0`, `runtime_executes_jobs: false`, and zero of
the 177 registry sources is cleared for collection.

## Which source classes are blocked

```text
terms_blocked           171   the registry has no terms column, so UNKNOWN,
                              and UNKNOWN is blocking
human_review_blocked      6   grants.gov family. The terms page is
                              client-rendered and served no policy text.
api_key_missing           0   SAM.gov shape — the shipped registry has no such
                              row, and the rule is proved against a probe
activation_approved       0
```

The five terms review queue items are untouched: `approved_count: 0`,
`sources_activated: 0`, all five `automation_blocked`.

## Which classes can pass hermetic preflight

```text
a fixture source          fixture_allowed — and never monitorable
a reviewed + approved row  activation_approved, reachable in a test
a dry-run collector        configured_dry_run_only, no blockers
a fully-configured
  live collector           activation_approved, reachable in a test and
                           unreachable in runtime (no object store)
```

Every permitted branch is reachable. An unreachable permitted branch makes every
refusal above it unfalsifiable — Gate 134F's lesson, kept out of a fifth lane.

## What legal / source / API approvals are still required

```text
a terms review per source       171 unreviewed, 6 unreadable without a human
robots.txt, fetched politely     per source, at activation time. Never fetched
                                 here, so unknown, so blocking.
an activation approval per source a decision, not a global flag
SAM.gov: an API key AND a role   scraping is prohibited
Grants.gov attribution           verbatim, if a review returns
                                 ATTRIBUTION_REQUIRED
```

## Did email, object storage or customer auth change?

No.

```text
email_delivery_readiness   true    (Gate 142, unchanged)
email_delivery             false   (unchanged, asserted by a test)
object_store_configured    false   (Gate 141, unchanged)
customer_auth_live         false   (unchanged, asserted by a test)
```

## Did production status change?

No. `production_source_monitoring` is false in the readiness service, the
collector preflight, the allowlist, every route and every artifact, and no
branch anywhere in this gate sets it.

## Defects found and fixed

```text
An exact-match host list missed four grants.gov rows. The registry has 128
distinct hosts across 177 rows, and simpler.grants.gov, www.grants.gov and
grants.gov are one publisher. Now matched by domain with a label boundary, so
evilgrants.gov still does not match.

The import detector collapsed every import to its top-level package, so
`from urllib.parse import urlsplit` read as `urllib` and flagged this gate's
own allowlist. Gate 94's enforcement service already distinguishes
urllib.parse from urllib.request; the detector now asks it.

After the host fix, every one of the 177 rows was blocked, which made
`activation_approved` unreachable. `terms_statuses` is now injectable - the
shape the real process has, where a human reviews terms and records the result
- so the permitted branch is reachable in a test and empty in runtime.

A fixture source was not monitorable and had no blocker, which tripped
`not_monitorable_and_nothing_blocked_it`. It needed a reason, not an exemption.
```

## Next gate

Gate 144 — beta onboarding cockpit foundation. What remains after it, in the
order the blockers unblock:

```text
customer_auth_live             blocked on invite_binding_passed — a second real
                               person accepting a real invite (Gate 136)
verified_operational_binding   Gate 137's two-part owner decision
terms review                   171 sources unreviewed, 6 needing a human
source_monitoring_live         the terms reviews plus five scheduler components
digest persistence             no nf_tenant_digest_records; delivery intents are
                               now persisted and name a digest nobody kept
recipient consent              named in Gate 142, not modelled anywhere
email_delivery                 a provider, a service, and an explicit activation
object_store_configured        Gate 141's five settings and an owner decision
```
