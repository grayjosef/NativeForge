"""Customer auth dependency contract (Gate 117B).

What a route-level auth dependency does, decided before the dependency exists.

## Four modes

```text
required   refuses an unauthenticated caller with 401
optional   permits one, and reports authenticated false
forbid     refuses an *authenticated* caller
unknown    refuses everybody
```

`forbid` is the one that needs a reason. A signed-in caller hitting `/login` is
not an error today — there is no signing in — but the mode exists because there
will be routes where an existing session is wrong: starting a fresh
authorization flow while holding a session invites session fixation, where an
attacker's flow completes into a victim's already-established cookie.

`unknown` refuses everybody, because a route whose auth mode nobody declared is
a route nobody thought about.

## Enforcement is not liveness

This is the distinction the whole gate turns on, and it is asserted in both
directions:

```text
a dependency in `required` mode refuses unauthenticated callers   -> enforcement
nobody can authenticate, so everybody is refused                  -> not liveness
```

`authorized` can be false with `customer_auth_live` false and the route working
exactly as designed. A 401 proves the application can say no; it proves nothing
about whether anyone could ever be told yes.

## The RLS boundary

`sets_rls_context` is derived and is false unless **both** an `organization_id`
was resolved per Gate 112 *and* a membership record was verified. A principal
existing is not an organization, and an organization claim is not a membership.

Today no principal resolves, so the question never arises — but the derivation
is written now, while it is cheap, rather than at the point where somebody needs
it to be true.

## No session is ever created here

`session_cookie_valid` is an input, not an outcome. This service reads a
decision about a cookie; it does not mint one, does not read a cookie value, and
does not touch a database.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_customer_auth_dependency_contract_v1"

DEPENDENCY_MODES: frozenset[str] = frozenset(
    {"required", "optional", "forbid", "unknown"}
)

# The mode a route gets when nobody declared one. Refuses everybody, because an
# undeclared auth mode is an unconsidered one.
DEFAULT_MODE = "unknown"

# HTTP status per outcome. 401 rather than 403: the caller has not proven who
# they are, which is a different failure from having proven it and lacking
# permission.
STATUS_OK = 200
STATUS_UNAUTHENTICATED = 401
STATUS_FORBIDDEN = 403

RESULT_FIELDS: tuple[str, ...] = (
    "dependency_mode",
    "session_cookie_present",
    "session_cookie_valid",
    "customer_auth_live",
    "login_live",
    "principal_resolved",
    "organization_id_resolved",
    "membership_verified",
    "role_mapping_available",
    "authorized",
    "http_status",
    "security_scheme_required",
    "blocked_reasons",
)

# Modes whose operations should advertise the security scheme in OpenAPI. Only
# `required` actually refuses an unauthenticated caller, so only `required`
# earns the advertisement - a scheme on an optional route would tell a reader a
# credential is needed when it is not.
SECURITY_SCHEME_MODES: frozenset[str] = frozenset({"required"})


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _module_importable(name: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def evaluate_auth_dependency(
    *,
    dependency_mode: Any = None,
    session_cookie_present: bool = False,
    session_cookie_valid: bool = False,
    principal_resolved: bool = False,
    organization_id_resolved: bool = False,
    membership_verified: bool = False,
    customer_auth_live: bool | None = None,
    login_live: bool | None = None,
    session_verification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """What a route's auth dependency decides for this caller. Deny by default.

    Gate 118 added `session_verification`: a result from
    `customer_session_verifier_service`, which supplies the four facts this
    contract previously had to be told. Passing one overrides the individual
    parameters, because a verifier that looked at the cookie is a better source
    than a caller asserting what it would have found.

    The individual parameters remain for tests that want to isolate a single
    conjunct without constructing a whole session.
    """
    if session_verification is not None:
        # Read from the verification rather than from the caller. A caller
        # asserting `principal_resolved=True` alongside a verification that
        # found no principal is the shape of a bug, and the verification wins.
        session_cookie_present = bool(session_verification.get("cookie_present"))
        session_cookie_valid = bool(session_verification.get("session_cookie_valid"))
        principal_resolved = bool(session_verification.get("principal_resolved"))
        organization_id_resolved = bool(
            session_verification.get("organization_id_valid")
        )
        membership_verified = bool(session_verification.get("membership_verified"))
    mode = str(dependency_mode or "").strip().lower()
    if mode not in DEPENDENCY_MODES:
        mode = DEFAULT_MODE

    if customer_auth_live is None or login_live is None:
        from nativeforge.services.customer_auth_activation_gate_service import (
            build_customer_auth_activation_gate,
        )

        gate = build_customer_auth_activation_gate()
        if customer_auth_live is None:
            customer_auth_live = bool(gate["customer_auth_live"])
        if login_live is None:
            login_live = bool(gate["login_live"])

    role_mapping_available = _module_importable(
        "nativeforge.services.customer_auth_role_mapping_service"
    )

    blocked_reasons: list[str] = []

    if mode == DEFAULT_MODE:
        blocked_reasons.append("route_declared_no_auth_dependency_mode")

    # A cookie that is present and invalid is worse than one that is absent: it
    # means somebody sent something, and it did not check out.
    #
    # Gate 119F: *why* it did not check out changes what an operator should do.
    # A verification that could not run for want of a signing key is a
    # configuration failure; one that ran and failed is a bad cookie. The
    # verifier now separates the two, so this contract stops flattening them.
    if session_cookie_present and not session_cookie_valid:
        if session_verification is not None and session_verification.get(
            "signature_unverifiable"
        ):
            blocked_reasons.append(
                "session_cookie_could_not_be_verified_no_signing_key_available"
            )
        elif session_verification is not None and session_verification.get(
            "signature_invalid"
        ):
            blocked_reasons.append("session_cookie_signature_did_not_verify")
        else:
            blocked_reasons.append("session_cookie_present_but_invalid")

    # A valid session with nobody behind it is a contradiction, and the kind
    # that would let a forged cookie become a principal.
    authenticated = bool(session_cookie_valid and principal_resolved)
    if session_cookie_valid and not principal_resolved:
        blocked_reasons.append("session_cookie_valid_but_no_principal_resolved")

    # Derived affirmatively, per mode.
    if mode == "required":
        authorized = authenticated
        http_status = STATUS_OK if authorized else STATUS_UNAUTHENTICATED
        if not authorized:
            blocked_reasons.append("required_mode_refuses_an_unauthenticated_caller")
    elif mode == "optional":
        # Always permitted. The caller learns they are anonymous rather than
        # being turned away.
        authorized = True
        http_status = STATUS_OK
    elif mode == "forbid":
        authorized = not authenticated
        http_status = STATUS_OK if authorized else STATUS_FORBIDDEN
        if not authorized:
            blocked_reasons.append("forbid_mode_refuses_an_authenticated_caller")
    else:
        authorized = False
        http_status = STATUS_UNAUTHENTICATED

    # The RLS boundary. Both conditions, always, and a principal is neither.
    sets_rls_context = bool(
        authenticated and organization_id_resolved and membership_verified
    )
    if authenticated and not organization_id_resolved:
        blocked_reasons.append("no_organization_id_resolved_from_the_principal")
    if authenticated and not membership_verified:
        blocked_reasons.append("no_verified_membership_for_this_organization")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "dependency_mode": mode,
            "session_cookie_present": bool(session_cookie_present),
            "session_cookie_valid": bool(session_cookie_valid),
            "customer_auth_live": bool(customer_auth_live),
            "login_live": bool(login_live),
            "principal_resolved": bool(principal_resolved),
            "authenticated": authenticated,
            "organization_id_resolved": bool(organization_id_resolved),
            "membership_verified": bool(membership_verified),
            "role_mapping_available": role_mapping_available,
            "authorized": authorized,
            "http_status": http_status,
            "security_scheme_required": mode in SECURITY_SCHEME_MODES,
            "sets_rls_context": sets_rls_context,
            # Gate 118: whether this decision came from a verified cookie or
            # from parameters a caller supplied. A route must use the first.
            "session_verified": session_verification is not None,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Constants: a dependency decides. It mints nothing and reads no
            # cookie value.
            "real_sessions_created": False,
            "real_users_created": False,
            "current_org_id_set": False,
            "session_cookie_value_read": False,
            "provider_contacted": False,
            "fabricated": False,
        }
    )


def build_dependency_contract_matrix(
    *, cases: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Every mode against every caller shape. Takes its input so a test can
    shrink it."""
    if cases is None:
        cases = [
            {"dependency_mode": mode, **caller}
            for mode in sorted(DEPENDENCY_MODES)
            for caller in (
                {},
                {"session_cookie_present": True},
                {"session_cookie_present": True, "session_cookie_valid": True},
                {
                    "session_cookie_present": True,
                    "session_cookie_valid": True,
                    "principal_resolved": True,
                },
            )
        ]

    rows = [evaluate_auth_dependency(**case) for case in cases]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "auth_dependency_contract_available": True,
            "modes": sorted(DEPENDENCY_MODES),
            "security_scheme_modes": sorted(SECURITY_SCHEME_MODES),
            "rows": rows,
            "case_count": len(rows),
            "authorized_count": sum(1 for r in rows if r["authorized"]),
            "unauthenticated_refusal_count": sum(
                1 for r in rows if r["http_status"] == STATUS_UNAUTHENTICATED
            ),
            "rls_context_count": sum(1 for r in rows if r["sets_rls_context"]),
            "real_sessions_created": False,
            "real_users_created": False,
            "current_org_id_set": False,
            "fabricated": False,
        }
    )


