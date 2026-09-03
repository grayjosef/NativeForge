# 734 — Gate 140: the matched-NOFO digest, operational

## What Gate 104 built and did not wire

Every component. None of them reachable.

```text
tenant_nofo_digest_snapshot_service            built
tenant_nofo_digest_change_detection_service    built
tenant_nofo_digest_item_explanation_service    built
tenant_pursuit_suppression_service             built
tenant_nofo_digest_builder_service             built
tenant_nofo_digest_demo_fixture_service        built

ready_for_demo_preview                         TRUE
preview_components_missing                     []
anything able to ask for a preview             NOTHING
```

`ready_for_demo_preview` had been true for thirty-six gates with nothing able to
request one. `tenant_digest_operational` was a literal `False` in six places and
no service derived it — the same family Gate 114A removed for
`customer_persistence_live` and Gate 139A for `awarded_operational_tracking`.

## The assembler

`tenant_nofo_digest_service.build_org_digest_preview` reads, all anchored on
`organization_id`:

```text
the tenant profile      -> the cadence the tenant chose
the source watchlist    -> what this tenant asked to watch
stored suppressions     -> what this tenant has already put in a pursuit
labelled fixture snapshots -> the candidates
```

and hands them to Gate 104's builder. It refuses a substitute anchor by name:

```text
not_an_anchor_for_a_digest:tenant_id
not_an_anchor_for_a_digest:customer_org_id
not_an_anchor_for_a_digest:organization_profile_id
```

## The routes

`src/nativeforge/api/tenant_digest_routes.py`, demo organizations only:

```text
GET    /v1/nf/demo/orgs/{org}/digest                  weekly by default
GET    /v1/nf/demo/orgs/{org}/digest?cadence=daily    if the profile enables it
GET    /v1/nf/demo/orgs/{org}/digest/readiness         what is and is not ready
POST   /v1/nf/demo/orgs/{org}/digest/cadence           enable or disable daily
POST   /v1/nf/demo/orgs/{org}/digest/suppress          hide one opportunity
POST   /v1/nf/demo/orgs/{org}/digest/lift              stop hiding it
```

## Weekly is the default and needs no setting

```text
GET /digest        cadence: weekly, default_cadence: weekly
                   daily_alerts_enabled: false
                   200, a digest
```

No configuration, no opt-in, no row anywhere saying "weekly". That is what
"default" means, and a test asserts it against an organization whose profile was
just created.

## Daily is optional and off

The setting lives in `nf_tenant_beta_profiles.digest_frequency`, which is a
stored column — so enabling it is a **profile write**, not a flag the digest
service keeps:

```text
GET /digest?cadence=daily          422
    daily_digest_requested_but_the_profile_has_not_enabled_it

POST /digest/cadence {"digest_frequency": "daily"}    200
GET /digest?cadence=daily                              200, cadence: daily

POST /digest/cadence {"digest_frequency": "weekly"}    200
GET /digest?cadence=daily                              422 again
```

Both directions are tested, because a permitted branch that nothing can reach
makes every refusal above it unfalsifiable — Gate 134F's lesson.

The cadence write is an upsert: it archives the previous profile and inserts,
and it carries every other fact forward. A cadence change is not a reason for a
tenant to lose its recognition status or its operating states, and a test reads
them back after the change to prove it did not.

## A preview is not a delivery

```text
delivery_status          preview_only, and no other value is permitted
email_delivery_live      false
emails_sent              0
source_monitoring_live   false
live_source_coverage     false
candidate_provenance     labelled_fixture_snapshots
```

There is no email service in this repository and none was written. A weekly
digest nobody receives is not a weekly digest — this gate makes the preview
**askable**, which is a smaller and true claim.

Change detection compares two recorded snapshots. It is not a comparison of two
live observations, and the digest says so in its caveats rather than in its
prose.

## Every item says what nobody knows

Fourteen declared fields, in the brief's order, asserted against a real item
rather than against a reader's memory:

```text
opportunity_id  source  title  jurisdiction  program_area
due_date  due_date_status  match_reason
eligibility_status  eligibility_evidence  blockers
recommended_action  pursuit_status  digest_visibility_status
```

The rules that make it honest:

```text
eligibility_status unknown        stays unknown; recommended_action becomes
                                  review_eligibility_with_a_human
a confident status with no
  match or exclusion evidence     fails an invariant
due_date_status                   the snapshot's provenance status, never a guess
due_date_verified without a date  fails an invariant
recommended_action                is never "apply". This service does not know
                                  whether a tenant should apply for anything.
```

The header counts both kinds of uncertainty — `items_with_unresolved_eligibility`
and `items_with_unverified_deadlines` — so a reader who skims the top of a digest
learns how much of it is unsettled.

## Caveats are not blockers

The first version of the assembler folded Gate 104's builder output into
`blocked_reasons`:

```text
items_with_unverified_deadlines:5
comparison_between_recorded_snapshots_not_live_checks
no_email_delivery_service_exists
```

Every one of those is a true statement **about** a digest and none of them stops
a preview. A working digest reported itself blocked. That is the same wrong-list
mistake Gate 138F made putting a production-write blocker into a customer-auth
list, and it would have made "blocked" mean nothing here too.

`caveats` is now its own list. `blocked_reasons` means the digest was not
produced, and the routes 422 on it.

A second, smaller version of the same error: an invariant demanded a caveat
whenever unverified deadlines were counted, and fired on a **daily digest that
was correctly refused** before the builder ever ran. It is now gated on `not
blocked_reasons` — a refused digest has no content to caveat, and demanding one
made every correct refusal look like a bug.
