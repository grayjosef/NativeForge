# 711 — Gate 135: customer auth activation survey

Measured before anything was implemented.

## Numbering

The brief asked for `708_GATE135_...` and `709`–`712`. Gate 134 committed
707–710 in the previous gate, so Gate 135 uses 711–715. Third numbering
collision in four gates; recorded rather than overwritten.

Three of the modules named for survey do not exist:
`customer_identity_repository_service`, `org_membership_repository_service`,
`customer_auth_current_user_service`. Their responsibilities live in
`dev_org_membership_bootstrap_service`, `identity_org_session_resolution_service`
and `api/auth.py::current_user`. Fifth gate running where a brief names modules
nobody built.

## Exact current `customer_auth_live` blockers

```text
invite_binding_passed                false
owner_has_not_authorized_customer_auth_activation
```

Everything else in `REQUIRED_AUTH_GATES` passes, including
`dev_header_disabled_for_production`, which Gate 134 cleared.

## Where `invite_binding_passed` is computed

```python
# auth0_live_validation_runner_service
def run_auth0_live_validation(*, invite_binding_passed: bool = False, ...)
```

A parameter no caller passes. The same shape as `org_binding_passed` and
`role_mapping_passed` before Gates 132 and 133 — the fifth instance in this
campaign of a gate reading a value nobody supplies.

## Does `membership_invite_approval_service` have a real write path?

**No.** It is 694 lines of decision logic — `evaluate_invite`,
`evaluate_membership_provenance`, `evaluate_role_change`,
`evaluate_membership_revocation`, `evaluate_membership_expiry` — with no
`sa.insert`, no connection parameter, and `persisted: False` on every result.

It also has **zero callers anywhere in `src/`**. The same state
`oidc_organization_id_resolution_service` was in before Gate 132.

## What the contract actually requires

```python
MEMBERSHIP_PROVENANCES = {"completed_invite", "operator_direct_write",
                          "migration_backfill", "unknown"}
TRUSTED_PROVENANCES   = {"completed_invite"}
```

> "a membership that did not come through a completed invite is not trusted,
> however well-formed its other columns are. An operator direct-write is the
> specific case this exists to refuse."

Run against the demo organization's real membership:

```text
identity        24df6919-…            (Gate 132's Google identity)
role            org_owner
membership_source  org_owner_approved
approved_by     itself                (the bootstrap: nobody else existed)
invited_by      NULL
provenance      operator_direct_write

evaluate_membership_provenance -> trusted: False
                                  untrusted_membership_provenance:operator_direct_write
```

And a claimed invite without one named:

```text
completed_invite_provenance_without_invite_id
```

The contract refuses an unfalsifiable claim, which is correct.

## Can the invite flow be executed for the demo org?

The *decision* half, yes. Run for real against the demo organization, owner
inviting a second person, approved and accepted:

```text
allowed                          true
can_activate_membership          true
membership_state_after_acceptance active
consumes_seat                    true      (seat_cap 5, seat_count 1)
blocked_reasons                  []
persisted                        FALSE
```

So the contract permits it and records nothing. That is the seam this gate has
to build.

### And the half that cannot be executed

A **completed** invite needs an invitee who accepts it. Accepting means
authenticating: the membership is created for a verified identity. The demo
organization has exactly one identity — the org owner — and one membership.

The owner cannot complete an invite to themselves. One membership per identity
per organization is a unique constraint, and an invite whose requester,
approver and invitee are the same person is self-dealing, which is the thing the
contract exists to prevent.

So a completed invite into this organization needs a **second real person to log
in**. Inventing one would be faking a user, which the hard rules forbid and
which would make the evidence worthless anyway.

### One gap found while measuring

`evaluate_invite` does **not** refuse a self-invite. Asked to evaluate the owner
inviting themselves, approved by themselves, it returns no blocked reasons. The
seat and role checks all pass because they are all about the same person. Worth
a guard, and recorded here whether or not one lands.

## Can a verified operational binding exist for the demo org?

No, unchanged from Gates 132–134. Gate 113's contract refuses a
`verified_binding` on a demo organization — a demo binding may not carry a
verifier — so the demo organization's binding is a `demo_fixture` and
`verified_operational_binding` stays false. It is not in `REQUIRED_AUTH_GATES`,
so it does not block `customer_auth_live`; it is reported beside it.

## Where owner approval must be recorded

Two decisions, deliberately separate since Gate 133D:

```text
login activation      customer_auth_owner_activation_decision_service
                      demo org, Google, dev/demo. Records login_live only, and
                      approves_customer_auth_live() has no branch returning True.
customer auth         NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL, an env var compared
                      against a fixed token. Unset.
```

Gate 135D adds a third: a **controlled dev customer-auth activation** decision,
narrower than the env var and separate from the login one.

## Can `customer_auth_live` be true in dev/demo without production rollout?

Yes — they are different claims and always have been. `customer_auth_live`
means customer authentication works and is switched on; `production_rollout` and
`controlled_customer_pilot` are separate flags that no gate here sets. Nothing in
`REQUIRED_AUTH_GATES` mentions either.

## Which dev-header chains are dead

Measured with word boundaries, because `require_demo_org` is a substring of
`require_demo_org_session` and a plain grep reports fourteen converted route
modules as consumers. Tenth substring-versus-meaning false positive in this
campaign.

```text
deps_db.get_org_context_with_db        code consumers: 0
deps_db.require_demo_org_db            code consumers: 0
deps_db.require_real_org_db            code consumers: 0
isolation_deps (whole module)          code consumers: 0
get_dev_org_context_explicit_only      code consumers: 0
```

Everything else that names them does so in prose: `api/auth.py` explaining why
it does not use one, `capability_guard.py` describing the header, Gate 134's
replacement explaining what it replaced, and `rls_context_claim_guard_service`
quoting the original function in a docstring.

`deps_db.get_db_session` is **not** dead — thirteen route modules still import
it. Only the three org-context functions go.

## Is deleting them safe?

Yes, with two conditions:

```text
1  the tests that exercise them directly must move to asserting removal -
   deleting a dependency and its test in one change removes the proof with it
2  the detectors that count consumers must keep working; several read
   `api/*.py` for these names and would see an empty directory listing rather
   than a finished migration if the file simply vanished
```

`NF_DEV_ORG_HEADERS=false` stays safe: after deletion nothing reads the header
at all, which is stronger than nothing depending on it.

## What can safely be activated in this gate

```text
CAN     delete the three dead chains
CAN     build the invite persistence seam, and record a real invite
CAN     record the controlled dev customer-auth activation decision
CAN     derive invite_binding_passed from rows instead of a parameter

CANNOT  complete an invite - it needs a second real person to authenticate
CANNOT  therefore claim invite_binding_passed, and therefore
CANNOT  claim customer_auth_live
CANNOT  verified_operational_binding on a demo organization
CANNOT  production rollout or controlled pilot - not authorized, not measured
```
