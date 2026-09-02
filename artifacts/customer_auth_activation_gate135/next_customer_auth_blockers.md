# Gate 135 — one blocker left, and it needs a person

## Where it stands

```text
login_live                            true
customer_auth_live                    FALSE
dev_header_disabled_for_production    true
owner approval                        recorded (Gate 135D decision)
invite_binding_passed                 FALSE   <- the only one left
```

Measured on the running backend: `customer_auth_live` is false for exactly one
named reason, `auth_gate_not_satisfied:invite_binding_passed`.

## What cleared

**Owner approval.** Mayhem authorized controlled dev customer-auth activation
for the demo organization explicitly. Gate 133D had already split "the demo
login may be called live" from "customer authentication is live"; this is the
second decision arriving. It checks the organization, the provider and the
environment on every call, refuses the real organization by name, refuses
production, and `approves_production_rollout` has no branch that returns True.

The `NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL` env var is still honoured. The
recorded decision is an additional route, not a replacement.

## What remains, and why it is a person rather than a task

`TRUSTED_PROVENANCES` is `{"completed_invite"}` — a membership that did not come
through a completed invite is not trusted, and the demo organization's one
membership is Gate 132's bootstrap, which is `operator_direct_write`.

A completed invite needs somebody to accept it, and accepting means
authenticating. The demo organization has one identity: the owner. The owner
cannot complete an invite to themselves — the repository refuses it by name
(`invite_requested_approved_and_accepted_by_one_identity`) and so does the
database on PostgreSQL.

So the blocker is: **a second real person logging in and accepting an invite.**

Inventing that person would be faking a user. It would also make the evidence
worthless: the gate exists to prove somebody else authorized a membership, and
an invitee this process made up authorizes nothing.

## What was built so it can be completed

```text
migration 0038                  nf_membership_invites
membership_invite_repository_service
  insert_invite                 issue and approve, recorded
  record_acceptance             accept, with three refusals that fire
  build_invite_binding_evidence derived from rows, not a parameter
```

Every branch is exercised against real rows in
`tests/test_gate135_customer_auth_activation.py`, including the completed one:
an invite issued by an owner, accepted by a second identity, producing a
membership, at which point `invite_binding_passed` is true.

`membership_invite_approval_service` had a write path of exactly nothing before
this — 694 lines, `persisted: False` on every result, zero callers in `src/`.

## The exact next action

```text
1  a second person signs in through /api/auth/login with a Google account
2  the owner issues an invite for the demo organization and approves it
3  that person accepts it; a membership is created naming the invite
4  invite_binding_passed becomes true, measured, and customer_auth_live with it
```

Step 1 is the one nobody here can do.

## Still false, and not touched

```text
production_rollout             false
controlled_customer_pilot      false
verified_operational_binding   false   Gate 113 refuses one on a demo org
customer_persistence_live      false
awarded_operational_tracking   false
tenant_digest_operational      false
source_monitoring_live         false
email_delivery                 false
object_store_configured        false
```

No email was sent by anything in this gate, and nothing in the invite path can
send one.
