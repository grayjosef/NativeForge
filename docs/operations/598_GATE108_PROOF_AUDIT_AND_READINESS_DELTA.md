# 598 — Gate 108F/G: proof, audit and readiness delta

`src/nativeforge/services/award_requirement_proof_audit_service.py`
`src/nativeforge/services/awarded_grants_requirements_readiness_service.py`

## Proof of submission is never fabricated

The only things that can produce a proof reference are a caller handing one over
or a demo fixture that says so on its face. There is no code path that generates
a plausible-looking receipt.

That matters more than it sounds. A compliance system that can invent proof is a
system whose proof means nothing — and the one time it would be discovered is an
audit, which is the worst possible time.

```text
proof_ref supplied by a caller     recorded as given
proof_ref labelled demo_fixture    recorded, and labelled everywhere it appears
no proof_ref                       proof_missing, never a placeholder
```

Marking something submitted without a receipt is allowed — a tenant may have
filed and not yet attached it — but it is reported as `proof_missing` and carries
a blocked reason. An invariant fails a result claiming proof it does not have,
and the mutation reporting missing proof as attached is caught.

## The demo proof carries its label

`demo-proof-0001` exists in the fixture set and is labelled `demo_fixture` on the
event, in the artifact, and in the audit trail count. An invariant fails a demo
proof that dropped its label.

## Nothing is deleted on a status change

Rejecting a report does not remove the proof it was submitted. Waiving a
requirement does not remove its history.

```text
proof_preserved            true
source_evidence_preserved  true
proof_deleted              false
audit_record_deleted       false
external_storage_contacted false
```

Every action appends; nothing overwrites. `proof_ref_history` carries prior
references forward through a rejection. This follows the rule Gate 104's
suppression contract holds: a record that can erase its own history is
indistinguishable from data loss.

No external upload or storage integration was added. `external_storage_contacted`
is a constant `False`.

## Audit events are reproducible from their own contents

`audit_event_id` is derived from tenant, award, requirement, action and time, so
the trail can be re-derived rather than depending on a counter somebody could
reset. An invariant recomputes it.

## Readiness delta

```text
ready_for_demo_contract                true
ready_for_operational_awarded_tracking false
```

Two questions with two answers. Contracts and labelled fixtures can be
demonstrated. An operational compliance tracker is a promise that a missed
deadline will be caught, and nothing here can make that promise.

Four components are missing, each **detected** rather than declared:

```text
ui_available                 looked for in frontend/src; no awarded surface
customer_persistence_live    no awarded-grant repository exists
document_storage_live        no award document store exists
requirement_extraction_live  no extractor reads award packages
```

The UI detector is tested both ways — it finds a surface in a temp tree that has
one, and reports absence otherwise — so `ui_available: False` means looked-for-
and-absent rather than never-checked.

`requirement_extraction_live` deliberately does **not** count the existing notice
extractor. Reading a NOFO produces a projected burden, which this gate spent its
length insisting is not an active obligation. A mutation pointing the detector at
the notice extractor is caught.

## What remains false

```text
operational awarded tracking  false
customer persistence          false
document storage              false
requirement extraction live   false
awarded grants UI             false
live source collection        false
source monitoring             false
source coverage               false
customer auth                 false
email delivery                false
production rollout            false
controlled customer pilot     false
```

No live fetch occurred in this gate. No collector ran, no URL was requested, no
scraper was activated, and no external storage was contacted.

## Next required actions, in order

1. **Reconcile `tenant_id` and `customer_org_id`** — two identity spaces meet on
   the awarded record and no bridge exists. Everything below inherits whichever
   answer this gets.
2. **Persist awarded records and requirements** — nothing survives a request, so
   a compliance calendar cannot be re-read after a missed deadline.
3. **Build the Awarded Grants surface** — the workspace is mandatory in the
   tenant beta contract and no UI exists for it.
4. **Attach document storage under the existing gates** — award packages have to
   live somewhere before requirements can be extracted from them.
5. **Wire requirement extraction to award documents** — extraction exists for
   notices; award packages are a different corpus and nothing reads them.
