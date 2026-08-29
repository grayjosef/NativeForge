# 609 — Gate 111C: verified binder authorization contract

`src/nativeforge/services/verified_binder_authorization_service.py`

## The gap this fills

Gate 110's binding store decision listed customer auth as its first blocked
reason: a verified binding needs a verifier, and nobody can be one until a person
can authenticate. This says *which* person, once they can.

## It authorizes; it does not bind

```text
binding_created   false, always
binding_modified  false, always
persisted         false, always
```

Creating the binding remains Gate 109's `build_binding`, which still applies its
own rules — an authorized verifier does not get to skip them. An authorization
service that can also perform the act it authorizes has no separation of duties
in it.

## Who may verify

```text
platform_admin  create, approve, revoke, resolve conflicts, inspect
tenant_admin    create, approve, revoke, resolve conflicts, inspect
grants_manager  inspect only
auditor         inspect only
grants_viewer   nothing
unknown         nothing
```

The `grants_manager` line is the interesting one. Inspection is how a pending
binding gets checked, and somebody has to be able to look without being able to
approve. Granting them verification too would collapse the four-eyes property
that Gate 109's `pending_review` status exists to create.

`grants_viewer` cannot even inspect — a viewer reads data, not pending identity
decisions.

## Production verification requires verified-org auth

An `authenticated_verified_org` principal with a UUID `organization_id`. Nothing
less. An unverified-org tenant_admin — same person, same role, organization never
established — is refused with
`production_verification_requires_authenticated_verified_org`.

Invariants fail any authorized verification without a verifier role, without
verified-org auth, or without verified membership.

## A demo principal verifies demo bindings only

```text
demo tenant_admin vs a demo_fixture binding    authorized
demo tenant_admin vs a production binding      refused
```

This is why `authenticated_demo` is a distinct status rather than a flag on a
real login. A demo tenant verifying a real binding would create a record nobody
checked, under the authority of nobody.

An invariant fails a demo principal authorized against a production binding, and
the mutation removing the check is caught.

## An unusable principal is authorized for nothing

Unauthenticated, expired, revoked and unknown all refuse every operation,
including inspection. A revoked platform admin has no more authority than a
stranger.

## cross_tenant_risk is reported on the attempt

True whenever a verification is attempted and refused by someone who was at
least authenticated — the useful signal is that somebody tried. It always routes
to `human_review_required`.
