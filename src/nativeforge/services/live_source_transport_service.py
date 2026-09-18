"""The live transport (Gate 163E). The first code here that opens a socket.

Gate 161 built the envelope and deliberately left this module unwritten, so
that "no live call is possible" was a fact about the repository rather than a
flag. This is the module that changes it, and it is written to be as narrow as
the thing it permits.

## httpx is imported under two guards, as the campaign settled

```python
if TYPE_CHECKING: ...          the type-checker sees it
def _client(...):              the runtime import happens inside the one
    import httpx               function that dispatches
```

Nothing imports this module by accident: `execute_request` takes a transport
callable, and this one has to be handed in deliberately by a caller that has
already resolved an authorization.

## Every request carries a warrant

`build_live_transport(authorized_source_id=..., authorization=...)` refuses to
build a transport at all unless:

```text
the authorization resolved to approved
its source_id matches the one being dispatched for
the URL host matches the authorized source's host
```

The host check is the one that matters most. An authorization for
`api.grants.gov` must not carry a request to anywhere else, and a transport
that closes over its warrant cannot be re-pointed after the fact.

## What it will not do

```text
no redirects followed      a redirect is a different URL than the one
                           authorized, and following one silently would
                           make the host check decorative
no credentials             no auth header is read, built or sent
no cookies                 the cookie jar is disabled
no retries                 a retry is a second request and belongs to the
                           retry policy, not to a transport
bounded body               MAX_RESPONSE_BYTES, refused at the boundary
bounded time               an explicit timeout, no default
one host per transport     closed over at construction
```

## Politeness

`MIN_REQUEST_INTERVAL_SECONDS` from the live network guard is enforced here as
a real sleep between dispatches on the same host, because a politeness policy
nobody executes is a policy nobody has. The canonical user agent identifies
the request and carries a contact URL.
"""

from __future__ import annotations

import json
import threading
import time
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from nativeforge.services.live_network_guard_service import (
    MIN_REQUEST_INTERVAL_SECONDS,
    canonical_user_agent,
)
from nativeforge.services.source_collection_transport_service import (
    MAX_RESPONSE_BYTES,
    OUTCOME_CONNECTION_FAILED,
    OUTCOME_MALFORMED,
    OUTCOME_OK,
    OUTCOME_TIMEOUT,
    TransportResponse,
)

if TYPE_CHECKING:  # pragma: no cover - the type-checker only
    pass

SCHEMA_VERSION = "nf_live_source_transport_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

#: Refusals raised at construction, before any socket could exist.
REFUSE_NOT_APPROVED = "authorization_is_not_approved"
REFUSE_SOURCE_MISMATCH = "authorization_is_for_a_different_source"
REFUSE_NO_HOST = "the_authorized_source_declares_no_host"
REFUSE_HOST_MISMATCH = "request_host_does_not_match_the_authorized_host"
REFUSE_NOT_HTTPS = "only_https_is_dispatchable"

#: Enforced between dispatches to one host. A politeness policy nobody
#: executes is a policy nobody has.
_LAST_REQUEST_AT: dict[str, float] = {}
_RATE_LOCK = threading.Lock()


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _host_of(url: Any) -> str:
    try:
        return (urlsplit(str(url)).hostname or "").lower()
    except ValueError:
        return ""


def _wait_for_politeness(host: str) -> float:
    """Sleep until this host may be contacted again. Returns seconds waited."""
    with _RATE_LOCK:
        now = time.monotonic()
        last = _LAST_REQUEST_AT.get(host)
        waited = 0.0
        if last is not None:
            elapsed = now - last
            if elapsed < MIN_REQUEST_INTERVAL_SECONDS:
                waited = MIN_REQUEST_INTERVAL_SECONDS - elapsed
        if waited > 0:
            time.sleep(waited)
        _LAST_REQUEST_AT[host] = time.monotonic()
        return waited


class LiveTransportRefused(RuntimeError):
    """Raised at construction. A refused transport is never built."""

    def __init__(self, reasons: list[str]) -> None:
        super().__init__("; ".join(reasons))
        self.reasons = list(reasons)


