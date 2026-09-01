"""Gate 133D: one approval, split into the two decisions it was standing in for.

## The problem with one env var

```python
ACTIVATION_APPROVAL_TOKEN = "MAYHEM_APPROVES_NATIVEFORGE_CUSTOMER_AUTH_ACTIVATION"
owner_approval = os.environ.get(APPROVAL_ENV, "") == APPROVAL_TOKEN
```

That one boolean gated both `customer_auth_live` and `login_live`. They are not
the same decision:

```text
login_live           the demo login path works and may be called live
customer_auth_live   customer authentication is live, for real Tribal
                     governments, on real organizations
```

Approving the first says nothing about the second. Gate 132's authorization was
explicit about its own scope - the demo organization only, "do not create
production bindings" - so reading it as approval for customer auth would be
inventing consent. And leaving `login_live` gated on the customer-auth approval
means the only way to admit that a working login works is to also claim customer
auth is live.

So this module represents the narrow decision and **cannot represent the broad
one**. `approves_customer_auth_live()` takes no arguments and returns `False`.
There is no parameter, no env var and no override that changes it. The broad
approval stays where it was, in `NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL`, unset.

## Why this is a committed record and not an env var

An approval is a decision, not a measurement, and the honest place for a
decision in this campaign is the repository - which is where every other one has
been recorded. An env var would put `login_live` at the mercy of whichever
machine ran the code, and the artifacts this feeds are committed.

What keeps a committed "approved" from being the declared-vs-derived defect is
that it approves almost nothing:

```text
scope             one organization_id, checked per call
provider          Google, checked per call
environment       dev/demo, checked against app_env
what it approves  login_live, and only if the measured facts pass anyway
what it cannot    customer_auth_live, production, a real org, a binding, a
                  persistence claim - none of which have a code path here
```

The decision does not make `login_live` true. It removes the *last* reason it
was false. Every measured conjunct still has to hold, which is why this is a
gate input and not a switch.

## Revocable without a deploy

`NF_DEMO_LOGIN_ACTIVATION_REVOKED` set to anything truthy turns it off. Only
off: there is deliberately no env var that turns it on, because an approval that
can be granted by an environment variable is an approval anybody with shell
access can grant.
"""

from __future__ import annotations

import json
import os
from typing import Any

SCHEMA_VERSION = "nf_customer_auth_owner_activation_decision_v1"

#: The one organization this decision covers. Gate 132's authorization named it.
APPROVED_ORGANIZATION_ID = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"

#: Named so the refusal is exercised rather than implied.
REFUSED_ORGANIZATION_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

APPROVED_PROVIDER = "google"
APPROVED_ISSUER = "https://accounts.google.com"

#: Environments the decision covers. `production` and `unknown` are absent: a
#: deployment that cannot say what it is does not get an approval.
APPROVED_ENVIRONMENTS: frozenset[str] = frozenset({"local", "dev", "test"})

#: Off, and only off. There is no counterpart that turns the decision on.
REVOCATION_ENV = "NF_DEMO_LOGIN_ACTIVATION_REVOKED"

#: What the decision covers, quoted from the instruction that granted it.
AUTHORIZATION_SOURCE = (
    "Gate 132 authorization: 'Authorization is limited to the demo organization "
    "only: organization_id: bbbbbbbb-cccc-dddd-eeee-ffffffffffff, org_type: "
    "demo, is_demo: true'; Gate 133 instruction: 'Record the owner-approved "
    "demo login activation decision' and 'Make login_live true if and only if "
    "the facts prove it.'"
)

#: Every claim this decision explicitly does not make. Enumerated so a test can
#: assert each one is refused, rather than trusting that none was mentioned.
NOT_APPROVED: tuple[str, ...] = (
    "customer_auth_live",
    "production_rollout",
    "real_organization_binding",
    "verified_operational_binding",
    "customer_persistence_live",
    "dev_header_production_exposure",
    "collector_activation",
    "email_delivery",
    "object_store_access",
    "live_grant_source_calls",
)

