"""Customer auth activation gate (Gate 115B).

One measurable answer to "may customer authentication be turned on?", unifying
the promotion gates Gate 19 modelled, the contracts Gates 111-112 built, and the
route reality Gate 115A measured.

## Why this is not the Gate 19 service

`login_live_promotion_gate_service` reports the same family of gates and
**cannot ever say yes**:

```python
login_live_claimed = False
if all_passed and preflight.get("validation_possible"):
    login_live_claimed = False        # assigned False, then False again
```

and its invariants fail the result if any of its three claims is True. Read as
code that branch is dead; read as policy it is a deliberate modelling gate.

That service is left exactly as it is. This one is the activation gate: its
`customer_auth_live` is derived from measurements, so it moves when the world
does. Today it is false, and it is false for seventeen nameable reasons rather
than because a constant says so.

## Secrets

`secret_present` is a boolean and nothing else. It comes from
`auth0_preflight_service`, which reads `os.environ` for presence only, never
returns a value, and self-checks its own serialised output for any env value of
length >= 8 before returning.

This service adds a second check on top: after building its result it scans the
serialised payload for every configured env value and refuses - setting
`activation_allowed` false and naming `secret_value_leaked_into_output` - if one
appears. Two independent checks, because a leaked client secret is the one
mistake in this gate that cannot be walked back.

No value is stored, logged, returned or committed.

## Owner authorization is a gate, not a formality

Every measured gate passing is necessary and not sufficient. `activation_allowed`
additionally requires an explicit owner authorization token, in the same shape
the storage gates use. Configuration arriving in an environment is not somebody
deciding to expose a login page to real Tribes.

## No network, no provider call

Preflight runs with `jwks_network_check_enabled=False` and the live validation
runner reports `network_calls: False` under an invariant that fails if it is
ever true. `issuer_jwks_validated` is false here because nothing was checked -
which is a different fact from checked-and-failed, and the service says which.
"""

from __future__ import annotations

import json
import os
from typing import Any

SCHEMA_VERSION = "nf_customer_auth_activation_gate_v1"

# The exact token an owner supplies out-of-band to authorize activation. Its
# presence is checked; its value is compared, never reported.
ACTIVATION_APPROVAL_ENV = "NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL"
ACTIVATION_APPROVAL_TOKEN = "MAYHEM_APPROVES_NATIVEFORGE_CUSTOMER_AUTH_ACTIVATION"

# Environment names this gate is aware of. Read for presence only, and used to
# scan the outgoing payload for leaks.
OIDC_ENV_KEYS: tuple[str, ...] = (
    "OIDC_ISSUER",
    "OIDC_CLIENT_ID",
    "OIDC_CLIENT_SECRET",
    "OIDC_AUDIENCE",
    "OIDC_CALLBACK_URL",
    "OIDC_LOGOUT_URL",
    "OIDC_ALLOWED_ORIGIN",
)

# Every gate that must be true before customer auth may be called live. Named
# individually so a report can say which one is missing rather than only that
# activation is refused.
REQUIRED_AUTH_GATES: tuple[str, ...] = (
    "provider_configured",
    "secret_present",
    "issuer_configured",
    "issuer_jwks_validated",
    "audience_configured",
    "callback_route_available",
    "callback_session_validated",
    "session_cookie_policy_available",
    "invite_binding_passed",
    "org_binding_passed",
    "role_mapping_passed",
    "organization_id_resolution_available",
    "membership_verification_available",
    "rls_claim_guard_available",
    "dev_header_disabled_for_production",
    # Gate 119: a login that cannot sign a session is a login that cannot
    # finish. Presence was known before; readiness was not.
    "session_signing_key_ready",
)

# The subset that decides whether a *login flow* can run. Narrower than auth
# activation: a login can complete without the dev header having been removed,
# but customer auth is not live while an unauthenticated header can still set
# the RLS context.
REQUIRED_LOGIN_GATES: tuple[str, ...] = (
    "provider_configured",
    "secret_present",
    "issuer_configured",
    "issuer_jwks_validated",
    "audience_configured",
    "callback_route_available",
    "callback_session_validated",
    "session_cookie_policy_available",
    "org_binding_passed",
    "role_mapping_passed",
    # Login is the act of issuing a session, so it needs the key that signs one.
    "session_signing_key_ready",
)