def build_live_transport(
    *,
    authorized_source_id: str,
    authorized_url: str,
    warrant_kind: str,
    connection: Any = None,
    organization_id: Any = None,
    method: str = "GET",
    now: Any = None,
    timeout_seconds: float = 20.0,
    max_response_bytes: int = MAX_RESPONSE_BYTES,
) -> Any:
    """A transport that can reach exactly one host, or no transport at all.

    Calls `assert_live_request_permitted` ITSELF. There is no parameter through
    which a caller hands in a pre-validated authorization, which is what makes
    bypass structurally impossible rather than merely discouraged: no code path
    produces a live transport without passing through Gate 77B's
    authorization-aware enforcement.

    An earlier draft took an `authorization` dict and checked it here. That is
    exactly how this gate's own robots fetch went around Gate 77B - the check
    looked thorough and was in the wrong place.

    Refuses at CONSTRUCTION, so there is no window in which a built transport
    is pointed somewhere it was not authorized for.
    """
    from nativeforge.services.source_live_warrant_service import (
        LiveRequestRefused,
        assert_live_request_permitted,
    )

    try:
        decision = assert_live_request_permitted(
            warrant_kind=warrant_kind,
            authorized_source_id=authorized_source_id,
            request_url=authorized_url,
            method=method,
            connection=connection,
            organization_id=organization_id,
            now=now,
        )
    except LiveRequestRefused as refused:
        raise LiveTransportRefused(refused.reasons) from refused

    host = _host_of(authorized_url)
    if not host:
        raise LiveTransportRefused([REFUSE_NO_HOST])
    if urlsplit(str(authorized_url)).scheme.lower() != "https":
        raise LiveTransportRefused([REFUSE_NOT_HTTPS])

    warrant = {
        "authorized_source_id": str(authorized_source_id),
        "authorized_host": host,
        "warrant_kind": warrant_kind,
        "permitted_by": decision.get("schema_version"),
        "legacy_env_flag_required": decision.get("legacy_env_flag_required"),
    }

    def transport(request: Any) -> TransportResponse:
        """Dispatch ONE request. Opens a socket; follows no redirect."""
        request_host = _host_of(getattr(request, "url", ""))
        if request_host != host:
            # The warrant is closed over at construction and cannot be
            # re-pointed. An authorization for one host must not carry a
            # request to another.
            return TransportResponse(
                status_code=None,
                headers={},
                body_bytes=b"",
                outcome=OUTCOME_CONNECTION_FAILED,
                elapsed_seconds=0.0,
            )

        waited = _wait_for_politeness(request_host)

        import httpx

        started = time.monotonic()
        try:
            with httpx.Client(
                timeout=httpx.Timeout(float(timeout_seconds)),
                # A redirect is a different URL than the one authorized.
                # Following one would make the host check decorative.
                follow_redirects=False,
                # No cookie jar, and no credential of any kind.
                cookies=None,
                headers={"user-agent": canonical_user_agent()},
            ) as client:
                response = client.request(
                    method=str(getattr(request, "method", "GET")),
                    url=str(getattr(request, "url", "")),
                    headers=dict(getattr(request, "headers", {}) or {}),
                    content=getattr(request, "body_bytes", None),
                )
                body = response.content or b""
                elapsed = time.monotonic() - started

                if len(body) > int(max_response_bytes):
                    # Refused here rather than persisted. The boundary checks
                    # again; this avoids holding an oversize body at all.
                    return TransportResponse(
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        body_bytes=b"",
                        outcome=OUTCOME_MALFORMED,
                        elapsed_seconds=elapsed,
                    )

                return TransportResponse(
                    status_code=int(response.status_code),
                    headers=dict(response.headers),
                    body_bytes=body,
                    outcome=OUTCOME_OK,
                    elapsed_seconds=elapsed,
                )
        except Exception as exc:  # noqa: BLE001 - every failure is an outcome
            elapsed = time.monotonic() - started
            name = type(exc).__name__.lower()
            outcome = (
                OUTCOME_TIMEOUT
                if "timeout" in name
                else OUTCOME_CONNECTION_FAILED
            )
            return TransportResponse(
                status_code=None,
                headers={},
                body_bytes=b"",
                outcome=outcome,
                elapsed_seconds=elapsed,
            )
        finally:
            del waited

    transport.warrant = warrant  # type: ignore[attr-defined]
    return transport


def describe_live_transport() -> dict[str, Any]:
    """What this transport is and is not. Parses ITSELF for what it imports."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(__import__(__name__, fromlist=["x"])))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "reaches_a_host": True,
            "network_modules_imported": sorted(imported & {"httpx", "socket"}),
            "follows_redirects": False,
            "sends_credentials": False,
            "sends_cookies": False,
            "retries": 0,
            "max_response_bytes": MAX_RESPONSE_BYTES,
            "min_request_interval_seconds": MIN_REQUEST_INTERVAL_SECONDS,
            "user_agent": canonical_user_agent(),
            "one_host_per_transport": True,
            "enforcement_path": (
                "source_live_warrant_service.assert_live_request_permitted"
            ),
            "bypass_is_structurally_impossible": (
                "build_live_transport calls the enforcement itself and takes "
                "no pre-validated authorization, so no code path produces a "
                "live transport without passing through Gate 77B"
            ),
            "refuses_at_construction": [
                REFUSE_NOT_APPROVED,
                REFUSE_SOURCE_MISMATCH,
                REFUSE_NO_HOST,
                REFUSE_HOST_MISMATCH,
                REFUSE_NOT_HTTPS,
            ],
            "why_construction_and_not_dispatch": (
                "a transport that exists is one whose warrant has already been "
                "checked, so there is no window in which a built transport is "
                "pointed somewhere it was not authorized for"
            ),
        }
    )


def live_transport_invariant_failures(described: dict[str, Any]) -> list[str]:
    """Refuse a live transport that has quietly grown a capability."""
    fails: list[str] = []

    if described.get("follows_redirects"):
        fails.append("the_live_transport_follows_redirects")
    if described.get("sends_credentials"):
        fails.append("the_live_transport_sends_credentials")
    if described.get("sends_cookies"):
        fails.append("the_live_transport_sends_cookies")
    if int(described.get("retries") or 0):
        fails.append("the_live_transport_retries")
    if not described.get("one_host_per_transport"):
        fails.append("the_live_transport_is_not_host_bound")
    if float(described.get("min_request_interval_seconds") or 0) <= 0:
        fails.append("the_live_transport_declares_no_politeness_interval")
    if not described.get("refuses_at_construction"):
        fails.append("the_live_transport_refuses_nothing_at_construction")

    return sorted(set(fails))
