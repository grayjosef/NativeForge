"""Fetch one public URL a signed-in customer named. Nothing else.

The thinnest module that can do this, on purpose. It is a network call site,
so it is on `hermetic_network_enforcement_service`'s approved list, and every
decision it acts on is made somewhere testable:

```text
customer_url_safety_service   is this destination public? (pure, no sockets)
live_network_guard_service    may this request proceed?   (pure, no sockets)
this module                   resolve, ask, read, stop
```

Security logic living inside a network client is security logic nobody can
test without a network. The address-class rules have forty-eight cases and
none of them opens a socket; that separation is what let the `is_global`
multicast hole surface in a unit test rather than in production.

## Every redirect is a new decision

A host that is public on the first request can answer `302` to
`http://169.254.169.254/`. So redirects are not followed by the client:
`follow_redirects=False`, and each hop is re-resolved and re-validated from
scratch, exactly as the original URL was. A chain that walks toward anything
non-public stops at the hop that does.

This also closes most of DNS rebinding's window. It does not close all of it:
between the lookup and the connection the record can change, and only
connecting to the validated address itself would fix that. That needs a
custom transport, is noted rather than pretended, and the exposure is one
request to one address with no credentials attached.

## Nothing of NativeForge goes out with it

No session cookie, no `Authorization`, no tenant identifier, no internal
header. The request carries the canonical user agent and nothing else, so a
customer cannot use a pasted link to make NativeForge hand its own
credentials to an address they chose.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass, field
from typing import Any

import httpx

from nativeforge.services.customer_url_safety_service import (
    MAX_REDIRECTS,
    MAX_RESPONSE_BYTES,
    REQUEST_TIMEOUT_SECONDS,
    evaluate_content_type,
    evaluate_length,
    evaluate_url,
)
from nativeforge.services.live_network_guard_service import (
    build_live_network_decision,
)
from nativeforge.services.nativeforge_user_agent_service import (
    NATIVEFORGE_USER_AGENT,
)

PURPOSE = "customer_supplied_url"
CALLER = "customer_supplied_url_fetch_service"


@dataclass(frozen=True)
class FetchResult:
    """What came back, or why nothing did."""

    fetched: bool
    url: str
    final_url: str = ""
    status_code: int | None = None
    content_type: str = ""
    body: str = ""
    bytes_read: int = 0
    #: Every URL in the chain, each one separately validated.
    hops: tuple[str, ...] = ()
    blocked_reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        # The body is deliberately absent: this is what gets logged and
        # returned to an API caller, and a fetched document does not belong
        # in an audit line.
        return {
            "fetched": self.fetched,
            "url": self.url,
            "final_url": self.final_url,
            "status_code": self.status_code,
            "content_type": self.content_type,
            "bytes_read": self.bytes_read,
            "hops": list(self.hops),
            "blocked_reasons": list(self.blocked_reasons),
        }


def resolve_addresses(host: str) -> list[str]:
    """Every address this host resolves to, or none if it does not.

    All of them, not the first. A client may connect to any address in the
    set, so validating one and connecting to another would be theatre.
    """
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError, OSError):
        return []
    return sorted({info[4][0] for info in infos})


def _permitted(
    url: str, *, robots_status: str, resolver
) -> tuple[bool, list[str], str]:
    """One hop: resolve it, classify it, then ask the guard."""
    addresses = resolver(_host_of(url))
    safety = evaluate_url(url, resolved_addresses=addresses)

    decision = build_live_network_decision(
        purpose=PURPOSE,
        target_url=url,
        caller=CALLER,
        allow_live_fetch=True,
        user_agent_status="canonical",
        rate_limit_status="policy_declared",
        robots_status=robots_status,
        # The guard never resolves anything itself; it is handed the verdict
        # the pure module reached.
        destination_status="public" if safety.allowed else "not_public",
    )

    reasons = list(safety.blocked_reasons) + list(decision["blocked_reasons"])
    allowed = safety.allowed and decision["decision_status"] == "allowed"
    return allowed, reasons, url


def _host_of(url: str) -> str:
    from urllib.parse import urlsplit

    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def fetch_customer_url(
    url: str,
    *,
    robots_status: str = "allowed",
    resolver=resolve_addresses,
    client_factory=None,
) -> FetchResult:
    """Read one public document at a URL a signed-in customer supplied.

    `resolver` and `client_factory` are injectable so the whole path can be
    exercised without a network — which is the only way the redirect rules get
    tested at all, since the interesting chains are ones no real host serves.
    """
    hops: list[str] = []
    current = (url or "").strip()

    allowed, reasons, _ = _permitted(
        current, robots_status=robots_status, resolver=resolver
    )
    if not allowed:
        return FetchResult(
            fetched=False,
            url=url,
            hops=(),
            blocked_reasons=tuple(dict.fromkeys(reasons)),
        )

    make_client = client_factory or _default_client

    with make_client() as client:
        for _ in range(MAX_REDIRECTS + 1):
            hops.append(current)
            try:
                with client.stream("GET", current) as response:
                    if response.is_redirect:
                        location = response.headers.get("location", "")
                        nxt = str(httpx.URL(current).join(location)) if location else ""
                        if not nxt:
                            return FetchResult(
                                fetched=False,
                                url=url,
                                hops=tuple(hops),
                                blocked_reasons=("redirect_without_location",),
                            )
                        # A new destination is a new decision. The host that
                        # was public a moment ago does not vouch for this one.
                        ok, why, _ = _permitted(
                            nxt, robots_status=robots_status, resolver=resolver
                        )
                        if not ok:
                            return FetchResult(
                                fetched=False,
                                url=url,
                                hops=tuple(hops),
                                blocked_reasons=tuple(
                                    [
                                        "redirect_destination_refused",
                                        *dict.fromkeys(why),
                                    ]
                                ),
                            )
                        current = nxt
                        continue

                    if response.status_code != 200:
                        return FetchResult(
                            fetched=False,
                            url=url,
                            final_url=current,
                            status_code=response.status_code,
                            hops=tuple(hops),
                            blocked_reasons=(f"http_status:{response.status_code}",),
                        )

                    type_ok, type_label = evaluate_content_type(
                        response.headers.get("content-type")
                    )
                    if not type_ok:
                        return FetchResult(
                            fetched=False,
                            url=url,
                            final_url=current,
                            status_code=response.status_code,
                            hops=tuple(hops),
                            blocked_reasons=(type_label,),
                        )

                    length_ok, length_label = evaluate_length(
                        response.headers.get("content-length")
                    )
                    if not length_ok:
                        return FetchResult(
                            fetched=False,
                            url=url,
                            final_url=current,
                            status_code=response.status_code,
                            hops=tuple(hops),
                            blocked_reasons=(length_label,),
                        )

                    # The real limit. `Content-Length` can be understated or
                    # absent, so the cap is enforced as bytes arrive and the
                    # read stops rather than the whole body being buffered.
                    chunks: list[bytes] = []
                    read = 0
                    for chunk in response.iter_bytes():
                        read += len(chunk)
                        if read > MAX_RESPONSE_BYTES:
                            return FetchResult(
                                fetched=False,
                                url=url,
                                final_url=current,
                                status_code=response.status_code,
                                bytes_read=read,
                                hops=tuple(hops),
                                blocked_reasons=("response_exceeded_size_limit",),
                            )
                        chunks.append(chunk)

                    raw = b"".join(chunks)
                    return FetchResult(
                        fetched=True,
                        url=url,
                        final_url=current,
                        status_code=response.status_code,
                        content_type=type_label,
                        body=raw.decode("utf-8", errors="replace"),
                        bytes_read=len(raw),
                        hops=tuple(hops),
                    )
            except httpx.HTTPError as exc:
                # The exception type, never its text: a connection error
                # message carries the address it tried, which is the one thing
                # a refusal must not hand back.
                return FetchResult(
                    fetched=False,
                    url=url,
                    hops=tuple(hops),
                    blocked_reasons=(f"transport_error:{type(exc).__name__}",),
                )

    return FetchResult(
        fetched=False,
        url=url,
        hops=tuple(hops),
        blocked_reasons=("too_many_redirects",),
    )


def _default_client() -> httpx.Client:
    return httpx.Client(
        # Followed by hand, one validated hop at a time.
        follow_redirects=False,
        timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS),
        headers={
            "User-Agent": NATIVEFORGE_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,text/plain,application/pdf",
        },
        # Nothing of NativeForge's goes out with a customer's link.
        cookies=None,
        trust_env=False,
    )
