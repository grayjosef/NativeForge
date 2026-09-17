"""The outbound transport boundary (Gate 161C).

## This module imports nothing network-capable, and that is the design

There is no `httpx`, no `requests`, no `socket` here. The boundary defines the
SHAPE of a transport and dispatches to an injected implementation — exactly the
pattern the three existing source transports already use, where the httpx import
is a default implementation rather than the interface:

```text
polite_http_get(url, ..., transport=None)
search_grants_gov_opportunities(source, http_post=None, ...)
resolve_url_real(url, ..., fetcher=None, ...)
```

A boundary that imported a client would be a fourth egress site. This one cannot
reach a host under any argument, which is a structural fact a verifier can prove
rather than a promise.

## Live transport is a hole, deliberately

`TRANSPORT_KINDS` names `live` and `execute_request` refuses it. There is no
live implementation in this repository, and Gate 161 does not write one:

```text
hermetic   implemented, and the only kind this gate can dispatch
live       NAMED, refused by policy, and ABSENT - no code to reach a host
```

Naming it matters. Leaving it out would mean adding it later under pressure,
and a vocabulary that pretends the live case does not exist cannot express
refusing it. Refusing a named thing is checkable; refusing an unnamed thing is
an omission somebody closes by accident.

## The guard decides; this dispatches

`live_network_guard_service` (Gate 94B) already owns the decision — deny by
default, requirements derived from purpose and collector type, nobody
self-exempts. This module does not re-implement any of that. It asks the
execution policy, which composes the guard, and refuses if the policy refuses.

Two layers, and they fail independently: the policy answers *may this source be
collected at all*, and this answers *may this transport kind run right now*. The
second can refuse for a reason the first never sees, such as a live transport
having no implementation.

## A response carries bytes, and never a credential

`TransportResponse` has `body_bytes`, a status, and headers that the caller is
expected to run through Gate 160's allowlist filter before persisting. It has no
field for a request header, an authorization value or a cookie, because a shape
with nowhere to put a credential cannot carry one.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_source_collection_transport_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

#: The kinds of transport this boundary knows about.
#:
#: `live` is named and has no implementation. See the module docstring.
HERMETIC = "hermetic"
LIVE = "live"

TRANSPORT_KINDS: tuple[str, ...] = (HERMETIC, LIVE)

#: The only kind Gate 161 can dispatch. Membership, not a negation of the
#: refused set - a kind added later is refused by default rather than permitted
#: by having been forgotten.
DISPATCHABLE_KINDS: frozenset[str] = frozenset({HERMETIC})

#: Methods a source request may use. Read-only: a collection that POSTed a
#: mutation to a source would be doing something nobody authorized, and
#: Grants.gov's search API is the one legitimate POST.
ALLOWED_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "POST"})

OUTCOME_OK = "response_received"
OUTCOME_TIMEOUT = "timeout"
OUTCOME_CONNECTION_FAILED = "connection_failed"
OUTCOME_REFUSED = "refused_before_dispatch"
OUTCOME_MALFORMED = "response_received_malformed_body"

TRANSPORT_OUTCOMES: tuple[str, ...] = (
    OUTCOME_OK,
    OUTCOME_TIMEOUT,
    OUTCOME_CONNECTION_FAILED,
    OUTCOME_REFUSED,
    OUTCOME_MALFORMED,
)

BLOCK_NO_TRANSPORT = "no_transport_implementation_supplied"
BLOCK_KIND_NOT_DISPATCHABLE = "transport_kind_is_not_dispatchable"
BLOCK_LIVE_NOT_IMPLEMENTED = "live_transport_has_no_implementation_in_this_repo"
BLOCK_POLICY_REFUSED = "the_execution_policy_refused_this_transport"
BLOCK_BAD_METHOD = "method_outside_the_allowed_set"
BLOCK_NO_URL = "no_request_url_supplied"
BLOCK_UNSAFE_REQUEST_HEADER = "request_header_outside_the_safe_set"

#: The only request headers this boundary will send. An allowlist, for the same
#: reason Gate 160 keeps one for responses: a header nobody has classified is
#: refused rather than kept because no pattern matched it.
#:
#: There is no Authorization here, and no mechanism to add one. Credentials are
#: Gate 162's decision and a later gate's mechanism.
ALLOWED_REQUEST_HEADERS: frozenset[str] = frozenset(
    {"user-agent", "accept", "accept-encoding", "accept-language", "if-none-match",
     "if-modified-since", "content-type"}
)

DEFAULT_TIMEOUT_SECONDS = 20.0

#: A response larger than Gate 160 can store is refused at the boundary rather
#: than fetched and then discarded.
MAX_RESPONSE_BYTES = 1024 * 1024


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


class TransportRequest:
    """What a transport is asked to do. Carries no credential."""

    __slots__ = ("method", "url", "headers", "timeout_seconds", "body_bytes")

    def __init__(
        self,
        *,
        method: str = "GET",
        url: str = "",
        headers: dict[str, str] | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        body_bytes: bytes | None = None,
    ) -> None:
        self.method = str(method or "GET").upper()
        self.url = str(url or "")
        self.headers = dict(headers or {})
        self.timeout_seconds = float(timeout_seconds)
        self.body_bytes = body_bytes

    def describe(self) -> dict[str, Any]:
        """A safe description. The URL is fingerprinted, never included."""
        from nativeforge.services.source_raw_payload_persistence_service import (
            fingerprint_url,
        )

        return _json_safe(
            {
                "method": self.method,
                # Never the URL. Query strings carry api keys, and Gate 160
                # settled this for stored evidence; a description is no
                # different.
                "url_fingerprint": fingerprint_url(self.url),
                "header_names": sorted(self.headers),
                "timeout_seconds": self.timeout_seconds,
                "has_body": self.body_bytes is not None,
                "body_size_bytes": len(self.body_bytes or b""),
            }
        )


class TransportResponse:
    """What came back. Bytes, a status, and headers the caller must filter."""

    __slots__ = ("status_code", "headers", "body_bytes", "outcome", "elapsed_seconds")

    def __init__(
        self,
        *,
        status_code: int | None = None,
        headers: dict[str, str] | None = None,
        body_bytes: bytes = b"",
        outcome: str = OUTCOME_OK,
        elapsed_seconds: float = 0.0,
    ) -> None:
        self.status_code = status_code
        self.headers = dict(headers or {})
        self.body_bytes = bytes(body_bytes or b"")
        self.outcome = str(outcome)
        self.elapsed_seconds = float(elapsed_seconds)


def _validate_request(request: TransportRequest) -> list[str]:
    blocked: list[str] = []
    if not request.url.strip():
        blocked.append(BLOCK_NO_URL)
    if request.method not in ALLOWED_METHODS:
        blocked.append(f"{BLOCK_BAD_METHOD}:{request.method}")
    for name in request.headers:
        if str(name).strip().lower() not in ALLOWED_REQUEST_HEADERS:
            # Named, so a caller can see WHICH header was refused without the
            # value appearing anywhere.
            blocked.append(f"{BLOCK_UNSAFE_REQUEST_HEADER}:{str(name).lower()}")
    return blocked


def _result(**fields: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "scope": CONTROLLED_SCOPE,
        "transport_kind": None,
        "dispatched": False,
        "outcome": OUTCOME_REFUSED,
        "status_code": None,
        "bytes_received": 0,
        "response_headers": {},
        "elapsed_seconds": 0.0,
        "blocked_reasons": [],
        "request": None,
        # Constants of this boundary. `live_source_call` is the one that
        # matters: a hermetic dispatch is not a call to anything.
        "live_source_call": False,
        "live_transport_enabled": False,
        "network_module_imported_here": False,
        "source_monitoring_live": False,
    }
    base.update(fields)
    base["blocked_reasons"] = sorted(set(base["blocked_reasons"] or []))
    return base


def execute_request(
    *,
    request: TransportRequest | None = None,
    transport_kind: str = HERMETIC,
    transport: Any = None,
    policy: dict[str, Any] | None = None,
    max_response_bytes: int = MAX_RESPONSE_BYTES,
) -> dict[str, Any]:
    """Dispatch one request through an injected transport, or refuse.

    `transport` is a callable taking a `TransportRequest` and returning a
    `TransportResponse`. It is injected rather than imported, which is why this
    module can be proven to reach nothing.
    """
    kind = str(transport_kind or "").strip()
    blocked: list[str] = []

    if kind not in TRANSPORT_KINDS:
        blocked.append(f"transport_kind_outside_vocabulary:{kind}")
    elif kind not in DISPATCHABLE_KINDS:
        blocked.append(f"{BLOCK_KIND_NOT_DISPATCHABLE}:{kind}")
        if kind == LIVE:
            # Said separately, because "not dispatchable" and "does not exist"
            # are different facts and an operator should see both.
            blocked.append(BLOCK_LIVE_NOT_IMPLEMENTED)

    # The policy decides whether this transport kind may run at all. It
    # composes Gate 94B's guard; this boundary does not re-decide.
    decision = policy or {}
    if decision:
        if kind == LIVE and not decision.get("live_transport_allowed"):
            blocked.append(BLOCK_POLICY_REFUSED)
        if kind == HERMETIC and not decision.get("hermetic_transport_allowed"):
            blocked.append(BLOCK_POLICY_REFUSED)

    if request is None:
        blocked.append("no_request_supplied")
        described = None
    else:
        blocked.extend(_validate_request(request))
        described = request.describe()

    if transport is None or not callable(transport):
        blocked.append(BLOCK_NO_TRANSPORT)

    if blocked:
        return _json_safe(
            _result(
                transport_kind=kind or None,
                blocked_reasons=blocked,
                request=described,
            )
        )

    response = transport(request)
    if not isinstance(response, TransportResponse):
        return _json_safe(
            _result(
                transport_kind=kind,
                blocked_reasons=["transport_returned_something_that_is_not_a_response"],
                request=described,
            )
        )

    body = response.body_bytes or b""
    if len(body) > int(max_response_bytes):
        # Refused at the boundary rather than handed on for Gate 160 to reject.
        # A response too large to store is a response nobody can keep evidence
        # of, and truncating it would produce bytes that never arrived.
        return _json_safe(
            _result(
                transport_kind=kind,
                dispatched=True,
                outcome=response.outcome,
                status_code=response.status_code,
                bytes_received=len(body),
                request=described,
                blocked_reasons=[
                    f"response_exceeds_max_bytes:{len(body)}>{int(max_response_bytes)}"
                ],
            )
        )

    return _json_safe(
        _result(
            transport_kind=kind,
            dispatched=True,
            outcome=response.outcome,
            status_code=response.status_code,
            bytes_received=len(body),
            response_headers=dict(response.headers),
            elapsed_seconds=response.elapsed_seconds,
            request=described,
            # A hermetic dispatch contacted nothing. The flag is derived from
            # the kind rather than passed in, so a transport cannot declare
            # itself hermetic while reaching a host.
            live_source_call=kind == LIVE,
        )
    ) | {"body_bytes": body}


def transport_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Refuse a dispatch result that claims something it must not."""
    fails: list[str] = []

    kind = result.get("transport_kind")
    if kind is not None and kind not in TRANSPORT_KINDS:
        fails.append(f"transport_kind_outside_vocabulary:{kind}")

    outcome = result.get("outcome")
    if outcome not in TRANSPORT_OUTCOMES:
        fails.append(f"outcome_outside_vocabulary:{outcome}")

    # THE invariant of this gate.
    if result.get("live_source_call"):
        fails.append("the_transport_reported_a_live_source_call")
    if result.get("live_transport_enabled"):
        fails.append("the_transport_reported_live_transport_enabled")
    if result.get("source_monitoring_live"):
        fails.append("the_transport_claimed:source_monitoring_live")
    if result.get("network_module_imported_here"):
        fails.append("the_boundary_claimed_it_imports_a_network_module")

    # A live dispatch must never succeed while this gate stands.
    if kind == LIVE and result.get("dispatched"):
        fails.append("a_live_transport_was_dispatched")

    if result.get("dispatched") and result.get("blocked_reasons"):
        # Except the oversize case, which dispatches and then refuses the body.
        if not any(
            "response_exceeds_max_bytes" in reason
            for reason in result["blocked_reasons"]
        ):
            fails.append("dispatched_alongside_blocked_reasons")

    if not result.get("dispatched") and not result.get("blocked_reasons"):
        fails.append("not_dispatched_without_naming_a_reason")

    # A refused dispatch must not report bytes.
    if not result.get("dispatched") and int(result.get("bytes_received") or 0):
        fails.append("a_refused_dispatch_reported_bytes")

    # The request description must never carry a URL or a credential.
    described = result.get("request") or {}
    if described:
        if "url" in described:
            fails.append("the_request_description_carries_a_url")
        for name in described.get("header_names") or []:
            lowered = str(name).lower()
            if lowered not in ALLOWED_REQUEST_HEADERS:
                fails.append(f"request_carried_an_unsafe_header:{lowered}")

    return sorted(set(fails))


