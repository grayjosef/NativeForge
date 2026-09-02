# 716 — Gate 136: invite activation readiness survey

Measured before anything was implemented. HEAD `7052e6b`.

## How an invite can be created today

```text
membership_invite_approval_service.evaluate_invite   decides
membership_invite_repository_service.insert_invite   writes
```

Both work. `insert_invite` was built in Gate 135 and is exercised against real
rows. Nothing calls either one outside tests.

## How an invite can be approved today

There is no separate approval step. `evaluate_invite` takes
`approval_state="approved"` and `approved_by` as inputs, and `insert_invite`
stores them. So an invite is issued and approved in one write, by whoever runs
it — which is correct for an owner inviting somebody into their own
organization, and is exactly why the self-dealing refusal exists.

## How an invite can be accepted today

```text
membership_invite_repository_service.record_acceptance
```

It exists and it is incomplete. Measured against the code:

```text
refuses   no connection, no organization anchor, no accepter
refuses   invite_not_found
refuses   invite_revoked
refuses   invite_not_approved:<state>
refuses   accepting_identity_does_not_exist
refuses   SELF_DEALT (accepter is the requester or the approver)

does NOT refuse   an EXPIRED invite
does NOT refuse   an invite already in state 'accepted'
does NOT check    that the accepter is the person who was invited
```

The third is the serious one. **Any existing identity that is not the requester
or the approver can accept any invite.** The invite stores
`invited_email_domain` and `invited_subject_fingerprint`, and acceptance reads
neither. An invite is supposed to name who it is for; this one names them and
then does not look.

And `record_acceptance` marks the invite accepted. It creates **no membership**,
so on its own it moves `invite_binding_passed` not at all.

## Whether any route, CLI or script exists for those steps

```text
routes under /api/auth     login, callback, logout, session, current-user
routes mentioning invite   0
scripts mentioning invite  0   (one match, in the coverage guard's keyword list)
CLI entry points           0
```

None. Gate 135 built the seam and left the entry points unbuilt, which is the
gap this gate closes.

## The chicken-and-egg that decides the accept path's shape

The brief ranks an API route above an operator script. Measured, a route cannot
work:

```text
api/auth.py callback, step 5:
    if organization_id_resolved and membership_verified:
        ... set_cookie(...)
```

The callback issues a session cookie **only** when the identity already
resolves to an organization through a membership row. An invited person has no
membership yet — that is the entire point of the invite — so they cannot hold a
session, so an authenticated accept route has nobody to authenticate.

A route that accepted an invite for an *un*authenticated caller would have to
trust something other than a session: an invite id in a URL, an email in a body,
a header. That is the class of authority this campaign has spent twenty-five
gates removing.

So the accept path is the operator script — option 3 — chosen because the higher
options are unreachable, and recorded here so it does not read as the easy pick.
What keeps the operator honest is that the script cannot choose the accepter: it
resolves the identity from `nf_identities` and requires it to match the invite.

## Whether the second account must be prelisted as an OAuth test user

**Yes.** From `690_GATE129_BROWSER_GOOGLE_OAUTH_SETUP_PROMPT.md`:

> "Configure the OAuth consent screen. External, Testing is fine for a dev
> domain. Add my own Google account as a test user."

and `691`:

> "the previous gate, with one test user."

The Google app is **External / Testing** with **one** test user. Google refuses
the authorization request for any account not on that list, before NativeForge
sees anything — the second account gets Google's "Access blocked" screen, not a
NativeForge error. Adding it is a step in the Google Cloud console and nothing
in this repository can do it.

## What the second person's first login actually produces

Worth stating, because it is the step that makes this executable without
inventing anybody:

```text
callback, step 3   writes an nf_identities row for the verified subject
                   idempotent on (issuer, subject)
callback, step 4   resolves no organization
callback, step 5   issues no cookie
```

So the invitee logs in **first**, gets a real identity row from real Google
OAuth, and only then can an invite be issued naming them and accepted for them.
Their second login is the one that produces a session.

## What verification proves `invite_binding_passed`

`build_invite_binding_evidence`, reading rows. It counts:

```text
invite_rows, approved_invite_rows, accepted_invite_rows
membership_rows, memberships_from_a_completed_invite
```

and requires an accepted invite **and** a membership held by the accepter.

One weakness found: `memberships_from_a_completed_invite` is derived by testing
whether a membership's `identity_id` is in the set of identities that accepted
an invite. It does not check that the membership came through that invite. A
membership written by an operator for somebody who separately accepted an
invite would count.

That cannot be fixed by reading harder, because the row has nowhere to say it:

```text
nf_org_memberships columns
  id organization_id identity_id is_demo state membership_source role
  role_source invited_by approved_by created_at revoked_at expires_at
```

No `invite_id`. And `evaluate_membership_provenance` refuses
`completed_invite` provenance without one
(`completed_invite_provenance_without_invite_id`) — a refusal that is currently
unfalsifiable from the database, because no membership row can name an invite.

## What verification proves `customer_auth_live`

`build_customer_auth_activation_gate`, wired in `api/auth.py::_gate` and
reachable at `GET /api/auth/session`. Measured now:

```text
login_live          true
customer_auth_live  false
blocked             auth_gate_not_satisfied:invite_binding_passed
```

Every other required gate passes, including
`dev_header_disabled_for_production` and owner approval.

## Current database state

```text
organizations   aaaaaaaa-… org_type real   seat_cap 5
                bbbbbbbb-… org_type demo   seat_cap 5
nf_identities   1   Google, gmail.com, email_verified, oidc_token_signature
memberships     1   demo org, org_owner, org_owner_approved,
                    approved_by = itself (Gate 132 bootstrap)
invites         0
app_env         local
nf_dev_org_headers  False
```

Seat cap 5, one seat used. A second member fits.

## What can be safely built now

```text
migration 0039   nf_membership_invites.invited_email_fingerprint
                   so acceptance can verify the accepter IS the invitee,
                   without the table ever holding an address
                 nf_org_memberships.invite_id
                   so a membership can name the invite it came through, which
                   makes the provenance refusal falsifiable and lets
                   memberships_from_a_completed_invite be a join

record_acceptance   add the three missing refusals: expired, already
                    accepted, and accepter-does-not-match-the-invite

insert_membership   accept invite_id and invited_by instead of hardcoding
                    None, still derived and validated

new service         the accept path: verify, record acceptance, create the
                    membership naming the invite, one transaction

scripts             issue, accept, and a verifier that recomputes both gates
```

None of that requires a second person. All of it is required before a second
person's few minutes are worth spending.

What cannot be built: the second person. Everything here exists so that when
they sign in, nothing has to be improvised.
