"""TA-1: polite HTTP fetch — guarded, fail-closed, one user-agent.

## What Gate 94 changed and why

This module predates Gate 92's crawler governance and was written to a more
permissive standard. Gate 93's survey found it disagreed with that governance in
four ways and bypassed every guard. All five of its callers inherited that.

```text
                       before            after
guard                  none              live_network_guard_service
allow_live_fetch       n/a (always on)   False by default
min interval           2.0s              5.0s (Gate 92 floor)
user-agent             its own string    the one canonical string
robots unavailable     fetch permitted   fetch refused
blacklist              not consulted     consulted before the request
circuit breaker        none              consulted before the request
```

## Robots: three outcomes, not one

The old code collapsed "404", "500", "timeout" and "unreachable" into a single
`None` and returned `True` for all of them — a host whose robots.txt timed out
read as fully permissive, which is exactly backwards: a host under load is when
a crawler should back off.

`robots_status` now distinguishes them, because they genuinely differ:

```text
allowed       fetched, and it permits this path
disallowed    fetched, and it forbids this path
absent        404 — conventionally means no restrictions, so a crawl may proceed
fetch_failed  timeout / 5xx / connection error — we do not know, so no crawl
unknown       not checked
```

Only `allowed` and `absent` permit a fetch. Flipping all four to deny would have
been simpler and wrong: a 404 robots.txt is a real answer, and treating it as a
failure would block most of the registry for no reason.

## The seam is preserved

`polite_http_get` still takes the same arguments and returns the same shape, and
`transport` is added so a test can inject a recorded response. Nothing was
removed — the functionality is guarded, not deleted.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from nativeforge.services.live_network_guard_service import (
    LiveNetworkPermissionError,
    build_live_network_decision,
)
from nativeforge.services.nativeforge_user_agent_service import (
    NATIVEFORGE_USER_AGENT,
)
from nativeforge.services.source_crawler_governance_service import (
    CIRCUIT_BREAKER_CONSECUTIVE_FAILURES,
    MIN_REQUEST_INTERVAL_SECONDS,
)

# The one canonical string, re-exported so existing importers of USER_AGENT keep
# working while there remains exactly one definition in the codebase.
USER_AGENT = NATIVEFORGE_USER_AGENT

# Gate 92's floor. Raised from 2.0; no host in the research set publishes a
# Crawl-delay, so the floor is self-imposed and this is it.
DEFAULT_MIN_INTERVAL_SECONDS = MIN_REQUEST_INTERVAL_SECONDS
DEFAULT_TIMEOUT_SECONDS = 20.0

# Robots outcomes. Only the satisfying pair permit a fetch.
ROBOTS_ALLOWED = "allowed"
ROBOTS_DISALLOWED = "disallowed"
ROBOTS_ABSENT = "absent"
ROBOTS_FETCH_FAILED = "fetch_failed"
ROBOTS_UNKNOWN = "unknown"

ROBOTS_PERMITTING = frozenset({ROBOTS_ALLOWED, ROBOTS_ABSENT})

# Response codes that should slow a crawler down rather than be retried at pace.
BACKOFF_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
BACKOFF_INITIAL_SECONDS = 30.0
BACKOFF_MULTIPLIER = 2.0
BACKOFF_MAX_SECONDS = 900.0

_per_domain_last_fetch: dict[str, float] = {}
_robots_cache: dict[str, tuple[str, RobotFileParser | None]] = {}
_consecutive_failures: dict[str, int] = {}

# Injected transport for tests: (url, headers, timeout) -> response-like object.
Transport = Callable[..., Any]


def reset_polite_fetch_state() -> None:
    _per_domain_last_fetch.clear()
    _robots_cache.clear()
    _consecutive_failures.clear()


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def _enforce_rate_limit(domain: str, *, min_interval_seconds: float) -> None:
    # The floor is a floor: a caller may be slower, never faster.
    interval = max(float(min_interval_seconds), MIN_REQUEST_INTERVAL_SECONDS)
    now = time.monotonic()
    last = _per_domain_last_fetch.get(domain)
    if last is not None:
        elapsed = now - last
        if elapsed < interval:
            time.sleep(interval - elapsed)
    _per_domain_last_fetch[domain] = time.monotonic()


def backoff_seconds_for(consecutive_failures: int) -> float:
    """Exponential backoff for 429/5xx, capped."""
    if consecutive_failures <= 0:
        return 0.0
    delay = BACKOFF_INITIAL_SECONDS * (
        BACKOFF_MULTIPLIER ** (consecutive_failures - 1)
    )
    return min(delay, BACKOFF_MAX_SECONDS)


def _httpx_get(url: str, *, headers: dict[str, str], timeout: float) -> Any:
    """The only place this module touches the network."""
    import httpx

    with httpx.Client(
        timeout=timeout, follow_redirects=True, headers=headers
    ) as client:
        return client.get(url)


def robots_status_for(
    url: str, *, transport: Transport | None = None
) -> str:
    """Fetch and classify robots.txt. Never returns a permissive default."""
    dom = _domain(url)
    if dom in _robots_cache:
        return _robots_cache[dom][0]

    scheme = urlparse(url).scheme or "https"
    robots_url = f"{scheme}://{dom}/robots.txt"
    do_get = transport or _httpx_get

    try:
        resp = do_get(
            robots_url,
            headers={"User-Agent": NATIVEFORGE_USER_AGENT},
            timeout=10.0,
        )
    except Exception:
        # A robots.txt we could not reach is not a robots.txt that said yes.
        _robots_cache[dom] = (ROBOTS_FETCH_FAILED, None)
        return ROBOTS_FETCH_FAILED

    status = getattr(resp, "status_code", None)
    if status == 404:
        # A 404 is a real answer: conventionally, no restrictions.
        _robots_cache[dom] = (ROBOTS_ABSENT, None)
        return ROBOTS_ABSENT
    if status is None or status >= 400:
        _robots_cache[dom] = (ROBOTS_FETCH_FAILED, None)
        return ROBOTS_FETCH_FAILED

    parser = RobotFileParser()
    parser.parse((getattr(resp, "text", "") or "").splitlines())
    verdict = (
        ROBOTS_ALLOWED
        if parser.can_fetch(NATIVEFORGE_USER_AGENT, url)
        else ROBOTS_DISALLOWED
    )
    _robots_cache[dom] = (verdict, parser)
    return verdict


def robots_allows_fetch(url: str, *, transport: Transport | None = None) -> bool:
    """True only when robots.txt affirmatively permits, or is a clean 404.

    Fail-closed. Before Gate 94 this returned True whenever robots.txt could
    not be read, so a timing-out host read as permissive.
    """
    return robots_status_for(url, transport=transport) in ROBOTS_PERMITTING


def _blocked(
    url: str, *, robots_status: str, error: str, reasons: list[str] | None = None
) -> dict[str, Any]:
    return {
        "url": url,
        "status_code": None,
        "text": "",
        "fetch_live": False,
        "robots_allowed": robots_status in ROBOTS_PERMITTING,
        "robots_status": robots_status,
        "error": error,
        "blocked_reasons": reasons or [],
        "guard_decision_status": "blocked",
    }


def polite_http_get(
    url: str,
    *,
    min_interval_seconds: float = DEFAULT_MIN_INTERVAL_SECONDS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    check_robots: bool = True,
    allow_live_fetch: bool = False,
    purpose: str = "source_discovery",
    caller: str = "polite_http_get",
    source_id: Any = None,
    terms_status: Any = None,
    activation_status: Any = None,
    collector_status: Any = None,
    credential_status: Any = None,
    collector_type: Any = None,
    transport: Transport | None = None,
) -> dict[str, Any]:
    """GET through the global guard. Refuses by default.

    `allow_live_fetch` defaults to False, so every existing caller is inert
    until it is updated deliberately. That is the intended outcome: five
    callers were reaching the network with no guard at all.
    """
    dom = _domain(url)

    # Robots first, so its outcome is an input to the guard rather than a
    # separate decision made beside it.
    robots_status = ROBOTS_UNKNOWN
    if check_robots:
        if allow_live_fetch:
            robots_status = robots_status_for(url, transport=transport)
        else:
            # Do not fetch robots.txt to answer a request we will refuse.
            robots_status = ROBOTS_UNKNOWN

    decision = build_live_network_decision(
        purpose=purpose,
        target_url=url,
        caller=caller,
        source_id=source_id,
        method="GET",
        allow_live_fetch=allow_live_fetch,
        terms_status=terms_status,
        activation_status=activation_status,
        collector_status=collector_status,
        robots_status=robots_status if check_robots else ROBOTS_ABSENT,
        credential_status=credential_status,
        collector_type=collector_type,
        rate_limit_status="policy_declared",
        user_agent_status="canonical",
        consecutive_failures=_consecutive_failures.get(dom, 0),
    )

    if not decision["allowed"]:
        return _blocked(
            url,
            robots_status=robots_status,
            error=(
                "robots_txt_disallow"
                if robots_status == ROBOTS_DISALLOWED
                else "live_network_refused"
            ),
            reasons=decision["blocked_reasons"],
        )

    _enforce_rate_limit(dom, min_interval_seconds=min_interval_seconds)
    do_get = transport or _httpx_get

    try:
        resp = do_get(
            url,
            headers={"User-Agent": NATIVEFORGE_USER_AGENT},
            timeout=timeout_seconds,
        )
    except Exception as exc:
        _consecutive_failures[dom] = _consecutive_failures.get(dom, 0) + 1
        return {
            "url": url,
            "status_code": None,
            "text": "",
            "fetch_live": False,
            "robots_allowed": True,
            "robots_status": robots_status,
            "error": str(exc),
            "blocked_reasons": [],
            "guard_decision_status": decision["decision_status"],
            "consecutive_failures": _consecutive_failures[dom],
        }

    status = getattr(resp, "status_code", None)
    if status in BACKOFF_STATUS_CODES:
        _consecutive_failures[dom] = _consecutive_failures.get(dom, 0) + 1
    else:
        _consecutive_failures[dom] = 0

    return {
        "url": str(getattr(resp, "url", url)),
        "status_code": status,
        "text": (getattr(resp, "text", "") or "") if status == 200 else "",
        "fetch_live": status == 200,
        "robots_allowed": True,
        "robots_status": robots_status,
        "error": None,
        "blocked_reasons": [],
        "guard_decision_status": decision["decision_status"],
        "consecutive_failures": _consecutive_failures[dom],
        "backoff_seconds": backoff_seconds_for(_consecutive_failures[dom]),
        "circuit_breaker_threshold": CIRCUIT_BREAKER_CONSECUTIVE_FAILURES,
    }


__all__ = [
    "BACKOFF_STATUS_CODES",
    "DEFAULT_MIN_INTERVAL_SECONDS",
    "DEFAULT_TIMEOUT_SECONDS",
    "LiveNetworkPermissionError",
    "ROBOTS_ABSENT",
    "ROBOTS_ALLOWED",
    "ROBOTS_DISALLOWED",
    "ROBOTS_FETCH_FAILED",
    "ROBOTS_PERMITTING",
    "ROBOTS_UNKNOWN",
    "USER_AGENT",
    "backoff_seconds_for",
    "polite_http_get",
    "reset_polite_fetch_state",
    "robots_allows_fetch",
    "robots_status_for",
]
