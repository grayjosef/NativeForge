# Gate 132 — the authorization, and what was created under it

## What Mayhem authorized

Quoted from the instruction that followed the `AUTHORIZE DEV ORG BINDING` stop
point:

> Authorization is limited to the demo organization only:
> organization_id: bbbbbbbb-cccc-dddd-eeee-ffffffffffff
> org_type: demo
> is_demo: true
>
> Do not bind the Google identity to: aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee
> Do not create production bindings.
> Do not write real customer data.
> Do not infer demo status from caller input alone.

## The identity

```text
provider          Google
issuer            https://accounts.google.com
subject           stored raw in nf_identities, per migration 0023's schema.
                  Never printed, never logged, never written to an artifact.
                  It is the (issuer, subject) lookup key and a hash cannot be
                  looked up against a claim without hashing the claim.
email domain      gmail.com
email             stored, verified, and authority for nothing
verification      oidc_token_signature — the only value the CHECK permits
```

## The organization, and why the enforcement is not the chat log

The authorization named one organization. An authorization in a transcript is
not an enforcement, so `dev_org_membership_bootstrap_service` refuses any
organization whose `organizations.org_type` is not `demo`, and derives `is_demo`
from that row. There is no `is_demo` parameter to pass.

```text
bbbbbbbb-cccc-dddd-eeee-ffffffffffff   org_type=demo   membership created
aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee   org_type=real   refused by name
```

The refusal was exercised, not assumed:
`bootstrap_membership_refused_for_a_non_demo_organization`.

## The demo-org inconsistency, reconciled first

Mayhem made this a precondition. Three sources claimed to know which
organizations are demo and they did not agree:

```text
before
  organizations.org_type          demo for bbbbbbbb-cccc-dddd-eeee-ffffffffffff
  NF_DEMO_ORG_IDS                 unset, so demo_org_uuid_set() was empty
  demo_isolation.org_type_for()   'real' for that same organization

after
  all three agree; allowlist_matches_database true
```

The database row is the authority, because it is the only one of the three that
is a fact about the organization rather than a statement about a deployment. The
allowlist is compared against it and a disagreement **refuses** the
classification rather than picking a winner.

## Records created

```text
nf_identities                     1   written by the callback, from a verified claim
nf_org_memberships                1   demo org, is_demo derived, role org_owner
nf_tenant_customer_org_bindings   1   demo_fixture, no verifier
```

Nothing was written for `aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee`: 0 memberships, 0 bindings.

## Self-approval, permitted exactly once

Migration 0024 requires an approver for any source but `verified_directory`. The
first membership in an organization has nobody to approve it, so it names
itself — and only while the organization has no memberships at all. The second
self-approved membership is refused
(`self_approval_permitted_only_for_the_first_membership`), which was observed
when this script was re-run.