def dependency_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in RESULT_FIELDS:
        if field not in result:
            fails.append(f"dependency_missing_field:{field}")

    for constant in (
        "real_sessions_created",
        "real_users_created",
        "current_org_id_set",
        "session_cookie_value_read",
        "provider_contacted",
        "fabricated",
    ):
        if result.get(constant) is not False:
            fails.append(f"dependency_claimed:{constant}")

    mode = result.get("dependency_mode")
    if mode not in DEPENDENCY_MODES:
        fails.append("dependency_mode_out_of_vocabulary")

    status = result.get("http_status")
    if status not in {STATUS_OK, STATUS_UNAUTHENTICATED, STATUS_FORBIDDEN}:
        fails.append(f"http_status_out_of_vocabulary:{status}")

    authenticated = bool(result.get("authenticated"))

    # A caller is authenticated only with a valid cookie and a resolved
    # principal. A forged cookie must not become a principal.
    if authenticated and not result.get("session_cookie_valid"):
        fails.append("authenticated_without_a_valid_session_cookie")
    if authenticated and not result.get("principal_resolved"):
        fails.append("authenticated_without_a_resolved_principal")

    # Required mode refuses, and says so with 401.
    if mode == "required":
        if result.get("authorized") is not authenticated:
            fails.append("required_mode_authorized_disagrees_with_authentication")
        if not result.get("authorized") and status != STATUS_UNAUTHENTICATED:
            fails.append("required_mode_refusal_without_a_401")
        if result.get("authorized") and status != STATUS_OK:
            fails.append("required_mode_permitted_without_a_200")

    # Optional mode never refuses.
    if mode == "optional":
        if not result.get("authorized"):
            fails.append("optional_mode_refused_a_caller")
        if status != STATUS_OK:
            fails.append("optional_mode_returned_a_non_200")

    # Forbid mode refuses the authenticated.
    if mode == "forbid" and authenticated and result.get("authorized"):
        fails.append("forbid_mode_permitted_an_authenticated_caller")

    # Unknown refuses everybody.
    if mode == "unknown":
        if result.get("authorized"):
            fails.append("unknown_mode_authorized_a_caller")
        if status != STATUS_UNAUTHENTICATED:
            fails.append("unknown_mode_did_not_refuse")

    # Only `required` advertises the scheme. A scheme on an optional route tells
    # a reader a credential is needed when it is not.
    if result.get("security_scheme_required") is not (mode in SECURITY_SCHEME_MODES):
        fails.append("security_scheme_required_disagrees_with_the_mode")

    # The RLS boundary, in both directions.
    if result.get("sets_rls_context"):
        if not result.get("organization_id_resolved"):
            fails.append("rls_context_without_an_organization_id")
        if not result.get("membership_verified"):
            fails.append("rls_context_without_a_verified_membership")
        if not authenticated:
            fails.append("rls_context_without_authentication")

    # A refusal must name itself.
    if not result.get("authorized") and not result.get("blocked_reasons"):
        fails.append("dependency_refused_without_a_reason")

    return fails


def dependency_matrix_invariant_failures(matrix: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if matrix.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    rows = matrix.get("rows") or []
    for row in rows:
        fails.extend(
            f"{row.get('dependency_mode')}:{f}"
            for f in dependency_invariant_failures(row)
        )

    if matrix.get("authorized_count") != sum(1 for r in rows if r.get("authorized")):
        fails.append("authorized_count_disagrees_with_the_rows")

    # No caller in any mode may set an RLS context while auth is not live.
    if matrix.get("rls_context_count"):
        fails.append("dependency_matrix_set_an_rls_context")

    for constant in (
        "real_sessions_created",
        "real_users_created",
        "current_org_id_set",
        "fabricated",
    ):
        if matrix.get(constant) is not False:
            fails.append(f"dependency_matrix_claimed:{constant}")

    return fails