GATE_FIELDS: tuple[str, ...] = REQUIRED_AUTH_GATES + (
    "customer_auth_live",
    "login_live",
    "activation_allowed",
    "blocked_reasons",
    "next_required_actions",
)

# What lifts each gate, so a refusal points somewhere. Ordered by what must
# happen first; the service reports only the entries whose gate is false.
GATE_REMEDIES: dict[str, str] = {
    "provider_configured": (
        "owner sets the OIDC_* environment variables out-of-band; this gate "
        "never stores or receives them"
    ),
    "secret_present": (
        "owner supplies OIDC_CLIENT_SECRET out-of-band; presence is detected, "
        "the value is never read into any output"
    ),
    "issuer_configured": "owner sets OIDC_ISSUER",
    "audience_configured": "owner sets OIDC_AUDIENCE",
    "issuer_jwks_validated": (
        "run the existing live validation path once configuration exists; no "
        "network check happens before then, so this is unvalidated rather "
        "than failed"
    ),
    "callback_route_available": (
        "NativeForge builds an OIDC callback route - engineering work, not "
        "configuration. No such route exists among the 178 endpoints"
    ),
    "session_cookie_policy_available": (
        "NativeForge defines a session cookie policy that passes its own "
        "invariants - Gate 116B"
    ),
    "callback_session_validated": (
        "validate a real callback and session once the route exists"
    ),
    "invite_binding_passed": "validate invite binding against a real flow",
    "org_binding_passed": (
        "validate that a verified claim resolves to an organization_id and a "
        "membership record - Gate 112's contract, exercised for real"
    ),
    "role_mapping_passed": (
        "configure provider roles and map them explicitly; unknown roles grant "
        "nothing by design"
    ),
    "organization_id_resolution_available": (
        "Gate 112's resolution service must be importable"
    ),
    "membership_verification_available": (
        "Gate 112's membership verification service must be importable"
    ),
    "rls_claim_guard_available": "Gate 111's RLS claim guard must be importable",
    "dev_header_disabled_for_production": (
        "replace X-NF-Org-Id with an authenticated claim, then disable it; 15 "
        "route modules depend on it today"
    ),
    "session_signing_key_ready": (
        "owner supplies NF_SESSION_SIGNING_KEY out-of-band from an environment "
        "or a secret manager; the committed local_dev_fixture key may never "
        "sign a production session - Gate 119B"
    ),
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _module_importable(name: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _owner_approval_present() -> bool:
    """Has the owner authorized activation, out-of-band?

    Compared, never reported. A wrong token is the same as no token.
    """
    return os.environ.get(ACTIVATION_APPROVAL_ENV, "") == ACTIVATION_APPROVAL_TOKEN


def build_customer_auth_activation_gate(
    *,
    preflight: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
    route_readiness: dict[str, Any] | None = None,
    dev_header_disabled_for_production: bool | None = None,
    owner_approval: bool | None = None,
    signing_key_readiness: dict[str, Any] | None = None,
    environment_preflight: dict[str, Any] | None = None,
    binding_evidence: dict[str, Any] | None = None,
    jwks_validation_evidence: dict[str, Any] | None = None,
    role_mapping_evidence: dict[str, Any] | None = None,
    login_activation_decision: dict[str, Any] | None = None,
    dev_header_exposure: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """May customer authentication be activated? Deny by default.

    Every input is injectable so each gate's true branch is reachable in a test.
    Without that, `customer_auth_live: True` would be unreachable and the whole
    contract would be indistinguishable from a constant.
    """
    from nativeforge.services.auth0_live_validation_runner_service import (
        run_auth0_live_validation,
    )
    from nativeforge.services.auth0_preflight_service import run_auth0_preflight
    from nativeforge.services.customer_auth_route_readiness_service import (
        build_route_readiness,
    )
    from nativeforge.services.customer_auth_signing_key_readiness_service import (
        build_signing_key_readiness,
    )

    # Offline. jwks_network_check_enabled defaults False and is not raised here.
    pre = preflight if preflight is not None else run_auth0_preflight()
    val = validation if validation is not None else run_auth0_live_validation()
    # Gate 134F. `route_org_resolution_enforced` used to require
    # `customer_auth_live`, which made the whole chain circular - see
    # `customer_auth_route_readiness_service`. It asks for `a principal can
    # exist` now, and Gate 132's binding evidence is exactly that measurement:
    # a verified identity resolving to an organization through a membership.
    if route_readiness is not None:
        routes = route_readiness
    elif binding_evidence is not None:
        routes = build_route_readiness(
            principal_possible=bool(binding_evidence.get("org_binding_passed"))
        )
    else:
        routes = build_route_readiness()

    if dev_header_disabled_for_production is None:
        # Detected from settings rather than from the containment service, which
        # shells out to systemctl and would make committed artifacts depend on
        # the machine that generated them.
        #
        # Gate 134F: the setting is one of two ways this can be true. The fact
        # the gate is reaching for is that an unauthenticated header cannot set
        # the RLS context - and a header no route reads cannot set anything,
        # whatever the setting says. So a *measured* zero satisfies it too.
        #
        # Measured, never assumed: without exposure evidence only the setting
        # decides, which keeps this deterministic for the artifacts it feeds.
        exposure = dev_header_exposure or {}
        measured_zero = bool(
            exposure.get("dev_header_route_count") == 0 and exposure.get("route_total")
        )
        dev_header_disabled_for_production = not _dev_header_enabled() or measured_zero

    if owner_approval is None:
        owner_approval = _owner_approval_present()

    # Injectable, so this gate's true branch is reachable without setting a
    # process-wide signing key. Gates 117 and 118 each shipped a conjunct whose
    # permitted branch could not be reached; this one can.
    signing = (
        signing_key_readiness
        if signing_key_readiness is not None
        else build_signing_key_readiness()
    )

    # Gate 132G. No connection is opened here and none is discovered: a caller
    # with a session passes what it measured, and a caller without one gets
    # every evidence field false. This service still touches no database.
    evidence = binding_evidence if binding_evidence is not None else {}

    # Gate 133. Two more measured facts and one recorded decision, on the
    # same terms: supplied by a caller that read them, absent and therefore
    # false for a caller that did not. Nothing here opens a connection.
    jwks_ev = jwks_validation_evidence if jwks_validation_evidence is not None else {}
    role_ev = role_mapping_evidence if role_mapping_evidence is not None else {}
    login_decision = (
        login_activation_decision if login_activation_decision is not None else {}
    )

    gates: dict[str, bool] = {
        # -- provider configuration, presence only -------------------------
        "provider_configured": bool(pre.get("validation_possible")),
        "secret_present": bool(pre.get("client_secret_present")),
        "issuer_configured": bool(pre.get("issuer_url_present")),
        "audience_configured": bool(pre.get("audience_present")),
        # -- validation ----------------------------------------------------
        # Gate 133B. The callback verifies Google's ID token against Google's
        # JWKS on every login, and until 0037 nothing wrote that down - so this
        # gate read `provider_validated`, a literal assigned False once. It is
        # measured now, from nf_auth_validation_events.
        "issuer_jwks_validated": bool(
            val.get("provider_validated") or jwks_ev.get("issuer_jwks_validated")
        ),
        # Gate 132G. These two were a literal `False` and a parameter nobody
        # passed - true in no environment for no reason. They are measured now,
        # from rows, and only when a caller supplies something to read: without
        # evidence they stay false, which keeps this gate's output the same on
        # every machine and keeps the artifacts it feeds reproducible.
        #
        # `or` rather than replacement: the validation runner's answer is still
        # honoured if it ever learns to say yes, and neither source can turn the
        # other off.
        "callback_session_validated": bool(
            val.get("callback_session_validated")
            or evidence.get("callback_session_validated")
        ),
        "invite_binding_passed": bool(val.get("invite_binding_passed")),
        "org_binding_passed": bool(
            val.get("org_binding_passed") or evidence.get("org_binding_passed")
        ),
        # Gate 133C. Membership rows have carried the mapping since Gate 132.
        # Nothing asked them; this was a parameter no caller passed.
        "role_mapping_passed": bool(
            val.get("role_mapping_passed") or role_ev.get("role_mapping_passed")
        ),
        # -- routes --------------------------------------------------------
        "callback_route_available": bool(routes.get("callback_route_available")),
        # Gate 116: reads whether a policy *exists*, not whether a route
        # enforces one. The field is named "available" and was measuring
        # enforcement, which meant a defined policy could never satisfy it.
        "session_cookie_policy_available": bool(
            routes.get("session_cookie_policy_available")
        ),
        # -- contracts -----------------------------------------------------
        "organization_id_resolution_available": _module_importable(
            "nativeforge.services.oidc_organization_id_resolution_service"
        ),
        "membership_verification_available": _module_importable(
            "nativeforge.services.customer_org_membership_verification_service"
        ),
        "rls_claim_guard_available": _module_importable(
            "nativeforge.services.rls_context_claim_guard_service"
        ),
        # -- posture -------------------------------------------------------
        "dev_header_disabled_for_production": bool(dev_header_disabled_for_production),
        # -- signing -------------------------------------------------------
        # Readiness, not presence: a key that came from the committed fixture is
        # present and may not sign anything a customer would be held to.
        "session_signing_key_ready": bool(signing.get("can_sign_production_session")),
    }

    blocked_reasons: list[str] = []
    for name in REQUIRED_AUTH_GATES:
        if not gates[name]:
            blocked_reasons.append(f"auth_gate_not_satisfied:{name}")

    # JWKS unvalidated is distinguished from JWKS validated-and-failed. Nothing
    # has been checked, and saying "failed" would be a fabricated measurement.
    # Gate 133B: a recorded event that reached the provider IS a network
    # check having happened. The preflight cannot see it - it runs offline and
    # the check happened inside a callback - so an unchecked preflight is no
    # longer the whole answer.
    jwks_unchecked = pre.get("jwks_reachable") is None and not jwks_ev.get(
        "provider_called"
    )
    if not gates["issuer_jwks_validated"] and jwks_unchecked:
        blocked_reasons.append("issuer_jwks_unvalidated_no_network_check_performed")

    if not owner_approval:
        blocked_reasons.append("owner_has_not_authorized_customer_auth_activation")

    # Derived affirmatively. Every conjunct must hold.
    all_auth_gates = all(gates[name] for name in REQUIRED_AUTH_GATES)
    all_login_gates = all(gates[name] for name in REQUIRED_LOGIN_GATES)

    customer_auth_live = bool(all_auth_gates and owner_approval)

    # Gate 133D. One env var used to gate both of these, which meant the only
    # way to admit that a working demo login works was to also claim customer
    # auth is live for real Tribes. They are different decisions and now have
    # different inputs.
    #
    # `or`, not replacement: approving customer auth approves the login path
    # it runs on, so the broad approval subsumes the narrow one. The narrow
    # one cannot work in the other direction -
    # `approves_customer_auth_live()` has no branch that returns True.
    login_activation_approved = bool(login_decision.get("approves_login_live"))
    login_approval = bool(owner_approval or login_activation_approved)

    # Login can run before the dev header is gone; customer auth is not live
    # while an unauthenticated header can still set the RLS context.
    login_live = bool(all_login_gates and login_approval)
    activation_allowed = customer_auth_live

    # Gate 121B. Consulted for *naming*, never for deriving: the sixteen gates
    # above decide, and this classifies what is missing by who would have to
    # act. Folding the preflight into the derivation would double-count the
    # facts the gates already measure, and a gate that could be satisfied two
    # ways is a gate nobody can reason about.
    #
    # Imported lazily. Nothing the preflight touches imports this module, but a
    # module-level import would make that a matter of luck rather than design.
    preflight = environment_preflight
    if preflight is None:
        from nativeforge.services.customer_auth_environment_preflight_service import (  # noqa: E501
            build_environment_preflight,
        )

        preflight = build_environment_preflight()

    activation_blockers = {
        # Each is a distinct operator action, and lumping them together is how
        # "auth is not configured" becomes an unactionable sentence.
        "provider_configuration_missing": not bool(
            preflight.get("provider_env_present")
        ),
        "secret_configuration_missing": not bool(preflight.get("secret_env_present")),
        "signing_key_not_fit_to_sign": str(
            preflight.get("signing_key_source") or "missing"
        )
        not in {"environment", "secret_manager"},
        "database_revision_not_applied": not bool(
            preflight.get("database_revision_ready")
        ),
        "callback_url_does_not_match_a_route": not bool(
            preflight.get("callback_path_matches_route")
        ),
        "role_mapping_not_validated": not gates["role_mapping_passed"],
        "dev_header_still_in_place": bool(
            preflight.get("dev_header_production_blocker")
        ),
        "owner_authorization_absent": not bool(owner_approval),
    }

    next_required_actions = [
        {"gate": name, "action": GATE_REMEDIES[name]}
        for name in REQUIRED_AUTH_GATES
        if not gates[name]
    ]
    if all_login_gates and not login_approval:
        next_required_actions.append(
            {
                "gate": "login_activation_decision",
                "action": (
                    "every measured login gate passes; record the owner's "
                    "demo login activation decision "
                    "(customer_auth_owner_activation_decision_service) or set "
                    f"{ACTIVATION_APPROVAL_ENV} for the broader claim"
                ),
            }
        )
    if not owner_approval:
        next_required_actions.append(
            {
                "gate": "owner_approval",
                "action": (
                    f"owner sets {ACTIVATION_APPROVAL_ENV} out-of-band. Every "
                    "gate passing is necessary and not sufficient: configuration "
                    "arriving in an environment is not a decision to expose a "
                    "login page to real Tribes."
                ),
            }
        )

    result = _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            **gates,
            "customer_auth_live": customer_auth_live,
            "login_live": login_live,
            "activation_allowed": activation_allowed,
            "owner_approval_present": bool(owner_approval),
            "login_activation_approved": login_activation_approved,
            "login_approval_present": login_approval,
            "jwks_validation_evidence_supplied": bool(jwks_ev),
            "role_mapping_evidence_supplied": bool(role_ev),
            "dev_header_exposure_supplied": bool(dev_header_exposure),
            "dev_header_routes_measured": (
                (dev_header_exposure or {}).get("dev_header_route_count")
            ),
            "missing_auth_gates": [
                name for name in REQUIRED_AUTH_GATES if not gates[name]
            ],
            "missing_login_gates": [
                name for name in REQUIRED_LOGIN_GATES if not gates[name]
            ],
            "issuer_jwks_network_check_performed": not jwks_unchecked,
            # Gate 121E. The same refusal, classified by who has to act on it.
            "activation_blockers": {
                name: bool(value) for name, value in sorted(activation_blockers.items())
            },
            "activation_blocker_names": sorted(
                name for name, value in activation_blockers.items() if value
            ),
            "operator_actionable_blocker_count": sum(
                1 for value in activation_blockers.values() if value
            ),
            "blocked_reasons": sorted(set(blocked_reasons)),
            "next_required_actions": next_required_actions,
            # Constants. A gate decides; it authenticates nobody.
            "secret_value_emitted": False,
            "secrets_stored": False,
            "network_calls": False,
            "identity_provider_contacted": False,
            "real_users_created": False,
            "real_sessions_created": False,
            "current_org_id_set": False,
            "fabricated": False,
        }
    )

    # Second, independent leak check. The preflight service performs its own
    # before returning; this one covers everything assembled since. A leaked
    # client secret is the one mistake in this gate that cannot be walked back.
    blob = json.dumps(result)
    for key in OIDC_ENV_KEYS:
        raw = os.environ.get(key) or ""
        if raw and len(raw) >= 8 and raw in blob:
            result["secret_value_emitted"] = True
            result["customer_auth_live"] = False
            result["login_live"] = False
            result["activation_allowed"] = False
            result["blocked_reasons"] = sorted(
                {*result["blocked_reasons"], "secret_value_leaked_into_output"}
            )
            break

    return result


def _dev_header_enabled() -> bool:
    """Is the unauthenticated org header still the way an org is chosen?"""
    try:
        from nativeforge.lib.settings import get_settings

        return bool(get_settings().nf_dev_org_headers)
    except Exception:  # pragma: no cover - settings always load in this repo
        # Unknown means enabled. An unreadable setting is not permission.
        return True


def activation_gate_invariant_failures(gate: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if gate.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in GATE_FIELDS:
        if field not in gate:
            fails.append(f"activation_gate_missing_field:{field}")

    for constant in (
        "secrets_stored",
        "network_calls",
        "identity_provider_contacted",
        "real_users_created",
        "real_sessions_created",
        "current_org_id_set",
        "fabricated",
    ):
        if gate.get(constant) is not False:
            fails.append(f"activation_gate_claimed:{constant}")

    # A leaked secret invalidates everything the result says.
    if gate.get("secret_value_emitted"):
        fails.append("activation_gate_emitted_a_secret_value")
        for claim in ("customer_auth_live", "login_live", "activation_allowed"):
            if gate.get(claim):
                fails.append(f"claim_survived_a_secret_leak:{claim}")

    # The rule this service exists to enforce.
    if gate.get("customer_auth_live"):
        for name in REQUIRED_AUTH_GATES:
            if not gate.get(name):
                fails.append(f"customer_auth_live_without:{name}")
        if not gate.get("owner_approval_present"):
            fails.append("customer_auth_live_without_owner_approval")
        if gate.get("missing_auth_gates"):
            fails.append("customer_auth_live_with_missing_gates")

    if gate.get("login_live"):
        for name in REQUIRED_LOGIN_GATES:
            if not gate.get(name):
                fails.append(f"login_live_without:{name}")
        # Gate 133D: either approval will do, and one of them must be there.
        # A login called live on nobody's decision is the claim this campaign
        # exists to prevent.
        if not gate.get("owner_approval_present") and not gate.get(
            "login_activation_approved"
        ):
            fails.append("login_live_without_a_login_activation_decision")

    # The narrow decision must never reach the broad claim.
    if gate.get("customer_auth_live") and not gate.get("owner_approval_present"):
        fails.append("customer_auth_live_on_a_login_only_decision")

    # Activation is exactly customer auth being live; two names, one decision.
    if gate.get("activation_allowed") is not gate.get("customer_auth_live"):
        fails.append("activation_allowed_disagrees_with_customer_auth_live")

    # Customer auth cannot be live while an unauthenticated header still sets
    # the RLS context, whatever else passed.
    if gate.get("customer_auth_live") and not gate.get(
        "dev_header_disabled_for_production"
    ):
        fails.append("customer_auth_live_with_the_dev_header_still_enabled")

    # A validated issuer requires a check to have happened.
    if gate.get("issuer_jwks_validated") and not gate.get(
        "issuer_jwks_network_check_performed"
    ):
        fails.append("issuer_jwks_validated_without_a_check_being_performed")

    # The missing lists must agree with the gates they summarise.
    expected_missing = [name for name in REQUIRED_AUTH_GATES if not gate.get(name)]
    if list(gate.get("missing_auth_gates") or []) != expected_missing:
        fails.append("missing_auth_gates_disagrees_with_the_gates")

    # Every unmet gate must point somewhere.
    actions = {entry.get("gate") for entry in gate.get("next_required_actions") or []}
    for name in expected_missing:
        if name not in actions:
            fails.append(f"unmet_gate_without_a_next_action:{name}")

    # A refusal must name itself.
    if not gate.get("activation_allowed") and not gate.get("blocked_reasons"):
        fails.append("activation_refused_without_a_reason")

    return fails
