# 412 — Gate 68A / 71: Production readiness delta

Two gates, one honest outcome each. 68A delivered what it set out to. 71
discovered it could not safely do what it set out to, and built the layer that
makes it possible later.

## Audit sink: now

| | Before | After |
| --- | --- | --- |
| Anything collects modeled events | **no** | yes — `submit_events` |
| Classification of persistable vs not | **no** | yes, per event, with reasons |
| `cross_org_access_attempt` refused before the repository | no — only at the write | **yes, at classification** |
| Events lost between input and accounting | undetectable | **impossible — accounting invariant** |
| Event arriving with `persisted: true` | undetected | refused |
| Live write path | none | optional, requires an explicit writer |

Twelve of the thirteen security verbs are persistable today. One is not, and it
is the one that matters:

```text
cross_org_access_attempt → refused, migration_required = 0028
```

The reason is structural, not a missing column count. The event concerns the
actor's org, the target's org, and possibly a third claimed org.
`nf_audit_events.organization_id` is `NOT NULL` and is the RLS predicate, so
there is one slot: the actor's org hides the event from the tenant attacked, and
the target's org attributes the attack to the victim.

Two design points worth stating:

- **Live mode with no writer is an error, not a silent no-op.** Falling back to
  modeled would tell a caller who asked for persistence that everything was
  fine while writing nothing.
- **A writer that raises surfaces.** The failure is recorded and a warning says
  the request should fail. An audit write that fails quietly is worse than a
  request that fails loudly.

## Audit persistence: now

**Still not live.** No provisioned database, so nothing is written. The sink is
step 4 of doc 391's six-step plan; steps 2, 3, 5 and 6 remain, and step 2 is
migration 0028.

The Gate 65 repository guard remains the last line of defence and still raises
if it is ever handed the unpersistable verb. The sink should never hand it one —
a test proves the writer never even sees it.

## Capability read enforcement: now

| | Before | After |
| --- | --- | --- |
| Enforcement logic for reads | existed (Gate 58), unexercised on reads | exercised and tested |
| Adapter for route wiring | none | `api/capability_guard.py` |
| Live routes enforcing capability | 0 | **0** |
| Client role headers | rejected by an unattached helper | rejected inside the decision path |
| Denials routed to an audit sink | no | yes, modeled mode |

**Zero routes wired, and that is the correct outcome.** The survey (doc 409)
found that every route on both planes resolves its organization from the
`X-NF-Org-Id` header and no route resolves an actor at all.
`resolve_request_identity` cannot return a verified customer because no OIDC
verifier is configured, and `enforce_capability` requires `membership_active`,
which is always `unknown` without a membership store.

Wiring anything would have produced one of two bad outcomes: deny 100% of
traffic including the public demo, or trust a client header as role proof. The
second is the precise vulnerability Gates 58–67 exist to prevent.

A test asserts no route file imports the guard, so if someone wires it, the test
fails and forces doc 411 to be updated.

## Live route wiring status

```text
Live routes wired: 0
Dry-run evaluation: available
Blocked on: Gate 69 (OIDC verifier), Gate 70 (membership-resolved org/role),
            provisioned database
```

## Owner-blocked

- Managed PostgreSQL 16+ and its `DATABASE_URL`, out-of-band
- Approval for migration 0028
- Retention decision for security audit events, including the shorter class for
  invite-denial events flagged in doc 406
- The email-in-audit resolution (doc 406)
- Real `OIDC_*` credentials — the single biggest unblock for Gate 71
- Backup automation, PITR decision, first restore drill
- Independent pen test, Slack webhook + redaction decision

## Engineering-blocked

- Migration 0028 and its RLS policy widening, plus the new check that an actor
  org cannot read target-only events
- Replacing `get_org_context_with_db` with identity-resolved org context — this
  is the change that unblocks all 124 read routes at once
- Invite/approval persistence and `source_invite_id` on `nf_org_memberships`
- Transactional seat counting
- Write-route enforcement (Gate 72), which is strictly after reads
- Source registry and discovery baseline (76–85)

## Controlled customer pilot delta

**None. Still NO_GO.**

```text
Controlled customer pilot: NO_GO
Production rollout:        NO_GO
Customer login live:       NO
Production storage live:   NO
Customer persistence:      NO
Pen-test passed:           NO
Slack live alert:          NOT PROVEN
```

What genuinely changed: security audit events are now collected and classified
rather than dropped by their callers, the one event the schema cannot represent
is refused before anything tries to write it, and the read-enforcement logic is
proven correct ahead of having anything to attach it to.

What did not change: nothing is persisted, no route enforces capability, and a
customer still cannot log in.

## The single most valuable next step

**Gate 69 — real OIDC credentials and a verified token.** It is the shared
blocker. It unblocks Gate 70, which unblocks all 124 read routes at once, which
unblocks Gate 72. Every other engineering task in this list is downstream of an
identity that can be trusted.
