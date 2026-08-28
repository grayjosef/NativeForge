# 600 — Gate 109B: tenant / customer org binding contract

`src/nativeforge/services/tenant_customer_org_identity_binding_service.py`

## tenant_id and customer_org_id are not automatically equivalent

They are two identity spaces that grew in different gates. Gates 90–91 built the
awarded lane on `customer_org_id`; Gates 103–108 built the tenant beta lane on
`tenant_id`. Nothing relates them, and this contract does not invent a relation.

A binding is a **record**. Two identifiers are related because somebody said so
and it was checked — never because they look alike, share a prefix, or have
similar names.

The failure this prevents is concrete. Bind the wrong pair and a Tribe sees
another Tribe's awarded grants, their digest suppressions leak across, and their
document library opens to strangers.

## Explicit binding is required

```text
unbound          one or both identifiers missing
pending_review   both asserted, nobody has checked
demo_fixture     a demo relationship, labelled as such
verified_binding both ids, a source that can verify, and an actual verifier
conflict         one value used for both identity spaces
revoked          a binding that was withdrawn
unknown          nothing established
```

Status is **derived**. A caller asks; the record decides. Requesting
`verified_binding` from `human_entered` produces `pending_review` and a blocked
reason naming the source, because asserting is not checking.

```text
VERIFYING_SOURCES = {admin_verified, migration_import}
```

Derived affirmatively — a source not in that set cannot verify, whatever else is
true of the record.

## Matching strings do not create a binding

`build_binding` never compares the two identifiers to decide they belong
together. A caller passing the same string for both gets `conflict`, not a
shortcut: one value cannot be two identity spaces at once, and doing that is the
exact conflation this contract exists to catch.

An invariant fails any record with identical identifiers not marked `conflict`,
and mutations removing either the detection or the invariant are caught.

## Matching names do not create one either

`acme-tribe` and `acme-tribe-org` produce `pending_review`, not a binding.
`derived_from_matching_names` is a constant `False` on every record.

## System inference is refused, and the refusal is recorded

`system_inferred_blocked` exists in the source vocabulary so an attempt to infer
a binding can be recorded as refused rather than silently succeeding. It produces
`pending_review` with `system_inference_is_not_a_binding`, and `system_inferred`
stays `False`.

## demo_fixture binding is not production verification

A demo binding lets a demo run. It never satisfies an operational surface.

```text
binding_status         demo_fixture       not verified_binding
binding_confidence     demo_only
is_production_verified False
```

An unlabelled demo binding is refused outright. An invariant fails a demo binding
claiming production verification, and another fails one that dropped its label.

## Tenant id shape is recorded

Gate 109A found two incompatible shapes coexisting:

```text
tn_<16 hex>    derived by Gate 51 from an organization profile id
anything else  free-form, supplied by the Gates 103-108 lanes
```

A record says which it holds. Treating them as one kind of thing would make this
contract worse than none — it would look authoritative while relating two
different things.

### Gate 51's derivation is evidence, not verification

`org_tenant_seat_model_service.make_tenant_id` produces `tn_<hash>` from an
*organization profile id*, and its docstring says "One organization = one
tenant". That is a real relationship, but it relates a tenant id to a third
identifier — not to the `customer_org_id` this binding is about.

So a `gate51_derived` shape is recorded and does not promote anything. A test
builds a real derived id, confirms the shape is detected, and confirms the
binding still lands in `pending_review`.

## Absence of a binding blocks operational persistence

Nothing here persists. What the contract provides is the fact the resolution
guard (doc 601) reads before permitting any operational read or write, and that
the awarded, digest and beta readiness services now require before reporting
operational readiness.

```text
bindings_persisted   false
identities_assumed_equivalent  false
```