RESULT_FIELDS: tuple[str, ...] = (
    "schema_version",
    "decision_recorded",
    "approves_login_live",
    "approves_customer_auth_live",
    "organization_id",
    "organization_in_scope",
    "provider",
    "provider_in_scope",
    "environment",
    "environment_in_scope",
    "revoked",
    "authorization_source",
    "not_approved",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _revoked() -> bool:
    return str(os.environ.get(REVOCATION_ENV, "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _environment(app_env: str | None = None) -> str:
    if app_env is not None:
        return str(app_env).strip().lower()
    from nativeforge.lib.settings import get_settings

    return str(get_settings().app_env or "").strip().lower()


def build_owner_activation_decision(
    *,
    organization_id: Any = None,
    provider: Any = None,
    app_env: str | None = None,
) -> dict[str, Any]:
    """Does the owner's decision cover this organization, provider and env?

    Every field is checked per call. A decision that approved "the demo login"
    once and then applied to whatever a caller passed would be a decision about
    nothing.
    """
    requested_org = str(organization_id or "").strip().lower()
    requested_provider = str(provider or "").strip().lower()
    environment = _environment(app_env)

    blocked_reasons: list[str] = []

    org_in_scope = requested_org == APPROVED_ORGANIZATION_ID
    if not requested_org:
        blocked_reasons.append("no_organization_id_supplied")
    elif requested_org == REFUSED_ORGANIZATION_ID:
        blocked_reasons.append("organization_is_the_explicitly_refused_real_org")
    elif not org_in_scope:
        blocked_reasons.append("organization_outside_the_approved_scope")

    provider_in_scope = requested_provider in {APPROVED_PROVIDER, APPROVED_ISSUER}
    if not requested_provider:
        blocked_reasons.append("no_provider_supplied")
    elif not provider_in_scope:
        blocked_reasons.append(
            f"provider_outside_the_approved_scope:{requested_provider}"
        )

    env_in_scope = environment in APPROVED_ENVIRONMENTS
    if not env_in_scope:
        blocked_reasons.append(
            f"environment_outside_the_approved_scope:{environment or 'unset'}"
        )

    revoked = _revoked()
    if revoked:
        blocked_reasons.append("decision_revoked_by_environment")

    approves_login_live = bool(
        org_in_scope
        and provider_in_scope
        and env_in_scope
        and not revoked
        and not blocked_reasons
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "decision_recorded": True,
            "approves_login_live": approves_login_live,
            # No parameter reaches this. It is not a default that a caller can
            # change; it is the shape of the decision.
            "approves_customer_auth_live": False,
            "organization_id": requested_org or None,
            "organization_in_scope": org_in_scope,
            "provider": requested_provider or None,
            "provider_in_scope": provider_in_scope,
            "environment": environment or None,
            "environment_in_scope": env_in_scope,
            "revoked": revoked,
            "authorization_source": AUTHORIZATION_SOURCE,
            "not_approved": list(NOT_APPROVED),
            "blocked_reasons": sorted(set(blocked_reasons)),
        }
    )


def approves_customer_auth_live() -> bool:
    """No. Takes no arguments, and there is no branch that returns True.

    The customer-auth approval lives in `NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL`
    and is checked by `customer_auth_activation_gate_service`. This module
    cannot grant it and must not look like it might.
    """
    return False


def decision_invariant_failures(decision: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if decision.get("approves_customer_auth_live"):
        fails.append("decision_approved_customer_auth_live")

    if decision.get("approves_login_live"):
        if not decision.get("organization_in_scope"):
            fails.append("login_live_approved_for_an_organization_out_of_scope")
        if decision.get("organization_id") == REFUSED_ORGANIZATION_ID:
            fails.append("login_live_approved_for_the_refused_real_org")
        if not decision.get("provider_in_scope"):
            fails.append("login_live_approved_for_a_provider_out_of_scope")
        if not decision.get("environment_in_scope"):
            fails.append("login_live_approved_in_an_environment_out_of_scope")
        if decision.get("revoked"):
            fails.append("login_live_approved_while_revoked")
        if decision.get("blocked_reasons"):
            fails.append("login_live_approved_alongside_blockers")

    missing = set(NOT_APPROVED) - set(decision.get("not_approved") or [])
    if missing:
        fails.append(f"not_approved_list_lost_entries:{sorted(missing)}")

    return fails
