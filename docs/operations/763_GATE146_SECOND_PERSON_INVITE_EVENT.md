# 763 — Gate 146: the second-person invite event

## What `customer_auth_live` is waiting for

```text
customer_auth_live          false
blocker                     invite_binding_passed
blocker kind                an event, not a decision
owner_activation_decision   already approves customer_auth_live
gates passing               16 of 17
```

Sixteen of the seventeen gates in `REQUIRED_AUTH_GATES` pass. The owner decision
that Gate 135 made a separate requirement is already granted. Nothing is
waiting on code and nothing is waiting on an approval.

## The blocker is a conjunction, and its name does not locate it

Gates 144 and 145 both report `invite_binding_passed`. True, and coarse — it
covers three things that must happen in order:

```text
stage 1   a second identity signs in       nf_identities gains a row
stage 2   the owner issues an invite       nf_membership_invites gains a row
stage 3   the owner accepts it for them    the invite is accepted AND an
                                           active membership names that invite
                                           AND the member is the accepter
```

Measured against the live database today:

```text
nf_identities                          1     the owner
nf_membership_invites                  0
nf_org_memberships                     1     the owner's, not from an invite
memberships_from_a_completed_invite    0
blocked_reasons    ['no_invite_has_been_recorded']
```

So the state is **not** "an invite is waiting to be accepted". No invite exists,
and the second person has never signed in. An operator told only
`invite_binding_passed` goes looking for an invite to accept and finds nothing,
which is why Gate 146's checklist reports the **stage** and names the earliest
unsatisfied step as the next action.

Today that step is stage 1, and its owner is *the second person* — not the
operator, and not a command.

## What proves each stage

```text
stage 1   an nf_identities row for a subject the provider verified.
          Counted, never selected: the row holds a real address and the
          provider subject.
stage 2   an nf_membership_invites row for the demo organization, holding the
          domain half and two fingerprints and no address.
stage 3   a join. The invite is accepted, an active membership names that
          invite, and the member is the accepter. Any one of the three alone
          proves nothing, which is the defect Gate 136 fixed.
```

## Why nothing in this repository can produce it

```text
a typed nf_identities row    the accepter is resolved from nf_identities and
                             must then match the invite's own fingerprint; a
                             row somebody typed satisfies neither half
a minted session             writes no identity row at all
a synthetic provider subject the faked user this gate exists to avoid
a directly written membership  invite_binding_passed joins the membership to
                             the invite and to the accepter; a membership that
                             merely shares an identity is counted separately,
                             as the near-miss it is
the owner's own login        already happened — it is the one identity and the
                             one membership above; the owner cannot accept
                             their own invite
the real organization        both scripts refuse it by name and exit 2 in a
                             production environment
```

All six are recorded in the checklist service as `REFUSED_SHORTCUTS`, and a
test asserts each is still refused.

## The two commands are safe, and already refuse the unsafe path

```text
nativeforge_demo_invite_issue.py
  demo org only; real org refused by name; production exits 2
  is_demo derived from organizations.org_type, not from a flag
  the issuer is read from the org's active org_owner row, never supplied, so
    an operator cannot forge who authorized a membership
  the address is read at runtime, never printed, never stored
  sends no email; the table has no column for an address to send to

nativeforge_demo_invite_accept.py
  refuses `no_identity_has_signed_in_with_that_address` when stage 1 is
    missing — the honest answer, not an error to work around
  a different address refuses rather than redirecting the membership
  both writes are one transaction
  has no bypass flag, and a test asserts none has appeared
```

## The one step that is not observable

The Google app is External/Testing. Google refuses an unenrolled account
*before NativeForge sees the request*, so the second person gets Google's own
"Access blocked" screen and no NativeForge log line explains it.

Nothing here can read the Google console, so test-user enrolment is reported
`UNKNOWN` rather than inferred from a failure indistinguishable from several
others. Up to 100 test users are allowed. **Do not publish the app** to work
around it.

## What Gate 146 built

```text
a checklist service    reports the stage, the counts, the blockers and the one
                       next human action; customer_auth_live is derived, never
                       a parameter
a verifier             separates readiness_passed from customer_auth_live and
                       exits 0 on readiness
three routes           GET only, demo org only, 401 unauthenticated
six artifacts          the path, not today's counts
```

It issued no invite, accepted none, wrote no identity, minted no session, sent
no mail, and touched no real organization.

## Next

`765_GATE146_NEXT_HUMAN_ACTION.md` has the steps in order.
