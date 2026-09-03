# 736 — Gate 140: the tenant digest readiness delta

## What changed

```text
                                    before Gate 140   after Gate 140
tenant_digest_operational           false (constant)  true (derived)
scope                               none              controlled_dev_demo
nf_source_watchlist_entries         no table          exists, RLS-policied
nf_tenant_pursuit_suppressions      no table          exists, RLS-policied
tenant_source_watchlist_service     absent            exists
suppression persistence             absent            exists
digest routes                       none              6
watchlist routes                    none              4
source_watchlist_persistence lane   0 of 9            complete write path
controlled_dev_persistence_count    6                 7
alembic head                        0039              0040
```

Unchanged, and deliberately:

```text
login_live                     true
customer_persistence_live      true
awarded_operational_tracking   true
customer_auth_live             false
verified_operational_binding   false
source_monitoring_live         false
email_delivery                 false
production_tenant_digest       false
production_rollout             false
controlled_customer_pilot      false
```

## How `tenant_digest_operational` is derived

`tenant_digest_operational_readiness_service.build_tenant_digest_readiness`.
Every conjunct is measured by something, and each is reported separately rather
than averaged:

```text
both route modules exist, are session-wired, read no dev header
a tenant profile exists for this organization
Gate 104's preview components import
the route smoke proved:
    the watchlist route works
    the digest preview route works
    weekly is the default with no setting
    the daily setting works, and is refused without it
    suppression works, with a real audit row
    unauthenticated is refused on all nine routes
    a cross-organization read is refused
customer_persistence_live is true
```

Any one of those false and it is false, with the reason named. `scope` is
`controlled_dev_demo` when true and `none` when false — there is no branch that
sets any other value.

## What is NOT required, and why saying so matters

```text
source_monitoring_required_for_preview   false
email_required_for_preview               false
```

Both are stated as fields rather than implied by their absence. Requiring live
source monitoring for a preview assembled from labelled fixture snapshots would
be an unsatisfiable conjunct — the lane would be permanently unreachable and
every "not ready" above it unfalsifiable. That is the defect Gate 134F removed
from the customer-auth chain, and this gate is not reintroducing it one lane
over.

`source_monitoring_live` and `email_delivery_available` are reported **beside**
those two fields and stay false. An invariant fails if either is ever true here.

The existing `tenant_nofo_digest_readiness_service.ready_for_operational_digest`
answers a different and stricter question — it additionally requires live source
collection, an email service and a verified operational binding. All three are
correctly false, and this gate did not touch it. Same separation Gate 138 made
for persistence and Gate 139 for awarded tracking.

## The verifier

```bash
bash scripts/verify_nativeforge_tenant_digest_operational.sh
```

`RESULT=PASS` only when `tenant_digest_operational=true`. It drives the routes
over real HTTP against the running server with a real signed session for the
demo organization's real owner identity, read out of `nf_org_memberships`.

Current result:

```text
RESULT=PASS
tenant_digest_operational=true
scope=controlled_dev_demo
source_watchlist=operational
digest_preview=operational
weekly_default=operational
daily_optional_setting=operational
pursuit_suppression=operational
customer_auth_live=False
source_monitoring_live=false
email_delivery=false
production_tenant_digest=false
```

The verifier seeds a fixture weekly profile before the smoke and archives it
afterwards, because Gate 138's persistence smoke archives everything it writes
and the demo organization therefore has no live profile between runs. It leaves
`0` live watchlist entries, `0` live suppressions, `0` rows for the real
organization and `0` rows that are not fixture-labelled — all counted and all
asserted.

One portability note: the count of rows belonging to the real organization reads
the anchors out and compares them as uuids in Python. Binding a `uuid` works on
PostgreSQL and binding `.hex` works on the sqlite the live stack runs, and
either one silently reads **zero** on the other dialect — a count that reports
"no rows for the real organization" without having looked is worse than no
count.

## What production tenant digest still needs

```text
a collector, activated under the existing gates
    live candidates instead of labelled fixture snapshots; change detection
    compares two recorded snapshots today, and a live comparison needs a second
    real observation

an email delivery service
    none exists. A weekly digest nobody receives is not a weekly digest.

digest persistence
    no nf_tenant_digest_records table. A digest that cannot be re-read cannot be
    audited after a missed deadline. This is why tenant_digest_persistence is
    still absent on the capability matrix while source_watchlist_persistence is
    now complete.

customer_auth_live true
    Gate 136's second-person invite event

verified_operational_binding
    Gate 137's two-part owner decision

the pursuit vocabulary settled
    three vocabularies disagree — PursuitWorkflowStatus,
    pursuit_workspace_contract, and doc 570's seven stages
```

## What is NOT the blocker

```text
the tables            both round-trip, org-anchored, RLS-policied
the routes            all nine operational, proved by calling them
cross-tenant reads    refused on every one
source monitoring     not required for a fixture preview, and not claimed
email                 not required for preview readiness, and not claimed
customer_auth_live    gates PRODUCTION writes; every row here is
                      fixture-labelled, and production_write = not demo_fixture
```

## What this gate does not claim

```text
live source monitoring       no
live source coverage         no
email delivery               no
production readiness         no
a controlled customer pilot  no
any 65% improvement          no
anything about the real org   aaaaaaaa-… is named once, in the survey, as the
                              organization no route reaches
```

`UNKNOWN` and `NEEDS HUMAN REVIEW` survive the whole path: an item whose
eligibility nobody established keeps `unknown` and recommends a human, and an
unverified deadline is reported as unverified and never inferred.
