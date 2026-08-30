# 652 — Gate 120A: identity binding repository survey

Read before implementing. Every answer below was measured, not recalled.

## The twelve questions

```text
1  binding table schema and constraints        16 columns, 4 CHECKs, RLS on
2  binding repository exists?                  no
3  binding API route exists?                   no
4  binder authorization wired to storage?      no - it decides, nothing writes
5  customer auth can produce a real verifier?  no - 11 of 16 gates unsatisfied
6  demo/test repository can insert safely?     yes, against an isolated database
7  RLS applies to binding reads/writes?        yes, org + demo, both directions
8  rows creatable without verified_by?         yes for pending/demo; no for
                                               verified_binding - a CHECK refuses
9  revocation path exists?                     in the contract, not in a database
10 audit/proof fields exist?                   all nine present
11 migration head remains 0030?                yes - this gate adds none
12 persistence readiness should change?        yes, one lane, and only one field
```

## 1. The table

`nf_tenant_customer_org_bindings`, migration 0029, 16 columns:

```text
id  organization_id  tenant_id  customer_org_id
binding_status  binding_source  binding_confidence
verified_by_identity_id  verified_at
revoked_at  revoked_by_identity_id
is_demo  human_review_required  blocked_reasons
created_at  updated_at
```

Four CHECK constraints, and two of them are the interesting ones:

```text
ck_nf_binding_status                  status in Gate 109's seven
ck_nf_binding_source                  source in Gate 109's six
ck_nf_binding_verified_needs_verifier a verified_binding must name its
                                      verifier AND when
ck_nf_binding_demo_has_no_verifier    a demo_fixture must name neither
```

The last two are a matched pair. A verified binding without a verifier is an
assertion wearing the word "verified"; a demo binding *with* one is a fixture
impersonating production verification. The database refuses both.

Two indexes:

```text
uq_nf_binding_active     unique (organization_id, tenant_id, customer_org_id)
                         WHERE revoked_at IS NULL
ix_nf_binding_organization
```

The partial unique index is the revocation design: one live binding per
organization/label pair, and a revoked row stays for the audit trail without
blocking a replacement.

Foreign keys point at `organizations` and `nf_identities` only. `tenant_id` and
`customer_org_id` are `text` with no foreign key, deliberately — Gate 113's
docstring is explicit that a label with a foreign key becomes an identity space
by accident, which is the whole problem Gates 109–112 exist to prevent.

## 2. No repository, and seven services that talk about one

```text
repositories/                       18 modules, none binding-related
services/*binding*                  7 modules
services naming the table           7, all of them contracts or readiness
```

The seven binding services decide, classify, summarise, and report. Not one of
them opens a database session, holds a connection, or issues a statement. The
word "store" in `tenant_customer_org_binding_store_service` names a *contract
for* a store, not a store.

`build_binding_record` produces a row-shaped dict and a `write_allowed`
boolean. Nothing consumes that boolean.

That is the gap: `write_allowed: True` has never been acted on, so the entire
path from "this row is permitted" to "this row exists" is untested.

## 3. No API route

28 API modules. The only near-match is `request_identity.py`, which is Gate
54's request-scoped identity resolution and is unrelated to bindings.

## 4. Binder authorization decides and stores nothing

`verified_binder_authorization_service` (Gate 111):

```text
BINDING_OPERATIONS   create_verified_binding, approve_pending_binding,
                     revoke_binding, resolve_conflict,
                     inspect_pending_binding, unknown
VERIFYING_OPERATIONS the first four
INSPECTION_OPERATIONS inspect_pending_binding
VERIFIER_ROLES       platform_admin, tenant_admin
INSPECTOR_ROLES      platform_admin, tenant_admin, grants_manager, auditor
```

`grants_manager` and `auditor` can inspect and can never verify. That
separation is already correct and this gate must not widen it.

The module mentions no table, no `Session`, no connection. It is a pure
decision, and nothing routes its answer to a write.

## 5. No real verifier can exist today

```text
required activation gates   16
missing                     11
customer_auth_live          false
login_live                  false
```

Missing: `provider_configured, secret_present, issuer_configured,
issuer_jwks_validated, audience_configured, callback_session_validated,
invite_binding_passed, org_binding_passed, role_mapping_passed,
dev_header_disabled_for_production, session_signing_key_ready`.

`verified_by_identity_id` references `nf_identities(id)` — a *verified OIDC
subject*. No OIDC subject can be verified, so no genuine verifier identity
exists to name. **A production verified binding is not merely unauthorized
today; it is unconstructible.**

That is the fact the whole gate has to respect. The repository can be built,
tested and proven correct without a single production verified row, and this
gate creates none.

## 6. A demo repository can insert safely, against its own database

