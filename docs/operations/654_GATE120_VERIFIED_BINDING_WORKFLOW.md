# 654 — Gate 120C: the verified binding workflow

`src/nativeforge/services/verified_binding_workflow_service.py`

## Three contracts that had never spoken to each other

```text
Gate 109  build_binding                 what a binding may assert
Gate 111  authorize_binding_operation   who may change one
Gate 120B repository                    where one goes
```

Each was correct alone and none could complete an operation. This service is the
join.

## Authorization first, contract second, storage last

The order is the design. A workflow that built the record first and checked the
role afterwards would still refuse — but it would have constructed a
fully-formed verified binding on behalf of a caller who was never allowed to
ask. Nothing would be written, and the shape of the thing would still have been
produced for them.

Checking authorization first means an unauthorized caller never reaches the
constructor, and the refusal they get names the role rather than the record. A
test asserts `binding_contract_valid: False` for a `grants_manager` approval —
not because the record was invalid, but because it was never built.

## Inspection is not approval, and this gate does not widen it

```text
INSPECTOR_ROLES  platform_admin, tenant_admin, grants_manager, auditor
VERIFIER_ROLES   platform_admin, tenant_admin
```

`grants_manager` and `auditor` may look at a pending binding forever and may
never approve one. A test asserts the same `grants_manager` principal is
permitted on `inspect_pending` and refused on `approve_pending` — one role,
two answers, which is the whole point of having two sets.

A second test pins both frozensets literally, so a later gate that quietly adds
a verifier role fails rather than passing silently.

## Five operations, mapped onto Gate 111's rather than restated

```text
inspect_pending          -> inspect_pending_binding
approve_pending          -> approve_pending_binding
create_verified_binding  -> create_verified_binding
revoke_binding           -> revoke_binding
resolve_conflict         -> resolve_conflict
```

A workflow name with no authorization operation behind it would be an operation
nobody could refuse, so the mapping is explicit and an invariant checks it.

## A demo fixture success is not a production success

The workflow completes end-to-end under a demo principal against a demo binding:

```text
repository_write_performed      True    a row was written
verified_operational_binding    False   and it binds nobody
```

Separate fields because they are separate facts. A fixture that inserted
successfully has proven the code path works; it has not produced a binding
anybody may act on.

## A production verified binding is unconstructible today

`verified_by_identity_id` references `nf_identities` — a **verified OIDC
subject**. Gate 120A measured eleven of sixteen activation gates unsatisfied, so
no OIDC subject can be verified, so no genuine verifier identity exists to name.

The workflow therefore refuses to write one at all:

```text
production_verified_binding_requires_live_customer_auth
```

That refusal was added during the gate. Without it the workflow would insert a
`verified_binding` row whenever authorization and the contract passed — a row
sitting in a table asserting that somebody verified something, while nobody
could have. Demo fixtures, revocations and conflicts are unaffected, because
none of them asserts a verification.

## The permitted branch is reachable, and injecting it proves nothing about reality

`customer_auth_live` and `login_live` are parameters. Supplied as `True`, the
workflow reaches `verified_operational_binding: True` with no blocked reasons —
which is what makes every refusal above it falsifiable rather than a constant.

Gates 117, 118 and 119 each shipped a conjunct whose permitted branch was
unreachable and had to go back and fix it. This one is injectable from the
start.

Injecting them does not make them true. When they are not supplied the real
activation gate is measured, and it reports false.

## Nothing here writes to the application database

The repository defaults to contract mode; a connection reaches it only from a
test or a fixture holding an isolated in-memory database of its own.

```text
production verified bindings created   0
real customer rows written             0
rows in the application database       0
provider contacted                     no
```
