# 607 — Gate 111A: customer auth boundary survey

Written before any implementation. Every claim was reproduced by running the
tree, not by reading intentions.

## Customer auth is not live, and an existing gate says so

`login_live_promotion_gate_service` already answers this question. Run today:

```text
login_live_claimed          False
production_auth_claimed     False
controlled_pilot_auth_ready False
all_required_gates_passed   False
missing_gates               provider_configured, secret_present,
                            issuer_jwks_validated, callback_session_validated,
                            invite_binding_passed, org_binding_passed,
                            role_mapping_passed
next_safe_action            Owner sets OIDC_* env vars out-of-band, re-runs
                            preflight + live validation, re-evaluates
```

Seven of ten promotion gates are missing. Three pass — `audit_event_emitted`,
`rbac_handoff_passed`, `tenant_boundary_passed` — which is exactly the shape of a
system with the internal plumbing built and no provider attached.

**Customer auth is false. This is measured, not assumed.**

## The auth surface is large and almost entirely contract-only

Roughly forty services touch auth: the `auth0_*` family (validation, preflight,
mode detection, live unlock), `oidc_*` (token verification, identity mapping,
config schema, readiness), `rbac_*` (policy contract, enforcement, privilege
matrix), `membership_*`, `login_claim_resolver`, `login_live_promotion_gate`,
`session_tenant_enforcement`, `request_identity`.

None of it is wired to a live provider. `auth0_preflight` reports
`provider_configured: False` and `client_secret_present: False`.

## No route is customer-authenticated

The API resolves organization identity from an **unauthenticated request
header**:

```python
# api/isolation_deps.py and api/deps_db.py
async def get_org_context_with_db(
    x_nf_org_id: str | None = Header(default=None, alias="X-NF-Org-Id"),
) -> OrgContext:
    ...
    oid = uuid.UUID(str(x_nf_org_id).strip())
    ...
    apply_org_rls_gucs(db, oid, ot)
```

Sixteen route modules depend on it. There is no token, no session, and no claim
verification anywhere in the path.

### The one place app.current_org_id is set

`deps_db.get_org_context_with_db` is the **only** code path that calls
`apply_org_rls_gucs`, and it sets the RLS context from that header after looking
the organization up.

`NF_DEV_ORG_HEADERS` gates it and **defaults to `True`**:

```python
nf_dev_org_headers: bool = Field(default=True, validation_alias="NF_DEV_ORG_HEADERS")
```

### What actually contains it today

Recorded precisely, because "a header sets the RLS context" deserves an accurate
exposure statement rather than an alarming one:

```text
nativeforge-backend.service        inactive - the API is not running
backend bind                       127.0.0.1:8000, and a test parses the unit
                                   file to prove it
cloudflared tunnel ingress origin  http://127.0.0.1:5175 - the static preview,
                                   not the API
public edge                        Cloudflare Access, 302 to the Access login
```

So this is a **latent dev-only path, not a live exposure**: the API is not
running, binds loopback when it does, and is not in the tunnel's ingress. What
contains it is deployment posture rather than the flag, since the flag defaults
on.

That is precisely the hazard Gate 111D exists to guard. Today nothing verifies a
claim before it reaches the RLS context; the only reason that is safe is that
nothing reaches the API at all.

## No service maps claims to organization_id

The most consequential finding, and it echoes Gate 110 exactly.

`oidc_identity_mapper_service` resolves a subject and an org claim, then hands
off to `resolve_auth_context(organization_profile_id=org_id, ...)`.

**It targets `organization_profile_id`, not `organization_id`.**

Gate 110 established what that identifier is: a `String(128)` with no foreign
key, on `nf_evidence_intake_records`, a table with no RLS policy and a check
constraint permitting only `local_dev_only` / `not_claimed` /
`production_forbidden`.

So even if a provider were attached tomorrow, the claim path would terminate in
an identifier that **is not the RLS authority**, with nothing connecting it to
the `organization_id` UUID that every policy enforces on. This is the same gap
Gate 110 found in `make_tenant_id`, in a second place.

Closing it is not this gate's work — but no contract here may paper over it, and
`org_claim_verified` is a separate field from `claims_verified` for that reason.

## Cloudflare Access is a front door, not app auth

The public edge returns `302` to `josefgray.cloudflareaccess.com`. That controls
who reaches the host; it says nothing about which organization a request may act
for, and it sets no RLS context.

A Cloudflare-authenticated visitor is still `unauthenticated` as far as the
application is concerned, and the principal contract keeps them there.

## Three role vocabularies already exist

```text
rbac_policy_contract   authorized_signer, draft_contributor, grant_manager,
                       operator_admin, operator_reviewer, tribal_admin, viewer,
                       unknown
org_tenant_seat_model  org_owner, org_admin, authorized_representative,
                       grant_lead, reviewer, viewer
internal               operator_internal
```

The Gate 111 brief asks for a fourth: `platform_admin`, `tenant_admin`,
`grants_manager`, `grants_viewer`, `auditor`, `unknown`. None of those names
exists in the tree today.

This is the same pattern as the identity names, and gets the same treatment: the
new vocabulary is defined for this contract and **mapped onto the existing two**,
with a completeness check that fails if either grows a role the mapping misses.
Nothing is renamed and nothing is forked.

## Membership exists as a contract

`membership_directory_service` and `postgres_membership_directory_service` model
org membership; the Postgres one documents that isolation is "enforced by the
database via `app.current_org_id`, not by this class". Modeled, not live —
customer persistence is false.

## Answers to the specific questions

```text
auth/login/session/OIDC/JWT services exist?   yes, ~40, all contract-only
any route customer-authenticated?             no - unauthenticated header
any service maps claims to organization_id?   no - it maps to
                                              organization_profile_id
any service sets app.current_org_id?          one: deps_db, from the header
any service validates org membership?         modeled only, not live
any admin role exists?                        operator_admin, org_admin,
                                              tribal_admin - but no
                                              platform_admin or tenant_admin
customer admin role?                          org_admin / org_owner (Gate 51)
platform admin role?                          operator_admin / operator_internal
any auth surface demo-only?                   effectively all of it
backend auth or only front-door auth?         front door only; backend auth is
                                              contract-only and not running
Auth0/OIDC referenced but not live?           yes - extensively referenced,
                                              provider_configured False
should customer auth be considered live?      NO
```

## What this gate must therefore build

1. A principal contract where **authenticated does not imply verified
   organization membership** — the two are separate fields because the claim
   path does not currently produce an `organization_id` at all.
2. A binder authorization service that refuses production verification to
   anything short of `authenticated_verified_org` with a UUID `organization_id`.
3. An RLS claim guard, because the one path that sets `app.current_org_id` today
   trusts an unauthenticated header, and any future auth-driven path must not
   inherit that.

## What this gate does not attempt

```text
attaching a provider              needs OIDC_* secrets set out-of-band by the
                                  owner; not a code change
making login live                 the promotion gate already owns that decision
closing the profile_id gap        the claim path terminating in
                                  organization_profile_id is real and named here;
                                  reconciling it is its own gate
changing the dev header path      it is contained by deployment posture today,
                                  and changing it without auth to replace it
                                  would break sixteen route modules for nothing
```
