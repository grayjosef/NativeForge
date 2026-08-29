# 608 — Gate 111B: auth principal contract

`src/nativeforge/services/customer_auth_principal_contract_service.py`

## Customer auth is not live

Not asserted here — read from `login_live_promotion_gate_service`, which already
owns the question:

```text
login_live_claimed          False
production_auth_claimed     False
missing_gates               provider_configured, secret_present,
                            issuer_jwks_validated, callback_session_validated,
                            invite_binding_passed, org_binding_passed,
                            role_mapping_passed
```

Seven of ten gates missing. This contract describes principals; it logs nobody
in, and `customer_auth_live` and `login_live` are constants `False` on every
record.

## Authenticated is not verified-org

The distinction the gate turns on, and it is not pedantic.

Gate 111A found `oidc_identity_mapper_service` resolves a claim to an
`organization_profile_id` — a `String(128)` with no foreign key, on a table with
no row-level security. It never produces the `organization_id` UUID the policies
enforce on.

So even a real, provider-validated login would establish *a person* without
establishing *which organization they may act for*. Two facts, two fields:

```text
claims_verified      the provider vouched for the subject
org_claim_verified   somebody established which organization_id that means
```

`authenticated_unverified_org` is a normal expected state, not a degraded one. A
test feeds an org claim of `org-profile-123` — the real shape of today's path —
and confirms it lands there.

## Demo auth is not production auth

`demo_fixture` is a source, not a lesser tier. A demo principal gets
`authenticated_demo`, never `authenticated_verified_org`, and
`is_production_authenticated` is False however many roles it carries. Invariants
fail a demo principal claiming production authentication or RLS context.

## Cloudflare Access is a front door

It controls who reaches the host. It establishes no organization and sets no RLS
context, so it is deliberately absent from `PRODUCTION_CAPABLE_SOURCES`. A
Cloudflare-authenticated visitor reaches `authenticated_unverified_org` at best,
with a blocked reason saying why.

Treating edge access as application auth would make everyone who can open the
site look like a customer.

## Permissions are cut down by status

Roles grant; status takes away.

```text
dead statuses                 no permissions at all
authenticated_demo            demo permissions, plus inspection
authenticated_unverified_org  nothing operational, and no verify_binding
authenticated_verified_org    the role's full grant
```

## Four role vocabularies, bridged not forked

Gate 111A found three already in the tree — `rbac_policy_contract` (8),
`org_tenant_seat_model` (6), and one internal role. This contract defines the
fifth vocabulary the brief asked for and **maps the existing two onto it**.

`role_mappings_are_complete()` imports both sources and fails if either grows a
role the mapping misses. Nothing is renamed and nothing is forked.

## RLS context requires a UUID organization_id

`rls_context_allowed` needs `authenticated_verified_org` and a UUID-shaped
`organization_id`, classified through Gate 110's role contract rather than
re-implemented. `tenant_id` and `customer_org_id` cannot produce it at all —
that refusal lives in the claim guard and is not duplicated here.
