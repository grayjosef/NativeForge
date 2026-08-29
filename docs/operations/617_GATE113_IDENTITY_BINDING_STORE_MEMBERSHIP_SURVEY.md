# 617 — Gate 113A: identity binding store and membership survey

Written before any implementation. Every claim was reproduced by reading the
schema, the migrations, the services and the tests.

## Existing identity and membership tables

```text
nf_identities        UNIQUE (issuer, subject) -> id (UUID)
                     subject, issuer, email, email_verified,
                     verification_source, disabled_at
nf_org_memberships   id (UUID)
                     organization_id  UUID FK organizations.id CASCADE
                     identity_id      UUID FK nf_identities.id CASCADE
                     state, membership_source, role, role_source,
                     invited_by, approved_by, revoked_at, expires_at, is_demo
```

RLS is applied by migration 0027 to both, keyed on
`organization_id = current_setting('app.current_org_id', true)::uuid`.

## No tenant/customer-org binding table exists

Searched every migration and the model file: zero matches. Latest revision is
0028. A migration is required for the binding store, and Gate 110 already
specified its shape.

## The membership lookup defect, in full

`postgres_membership_directory_service.lookup_membership`:

```python
def lookup_membership(self, *, identity_id, organization_profile_id):
    ...
    f"WHERE identity_id = :identity_id AND organization_id = :org",
    {"identity_id": identity_id, "org": str(organization_profile_id)},
```

A parameter named for the `String(128)` profile identifier, bound to a
`Uuid(as_uuid=True)` foreign key column.

### Why it has never surfaced

Two masks, and neither is a fix:

```text
self.configured is False in normal operation - no Postgres, so _query returns
nothing and the method exits before the predicate matters

the tests supply a fake row_source that returns rows regardless of the SQL, so
the value never reaches a real UUID column
```

Against a real Postgres with a profile-shaped value, the `::uuid` comparison
would raise rather than silently mismatch. That is the database refusing the
conflation — but relying on it means an exception inside a request handler
instead of a refusal with a reason.

### Call sites

```text
lookup_membership              2, both inside the Postgres service itself
resolve_persisted_membership   1 definition, 19 call sites in
                               tests/test_gate62_storage_membership_rls_path.py
```

Narrow enough to rename safely.

### The tests encode the defect

```text
tests/test_gate62_...  ORG = "org-profile-1"   passed to
                       resolve_persisted_membership(organization_profile_id=ORG)
                       -> lookup_membership -> WHERE organization_id = :org
```

Nineteen call sites, three of which assert `allowed is True`.

So the brief's instruction — "tests must fail if a profile-shaped string reaches
the UUID organization_id path" — means those three currently *pass* on a path
that should refuse them. Fixing the service without updating the constant would
break them; that is the correct direction, and the fix is one line: `ORG` becomes
a UUID, and nineteen call sites become correct at once.

## The in-memory service is not the same bug

`membership_directory_service.InMemoryMembershipDirectory.lookup` keys a plain
dict on `(subject, organization_profile_id)`. There is no UUID column and no RLS
behind it; profile-keying is coherent there, and Gate 61's `ORG_A = "org-aaaa"`
is a legitimate key.

It needs vocabulary agreement, not a bug fix. Conflating the two services'
problems would produce a change that breaks Gate 61 for no safety gain.

## Does a migration conflict with Gate 110?

Gate 110 reported `migration_safe_now: False` for three reasons: no customer
auth to supply a verifier, no customer persistence to write into, and no verified
binding to store.

Those are reasons not to **store a verified binding**. They are not reasons the
table cannot exist. An empty table under RLS stores nothing, claims nothing and
is reversible by its own downgrade.

The distinction matters and is kept explicit: creating the table must not flip
`operational_binding_storage_allowed`, and `migration_applied` — currently a
hard-coded `False` in the decision service — must become **detected** from the
migrations directory rather than asserted, or it becomes a lie the moment the
revision lands.

## Recommended schema

Gate 110 specified it; this gate implements it unchanged.

```text
nf_tenant_customer_org_bindings
  id                       UUID PK
  organization_id          UUID NOT NULL FK organizations.id CASCADE  <- anchor
  tenant_id                text NOT NULL   label, not a foreign key
  customer_org_id          text NOT NULL   label, not a foreign key
  binding_status           text NOT NULL   Gate 109 vocabulary, CHECK
  binding_source           text NOT NULL   Gate 109 vocabulary, CHECK
  binding_confidence       text NOT NULL
  verified_by_identity_id  UUID NULL FK nf_identities.id
  verified_at              timestamptz NULL
  revoked_at               timestamptz NULL
  revoked_by_identity_id   UUID NULL FK nf_identities.id
  human_review_required    boolean NOT NULL DEFAULT true
  blocked_reasons          jsonb NOT NULL DEFAULT '[]'
  created_at, updated_at   timestamptz NOT NULL

  CHECK  verified_binding requires verified_at AND verified_by_identity_id
  CHECK  demo_fixture may not carry a verifier
  UNIQUE (organization_id, tenant_id, customer_org_id) WHERE revoked_at IS NULL
  RLS    organization_id = current_setting('app.current_org_id', true)::uuid
```

`tenant_id` and `customer_org_id` are `text` and carry no foreign key,
deliberately: they are labels, and a label with a foreign key would become an
identity space by accident.

## Answers to the specific questions

```text
existing identity tables            nf_identities
existing membership tables          nf_org_memberships
existing RLS on them                yes, migration 0027, organization_id keyed
binding table exists?               no
migration required?                 yes, and it is additive and reversible
membership lookup bug               postgres_membership_directory_service:258
lookup_membership call sites         2, both internal
signature safely renameable?         yes
in-memory service needs the change?  vocabulary only - its profile keying is
                                     correct for a dict with no UUID column
tests depending on the parameter      19 in Gate 62; three assert allowed True
persistence guard needs patching?     no rule change - it already refuses
                                     tenant_id and customer_org_id; only the
                                     readiness surface learns the store exists
```

## What this gate does not attempt

```text
inserting rows                  the table starts empty and stays empty
making persistence live         customer_persistence_live stays false
making auth live                no provider, no verifier
changing the in-memory service  beyond adding organization_id vocabulary
removing the dev org header     Gate 112's containment record still stands
```
