# 727 — Gate 139: awarded grants operational survey

Measured before anything was implemented. HEAD `e10f32a`.

## Why `awarded_operational_tracking` is currently false

It is a **constant**, in nine places, and no service derives it.

```text
dev_header_kill_artifact_service.py:310        "awarded_operational_tracking": False
login_live_dev_header_kill_artifact_service    "awarded_operational_tracking": False
first_dev_org_binding_artifact_service.py:326  "awarded_operational_tracking": False
customer_auth_activation_gate_service          False   (added in Gate 138F)
award_requirement_proof_audit_persistence_…    "awarded_operational_tracking_ready": False
```

Every one is a literal. There is no
`awarded_operational_tracking_readiness_service`, nothing measures it, and
nothing could currently make it true.

That is the same family Gate 114A found and removed for
`customer_persistence_live` — a fact stated three ways, all constants, all
correct today and all of which would keep saying `False` after the thing became
real. This gate replaces the constant with a measurement.

## Which post-award lanes are repository-live

All four, proved in Gate 138 by a real round trip against the live dev database:

```text
awarded_grants_persistence      write ✓ read-by-id ✓ cross-org refused ✓ archive ✓
award_requirements_persistence  write ✓ read-by-id ✓ cross-org refused ✓ archive ✓
proof_audit_persistence         write ✓ read-by-id ✓ cross-org refused ✓ archive ✓
document_library_persistence    write ✓ read-by-id ✓ cross-org refused ✓ archive ✓
```

## Which are route-live

**None.**

```text
src/nativeforge/api/awarded_grants_routes.py            ABSENT
src/nativeforge/api/award_requirements_routes.py        ABSENT
src/nativeforge/api/award_requirement_proof_routes.py   ABSENT
src/nativeforge/api/award_document_routes.py            ABSENT
```

Four modules, none of them exists. Gate 138 reported this per lane rather than
averaging it, and said the honest thing: repository-live is not
customer-usable. This gate is the part that makes it usable.

The one post-award-adjacent module that *does* exist,
`tribal_profile_routes.py`, is the tenant-profile lane and is already
session-wired — it is the template, not the work.

## What the routes will be built on

```text
customer_org_context_dependency   Gate 134E
  require_demo_org_session          nf_session -> nf_org_memberships ->
                                    organizations.org_type -> OrgContext
  require_real_org_session          the same, refusing a demo organization

  401  no session cookie, or one that is forged, expired or signed elsewhere
  403  valid session, no membership / a member of B asking about A
  X-NF-Org-Id                       not a parameter on any function here

tenant_guard.guard_same_org_404     the URL's organization must match the
                                    session's. 404, so another organization's
                                    existence is not confirmed.
```

Two layers, and they answer different questions: the dependency decides which
organization the caller **is**, the guard decides whether the URL **agrees**.

## Whether the demo org can create / list / update / archive fixture rows

Yes at the repository level, proved in Gate 138. Every lane offers:

```text
prepare_*_write   decide, no connection needed
create_*          insert, if prepare permits
get_*             by id, anchored on organization_id
list_*            anchored on organization_id, labels narrow only
archive_*         the only lifecycle operation. No delete anywhere.
```

`update` is the gap. Measured, the repositories offer **no update path** for an
awarded grant's status or owner — only create and archive.

```text
awarded_grants          create, get, list, archive.        No update.
award_requirements      create, get, list, archive.        No update.
proof_audit             create, get, list, supersede, archive.
document_store          create, get, list, archive.        No update.
```

That is deliberate and documented in each one:

> "There is no upsert. An award is a discrete event: a correction is a new row
> and the mistaken one is archived with `mistaken_award`, so the audit trail
> shows what was believed and when."

> "No update of an event's own facts. What was believed at the time is what the
> row says, forever."

So the brief's "update status/owner/metadata where safe" and "update requirement
status" have **no safe repository path**, and this gate will not invent one. A
status change is a new row plus an archive of the old one — which the routes
can express as a *supersede* operation without adding an UPDATE the audit model
refuses.

`proof_audit` is the exception: it has `supersede_proof_event`, which is the
correct shape and will be exposed.

## Whether requirements attach to awarded grants

Yes. `nf_award_requirements.awarded_grant_id`, and `awarded_grant_id` is in
that repository's `FORBIDDEN_ANCHOR_NAMES` — it is a relationship, never the
authority. Same-organization attachment is what the route must enforce, since
the repository anchors on `organization_id` independently.

## Whether proof events attach to requirements

Yes, `award_requirement_id` plus `awarded_grant_id`, both in
`FORBIDDEN_ANCHOR_NAMES` for the same reason.

## Whether document metadata attaches without body storage

Yes, and this is the cleanest part of the survey.

```text
awarded_grant_id      nullable
award_requirement_id  nullable
proof_event_id        nullable
at least one required — "a document attached to nothing is a file in a drawer"

object_key IS NULL OR object_store_configured     a CHECK constraint
```

`object_store_configured` is bridged from Gate 96's `detect_body_store_mode()`,
**never accepted from a caller**, and measured now:

```text
detect_object_store_configured()  ->  False
```

So the database itself refuses an `object_key` today. Metadata-only is not a
convention this gate is choosing — it is what the schema permits.

## Whether an object store is required for metadata-only operation

**No.** A document row is a reference: `document_status = reference_recorded`,
no bytes read, written, hashed or transmitted. The route will accept no body and
will refuse one with a named blocker rather than a 500.

## The two refusals this gate must not weaken

```text
unsupported requirements       stay `unknown` or `needs_human_review`
deadlines                      never inferred from generic text
```

Both are already vocabulary in the repository:

```text
due_date_statuses     calculated, estimated, needs_human_review, unknown,
                      unsupported, verified
requirement_sources   evidence_extracted, human_entered, needs_human_review,
                      projected_from_nofo, unknown, unsupported_document_type
```

And `award_requirements_repository_service.prohibited_inferences()` already
names what may not be derived. The routes will accept a due date only when a
caller supplies one, with a `due_date_status` the caller also supplies — never
computed from a title or a description.

## What can safely become true in this gate

```text
four route modules, session-wired, 401/403/404 failing closed
awarded_operational_tracking_readiness_service   the measurement
awarded_operational_tracking = TRUE, controlled_dev_demo, if the routes
  actually work under an authenticated org context
```

And what must not move:

```text
customer_auth_live              governed by its own gates. Untouched.
verified_operational_binding    false. Untouched.
object_store_configured         false. No store contacted, no body written.
production awarded tracking     false.
customer_persistence_live       true, and must stay true.
```

## Exact blockers remaining after this gate

For **controlled dev/demo** awarded tracking: none, if the route smoke passes.

For **production** awarded tracking, three, none of them this gate's:

```text
customer_auth_live true          Gate 136's second-person invite event
verified_operational_binding     Gate 137's two-part owner decision
object_store_configured          document bodies. Gate 141's subject.
```

And one shape worth recording rather than fixing: **there is no update path**
anywhere in the post-award repositories, by design. Any product surface that
wants "change this status" gets create-plus-archive, and this gate will expose
that honestly rather than adding an UPDATE the audit model was built to refuse.
