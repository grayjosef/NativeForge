# 622 — Gate 114B: the customer persistence capability contract

`src/nativeforge/services/customer_persistence_capability_service.py`

Eight lanes, and four separate questions asked of each.

## The four questions

```text
schema_available       is there a table?
rls_backed             does a migration install a policy on it?
write_path_available   can anything address it, and does it carry the anchor?
operational            may anything actually be written today?
```

Collapsing these into one word is the failure this service exists to prevent.
"NativeForge has customer persistence" is a sentence somebody can write from a
single green boolean, and it would be false.

## Seven conjuncts to reach operational

```python
write_path_available = (
    schema_available
    and organization_id_anchor_available
    and rls_backed
    and repository_available
    and service_contract_available
)
operational = write_path_available and customer_auth_live and not blocked_reasons
```

Derived affirmatively. Nothing is subtracted from a permissive default and no
caller flag grants anything.

## Where each lane stands

```text
lane                              schema  rls  repo  contract  write  operational
tenant_profile_persistence          yes   yes   yes    yes      yes      no
identity_binding_persistence        yes   yes   no     yes      no       no
tenant_digest_persistence           no    no    no     yes      no       no
awarded_grants_persistence          no    no    no     no       no       no
award_requirements_persistence      no    no    no     no       no       no
document_library_persistence        no    no    no     no       no       no
source_watchlist_persistence        no    no    no     no       no       no
beta_onboarding_persistence         no    no    no     no       no       no
```

Two lanes are worth reading closely.

**`tenant_profile_persistence` is complete except for auth.** `nf_tribal_profiles`
has one row per organization, `organization_id` unique and NOT NULL, `is_demo`,
RLS since migration 0003, and a repository that writes. Its only blocked reason
is `no_customer_auth_so_nobody_owns_the_row`. Built and unusable — which is what
`demo_only: true` means here.

**`identity_binding_persistence` is the inverse.** Gate 113 created the table
under RLS and the service that decides what may enter it, and deliberately no
write path. `no_repository_can_address_this_capability` is not an oversight;
it is Gate 113's boundary restated by a different service.

## The defect this replaced

Gate 114A found the same fact stated three ways:

```text
awarded lane   customer_persistence_live = _module_importable(
                   "nativeforge.repositories.awarded_grant")
digest lane    customer_persistence = False        hard-coded
beta lane      customer_persistence_live = False   hard-coded
```

All three reported `False` and all three were correct, for unrelated reasons.

Two were constants of the kind Gate 113 removed from `migration_applied`: they
would have gone on saying `False` after persistence became real. The third was
worse, because it moved in the unsafe direction — creating an empty
`repositories/awarded_grant.py` would have flipped `customer_persistence_live`
to `True` with no table, no policy, no anchor and nobody able to authenticate.

All three now call `build_capability`, which requires all seven conjuncts.

## Detection roots are injectable

`models_path`, `versions_dir` and `repositories_dir` are parameters. A test
points them at an empty directory and observes every lane reporting absent —
without that, `schema_available: False` would be unreachable for the two lanes
that have a table, and an unreachable branch is an untested one.

`customer_auth_live` is injectable for the same reason, in the other direction:
forcing it true makes exactly one lane operational and
`customer_persistence_live` true. That is what makes today's `False` a
measurement rather than a constant.

## How customer_auth_live is detected, and why not the obvious ways

> **Superseded by Gate 115.** The mechanism below was correct for Gate 114,
> which had nothing that could measure customer auth. Gate 115 built the
> activation gate, and this value now reads it through
> `customer_auth_live_detector_service`. See docs 627 and 631. The reasoning
> below is kept because it records why the obvious alternatives were rejected,
> and those reasons still hold.

Not from `tenant_beta_readiness_service`: that module now asks this one about
persistence, and asking back would be a cycle.

Not from `dev_org_header_containment_service`: it shells out to `systemctl`,
which would make every committed capability artifact depend on the machine that
generated it.

So it is detected locally and affirmatively — something must exist for auth to
be live. That is a module-existence check, which this same document criticises
above. The difference is direction and weight: there, one empty file flipped a
readiness claim on its own; here it is one conjunct of seven, and an empty file
still leaves a lane with no table, no policy, no anchor and no repository.

Gate 112's finding stands behind the `False` it returns: the only org-context
path in the application is an unauthenticated dev header, and
`dev_org_header_containment_service.production_safe` is a constant `False`.

## Bridged, never forked

`RLS_ANCHOR_COLUMN` and `FORBIDDEN_ANCHOR_NAMES` are imported from Gate 113's
binding store rather than restated. A test asserts the two modules hold the same
objects. A second copy of those names is how the layers would come to disagree.
