# 360 — Gate 51: Tenant isolation + organization seat model

Status: contracts implemented and tested. **Not** wired to production storage.
Service: `src/nativeforge/services/org_tenant_seat_model_service.py`
Tests: `tests/test_tenant_authority_discovery_gate51_57.py`

## Product rule

One organization = one tenant. Default seat cap = **5**. No customer may see
another organization's workspace, opportunities, evidence, feedback, documents,
exports, drafts, or audit events.

## What this gate does and does not do

It adds the organization seat / membership / invite model as **pure contracts**
evaluated from caller-supplied state. It does not add a database table, an API
route, or a login. Production storage, customer persistence and customer login
all remain **not live**, and every record this module emits carries
`production_storage_claimed=false`, `customer_persistence_claimed=false` and
`login_live_claimed=false` so that stays machine-checkable rather than
remembered.

It deliberately **composes with** the existing enforcement primitives rather
than replacing them:

- `tenant_boundary_enforcement_service` (Block 31) still makes the same-org
  decision. `evaluate_tenant_scoped_access` delegates to it, so there is one
  enforcement rule rather than two that can drift apart.
- `rbac_policy_contract_service` (Block 35) keeps its older role vocabulary for
  the surfaces already pinned to it.

## Roles

Seat-consuming customer roles: `org_owner`, `org_admin`,
`authorized_representative`, `grant_lead`, `reviewer`, `viewer`.

Internal: `operator_internal` — support/review only. It **does not consume a
seat** and **never implies customer authority**. Both facts are asserted in
tests, because the failure mode (a support account quietly counting as an
organization representative) is invisible until the moment it matters.

## Seat rules

| Rule | Behaviour |
| --- | --- |
| Default cap | 5 |
| 6th seat | blocked — `invite_state=blocked_seat_limit` |
| Override | requires explicit `override_approved_by`; lands in `pending_override_approval` |
| Override audit | `seat_limit_override_requested` + `seat_limit_override_approved` |
| Unknown role | denied |
| `operator_internal` | allowed, consumes no seat, no authority |

## Isolation rules

Deny by default, org-scoped by default. A cross-org attempt emits **two** audit
events — `cross_org_access_attempt` and `tenant_access_denied` — so both the
attempt and the denial are visible in the record.

`TENANT_SCOPED_OBJECTS` extends the Block 31 list with the Gate 54/55 discovery
objects (`source_candidate_note`, `discovery_shortlist`) so new surfaces are
org-scoped from the start rather than retrofitted later.

## Proven by test

- default cap is 5
- sixth seat invite blocked by default
- override requires approval and is audited
- `operator_internal` consumes no seat and carries no authority
- cross-org workspace / evidence / feedback access denied and audited
- same-org access allowed with no denial events
- no production storage / persistence / login-live claim

## Not done in this gate

Persistence, API-layer enforcement, and real login. Those are production gates
and remain NO_GO. The contracts have to be right first; wiring them to storage
before a storage approval and a pen test would be the actual risk.
