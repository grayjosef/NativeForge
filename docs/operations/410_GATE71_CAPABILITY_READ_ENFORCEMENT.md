# 410 — Gate 71: Capability read enforcement

## What was wired

**No live routes.** See doc 411 for the count and doc 409 for why.

What exists is `src/nativeforge/api/capability_guard.py`, with two entry points:

| Function | Mode | Attached to |
| --- | --- | --- |
| `evaluate_read_capability` | dry-run | nothing — computes and records |
| `require_read_capability` | live, raises 403 | nothing |

Both are fully tested at the adapter level.

## What remains dry-run

All of it. `evaluate_read_capability` computes the decision a live route would
reach, routes denial events through the Gate 68A audit sink in modeled mode, and
returns `enforced: false`. An invariant fails any dry-run result claiming
enforcement.

## What is blocked, and on what

| Blocker | Gate | Effect |
| --- | --- | --- |
| No OIDC verifier | 69 | every identity is `anonymous`, `demo_operator`, or `oidc_configured_unverified` |
| No membership store | 70 + provisioning | `membership_state` is always `unknown`, so `membership_active` is always `False` |
| Org comes from `X-NF-Org-Id` | 70 | no route knows *which customer* is calling, only which org was named |

Any one of these alone is sufficient to block wiring.

## What the guard refuses

Deny-by-default throughout. Every one of these is a test:

- **Anonymous** — no credential.
- **`demo_operator`** — Cloudflare Access proves an operator reached the edge,
  not that a customer logged in. This distinction is the whole reason the demo
  is safe to expose.
- **`oidc_configured_unverified`** — a bearer token was presented and nothing
  verified it.
- **`verification_trusted: false`** — denied even when `identity_state` looks
  right, so a half-built identity cannot slip through.
- **Client-asserted role headers** — `X-NF-Role`, `X-NF-Roles`,
  `X-NF-Capability` are *rejected*, not ignored. A silently ignored spoof lets
  the caller believe it worked.
- **`X-NF-Org-Id` as membership proof** — it gets a request into an org's
  routes; the role must come from the directory.
- **Non-active membership** — `invited`, `suspended`, `removed`, `unknown` all
  deny.
- **Missing capability** — `viewer` holds `view_workspace` but not
  `view_org_audit_events`.
- **Write and authority capabilities** — out of scope for this gate; rejected as
  `capability_not_a_wired_read_capability`.
- **Permanently blocked capabilities** — the production gates stay unreachable.

### There is no input for a client-supplied role

`evaluate_read_capability` has no `asserted_role`, `client_role`, `role_header`
or `claimed_role` parameter, and a test asserts their absence. That is a cheaper
guarantee than validating such a parameter correctly.

## Capability vocabulary

The gate suggested `view_evidence`, `view_feedback`, `preview_package_export`,
`view_source_registry`. **None exists**, and the instruction was to use existing
vocabulary rather than invent duplicates. Two existing capabilities cover reads:

| Capability | Held by |
| --- | --- |
| `view_workspace` | every customer role, plus `operator_internal` |
| `view_org_audit_events` | `org_owner` only |

Read families map onto them:

```text
workspace_read          → view_workspace
evidence_read           → view_workspace
feedback_read           → view_workspace
package_export_preview  → view_workspace
source_registry_read    → view_workspace
org_audit_read          → view_org_audit_events
```

A test asserts `READ_CAPABILITIES ⊆ CAPABILITIES`, so a second vocabulary cannot
appear silently.

Worth noting: `view_workspace` being held by *every* role means it is a weak
gate on its own. It separates "member of this org" from "not a member", which is
the useful distinction for a read path, but it does not differentiate a `viewer`
from an `org_owner`. Finer-grained read capabilities may be worth adding later —
that is a matrix change, not something to bolt on here.

## Which audit events fire

`enforce_capability` emits `authority_sensitive_action_blocked` on denial. The
guard passes it to `submit_events(..., mode="modeled")`, which classifies it as
persistable-but-not-written and accounts for it. Nothing is written; nothing is
dropped.

## Why write routes are out of scope

Three reasons, in order of weight:

1. **The same blocker is worse there.** If reads cannot be enforced for lack of
   a verified actor, writes certainly cannot — and a write route that denies
   everything is a broken product rather than a locked-down one.
2. **Writes need the audit trail that does not exist yet.** A write without a
   persisted audit record is unreviewable, and audit persistence is blocked on
   migration 0028.
3. **Ordering discipline.** The gate sequence puts reads at 71 and writes at 72
   precisely so the read path can be proven before anything mutates.

Final approval and portal submission remain in
`PERMANENTLY_BLOCKED_CAPABILITIES` and are unreachable regardless of role.

## Why the pilot remains NO_GO

A customer cannot log in, so there is no identity to enforce against. Their
membership cannot be stored, so there is no role to grant. Their denials cannot
be persisted, so enforcement would be unauditable.

This gate proved the enforcement logic is correct. It did not make any of those
three true.

```text
Controlled customer pilot: NO_GO
Production rollout:        NO_GO
Customer login live:       NO
Production storage live:   NO
```
