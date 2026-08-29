# 616 — Gate 112F/G: readiness delta

## What this gate added

```text
oidc_organization_id_resolution_contract_available  true
membership_verification_contract_available          true
dev_header_containment_contract_available           true
organization_id_required_for_rls                    true
organization_profile_id_is_rls_authority            false
```

Contracts only. Nothing here logs anybody in, contacts a provider, sets an RLS
context, changes a schema or writes a row.

## What remains false

```text
customer auth live               false
login live                       false
dev header production safe       false
binding store built              false
verified operational binding     false
operational awarded tracking     false
operational digest               false
beta onboarding                  false
customer persistence             false
document storage                 false
live source collection           false
source monitoring                false
source coverage                  false
```

`customer_auth_live` and `login_live` are read from
`login_live_promotion_gate_service`, which still reports seven of ten gates
missing. The artifact carries that list verbatim, so the claim is checkable
rather than a bare `false`.

No live provider call occurred. No live fetch occurred. No collector ran.

## No migration was applied, and none is needed

Gate 112A found `nf_identities` (unique on issuer + subject) and
`nf_org_memberships` (`identity_id` FK, `organization_id` FK, under RLS) already
model the claim → organization_id path. The gap was service-layer only.

```text
migration_applied   false
schema_changed      false
```

## A tightening of Gate 111

`rls_context_allowed` on the auth principal now requires `membership_verified` as
well as verified-org auth. An organization claim says *which* organization was
asserted; membership says the person belongs to it.

Two Gate 111 tests were updated to supply the new fact rather than deleted, and
two were added — one confirming a verified-org principal without membership gets
no context, one confirming the invariant catches a forged claim. The rule they
guarded got stronger, not obsolete.

## Readiness services

The three readiness services already required a verified binding from Gate 109
and already reported false. No duplicate key was added — a second flag false for
a related reason is noise, not safety.

The binding store decision's next-actions already named this gate's work from
Gate 111 and remain accurate: attach a provider, and map claims to
`organization_id`. The second is now built.

## Demo fixtures

Eight labelled claim cases, one per resolution outcome. **Exactly one reaches an
RLS context**, and a test asserts that count rather than trusting it.

```text
customer_auth_live            false
login_live                    false
real_user_data                false
real_sessions_created         false
identity_provider_contacted   false
secrets_stored                false
current_org_id_set            false
```

The pair worth reading together is `verified_uuid_org_with_membership` and
`verified_profile_only`: same provider, same verified claims, and one resolves to
the `organization_id` RLS enforces on while the other stops at a profile id. That
is the exact distance the real claim path falls short by.

As in Gate 111, the permitted case is a fixture and not evidence: it shows what a
resolved principal *would* be allowed to do, and no provider was contacted to
build it.

## Carried forward

```text
lookup_membership names a profile id and queries organization_id
    postgres_membership_directory_service binds a parameter called
    organization_profile_id to the organization_id UUID column. Dormant -
    customer persistence is false - but it is the same conflation this lane
    exists to prevent. Named in doc 612; belongs with the work that makes
    membership live, because fixing the signature touches the in-memory
    directory too.

the OIDC mapper still targets organization_profile_id
    Gate 17's, fixture-only, and rewriting it with no provider attached would be
    changing code that reality has never exercised. This gate supplies the
    contract it should call into when a provider arrives.
```
