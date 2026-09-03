# Gate 140 — what the tenant digest still does not reach

## What is operational

```text
tenant_digest_operational   TRUE
scope                       controlled_dev_demo
```

Add a source to the watchlist, read it back anchored on `organization_id`, ask
for the weekly digest with no setting at all, ask for the daily one and be
refused until the profile enables it, suppress an opportunity with an audit row
behind it, watch the item move rather than vanish, lift it, archive a watchlist
entry and find the row still there.

`customer_auth_live` is **false** and was not required: every row this gate
writes is fixture-labelled, and `production_write = not demo_fixture`.

## What every route refuses

```text
unauthenticated                          401, all nine routes
a forged X-NF-Org-Id                     401 - not a parameter on any route
a caller setting is_demo or fact_status  400, named
a registry source id nobody issued       400, source_id_is_not_in_the_source_registry
a fixture id without the fixture prefix  400, named
an unrecognised cadence                  422, cadence_not_recognised
a daily digest with no opt-in            422, the_profile_has_not_enabled_it
a suppression with no audit event        contract:no_audit_event_recorded
a cross-organization read                403/404 - which does not confirm the row exists
```

## Watching is not monitoring

A watchlist entry is a statement of interest. It is not coverage:

```text
source_monitoring_live               false, every response, every entry
last_checked_at                      null, every entry
live_grant_sources_called            false
network_calls_to_grant_sources       0
collectors_activated                 0
```

The digest's candidates are **labelled fixture snapshots**. Change detection
compares two recorded snapshots, not two live observations.

## A digest that is previewed is not a digest that is delivered

```text
delivery_status          preview_only, and no other value is permitted
email_delivery_live      false
emails_sent              0
```

There is no email service in this repository. A weekly digest nobody receives
is not a weekly digest, and this gate does not pretend otherwise — it makes the
preview askable, which is a different and smaller claim.

## What production tenant digest still needs

```text
a collector, activated under the existing gates    live candidates instead of fixtures
an email delivery service                          nothing to send a digest with
digest persistence                                 no digest table exists; a digest
                                                   that cannot be re-read cannot be
                                                   audited after a missed deadline
customer_auth_live true                            Gate 136's second-person invite event
verified_operational_binding                       Gate 137's two-part owner decision
the pursuit vocabulary settled                     three vocabularies disagree -
                                                   PursuitWorkflowStatus,
                                                   pursuit_workspace_contract, and
                                                   doc 570's seven stages
```

## What is NOT the blocker

```text
the tables            both round-trip, org-anchored, RLS-policied
the routes            all nine operational, proved by calling them
cross-tenant reads    refused on every one
source monitoring     not required for a fixture preview, and not claimed
email                 not required for preview readiness, and not claimed
customer_auth_live    gates PRODUCTION writes, not fixture-labelled ones
```

## What the digest says about what it does not know

Nothing is rounded up. Of the items in the weekly preview:

```text
items visible                        9
items total                          9
```

An item whose eligibility nobody has established keeps `unknown`, and its
`recommended_action` is `review_eligibility_with_a_human`. An item whose
deadline nobody has verified reports `due_date_status` saying so. No
`recommended_action` this service can emit is "apply".

## Rows left behind

```text
watchlist entries, live              0
watchlist entries, total             2
suppressions, live                   0
suppressions, total                  1
rows for another organization        0
rows for the real organization       0
rows that are not fixture-labelled   0
```

Archiving and lifting keep their rows, which is why "live" is lower than
"total" and why nothing was deleted.

## Still false, and not touched

```text
production_tenant_digest       false
source_monitoring_live         false
email_delivery                 false
live_source_coverage           false
customer_auth_live             false
verified_operational_binding   false
object_store_configured        false
production_rollout             false
controlled_customer_pilot      false
```
