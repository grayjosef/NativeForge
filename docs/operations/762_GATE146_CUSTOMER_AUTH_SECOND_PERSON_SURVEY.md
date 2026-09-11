# 762 — Gate 146: the customer-auth second-person event, surveyed

Read-only. Nothing below was activated, issued, accepted, or written.

## The measured state, today

```text
customer_auth_live                                false
blocker                                           invite_binding_passed
owner_activation_decision                         approves_customer_auth_live
login_live                                        true
dev_header_consumers                              0
```

Sixteen of the seventeen gates in `REQUIRED_AUTH_GATES` pass, and the owner
decision that Gate 135 made a separate requirement **already approves**. One
blocker remains, and it is not a decision. It is an event that has not happened.

## The blocker is earlier than the campaign has been recording it

Gates 144 and 145 both report the blocker as `invite_binding_passed`, which is
true but coarse. Measured against the live database:

```text
nf_identities                                     1
nf_membership_invites                             0
nf_org_memberships                                1
memberships_from_a_completed_invite               0
blocked_reasons               ['no_invite_has_been_recorded']
```

One identity — the owner. One membership — the owner's, which did not come
through an invite because there was no invite to come through.

So the state is not "an invite is waiting to be accepted". **No invite exists,
and the second person has never signed in.** Step 1 of doc 717 has not run.
That distinction matters: the next human action is not "accept the invite", it
is two steps earlier, and one of those two is not a command at all.

## Three sequential sub-blockers behind the one name

`invite_binding_passed` is a conjunction, and the verifier's count table already
says which conjunct is missing:

```text
stage 1   a second identity signs in         nf_identities 1 -> 2
stage 2   the owner issues an invite         invite_rows 0 -> 1
stage 3   the owner accepts it for them      accepted_invite_rows 0 -> 1
                                             and the membership names it
```

Today we are before stage 1. Gate 146's checklist reports the stage, not just
the conjunction, so an operator is told the one thing to do next rather than
the three things that are all still outstanding.

## Why this cannot be made true from inside the repository

Stage 1 requires a **real second Google account completing real OAuth**. The
callback writes `nf_identities` only for a subject Google verified. Nothing in
this repository can produce one:

```text
a fake identity row       has no verified subject; the accept script resolves
                          the identity from nf_identities and then requires it
                          to match the invite's own fingerprint, so a row
                          somebody typed satisfies neither half
a fake session            does not write an identity at all, and the callback
                          issues a cookie only once a membership resolves
a synthetic subject       is the faked user this whole gate exists to avoid
an owner-only login       already happened; it is the 1 identity and the 1
                          membership above, and it is what makes
                          `memberships_matching_an_accepter_by_identity_only`
                          a number worth printing beside the real one
```

Gate 136 built the derivation so that all three fail. `build_invite_binding_evidence`
requires an accepted invite **and** a membership that names that invite **and**
whose holder is the accepter — a join, not a coincidence — and
`invite_evidence_invariant_failures` refuses a pass that arrived without any of
them.

## The one step that is not a command, and is not detectable

The Google app is **External / Testing**. Google refuses an account that is not
on its test-user list *before NativeForge sees the request*, so the second
person gets Google's own "Access blocked" screen and no NativeForge log line
explains it.

Nothing in this repository can read the Google console. Whether the second
account has been enrolled is therefore **UNKNOWN / NEEDS HUMAN REVIEW**, and
Gate 146 must report it that way rather than inferring it from a failure that
looks identical to several other failures.

Up to 100 test users are allowed. Publishing the app to get around it would
expose a dev consent screen to anybody with the URL and is not needed.

## Are the two scripts safe to run?

Both, yes — and both already refuse the unsafe path.

```text
nativeforge_demo_invite_issue.py
  demo org only, real org refused by name, production env exits 2
  is_demo derived from organizations.org_type, not from a flag
  the issuer is read from the org's active org_owner row, never supplied,
    so an operator cannot forge who authorized a membership
  sends no email; the table has no column for an address to send to
  the address is read at runtime, never printed, never stored

nativeforge_demo_invite_accept.py
  refuses `no_identity_has_signed_in_with_that_address` when stage 1 is
    missing, which is the honest answer and not an error to work around
  the accepter is resolved from nf_identities and must match the invite's
    fingerprint; running it with another address refuses rather than
    redirecting the membership
  both writes are one transaction
```

There is no flag on either that accepts on behalf of somebody who has not
authenticated.

## What may be stored, and what must never be printed

`nf_identities` holds the real thing:

```text
nf_identities.email        a real address
nf_identities.subject      the provider subject
```

Neither may be selected into any readout, artifact, route response, or verifier
line. The invite table was designed around this and keeps only derived halves:

```text
invited_email_domain           the domain half
invited_email_fingerprint      a fingerprint
invited_subject_fingerprint    a fingerprint
```

Counts, booleans, stage names and blocker names are safe. Identifiers are not,
with one exception: the **invite id** is printed by the issue script on purpose,
because the operator needs it for stage 3 and it identifies no person.

## What would constitute proof

```text
invite_rows                          >= 1
accepted_invite_rows                 >= 1
memberships_from_a_completed_invite  >= 1
the accepter                         an identity distinct from the owner
blocked_reasons                      empty
invariant failures                   none
```

and then `verify_nativeforge_customer_auth_live.sh` returning `RESULT=PASS`
with `customer_auth_live=true`, `scope=controlled_dev_demo_org_only`.

## What must remain false after a readiness gate

Gate 146 is a readiness gate. A correct readiness path is not the event, so
after it:

```text
customer_auth_live               false
invite_binding_passed            false
verified_operational_binding     false
controlled_customer_pilot        false
production_rollout               false
```

This is the same readiness-is-not-capability distinction Gate 145 named five
times. `readiness_passed=true` alongside `customer_auth_live=false` is the
correct and expected output, and the verifier must report both rather than
collapsing them — a verifier that failed because a human has not done a human
thing would train an operator to ignore it.

## One wording correction this survey turned up

Doc 717 opens:

> Not theoretical. Every command below exists and has been run end to end.

Every command does exist and each was exercised during Gate 136. But the live
database says the event has not occurred, and a reader in a hurry will take
"has been run end to end" to mean it has. That is the declared-versus-derived
confusion this campaign keeps finding, sitting in the runbook for the very
event it describes. Gate 146G corrects the sentence and points it at the
measured state instead.

## Exact next human action

```text
1  enrol the second Google account as a test user in the Google console
     console.cloud.google.com -> APIs & Services -> OAuth consent screen
     -> Audience -> ADD USERS -> SAVE
   not a command, not detectable from here

2  that account signs in once, in a clean browser profile
     https://nf-dev.mayhem-nc.dev/api/auth/login
     expect NO session. An identity row is written; the membership does not
     exist yet, so no cookie is issued. That is correct.

3  ./scripts/nativeforge_demo_invite_issue.py  --email <that address>
4  ./scripts/nativeforge_demo_invite_accept.py --invite-id <from 3> --email <same>
5  that account signs in again; now a session is issued
6  ./scripts/verify_nativeforge_customer_auth_live.sh
```

Steps 3 and 4 are the operator's. Steps 1, 2 and 5 need the second person.

## What Gate 146 builds

A checklist service that reports the stage and the earliest unsatisfied step; a
verifier that separates `readiness_passed` from `customer_auth_live`; routes
that answer the same three questions for the cockpit; artifacts; and the docs
that say what must not be printed. It does not issue an invite, does not accept
one, and does not make `customer_auth_live` true.
