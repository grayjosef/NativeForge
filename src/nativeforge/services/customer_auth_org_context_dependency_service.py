"""Customer auth organization context dependency (Gate 122B).

The replacement for the dev-header organization context, decided before it is
wired anywhere.

## Three modes, and only one of them ever accepts a header

```text
required            a verified session, or 401
optional            a verified session, or no_org_context - never a fake one
dev_demo_explicit   X-NF-Org-Id, and only outside production
```

The third mode is named for what it is. Today's behaviour is the same posture
arrived at by accident: `nf_dev_org_headers` defaults to true and nobody turned
it off, so routes work. After this the dev path has a name, a mode, and a
refusal in production — which is the difference between a decision and a
default.

## optional does not mean anonymous-gets-an-org

The interesting failure mode is not a route that refuses too much. It is a route
in `optional` mode that, finding no session, quietly substitutes a default
organization so the page renders.

```text
optional + no session  ->  org_context_available: False
                           organization_id:       None
                           http_status:           200
```

Two hundred, and no organization. A caller gets a page with nothing scoped to
anybody, which is correct and looks broken — and looking broken is the point. An
invariant refuses any result carrying an `organization_id` without
`organization_id_resolved`.

## A verified session is not an organization

Gate 112's rule, arriving at the dependency layer. Three separate conjuncts:

```text
session_valid            somebody holds a credential we issued
organization_id_resolved ...and a claim resolved to an organization_id
membership_verified      ...and a membership record backs it
```

A signed cookie proves the first. It proves neither of the others, because
memberships get revoked and a session outlives the revocation until it expires.
`rls_claim_guard_passed` requires all three plus a trusted claim source.

## The dev header is never an authority, in any mode

Gate 111's claim guard has refused `dev_request_header` in both production and
non-production since it was written, and nothing routed its answer. This service
routes it.

In `dev_demo_explicit` the header may select an organization for a *dev* request
and `production_safe` is false, `rls_claim_guard_passed` is false, and
`dev_header_used` is true. It is a convenience with its provenance attached, not
an authentication.

## tenant_id, customer_org_id, organization_profile_id

None of the three may set an RLS context, in any mode, ever. They are refused by
name rather than ignored: a caller offering one should learn it was not
honoured, because silently dropping it is how somebody comes to believe it
worked.
"""

from __future__ import annotations

import json
import re
from typing import Any

from nativeforge.services.rls_context_claim_guard_service import (
    RLS_ELIGIBLE_IDENTITY_NAMES,
    RLS_FORBIDDEN_IDENTITY_NAMES,
    evaluate_rls_context_claim,
)

SCHEMA_VERSION = "nf_customer_auth_org_context_dependency_v1"

DEPENDENCY_MODES = frozenset({"required", "optional", "dev_demo_explicit", "unknown"})

# The mode a route gets when nobody declared one. Refuses everybody, because an
# undeclared mode is an unconsidered one. Bridged from Gate 117's contract.
DEFAULT_MODE = "unknown"

# The header. Named here so a result can say it was refused rather than a reader
# having to infer it.
DEV_HEADER_NAME = "X-NF-Org-Id"

# The setting that enables it. Presence of the setting is not permission.
DEV_HEADER_SETTING = "nf_dev_org_headers"

# An identity name that is never an RLS authority. `organization_profile_id` is
# added to Gate 111's two because Gates 110-113 exist for that substitution.
FORBIDDEN_IDENTITY_NAMES = frozenset(
    {*RLS_FORBIDDEN_IDENTITY_NAMES, "organization_profile_id"}
)

STATUS_OK = 200
STATUS_UNAUTHENTICATED = 401
STATUS_FORBIDDEN = 403
STATUS_UNAVAILABLE = 503

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