def describe_boundary() -> dict[str, Any]:
    """What this boundary is, derived from its own module rather than declared.

    `network_modules_imported` is computed by parsing this file. A constant
    saying "none" would be correct today and wrong the day somebody adds an
    import, without anything changing in the line that says so.
    """
    import ast
    from pathlib import Path

    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    network = {
        "httpx",
        "requests",
        "aiohttp",
        "urllib3",
        "socket",
        "ftplib",
        "telnetlib",
        "selenium",
        "playwright",
        "urllib.request",
        "http.client",
    }
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in network or alias.name.split(".")[0] in network:
                    imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module in network or node.module.split(".")[0] in network:
                imported.add(node.module)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "transport_kinds": list(TRANSPORT_KINDS),
            "dispatchable_kinds": sorted(DISPATCHABLE_KINDS),
            "live_transport_implemented_here": False,
            "live_transport_enabled": False,
            "allowed_methods": sorted(ALLOWED_METHODS),
            "allowed_request_headers": sorted(ALLOWED_REQUEST_HEADERS),
            "max_response_bytes": MAX_RESPONSE_BYTES,
            "transport_is_injected_not_imported": True,
            # Derived by parsing this file.
            "network_modules_imported": sorted(imported),
            "reaches_a_host": bool(imported),
            "the_guard_that_decides": (
                "live_network_guard_service.build_live_network_decision, via "
                "source_collection_execution_policy_service"
            ),
            "legacy_transports_not_refactored": [
                "polite_http_fetch_service",
                "grants_gov_search_api_adapter_service",
                "real_url_resolver_service",
            ],
            "why_not_refactored": (
                "each is already guarded, already injectable, already on the "
                "approved list with a reason, and none is on the execution "
                "envelope's path. Rewriting three working transports to route "
                "through a boundary with no live implementation would move "
                "code and defer the benefit. See doc 837."
            ),
        }
    )
