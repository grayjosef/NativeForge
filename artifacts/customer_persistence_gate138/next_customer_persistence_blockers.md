# Gate 138 — what customer persistence still does not reach

## What is live

```text
customer_persistence_live   TRUE
scope                       controlled_dev_demo
```

Proved, not asserted: a `demo_fixture`-labelled row into each of five
lanes, read back **by id** anchored on `organization_id`, a cross-organization
read returning nothing, and an archive leaving nothing live.

```text
rows written   5
rows archived  5
rows left live 0
cross-org rows 0
```

`customer_auth_live` is **false** and was not required. A fixture-labelled write
is not a production write, which is the line the repositories already drew.

## Repository-live but route-missing

```text
  award_requirements_persistence
  awarded_grants_persistence
  document_library_persistence
  proof_audit_persistence
```

Repository-live is not customer-usable. Nothing here fakes a route, and the
lane matrix reports the two separately rather than averaging them.

One lane has routes and they fail closed: `/v1/nf/demo/orgs/…/tribal-profile`
returns 401 unauthenticated and 401 with a forged `X-NF-Org-Id`.

## What production persistence still needs

Three, none of them this gate's:

```text
customer_auth_live true          Gate 136's second-person invite event.
                                 docs/operations/717 has the four steps.
verified_operational_binding     Gate 137's two-part owner decision:
                                 an id added to
                                 AUTHORIZED_REAL_ORGANIZATION_IDS *and* an
                                 approval object naming it.
object_store_configured          document bodies. Not touched here - the
                                 document lane records a reference and no
                                 store is contacted.
```

## What is NOT the blocker

```text
invite_binding_passed        gates customer_auth_live, which gates
                             PRODUCTION writes. A demo organization's owner
                             writing a fixture row into their own
                             organization needs an accountable principal,
                             not a second member.
verified_operational_binding Gate 113 refuses one on a demo organization at
                             all, so requiring it for demo persistence would
                             make demo persistence permanently unreachable.
the write path               exists in all five lanes and round-trips.
cross-tenant reads           refused; every read is anchored on
                             organization_id and a label never selects.
```

## Still false, and not touched

```text
production_persistence_ready   false
awarded_operational_tracking   false   Gate 139's facts do not exist yet
object_store_configured        false
tenant_digest_operational      false
source_monitoring_live         false
email_delivery                 false
customer_auth_live             false
verified_operational_binding   false
production_rollout             false
controlled_customer_pilot      false
```

Three lanes have no table at all and stay false honestly:
`tenant_digest_persistence`, `source_watchlist_persistence`,
`beta_onboarding_persistence`.
