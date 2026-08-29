# 619 — Gate 113D: membership lookup wired to organization_id

The defect, the fix, and the two masks that kept it invisible.

## The defect

`postgres_membership_directory_service.lookup_membership`, before this gate:

```python
def lookup_membership(self, *, identity_id, organization_profile_id):
    ...
    f"WHERE identity_id = :identity_id AND organization_id = :org",
    {"identity_id": identity_id, "org": str(organization_profile_id)},
```

A parameter named for `organization_profile_id` — a `String(128)` with no
foreign key and no RLS behind it — bound to `organization_id`, a
`Uuid(as_uuid=True)` foreign key to `organizations.id` that every RLS policy
casts and compares.

Two identity spaces sharing one variable, in the query that decides whether a
person is a member of an organization.

## Why it never surfaced

```text
self.configured is False in normal operation. No Postgres is provisioned, so
_query returns nothing and the method exits before the predicate matters.

The Gate 62 tests supply a fake row_source that answers by table name rather
than by parsing SQL, so the value never reached a real UUID column.
```

Neither is a fix. Against a real PostgreSQL with a profile-shaped value the
`::uuid` comparison raises — the database refusing the conflation on our behalf,
which is a far worse place to discover it than here. An exception inside a
request handler is not a refusal with a reason.

## The tests encoded the defect too

```text
tests/test_gate62_storage_membership_rls_path.py
  ORG = "org-profile-1"            a profile-shaped string
  19 call sites passing it as organization_profile_id
  3 of them asserting allowed is True
```

Three tests were passing on a path that should have refused their input. Fixing
the service without the constant would have broken them, and that is the correct
direction: `ORG` is now `00000000-0000-4000-8000-0000000000a1` and all nineteen
call sites became correct at once.

## The fix

```python
def lookup_membership(self, *, identity_id, organization_id):
    if not identity_id or not organization_id or not self.configured:
        return None
    if not _is_uuid_shaped(organization_id):
        return None
```

Renamed, not aliased. Keeping `organization_profile_id` as an accepted keyword
would have preserved the defect behind a working signature; a caller that still
passes it now gets a `TypeError`, which a test asserts.

The UUID check refuses rather than coerces. A profile id is not an organization
id, and passing one would either raise in Postgres or match nothing — both worse
than a named refusal.

## The resolver keeps the old name, deliberately

`resolve_persisted_membership` takes both, and they behave differently:

```text
organization_id           the parameter that reaches the UUID path

organization_profile_id   forwarded only if uuid-shaped, and then with the
                          reason organization_supplied_under_the_deprecated_parameter
                          otherwise refused with
                          organization_profile_id_is_not_an_organization_id
```

A UUID arriving under the old name is an organization id wearing the wrong
label: refusing it outright would break callers for no safety gain, and
accepting it silently would hide that they are still using the old name. It is
accepted and said out loud.

## Two stale references the rename exposed

Both were found by the tests, and both are the same class of bug as the original:

```text
the defence-in-depth row check still compared the row's organization_id against
organization_profile_id, which is None once a caller uses the correct name -
so every row would have mismatched

the audit event still recorded organization_profile_id, so the trail would have
named the wrong identity - or no identity at all - for every correct call
```

An audit event that names the wrong identity is precisely the failure this gate
exists to fix, one layer up. Both now use the organization that actually reached
the lookup.

## The in-memory directory is not the same bug

`InMemoryMembershipDirectory.lookup` keys a plain dict on
`(subject, organization_profile_id)`. There is no UUID column and no row-level
security behind it, so profile keying is coherent there and Gate 61's
`ORG_A = "org-aaaa"` is a legitimate key.

It gained `organization_id` as an accepted alternative for vocabulary agreement.
Changing the keying would have broken Gate 61 for no safety gain, and treating
the two services' situations as one problem would have produced exactly that.

## The wiring, as committed

`artifacts/tenant_customer_org_binding_store/membership_organization_id_wiring.csv`

```text
call_site                                              parameter                gate_113_status
postgres.lookup_membership                             organization_id          renamed_by_gate_113
postgres.resolve_persisted_membership                  organization_id          renamed_by_gate_113
postgres.resolve_persisted_membership                  organization_profile_id  deprecated_by_gate_113
in_memory.lookup                                       organization_id          vocabulary_added_by_gate_113
in_memory.lookup                                       organization_profile_id  correct_here_unchanged
```
