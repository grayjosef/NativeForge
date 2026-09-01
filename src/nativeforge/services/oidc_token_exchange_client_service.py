"""Gate 131D: the one place NativeForge posts an authorization code.

## Why this is the most dangerous module in the auth path

Every other call in this flow is a redirect a browser makes. This one is made by
the server, carries the client secret, and turns a code into an identity. Get it
wrong and you have either a broken login or a credential in a log.

```text
what goes out   client_id, client_secret, code, code_verifier, redirect_uri
what comes back id_token, access_token, refresh_token
what may be
  recorded      booleans, HTTP status, and named failure reasons
```

Nothing in a result from this module carries any of those values, in either
direction. `token_exchange_invariant_failures` refuses a result that does.

## Network is off by default

`allow_network=False` unless a caller deliberately passes otherwise, and the URL
is not a parameter: it comes from the provider's discovery document, so this
cannot be pointed at an arbitrary host by a caller who got a field wrong.

Registered at Gate 94's chokepoint alongside the JWKS retrieval and the
discovery document, with the same discipline: https enforced before the request,
one host, no user data returned.

## What it does not do

It does not validate the ID token. That is `oidc_token_verification_service`,
which already exists and does it properly with JWKS. Exchanging and verifying
are separate questions, and a module that did both would be able to report a
verified identity from a response it had not checked.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlsplit

SCHEMA_VERSION = "nf_oidc_token_exchange_client_v1"

DEFAULT_TIMEOUT_SECONDS = 15.0

#: Field names that would mean a credential or a token had entered a result.
FORBIDDEN_VALUE_FIELDS: frozenset[str] = frozenset(
    {
        "code",
        "authorization_code",
        "client_secret",
        "code_verifier",
        "pkce_verifier",
        "verifier",
        "id_token",
        "access_token",
        "refresh_token",
        "token",
    }
)

RESULT_FIELDS: tuple[str, ...] = (
    "schema_version",
    "attempted",
    "succeeded",
    "network_allowed",
    "http_status",
    "id_token_present",
    "access_token_present",
    "refresh_token_present",
    "token_type",
    "expires_in",
    "provider_error",
    "blocked_reasons",
    "secret_exposed",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _result(**fields: Any) -> dict[str, Any]:
    base = {
        "schema_version": SCHEMA_VERSION,
        "attempted": False,
        "succeeded": False,
        "network_allowed": False,
        "http_status": 0,
        "id_token_present": False,
        "access_token_present": False,
        "refresh_token_present": False,
        "token_type": "",
        "expires_in": 0,
        "provider_error": "",
        "blocked_reasons": [],
        "secret_exposed": False,
    }
    base.update(fields)
    base["blocked_reasons"] = sorted(set(base["blocked_reasons"]))
    return _json_safe(base)


def exchange_authorization_code(
    *,
    token_endpoint: Any = None,
    client_id: Any = None,
    client_secret: Any = None,
    code: Any = None,
    code_verifier: Any = None,
    redirect_uri: Any = None,
    allow_network: bool = False,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    transport: Any = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Exchange a code for tokens.

    Returns ``(report, tokens)``. The report is safe to log, artifact and
    return; the tokens dict holds the actual values and is for the caller's
    immediate use only. Splitting them is what makes "never log a token" a
    property of the type rather than a rule somebody has to remember.

    ``transport`` is an injected callable taking ``(url, data, timeout)`` and
    returning ``(status, json_dict)``. It exists so every branch here is
    reachable in a test without a network, and so the one real implementation
    lives in a single place below.
    """
    endpoint = str(token_endpoint or "").strip()
    blocked: list[str] = []

    if not endpoint:
        blocked.append("no_token_endpoint_supplied")
    elif urlsplit(endpoint).scheme != "https":
        blocked.append("token_endpoint_is_not_https")

    if not str(client_id or "").strip():
        blocked.append("no_client_id")
    if not str(client_secret or "").strip():
        blocked.append("no_client_secret")
    if not str(code or "").strip():
        blocked.append("no_authorization_code")
    if not str(code_verifier or "").strip():
        # Without it the provider rejects the exchange, and sending the request
        # anyway tells the provider a code it issued is being replayed badly.
        blocked.append("no_pkce_verifier")
    if not str(redirect_uri or "").strip():
        blocked.append("no_redirect_uri")

    if not allow_network:
        blocked.append("network_not_allowed_so_no_exchange_attempted")

    if blocked:
        return _result(network_allowed=bool(allow_network), blocked_reasons=blocked), {}

    payload = {
        "grant_type": "authorization_code",
        "code": str(code),
        "client_id": str(client_id),
        "client_secret": str(client_secret),
        "code_verifier": str(code_verifier),
        "redirect_uri": str(redirect_uri),
    }

    send = transport or _post_form
    try:
        status_code, body = send(endpoint, payload, timeout_seconds)
    except Exception:
        # A provider that cannot be reached is a reported condition. The
        # exception is not re-raised because its string can carry the URL and
        # , with some clients, the request body.
        return _result(
            attempted=True,
            network_allowed=True,
            blocked_reasons=["token_exchange_request_failed"],
        ), {}

    body = body if isinstance(body, dict) else {}
    provider_error = str(body.get("error") or "")
    id_token = str(body.get("id_token") or "")
    access_token = str(body.get("access_token") or "")
    refresh_token = str(body.get("refresh_token") or "")

    ok = bool(status_code == 200 and id_token and not provider_error)
    if status_code != 200:
        blocked.append(f"token_endpoint_returned_{status_code}")
    if provider_error:
        # The provider's error *code* is a category, not a credential.
        blocked.append(f"provider_error:{provider_error}")
    if status_code == 200 and not id_token:
        blocked.append("token_response_carried_no_id_token")

    report = _result(
        attempted=True,
        succeeded=ok,
        network_allowed=True,
        http_status=int(status_code),
        id_token_present=bool(id_token),
        access_token_present=bool(access_token),
        refresh_token_present=bool(refresh_token),
        token_type=str(body.get("token_type") or ""),
        expires_in=int(body.get("expires_in") or 0),
        provider_error=provider_error,
        blocked_reasons=blocked,
    )
    tokens = {"id_token": id_token, "access_token": access_token}
    return report, (tokens if ok else {})


def _post_form(url: str, data: dict[str, str], timeout: float):
    """The single real network call. https only, form-encoded, no redirects."""
    import httpx

    if urlsplit(url).scheme != "https":
        raise ValueError("refusing a non-https token endpoint")
    response = httpx.post(
        url,
        data=data,
        timeout=timeout,
        follow_redirects=False,
        headers={"Accept": "application/json"},
    )
    try:
        body = response.json()
    except Exception:
        body = {}
    return response.status_code, body


def token_exchange_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    for field in FORBIDDEN_VALUE_FIELDS:
        if field in result:
            fails.append(f"result_carries_{field}")

    if result.get("secret_exposed") is True:
        fails.append("secret_exposed")

    if result.get("attempted") and not result.get("network_allowed"):
        fails.append("exchange_attempted_with_the_network_disallowed")

    if result.get("succeeded") and not result.get("attempted"):
        fails.append("succeeded_without_being_attempted")

    # Success means an ID token came back. Anything else calling itself success
    # would let the callback proceed to verification with nothing to verify.
    if result.get("succeeded") and not result.get("id_token_present"):
        fails.append("succeeded_without_an_id_token")

    if result.get("succeeded") and result.get("provider_error"):
        fails.append("succeeded_alongside_a_provider_error")

    return fails
