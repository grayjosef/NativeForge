# 712 — Gate 135: invite binding evidence

## The service that decided nothing down

`membership_invite_approval_service`, before this gate:

```text
694 lines
0 sa.insert / sa.update
0 connection parameters
"persisted": False on every result
0 callers anywhere in src/
```

It is a complete invite and approval contract — states, seat caps, role
capabilities, expiry, revocation, provenance — that had never been asked a
question by anything in the running application. `invite_binding_passed` was a
parameter of `run_auth0_live_validation` that no caller passed, the fifth
instance of that shape in this campaign.

## What the contract actually requires

```python
MEMBERSHIP_PROVENANCES = {"completed_invite", "operator_direct_write",
                          "migration_backfill", "unknown"}
TRUSTED_PROVENANCES   = {"completed_invite"}
```

> "a membership that did not come through a completed invite is not trusted,
> however well-formed its other columns are."

And a completed invite must name itself — `completed_invite_provenance_without_invite_id`.
That refusal is unfalsifiable while there is nowhere for an invite to be, which
is why the seam had to be built before the gate could be measured.

## Migration 0038 — `nf_membership_invites`

```text
stored     invite_id, organization_id, is_demo, requested_role,
           requested_by/_role, approved_by/_role, accepted_by_identity_id,
           invite_state, approval_state, seat_cap, seat_count, timestamps
           invited_email_domain          the domain half only
           invited_subject_fingerprint   sha256(subject)[:32]
refused    the invitee's address, the provider subject, any token
```

An invite carries a person's contact details by nature, so this is the table
that must not keep them. The address is what an invite is *sent to*, and nothing
in NativeForge sends one.

Two CHECKs make the gate's input un-forgeable by a single UPDATE:

```sql
accepted_at IS NULL OR invite_state = 'accepted'
invite_state <> 'accepted' OR accepted_by_identity_id IS NOT NULL
```

An accepted invite names who accepted it.

## A gap the decision service does not close

`evaluate_invite` **does not refuse a self-invite**. Asked to evaluate the org
owner inviting themselves, approved by themselves, it returns no blocked
reasons — every seat and role check passes because they are all about the same
person, and each one passes honestly.

Found while surveying. The repository refuses it by name on every dialect:

```text
invite_requested_approved_and_accepted_by_one_identity
```

Enforced in code rather than only as a PostgreSQL CHECK, because the dev
database is SQLite and a guard that fires only in production is not a guard for
the environment it runs in.

## What `invite_binding_passed` now means

Derived from rows, in two parts that are counted separately so the difference
stays visible:

```text
an invite that was accepted        by an identity that exists
a membership that identity holds   active, unrevoked
```

Either alone proves nothing. An invite issued and approved and never accepted
has bound nobody; an acceptance without a membership has produced nothing.

## Measured

Against the dev database:

```text
invite_rows                            0
approved_invite_rows                   0
accepted_invite_rows                   0
membership_rows                        1
memberships_from_a_completed_invite    0
invite_binding_passed                  FALSE
blocked                                no_invite_has_been_recorded
```

The one membership is Gate 132's bootstrap. Its provenance is
`operator_direct_write`, which the contract refuses — correctly, and by design:
the first membership in an organization has nobody to approve it, which is why
Gate 132 restricted self-approval to exactly that case.

## Why no invite was written to the dev database

Issuing one requires an invitee. Writing an invite addressed to a person who
does not exist, or accepting one on their behalf, would be fabricating the
evidence this gate measures — and the gate exists to prove somebody else
authorized a membership. An invitee this process invented authorizes nothing.

So the seam is proved against real rows in a test database, including the
completed branch, and the dev database records the honest zero.

## Every branch, exercised

`tests/test_gate135_customer_auth_activation.py`:

```text
issue + approve, address and subject not stored          rows_written 1
approved, never accepted                                 passed false
owner accepts their own invite                           refused, self-dealt
acceptance by an identity that does not exist            refused
accepted, no membership yet                              passed false
accepted + membership held by the accepter               passed TRUE
```

The last one is the state the demo organization cannot reach on its own.
