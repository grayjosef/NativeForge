# 731 — Gate 139: awarded readiness delta

## The delta

```text
                                    before 139    after 139
awarded_operational_tracking          false         TRUE
  scope                               —             controlled_dev_demo
  derived by                          nothing       a readiness service
  stated as                           a constant    a measurement
  post-award route modules            0             4
  post-award route operations         0             17

route-live lanes                      0             4
repository-live lanes                 4             4
end-to-end post-award smoke           none          passes

customer_persistence_live             true          true
customer_auth_live                    false         false
login_live                            true          true
verified_operational_binding          false         false
object_store_configured               false         false
alembic head                          0039          0039  (no migration)
```

## `awarded_operational_tracking` was a constant in nine places

```text
dev_header_kill_artifact_service.py:310        False
login_live_dev_header_kill_artifact_service    False
first_dev_org_binding_artifact_service.py:326  False
customer_auth_activation_gate_service          False   (Gate 138F)
award_requirement_proof_audit_persistence_…    False
```

All literals. All correct at the time, and all of which would have kept saying
`False` after the thing became real — the family Gate 114A removed for
`customer_persistence_live`. It is derived now, from route detection plus a
route smoke plus Gate 138's repository proof, and the negative branches are
reachable (a `repo_root` a route module does not live under reports it absent).

## The evidence

Measured by `scripts/verify_nativeforge_awarded_operational_tracking.sh`,
against the **running server over real HTTP**:

```text
RESULT=PASS
awarded_operational_tracking=true
scope=controlled_dev_demo
route_live_lanes=award_requirements awarded_grants document_metadata proof_audit
customer_auth_live=False
production_awarded_tracking=false
object_store_configured=false
document_body_storage_ready=false
```

The sequence: create an award, attach a requirement, attach a proof event,
attach a document reference, read each back anchored on `organization_id`, read
each as another organization and get nothing, archive all four in reverse
dependency order. Rows left live afterwards: **0**.

The session is real — minted through `customer_session_format_service` for the
demo organization's existing owner identity, read out of `nf_org_memberships`.
No fake user, no fake session, no fake membership.

## Which lanes are route-live

All four:

```text
awarded_grants       api/awarded_grants_routes.py
award_requirements   api/award_requirements_routes.py
proof_audit          api/award_requirement_proof_routes.py
document_metadata    api/award_document_routes.py
```

Each detected by **parsing** for `Depends(require_demo_org_session)` rather than
by substring — Gate 133 found `if TABLE_NAME in body` counting a docstring
mention as a use, and this campaign has now found ten of those.

## Which remain route-missing

None of the four. `tenant_profile_persistence` was already route-live from Gate
134's conversion. The three lanes with no table at all —
`tenant_digest_persistence`, `source_watchlist_persistence`,
`beta_onboarding_persistence` — remain absent and are not this gate's.

## Document body storage remains blocked

```text
object_store_configured        false
document_body_storage_ready    false
object store contacted         no
document bodies written        0
```

And metadata readiness deliberately does **not** require a store. Requiring one
would make the lane permanently unreachable — the unsatisfiable-conjunct shape
Gate 134F removed — so the two are reported separately and body readiness stays
false on its own.

## Did `customer_auth_live` change?

No. This gate touched no auth gate. `awarded_operational_tracking` is
controlled dev/demo, every row is fixture-labelled, and
`production_write = not demo_fixture` in every post-award repository — so no
production gate was consulted, let alone satisfied.

`production_awarded_tracking` is reported `False` with no branch that sets it.

## Was real customer data written? Was the real org touched?

No, and no. Every row carries `fact_status = demo_fixture` and `is_demo = true`,
every row is archived, and no route module mentions the real organization or a
real-organization session dependency.

## Four defects found while building this

**1. Pydantic silently dropped `is_demo: false`.** A caller could try to relabel
a fixture write as production and the field vanished before the refusal saw it.
Caught by this gate's own smoke invariant (`caller_relabel_refused: False`).
The bodies allow extras now, and `declared_fields` keeps strays out of the
repositories.

**2. The supersede route passed the caller's `event_type`** into a function that
sets it itself — `TypeError: got multiple values`. The repository names it
because a supersede is a supersede.

**3. A schema contradiction in `nf_award_requirement_proof_events`.**
`supersedes_event_id` is `ON DELETE SET NULL` and the CHECK requires it non-null
for a `proof_superseded` row, so deleting a superseded event is impossible.
Never met before because nothing had exercised supersede. Recorded rather than
fixed — proof events are append-only and there is no DELETE path at all. Full
account in `730`.

**4. The artifact rebound `engine` and not `SessionLocal`.** `get_db_session`
yields `SessionLocal()`, bound to an engine at import time, so the routes read
whichever database was current when the module first loaded — inside the suite,
conftest's, which had no membership for the artifact's organization. Every
create returned 403 while the setup had written to a different file entirely.
Replaced with FastAPI's `dependency_overrides`, which is the supported seam and
reaches across no modules.

## Next

```text
customer_auth_live true          Gate 136's second-person invite event
verified_operational_binding     Gate 137's two-part owner decision
object_store_configured          document BODIES — Gate 141's subject
```

None of the three is this gate's, and none of them blocks controlled dev/demo
post-award tracking, which is live.
