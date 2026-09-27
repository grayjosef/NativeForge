"""Whether a URL a customer typed is safe for this server to open.

A customer pasting a link asks NativeForge's server to make a request to an
address the customer chose. That is server-side request forgery in its
ordinary form, and the address that matters is almost never the one that
looks dangerous: it is `169.254.169.254`, or `localhost`, or a hostname whose
DNS record happens to resolve inside the deployment's own network.

## Why the decision is separated from the request

Everything here is pure. It takes a URL and, where the caller has resolved
one, a list of IP addresses, and returns a decision. It opens no socket and
performs no lookup, which is what makes the rules exhaustively testable -
every address class below has a test, and none of them needs a network.

The module that actually fetches is thin by design and is on
`hermetic_network_enforcement_service`'s approved list. Security logic that
lives inside a network client is security logic nobody can test without a
network.

## What "public" means here

`ipaddress.is_global` and an explicit list of disqualifying classes, both.

The first draft used `is_global` alone, on the reasoning that the standard
library tracks the IANA special-purpose registries and hand-written ranges go
stale. The reasoning is sound and the conclusion was wrong: `is_global` is
**True** for multicast, so `224.0.0.1` and `ff02::1` were allowed. The test
that enumerates address classes caught it on the first run.

So both. `is_global` catches the ranges nobody remembers, and the named
classes catch what `is_global` does not consider its job - each one decides,
rather than merely explaining a decision already made. An address must pass
every check, and the caller is told which class it fell into so a customer
can be given something better than "blocked".

## An IPv4-mapped IPv6 address is an IPv4 address

`::ffff:169.254.169.254` is the metadata endpoint wearing a different hat,
and `is_global` on the v6 form does not see through the mapping. It is
unwrapped before classification.

## This authorizes one request, not a crawl

A decision here says a specific URL may be fetched once because a signed-in
customer named it. It is not a source activation, it does not permit the
neighbouring pages, and it does not make the result globally publishable.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

#: The scheme. Only one: the guard's `customer_supplied_url` purpose requires
#: https before this is reached, and allowing http would mean a customer's
#: link could be read and rewritten in transit by anyone on the path.
ALLOWED_SCHEMES = frozenset({"https"})

#: Ports a public document is served from. An arbitrary port is how a URL
#: reaches an internal service that happens to speak HTTP.
ALLOWED_PORTS = frozenset({443})

#: How many hops a redirect chain may take. Long chains are how a validated
#: public host walks somebody to an internal one.
MAX_REDIRECTS = 5

#: Bytes. A funding notice is a document, not a disk image.
MAX_RESPONSE_BYTES = 12 * 1024 * 1024

#: Seconds for the whole exchange, connection included.
REQUEST_TIMEOUT_SECONDS = 20.0

#: What a public document is served as. A response outside this set is not
#: something to parse, whatever it claims.
ALLOWED_CONTENT_TYPES = frozenset(
    {
        "text/html",
        "application/xhtml+xml",
        "text/plain",
        "application/pdf",
    }
)


@dataclass(frozen=True)
class UrlDecision:
    """Whether a URL may be fetched, and why not when it may not."""

    allowed: bool
    url: str
    host: str = ""
    scheme: str = ""
    port: int | None = None
    #: Machine-readable, stable. Named so a caller can map them to copy.
    blocked_reasons: tuple[str, ...] = ()
    #: The addresses this decision was made against, when any were supplied.
    checked_addresses: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "url": self.url,
            "host": self.host,
            "scheme": self.scheme,
            "port": self.port,
            "blocked_reasons": list(self.blocked_reasons),
            "checked_addresses": list(self.checked_addresses),
        }


def classify_address(raw: str) -> tuple[bool, str]:
    """Whether one address is a public destination, and its class if not.

    Every check below decides. An earlier version treated them as labels on a
    decision `is_global` had already made, which let multicast through:
    `IPv4Address("224.0.0.1").is_global` is True, because `is_global` is
    defined against the private-use registries and multicast is not one of
    them.
    """
    try:
        address = ipaddress.ip_address(raw)
    except ValueError:
        return False, "not_an_ip_address"

    # `::ffff:127.0.0.1` is 127.0.0.1. Unwrapped before anything else, because
    # `is_global` on the wrapper does not see the address inside it.
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped

    # Ordered most specific first, so the reported class is the useful one:
    # 169.254.169.254 is link-local *and* private, and the interesting fact
    # about it is that it is the metadata endpoint.
    if address.is_loopback:
        return False, "loopback"
    if address.is_link_local:
        return False, "link_local"
    if address.is_multicast:
        return False, "multicast"
    if address.is_unspecified:
        return False, "unspecified"
    if address.is_private:
        return False, "private"
    if address.is_reserved:
        return False, "reserved"

    # Last, and still required: the ranges none of the above name.
    if not address.is_global:
        return False, "not_global"
    return True, "global"


def evaluate_url(
    url: str, *, resolved_addresses: list[str] | None = None
) -> UrlDecision:
    """Whether this URL may be fetched on a customer's behalf.

    `resolved_addresses` is what the caller's DNS lookup returned. Omitting it
    checks only the parts of the URL that can be judged without a lookup, and
    the result is **never** `allowed` - a hostname that has not been resolved
    has not been shown to be public, and treating "no addresses supplied" as
    "nothing wrong" is precisely the hole this exists to close.
    """
    reasons: list[str] = []
    text = (url or "").strip()

    if not text:
        return UrlDecision(allowed=False, url="", blocked_reasons=("url_is_empty",))

    try:
        parts = urlsplit(text)
    except ValueError:
        return UrlDecision(
            allowed=False, url=text, blocked_reasons=("url_is_unparseable",)
        )

    scheme = (parts.scheme or "").lower()
    if scheme not in ALLOWED_SCHEMES:
        reasons.append(f"scheme_not_allowed:{scheme or 'none'}")

    host = (parts.hostname or "").lower()
    if not host:
        reasons.append("url_has_no_host")

    # Credentials in a URL are a way to make one host look like another, and
    # a way to hand a secret to whatever is actually at the other end.
    if parts.username or parts.password:
        reasons.append("url_contains_credentials")

    port: int | None = None
    try:
        port = parts.port
    except ValueError:
        reasons.append("url_port_is_invalid")
    effective_port = port if port is not None else (443 if scheme == "https" else None)
    if effective_port is not None and effective_port not in ALLOWED_PORTS:
        reasons.append(f"port_not_allowed:{effective_port}")

    addresses = tuple(resolved_addresses or ())
    if not addresses:
        # Not "unknown, proceed". Unresolved means unproven.
        reasons.append("host_was_not_resolved")
    else:
        for raw in addresses:
            ok, label = classify_address(raw)
            if not ok:
                # The address is not echoed back. A refusal naming the
                # internal address it resolved to is a small map of the
                # deployment's network, handed to whoever supplied the URL.
                reasons.append(f"destination_not_public:{label}")

    return UrlDecision(
        allowed=not reasons,
        url=text,
        host=host,
        scheme=scheme,
        port=effective_port,
        blocked_reasons=tuple(dict.fromkeys(reasons)),
        checked_addresses=addresses,
    )


def evaluate_content_type(value: str | None) -> tuple[bool, str]:
    """Whether a response is a document worth parsing."""
    raw = (value or "").split(";", 1)[0].strip().lower()
    if not raw:
        return False, "content_type_missing"
    if raw not in ALLOWED_CONTENT_TYPES:
        return False, f"content_type_not_allowed:{raw}"
    return True, raw


def evaluate_length(declared: str | None) -> tuple[bool, str]:
    """Whether a declared body length is within bounds.

    Advisory only. A server can understate `Content-Length` or omit it, so the
    reader enforces the real limit as bytes arrive; this rejects the honest
    oversized response before it is transferred.
    """
    if declared is None or declared == "":
        return True, "content_length_absent"
    try:
        size = int(declared)
    except ValueError:
        return True, "content_length_unparseable"
    if size > MAX_RESPONSE_BYTES:
        return False, f"response_too_large:{size}"
    return True, "within_limit"
