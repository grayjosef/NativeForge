# 676 — Gate 126A: proof/audit persistence survey

Read before implementing. Every answer below was measured, not recalled.

## The eleven questions

```text
1  proof/audit service contract     329 lines, 4 public functions, no storage
2  proof/audit table/model/repo     none of the three
3  document storage                 no. award_document_store_service is absent
4  append-only?                     yes for the event, with two narrow updates
5  status derived or stored         stored per event, derived per requirement
6  reference nf_award_requirements  yes, FK, ON DELETE CASCADE
7  organization_id on the event     yes, and this is not redundant
8  migration required               yes - 0034
9  API route exists                 no
10 repository-backed without auth   yes, the Gate 120/123/124/125 shape
11 readiness change                 yes, and Gate 125 left a trap for it
```

## The defect this survey found: I planted it last gate

Gate 125 added a measured probe so proof/audit persistence would move on its own
the day it was built:

```python
def _proof_audit_persistence_available() -> bool:
    return _module_importable(
        "nativeforge.services.award_requirement_proof_repository_service"
    )
```

Gate 126C asks for a module called
`award_requirement_proof_audit_repository_service`.

```text
probe expects   nativeforge.services.award_requirement_proof_repository_service
gate 126C asks  nativeforge.services.award_requirement_proof_audit_repository_service
same name?      NO
```

Building the repository at the name the brief specifies leaves
`proof_audit_persistence_available` **false forever**, and the readiness report
would keep saying the store does not exist while it sat in the same directory.

This is precisely the family Gate 124A found — `awarded_grant_record_contract_service`
against `awarded_grant_record_service`, `award_requirements_model_service`
against `award_requirement_model_service` — a detector reporting on a *name*
rather than a capability. Gate 124 added a test asserting every module in
`CAPABILITY_CONTRACT_MODULES` imports, so a third typo could not hide there.

`CAPABILITY_REPOSITORY_MODULES` has no such test. That is the hole this one came
through, and Gate 126E closes it.

**Decision.** The module is built at the name Gate 126C specifies. Readiness
stops naming a module at all and asks the capability model, the way
`_awarded_grants_storage_facts` already does — one place names the module, and a
new test asserts every name in that map imports.

## 1. The contract, and the vocabulary it does not have

```text
award_requirement_proof_audit_service      329 lines
  build_audit_event_id      sha256 over the event's own facts
  record_proof_action       one action -> one event
  build_audit_trail         a fold over events; takes only `events`
  proof_audit_invariant_failures
```

Every result already carries the constants this campaign expects:

```text
proof_deleted              False
audit_record_deleted       False
proof_preserved            True
source_evidence_preserved  True
external_storage_contacted False
fabricated                 False
```

The vocabulary is where it gets interesting:

```text
PROOF_ACTIONS            attach_proof, mark_submitted, mark_accepted,
                         mark_rejected, mark_waived, unknown
PROOF_EXPECTING_ACTIONS  mark_submitted, mark_accepted
DEMO_PROOF_LABEL         "demo_fixture"
```

Six verbs. The gate brief names eight event types, and **four of them do not
exist in Gate 108's vocabulary**:

```text
brief                        Gate 108 action        verdict
proof requested              -                      NEW
proof uploaded / attached    attach_proof           bridged
proof submitted              mark_submitted         bridged
proof accepted               mark_accepted          bridged
proof rejected               mark_rejected          bridged
proof needs review           -                      NEW
proof superseded             -                      NEW
audit note added             -                      NEW
(none)                       mark_waived            bridged
```

So this gate **extends** Gate 108's vocabulary rather than bridging it whole,
and says so rather than quietly forking. A test asserts every value in
`PROOF_ACTIONS` maps to an event type, so the extension cannot drift into a
replacement.

`event_status` is a different question — what the proof *is* now — and that one
is bridged unchanged from `PROOF_STATUSES` in `award_requirement_model_service`:

```text
not_submitted, proof_missing, proof_attached,
proof_accepted, proof_rejected, unknown
```

## 2–3. No tables, and the migrations confirm it

```text
tables in migrations                33
matching proof / audit / document   nf_audit_events (0002)
                                    nf_authority_proof_records (0026)
                                    nf_pursuit_calendar_events (0007)
```

None is an award requirement proof trail. `nf_audit_events` is Sprint 0's
generic demo audit table (`action`, `payload`, `actor_id`).
`nf_authority_proof_records` is Gate 52's authority lifecycle — a different
proof entirely, about who may act for an organization.
`nf_pursuit_calendar_events` is pursuit-side.

```text
nf_award_requirement_proof_events   does not exist
nf_award_documents                  does not exist
nf_document_library                 does not exist
services/award_document_store_service  absent
api/award_requirement_proof_events     absent
```

## 4. Append-first, with exactly two updates

An audit trail that can be rewritten is not one. But two columns must change
after insert, and both are one-way:

```text
superseded_at    set when a later event replaces this one. Never cleared.
archived_at      set when the row leaves the active view. Never cleared.
```

Everything else is written once. There is no delete path, `rows_deleted` is a
constant `0`, and superseding writes a *new* row that points back — the prior
event keeps its own reference, its own timestamps and its own actor.

That is the whole reason this is a separate table from `nf_award_requirements`:
Gate 125A recorded it, and it holds. One requirement submitted, rejected,
resubmitted and accepted is four rows with four actors and four timestamps.
Putting that on the requirement row would mean overwriting the history, which is
the one thing an audit trail may never do.