Gate 119C established the pattern and it applies unchanged: an in-memory SQLite
created inside the fixture or test, the table built from the Core definition,
and disposed at the end. It is a real INSERT against a real table with real
constraints — which is the only way to prove that the CHECK on
`verified_binding` actually fires.

Nothing touches the application's database. `rows written in the application
database: 0` stays true.

**Constraint carried forward from Gate 119C's defect:** the Core `sa.Table`
must restate the migration's constraints. A Core table that declares only
columns produces a *weaker* schema than production, and a test against it
passes on writes the real database refuses.

## 7. RLS applies, in both directions

```sql
organization_id = current_setting('app.current_org_id', true)::uuid
AND is_demo = current_setting('app.current_org_is_demo', true)::boolean
```

`USING` and `WITH CHECK`, the same predicate the other eighteen policied tables
carry. So reads are org-scoped and writes cannot insert a row into another
organization's scope.

The repository must therefore never accept `tenant_id` or `customer_org_id` as
a selector on its own. A read anchored on a label is a read the policy cannot
scope, and Gate 113's `read_bindings_for_organization` already models the right
shape: anchor on `organization_id`, let labels narrow.

## 8. Rows without a verifier: permitted, and only for the right statuses

```text
pending_review   no verifier required
demo_fixture     verifier forbidden
verified_binding verifier and verified_at both required, enforced by CHECK
```

So the repository does not need to invent this rule — it needs to not
contradict it, and to fail loudly rather than silently when it would.

## 9. Revocation exists in the contract, not in a database

`revoke_binding` in the store service returns a modified dict with
`binding_status: revoked`, `rows_deleted: 0` and `history_preserved: True`.

It has never been applied to a row, because there are no rows. The repository
must make revocation an UPDATE that sets `revoked_at`, never a DELETE, and the
partial unique index is what makes that safe.

## 10. Audit fields: all nine present

```text
verified_by_identity_id  verified_at
revoked_by_identity_id   revoked_at
human_review_required    blocked_reasons
created_at  updated_at  is_demo
```

Nothing needs adding. `blocked_reasons` is `JSON not null default '[]'`, so a
refused row can carry its own reasons if one is ever written for audit.

## 11. Migration head stays 0030

This gate adds no migration. The table it needs was built by Gate 113 and has
been empty since.

## 12. Readiness should change, and by exactly one field

Today:

```text
identity_binding_persistence   schema=True repo=False rls=True operational=False
customer_persistence_live      False
spine ready_to_build_next      None
spine next_gate_recommendation customer_authentication
```

`repository_available` is measured by probing for a **file**:

```python
repository_available = (repos / f"{CAPABILITY_REPOSITORIES[name]}.py").is_file()
# CAPABILITY_REPOSITORIES["identity_binding_persistence"] = "identity_binding"
```

That probe looks in `src/nativeforge/repositories/` for `identity_binding.py`.
A repository built at `src/nativeforge/services/..._repository_service.py`
would be invisible to it.

**This is a declared-versus-derived defect in waiting.** The detector measures a
filename convention rather than whether anything can actually address the table.
Left alone, it would report `repository_available: False` for a working
repository — or, patched carelessly, would flip all eight lanes at once.

The fix: detect by import, per capability, with only `identity_binding_persistence`
pointed at the new module. The other seven keep their `repositories/` paths and
stay false, because they are still false.

What must **not** change: `operational` for this lane requires
`customer_auth_live`, which is false. A repository existing moves
`repository_available` and `write_path_available`. It does not move
`operational`, `customer_persistence_live`, or `verified_operational_binding`.

## Gate 120E: the API route decision, made here

**Skip it.** Reasons, in order of weight:

```text
1  a read route needs a session to scope by. /current-user is the only route
   that enforces, and it 401s for everybody, so an authenticated binding read
   is unreachable and its permitted branch untestable.

2  the table is empty. A route returning `no_binding` for every caller
   forever is a route whose only behaviour is its refusal.

3  a route is a surface. Adding one before a session can reach it means the
   first thing to exercise it will be a real browser with a real cookie -
   which is the worst place to discover a scoping mistake.
```

The repository and workflow are the safer boundary and are testable today. This
is recorded in doc 655 rather than left as an omission.

## Implementation constraints carried out of this survey

```text
1  organization_id is the only anchor; labels never select alone
2  the Core sa.Table must restate 0029's constraints (Gate 119C's defect)
3  revocation is an UPDATE, never a DELETE
4  a verified binding needs a verifier identity AND a timestamp
5  a demo fixture binding may carry neither
6  repository_available must be derived from what can address the table,
   not from a filename, and only the lane actually built may move
7  operational verified binding stays false while customer_auth_live is false
8  bridge Gate 109's vocabularies and Gate 111's roles - import, never restate
9  every new conjunct both derived and injectable, or its branch is unreachable
10 no production verified row, in any database, at any point
```
