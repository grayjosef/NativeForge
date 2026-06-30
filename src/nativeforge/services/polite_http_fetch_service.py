"""TA-1: polite HTTP fetch — identifying UA, per-domain rate limit, robots.txt."""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

USER_AGENT = (
    "NativeForge/1.0 (+https://github.com/grayjosef/NativeForge; "
    "grant-discovery; respectful-crawler)"
)
DEFAULT_MIN_INTERVAL_SECONDS = 2.0
DEFAULT_TIMEOUT_SECONDS = 20.0

_per_domain_last_fetch: dict[str, float] = {}
_robots_cache: dict[str, RobotFileParser | None] = {}


def reset_polite_fetch_state() -> None:
    _per_domain_last_fetch.clear()
    _robots_cache.clear()


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def _enforce_rate_limit(domain: str, *, min_interval_seconds: float) -> None:
    now = time.monotonic()
    last = _per_domain_last_fetch.get(domain)
    if last is not None:
        elapsed = now - last
        if elapsed < min_interval_seconds:
            time.sleep(min_interval_seconds - elapsed)
    _per_domain_last_fetch[domain] = time.monotonic()


def _robots_parser(base_url: str) -> RobotFileParser | None:
    dom = _domain(base_url)
    if dom in _robots_cache:
        return _robots_cache[dom]
    robots_url = f"{urlparse(base_url).scheme}://{dom}/robots.txt"
    rp = RobotFileParser()
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            resp = client.get(robots_url, headers={"User-Agent": USER_AGENT})
        if resp.status_code >= 400:
            _robots_cache[dom] = None
            return None
        rp.parse(resp.text.splitlines())
        _robots_cache[dom] = rp
        return rp
    except Exception:
        _robots_cache[dom] = None
        return None


def robots_allows_fetch(url: str) -> bool:
    """Return True when robots.txt permits fetch or is unavailable."""
    rp = _robots_parser(url)
    if rp is None:
        return True
    return rp.can_fetch(USER_AGENT, url)


def polite_http_get(
    url: str,
    *,
    min_interval_seconds: float = DEFAULT_MIN_INTERVAL_SECONDS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    check_robots: bool = True,
) -> dict[str, Any]:
    """GET with rate limit, UA, optional robots gate."""
    dom = _domain(url)
    if check_robots and not robots_allows_fetch(url):
        return {
            "url": url,
            "status_code": None,
            "text": "",
            "fetch_live": False,
            "robots_allowed": False,
            "error": "robots_txt_disallow",
        }
    _enforce_rate_limit(dom, min_interval_seconds=min_interval_seconds)
    try:
        with httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            resp = client.get(url)
        return {
            "url": str(resp.url),
            "status_code": resp.status_code,
            "text": resp.text if resp.status_code == 200 else "",
            "fetch_live": resp.status_code == 200,
            "robots_allowed": True,
            "error": None,
        }
    except Exception as exc:
        return {
            "url": url,
            "status_code": None,
            "text": "",
            "fetch_live": False,
            "robots_allowed": True,
            "error": str(exc),
        }
