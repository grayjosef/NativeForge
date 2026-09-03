# 732 — Gate 140: tenant digest and watchlist survey

Measured before anything was implemented. HEAD `27aaa63`.

## Why `tenant_digest_operational` is currently false

Same shape as Gate 139's `awarded_operational_tracking`: it is a **constant** in
six places and no service derives it.

```text
dev_header_kill_artifact_service.py:311        "tenant_digest_operational": False
login_live_dev_header_kill_artifact_service    False
first_dev_org_binding_artifact_service.py:327  False
plus three artifact prose lines
```

There *is* a `tenant_nofo_digest_readiness_service`, and it answers a different
question — `ready_for_operational_digest` — which nothing named
`tenant_digest_operational` reads.

## Gate 104 built more than the brief expects

Every digest component already exists and is contract-complete:

```text
tenant_nofo_digest_builder_service            weekly default, daily opt-in
tenant_nofo_digest_item_explanation_service   why each item matched
tenant_nofo_digest_change_detection_service   what changed since last time
tenant_nofo_digest_snapshot_service           the comparison basis
tenant_pursuit_suppression_service            suppression, already org-scoped
tenant_nofo_digest_demo_fixture_service       labelled fixture snapshots
tenant_nofo_digest_readiness_service          the component check
```

Measured right now:

```text
ready_for_demo_preview            TRUE
preview_components_missing        []
weekly_digest_preview_available   TRUE
daily_alerts_preview_available    TRUE
suppression_contract_available    TRUE
explanation_service_available     TRUE
change_detection_available        TRUE
snapshot_contract_available       TRUE

ready_for_operational_digest      FALSE
```

**Every preview component is present and none of them has a route.** That is
the gap, and it is exactly the gap Gate 139 closed for the post-award lanes:
repository-live — or here, service-live — is not customer-usable.

## What `ready_for_operational_digest` waits on

```python
operational_facts = {
    "verified_operational_identity_binding": ...,   # false, Gate 137
    "email_delivery_available": ...,                # false, no email service
    "live_source_collection_available": ...,        # false, no collectors
    "customer_persistence_live": ...,               # false — see below
}
ready_for_operational_digest = not preview_missing and not operational_missing
```

Three of those four are correct and must stay false: this gate sends no email,
calls no live source, and does not touch the real organization.

The fourth is a wiring detail worth naming. `customer_persistence_live` here
reads `_capability_persistence_live("tenant_digest_persistence")`, and that lane
has **no table** — so it is false for a reason unrelated to Gate 138's proof.

So `ready_for_operational_digest` is the **production** question, and it stays
false. `tenant_digest_operational` for controlled dev/demo is a different one,
and this gate derives it separately rather than loosening that conjunct — the
same separation Gate 138 made for persistence and Gate 139 for awarded tracking.

## Whether source watchlist persistence exists

**No.**

```text
tenant_source_watchlist_service        ABSENT
nf_source_watchlist_entries            NO TABLE
capability lane                        source_watchlist_persistence
  schema_available                     False
  repository_available                 False
  service_contract_available           False
```

Gate 138's matrix already reported this lane absent on all three counts, and it
stayed false honestly. It needs a migration and a repository, and that is the
main build of this gate.

## Whether digest candidate persistence exists

**No table**, and it turns out not to need one.

`nf_tenant_digest_records` does not exist. But the digest is a **preview**
assembled from snapshots at request time — `build_tenant_digest` takes items and
returns a digest; it stores nothing and `delivery_status` may only be
`preview_only` or `not_configured`, under an invariant.

So a persisted digest record would be storing a view, and the thing that must
persist across requests is the **suppression state** — which is what makes an
item disappear from next week's list. That is the honest scope: persist
suppression, compute the digest.

## Whether a digest preview route exists

No. No route module mentions digest or watchlist, and the OpenAPI spec has no
path for either.

## Whether a weekly default and a daily option exist

Yes, both, in the builder:

```text
CADENCES         weekly | daily | manual_preview | unknown
DEFAULT_CADENCE  weekly
```

> "A daily digest built for a tenant whose profile does not enable daily alerts
> is refused with a reason rather than silently produced."

The tenant profile carries `digest_frequency` with vocabulary
`daily | weekly | none` — so the setting has somewhere to live already, in
`nf_tenant_beta_profiles`, which Gate 138 proved round-trips.

## Whether pursuit suppression exists

Yes. `tenant_pursuit_suppression_service` has statuses, reasons, an id builder,
`suppress_for_tenant`, `is_suppressed_for_tenant` and a summariser — and the
digest builder already consults it.

What it does not have is **persistence**. `suppress_for_tenant` returns a record;
nothing writes one. So suppression works within a single call and forgets
between them, which means "once pursuit starts, the item disappears from future
digests" is not currently true across requests.

That is the second build of this gate.

## Whether the tenant profile can drive matching

Yes. `nf_tenant_beta_profiles` carries `priority_topics`, `excluded_topics`,
`operating_states`, `applicant_classes`, `source_watchlist_preferences` and
`digest_frequency` — and Gate 138 proved the lane round-trips through
`tenant_profile_repository_service`.

## Whether source monitoring is required for a controlled fixture digest

**No**, and requiring it would make the lane permanently unreachable.

```text
live_source_collection_available   False   no collectors, by design
source_monitoring_live             False
```

A fixture digest is built from labelled fixture snapshots —
`demo_scope: digest_preview_from_labelled_fixture_snapshots` is already the
readiness service's own words. Requiring live monitoring for a preview built
from fixtures is the unsatisfiable-conjunct shape Gate 134F removed.

Both stay false and are reported separately, as `object_store_configured` was in
Gate 139.

## Whether email delivery is required for preview readiness

No, for the same reason, and the builder is already explicit:

> "There is no email service in this repository — Gate 103 found zero, Gate 104A
> confirmed it. `delivery_status` may only be `preview_only` or
> `not_configured` here, and an invariant fails `queued`, `sent` or anything
> else. A digest that could report itself sent would be a digest somebody
> eventually believes was."

## What can safely become true in this gate

```text
migration 0040   nf_source_watchlist_entries
                 nf_tenant_pursuit_suppressions
tenant_source_watchlist_service        the repository the lane never had
suppression persistence                so suppression survives a request
tenant_nofo_digest_service             the org-scoped preview assembler
api/tenant_watchlist_routes.py         list / add / archive
api/tenant_digest_routes.py            weekly + daily preview, suppress,
                                       readiness
tenant_digest_operational_readiness_service   the measurement
tenant_digest_operational = TRUE, controlled_dev_demo
```

And what must not move:

```text
source_monitoring_live         false
email_delivery                 false
live source calls              none
object store                   not contacted
customer_auth_live             false, governed by its own gates
production tenant digest       false
```

## Exact blockers remaining after this gate

For **controlled dev/demo**: none, if the route smoke passes.

For **production** tenant digest, four, none of them this gate's:

```text
live_source_collection_available   collectors. Not this campaign yet.
source_monitoring_live             the same.
email_delivery_available           there is no email service at all.
verified_operational_identity_binding   Gate 137's two-part owner decision.
```

## Two claims this gate must not make

Recorded here because the brief names them and because they are the kind of
thing that gets written by accident:

```text
no "65% improvement" claim   nothing here measures an improvement against
                             anything, and no field will imply one
no live coverage claim       live_source_coverage stays false; the digest is
                             built from labelled fixture snapshots and every
                             response says so
```
