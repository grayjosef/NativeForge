# 613 — Gate 112B: claim to organization_id contract

`src/nativeforge/services/oidc_organization_id_resolution_service.py`

## organization_id is required for RLS; organization_profile_id is not authority

Every row-level security policy reads
`organization_id = current_setting('app.current_org_id', true)::uuid`. Gate 111
found the claim path terminates one identifier short of that: at
`organization_profile_id`, a `String(128)` with no foreign key on a table with no
RLS policy.

This contract closes the distance, or says precisely why it could not.

## Nine outcomes, eight of which block RLS

```text
resolved_verified_organization_id  verified claims, UUID org, verified member
resolved_demo_fixture              a demo path; never production
resolved_profile_only              a profile id and nothing else
unresolved_no_org_claim            no organization asserted
unresolved_unverified_claims       the provider did not vouch for the subject
unresolved_invalid_uuid            an org claim that cannot survive ::uuid
unresolved_membership_missing      a UUID org, nobody says they belong to it
conflict                           profile and organization claims disagree
unknown                            nothing established
```

`resolved_profile_only` is its own status rather than a generic failure, because
it is what the current mapper actually produces. A caller can tell "we know who
they are and which profile, but not which organization" from "we know nothing".

## A profile id is never promoted

`organization_profile_id` is carried on every result as **evidence**.
`resolved_organization_id` is populated only under a resolved status, and an
invariant fails any result where the two are equal.

The mutation that promotes a profile id into the resolved field is caught, as is
the one that drops the invariant.

## Verification order is not cosmetic

```text
subject -> conflict -> demo -> claims_verified -> org claim present
        -> UUID shape -> membership -> resolved
```

Claims are verified before the organization is resolved, and membership before
RLS is permitted. Resolving an organization from claims nobody vouched for would
produce a confident-looking answer built on nothing — and that answer would then
be what some future caller passes to `set_config`.

## Membership is matched on organization_id

`_membership_for` compares `record["organization_id"]` to the candidate, never a
profile id and never "a record exists". A membership for a different
organization does not count, and the mutation that matches any record is caught.

Revocation is read from `revoked_at`, and state from `state` — a row means
somebody once proposed a relationship, not that it currently holds.

## No migration was needed

Gate 112A found the schema already models this:

```text
nf_identities        UNIQUE (issuer, subject) -> id
nf_org_memberships   identity_id FK, organization_id FK, under RLS
```

The gap was service-layer only. This contract reads membership records the
caller supplies and queries nothing itself.

## One redundant conjunct, documented rather than hidden

`rls_context_allowed` checks the resolution status *and* the resolved value's
shape. Since `resolved` is `None` under every non-resolved status, the status
check is unreachable by construction, and mutation testing confirms a mutation
widening it survives against real inputs.

It is kept as defence in depth against a future edit that populates `resolved`
earlier, the redundancy is stated in the code, and the protection it would
provide is carried by the `partial_resolution_permitted_rls` invariant — which is
tested against a forged result.

Recording that is better than deleting the conjunct and better than pretending
the mutation was caught.
