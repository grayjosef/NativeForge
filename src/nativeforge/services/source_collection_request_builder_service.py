"""Request construction (Gate 161E).

Deterministic. Opens nothing, resolves nothing, and has no parameter that
accepts a credential.

## The URL comes from the source definition, never from a caller

`build_source_request` takes a source definition and produces a
`TransportRequest`. There is no `url=` parameter on the public path, because a
function that accepts a URL from a request handler is an SSRF surface, and the
route layer would then be the only thing standing between a caller and an
arbitrary host.

A caller supplies *which source*, and the source definition supplies where it
lives. That is the difference between "fetch this source" and "fetch this URL",
and only the first is a thing this system does.

## Credentials have no door here

There is no `api_key`, no `token`, no `auth` parameter and no header the caller
can set. `ALLOWED_REQUEST_HEADERS` on the transport boundary refuses anything
outside a short allowlist, and this builder only ever produces headers from that
set.

When a source eventually needs a credential, that is a Gate 162 decision about
which sources may be reached and a later gate's mechanism for holding the
secret. Neither belongs in a request builder, and leaving the door out now means
nobody has to remember to lock it.

## A query string is built from declared parameters only

```text
declared in the source definition   -> may appear in the query
supplied by a caller                -> refused
anything credential-shaped          -> refused by name AND by value
```

The second check matters because a source definition is data, and data can be
wrong. A `query_params` entry called `api_key` is refused even though the
definition declared it, because the definition is not an authorization to store
a secret in a URL.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode, urlparse

from nativeforge.services.source_collection_transport_service import (
    ALLOWED_METHODS,
    ALLOWED_REQUEST_HEADERS,
    DEFAULT_TIMEOUT_SECONDS,
    TransportRequest,
)

SCHEMA_VERSION = "nf_source_collection_request_builder_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

#: Query parameter names that may never appear, whatever a source definition
#: says. Checked by exact name, and the values are checked separately.
CREDENTIAL_PARAM_NAMES: frozenset[str] = frozenset(
    {
        "api_key",
        "apikey",
        "key",
        "token",
        "access_token",
        "auth",
        "auth_token",
        "password",
        "secret",
        "client_secret",
        "signature",
        "sig",
        "sas",
        "x-api-key",
    }
)

#: Only https. An http source would send whatever it sends in clear text, and
#: a redirect from http to https is a decision a transport should not be making
#: on a collection's behalf.
ALLOWED_SCHEMES: frozenset[str] = frozenset({"https"})

BLOCK_NO_SOURCE = "no_source_definition_supplied"
BLOCK_NO_ENDPOINT = "the_source_definition_declares_no_endpoint"
BLOCK_SCHEME = "endpoint_scheme_is_not_https"
BLOCK_BAD_METHOD = "method_outside_the_allowed_set"
BLOCK_CREDENTIAL_PARAM = "query_parameter_name_looks_like_a_credential"
BLOCK_CREDENTIAL_VALUE = "query_parameter_value_looks_like_a_credential"
BLOCK_CALLER_URL = "a_caller_supplied_url_is_never_accepted"
BLOCK_NO_HOST = "endpoint_has_no_host"


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _value_looks_like_a_credential(value: Any) -> str | None:
    """Ask Gate 95D's scanner rather than inventing a second set of rules."""
    text = str(value or "")
    if not text.strip():
        return None
    try:
        from nativeforge.services.raw_payload_secret_scan_service import (
            scan_payload_for_secrets,
        )
    except ImportError:  # pragma: no cover - the scanner is part of the repo
        return None
    try:
        result = scan_payload_for_secrets(body=text)
    except Exception:  # noqa: BLE001 - a scanner failure refuses the value
        return "scanner_failed_so_the_value_is_refused"
    findings = result.get("findings") or []
    if findings:
        return ",".join(sorted({str(f.get("kind") or "unknown") for f in findings}))
    return None


