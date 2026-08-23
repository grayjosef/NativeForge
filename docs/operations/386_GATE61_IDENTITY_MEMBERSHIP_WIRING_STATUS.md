# 386 — Gate 61E: Identity → membership wiring status

## Honest status

```text
live route wired:            NOTHING
dry-run adapter only:        the full chain, end to end, proven by test
not wired:                   every customer route
blocked on production storage: membership persistence, and therefore live wiring
```

## The chain now exists end to end — in tests

For the first time in this campaign, the whole path runs:

```text
RS256 token          -> verify_oidc_token          (Gate 60, real crypto)
verified result      -> identity_from_verified_token (Gate 60)
verified identity    -> resolve_trusted_membership  (Gate 61, in-memory adapter)
trusted role         -> enforce_capability          (Gate 58 seam)
capability           -> allowed / denied
```

`test_trusted_role_flows_into_enforce_capability` walks all five steps: signs a
token with a generated keypair, verifies it, maps it to an identity, resolves a
trusted membership from the adapter, feeds the resulting role into
`enforce_capability`, and asserts `assemble_evidence` is granted to a
`grant_lead` while `certify_org_facts` is still denied.

That last assertion matters as much as the first: reaching the end of the chain
does not make a role omnipotent.

## Why nothing is wired to a live route

Same reasoning as Gate 59 doc 376, now with a sharper edge because the chain
works:

1. **The directory has no store.** `InMemoryMembershipDirectory` holds records
   for the life of a process. Wiring it to a live route would mean membership
   that vanishes on restart and that nobody can actually populate — a lookup
   that always returns "no membership record" and therefore denies every
   request, including the demo.
2. **Populating it would mean inventing memberships.** The only way to make a
   live route succeed today is to seed the adapter with records nobody approved.
   That is fabricating membership, which is on the hard-rules list, and it would
   produce audit events that look like real authorisation.
3. **`verified_directory` has no producer.** The trusted source exists as an
   allowlist entry. Nothing writes to it, and nothing can until there is a
   schema and a store.

So the adapter stays a test vehicle. The alternative — a live route backed by
in-memory records — would be the "fake production layer" this gate was
explicitly told not to build.

## What is honestly claimable

| Claim | Status |
| --- | --- |
| Token verification implemented | TRUE (Gate 60) |
| Identity contract implemented | TRUE (Gate 59) |
| Membership → role derivation implemented | TRUE (Gate 61) |
| Capability enforcement seam implemented | TRUE (Gate 58) |
| Whole chain proven end to end | TRUE — **in tests, with an in-memory adapter** |
| Membership persisted | FALSE |
| `live_customer_membership_lookup` | FALSE |
| `production_storage_live` | FALSE |
| `customer_login_live` | FALSE |
| Any customer route enforcing capability | FALSE |

## Flags carried by every Gate 61 artifact

```text
storage_backend_state          = "in_memory_test_adapter"
production_storage_live        = false
customer_persistence_claimed   = false
live_customer_membership_lookup= false
customer_login_live_claimed    = false
membership_schema_exists       = false
persisted                      = false   (on every record and audit event)
```

Invariants fail any record or status object that sets these otherwise, so the
claim cannot drift by accident.

## What unblocks live wiring

In strict order:

1. **Owner approves production storage** (doc 387). Everything below is blocked
   on this single decision.
2. Write migrations `0023`–`0027` (doc 384 §5) against real Postgres.
3. **Prove RLS actually works** — doc 383 correction 1: the policies exist but
   have never executed, and the app role must be non-owner and non-superuser or
   they are silently bypassed.
4. Implement a `PostgresMembershipDirectory` behind the same interface, so the
   resolver does not change.
5. Build an invite/approval path so memberships are created by a human decision
   with `approved_by` recorded, not seeded.
6. Wire `identity_dependency` + `resolve_trusted_membership` +
   `enforce_capability` onto **read** routes first — a read denial is
   recoverable, a write denial is not.
7. Only then, authority-sensitive writes.

Step 5 is worth calling out: it is not just a schema. Somebody has to be able to
invite a colleague and have an org owner approve them, or memberships can only
be created by an operator reaching into the database — which is exactly the
internal-operator overreach threat in doc 366.
