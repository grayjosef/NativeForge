# Gate 146 — the next human action

`customer_auth_live` is false for one reason, and it is not a decision
anybody has withheld. It is an event that has not happened.

```text
blocker                     invite_binding_passed
owner_activation_decision   already approves customer_auth_live
```

## The steps, in order

```text
0  enrol the second Google account as an OAuth test user
     console.cloud.google.com -> APIs & Services
     -> OAuth consent screen -> Audience -> ADD USERS -> SAVE
     not a command, and not observable from this repository

1  that account signs in once, in a clean browser profile
     expect NO session. An identity row is written; the membership
     does not exist yet, so no cookie is issued. That is correct.

2  ./scripts/nativeforge_demo_invite_issue.py --email <address>
     copy the invite id it prints

3  ./scripts/nativeforge_demo_invite_accept.py \
       --invite-id <from step 2> --email <the same address>

4  that account signs in again; now a session is issued

5  ./scripts/verify_nativeforge_customer_auth_second_person_event.sh
```

Steps 2 and 3 are the operator's. Steps 0, 1 and 4 need the second
person, and step 0 needs the Google console.

## Why none of this can be done from here

```text
insert an nf_identities row by hand
    the accepter is resolved from nf_identities and must then match the invite's own fingerprint; a typed row satisfies neither half
mint a session cookie for a second person
    a session writes no identity row at all
synthesize a provider subject
    it is the faked user this gate exists to avoid
write a membership directly, without an invite
    invite_binding_passed joins the membership to the invite and to the accepter; a membership that merely shares an identity is counted separately as the near-miss it is
count the owner's own login as the second person
    the owner cannot accept their own invite, and the accepter must be an identity distinct from the org owner
run the path against the real organization
    both scripts refuse aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee by name and exit non-zero in a production environment
```

## What must not be printed

```text
the invited address                lives in nf_identities.email
                                   report instead: the domain half and a fingerprint, on the invite row
the provider subject               lives in nf_identities.subject
                                   report instead: a fingerprint, on the invite row
the session cookie                 lives in the browser
                                   report instead: a boolean saying whether a session was issued
the OAuth state and PKCE verifier  lives in the redirect state store
                                   report instead: nothing; no readout needs them
```

Safe to print: the invite id — the operator needs it for the accept command and it identifies no person; the issue script prints it on purpose.

## What stays false when this gate passes

```text
customer_auth_live   false
invite_binding_passed   false
verified_operational_binding   false
controlled_customer_pilot   false
production_rollout   false
```

This gate proves the path. It does not walk it.
