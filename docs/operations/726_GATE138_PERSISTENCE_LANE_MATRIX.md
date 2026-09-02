# 726 — Gate 138: the persistence lane matrix

## Every lane, and what each one actually proved

```text
lane                            table                              repo  route
tenant_profile_persistence      nf_tenant_beta_profiles            LIVE  LIVE
awarded_grants_persistence      nf_awarded_grants                  LIVE  —
award_requirements_persistence  nf_award_requirements              LIVE  —
proof_audit_persistence         nf_award_requirement_proof_events  LIVE  —
document_library_persistence    nf_award_documents                 LIVE  —
identity_binding_persistence    nf_tenant_customer_org_bindings    (a)   —
tenant_digest_persistence       nf_tenant_digest_records           NO TABLE
source_watchlist_persistence    nf_source_watchlist_entries        NO TABLE
beta_onboarding_persistence     nf_beta_onboarding_records         NO TABLE
```

(a) `identity_binding_persistence` has a complete write path and is available
for a controlled dev/demo write, but it is not one of the five lanes this gate
round-tripped — Gate 137 covers that table's write path and its refusals, and
proving it twice in two shapes would let the two disagree.

## Repository-live means all four steps

```text
                                write  read-by-id  cross-org  cleanup
tenant_profile_persistence        ✓        ✓        refused      ✓
awarded_grants_persistence        ✓        ✓        refused      ✓
award_requirements_persistence    ✓        ✓        refused      ✓
proof_audit_persistence           ✓        ✓        refused      ✓
document_library_persistence      ✓        ✓        refused      ✓
```

Totals across the five: 5 written, 5 archived, **0 left live**, 0 cross-org
rows read. Plus 5 scaffolding rows written and 5 archived — four lanes hang off
an award they create themselves.

## Route-live means one

```text
tenant_profile_persistence   api/tribal_profile_routes.py
  prefix /v1/nf/demo/orgs and /v1/nf/real/orgs
  require_demo_org_session / require_real_org_session   Gate 134
  _same_org(org_id, ctx)                                path org == session org

  GET  /v1/nf/demo/orgs/{demo}/tribal-profile      401 unauthenticated
       … with a forged X-NF-Org-Id                 401
```

The other four lanes have **no routes**. That is reported, not smoothed over:
repository-live is not customer-usable, and a lane a customer cannot reach is
not a feature they have.

## What each lane writes, and what it refuses to

Every row carries:

```text
fact_status = demo_fixture
is_demo     = true
```

which is what makes `production_write` false in every repository underneath.

```text
tenant_profile        a profile, one live per organization. Upsert archives
                      the previous one - the partial unique index makes that
                      the only safe shape.
awarded_grants        an award. No upsert: a correction is a new row and the
                      mistaken one is archived, so the trail shows what was
                      believed and when.
award_requirements    a requirement. No upsert: a recurring obligation is many
                      rows, one per period.
proof_audit           an event. Append only. What was believed at the time is
                      what the row says, forever.
document_library      a REFERENCE to a document. No bytes are read, written,
                      hashed or transmitted. object_store_configured stays
                      false and no store is contacted.
```

## Cleanup, and why it is archival

No repository offers a delete, and none was added. `archive_*` is what each one
has, and that is right: these are audit surfaces where a hard delete would be
the wrong primitive to introduce for a smoke test's convenience.

So the proof leaves an archived row rather than no row — the brief's "mark it
as a test artifact" branch, chosen because it is the only one available.

Each run adds five archived fixture rows to the dev database plus five archived
scaffolding rows. They are labelled, they are in the demo organization, and
nothing reads archived rows by default.

## The three absent lanes

```text
tenant_digest_persistence     no nf_tenant_digest_records
source_watchlist_persistence  no nf_source_watchlist_entries, no contract
beta_onboarding_persistence   no nf_beta_onboarding_records, no contract
```

All three stay false, honestly, and are available for neither a production nor
a controlled dev write. A lane with no table has nothing to prove.

## Three modules the brief named that exist under other names

```text
tenant_beta_profile_repository_service      -> tenant_profile_repository_service
award_requirement_proof_repository_service  -> award_requirement_proof_audit_
                                               repository_service
award_documents_repository_service          -> award_document_store_
                                               repository_service
```

Seventh gate running with a brief naming modules by a plausible name nobody
used. Worth recording rather than silently resolving, because Gate 124A found
two *detectors* missing real services for exactly this reason — a probe on a
name rather than a capability — and the capability service now carries a map of
derived answers with that history written beside it.

## What the matrix says versus what the round trip says

```text
capability matrix          reads models, migrations, imports. Writes nothing.
                           write_path_available: 6 lanes
                           controlled_dev_persistence_available: 6 lanes
                           customer_persistence_live (production): false

activation service         writes a row and reads it back.
                           lanes round-trip proved: 5
                           customer_persistence_live (controlled): TRUE
```

The two answer different questions and are kept apart on purpose. A lane with
all five components and a broken INSERT reports `write_path_available: True`
and would fail the round trip — which is the whole reason the second surface
exists.
