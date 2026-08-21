# Auth Provider Decision Matrix (Gate 16 / Block 37)

## Recommendation

**Auth0 / OIDC + invite/allowlist org binding** (`auth0_oidc`)

Keep fixture/internal auth for demo/tests until secrets are provisioned and login is validated.

## Options compared

| Provider | Sunday feasibility | Production suitability | Recommendation |
|----------|--------------------|------------------------|----------------|
| Fixture/internal | already in place | not suitable | keep for demo/tests |
| External pilot allowlist | after owner choice | pilot only | pair with OIDC |
| Google OAuth/Workspace | conditional | good for pilot | if orgs on Google |
| Auth0/OIDC | conditional | strong | **recommended default** |
| Supabase Auth | low (not in stack) | conditional | reject unless adopted |
| Custom auth | not feasible | not recommended | reject |
| Production not supported | honest status | not supported | keep as status |

## Current claims

* external_auth_configured: **false**
* login_live_claimed: **false**
* production_auth_claimed: **false**
* controlled customer pilot: **NO_GO**

## Owner action

Select Auth0/OIDC (or Google if Workspace-only), provision secrets, validate callback. Do not claim login live until validated.
