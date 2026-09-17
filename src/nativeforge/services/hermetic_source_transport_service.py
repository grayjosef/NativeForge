"""The hermetic transport (Gate 161F).

A transport that serves registered fixtures and cannot reach a host. It imports
no network module, opens no socket, resolves no name, and has no code path that
could — which a verifier proves by parsing this file rather than by trusting
this sentence.

## Registered, not fetched

```python
registry = HermeticTransportRegistry()
registry.register("https://example.gov/api/grants", status_code=200,
                  body_bytes=b'{"opportunities":[]}')
response = registry.transport(request)
```

A request for a URL nobody registered returns `connection_failed`, not a
network attempt. That is the correct hermetic answer: an unregistered host does
not exist in this world, and pretending otherwise would be the one behaviour
that could hide a real call.

## Failure modes are fixtures too

```text
200                a body, headers, an ETag
404                a source that has gone
429 + Retry-After  a rate limit, which Gate 157's retry policy classifies
timeout            no response at all
500 / 503          transient server failure
malformed bytes    a 200 whose body is not what any parser expects
```

Every one is registered rather than simulated by raising. A transport that
raised on timeout would make the caller's error handling the thing under test;
returning a `TransportResponse` with `outcome="timeout"` keeps the caller's
classification logic on the path where it belongs.

Malformed bytes matter especially: 161J requires that a response which cannot be
parsed is still persisted as raw evidence. A body of `b"\\x00\\xff not json"`
with status 200 is exactly that case, and it must reach Gate 160 intact.

## Deterministic

`elapsed_seconds` is whatever the fixture declares. Nothing here sleeps, so a
timeout fixture costs no wall-clock time and the verifier does not take twenty
seconds to prove a twenty-second timeout is classified transient.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.source_collection_transport_service import (
    OUTCOME_CONNECTION_FAILED,
    OUTCOME_MALFORMED,
    OUTCOME_OK,
    OUTCOME_TIMEOUT,
    TransportRequest,
    TransportResponse,
)

SCHEMA_VERSION = "nf_hermetic_source_transport_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

#: A body that is not valid UTF-8 and is not any recognisable format. Used for
#: the malformed case, and deliberately the same shape Gate 160 proved it can
#: round-trip.
MALFORMED_BODY = b"\x00\xff\xfe not json, not xml, not anything \x80\x81"


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _normalize(url: Any) -> str:
    """Exact-match keying. No DNS, no canonicalization, no resolution.

    Lowercased and stripped only, because a fixture registered for one spelling
    of a URL should answer the same spelling. Anything cleverer would be a form
    of resolution, and resolution is what this transport must not do.
    """
    return str(url or "").strip().lower()


class HermeticTransportRegistry:
    """Fixture responses, keyed by (method, url). Reaches nothing."""

    def __init__(self) -> None:
        self._fixtures: dict[tuple[str, str], dict[str, Any]] = {}
        self._calls: list[dict[str, Any]] = []

    # ---- registration --------------------------------------------------
    def register(
        self,
        url: Any,
        *,
        method: str = "GET",
        status_code: int | None = 200,
        body_bytes: bytes = b"",
        headers: dict[str, str] | None = None,
        outcome: str = OUTCOME_OK,
        elapsed_seconds: float = 0.0,
    ) -> None:
        """Teach this transport about one request it may answer."""
        self._fixtures[(str(method).upper(), _normalize(url))] = {
            "status_code": status_code,
            "body_bytes": bytes(body_bytes or b""),
            "headers": dict(headers or {}),
            "outcome": str(outcome),
            "elapsed_seconds": float(elapsed_seconds),
        }

    def register_ok(
        self, url: Any, body_bytes: bytes, *, method: str = "GET", etag: str = "v1"
    ) -> None:
        self.register(
            url,
            method=method,
            status_code=200,
            body_bytes=body_bytes,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Content-Length": str(len(body_bytes)),
                "ETag": f'W/"{etag}"',
                # Deliberately included so the caller's Gate 160 filter has
                # something to refuse. A fixture that only ever sent safe
                # headers would never exercise the allowlist.
                "Set-Cookie": "hermetic=must-be-refused",
            },
        )

    def register_not_found(self, url: Any, *, method: str = "GET") -> None:
        self.register(
            url,
            method=method,
            status_code=404,
            body_bytes=b'{"error":"not found"}',
            headers={"Content-Type": "application/json"},
        )

    def register_rate_limited(
        self, url: Any, *, method: str = "GET", retry_after: int = 120
    ) -> None:
        self.register(
            url,
            method=method,
            status_code=429,
            body_bytes=b'{"error":"rate limited"}',
            headers={
                "Content-Type": "application/json",
                "Retry-After": str(retry_after),
            },
        )

    def register_server_error(
        self, url: Any, *, method: str = "GET", status_code: int = 503
    ) -> None:
        self.register(
            url,
            method=method,
            status_code=status_code,
            body_bytes=b'{"error":"service unavailable"}',
            headers={"Content-Type": "application/json"},
        )

    def register_timeout(
        self, url: Any, *, method: str = "GET", after_seconds: float = 20.0
    ) -> None:
        """A timeout is a fixture, not a sleep. Nothing here waits."""
        self.register(
            url,
            method=method,
            status_code=None,
            body_bytes=b"",
            outcome=OUTCOME_TIMEOUT,
            elapsed_seconds=float(after_seconds),
        )

    def register_malformed(self, url: Any, *, method: str = "GET") -> None:
        """A 200 whose body no parser will accept.

        The raw bytes must still be persisted. Gate 161J: parsing success is
        not a prerequisite for preserving evidence.
        """
        self.register(
            url,
            method=method,
            status_code=200,
            body_bytes=MALFORMED_BODY,
            headers={"Content-Type": "application/json"},
            outcome=OUTCOME_MALFORMED,
        )

    # ---- dispatch -------------------------------------------------------
    def transport(self, request: TransportRequest) -> TransportResponse:
        """Answer from the fixture table, or report a connection failure."""
        key = (request.method, _normalize(request.url))
        self._calls.append(
            {
                "method": request.method,
                "url_registered": key in self._fixtures,
                "header_names": sorted(request.headers),
            }
        )

        fixture = self._fixtures.get(key)
        if fixture is None:
            # An unregistered host does not exist in this world. Returning a
            # connection failure is the honest answer; anything else could
            # hide a real call.
            return TransportResponse(
                status_code=None,
                body_bytes=b"",
                outcome=OUTCOME_CONNECTION_FAILED,
                elapsed_seconds=0.0,
            )

        return TransportResponse(
            status_code=fixture["status_code"],
            headers=fixture["headers"],
            body_bytes=fixture["body_bytes"],
            outcome=fixture["outcome"],
            elapsed_seconds=fixture["elapsed_seconds"],
        )

    # ---- what happened --------------------------------------------------
    @property
    def call_count(self) -> int:
        return len(self._calls)

    def describe(self) -> dict[str, Any]:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "scope": CONTROLLED_SCOPE,
                "registered_fixtures": len(self._fixtures),
                "registered_keys": sorted(
                    f"{method} {url}" for method, url in self._fixtures
                ),
                "calls_made": len(self._calls),
                "calls": self._calls,
                # Constants, and structurally true: see describe_hermetic_transport.
                "network_module_imported": False,
                "socket_opened": False,
                "dns_resolved": False,
                "live_source_call": False,
                "sleeps": False,
                "source_monitoring_live": False,
            }
        )


def describe_hermetic_transport() -> dict[str, Any]:
    """What this transport is, derived by parsing its own module.

    Constants would be correct today and wrong the day somebody adds an import.
    This reads the file.
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
        "asyncio",
        "time",
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

    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            rendered = _dotted(node.func)
            if rendered:
                called.add(rendered)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "network_modules_imported": sorted(imported),
            # Named to MATCH `describe_boundary`. It reported
            # `can_reach_a_host` until Gate 161's health lane asked for
            # `reaches_a_host`, got None, and passed because the key was
            # missing rather than because the answer was no.
            "reaches_a_host": bool(imported),
            "sleeps": any(
                name in called for name in ("time.sleep", "sleep", "asyncio.sleep")
            ),
            "fixture_kinds": [
                "ok_200",
                "not_found_404",
                "rate_limited_429_with_retry_after",
                "server_error_5xx",
                "timeout",
                "malformed_200_body",
            ],
            "an_unregistered_url_returns": OUTCOME_CONNECTION_FAILED,
            "why": (
                "an unregistered host does not exist in this world. Returning "
                "a connection failure is the honest answer; anything else "
                "could hide a real call."
            ),
            "malformed_bytes_still_persist": (
                "parsing success is not a prerequisite for preserving evidence"
            ),
        }
    )


def _dotted(node: Any) -> str | None:
    """Dotted path of a callee built purely from names and attributes."""
    import ast

    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else None
    return None