def build_source_request(
    *,
    source_definition: dict[str, Any] | None = None,
    user_agent: Any = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    caller_supplied_url: Any = None,
) -> dict[str, Any]:
    """Construct one request from a source definition. Never from a caller URL.

    `caller_supplied_url` exists ONLY so the refusal is reachable and testable.
    Passing anything but None is refused; it is not a way to set the URL.
    """
    definition = dict(source_definition or {})
    blocked: list[str] = []

    if caller_supplied_url is not None:
        # The SSRF refusal, made explicit and falsifiable. A parameter that
        # silently ignored the value would leave nothing to test.
        blocked.append(BLOCK_CALLER_URL)

    if not definition:
        blocked.append(BLOCK_NO_SOURCE)

    endpoint = str(definition.get("endpoint") or "").strip()
    if not endpoint:
        blocked.append(BLOCK_NO_ENDPOINT)

    parsed = urlparse(endpoint) if endpoint else None
    if parsed is not None:
        if parsed.scheme.lower() not in ALLOWED_SCHEMES:
            blocked.append(f"{BLOCK_SCHEME}:{parsed.scheme or 'none'}")
        if not parsed.netloc:
            blocked.append(BLOCK_NO_HOST)

    method = str(definition.get("method") or "GET").upper()
    if method not in ALLOWED_METHODS:
        blocked.append(f"{BLOCK_BAD_METHOD}:{method}")

    # ---- the query, from declared parameters only ----------------------
    declared = definition.get("query_params") or {}
    safe_params: dict[str, str] = {}
    refused_params: list[str] = []
    if isinstance(declared, dict):
        for name, value in declared.items():
            lowered = str(name).strip().lower()
            if lowered in CREDENTIAL_PARAM_NAMES:
                # Refused even though the definition declared it. A definition
                # is data; data can be wrong, and declaring a parameter is not
                # an authorization to put a secret in a URL.
                refused_params.append(lowered)
                blocked.append(f"{BLOCK_CREDENTIAL_PARAM}:{lowered}")
                continue
            finding = _value_looks_like_a_credential(value)
            if finding:
                refused_params.append(lowered)
                blocked.append(f"{BLOCK_CREDENTIAL_VALUE}:{lowered}:{finding}")
                continue
            safe_params[str(name)] = str(value)

    # ---- headers, from the transport's allowlist only ------------------
    headers: dict[str, str] = {}
    if user_agent:
        headers["User-Agent"] = str(user_agent)
    accept = definition.get("accept")
    if accept:
        headers["Accept"] = str(accept)
    # Conditional-request headers, when the source definition carries what a
    # previous attempt learned. These make a re-fetch cheap and are the reason
    # ETag and Last-Modified are on Gate 160's response allowlist.
    if definition.get("if_none_match"):
        headers["If-None-Match"] = str(definition["if_none_match"])
    if definition.get("if_modified_since"):
        headers["If-Modified-Since"] = str(definition["if_modified_since"])
    if method == "POST" and definition.get("content_type"):
        headers["Content-Type"] = str(definition["content_type"])

    for name in headers:
        if name.strip().lower() not in ALLOWED_REQUEST_HEADERS:
            blocked.append(f"header_outside_the_transport_allowlist:{name.lower()}")

    if blocked:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "scope": CONTROLLED_SCOPE,
                "usable": False,
                "blocked_reasons": sorted(set(blocked)),
                "refused_query_parameters": sorted(set(refused_params)),
                "request": None,
                "source_id": definition.get("source_id"),
                "network_calls": 0,
                "dns_resolved": False,
                "credentials_accepted": False,
                "source_monitoring_live": False,
            }
        )

    url = endpoint
    if safe_params:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{urlencode(sorted(safe_params.items()))}"

    request = TransportRequest(
        method=method,
        url=url,
        headers=headers,
        timeout_seconds=float(timeout_seconds),
        body_bytes=(
            str(definition.get("body") or "").encode("utf-8")
            if method == "POST" and definition.get("body")
            else None
        ),
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "usable": True,
            "blocked_reasons": [],
            "refused_query_parameters": sorted(set(refused_params)),
            # The description fingerprints the URL rather than carrying it.
            "request": request.describe(),
            "source_id": definition.get("source_id"),
            "method": method,
            "query_parameter_names": sorted(safe_params),
            "header_names": sorted(headers),
            "scheme": (parsed.scheme if parsed else None),
            "is_https": bool(parsed and parsed.scheme.lower() == "https"),
            "network_calls": 0,
            "dns_resolved": False,
            "credentials_accepted": False,
            "url_came_from": "the_source_definition",
            "source_monitoring_live": False,
        }
    ) | {"transport_request": request}


def request_builder_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Refuse a built request that carries something it must not."""
    fails: list[str] = []

    if result.get("credentials_accepted"):
        fails.append("the_builder_claimed_it_accepts_credentials")
    if result.get("dns_resolved"):
        fails.append("the_builder_claimed_it_resolved_a_name")
    if int(result.get("network_calls") or 0) != 0:
        fails.append("the_builder_counted_a_network_call")
    if result.get("source_monitoring_live"):
        fails.append("the_builder_claimed:source_monitoring_live")

    if result.get("usable") and result.get("blocked_reasons"):
        fails.append("usable_alongside_blocked_reasons")
    if not result.get("usable") and not result.get("blocked_reasons"):
        fails.append("unusable_without_naming_a_reason")
    if not result.get("usable") and result.get("request"):
        fails.append("an_unusable_result_still_produced_a_request")

    # Nothing credential-shaped may reach the query.
    for name in result.get("query_parameter_names") or []:
        if str(name).strip().lower() in CREDENTIAL_PARAM_NAMES:
            fails.append(f"a_credential_parameter_reached_the_query:{name}")

    # Nothing outside the transport allowlist may reach the headers.
    for name in result.get("header_names") or []:
        if str(name).strip().lower() not in ALLOWED_REQUEST_HEADERS:
            fails.append(f"a_header_outside_the_allowlist_was_built:{name}")

    # The description must never carry a URL.
    described = result.get("request") or {}
    if described and "url" in described:
        fails.append("the_request_description_carries_a_url")

    if result.get("usable") and not result.get("is_https"):
        fails.append("a_usable_request_is_not_https")

    if result.get("url_came_from") not in (None, "the_source_definition"):
        fails.append(f"the_url_came_from:{result.get('url_came_from')}")

    return sorted(set(fails))
