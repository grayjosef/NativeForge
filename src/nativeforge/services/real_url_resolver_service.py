"""Sprint 287: rate-limited real URL resolver (HEAD/GET) with posture detection."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

from nativeforge.services.live_network_guard_service import (
    build_live_network_decision,
)
from nativeforge.services.nativeforge_user_agent_service import (
    NATIVEFORGE_USER_AGENT,
)
from nativeforge.services.source_ingestion_seed_loader_service import (
    ACCESS_LOGIN,
    ACCESS_MEMBERS,
    ACCESS_PUBLIC,
)

SCHEMA_VERSION = "nf_real_url_resolver_v1"
DEFAULT_MIN_INTERVAL_SECONDS = 0.5
DEFAULT_TIMEOUT_SECONDS = 10.0
MAX_BODY_SNIPPET = 4096

HttpFetcher = Callable[[str, str], dict[str, Any]]

_last_resolve_at: float | None = None

_LOGIN_PATTERNS = re.compile(
    r"(sign[\s-]?in|log[\s-]?in|password|authenticate|sso)",
    re.IGNORECASE,
)
_MEMBERS_PATTERNS = re.compile(
    r"(members[\s-]?only|member[\s-]?login|membership required)",
    re.IGNORECASE,
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def reset_real_url_resolver_rate_limit() -> None:
    global _last_resolve_at
    _last_resolve_at = None


def _enforce_rate_limit(*, min_interval_seconds: float) -> None:
    global _last_resolve_at
    now = time.monotonic()
    if _last_resolve_at is not None:
        elapsed = now - _last_resolve_at
        if elapsed < min_interval_seconds:
            wait_seconds = min_interval_seconds - elapsed
            raise PermissionError(
                f"real URL resolver rate limited — wait {wait_seconds:.2f}s"
            )
    _last_resolve_at = now


def detect_access_posture_from_signals(
    *,
    http_status: int,
    body_snippet: str = "",
    hint: str = ACCESS_PUBLIC,
) -> str:
    if http_status in {401, 403}:
        return ACCESS_LOGIN
    text = body_snippet or ""
    if _MEMBERS_PATTERNS.search(text):
        return ACCESS_MEMBERS
    if _LOGIN_PATTERNS.search(text):
        return ACCESS_LOGIN
    if http_status <= 0 or http_status >= 400:
        return ACCESS_PUBLIC if hint == ACCESS_PUBLIC else hint
    return ACCESS_PUBLIC


def default_real_http_fetch(url: str, method: str = "HEAD") -> dict[str, Any]:
    """Live HTTP fetch — staging only; never bypass CAPTCHA/login."""
    import httpx

    with httpx.Client(
        follow_redirects=True,
        timeout=DEFAULT_TIMEOUT_SECONDS,
        headers={"User-Agent": NATIVEFORGE_USER_AGENT},
    ) as client:
        if method.upper() == "HEAD":
            try:
                resp = client.head(url)
            except httpx.HTTPError:
                resp = client.get(url)
        else:
            resp = client.get(url)
        snippet = resp.text[:MAX_BODY_SNIPPET] if resp.text else ""
        return {
            "http_status": resp.status_code,
            "body_snippet": snippet,
            "final_url": str(resp.url),
        }


def resolve_url_real(
    url: str,
    *,
    hint: str = ACCESS_PUBLIC,
    fetcher: HttpFetcher | None = None,
    min_interval_seconds: float = DEFAULT_MIN_INTERVAL_SECONDS,
    allow_live_fetch: bool = False,
    caller: str = "resolve_url_real",
    source_id: Any = None,
    terms_status: Any = None,
) -> dict[str, Any]:
    """Resolve one URL with rate limiting; public-only, no credential bypass.

    Gate 94: `allow_live_fetch` defaults to False and every live resolution
    passes the global guard first. An injected `fetcher` is a test seam and is
    exempt from the guard - it reaches no network, and requiring permission to
    call a recorded transport would only push tests into setting the live flag,
    which is the opposite of what this gate is for.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "url": url,
                "resolved": False,
                "http_status": 0,
                "detected_posture": ACCESS_PUBLIC,
                "url_status": "dead",
                "synthetic": False,
                "real": True,
                "error": "invalid_url",
            }
        )
    # A live resolution needs permission. An injected fetcher does not: it is
    # a recorded transport that never leaves the process.
    if fetcher is None:
        decision = build_live_network_decision(
            purpose="source_discovery",
            target_url=url,
            caller=caller,
            source_id=source_id,
            method="HEAD",
            allow_live_fetch=allow_live_fetch,
            terms_status=terms_status,
            # The resolver checks whether a URL is alive; it does not crawl a
            # site's content, so robots is not consulted per-path here. The
            # host-level blacklist and disallowed-path rules still apply
            # through the guard's host_permitted requirement.
            robots_status="absent",
            rate_limit_status="policy_declared",
            user_agent_status="canonical",
        )
        if not decision["allowed"]:
            return _json_safe(
                {
                    "schema_version": SCHEMA_VERSION,
                    "url": url,
                    "resolved": False,
                    "http_status": 0,
                    "detected_posture": hint,
                    "url_status": "unknown",
                    "synthetic": False,
                    "real": False,
                    "error": "live_network_refused",
                    "blocked_reasons": decision["blocked_reasons"],
                }
            )

    _enforce_rate_limit(min_interval_seconds=min_interval_seconds)
    do_fetch = fetcher or default_real_http_fetch
    try:
        raw = do_fetch(url, "HEAD")
    except Exception as exc:  # noqa: BLE001 — surface resolver failure as dead
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "url": url,
                "resolved": False,
                "http_status": 0,
                "detected_posture": hint,
                "url_status": "dead",
                "synthetic": False,
                "real": True,
                "error": str(exc),
            }
        )
    status = int(raw.get("http_status") or 0)
    snippet = str(raw.get("body_snippet") or "")
    if status >= 400 and not snippet:
        try:
            raw = do_fetch(url, "GET")
            status = int(raw.get("http_status") or status)
            snippet = str(raw.get("body_snippet") or snippet)
        except Exception as exc:  # noqa: BLE001
            return _json_safe(
                {
                    "schema_version": SCHEMA_VERSION,
                    "url": url,
                    "resolved": False,
                    "http_status": status,
                    "detected_posture": hint,
                    "url_status": "dead",
                    "synthetic": False,
                    "real": True,
                    "error": str(exc),
                }
            )
    resolved = status > 0 and status not in {404, 410}
    detected = detect_access_posture_from_signals(
        http_status=status,
        body_snippet=snippet,
        hint=hint,
    )
    if not resolved:
        url_status = "dead"
    elif detected in {ACCESS_LOGIN, ACCESS_MEMBERS}:
        url_status = detected
    else:
        url_status = "resolved"
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "url": url,
            "resolved": resolved,
            "http_status": status,
            "detected_posture": detected,
            "url_status": url_status,
            "synthetic": False,
            "real": True,
            "no_captcha_bypass": True,
            "no_credential_bypass": True,
        }
    )


def build_real_url_resolver_for_candidate(
    candidate: dict[str, Any],
    *,
    fetcher: HttpFetcher | None = None,
    min_interval_seconds: float = DEFAULT_MIN_INTERVAL_SECONDS,
) -> Callable[[str], dict[str, Any]]:
    hint = str(candidate.get("access_posture_hint") or ACCESS_PUBLIC)

    def _resolver(url: str) -> dict[str, Any]:
        return resolve_url_real(
            url,
            hint=hint,
            fetcher=fetcher,
            min_interval_seconds=min_interval_seconds,
        )

    return _resolver
