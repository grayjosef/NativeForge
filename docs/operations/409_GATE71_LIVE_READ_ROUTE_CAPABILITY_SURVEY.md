# 409 — Gate 71A: Live read route capability survey

## The finding, first

**No route in this application can safely carry live capability enforcement
today.** Not because the enforcement layer is missing — Gate 58 built it — but
because no route has a verified actor to enforce against.

## Route architecture

Routes are organised as **paired planes**: every family exists twice, once as
`demo_*_router` and once as `real_*_router`.

| Family | GET routes per plane |
| --- | --- |
| `opportunity_discovery_routes` | 31 |
| `source_ingestion_routes` | 5 |
| `pursuit_routes` | 5 |
| `trust_routes` | 4 |
| `operator_workbench_advisory_routes` | 4 |
| `pursuit_brief_routes` | 2 |
| `grant_spark_routes` | 2 |
| `nofo_extraction_routes` | 2 |
| `tribal_profile_routes` | 2 |
| `sprint0_routes` | 1–2 |
| `activation_routes` | 1 |
| `form_package_routes` | 1 |
| `spark_scoring_routes` | 1 |
| `isolation_routes` | 2 (`@router.get`) |

Roughly 62 GET handlers per plane, ~124 read routes total.

## Where organization context comes from

Both planes resolve `OrgContext` through the same dependency chain:

```
require_demo_org_db / require_real_org_db
  → get_org_context_with_db(db, x_nf_org_id: Header("X-NF-Org-Id"))
      → 503 unless NF_DEV_ORG_HEADERS=true
      → 400 if the header is absent
      → org_type read from the persisted organizations row
      → apply_org_rls_gucs(db, oid, ot)
```

Two things are true and worth separating:

- The org **type** (demo vs real) is read from the database, not the client. That
  is genuinely not spoofable, and `apply_org_rls_gucs` sets the RLS GUCs so
  Postgres enforces scoping. Good.
- **Which org you are** comes from `X-NF-Org-Id`, a client header, gated on
  `NF_DEV_ORG_HEADERS`. `isolation_deps.py` says so in its own docstring:
  *"Development-only dependencies... Production must replace this with JWT +
  organizations.org_type lookup."*

So the `real` plane is not customer-authenticated either. It is the same dev
header pointed at non-demo organizations.

## Where actor identity comes from

Nowhere. No route depends on `resolve_request_identity` or
`identity_dependency`. Even if one did, `resolve_request_identity` can only
return:

| State | Why it is not a customer |
| --- | --- |
| `anonymous` | no credential at all |
| `demo_operator` | Cloudflare Access proved an operator reached the edge |
| `oidc_unconfigured` | bearer supplied, no OIDC config |
| `oidc_configured_unverified` | bearer supplied, **no verifier wired** |

There is no `oidc_verified` state reachable in the running system.

## Why `enforce_capability` would deny everything

```python
def _base_denials(context, *, require_role: bool):
    ...
    if require_role:
        if not context.get("role_known"):      reasons.append("missing_or_unknown_role")
        if not context.get("membership_active"): reasons.append("membership_not_active")
```

`enforce_capability` calls this with `require_role=True`. With no membership
store, `membership_state` normalises to `unknown`, so `membership_active` is
`False` on every request. Attaching it to a live route denies 100% of traffic,
including the public demo.

## Route classification

| Family | Tenant-guarded | Identity context | Capability-ready | Verdict |
| --- | --- | --- | --- | --- |
| discovery (demo) | yes | dev header only | no | **demo-only** |
| discovery (real) | yes | dev header only | no | **blocked on live membership** |
| source_ingestion (both) | yes | dev header only | no | blocked |
| pursuit (both) | yes | dev header only | no | blocked |
| trust (both) | yes | dev header only | no | blocked |
| workbench_advisory (both) | yes | dev header only | no | blocked |
| pursuit_brief, grant_spark, nofo, profile, form_package, spark_scoring, activation | yes | dev header only | no | blocked |
| `isolation_routes` | yes | dev header only | no | **do-not-wire** — these exist to test NF-001 isolation; adding a second guard would change what they prove |
| `health.py` | n/a | none | n/a | **do-not-wire** — unauthenticated by design |

**Capability-check-ready: 0 routes. Identity-context-ready: 0 routes.**

## The rule that decides this gate

From the gate instruction:

> Do not attach checks that require trusted live membership to routes that only
> have demo/dev header context.

Every route has only demo/dev header context. So nothing gets wired.

The two available alternatives were both rejected:

1. **Attach enforcement anyway.** Denies every request including the demo,
   which breaks `/?view=sc_customer_demo` — a hard rule.
2. **Derive a role from `X-NF-Org-Id` or `X-NF-Role`.** Trusts a client header
   as membership proof. This is the precise vulnerability Gates 58–67 exist to
   prevent, and it would make every honest claim in those gates false.

## What was built instead

`src/nativeforge/api/capability_guard.py` in **dry-run** mode: it computes the
decision a live route would reach, records it, routes denial events through the
Gate 68A audit sink, and changes no response. `require_read_capability` is the
live path — implemented, tested, attached to nothing.

A test asserts no route file imports the guard, so if someone wires it, that
test fails and forces doc 411 to be updated rather than letting the docs drift.

## Capability vocabulary

The gate suggested `view_evidence`, `view_feedback`, `preview_package_export`,
`view_source_registry`. **None of those exist**, and the instruction was to use
existing vocabulary rather than invent duplicates. The Gate 57 matrix has
`view_workspace` (held by every customer role) and `view_org_audit_events` (held
by `org_owner` only). Read families map onto those two:

```text
workspace_read          → view_workspace
evidence_read           → view_workspace
feedback_read           → view_workspace
package_export_preview  → view_workspace
source_registry_read    → view_workspace
org_audit_read          → view_org_audit_events
```

A test asserts `READ_CAPABILITIES ⊆ CAPABILITIES`, so no second vocabulary can
appear without failing.

## What unblocks wiring

1. **Gate 69** — a real OIDC verifier, giving `oidc_verified` identities.
2. **Gate 70** — org and role resolved from a persisted membership directory
   instead of a header.
3. A provisioned database, so membership can be `active` rather than `unknown`.

Once those land, wiring is one line per route.
