# Gate 136 — the blocker, if the verifier still says BLOCKED

## `invite_binding_passed`

Which of the counts is zero says which step has not happened:

```text
invite_rows                          0   step 2 has not run
accepted_invite_rows                 0   step 3 has not run, or it refused
memberships_from_a_completed_invite  0   step 3 refused after accepting,
                                         which cannot persist - it rolls back
```

And one that is not zero:

```text
memberships_matching_an_accepter_by_identity_only  >0
```

means somebody holds a membership *and* accepted an invite, and the membership
does not name it. That is the exact state migration 0039 exists to stop passing
as evidence. It is reported rather than counted, so the near-miss is visible.

## `owner_activation_decision`

Blocked means the recorded decision does not cover this call. It is checked per
call against the organization, the provider and the environment, so:

```text
organization_outside_the_approved_scope   not bbbbbbbb-cccc-dddd-eeee-ffffffffffff
provider_outside_the_approved_scope       OIDC_ISSUER is not Google
environment_outside_the_approved_scope    NF_APP_ENV is not one of
                                          ['dev', 'local', 'test']
decision_revoked_by_environment           the revocation variable is set
```

## `login_live`

If this is blocked, Gate 133's work has regressed and the invite is not the
problem. Run `./scripts/verify_nativeforge_demo_live_stack.sh` first.

## `gate_says_live_while_measurements_say:...`

The gate claims `customer_auth_live` and the rows do not agree. Worse news than
a blocker: one of the two is wrong. The verifier will not pick which, and this
is the one output that should stop everything.

## What is NOT the blocker

```text
production rollout            not authorized, and not what this gate is
controlled customer pilot     not authorized, and not what this gate is
verified_operational_binding  false by Gate 113's contract on a demo org,
                              and not in REQUIRED_AUTH_GATES
email delivery                nothing can send one; the invite table has
                              no column for an address to send to
```