## 5. Status is stored per event, and derived per requirement

```text
event_status              on the event. What this event made true.
requirement.proof_status  on the requirement. What is true now.
```

The event stores its own status because an audit trail records what was believed
at the time — a rejection that was later overturned is still a rejection that
happened. The requirement's current status is a *derivation over the events*,
and this gate exposes it as `derive_current_proof_status` rather than writing it
back onto the requirement row.

Not written back, deliberately: two writers on one column is how the two come to
disagree, and the requirement's `proof_status` already has Gate 125's CHECK
constraints behind it. A later gate can reconcile them under one writer; this
gate reads.

## 6–7. Three identifiers, and only one is authority

```text
organization_id       UUID, FK organizations, the RLS predicate's left side
award_requirement_id  UUID, FK nf_award_requirements, a row relationship
awarded_grant_id      UUID, FK nf_awarded_grants, context only, nullable
```

Gate 125 established the shape: the policy reads `organization_id`, so a table
without that column cannot be scoped at all, and reaching the organization
through two joins would make this table's policy depend on two other tables'
policies. Both `award_requirement_id` and `awarded_grant_id` join
`FORBIDDEN_ANCHOR_NAMES`.

`awarded_grant_id` is nullable and denormalised on purpose — it is the award a
proof belongs to, carried so a portfolio view need not join through the
requirement, and it is context rather than a second relationship. An invariant
refuses it substituting for the anchor.

## 8. Migration 0034

```text
0034_nf_award_requirement_proof_events    head 0033 -> 0034
```

## 9. No API route

Zero route decorators matching awards, requirements or proof. **Skip it**, for
the Gate 120/122/123/124/125 reasons plus one specific to this gate:

```text
1  a read route needs a session to scope by, and /current-user 401s for
   everybody, so the authenticated branch is unreachable and untestable
2  the table will hold zero rows, so the route's only behaviour is
   `no_proof_events`
3  a proof event is the record a funder's auditor reads. The first surface
   that serves one is the surface that will be believed about whether a Tribe
   filed something, and an empty table returning `no_proof_events` is
   indistinguishable from a Tribe that filed nothing. Serving that before a
   real tenant can be authenticated builds the failure mode first
```

## 10–11. What this gate moves, and the two stale claims it creates

```text
customer_auth_live                     false
verified_operational_binding           false
customer_persistence_live              false
document_storage_live                  false
ready_for_operational_awarded_tracking false
capability lanes                       8, none with `proof` in the name
guard operations                       9, none with `proof` in the name
```

**A ninth capability lane.** A proof event is customer data, owned by an
organization, RLS-scoped, with its own table and repository. That is what a
persistence lane *is*, so modelling it as a bare readiness boolean would hide a
real lane behind a flag — the inverse of the defect above. Measured cost of the
ninth lane: exactly one position assertion
(`beta_onboarding_persistence position == 8`), which should have been derived
anyway since the claim it is reaching for is "onboarding is last".

**Two claims Gate 125 will be left telling.** Both are mine, both from last
gate, and both would go stale silently rather than loudly:

```text
1  test_gate125 asserts readiness["proof_audit_persistence_available"] is False.
   Gate 126 makes it true. The test must move, and should move to a derived
   form so it does not need moving again.

2  award_requirements_persistence_artifact_service freezes
   proof_audit_persistence_available: False in FIXED_CLAIMS, and lists it in
   FORBIDDEN_CAPABILITY_FLAGS - a scan that refuses any payload claiming it.

   So once the store exists, the Gate 125 artifacts either keep saying `false`
   (a stale claim its own invariants would not catch, because they compare the
   declaration against the same frozen constant) or refuse to write at all.
```

The second is the more dangerous shape: a check that agrees with itself. The
repair is to measure rather than freeze — the capability scan refuses a payload
claiming a capability that is **not actually available**, which self-corrects as
capabilities land instead of needing an edit per gate.

## Implementation constraints carried out of this survey

```text
1  migration 0034 creates nf_award_requirement_proof_events
2  organization_id anchors; award_requirement_id and awarded_grant_id are both
   refused as anchors, by name; tenant_id, customer_org_id and
   organization_profile_id likewise
3  event_type extends Gate 108's PROOF_ACTIONS with four new verbs, and a test
   asserts every existing action still maps
4  event_status is bridged unchanged from PROOF_STATUSES
5  append-first: superseded_at and archived_at are the only post-insert writes,
   both one-way. No DELETE path
6  a superseding event is a NEW row pointing back; the prior row is retained
7  a rejected event is retained, and rejection never removes the proof reference
8  proof_document_ref does not imply a document store, and
   proof_document_storage_available is false and injectable
9  submitted does not imply accepted; accepted requires a submission AND a
   reference; each is a separate named refusal
10 the requirement's current proof status is DERIVED over events, never written
   back onto the requirement row
11 the Core sa.Table restates every CHECK constraint (Gate 119C's defect)
12 a ninth capability lane, a ninth guard operation, a ninth spine entry
13 readiness asks the capability model, not a module name; a new test asserts
   every module in CAPABILITY_REPOSITORY_MODULES imports
14 Gate 125's capability scan measures rather than freezes
15 every new conjunct both derived and injectable
16 no API route; document why
```
