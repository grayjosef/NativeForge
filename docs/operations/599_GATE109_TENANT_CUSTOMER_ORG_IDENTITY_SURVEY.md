# 599 — Gate 109A: tenant / customer org identity survey

Written before any implementation. Every claim was reproduced by running the
tree.

## The brief's premise needs correcting in two ways

Gate 108 reported two identity names and no bridge. Both halves are incomplete.

```text
brief says   two ids, tenant_id and customer_org_id, no bridge exists
tree says    FOUR names, and a derivation already exists
```

Neither correction makes the gate unnecessary. Both make it more urgent, and
they change what the binding contract has to model.

## Four names, not two

```text
organization_id    UUID       ~18 DB tables      the persistence truth
org_id             string     ~70 services       the operational id
customer_org_id    string     6 services         Gates 90-91, 108
tenant_id          string     20 services        Gates 51, 103-108
```

`organization_id` is the one the brief never mentions and the one that matters
most, because it is the only identity the database actually stores.

## Row-level security keys on the organization, not the tenant

`src/nativeforge/db/rls.py`:

```python
session.execute(
    text("SELECT set_config('app.current_org_id', :oid, true)"),
    {"oid": str(org_id)},
)
```

The cross-tenant isolation that already exists is **org-scoped**, enforced by
Postgres RLS policies against `app.current_org_id`.

Confirmed by search:

```text
tenant_id columns in src/nativeforge/db/         none
tenant_id in src/nativeforge/repositories/       none
customer_org_id in db, repositories or api       none
routes reading tenant_id                         none
```

So `tenant_id` today is a **product-lane label with no enforcement behind it and
no column to persist into**. That is not an argument for abandoning it — Gates
103–108 built real contracts on it — but it is the reason this gate must run
before persistence rather than after. Persisting a tenant-scoped record into an
org-scoped store without an explicit binding is how the leak happens.

## A derivation already exists

`org_tenant_seat_model_service.py:96`, from Gate 51:

```python
def make_tenant_id(organization_profile_id: str) -> str:
    raw = f"tenant::{organization_profile_id}".encode()
    return f"tn_{hashlib.sha256(raw).hexdigest()[:16]}"
```

Its module docstring states plainly: **"One organization = one tenant."**

So the tree already contains both an equivalence claim and a one-way function
implementing it. The brief's instruction not to derive one id from the other is
a rule about *new* code; it does not describe the code that is there.

### But it reaches almost nothing

```text
call sites of make_tenant_id   3, all inside org_tenant_seat_model_service
consumers in the tenant lane   none
```

Gates 103–108 never call it. Their tenant ids are free-form strings supplied by
callers.

## Two incompatible tenant_id shapes coexist

The sharpest finding, and the one the binding contract has to handle:

```text
Gate 51 derived      make_tenant_id("org-profile-123")  ->  tn_c206946f01e50396
Gate 104/108 lane    DEMO_TENANT_ID                     ->  nf-demo-tenant-01
Gate 108 customer    DEMO_CUSTOMER_ORG_ID               ->  nf-demo-org-01
```

Nothing in the tree distinguishes them. A `tn_`-prefixed id carries a real
relationship to an organization profile; an `nf-demo-tenant-01` carries none.
Treating them as one kind of thing is the mistake that would make a binding
contract worse than no binding contract, because it would look authoritative
while binding two different things.

The binding record therefore records the **shape** of the tenant id it holds,
and a derived id is not automatically a verified binding — it is evidence that
one organization profile produced it, which is a different claim from "this
tenant is that customer org".

## Where both ids appear together

```text
awarded_grant_record_service            both, with tenant_org_binding_status
award_transition_service                both, in the Gate 108 tenant lane
awarded_grants_demo_fixture_service     both
awarded_grants_requirements_readiness   both
```

Gate 108 carried both deliberately and derived neither. That is the only surface
where the two meet honestly today.

`awarded_grant_portfolio_service` and `grant_lane_separation_service` use
`customer_org_id` alone; the whole Gates 103–104 tenant lane uses `tenant_id`
alone.

## Where one identifier is missing but needed

```text
tenant digest lane        tenant_id only; nothing ties a digest to an org, so
                          it cannot be persisted or access-controlled today
awarded grants portfolio  customer_org_id only; a tenant cannot reach its own
                          awarded records without a binding
document/evidence lane    org_id only (evidence_metadata_model_service,
                          evidence_storage_adapter_service); no tenant concept
source watchlist          tenant_source_priority_service is tenant_id only
```

## Demo-only versus persistence-facing

```text
demo/contract only   every tenant_* service, the awarded grants Gate 108 set,
                     org_tenant_seat_model (explicitly "not persisted")
persistence-facing   the ~18 db models, the repositories, the api routes -
                     all organization_id, none tenant-aware
```

The line is clean and worth stating: **nothing tenant-scoped is persistence-facing
yet.** That is exactly why the binding can still be defined cheaply.

## Does anything silently equate them today?

```text
silent equivalence in code      no
declared equivalence in a
  docstring                     yes - Gate 51, "One organization = one tenant"
implemented derivation          yes - make_tenant_id, one-way, 3 internal uses
inference from matching strings no
inference from names            no
```

No service compares a `tenant_id` to a `customer_org_id` and treats a match as a
binding. The risk is prospective rather than present, which is the right time to
close it.

## What this gate must therefore model

1. A binding is a **record**, not a computation. Two ids are related because
   somebody said so and it was checked, never because they look alike.
2. The binding must record the **tenant id shape**, because a Gate 51 derived id
   and a free-form beta id are different kinds of claim.
3. Gate 51's derivation is **evidence**, not verification. It relates a tenant id
   to an *organization profile id*, which is a third identifier again.
4. The guard must key operational permission on the binding, and must treat the
   absence of one as a cross-tenant risk rather than as a neutral default.
5. Nothing here makes persistence live. The point is to be ready for it.

## What this gate does not do

```text
does not reconcile org_id and organization_id   ~70 services and 18 tables;
                                                its own gate
does not persist bindings                       no storage is live
does not rewrite Gate 51                        its derivation stays as it is,
                                                classified rather than removed
does not touch RLS                              the org-scoped boundary is the
                                                one that works
```
