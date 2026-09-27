"""What environment this deployment is, and what that obliges it to do.

Three places already decided this independently and did not agree:

```text
staging_environment_guard_service     PRODUCTION_ENVS = {production, prod}
customer_session_cookie_policy        production when app_env in {prod, production}
customer_auth_owner_activation        APPROVED_ENVIRONMENTS = {local, dev, test}
```

That was survivable while every environment was either a laptop or
`production`. It stopped being survivable the moment a fourth existed.

## controlled-live

`controlled-live` is a real Railway environment serving
`nativeforge.mayhem-nc.dev` over the public internet to invited people. It is
not a laptop and it is not the production launch.

The trap, and the reason this module exists rather than a one-line edit:
naming the environment `controlled-live` in the old model would have made
`_production_environment()` false, which would have dropped `secure` from the
session cookie. The deployment would have become *less* safe by being
described *more* honestly. A model where telling the truth costs you security
is a model that teaches people to lie.

So the two questions are separated, because they have different answers:

```text
is it internet-facing?      controlled-live YES - secure cookies, no dev headers
is it the production launch? controlled-live NO  - still fail-closed
```

## Eligibility is not approval

`APPROVED_ENVIRONMENTS` says which environments an owner's approval *can*
cover. It does not approve anything. Every other required gate still has to
pass, and `production` and `unknown` are absent on purpose: a deployment that
cannot say what it is does not get an approval.
"""

from __future__ import annotations

UNKNOWN = "unknown"

LOCAL = "local"
DEV = "dev"
TEST = "test"
STAGING = "staging"
CONTROLLED_LIVE = "controlled-live"
PRODUCTION = "production"

#: `prod` is an alias people type. It is not a second environment.
PRODUCTION_ENVS: frozenset[str] = frozenset({PRODUCTION, "prod"})

#: Reachable from the public internet, whatever else is true of it. These owe
#: their users production-grade transport: `Secure` on the session cookie, and
#: no unauthenticated header that can set a tenant context.
#:
#: `controlled-live` is here because the people using it are reaching it over
#: the internet. How few of them there are does not change what the cookie
#: travels over.
INTERNET_FACING_ENVS: frozenset[str] = PRODUCTION_ENVS | {CONTROLLED_LIVE}

#: Environments an owner's recorded approval may cover.
#:
#: `production` is deliberately absent: a full production launch is a separate,
#: explicit decision, and widening this set is not how it gets made. `unknown`
#: is absent for the same reason it always was.
APPROVAL_ELIGIBLE_ENVS: frozenset[str] = frozenset(
    {LOCAL, DEV, TEST, CONTROLLED_LIVE}
)

#: Every spelling this application recognises. Anything else normalises to
#: `unknown`, which is fail-closed everywhere it is consulted.
KNOWN_ENVS: frozenset[str] = frozenset(
    {LOCAL, DEV, TEST, STAGING, CONTROLLED_LIVE} | PRODUCTION_ENVS
)


def normalize_app_env(value: str | None) -> str:
    """One spelling, or `unknown`.

    Underscores and spaces fold to the hyphen this module uses, so
    `CONTROLLED_LIVE` and `controlled live` reach the same place as
    `controlled-live`. A value nobody recognises is not guessed at: it becomes
    `unknown`, and `unknown` is treated as the least privileged thing it could
    be, never the most.
    """
    text = str(value or "").strip().lower().replace("_", "-").replace(" ", "-")
    if not text:
        return UNKNOWN
    return text if text in KNOWN_ENVS else UNKNOWN


def is_internet_facing(value: str | None) -> bool:
    """Whether this deployment owes its users production-grade transport.

    `unknown` counts as internet-facing. A process that cannot say where it is
    running is not given the benefit of the doubt about who can reach it -
    getting this backwards is how a real deployment ends up with a cookie that
    is not `Secure`.
    """
    env = normalize_app_env(value)
    return env == UNKNOWN or env in INTERNET_FACING_ENVS


def is_production_launch(value: str | None) -> bool:
    """The production launch specifically, not merely "live".

    `controlled-live` is live and is not this.
    """
    return normalize_app_env(value) in PRODUCTION_ENVS


def is_approval_eligible(value: str | None) -> bool:
    """Whether an owner's approval may cover this environment at all.

    Eligibility, not approval: everything else still has to pass.
    """
    return normalize_app_env(value) in APPROVAL_ELIGIBLE_ENVS
