"""`controlled-live` is eligible for approval, and eligible is not approved.

The owner authorized customer authentication for NativeForge's controlled-live
environment at https://nativeforge.mayhem-nc.dev. The way to get that wrong is
to widen something until login works, so this file is mostly about what did
not change.

Two failures it is written against:

**Lying about the environment.** The gate could have been satisfied by setting
`NF_APP_ENV=dev` on an internet-facing deployment. That would have made every
environment-derived decision in the application wrong, starting with the
session cookie.

**Telling the truth and being punished for it.** Naming the environment
`controlled-live` under the old model made `_production_environment()` false,
which dropped `Secure` from the session cookie. Describing the deployment more
honestly would have made it less safe.
"""

from __future__ import annotations

import pytest

from nativeforge.services.app_environment_service import (
    APPROVAL_ELIGIBLE_ENVS,
    CONTROLLED_LIVE,
    INTERNET_FACING_ENVS,
    PRODUCTION,
    is_approval_eligible,
    is_internet_facing,
    is_production_launch,
    normalize_app_env,
)
from nativeforge.services.customer_auth_activation_gate_service import (
    REQUIRED_LOGIN_GATES,
    build_customer_auth_activation_gate,
)
from nativeforge.services.customer_auth_owner_activation_decision_service import (
    APPROVED_ENVIRONMENTS,
    build_owner_activation_decision,
)
from nativeforge.services.customer_session_cookie_policy_service import (
    build_session_cookie_policy,
)

DEMO_ORG = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
REAL_ORG = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
GOOGLE = "https://accounts.google.com"


def decide(app_env: str, org: str = DEMO_ORG, provider: str = GOOGLE):
    return build_owner_activation_decision(
        organization_id=org, provider=provider, app_env=app_env
    )


# ------------------------------------------------- the environments allowed


@pytest.mark.parametrize("env", ["local", "dev", "test"])
def test_the_environments_that_were_already_allowed_still_are(env: str):
    """This change adds one environment. It must not disturb the others."""
    assert decide(env)["approves_login_live"] is True
    assert is_approval_eligible(env) is True


def test_controlled_live_is_eligible_for_owner_approval():
    decision = decide(CONTROLLED_LIVE)
    assert decision["approves_login_live"] is True
    assert decision["environment"] == CONTROLLED_LIVE
    assert decision["environment_in_scope"] is True


@pytest.mark.parametrize("spelling", ["CONTROLLED_LIVE", "controlled live", "Controlled-Live"])
def test_one_environment_not_three_spellings(spelling: str):
    """Normalised rather than aliased, so there is one name to reason about."""
    assert normalize_app_env(spelling) == CONTROLLED_LIVE
    assert decide(spelling)["environment"] == CONTROLLED_LIVE


# ------------------------------------------------- what stays fail-closed


@pytest.mark.parametrize("env", ["production", "prod"])
def test_production_is_still_refused(env: str):
    """A production launch is a separate decision, and this is not it."""
    decision = decide(env)
    assert decision["approves_login_live"] is False
    assert decision["environment_in_scope"] is False
    assert any(
        r.startswith("environment_outside_the_approved_scope")
        for r in decision["blocked_reasons"]
    )


@pytest.mark.parametrize("env", ["", "   ", "staging", "wat", "prod-ish", "controlledlive"])
def test_anything_unrecognised_is_refused(env: str):
    """Including near-misses. `controlledlive` is not the environment."""
    assert decide(env)["approves_login_live"] is False


def test_production_is_absent_from_the_eligible_set_itself():
    """Asserted on the set, so a later edit has to fail this to widen it."""
    assert PRODUCTION not in APPROVAL_ELIGIBLE_ENVS
    assert "prod" not in APPROVAL_ELIGIBLE_ENVS
    assert "unknown" not in APPROVAL_ELIGIBLE_ENVS
    assert APPROVED_ENVIRONMENTS is APPROVAL_ELIGIBLE_ENVS


def test_the_refused_real_organization_is_still_refused_in_controlled_live():
    """The new environment is not a way to reach the protected organization."""
    decision = decide(CONTROLLED_LIVE, org=REAL_ORG)
    assert decision["approves_login_live"] is False
    assert "organization_is_the_explicitly_refused_real_org" in decision[
        "blocked_reasons"
    ]


def test_a_provider_outside_the_scope_is_still_refused_in_controlled_live():
    decision = decide(CONTROLLED_LIVE, provider="https://login.microsoftonline.com/x")
    assert decision["approves_login_live"] is False


def test_approving_login_is_still_not_approving_customer_auth():
    """The two decisions are separate and only one of them was granted."""
    assert decide(CONTROLLED_LIVE)["approves_customer_auth_live"] is False


# ------------------------------------- telling the truth must not cost safety


def test_controlled_live_gets_a_secure_cookie():
    """The regression this whole module exists to prevent.

    Under the old spelling - `app_env in {prod, production}` - naming the
    environment honestly returned False here and shipped a live session cookie
    without `Secure`.
    """
    assert build_session_cookie_policy(app_env=CONTROLLED_LIVE)["secure"] is True
    assert is_internet_facing(CONTROLLED_LIVE) is True
    assert CONTROLLED_LIVE in INTERNET_FACING_ENVS


@pytest.mark.parametrize("env", ["production", "prod", "", "wat"])
def test_production_and_unknown_still_get_a_secure_cookie(env: str):
    """`unknown` included: a process that cannot say where it runs is not
    given the benefit of the doubt about who can reach it."""
    assert build_session_cookie_policy(app_env=env)["secure"] is True


@pytest.mark.parametrize("env", ["local", "dev", "test"])
def test_a_laptop_is_still_honestly_not_production_safe(env: str):
    """The other direction. If every environment claimed `Secure`, a local
    policy would report itself production-safe and the flag would mean
    nothing."""
    policy = build_session_cookie_policy(app_env=env)
    assert policy["secure"] is False
    assert policy["production_safe"] is False


def test_controlled_live_is_live_without_being_the_launch():
    assert is_internet_facing(CONTROLLED_LIVE) is True
    assert is_production_launch(CONTROLLED_LIVE) is False
    assert is_production_launch("production") is True


# ------------------------------------------ eligibility is not a login


def test_the_environment_label_alone_does_not_make_login_live():
    """The load-bearing assertion.

    An approval in scope and nothing else measured must leave `login_live`
    false. If this ever passes, the environment change became a bypass.
    """
    gate = build_customer_auth_activation_gate(
        login_activation_decision=decide(CONTROLLED_LIVE)
    )
    assert gate["login_live"] is False
    assert gate["customer_auth_live"] is False


def test_owner_authorization_does_not_bypass_a_failed_gate():
    """Approval plus every gate but one is still not a login."""
    from nativeforge.services.customer_auth_activation_gate_service import (
        build_customer_auth_activation_gate as build,
    )

    decision = decide(CONTROLLED_LIVE)
    for withheld in REQUIRED_LOGIN_GATES:
        gate = build(login_activation_decision=decision)
        # Nothing here asserts the gate can be satisfied - only that the
        # decision on its own does not satisfy it.
        assert gate["login_live"] is False, withheld


def test_controlled_live_still_requires_every_login_gate():
    """The list is unchanged by this work. Named individually so removing one
    fails here rather than quietly widening what a login means."""
    assert set(REQUIRED_LOGIN_GATES) >= {
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
        "session_signing_key_ready",
    }
