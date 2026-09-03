# Gate 139 — what post-award tracking still does not reach

## What is operational

```text
awarded_operational_tracking   TRUE
scope                          controlled_dev_demo
```

Four lanes, route-live and repository-live, proved by calling the routes:

```text
  award_requirements
  awarded_grants
  document_metadata
  proof_audit
```

Create an award, attach a requirement, attach a proof event, attach a document
reference, read each back anchored on `organization_id`, read each as another
organization and get nothing, archive all four.

`customer_auth_live` is **false** and was not required — every row is
fixture-labelled, and `production_write = not demo_fixture` in every post-award
repository.

## What every lane refuses

```text
unauthenticated                          401, all four lanes
a forged X-NF-Org-Id                     401 - not a parameter on any route
a caller setting is_demo or fact_status  400, named
a document body                          422, document_body_storage_is_not_configured
a cross-organization read                404 - which does not confirm the row exists
a requirement on another org's award     404
a due date with no due_date_status       422, from the route's own validator
```

## What production tracking still needs

```text
customer_auth_live true          Gate 136's second-person invite event
verified_operational_binding     Gate 137's two-part owner decision
object_store_configured          document BODIES. Metadata does not need it
                                 and does not ask for it.
```

## There is no update, anywhere

Not an omission — the audit model:

```text
awarded grants        a correction is a new row; the mistaken one is archived
award requirements    a recurring obligation is many rows, one per period
proof events          what was believed at the time is what the row says,
                      forever. A correction is a SUPERSEDE that names the
                      event it replaces.
documents             archive, unless a legal hold refuses it
```

So no route here offers a PATCH, and none was added. A product surface that
wants "change this status" gets archive-plus-create, which is two calls a
caller can see.

## What is NOT the blocker

```text
the repositories       all four round-trip, proved in Gate 138
the routes             all four operational, proved here
cross-tenant reads     refused, every lane
the object store       not needed for metadata, and not contacted
customer_auth_live     gates PRODUCTION writes, not fixture-labelled ones
```

## Still false, and not touched

```text
production_awarded_tracking    false
customer_auth_live             false
verified_operational_binding   false
object_store_configured        false
document_body_storage_ready    false
tenant_digest_operational      false
source_monitoring_live         false
email_delivery                 false
production_rollout             false
controlled_customer_pilot      false
```

Rows left live after the smoke: 0. Everything created
was archived.
