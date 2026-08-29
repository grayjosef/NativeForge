"""Customer auth live detector (Gate 115F).

One question, one answer, cheaply: **is customer authentication live?**

## Why this exists rather than a direct dependency

Gate 115B's activation gate is the authority on this. Calling it directly from
the readiness surfaces would be wrong twice over:

```text
cost    the gate reads the route table, which imports nativeforge.main and
        builds the whole application. The capability model is called from three
        readiness services and two artifact writers, several times each.

cycles  nativeforge.main imports the route modules, which import services. A
        readiness service that reached the gate would be importing the
        application that imports it.
```

So this module answers the question with the two cheapest *necessary*
conditions first, and only pays for the full gate when both hold:

```text
provider configured?   seven env presence booleans, no values read
owner authorized?      one env comparison, value never reported
```

Either false means auth is not live, and no route table is loaded. Both true
means somebody has configured a provider and authorized activation, at which
point building the application to check for a callback route is worth it and
the full gate decides.

This is a short-circuit over necessary conditions, not a weaker rule. The
positive answer still comes from `build_customer_auth_activation_gate` with
every one of its fifteen gates checked.

## What it replaces

Gate 114 detected this by asking whether a customer-session module existed. That
was one conjunct of seven and could not on its own make a lane operational, but
it was still a module-existence proxy standing in for a fact nobody could
measure yet. Gate 115 can measure it, so the proxy is gone.

## Secrets

Presence and equality only. No value is read into a return, a log or a field.
"""

from __future__ import annotations

import os

from nativeforge.services.customer_auth_activation_gate_service import (
    ACTIVATION_APPROVAL_ENV,
    ACTIVATION_APPROVAL_TOKEN,
    OIDC_ENV_KEYS,
)

SCHEMA_VERSION = "nf_customer_auth_live_detector_v1"


def _all_oidc_env_present() -> bool:
    """Presence only. No value is returned, compared to, or recorded."""
    return all(
        bool((os.environ.get(key) or "").strip()) for key in OIDC_ENV_KEYS
    )


def _owner_authorized() -> bool:
    return os.environ.get(ACTIVATION_APPROVAL_ENV, "") == ACTIVATION_APPROVAL_TOKEN


def detect_customer_auth_live() -> bool:
    """Is customer authentication live? Deny by default.

    Two cheap necessary conditions, then the full activation gate. Never raises:
    a readiness surface that crashed while asking whether auth was live would be
    worse than one that answered no.
    """
    if not _all_oidc_env_present():
        return False
    if not _owner_authorized():
        return False

    try:
        from nativeforge.services.customer_auth_activation_gate_service import (
            build_customer_auth_activation_gate,
        )

        return bool(build_customer_auth_activation_gate().get("customer_auth_live"))
    except Exception:  # pragma: no cover - defensive; unknown is not permission
        return False


def detect_login_live() -> bool:
    """Is a customer login flow live? Same short-circuit, narrower gate set."""
    if not _all_oidc_env_present():
        return False
    if not _owner_authorized():
        return False

    try:
        from nativeforge.services.customer_auth_activation_gate_service import (
            build_customer_auth_activation_gate,
        )

        return bool(build_customer_auth_activation_gate().get("login_live"))
    except Exception:  # pragma: no cover - defensive; unknown is not permission
        return False
