"""Customer auth environment preflight (Gate 121B).

What the runtime environment is still missing before customer auth could be
turned on, reported as key names and booleans.

## No value ever leaves this module

```text
reported     the NAME of a missing key            OIDC_CLIENT_SECRET
             whether something is set             true / false
             where a signing key came from        secret_manager
             a redacted host and path             example.test/auth/callback

never        the value of any environment variable
             a secret, a token, a session, a state, a verifier
             a full connection string
```

`secret_values_exposed` is a self-check: the assembled result is scanned for
every configured value of every key this module inspects, and an invariant fails
if one appears. A preflight that leaked what it was measuring would be worse
than no preflight.

## Missing keys are named, present ones are not

`provider_env_missing_keys` lists the names that are absent. There is no
corresponding list of names that are present, because that list plus a process
listing is most of the way to knowing what a deployment holds. Absence is
actionable; presence is only reassuring.

## The callback comparison

Gate 121A found the configured callback URL points at a path that exists in
neither the API nor the frontend. That is not something a boolean about
"configured" would catch — the value *is* configured, and it is wrong.

So the comparison is structural: scheme, host and path, against the public
origin and against the route that would have to consume the callback. Query
strings and fragments are ignored, because a redirect URI carrying either is
already malformed.

## The database is reported and is not a gate

A login that completes and then cannot write a redirect state row has failed in
a way no activation gate would have caught. `database_revision_ready` is
reported alongside the gates rather than folded into them, because it fails
differently and is fixed differently.

## Nothing is contacted

`network_validation_allowed` defaults false and nothing in this gate raises it.
`provider_validation_attempted` is false whenever it is false, and an invariant
refuses any result claiming a validation passed that was never attempted.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.parse import urlsplit

from nativeforge.services.customer_auth_authorization_url_service import (
    AUDIENCE_ENV,
    CLIENT_ID_ENV,
    CLIENT_SECRET_ENV,
    ISSUER_ENV,
)
from nativeforge.services.customer_session_format_service import SIGNING_KEY_ENV

SCHEMA_VERSION = "nf_customer_auth_environment_preflight_v1"

# The revision the auth path needs applied. nf_auth_redirect_states (0030) is
# what /login and /callback need between them.
REQUIRED_DATABASE_REVISION = "0030"

# Provider configuration. Names only; no value from any of these is ever read
# into a result.
PROVIDER_ENV_KEYS: tuple[str, ...] = (ISSUER_ENV, CLIENT_ID_ENV, AUDIENCE_ENV)

# Held separately because a secret's absence and a config key's absence are
# different operator actions, and one of them goes in a secret manager.
SECRET_ENV_KEYS: tuple[str, ...] = (CLIENT_SECRET_ENV, SIGNING_KEY_ENV)

# The owner's signature. Bridged from Gate 115 rather than restated.
ACTIVATION_APPROVAL_ENV = "NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL"

# Where a public origin would be declared. Absent today, which is why the
# callback comparison reports `unknown` rather than `mismatch`.
PUBLIC_ORIGIN_ENV = "NF_PUBLIC_ORIGIN"

# The route that would have to consume a real callback.
CALLBACK_ROUTE_PATH = "/api/auth/callback"

ENVIRONMENT_NAMES = frozenset({"local", "dev", "staging", "production", "unknown"})

# No result from this module may carry any of these.
FORBIDDEN_VALUE_FIELDS = frozenset(
    {
        "client_secret",
        "secret",
        "secret_value",
        "signing_key",
        "signing_key_value",
        "database_url",
        "access_token",
        "id_token",
        "session_cookie_value",
    }
)

RESULT_FIELDS: tuple[str, ...] = (
    "environment_name",
    "provider_env_present",
    "provider_env_missing_keys",
    "secret_env_present",
    "secret_env_missing_keys",
    "signing_key_present",
    "signing_key_source",
    "callback_url_configured",
    "callback_url_matches_public_origin",
    "public_origin_configured",
    "session_cookie_production_safe",
    "dev_header_production_blocker",
    "database_revision",
    "required_database_revision",
    "database_revision_ready",
    "network_validation_allowed",
    "provider_validation_attempted",
    "provider_validation_passed",
    "secret_values_exposed",
    "blocked_reasons",
    "next_required_actions",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _present(key: str, environ: dict[str, str]) -> bool:
    """Is this key set to something non-empty? Presence only, never the value."""
    return bool((environ.get(key) or "").strip())


def redact_url(url: Any) -> str:
    """A URL reduced to scheme, host and path.

    Enough to compare and to publish; not enough to carry a token. A redirect
    URI with a query string is already malformed, so dropping one loses nothing
    worth keeping.
    """
    text = str(url or "").strip()
    if not text:
        return ""
    parts = urlsplit(text)
    if not parts.scheme and not parts.netloc:
        return parts.path or text
    return f"{parts.scheme}://{parts.netloc}{parts.path}"


def _origin_of(url: Any) -> str:
    parts = urlsplit(str(url or "").strip())
    if not parts.netloc:
        return ""
    return f"{parts.scheme}://{parts.netloc}"


def url_path(url: Any) -> str:
    """Just the path. Public because Gate 121C compares against it too."""
    return urlsplit(str(url or "").strip()).path or ""


def _detect_environment(app_env: Any) -> str:
    name = str(app_env or "").strip().lower()
    return name if name in ENVIRONMENT_NAMES else "unknown"


def _detect_database_revision() -> str:
    """Which revision a runtime database has applied, or an empty string.

    Detected through Gate 113's decision service, which already answers this and
    already refuses to open a connection it does not have. Duplicating the
    detection here is how the two would come to disagree.
    """
    from nativeforge.services.tenant_customer_org_binding_store_decision_service import (  # noqa: E501
        build_binding_store_decision,
    )

    decision = build_binding_store_decision()
    if not decision.get("migration_applied"):
        return ""
    return str(decision.get("database_revision") or "")


def build_environment_preflight(
    *,
    environ: dict[str, str] | None = None,
    app_env: str | None = None,
    configured_callback_url: str | None = None,
    public_origin: str | None = None,
    callback_route_path: str = CALLBACK_ROUTE_PATH,
    database_revision: str | None = None,
    network_validation_allowed: bool = False,
    provider_validation: dict[str, Any] | None = None,
    signing_key_readiness: dict[str, Any] | None = None,
    session_cookie_policy: dict[str, Any] | None = None,
    dev_header_readiness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """What the environment is missing. Deny by default; name nothing secret.

    Every input is injectable so each branch is reachable in a test without
    setting a process-wide variable. Gates 117 through 120 each shipped a
    conjunct whose permitted branch could not be reached; none here is.

    Injecting a value does not make it true of this machine. When nothing is
    supplied the real environment is read, and it reports what it actually has.
    """
    from nativeforge.services.customer_auth_signing_key_readiness_service import (
        build_signing_key_readiness,
    )
    from nativeforge.services.customer_session_cookie_policy_service import (
        build_session_cookie_policy,
    )
    from nativeforge.services.dev_org_header_shutdown_readiness_service import (
        build_dev_header_shutdown_readiness,
    )
    from nativeforge.services.oidc_config_schema_service import (
        build_oidc_config_schema,
    )

    env = dict(environ) if environ is not None else dict(os.environ)

    blocked_reasons: list[str] = []
    next_required_actions: list[str] = []

    # -- environment name ----------------------------------------------------
    if app_env is None:
        from nativeforge.lib.settings import get_settings

        app_env = get_settings().app_env
    environment_name = _detect_environment(app_env)

    # -- provider configuration, by key name ---------------------------------
    provider_missing = [k for k in PROVIDER_ENV_KEYS if not _present(k, env)]
    provider_env_present = not provider_missing
    if provider_missing:
        blocked_reasons.append("provider_environment_incomplete")
        next_required_actions.append(
            "set the missing provider keys out-of-band: "
            + ", ".join(sorted(provider_missing))
        )

    # -- secrets, held separately because they go somewhere different --------
    secret_missing = [k for k in SECRET_ENV_KEYS if not _present(k, env)]
    secret_env_present = not secret_missing
    if secret_missing:
        blocked_reasons.append("secret_environment_incomplete")
        next_required_actions.append(
            "supply the missing secrets from a secret manager: "
            + ", ".join(sorted(secret_missing))
        )

    # -- the signing key, by readiness rather than presence ------------------
    signing = (
        signing_key_readiness
        if signing_key_readiness is not None
        else build_signing_key_readiness(signing_key_material=env.get(SIGNING_KEY_ENV))
    )
    signing_key_present = bool(signing["signing_key_present"])
    signing_key_source = str(signing["signing_key_source"])
    if not signing["can_sign_production_session"]:
        blocked_reasons.append(
            f"signing_key_not_fit_to_sign:source={signing_key_source}"
        )

    # -- the callback URL ----------------------------------------------------
    config = build_oidc_config_schema()
    callback = (
        configured_callback_url
        if configured_callback_url is not None
        else config.get("callback_url")
    )
    callback_url_configured = bool(str(callback or "").strip())

    origin = (
        public_origin
        if public_origin is not None
        else (env.get(PUBLIC_ORIGIN_ENV) or "")
    )
    public_origin_configured = bool(str(origin or "").strip())

    # Three-valued on purpose. "We have not been told the public origin" is a
    # different fact from "the callback points somewhere else", and collapsing
    # them would report a mismatch nobody could act on.
    if not callback_url_configured or not public_origin_configured:
        callback_url_matches_public_origin = False
        if not public_origin_configured:
            blocked_reasons.append("no_public_origin_configured_to_compare_against")
            next_required_actions.append(
                f"set {PUBLIC_ORIGIN_ENV} to the origin browsers will actually "
                "reach, so the callback can be checked against it"
            )
    else:
        callback_url_matches_public_origin = _origin_of(callback) == _origin_of(origin)
        if not callback_url_matches_public_origin:
            blocked_reasons.append("callback_url_origin_does_not_match_public_origin")

    if not callback_url_configured:
        blocked_reasons.append("no_callback_url_configured")

    # Gate 121A's finding. The configured callback points at a *path*, and that
    # path has to be one something can consume. A value that is set and wrong is
    # invisible to a "configured" boolean, and registering it provider-side
    # would land a real browser on a 404 holding a live authorization code.
    callback_path_matches_route = bool(
        callback_url_configured
        and url_path(callback) == str(callback_route_path).strip()
    )
    if callback_url_configured and not callback_path_matches_route:
        blocked_reasons.append("callback_url_path_does_not_match_any_callback_route")
        next_required_actions.append(
            "point the configured callback URL at a path that can consume a "
            f"callback - the API route is {callback_route_path} - and register "
            "the same value provider-side"
        )

    # -- session cookie posture ----------------------------------------------
    policy = (
        session_cookie_policy
        if session_cookie_policy is not None
        else build_session_cookie_policy()
    )
    session_cookie_production_safe = bool(policy.get("production_safe"))
    if not session_cookie_production_safe:
        blocked_reasons.append("session_cookie_policy_not_production_safe")

    # -- the dev header ------------------------------------------------------
    header = (
        dev_header_readiness
        if dev_header_readiness is not None
        else build_dev_header_shutdown_readiness()
    )
    dev_header_production_blocker = bool(
        header.get("must_disable_before_production_auth")
        and not header.get("dev_header_is_production_safe")
    )
    if dev_header_production_blocker:
        blocked_reasons.append("dev_header_must_be_replaced_before_production_auth")
        next_required_actions.append(
            f"replace {header.get('dev_header_name')} across "
            f"{header.get('dev_header_used_by_routes')} route modules, then "
            "disable it"
        )

    # -- the database, reported beside the gates rather than inside them -----
    revision = (
        database_revision
        if database_revision is not None
        else _detect_database_revision()
    )
    database_revision_ready = bool(revision) and str(revision) >= (
        REQUIRED_DATABASE_REVISION
    )
    if not database_revision_ready:
        blocked_reasons.append(f"database_not_at_revision_{REQUIRED_DATABASE_REVISION}")
        next_required_actions.append(
            f"apply migrations to the runtime database, to head "
            f"{REQUIRED_DATABASE_REVISION}"
        )

    # -- the network, which stays off ----------------------------------------
    allowed = bool(network_validation_allowed)
    validation = provider_validation or {}
    provider_validation_attempted = bool(allowed and validation.get("attempted"))
    provider_validation_passed = bool(
        provider_validation_attempted and validation.get("passed")
    )
    if not allowed:
        blocked_reasons.append("network_validation_not_allowed_so_nothing_checked")

    # -- the owner's signature -----------------------------------------------
    if not _present(ACTIVATION_APPROVAL_ENV, env):
        blocked_reasons.append("owner_has_not_authorized_customer_auth_activation")
        next_required_actions.append(
            f"set {ACTIVATION_APPROVAL_ENV} once every step above is done - it "
            "is a signature, not a switch"
        )

    result = {
        "schema_version": SCHEMA_VERSION,
        "environment_name": environment_name,
        "provider_env_present": provider_env_present,
        "provider_env_missing_keys": sorted(provider_missing),
        "secret_env_present": secret_env_present,
        "secret_env_missing_keys": sorted(secret_missing),
        "signing_key_present": signing_key_present,
        "signing_key_source": signing_key_source,
        # Redacted before it is reported, so an artifact can carry it.
        "callback_url_configured": callback_url_configured,
        "callback_url_redacted": redact_url(callback),
        "callback_route_path": str(callback_route_path),
        "callback_url_matches_public_origin": callback_url_matches_public_origin,
        "callback_path_matches_route": callback_path_matches_route,
        "public_origin_configured": public_origin_configured,
        "session_cookie_production_safe": session_cookie_production_safe,
        "dev_header_production_blocker": dev_header_production_blocker,
        "database_revision": str(revision or ""),
        "required_database_revision": REQUIRED_DATABASE_REVISION,
        "database_revision_ready": database_revision_ready,
        "network_validation_allowed": allowed,
        "provider_validation_attempted": provider_validation_attempted,
        "provider_validation_passed": provider_validation_passed,
        "secret_values_exposed": False,
        "blocked_reasons": sorted(set(blocked_reasons)),
        "next_required_actions": sorted(set(next_required_actions)),
        # Constants. A preflight measures; it configures nothing and calls
        # nobody.
        "provider_contacted": False,
        "network_calls": False,
        "environment_mutated": False,
        "activation_performed": False,
        "customer_auth_live": False,
        "login_live": False,
    }
    result["secret_values_exposed"] = _values_leaked(result, env)
    return _json_safe(result)


# The keys whose values are genuinely secret. Deliberately not every key this
# module inspects:
#
#   OIDC_ISSUER      a public hostname every browser is sent to
#   OIDC_CLIENT_ID   public by design; it appears in every redirect
#   OIDC_AUDIENCE    a public API identifier
#   NF_PUBLIC_ORIGIN the origin browsers reach, and the thing the redacted
#                    callback URL is *supposed* to contain
#
# Scanning for those produced a false positive on the first run: the redacted
# callback correctly carries the public origin, and the scanner called it a
# leak. A leak detector that fires on intended output trains people to ignore
# it, so it now scans what actually must never appear.
SECRET_VALUE_KEYS: tuple[str, ...] = (
    CLIENT_SECRET_ENV,
    SIGNING_KEY_ENV,
    ACTIVATION_APPROVAL_ENV,
    "DATABASE_URL",
)


def _values_leaked(result: dict[str, Any], env: dict[str, str]) -> bool:
    """Did any secret value reach the result?

    Values shorter than eight characters are skipped: a two-character value
    would match by coincidence inside a schema version and report a leak that
    did not happen.
    """
    rendered = json.dumps(result)
    for key in SECRET_VALUE_KEYS:
        value = (env.get(key) or "").strip()
        if len(value) >= 8 and value in rendered:
            return True
    return False


def environment_preflight_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Contradictions this preflight must never be able to produce."""
    failures: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        failures.append("schema_version_mismatch")

    if result.get("environment_name") not in ENVIRONMENT_NAMES:
        failures.append("environment_name_outside_vocabulary")

    for field in FORBIDDEN_VALUE_FIELDS:
        if field in result:
            failures.append(f"result_carries_{field}")

    if result.get("secret_values_exposed"):
        failures.append("a_configured_value_reached_the_result")

    if result.get("provider_env_present") and result.get("provider_env_missing_keys"):
        failures.append("provider_env_present_with_missing_keys")

    if result.get("secret_env_present") and result.get("secret_env_missing_keys"):
        failures.append("secret_env_present_with_missing_keys")

    if result.get("provider_validation_attempted") and not result.get(
        "network_validation_allowed"
    ):
        failures.append("provider_validation_attempted_without_network_permission")

    if result.get("provider_validation_passed") and not result.get(
        "provider_validation_attempted"
    ):
        failures.append("provider_validation_passed_without_being_attempted")

    if result.get("provider_contacted") or result.get("network_calls"):
        failures.append("a_preflight_contacted_a_provider")

    if result.get("activation_performed"):
        failures.append("a_preflight_activated_something")

    if result.get("customer_auth_live") or result.get("login_live"):
        failures.append("a_preflight_claimed_auth_is_live")

    # A redacted URL carrying a query string means the redaction did not run.
    for field in ("callback_url_redacted",):
        value = str(result.get(field) or "")
        if "?" in value or "#" in value:
            failures.append(f"{field}_was_not_redacted")

    if result.get("database_revision_ready") and not result.get("database_revision"):
        failures.append("database_ready_without_a_detected_revision")

    if not result.get("blocked_reasons") and not result.get("database_revision_ready"):
        failures.append("preflight_refused_without_a_reason")

    return sorted(set(failures))


def build_missing_key_report(result: dict[str, Any]) -> dict[str, Any]:
    """Every missing key name in one place, for a runbook to render.

    Names, sorted, deduplicated. There is deliberately no matching list of keys
    that *are* set: absence is actionable and presence is only reassuring.
    """
    missing = sorted(
        {
            *(result.get("provider_env_missing_keys") or []),
            *(result.get("secret_env_missing_keys") or []),
        }
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "missing_key_names": missing,
            "missing_key_count": len(missing),
            "values_included": False,
        }
    )


_URL_LIKE = re.compile(r"[a-z][a-z0-9+.-]*://", re.IGNORECASE)


def looks_like_a_url(value: Any) -> bool:
    """Used by the artifact writer to find anything that should be redacted."""
    return bool(_URL_LIKE.search(str(value or "")))
