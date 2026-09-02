# 715 — Gate 135: readiness delta

## The delta

```text
                                     before 135   after 135
customer_auth_live blockers              2            1
  owner_approval                       absent       RECORDED
  invite_binding_passed                 false        false

dev-header chains present in api/          5            0
dev-header route consumers                 0            0
dev-header provider modules                2            0

login_live                              true         true
customer_auth_live                     false        false
verified_operational_binding           false        false
alembic head                            0037         0038
```

One of the two blockers cleared. The one that remains is not an engineering
task — it is a second person signing in.

## What the gate says on the running backend

```text
GET /api/auth/session

login_live          true
customer_auth_live  false
blocked             auth_gate_not_satisfied:invite_binding_passed
```

Exactly one named reason. Gate 134 left two.

## `invite_binding_passed` went from unmeasurable to measured-false

That is a smaller-sounding change than it is. Before this gate the flag was a
parameter of `run_auth0_live_validation` that no caller passed, backed by a
694-line decision service with zero writes, zero connection parameters, and zero
callers in `src/`. There was no table for an invite to be in, so the contract's
central refusal — a membership must come through a completed invite — could not
be satisfied by anything, and could not be falsified either.

It is derived from rows now, in two parts counted separately: an invite that was
accepted by an identity that exists, and a membership that identity actually
holds. Either alone proves nothing. Full account in `712`.

## What cleared: owner approval

Recorded rather than declared. `build_customer_auth_activation_decision` checks
the organization, the provider and the environment on every call; refuses
`aaaaaaaa-…` by name; refuses production; and reads one environment variable
that can only revoke. No variable turns it on. Full account in `713`.

## The chains are gone

159 lines across three files. `deps_db.get_org_context_with_db` and its two
guards, all of `isolation_deps.py`, and
`deps_customer_auth.get_dev_org_context_explicit_only`. Nothing in `api/` reads
`X-NF-Org-Id` any more, and five modules that still name it name it to explain
why they do not use it. Full account in `714`.

## What did not move

```text
production_rollout             false    not authorized, no branch sets it
controlled_customer_pilot      false    not authorized, no branch sets it
verified_operational_binding   false    Gate 113 refuses one on a demo org
customer_persistence_live      false
awarded_operational_tracking   false
tenant_digest_operational      false
source_monitoring_live         false
email_delivery                 false
object_store_configured        false
```

No email was sent. Nothing in the invite path can send one — the table does not
store an address, only the domain half and a fingerprint of the subject.

No real organization was touched, no real customer data was written, and no
invite was written to the dev database.

## Two defects found while measuring

**`evaluate_invite` does not refuse a self-invite.** Asked to evaluate the owner
inviting themselves, approved by themselves, it returns no blocked reasons —
every seat and role check passes, and each one passes honestly, because they are
all about the same person. Refused in the repository by name on every dialect,
and by a CHECK on PostgreSQL.

**The mention detector matched substrings.** `require_demo_org` is a prefix of
`require_demo_org_session`, the replacement all fourteen converted modules were
moved onto, so the detector reported every one of them as still discussing the
header. Word-bounded now. Tenth instance in this campaign.

## Next

```text
1  a second person signs in through /api/auth/login with a Google account
2  the owner issues an invite for the demo organization and approves it
3  that person accepts it; a membership is created naming the invite
4  invite_binding_passed becomes true, measured, and customer_auth_live with it
```

Step 1 is the one nobody here can do. Everything behind it is built and
exercised against real rows, including the completed branch — see the last
section of `712`.

After that, and separately: `verified_operational_binding` needs a real
organization, which needs the write path recorded as missing in `705`, which
needs a decision that is not this one.
