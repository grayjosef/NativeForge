# 699 — Gate 132: first dev org binding survey

Measured before anything was implemented.

## The brief's module names, mapped

Three of the modules named in the survey list do not exist:

```text
verified_org_binder_service          ABSENT
customer_session_cookie_service      ABSENT
customer_current_user_service        ABSENT
```

The real modules with those responsibilities:

```text
verified_binder_authorization_service          who may bind
verified_binding_workflow_service              the binding workflow
customer_session_cookie_policy_service         cookie flags
customer_session_format_service                session encode/sign
customer_session_verifier_service              session decode/verify
api/auth.py::current_user                      the route itself
```

Third gate running where a brief names modules nobody built. Recorded rather
than silently substituted, because Gates 124 and 126 each lost time to a probe
naming a module that did not exist, and a brief that does it is the same hazard
pointed at a person.

## Where the records live

```text
identities        nf_identities                    migration 0023
memberships       nf_org_memberships               migration 0024
bindings          nf_tenant_customer_org_bindings  migration 0029
```

All three exist in the runtime database at head 0036. All three hold **zero
rows**.

### nf_identities

```text
id, subject, issuer, email, email_verified, verification_source,
created_at, last_seen_at, disabled_at
```

`subject` is `VARCHAR(255)` and holds the provider subject **raw**, not hashed.
That is deliberate rather than an oversight: OIDC identity lookup is
`(issuer, subject)`, and a hash cannot be looked up against a claim without
hashing the claim the same way — which is fine, but the schema as built expects
the value. The brief asks for "hashed or safely represented"; the existing
schema's answer is "stored, scoped to a table with no RLS-crossing joins".
Changing it is a migration, not a Gate 132 decision.

### nf_org_memberships

```text
id, organization_id, identity_id, is_demo, state, membership_source,
role, role_source, invited_by, approved_by, created_at, revoked_at, expires_at
```

`is_demo` is NOT NULL and pairs with the RLS predicate every tenant table
carries: `organization_id = current_setting('app.current_org_id')::uuid AND
is_demo = current_setting('app.current_org_is_demo')::boolean`. A membership
therefore commits to demo-or-real at creation.

`role_source` and `membership_source` exist so a role can never be recorded
without saying where it came from.

### nf_tenant_customer_org_bindings

```text
id, organization_id, tenant_id, customer_org_id, binding_status,
binding_source, binding_confidence, verified_by_identity_id, verified_at,
revoked_at, revoked_by_identity_id, is_demo, human_review_required,
blocked_reasons, created_at, updated_at
```

`organization_id` is the anchor. `tenant_id` and `customer_org_id` are NOT NULL
text and are **never authority** — Gate 109's rule, and the repository refuses
them as such.

## Does a dev organization already exist?

Yes. Two, and choosing between them is a real decision.

```text
aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee   org_type = real   seat_cap 5
bbbbbbbb-cccc-dddd-eeee-ffffffffffff   org_type = demo   seat_cap 5
```

Both carry `display_name: NULL` and `created_at: 1970-01-01`, which is what a
seeded fixture row looks like rather than an organization anybody set up.

`NF_DEMO_ORG_IDS` is **unset**, so `demo_org_uuid_set()` is empty. Nothing
currently treats either id as a demo org at the settings layer, even though one
is typed `demo` in its own column.

That matters: `is_demo` on a membership is a column the caller sets, not
something derived from `organizations.org_type`. Two sources for one fact, and
they do not currently agree with each other because one of them is empty.

## Has the authenticated Google identity been observed?

Yes, once, in Gate 131's browser smoke — verified by JWKS, email domain
`gmail.com`. It was **not persisted**: the callback holds the verification
result in a local and writes nothing.

So the subject exists in Google's records and in one Gate 131 log line, and
nowhere in NativeForge.

## What exists, and what does not

```text
identity persistence      DOES NOT EXIST. No INSERT into nf_identities
                          anywhere in src/.
membership creation       DOES NOT EXIST. No INSERT into nf_org_memberships
                          anywhere in src/.
binding creation          EXISTS. tenant_customer_org_binding_repository_service
                          .insert_binding(), real sa.insert, gated by
                          prepare_insert() so the decision and the write cannot
                          disagree.
membership READ           EXISTS. postgres_membership_directory_service
                          .resolve_persisted_membership().
org resolution            EXISTS. oidc_organization_id_resolution_service,
                          never run against a real identity.
current-user reads
  the binding             NO. The route passes `membership_verified=False`
                          deliberately: "a membership record is a database
                          question this route does not ask."
```

## Exact missing pieces

```text
1  a write path for nf_identities
2  a write path for nf_org_memberships
3  the callback resolving a verified claim to an organization_id
4  current_user asking the database whether a membership exists
5  the callback minting a session once 3 and 4 hold
```

Item 3's logic exists and has never been invoked. Items 1, 2, 4 and 5 are new
code. Item 1 and 2 are the ones that write rows tying a real person to an
organization.

## The decision this gate cannot make for itself

Which organization, and whether demo or real.

```text
demo org   bbbbbbbb-...   consistent with "dev only", and is_demo=true
                          keeps the membership inside the demo RLS partition
real org   aaaaaaaa-...   org_type says real; binding a live Google identity
                          to it is closer to a production binding than this
                          gate is permitted to create
```

Binding to the `real` row would create the first live identity-to-organization
association in NativeForge under an org typed `real`. The hard rules forbid a
production binding, and `org_type='real'` is the closest thing this database has
to that label.

The demo org is the defensible choice, and it is still Mayhem's to authorize
rather than mine to infer.

## What will not be claimed

`customer_auth_live` requires more than a binding: `role_mapping_passed`,
`dev_header_disabled_for_production` and owner approval are separate gates and
none of them moves here. `login_live` becomes measurable only if a session mints
and `/api/auth/current-user` recognises it.
