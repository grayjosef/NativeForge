# 411 — Gate 71: Route wiring status

Status document. Deliberately blunt, because the honest answer is a number.

```text
Live routes wired: 0
Dry-run capability evaluation available: yes (adapter-level)
Reason: no route carries a verified actor identity
```

## Why zero

Every read route resolves its organization from the `X-NF-Org-Id` header. No
route resolves an actor. `enforce_capability` requires `role_known` and
`membership_active`, both of which are `unknown` without a membership store, so
live enforcement would deny 100% of requests — including the public demo, which
is a hard rule.

The alternative — deriving a role from a client header — is the vulnerability
this campaign exists to prevent. Full survey in doc 409.

## Per-family status

| Family | Reads | Tenant guard | Live capability | Status |
| --- | --- | --- | --- | --- |
| opportunity_discovery | 31×2 | yes | no | blocked: no verified actor |
| source_ingestion | 5×2 | yes | no | blocked: no verified actor |
| pursuit | 5×2 | yes | no | blocked: no verified actor |
| trust | 4×2 | yes | no | blocked: no verified actor |
| operator_workbench_advisory | 4×2 | yes | no | blocked: no verified actor |
| pursuit_brief | 2×2 | yes | no | blocked: no verified actor |
| grant_spark | 2×2 | yes | no | blocked: no verified actor |
| nofo_extraction | 2×2 | yes | no | blocked: no verified actor |
| tribal_profile | 2×2 | yes | no | blocked: no verified actor |
| form_package | 1×2 | yes | no | blocked: no verified actor |
| spark_scoring | 1×2 | yes | no | blocked: no verified actor |
| activation | 1×2 | yes | no | blocked: no verified actor |
| sprint0 | 1–2×2 | yes | no | blocked: no verified actor |
| isolation_routes | 2 | yes | no | **do-not-wire** — exist to prove NF-001 isolation; a second guard would change what they prove |
| health | 1 | n/a | n/a | **do-not-wire** — unauthenticated by design |

## What is enforced on these routes today

Not nothing:

- **Tenant isolation** — Gate 58's guard on all 205 org-scoped handlers.
- **Postgres RLS** — `apply_org_rls_gucs` sets the scoping GUCs per request;
  Gate 62 proved the policies execute and Gate 64 made that proof repeatable.
- **Org type** — read from the persisted `organizations` row, not the client.
- **Role assertion rejection** — `reject_role_assertion_headers` exists and
  refuses `X-NF-Role` / `X-NF-Roles` / `X-NF-Capability`.

What is *not* enforced is role/capability, because there is no trustworthy role.

## What the dry-run layer gives you

`evaluate_read_capability` computes the decision a live route would reach and
returns it without changing any response. Useful for two things:

1. Proving the enforcement logic is correct before it can break anything.
2. Making the wiring change small later — one call per route instead of a
   redesign.

Denial events route through the Gate 68A sink in modeled mode, so they are
accounted rather than dropped.

## Drift protection

`test_the_guard_is_attached_to_no_route` scans `src/nativeforge/api/*.py` for
imports of `capability_guard`. If anyone wires it, that test fails with a message
telling them to update this document and add route-level tests.

That is the mechanism that keeps this file from becoming a lie. It has one
limitation worth stating: it detects an *import*, so a route wired through some
other indirection would evade it.

## Wiring checklist for later

When Gate 69/70 land:

1. Add `identity_dependency` to the route's dependency list.
2. Resolve `(issuer, subject)` → membership → trusted role via
   `PostgresMembershipDirectory`.
3. Call `require_read_capability(capability=..., organization_id=...,
   identity=..., trusted_role=..., membership_state=...)`.
4. Start with **one** `real`-plane read route, not all 124.
5. Confirm the demo plane still works — the demo has no customer identity and
   must not begin 403-ing.
6. Update this document and add route-level tests.

Step 5 is the one most likely to be missed. The demo is the thing being sold; a
correct-but-total lockout is still an outage.