RESULT_FIELDS: tuple[str, ...] = (
    "dependency_mode",
    "session_present",
    "session_valid",
    "organization_id_resolved",
    "membership_verified",
    "rls_claim_guard_passed",
    "dev_header_used",
    "dev_header_allowed",
    "production_safe",
    "org_context_available",
    "http_status",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _uuid_shaped(value: Any) -> bool:
    """Can this survive the ``::uuid`` cast every RLS policy performs?"""
    return bool(_UUID_RE.match(str(value or "").strip()))


def evaluate_org_context(
    *,
    dependency_mode: Any = None,
    session_verification: dict[str, Any] | None = None,
    session_present: bool = False,
    session_valid: bool = False,
    membership_verified: bool = False,
    resolved_organization_id: Any = None,
    dev_header_value: Any = None,
    dev_header_setting_enabled: bool = False,
    production_context: bool = True,
    claimed_identity_name: Any = None,
    claimed_identity_value: Any = None,
) -> dict[str, Any]:
    """What organization context a route may act in. Deny by default.

    ``session_verification`` is a result from Gate 118's verifier. Supplying one
    overrides the individual booleans, because a verifier that looked at the
    cookie is a better source than a caller asserting what it would have found.
    The individual parameters remain for tests isolating a single conjunct.
    """
    mode = str(dependency_mode or "").strip().lower()
    if mode not in DEPENDENCY_MODES:
        mode = DEFAULT_MODE

    blocked_reasons: list[str] = []

    if mode == DEFAULT_MODE:
        blocked_reasons.append("route_declared_no_org_context_mode")

    # -- the session ---------------------------------------------------------
    if session_verification is not None:
        # Read from the verification rather than from the caller. A caller
        # asserting a valid session alongside a verification that found none is
        # the shape of a bug, and the verification wins.
        session_present = bool(session_verification.get("cookie_present"))
        session_valid = bool(session_verification.get("session_cookie_valid"))
        membership_verified = bool(session_verification.get("membership_verified"))
        if resolved_organization_id is None:
            resolved_organization_id = session_verification.get("organization_id")

    session_present = bool(session_present)
    session_valid = bool(session_valid)

    if session_present and not session_valid:
        # Worse than an absent session: somebody sent something and it did not
        # check out.
        blocked_reasons.append("session_present_but_invalid")

    # -- the organization ----------------------------------------------------
    organization_id = str(resolved_organization_id or "").strip()
    organization_id_resolved = bool(
        session_valid and organization_id and _uuid_shaped(organization_id)
    )
    if session_valid and organization_id and not _uuid_shaped(organization_id):
        # Gates 110-113: a profile id is a real value in the wrong identity
        # space, and every RLS policy casts to ::uuid.
        blocked_reasons.append("resolved_organization_id_is_not_uuid_shaped")
    elif session_valid and not organization_id:
        blocked_reasons.append("no_organization_id_resolved_from_the_session")

    # -- an identity offered by name -----------------------------------------
    # Refused rather than ignored. A caller that offered one should learn it was
    # not honoured.
    offered = str(claimed_identity_name or "").strip()
    if offered and offered in FORBIDDEN_IDENTITY_NAMES:
        blocked_reasons.append(f"identity_name_cannot_set_rls_context:{offered}")
    elif offered and offered not in RLS_ELIGIBLE_IDENTITY_NAMES:
        blocked_reasons.append(f"identity_name_not_recognised:{offered}")

    # -- membership ----------------------------------------------------------
    membership_verified = bool(membership_verified)
    if organization_id_resolved and not membership_verified:
        # Gate 112 at the dependency layer: a valid session is not a membership.
        blocked_reasons.append("no_verified_membership_for_this_organization")

    # -- the dev header ------------------------------------------------------
    dev_header_present = bool(str(dev_header_value or "").strip())
    dev_header_allowed = bool(
        mode == "dev_demo_explicit"
        and dev_header_setting_enabled
        and not production_context
    )
    dev_header_used = bool(dev_header_present and dev_header_allowed)

    if dev_header_present and production_context:
        blocked_reasons.append(f"{DEV_HEADER_NAME}_is_not_an_authority_in_production")
    if dev_header_present and mode != "dev_demo_explicit":
        blocked_reasons.append(
            f"{DEV_HEADER_NAME}_offered_to_a_route_that_is_not_dev_demo_explicit"
        )
    if mode == "dev_demo_explicit" and not dev_header_setting_enabled:
        blocked_reasons.append(f"{DEV_HEADER_SETTING}_is_disabled")
    if mode == "dev_demo_explicit" and production_context:
        blocked_reasons.append("dev_demo_explicit_mode_is_refused_in_production")

    # -- the claim guard -----------------------------------------------------
    # Gate 111 decides, and this is the first thing to route its answer. The
    # source is derived from what actually produced the identity, never
    # declared by a caller.
    claim_source = "unknown"
    if dev_header_used:
        claim_source = "dev_request_header"
    elif organization_id_resolved:
        claim_source = "verified_auth_claim"

    guard = evaluate_rls_context_claim(
        principal={
            "auth_status": (
                "authenticated_verified_org" if session_valid else "unauthenticated"
            ),
            "organization_id": organization_id or None,
            "org_claim_verified": bool(membership_verified),
        },
        claimed_identity_name=(offered or "organization_id"),
        claimed_identity_value=(
            claimed_identity_value
            if claimed_identity_value is not None
            else (organization_id or None)
        ),
        claim_source=claim_source,
        resolved_organization_id=organization_id or None,
        production_context=production_context,
    )
    rls_claim_guard_passed = bool(guard["rls_context_allowed"])
    if not rls_claim_guard_passed:
        blocked_reasons.extend(
            f"claim_guard:{reason}" for reason in guard["blocked_reasons"]
        )

    # -- derived affirmatively ----------------------------------------------
    # Every conjunct must hold. Nothing is subtracted from a permissive default.
    org_context_available = bool(
        mode in {"required", "optional"}
        and session_valid
        and organization_id_resolved
        and membership_verified
        and rls_claim_guard_passed
    )

    # A dev context is a context, and it is not a production-safe one.
    #
    # The header's own value selects the organization here, and nowhere else.
    # It must still be UUID-shaped, because a dev context that could not survive
    # the `::uuid` cast would fail at the database rather than at this boundary
    # - and a dev path that fails somewhere less legible than production is a
    # dev path that teaches the wrong lesson.
    dev_organization_id = str(dev_header_value or "").strip() if dev_header_used else ""
    if dev_header_used and not _uuid_shaped(dev_organization_id):
        blocked_reasons.append(f"{DEV_HEADER_NAME}_is_not_uuid_shaped")
        dev_organization_id = ""

    dev_org_context_available = bool(
        mode == "dev_demo_explicit"
        and dev_header_used
        and dev_organization_id
        and not production_context
    )

    production_safe = bool(org_context_available and not dev_header_used)

    # -- the status ----------------------------------------------------------
    if mode == "required":
        http_status = STATUS_OK if org_context_available else STATUS_UNAUTHENTICATED
    elif mode == "optional":
        # No session is not an error in optional mode. No organization is the
        # honest result, and the route renders nothing scoped to anybody.
        http_status = STATUS_OK
    elif mode == "dev_demo_explicit":
        if production_context:
            http_status = STATUS_FORBIDDEN
        elif not dev_header_setting_enabled:
            http_status = STATUS_UNAVAILABLE
        else:
            http_status = STATUS_OK if dev_org_context_available else STATUS_FORBIDDEN
    else:
        http_status = STATUS_UNAUTHENTICATED

    result = {
        "schema_version": SCHEMA_VERSION,
        "dependency_mode": mode,
        "session_present": session_present,
        "session_valid": session_valid,
        "organization_id_resolved": organization_id_resolved,
        "membership_verified": membership_verified,
        "rls_claim_guard_passed": rls_claim_guard_passed,
        "claim_source": claim_source,
        "dev_header_name": DEV_HEADER_NAME,
        "dev_header_present": dev_header_present,
        "dev_header_used": dev_header_used,
        "dev_header_allowed": dev_header_allowed,
        "production_context": bool(production_context),
        "production_safe": production_safe,
        "org_context_available": org_context_available,
        "dev_org_context_available": dev_org_context_available,
        "http_status": http_status,
        "blocked_reasons": sorted(set(blocked_reasons)),
        # Constants. A dependency decides; it authenticates nobody and writes
        # nothing.
        "organization_created": False,
        "session_created": False,
        "current_org_id_set": False,
        "customer_auth_live": False,
        "login_live": False,
        "fabricated": False,
    }
    # Only ever present when it was actually resolved. An organization_id
    # sitting beside `organization_id_resolved: False` is a fabricated context.
    if organization_id_resolved:
        result["organization_id"] = organization_id or None
    elif dev_org_context_available:
        # Labelled by which path produced it. A reader seeing an
        # `organization_id` beside `production_safe: False` should be able to
        # tell at a glance that a header chose it.
        result["organization_id"] = dev_organization_id or None
    return _json_safe(result)


def org_context_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Contradictions this dependency must never be able to produce."""
    failures: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        failures.append("schema_version_mismatch")

    mode = str(result.get("dependency_mode") or "")
    if mode not in DEPENDENCY_MODES:
        failures.append("dependency_mode_outside_vocabulary")

    # The one this whole service exists to prevent.
    if result.get("org_context_available") and result.get("dev_header_used"):
        failures.append("a_dev_header_produced_a_production_org_context")

    if result.get("dev_header_used") and result.get("production_context"):
        failures.append("a_dev_header_was_used_in_production")

    if result.get("dev_header_used") and not result.get("dev_header_allowed"):
        failures.append("a_dev_header_was_used_without_being_allowed")

    if result.get("dev_header_allowed") and mode != "dev_demo_explicit":
        failures.append("a_dev_header_was_allowed_outside_dev_demo_explicit_mode")

    if result.get("production_safe") and result.get("dev_header_used"):
        failures.append("production_safe_claimed_with_a_dev_header")

    if result.get("org_context_available"):
        for conjunct in (
            "session_valid",
            "organization_id_resolved",
            "membership_verified",
            "rls_claim_guard_passed",
        ):
            if not result.get(conjunct):
                failures.append(f"org_context_available_without:{conjunct}")

    # A fabricated organization is the failure mode of `optional`.
    if result.get("organization_id") and not (
        result.get("organization_id_resolved")
        or result.get("dev_org_context_available")
    ):
        failures.append("an_organization_id_was_reported_without_being_resolved")

    if result.get("organization_id_resolved") and not result.get("session_valid"):
        failures.append("an_organization_resolved_without_a_valid_session")

    if mode == "required" and result.get("org_context_available"):
        if result.get("http_status") != STATUS_OK:
            failures.append("required_mode_permitted_a_context_without_a_200")
    if mode == "required" and not result.get("org_context_available"):
        if result.get("http_status") != STATUS_UNAUTHENTICATED:
            failures.append("required_mode_refused_without_a_401")

    if mode == "optional" and result.get("http_status") != STATUS_OK:
        failures.append("optional_mode_returned_a_non_200")

    if result.get("current_org_id_set"):
        failures.append("a_dependency_contract_set_the_rls_context")

    if result.get("organization_created") or result.get("session_created"):
        failures.append("a_dependency_contract_created_something")

    if result.get("customer_auth_live") or result.get("login_live"):
        failures.append("a_dependency_contract_claimed_auth_is_live")

    if not result.get("org_context_available") and not result.get("blocked_reasons"):
        failures.append("org_context_refused_without_a_reason")

    return sorted(set(failures))


def build_org_context_matrix(*, cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Run a set of cases and report what none of them achieved."""
    rows: list[dict[str, Any]] = []
    for case in cases:
        result = evaluate_org_context(**case["request"])
        rows.append(
            {
                "case": case["case"],
                "dependency_mode": result["dependency_mode"],
                "session_valid": result["session_valid"],
                "organization_id_resolved": result["organization_id_resolved"],
                "membership_verified": result["membership_verified"],
                "rls_claim_guard_passed": result["rls_claim_guard_passed"],
                "dev_header_used": result["dev_header_used"],
                "org_context_available": result["org_context_available"],
                "production_safe": result["production_safe"],
                "http_status": result["http_status"],
                "blocked_reasons": result["blocked_reasons"],
                "invariant_failures": org_context_invariant_failures(result),
            }
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "case_count": len(rows),
            "rows": rows,
            "org_context_available_count": sum(
                1 for r in rows if r["org_context_available"]
            ),
            "dev_header_used_count": sum(1 for r in rows if r["dev_header_used"]),
            "refused_401_count": sum(1 for r in rows if r["http_status"] == 401),
            "invariant_failures": sorted(
                {f for r in rows for f in r["invariant_failures"]}
            ),
        }
    )
