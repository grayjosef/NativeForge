# 728 — Gate 139: awarded grants behind authenticated routes

## What existed, and what did not

```text
awarded_grants_persistence   repository-live since Gate 138   route-missing
```

Four route modules were named in the brief and none of them existed. Gate 138
reported that per lane rather than averaging it, and said the honest thing:
repository-live is not customer-usable. This is the part that makes it usable.

## The routes

```text
POST   /v1/nf/demo/orgs/{org}/awarded-grants                     create
GET    /v1/nf/demo/orgs/{org}/awarded-grants                     list
GET    /v1/nf/demo/orgs/{org}/awarded-grants/{award_id}          read one
POST   /v1/nf/demo/orgs/{org}/awarded-grants/{award_id}/archive  archive
```

Demo organizations only. There is deliberately **no real-organization
counterpart**: building one would create a route to
`aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee` that nobody has authorized, and Gate
137's activation boundary exists precisely because that authorization does not.
A test asserts no route module mentions `require_real_org_session` or
`/v1/nf/real/orgs`.

## Two layers, two questions

```text
require_demo_org_session   which organization IS the caller
                             nf_session -> nf_org_memberships ->
                             organizations.org_type -> OrgContext
guard_same_org_404         does the URL agree
```

Measured, over real HTTP against the running server:

```text
GET  .../awarded-grants                              401  unauthenticated
     … with a forged X-NF-Org-Id                     401
     … with a forged nf_session cookie               401
     … a session for B asking about A's URL          404
```

404, not 403, for the cross-organization case — which does not confirm that the
other organization exists.

## There is no PATCH, and that is the audit model

`awarded_grants_repository_service` has no update path and says why:

> "There is no upsert. An award is a discrete event: a correction is a new row
> and the mistaken one is archived with `mistaken_award`, so the audit trail
> shows what was believed and when."

So a correction is archive-then-create, two calls a caller can see. A PATCH
would have had to invent an UPDATE the table was built to refuse. A test
asserts no route module contains `@router.patch` or `@router.put`, in any lane.

The archive response says so in the payload rather than leaving it to be
discovered:

```json
"update_path_available": false,
"update_path_available_because":
  "an award is a discrete event; a correction is a new row and the mistaken
   one is archived"
```

## The label is not the caller's

Every row these routes write carries `is_demo: true` and
`fact_status: demo_fixture`, forced. A caller supplying either — or
`organization_id`, `tenant_id`, `customer_org_id`, `organization_profile_id`,
`customer_auth_live`, `verified_operational_binding`, `object_store_configured`
— gets **400 with the field named**.

That refusal did not work in the first version. Pydantic drops an unknown field
**silently**, so `is_demo: false` never reached `refuse_caller_supplied` and was
ignored rather than refused — and ignored is how a caller comes to believe a
production write happened. This gate's own smoke invariant caught it
(`caller_relabel_refused: False`).

The bodies allow extras now so the refusal can see them, and a separate
`declared_fields` keeps strays out of the repositories — every one takes its
fields as keyword arguments and an unknown one is a `TypeError`.

## Why this needs no `customer_auth_live`

`production_write = not demo_fixture` in every post-award repository. A
fixture-labelled write is not a production write and needs neither
`customer_auth_live` nor a verified operational binding. That line was already
drawn; Gate 138 found it and this gate relies on it rather than restating it.

## The identity a row is attributed to

`OrgContext` carries `org_id` and `org_type` and no principal — it answers which
organization, not which person. So `created_by_identity_id` comes from
`nf_org_memberships` through Gate 138's resolver, which is also what the
database requires: the column is a foreign key into `nf_identities`, and Gate
138 found that out by having a synthetic id refused.

A route for an organization with no active membership gets 403 with
`no_active_membership_identity_to_attribute_the_row_to`, rather than an
`IntegrityError`.
