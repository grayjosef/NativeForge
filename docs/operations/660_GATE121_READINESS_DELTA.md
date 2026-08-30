# 660 — Gate 121: readiness delta

What changed, what did not, and the sentence to refuse.

## The sentence to refuse

> "The preflight exists, so we know how to turn auth on."

The preflight says what is missing. Nothing in it configures anything.

**Eleven of sixteen** activation gates are unsatisfied, and the finding that
matters most is this: **not one of them can be satisfied by writing code.** Five
need environment variables, two need provider-console work, three need a real
browser completing a real redirect, and one needs fifteen route modules changed
and then a switch thrown.

Everything NativeForge can do alone for customer auth has been done.

## What moved

```text
                                  before      after
environment preflight             none        key names and booleans
provider readiness                none        10 gates, all measurable offline
operator runbook                  none        28 items, 9 sections, 6 do-not-do
activation blockers               a gate list named by who has to act
callback URL correctness          unchecked   measured, and it is wrong
database revision readiness       unreported  reported beside the gates
```

## What did not move

```text
customer_auth_live                     false
login_live                             false
provider_configured                    false
secret_present                         false
session_signing_key_ready              false
verified_operational_binding           false
operator_authorization_present         false
customer_persistence_live              false
beta_onboarding_ready                  false
production_rollout_ready               false
source_monitoring_live                 false
source_coverage_claimed                false
production verified bindings created   0
real customer rows written             0
real users created                     0
production sessions created            0
provider contacted                     no
network call made                      no
alembic head                           0030, unchanged
```

## The defect this gate found

```text
configured callback   http://localhost:5173/auth/callback
API callback route    /api/auth/callback
frontend route        none - the frontend declares no routes at all
```

The only occurrences of `/auth/callback` in the frontend tree are inside a
committed demo JSON snapshot that embeds this same config schema's output.

The value an operator would copy into the provider console today points at a
path that exists in neither the API nor the frontend. Registering it and
completing a login would land a real browser on a 404 **holding a live
authorization code** — the code would then be burned, and the failure would look
like a provider problem rather than a configuration one.

`environment_scope` is `local_dev_checklist` and `human_review_required` is
true, so the value never claimed to be production-correct. It had also never
been checked against anything. Two gates now check it:
`callback_path_matches_route` and `callback_route_matches_redirect_uri`, and a
test pins the current false so a fix is noticed.

## The eight named blockers

The activation gate now classifies its refusal by who has to act:

```text
provider_configuration_missing        operator: three env keys
secret_configuration_missing          owner: a secret manager
signing_key_not_fit_to_sign           owner: a secret manager
database_revision_not_applied         operator: alembic upgrade head
callback_url_does_not_match_a_route   operator + provider admin
role_mapping_not_validated            provider admin + engineering
dev_header_still_in_place             engineering, then operator
owner_authorization_absent            owner, last
```

"Auth is not configured" was true and unactionable. This is the same refusal,
addressed to somebody.

## Two false positives, both in my own detectors

**The leak scanner fired on intended output.** It checked every key the preflight
inspects, including `NF_PUBLIC_ORIGIN` — and the redacted callback URL correctly
contains the public origin. Narrowed to the four keys whose values are genuinely
secret. A leak detector that fires on intended output trains people to ignore
it.

**The command scanner refused one of my own commands.** A shell loop printing
key *names* was refused because a scanner cannot tell a name from a value. The
fix was to change the command, not the rule — it now asks the preflight, which
already guarantees names-only output and is tested for it.

## One branch had to be made reachable

`build_environment_preflight` initially read the cookie policy and dev-header
facts from the real environment only, which made zero-blockers impossible to
reach and every refusal above it unfalsifiable. Both are now injectable, and a
test drives the preflight to **zero blocked reasons and zero next required
actions** — with `customer_auth_live` still false, because a preflight measures
and does not activate.

Gates 117, 118, 119 and 120 each shipped that same defect once. This is the
fifth.

## The fixture staircase

Eight cases walk one hypothetical deployment from nothing configured to
everything configured, each adding exactly one thing:

```text
1  all_missing
2  + issuer, client id, audience
3  + client secret
4  + signing key                          callback still points nowhere
5  + a callback that matches a route      database still empty
6  + a migrated database                  roles still unmapped
7  + mapped roles
8  + the owner's signature                and auth is STILL not live
```

A set where every case failed differently would prove each check works in
isolation. A staircase proves the order is right — that fixing step 3 does not
accidentally satisfy step 5.

Case 8 is the point of the set. Every preflight gate green, the owner's
signature present, and `customer_auth_live: false`, because three of the sixteen
gates need a real browser and nobody has run one.

## Next operator actions, in dependency order

```text
1  create the provider application
2  set OIDC_ISSUER, OIDC_CLIENT_ID, OIDC_CLIENT_SECRET, OIDC_AUDIENCE
3  set NF_SESSION_SIGNING_KEY from an environment or secret manager
4  fix the redirect URI so it matches a route, and register it provider-side
5  apply migrations to the runtime database, to head 0030
6  define provider roles and map them explicitly
7  run the callback smoke once, with a real browser
8  replace X-NF-Org-Id across 15 route modules, then disable it
9  set NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL
```

Steps 1–4 unblock the most at once. Step 9 is last on purpose: the approval
variable is an owner's signature, not a switch, and signing before 1–8 would
authorize an activation that cannot happen.

## What none of it did

```text
secrets printed or committed          none
environment values printed            none
env values in any artifact            none - key names and booleans only
provider called                       no
URL fetched                           no
collector executed                    no
scraper activated                     no
email sent                            no
customer data written                 none
production verified bindings          0
real users created                    0
production sessions created           0
```

The artifact writer refuses on four independent checks: nested credential field
names, unredacted URLs, unsafe runbook commands, and every configured `OIDC_*`
environment value. A test plants a secret in the environment and asserts it
reaches no file; three more assert each new scanner actually fires.
