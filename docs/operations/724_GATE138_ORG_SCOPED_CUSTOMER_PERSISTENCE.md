# 724 — Gate 138: org-scoped customer persistence

## Did `customer_persistence_live` become true?

**Yes**, in controlled dev/demo, and it is proved rather than declared.

```text
customer_persistence_live   TRUE
scope                       controlled_dev_demo
customer_auth_live          false  (and not required)
production_persistence      false
```

Measured against the **live dev database** by
`scripts/verify_nativeforge_customer_persistence_live.sh`:

```text
RESULT=PASS
count=rows_written n=5
count=rows_archived n=5
count=rows_left_live n=0
count=cross_org_rows_read n=0
fact_status_written=demo_fixture
```

## The exact evidence

Four steps per lane, in that order, and a lane counts only if all four behave:

```text
write   a demo_fixture-labelled row through the lane's own repository
read    that row back BY ID, anchored on organization_id
refuse  the same read for a different organization
archive it, so the proof leaves nothing live
```

Five lanes, all four steps each:

```text
tenant_profile_persistence      write ✓ read ✓ cross-org refused ✓ cleanup ✓
awarded_grants_persistence      write ✓ read ✓ cross-org refused ✓ cleanup ✓
award_requirements_persistence  write ✓ read ✓ cross-org refused ✓ cleanup ✓
proof_audit_persistence         write ✓ read ✓ cross-org refused ✓ cleanup ✓
document_library_persistence    write ✓ read ✓ cross-org refused ✓ cleanup ✓
```

## Why this needs no `customer_auth_live`

`customer_persistence_capability_service` blocked every lane with

```text
no_customer_auth_so_nobody_owns_the_row
```

That blocker reaches for *somebody is accountable for this row*. The fact is
already true, measured from rows:

```text
org_binding_passed           TRUE   an identity resolves to an organization
                                    through a membership row
callback_session_validated   TRUE   a real session was validated
role_mapping_passed          TRUE   the role comes from nf_org_memberships
cookie_claim_can_override_membership   False
email_domain_can_map_a_role            False
```

And the repositories underneath already draw the line in the right place:

```python
# every one of the five, identically
demo_fixture = bool(is_demo) or fact_status == "demo_fixture"
production_write = not demo_fixture
if production_write and not customer_auth_live:
    refuse
```

`production_write`, specifically. The blanket `CAPABILITY_REQUIRES_AUTH = True`
did not make that distinction, so it reported every lane dead for a reason that
applies only to production writes.

`customer_auth_live` is false because `invite_binding_passed` is false — which
is about how a *second* member was authorized, and says nothing about whether
the first owns their own rows. Same shape Gate 134F found one layer up, and the
same remedy: ask for the fact directly, keep `customer_auth_live` a sufficient
condition rather than a necessary one.

## Which lanes are route-live

One.

```text
tenant_profile_persistence   api/tribal_profile_routes.py     ROUTE-LIVE
awarded_grants_persistence   —                                route missing
award_requirements_persistence —                              route missing
proof_audit_persistence      —                                route missing
document_library_persistence —                                route missing
```

Measured at the route:

```text
GET /v1/nf/demo/orgs/{demo}/tribal-profile          401
     … with a forged X-NF-Org-Id header             401
```

It fails closed, and the dev header cannot open it — Gates 134 and 135 removed
the chain that read it. The route also checks `_same_org(org_id, ctx)`, so the
path organization must match the session organization.

**Repository-live is not customer-usable.** Four lanes have no route and this
says so per lane rather than averaging it into one word. Nothing here fakes one.

## The accountable identity is derived, not supplied

Rows are attributed to the organization's active `org_owner` identity, read
from `nf_org_memberships`.

Found by the live database refusing the first run:
`created_by_identity_id` is a foreign key into `nf_identities`, and a synthetic
id has no row to point at. The throwaway SQLite database had no such target
table and accepted it — so the proof passed where it did not matter and failed
where it did.

The constraint was right and so is what it forces: the principal accountable
for the row is the identity the row should name.

## Cleanup is archival

No repository offers a delete, and none was added. These are audit surfaces
where a hard delete would be the wrong primitive to introduce for a smoke
test's convenience, so the proof leaves an archived row rather than no row.
That is the brief's "mark it as a test artifact" branch, chosen because it is
the only one the repositories offer.

Each lane archives its own row **and** the scaffolding it wrote — four of five
hang off an award they create themselves.

## What was not touched

```text
real organization aaaaaaaa-…      refused, by name and by classification
real customer data               none; every row is demo_fixture / is_demo
object store                     not contacted
document bodies                  none; the lane records a reference
live grant sources               not called
collectors                       not activated
email                            not sent
customer_auth_live               unchanged, still false
verified_operational_binding     unchanged, still false
```

## What production persistence still needs

```text
customer_auth_live true          Gate 136's second-person invite event
verified_operational_binding     Gate 137's two-part owner decision
object_store_configured          document bodies, untouched here
```
