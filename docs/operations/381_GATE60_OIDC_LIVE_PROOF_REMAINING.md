# 381 — Gate 60: OIDC live proof remaining

Gate 60 implemented token verification. It did **not** make customer login live,
and this document is the checklist that stands between the two.

## Current flag state

```text
TOKEN_VERIFICATION_IMPLEMENTED = True    # Gate 60: real RS256 verifier exists
LIVE_AUTH0_TOKEN_PROVEN        = False   # no live Auth0 token has ever verified
login_live_claimed             = False
customer_login_live_claimed    = False
```

Strict readiness now fails for a **different reason** than before Gate 60. The
blocking reason moved rather than disappearing:

```text
before Gate 60:  blocked_reason=token_verification_path_not_implemented
after  Gate 60:  blocked_reason=live_auth0_token_not_proven
```

Verified behaviour:

```text
no config,   default  -> RESULT=PASS   (demo must keep running)
no config,   --strict -> RESULT=FAIL   missing_required_config + live proof absent
full config, --strict -> RESULT=FAIL   live_auth0_token_not_proven
```

## Auth0/OIDC inputs still needed from the owner

Supplied out-of-band, never committed:

| Env var (canonical) | Purpose |
| --- | --- |
| `OIDC_ISSUER` | Auth0 tenant issuer URL |
| `OIDC_AUDIENCE` | API identifier the token is minted for |
| `OIDC_JWKS_URL` | JWKS endpoint for the tenant |
| `OIDC_CLIENT_ID` | application client id |
| `OIDC_CLIENT_SECRET` | only if a confidential client is used |

`NATIVEFORGE_OIDC_*` is accepted as an alias for each. `config_source_keys`
reports which spelling registered, so a typo is visible rather than silent.

## Proof required before `login_live` can become true

Every item must be evidenced, not asserted:

1. **Real OIDC issuer** configured and reported present.
2. **Real audience / client id** configured.
3. **Real JWKS URL** configured, and JWKS retrievable — with the fetch's
   timeout and fail-closed behaviour exercised, not just its happy path.
4. **Live token from Auth0** obtained through an actual login.
5. **Signature verified** against the live JWKS (not the test keypair).
6. **Issuer verified** against the live issuer.
7. **Audience verified** against the live audience.
8. **exp / nbf verified** on the live token.
9. **Subject mapped** to a stable identifier.
10. **Membership mapped from a trusted source** — a real directory, with
    `membership_source="verified_directory"`. A token alone never proves
    membership; this is the item with no implementation at all today.
11. **Role mapped from a trusted source** — same directory, same rule.
12. **`login_claim_resolver` / `login_live_promotion_gate` updated** — that
    service already defines the 10 required gates and remains the authority.
13. **Tests / runbook evidence captured** — the live verification recorded as an
    artifact, with a rerunnable procedure.

Only when 1–13 hold may `LIVE_AUTH0_TOKEN_PROVEN` be flipped, and only then can
`login_live` be considered. Flipping either flag without the evidence would make
every downstream claim in the product false.

## Item 10 is the real remaining work

Items 1–9 are configuration plus one live login. Item 10 — a **trusted membership
directory** — has no implementation whatsoever. Gate 51 modelled memberships as
a contract over caller-supplied state; nothing populates it from a store, and
`verified_directory` is currently an allowlist entry with no producer.

Until that exists, even a perfectly verified live Auth0 token yields
`membership_trusted=False` and therefore `may_act_as_customer=False`. Token
verification was the missing *first* link; membership is now the missing *second*.

Membership storage also depends on the production storage approval, which is
owner-blocked. So the honest sequencing is:

```text
owner: OIDC creds  ->  live token proof (items 1-9)
owner: storage approval  ->  membership directory (item 10)
                         ->  role mapping (item 11)
                         ->  capability on live routes
```

## Why Cloudflare Access is still not customer login

Access protects `nf-dev.mayhem-nc.dev` and proves someone cleared an **operator**
gate. It carries no organization membership and no customer role. A tribal grant
officer's authority to act for their organization is a different fact entirely
from "this person reached the demo URL".

Enforced structurally, not by convention:

- `identity_from_cloudflare_access` returns `demo_operator`, never `oidc_verified`
- `cloudflare_access` is absent from `TRUSTED_VERIFICATION_SOURCES`
- two invariants fail any record treating Access as customer login or as trusted
  verification
- tests assert an Access identity cannot hold customer authority

This is the conflation most likely to cause a real incident — an operator session
being mistaken for an organization's authority — so it is blocked in the type
system, the invariants, and the tests rather than in prose alone.
