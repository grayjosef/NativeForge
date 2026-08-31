"""Gate 130A: where a provider's endpoints actually are.

## The defect this closes

Three endpoint paths were hardcoded under the issuer:

```text
AUTHORIZE_PATH = "/authorize"
TOKEN_PATH     = "/oauth/token"
JWKS_PATH      = "/.well-known/jwks.json"
```

Those are Auth0's conventions, and every gate that used them targeted Auth0, so
they were right. For Google they are wrong, and not merely by a path segment:

```text
                 concatenated under issuer          Google actually publishes
authorization    accounts.google.com/authorize      accounts.google.com/o/oauth2/v2/auth
token            accounts.google.com/oauth/token    oauth2.googleapis.com/token
jwks             accounts.google.com/.well-known/   www.googleapis.com/oauth2/v3/certs
                   jwks.json
```

Two of the three are on a **different host**. No amount of path concatenation
under the issuer can reach them, so a Google login built this way sends the
browser to a 404 and the flow ends before the user sees a consent screen.

The comments on those constants were honest about it — "discovery would fetch
these from the well-known document, which is the network call this gate does not
make". That was a fair trade while the provider was Auth0-shaped. It stops being
one the moment the provider is not.

## Declared versus derived, once more

An endpoint assembled from a convention is a *declaration*. An endpoint read
from the provider's own discovery document is *derived*. This campaign has spent
seven gates on that distinction, and this is the same shape: a constant that was
accidentally correct for one provider and silently wrong for another.

So endpoints are reported with `discovered` beside them. A caller that needs to
know whether it is looking at a fact or a guess can ask, and
`endpoints_are_conventional` says plainly when they are a guess.

## Network

Off by default, as everywhere else in this campaign. `allow_network=True` is a
deliberate, per-call decision and reaches exactly one URL: the configured
issuer's `/.well-known/openid-configuration`. It is the provider's own public
metadata document — it carries no credential, requires none, and returns no
user data.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlsplit

SCHEMA_VERSION = "nf_oidc_provider_discovery_v1"

DISCOVERY_PATH = "/.well-known/openid-configuration"

#: Auth0's conventions. Kept because several gates target Auth0 and reach these
#: offline, and removing them would break a working path to fix a different one.
#: They are a fallback that reports itself as a fallback.
CONVENTIONAL_AUTHORIZE_PATH = "/authorize"
CONVENTIONAL_TOKEN_PATH = "/oauth/token"
CONVENTIONAL_JWKS_PATH = "/.well-known/jwks.json"

#: Issuers whose endpoints are known not to follow the conventional shape.
#: Present so an offline caller is refused rather than handed a wrong URL —
#: `endpoints_are_conventional` being true for one of these is a defect, not a
#: degraded mode.
KNOWN_NON_CONVENTIONAL_ISSUERS: frozenset[str] = frozenset(
    {
        "https://accounts.google.com",
        "accounts.google.com",
    }
)

ENDPOINT_FIELDS: tuple[str, ...] = (
    "authorization_endpoint",
    "token_endpoint",
    "jwks_uri",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _normalise_issuer(issuer: Any) -> str:
    return str(issuer or "").strip().rstrip("/")


def discovery_url(issuer: Any) -> str:
    """Where the provider publishes its metadata. Empty if no issuer."""
    root = _normalise_issuer(issuer)
    return f"{root}{DISCOVERY_PATH}" if root else ""


def fetch_provider_metadata(
    issuer: Any,
    *,
    allow_network: bool = False,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    """Read the issuer's discovery document. Denied unless network is allowed.

    Returns the parsed document under `metadata`, or names why it has none.
    Never raises for a network problem: a provider that cannot be reached is a
    reported condition, not a crash in a readiness path.
    """
    url = discovery_url(issuer)
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "issuer": _normalise_issuer(issuer),
        "discovery_url": url,
        "network_allowed": bool(allow_network),
        "attempted": False,
        "succeeded": False,
        "metadata": None,
        "blocked_reasons": [],
    }

    if not url:
        result["blocked_reasons"].append("no_issuer_configured")
        return _json_safe(result)
    if not allow_network:
        result["blocked_reasons"].append("network_not_allowed_so_nothing_fetched")
        return _json_safe(result)
    if urlsplit(url).scheme != "https":
        result["blocked_reasons"].append("discovery_url_is_not_https")
        return _json_safe(result)

    result["attempted"] = True
    try:
        import urllib.request

        with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
            if getattr(response, "status", 200) != 200:
                result["blocked_reasons"].append("discovery_document_not_200")
                return _json_safe(result)
            document = json.loads(response.read().decode("utf-8"))
    except Exception:
        # The provider's availability is not this service's to assert.
        result["blocked_reasons"].append("discovery_fetch_failed")
        return _json_safe(result)

    if not isinstance(document, dict):
        result["blocked_reasons"].append("discovery_document_not_an_object")
        return _json_safe(result)

    # A document that names a different issuer is not this provider's.
    declared = _normalise_issuer(document.get("issuer"))
    if declared and declared != _normalise_issuer(issuer):
        result["blocked_reasons"].append("discovery_document_issuer_mismatch")
        return _json_safe(result)

    result["succeeded"] = True
    result["metadata"] = document
    return _json_safe(result)


def build_provider_endpoints(
    issuer: Any,
    *,
    metadata: dict[str, Any] | None = None,
    allow_network: bool = False,
) -> dict[str, Any]:
    """The three endpoints, and whether they were discovered or guessed.

    `metadata` is injectable so every branch is reachable offline — the whole
    point of the discovered/conventional distinction is lost if a test can only
    ever see one of them.
    """
    root = _normalise_issuer(issuer)
    blocked_reasons: list[str] = []
    discovery: dict[str, Any] | None = None

    document = metadata
    if document is None and allow_network:
        discovery = fetch_provider_metadata(issuer, allow_network=True)
        document = discovery.get("metadata")
        blocked_reasons.extend(discovery.get("blocked_reasons") or [])

    endpoints: dict[str, str] = {}
    discovered = False
    if isinstance(document, dict):
        found = {
            field: str(document.get(field) or "").strip() for field in ENDPOINT_FIELDS
        }
        if all(found.values()):
            endpoints = found
            discovered = True
        else:
            missing = sorted(k for k, v in found.items() if not v)
            for name in missing:
                blocked_reasons.append(f"discovery_document_missing:{name}")

    conventional = False
    if not discovered:
        if not root:
            blocked_reasons.append("no_issuer_configured")
        elif root in KNOWN_NON_CONVENTIONAL_ISSUERS:
            # Known to not follow the convention. Guessing here is how a login
            # reaches a 404 with every gate reporting ready.
            blocked_reasons.append(
                f"issuer_does_not_follow_the_conventional_shape:{root}"
            )
        else:
            endpoints = {
                "authorization_endpoint": f"{root}{CONVENTIONAL_AUTHORIZE_PATH}",
                "token_endpoint": f"{root}{CONVENTIONAL_TOKEN_PATH}",
                "jwks_uri": f"{root}{CONVENTIONAL_JWKS_PATH}",
            }
            conventional = True

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "issuer": root,
            "discovery_url": discovery_url(issuer),
            "endpoints_available": bool(endpoints),
            "endpoints_discovered": discovered,
            "endpoints_are_conventional": conventional,
            "network_allowed": bool(allow_network),
            "network_attempted": bool(discovery and discovery.get("attempted")),
            "authorization_endpoint": endpoints.get("authorization_endpoint", ""),
            "token_endpoint": endpoints.get("token_endpoint", ""),
            "jwks_uri": endpoints.get("jwks_uri", ""),
            "blocked_reasons": sorted(set(blocked_reasons)),
            "secret_exposed": False,
            "provider_called": bool(discovery and discovery.get("attempted")),
        }
    )


def provider_discovery_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("secret_exposed") is True:
        fails.append("secret_exposed")

    # Both true would mean the same endpoints were read and guessed at once.
    if result.get("endpoints_discovered") and result.get("endpoints_are_conventional"):
        fails.append("discovered_and_conventional_at_once")

    # The defect this service exists to prevent.
    issuer = _normalise_issuer(result.get("issuer"))
    if issuer in KNOWN_NON_CONVENTIONAL_ISSUERS and result.get(
        "endpoints_are_conventional"
    ):
        fails.append(f"conventional_endpoints_for_known_non_conventional:{issuer}")

    # An endpoint on the issuer's host is not automatically wrong, but claiming
    # discovery while producing nothing is.
    if result.get("endpoints_discovered") and not result.get("authorization_endpoint"):
        fails.append("discovered_without_an_authorization_endpoint")

    if result.get("network_attempted") and not result.get("network_allowed"):
        fails.append("network_attempted_without_permission")

    return fails
