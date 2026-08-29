# 646 — Gate 118: readiness delta

What changed, what did not, and the sentence to refuse.

## The sentence to refuse

> "NativeForge has a session format and a verifier, so sessions work."

The format exists, the verifier runs, and **no cookie can verify**, because no
signing key is configured. `session_cookie_valid` is false for every cookie in
the real environment, and ten of fifteen activation gates remain unsatisfied.

## What moved

```text
                                       before   after   why
session format                         none     nf1.*   signed, expiring
session verifier                       none     6 checks
redirect state store contract          none     4 scopes, single-use
session_cookie_valid derivation        constant measured
/session reports why a cookie failed   no       yes     booleans, never a value
/callback reports the state store      no       yes     contract_only scope
```

## What did not move

```text
session_signing_key_present            false
session_cookie_valid (real env)        false
state_store_production                 false    contract_only scope
customer_auth_live                     false
login_live                             false
missing activation gates               10, unchanged
provider_configured                    false
secret_present                         false
ready_for_live_login                   false
customer_persistence_live              false
operational_awarded_tracking_ready     false
operational_digest_ready               false
beta_onboarding_ready                  false
dev header production safe             false
source_monitoring_live                 false
source_coverage_claimed                false
```

## A derived false became a measured false

Gate 117's dependency read:

```python
# No session format exists, so no cookie can be valid.
valid = False
```

That was a derivation with nothing behind it. The cookie is now parsed, its
signature checked, its expiry compared and its organization validated — and it
comes out invalid for a nameable reason:
`no_signing_key_available_so_nothing_can_be_verified`.

Same answer, different epistemics. `/api/auth/session` now reports
`cookie_parseable`, `signature_valid` and `session_expired` as separate
booleans, so a caller learns which check failed.

## Two defects found and fixed during the gate

**A store is not a consume.** Both operations returned the same shape, and the
invariants judged a successful store by whether consumption was allowed — which
is false for every store, correctly, and was reported as an unexplained refusal.
An `operation` field now names which call produced a result.

**`ready_for_live_login` became unreachable, again.** Adding a signing-key
requirement as an invariant without adding it as a *conjunct* meant the service
could produce a result that failed its own invariant, and the permitted branch
could not be reached in a test. The key is now both a conjunct and injectable —
the same lesson Gate 117 learned one conjunct earlier.

## A fourth substring false positive

Searching for `SECRET_KEY` returns five hits. All five are **redaction
regexes** — services scanning *for* secret-shaped keys in order to suppress
them:

```python
_SECRET_KEY_RE = re.compile(...)
if _SECRET_KEY_RE.search(str(k)):   # suppress this key
```

The opposite of a signing key. After Gate 117's `S256`/`RS256`, Gate 116's
`api/auth.py` counted as a dev-header dependant for documenting why it does not
use one, and Gate 118A's `authorization_url` hits landing in Gate 116B's
docstring explaining that no authorization URL exists.

## No table, no session, no credential committed

```text
database table added            no - it would be a table nothing writes to
production sessions created     none
real users created              none
session cookie committed        none
state value committed           none
PKCE verifier committed         none
signing key committed           none (the fixture key signs nothing)
provider contacted              no
network call made               no
```

The artifact writer refuses on three independent checks: nested credential field
names, fixture values by content, and every configured `OIDC_*` environment
value. A test plants a secret in the environment and asserts it reaches no file.

Alembic head remains **0029**.

## What the next gate needs

```text
1. a signing key                 owner supplies NF_SESSION_SIGNING_KEY
                                 out-of-band. This is the single thing between
                                 the verifier and a cookie that could verify.

2. the redirect flow, live       /login issues a state and a verifier, stores
                                 them, and returns an authorization URL; the
                                 store moves to a database scope

3. owner supplies OIDC_*         provider_configured, secret_present,
                                 issuer_configured, audience_configured

4. network_call_allowed          turned on deliberately, under review

5. replace the dev header        15 modules depend on it

6. owner authorizes              NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL
```

Steps 1 and 2 are the honest next move, and they belong together: a signing key
with no flow issues nothing, and a flow with no key signs nothing.
