# 388 — Gate 61H: Production readiness delta

## What storage path is now clear

Previously "storage is blocked" was a sentence. It is now a decision with eight
questions, a recommended backend, a named schema scope, and an approval token
(`387`). The survey (`383`) established what actually exists rather than what was
assumed.

Two corrections came out of that survey, both of which change the picture:

1. **RLS is written but has never executed.** Migration `0002` enables and
   forces row-level security and creates per-table org-scope policies — all
   guarded by `dialect.name == "postgresql"`. No Postgres has ever been
   connected. Earlier docs listed RLS as unbuilt; *written but unexercised* is a
   more dangerous state, because untested isolation code reads like protection.
2. **An audit table already exists.** `nf_audit_events` plus a repository, used
   by two discovery routes. My Gate 58/59 docs said audit persistence did not
   exist. The accurate gap is narrower: the table exists, and Gate 58's
   tenant-denial events are not wired to it.

## What membership path is now clear

The chain Gate 59 identified as broken now runs end to end:

```text
RS256 token -> verified identity -> trusted membership -> trusted role -> capability
   Gate 60        Gate 60             Gate 61              Gate 61        Gate 58
```

`test_trusted_role_flows_into_enforce_capability` walks all five steps with real
crypto and asserts both that `assemble_evidence` is granted to a `grant_lead`
and that `certify_org_facts` is still denied.

Design decisions worth keeping: only `membership_record` is a trusted role
source — an Auth0 group claim is the IdP administrator's opinion, not this
product's membership record. Expiry, revocation, approval-without-approver and
unknown roles are all *derived* rather than believed.

## What remains dry-run / in-memory

Everything about membership persistence:

```text
storage_backend_state           = in_memory_test_adapter
production_storage_live         = false
customer_persistence_claimed    = false
live_customer_membership_lookup = false
membership_schema_exists        = false
persisted                       = false   (every record, every audit event)
```

No live route is wired. The adapter is called
`InMemoryMembershipDirectory` and a test asserts its name contains neither
"production" nor "live". Migrations `0023`–`0027` are **specified and
deliberately unwritten** — writing them now would produce migrations validated
only against in-memory SQLite, which proves nothing about the Postgres RLS
behaviour that matters most.

## What remains owner-blocked

1. **Production storage approval** — doc 387. The single highest-leverage
   decision available; it gates items 5–10 below.
2. **Real `OIDC_*` credentials** — Gate 60 live token proof.
3. **Independent pen test.**
4. **Live Slack webhook + redaction decision.**

## What remains engineering-blocked

5. Migrations `0023`–`0027` (blocked on 1)
6. **Prove RLS actually executes** — with a non-owner, non-superuser app role,
   or the policies are silently bypassed (blocked on 1)
7. `PostgresMembershipDirectory` behind the same interface (blocked on 1, 5)
8. **Invite / approval path**, so memberships are created by a human decision
   with `approved_by` recorded rather than seeded by an operator (blocked on 5)
9. Capability enforcement on live read routes, then writes (blocked on 7, 8)
10. Audit persistence — wire tenant-denial events to the existing table
    (blocked on 1)
11. Discovery measurement baseline (blocked on 1, 9)
12. Customer pilot runbook (blocked on all of the above)

Item 8 is easy to miss in a schema discussion but is a real requirement: without
it, the only way to create a membership is an operator writing rows directly,
which is precisely the internal-operator overreach threat in doc 366.

## Why controlled customer pilot remains NO_GO

```text
Controlled customer pilot: NO_GO
Production rollout:        NO_GO
Customer login live:       NO
Production storage:        NO
Customer persistence:      NO
Pen-test passed:           NO
Slack live alert:          NOT PROVEN
```

A pilot means a named person from a specific tribal organization logs in and is
provably limited to that organization's data. Today:

- their identity **can** be verified (Gate 60)
- their membership **cannot be looked up** — there is nowhere for it to live
- so `may_act_as_customer` is `false`, correctly
- and the storage-layer isolation that would backstop an application bug has
  never been executed

Gate 61 made the remaining gap precise and small. It did not close it, and every
artifact says so in a machine-checkable field.

## Honest summary

This gate deliberately did **not** build a fake production layer. It surveyed
what exists, corrected two of my own earlier claims, specified the storage
decision as an answerable checklist, and built the membership link only as far
as an explicitly-named in-memory adapter allows — which turned out to be far
enough to prove the entire identity-to-capability chain works.

The next move is a decision, not code.
