# 709 — Gate 134: how organization context is derived now

```text
before   X-NF-Org-Id  ->  organizations.org_type          ->  OrgContext
after    nf_session   ->  nf_org_memberships              ->
                          organizations.org_type          ->  OrgContext
```

One module: `src/nativeforge/api/customer_org_context_dependency.py`.

## Why one module and not 207 conversions

There are 207 routes and every one already depended on one of two names. Two
hundred and seven hand-written org resolutions is 207 chances to get the
cross-tenant check subtly different. The replacement provides two names with the
same shapes, so a conversion is an import swap and the resolution lives in one
place where it can be read.

## The chain

```text
1  nf_session cookie, HMAC-verified by customer_session_verifier_service
2  the principal it carries -> resolve_session_organization (Gate 132)
   -> the identity's single ACTIVE, unrevoked, unexpired membership
3  the membership's organization must be the one the cookie claims
4  organizations.org_type -> classify_organization (Gate 132) -> demo or real
5  apply_org_rls_gucs(db, organization_id, org_type)
6  OrgContext
```

Every step can refuse, and each refusal is named.

## What it refuses, and with which code

```text
no session cookie                  401   nobody is asking
cookie present, invalid            401   forged, expired, or signed elsewhere
valid session, no membership       403   somebody is asking, for nothing
valid session, wrong organization  403   a member of B is not a member of A
demo-only route, real org          403   the existing require_*_org_db rule
real-only route, demo org          403   the same rule, other direction
X-NF-Org-Id                        ignored - it is not a parameter
```

401 versus 403 is Gate 117's distinction and it is worth keeping. 401 means
*authenticate*; 403 means *you did, and it is still no*. A membership that does
not exist is not an authentication problem.

## The header is not read, refused, or checked

There is no `X-NF-Org-Id` parameter on any function in that module. Refusing a
header requires reading it, and a dependency that reads it is one edit from
trusting it.

A test asserts this structurally rather than by outcome: it parses the module
and every converted route module with `ast` and checks that the header name
appears in no `Header(alias=...)` anywhere, and in the dependency only as the
constant that names what is refused. A route that happens to ignore the header
today is not the same as one that cannot read it.

## The cross-organization rule

Gate 132 found this defect and fixed it in `api/auth.py`; it is enforced here
too, because this is where 207 routes now get their organization:

```python
if resolution["organization_id"] != parsed["organization_id"]:
    # a cookie naming A held by a member of B is not a member of A
```

Accepting it because *some* membership exists is the cross-tenant read every RLS
rule in this codebase is written against.

## RLS context is applied here

`deps_db.get_org_context_with_db` called `apply_org_rls_gucs` and so does this.
Gate 122's replacement deliberately did not, and gave the reason: it was attached
to no route, and setting `app.current_org_id` on the strength of a decision
nobody had acted on would have been this campaign's own defect one layer lower.
Routes act on this one, and the organization it sets came from a membership row.

## The dev/test escape hatch

There is none in this module. `deps_customer_auth.get_dev_org_context_explicit_only`
still exists — refused in production, 503 when the setting is off — and **no
route depends on it**. It was Gate 122's honest naming of the header for what it
is, and it stays until Gate 135 removes the chains.

## What the tests use

`tests/session_org_helper.py`. It writes an `organizations` row, an
`nf_identities` row through the actual upsert path, and an `nf_org_memberships`
row, then mints a session through the real session service, which refuses one
that would not verify.

Nothing there is a stub. A test that passes has exercised verification,
resolution, classification and the RLS call — not a mock of them.

One thing it has to work around, recorded where it does it: Gate 132's bootstrap
refuses any organization whose `org_type` is not `demo`, so there is no write
path for a real-organization membership anywhere in `src/`. The helper inserts
that row directly and says why.
