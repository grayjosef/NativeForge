# 612 — Gate 112A: OIDC organization_id resolution survey

Written before any implementation. Every claim was reproduced by reading the
schema, the migrations and the services.

## Headline: no migration is needed, and the schema already models the path

The most useful finding, and it inverts the expected shape of this gate.

```text
nf_identities        UNIQUE (issuer, subject) -> id (UUID)
nf_org_memberships   identity_id      UUID FK nf_identities.id
                     organization_id  UUID FK organizations.id
                     state, membership_source, role, revoked_at, expires_at
                     under RLS: organization_id = current_setting(
                         'app.current_org_id', true)::uuid
```

That is exactly the claim → organization_id path:

```text
OIDC claim gives (issuer, subject)
  -> nf_identities unique(issuer, subject) -> identity_id
    -> nf_org_memberships (identity_id, organization_id) -> organization_id UUID
      -> the RLS authority Gate 110 proved
```

**The database already knows how to answer this question.** The gap is entirely
in the service layer, which never asks it.

## No service resolves a claim to organization_id

Searched across every `oidc_*`, `auth0_*` and `login_*` service:

```text
occurrences of organization_id   0
```

`oidc_identity_mapper_service.map_oidc_claims_to_auth_context` resolves an org
claim and hands it to `resolve_auth_context(organization_profile_id=org_id)`.
That terminates in the `String(128)` identifier Gate 110 established is not the
RLS authority — no foreign key, on a table with no RLS policy and a check
constraint forbidding production use.

## Current OIDC claim fields

```text
subject              required; missing_subject if absent
email                required; missing_email if absent
email_verified       email_not_verified if false
organization_claim   the org assertion from the token
allowed_org_binding  an expected value to compare against
invite_id            invite_not_bound if absent
roles_or_groups      mapped to one of grant_manager / tribal_admin /
                     operator_reviewer / viewer
provider_validated   defaults False
session_status       defaults no_session
```

An `org_mismatch` reason fires when `organization_claim` and
`allowed_org_binding` disagree — so a comparison exists, but between two claim
strings, never against an `organization_id`.

## Auth0 services carry no claim mapping

The `auth0_*` family is preflight, mode detection, live validation, live-unlock
and ingest. `auth0_preflight` reports `provider_configured: False` and
`client_secret_present: False`. None of them maps a claim to an organization.

## A concrete defect in membership lookup

`postgres_membership_directory_service.lookup_membership`:

```python
def lookup_membership(self, *, identity_id, organization_profile_id):
    ...
    f"WHERE identity_id = :identity_id AND organization_id = :org",
    {"identity_id": identity_id, "org": str(organization_profile_id)},
```

The parameter is **named** `organization_profile_id` and is bound to the
**`organization_id` column** — a `Uuid(as_uuid=True)` foreign key to
`organizations.id`.

Two identity spaces, one variable. A caller passing a real profile id string
would either fail the UUID cast in Postgres or match nothing; a caller passing an
`organization_id` would work, while the parameter name says they should not.

It is dormant — `self.configured` requires Postgres, and customer persistence is
false — but it is the same conflation Gates 109 through 111 exist to prevent,
sitting inside the membership lookup that any resolution path must use. Recorded
here, guarded by this gate's contract, and named as follow-up work rather than
fixed in passing: changing that signature touches the in-memory directory too and
belongs with the work that makes membership live.

The in-memory `membership_directory_service` is consistently
`organization_profile_id`-keyed throughout, which is at least coherent.

## Nothing consumes mapped claims

```text
routes consuming mapped claims       none
services setting app.current_org_id  one - api/deps_db.py, from the
                                     unauthenticated X-NF-Org-Id dev header
```

Unchanged from Gate 111. The mapper produces an auth context that nothing reads.

## Claim mapping is fixture-only

`provider_validated` defaults False, `login_live_claimed` is hard-coded False in
the mapper with a comment naming Gate 17, and
`login_live_promotion_gate_service` still reports seven of ten gates missing. The
mapper is production-*capable* in shape and fixture-only in fact.

## Exact current blockers

```text
1. no service resolves an organization claim to organization_id
   the claim path ends at organization_profile_id, which is not the authority

2. membership verification is keyed on organization_profile_id
   and the Postgres lookup binds that parameter to the organization_id column

3. no provider is attached
   provider_configured False, secret_present False - owner action, out of band

4. nothing consumes a resolved identity
   the one path that sets app.current_org_id reads an unauthenticated header
```

Blockers 1 and 2 are code. Blocker 3 is not. Blocker 4 is Gate 111's dev-header
containment question, carried forward.

## What this gate builds

A resolution contract that takes the claim material and says, explicitly, which
of the nine outcomes it reached — and refuses RLS for eight of them. A membership
verification contract keyed on `organization_id`. A containment record for the
dev header. No migration, because none is needed.

## What this gate does not attempt

```text
rewriting the OIDC mapper          it is Gate 17's, fixture-only, and rewriting
                                   it without a provider attached would be
                                   changing untested-by-reality code
fixing lookup_membership           named above; belongs with making membership
                                   live, and touches the in-memory directory too
attaching a provider               owner sets OIDC_* out of band
removing the dev header            would break sixteen route modules with no
                                   auth to replace it
```
