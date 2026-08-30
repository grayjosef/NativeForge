# 656 — Gate 121A: auth activation preflight survey

Read before implementing. Every answer below was measured, not recalled.

No environment value appears in this document. Where a value would be the
answer, the answer is a key name and a boolean.

## The eleven questions

```text
1  the current activation gates              16 auth, 11 login
2  satisfied                                 5
3  unsatisfied                               11
4  require code                              0
5  require operator configuration            5
6  require provider-side configuration       2
7  require database migration application    1, and it is not counted as a gate
8  require a live callback smoke             3
9  satisfiable without external config       none
10 readiness service lying by proxy          none found this gate
11 exact next operator actions               below
```

## 1–3. Where the gate stands

```text
satisfied (5)
  callback_route_available
  session_cookie_policy_available
  organization_id_resolution_available
  membership_verification_available
  rls_claim_guard_available

unsatisfied (11)
  provider_configured
  secret_present
  issuer_configured
  audience_configured
  session_signing_key_ready
  issuer_jwks_validated
  role_mapping_passed
  callback_session_validated
  invite_binding_passed
  org_binding_passed
  dev_header_disabled_for_production
```

`customer_auth_live: false`, `login_live: false`, and the owner approval
variable is absent.

The five satisfied gates are all *code* gates — things NativeForge builds.
Every gate that is still false depends on something outside this repository.

## 4–8. What kind of action each blocker needs

This is the classification the whole gate exists to produce.

```text
operator_env (5)
  provider_configured        OIDC_ISSUER + OIDC_CLIENT_ID + OIDC_CLIENT_SECRET
  secret_present             OIDC_CLIENT_SECRET
  issuer_configured          OIDC_ISSUER
  audience_configured        OIDC_AUDIENCE
  session_signing_key_ready  NF_SESSION_SIGNING_KEY, from an environment or a
                             secret manager. The committed fixture key is
                             disqualified by source, not by length.

provider_side_plus_config (1)
  role_mapping_passed        roles defined in the provider console AND mapped
                             explicitly here. Unknown roles grant nothing.

provider_side_plus_network (1)
  issuer_jwks_validated      requires fetching the issuer's JWKS. This is a
                             network call and it is off by default.

live_callback_smoke (3)
  callback_session_validated a real browser completing a real redirect
  invite_binding_passed      the same, exercising the invite path
  org_binding_passed         the same, resolving to an organization_id and a
                             membership record

code_then_operator (1)
  dev_header_disabled_for_production
                             15 route modules depend on X-NF-Org-Id. The code
                             work is replacing it; the operator work is turning
                             it off afterwards.
```

**Zero gates are code-only.** That is the headline. Everything NativeForge can
do alone for customer auth has been done, and the campaign has reached the point
where the next move belongs to somebody with provider credentials.

## 7. The database, which is not a gate and blocks anyway

```text
migration_defined      true
migration_applied      false
alembic head           0030
```

No runtime database has applied any of it. This is not one of the sixteen
activation gates and it does not need to be — but a login that completes and
then cannot write a redirect state row has failed in a way no gate would have
caught. The preflight reports it separately as `database_revision_ready`.

The required revision for the auth path is **0030**: `nf_auth_redirect_states`
is what `/login` and `/callback` need between them.

## A defect found by this survey: the callback URL points nowhere

```text
configured callback_url     http://localhost:5173/auth/callback
API callback route          /api/auth/callback
frontend route at /auth/callback   none - the frontend declares no routes
```

The only occurrences of `/auth/callback` in the frontend tree are inside a
committed demo JSON snapshot that embeds this same config schema's output.

So the value an operator would copy into the provider console today points at a
path that exists in neither the API nor the frontend. Registering it and
completing a login would land the browser on a 404 holding an authorization
code — the code would then be burned, and the failure would look like a provider
problem rather than a configuration one.

`environment_scope` is `local_dev_checklist` and `human_review_required` is
true, so the value has never claimed to be production-correct. It has also
never been checked against anything. Gate 121C checks it:
`callback_route_matches_redirect_uri`.

## 9. Nothing can be satisfied from inside this repository

Stated explicitly because it is the useful conclusion. There is no code change
that moves any remaining gate. A gate that a future session could satisfy by
writing more services would be worth naming here; none exists.

## 10. Readiness proxy audit

Gate 120 found `repository_available` measured by probing for a **filename** —
a detector reporting a naming convention rather than a capability. This survey
looked for more of the same across every `*readiness*` service:

```text
awarded_grants_requirements_readiness_service      6 module probes
customer_auth_route_readiness_service              4
tenant_beta_readiness_service                      5
tenant_nofo_digest_readiness_service               5
tenant_customer_org_binding_store_readiness_service 4
dev_org_header_shutdown_readiness_service          2
source_scheduler_readiness_service                 6 module + 1 file probe
backup_restore_readiness_service                   1 file probe
```

Every one of those probes names its field `*_available` and reports exactly what
it measured: whether a module can be imported. That is honest — "a contract
exists" is a real fact and the field says so.

The Gate 120 defect was different in kind: `repository_available` claimed a
*capability* (something can address this table) from a *filename*. No second
instance of that pattern was found.

One derivation worth recording as correct rather than suspicious:
`auth_replacement_available` is false while `auth_replacement_routes_available`
is true. The routes exist and enforce; the replacement is not available because
`ready_for_live_login` is false. A route that refuses everybody is not a
replacement for the dev header.

## 11. Exact next operator actions

In dependency order. Each is out-of-band; none is a code change.

```text
1  Auth0/OIDC tenant exists, application created
2  set OIDC_ISSUER, OIDC_CLIENT_ID, OIDC_CLIENT_SECRET, OIDC_AUDIENCE
3  set NF_SESSION_SIGNING_KEY from an environment or a secret manager
4  decide the real redirect URI and register it provider-side, then set the
   same value here. It must match a route that can consume a callback.
5  apply migrations to the runtime database, to head 0030
6  define roles in the provider and map them explicitly
7  run the callback smoke once, with a real browser
8  replace X-NF-Org-Id across 15 route modules, then disable it
9  set NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL
```

Steps 1–4 are the ones that unblock the most at once. Step 9 is last on purpose:
the approval variable is an owner's signature, not a switch, and signing before
1–8 would authorize an activation that cannot happen.

## Implementation constraints carried out of this survey

```text
1  key names and booleans only; no environment value in any output or artifact
2  network_validation_allowed and jwks_network_check_allowed default false and
   nothing in this gate raises them
3  the callback comparison is host + path only, and the redirect URI is
   redacted before it reaches an artifact
4  database_revision_ready is detected, not asserted, and its absence is
   reported separately from the sixteen gates
5  provider_ready requires every non-network gate; a network check that never
   ran is `unvalidated`, never `failed`
6  the runbook's verification commands must not echo a value - presence checks
   only, and anything that could print a secret is written to /tmp
7  every new conjunct both derived and injectable, or its branch is unreachable
8  no gate may be satisfied by this gate; the preflight measures, it does not
   activate
```
