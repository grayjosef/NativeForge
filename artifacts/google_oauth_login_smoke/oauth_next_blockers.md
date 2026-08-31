# Gate 130 — what is blocking a real Google login

## Cleared by this gate

The authorization endpoint. It was assembled as `issuer + "/authorize"`, which
is Auth0's convention. Google's is `/o/oauth2/v2/auth`, and its token and JWKS
endpoints are on different hosts entirely:

```text
                 was built as                       Google publishes
authorization    accounts.google.com/authorize      accounts.google.com/o/oauth2/v2/auth
token            accounts.google.com/oauth/token    oauth2.googleapis.com/token
jwks             accounts.google.com/.well-known/   www.googleapis.com/oauth2/v3/certs
                   jwks.json
```

A Google login built from the convention reaches a 404 before the user sees a
consent screen. Endpoints are now read from the provider's discovery document,
and for an issuer known not to follow the convention no endpoint is produced at
all rather than a wrong one.

With Google's metadata supplied, the authorization URL now targets
`https://accounts.google.com/o/oauth2/v2/auth` and reports
`authorization_url_available: True`.

## Not cleared, and not this agent's to clear

```text
1  a Google OAuth client does not exist
2  the seven env values are unset          0 of 7 present
```

Creating the client requires the Google Cloud console under the owner's account,
and the client secret is displayed there. This agent does not authenticate to
the owner's Google account and does not transcribe a client secret.

## What the owner does

Follow `docs/operations/690_GATE129_BROWSER_GOOGLE_OAUTH_SETUP_PROMPT.md`. The
values it names are unchanged and correct:

```text
authorized JavaScript origin   https://nf-dev.mayhem-nc.dev
authorized redirect URI        https://nf-dev.mayhem-nc.dev/api/auth/callback
```

No trailing slash, and `/api/auth/callback` rather than `/auth/callback`.

Then set the seven keys and restart:

```bash
systemctl --user restart nativeforge-backend.service
```

## Then, and only then

A browser already holding a Cloudflare Access session for the host starts login,
Google redirects to the callback, state and PKCE validate, and
`/api/auth/current-user` answers with an identity or a named org-binding
blocker. Until a browser completes that, `login_live` and `customer_auth_live`
stay false — configuration is not authentication.

## Current activation blockers

```text
callback_url_does_not_match_a_route
dev_header_still_in_place
owner_authorization_absent
provider_configuration_missing
role_mapping_not_validated
secret_configuration_missing
signing_key_not_fit_to_sign
```
