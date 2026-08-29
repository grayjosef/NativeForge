"""Customer session cookie policy (Gate 116B).

What a NativeForge session cookie must be, decided before any session exists.

## A policy is not a session

This service defines attributes. It sets no cookie, mints no session value and
knows nothing about any user. `sessions_live` is a constant `False` with an
invariant behind it, because "we have a session cookie policy" is one short step
from "we have sessions" and the two are not related.

Gate 116A found zero cookie handling anywhere in NativeForge — no `set_cookie`,
no `SameSite`, no `Response` import in the whole `api/` package. Nothing
constrains this policy, which means nothing excuses getting it wrong either.

## The non-negotiables

```text
http_only    true      a session readable by script is a session stealable by
                       one, and the frontend has no reason to read it
same_site    lax       enough to stop cross-site POSTs carrying the session,
                       loose enough that the OIDC redirect back from the
                       provider still arrives with it
secure       true      required for production_safe; false in local dev over
                       http, and that is exactly why local dev is not
                       production safe
```

`same_site=strict` would break the callback: the browser arrives at
`/api/auth/callback` from the provider's origin, and a strict cookie would not
be sent. `lax` sends cookies on top-level GET navigations, which is what a
callback is. Both are permitted by the policy vocabulary; `lax` is chosen and
the reason is recorded rather than left to be rediscovered.

## PKCE is required, and nothing in this repository proves otherwise

The brief allows `pkce_required` to be false if the existing OIDC flow proves it
unnecessary. Gate 116A searched every service module:

```text
pkce  0    code_verifier  0    code_challenge  0
authorization_url  0    token_exchange  0
```

There is no existing flow. An absent flow proves nothing, and "no evidence
against" is not evidence for. PKCE stays required.

## production_safe is derived and currently false

```python
production_safe = (
    http_only and secure and same_site in {"lax", "strict"}
    and csrf_required and state_required and pkce_required
    and rotation_required and logout_clears_cookie
    and max_age_seconds <= MAX_SESSION_SECONDS
)
```

Under the default local-dev environment `secure` is false, so `production_safe`
is false — with a named reason rather than a shrug. A test forces a production
environment and asserts the true branch is reachable, so today's false is a
measurement.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_customer_session_cookie_policy_v1"

COOKIE_NAME = "nf_session"

# The only values a session cookie may carry. `none` is deliberately absent:
# SameSite=None requires Secure and permits the cookie on cross-site subrequests,
# which is the property CSRF depends on.
ALLOWED_SAME_SITE: frozenset[str] = frozenset({"lax", "strict"})

# Chosen rather than defaulted. See the module docstring: strict would not be
# sent on the top-level navigation back from the identity provider.
DEFAULT_SAME_SITE = "lax"

DEFAULT_PATH = "/"

# Eight hours. Long enough for a working day, short enough that a stolen cookie
# expires before the next one. Rotation is separately required.
DEFAULT_MAX_AGE_SECONDS = 8 * 60 * 60

# A session that outlives a week is a credential, and credentials belong in a
# provider rather than in a cookie.
MAX_SESSION_SECONDS = 7 * 24 * 60 * 60

POLICY_FIELDS: tuple[str, ...] = (
    "cookie_name",
    "http_only",
    "secure",
    "same_site",
    "path",
    "domain",
    "max_age_seconds",
    "csrf_required",
    "state_required",
    "pkce_required",
    "rotation_required",
    "logout_clears_cookie",
    "production_safe",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _production_environment(app_env: str | None = None) -> bool:
    if app_env is not None:
        return str(app_env).strip().lower() in {"prod", "production"}
    try:
        from nativeforge.lib.settings import get_settings

        return str(get_settings().app_env).strip().lower() in {"prod", "production"}
    except Exception:  # pragma: no cover - settings always load here
        # Unknown is not production. Claiming production would flip `secure`
        # true and make a local policy look production-safe.
        return False


def build_session_cookie_policy(
    *,
    app_env: str | None = None,
    secure: bool | None = None,
    same_site: str | None = None,
    max_age_seconds: int | None = None,
    domain: str | None = None,
) -> dict[str, Any]:
    """The session cookie contract. Sets no cookie and creates no session."""
    production = _production_environment(app_env)

    # Secure follows the environment unless a caller forces it, so a local dev
    # policy is honestly not production-safe rather than pretending.
    if secure is None:
        secure = production

    chosen_same_site = str(same_site or DEFAULT_SAME_SITE).strip().lower()
    age = int(
        max_age_seconds
        if max_age_seconds is not None
        else DEFAULT_MAX_AGE_SECONDS
    )

    # Constants, because none of them has a safe false branch.
    http_only = True
    csrf_required = True
    state_required = True
    pkce_required = True
    rotation_required = True
    logout_clears_cookie = True

    blocked_reasons: list[str] = []

    if chosen_same_site not in ALLOWED_SAME_SITE:
        blocked_reasons.append(f"same_site_out_of_vocabulary:{chosen_same_site}")
    if not secure:
        blocked_reasons.append("cookie_not_marked_secure_so_not_production_safe")
    if age <= 0:
        blocked_reasons.append("max_age_seconds_must_be_positive")
    if age > MAX_SESSION_SECONDS:
        blocked_reasons.append(
            f"max_age_seconds_exceeds_{MAX_SESSION_SECONDS}_second_ceiling"
        )

    # Derived affirmatively. Every conjunct must hold.
    production_safe = bool(
        http_only
        and secure
        and chosen_same_site in ALLOWED_SAME_SITE
        and csrf_required
        and state_required
        and pkce_required
        and rotation_required
        and logout_clears_cookie
        and 0 < age <= MAX_SESSION_SECONDS
        and not blocked_reasons
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "cookie_name": COOKIE_NAME,
            "http_only": http_only,
            "secure": bool(secure),
            "same_site": chosen_same_site,
            "path": DEFAULT_PATH,
            # No domain is set: a host-only cookie is not sent to subdomains,
            # and NativeForge has no cross-subdomain session requirement.
            "domain": domain,
            "max_age_seconds": age,
            "csrf_required": csrf_required,
            "state_required": state_required,
            "pkce_required": pkce_required,
            "rotation_required": rotation_required,
            "logout_clears_cookie": logout_clears_cookie,
            "production_safe": production_safe,
            "production_environment": production,
            "same_site_rationale": (
                "lax is sent on the top-level navigation back from the identity "
                "provider; strict would not be, and the callback would arrive "
                "without the session cookie"
            ),
            "pkce_rationale": (
                "no authorization-url builder, token exchange or code_verifier "
                "exists anywhere in this repository, so nothing proves PKCE "
                "unnecessary. An absent flow is not evidence."
            ),
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Constants: a policy defines attributes and creates nothing.
            "sessions_live": False,
            "real_sessions_created": False,
            "real_users_created": False,
            "cookie_set_by_this_service": False,
            "secret_value_emitted": False,
            "fabricated": False,
        }
    )


def policy_invariant_failures(policy: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if policy.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in POLICY_FIELDS:
        if field not in policy:
            fails.append(f"cookie_policy_missing_field:{field}")

    for constant in (
        "sessions_live",
        "real_sessions_created",
        "real_users_created",
        "cookie_set_by_this_service",
        "secret_value_emitted",
        "fabricated",
    ):
        if policy.get(constant) is not False:
            fails.append(f"cookie_policy_claimed:{constant}")

    # The non-negotiables, each with no safe false branch.
    if policy.get("http_only") is not True:
        fails.append("session_cookie_readable_by_script")
    if policy.get("state_required") is not True:
        fails.append("state_not_required")
    if policy.get("pkce_required") is not True:
        fails.append("pkce_not_required")
    if policy.get("csrf_required") is not True:
        fails.append("csrf_not_required")
    if policy.get("rotation_required") is not True:
        fails.append("session_rotation_not_required")
    if policy.get("logout_clears_cookie") is not True:
        fails.append("logout_does_not_clear_the_cookie")

    if policy.get("same_site") not in ALLOWED_SAME_SITE:
        fails.append("same_site_out_of_vocabulary")

    age = policy.get("max_age_seconds")
    if not isinstance(age, int) or age <= 0:
        fails.append("max_age_seconds_is_not_a_positive_integer")
    elif age > MAX_SESSION_SECONDS:
        fails.append("session_lifetime_exceeds_the_ceiling")

    # production_safe requires every one of them, and Secure above all.
    if policy.get("production_safe"):
        if not policy.get("secure"):
            fails.append("production_safe_without_secure")
        if policy.get("same_site") not in ALLOWED_SAME_SITE:
            fails.append("production_safe_with_an_invalid_same_site")
        if policy.get("blocked_reasons"):
            fails.append("production_safe_with_blocked_reasons")

    # A refusal must name itself.
    if not policy.get("production_safe") and not policy.get("blocked_reasons"):
        fails.append("policy_not_production_safe_without_a_reason")

    return fails
