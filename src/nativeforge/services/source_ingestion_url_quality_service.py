"""Sprint 259: URL quality + access posture verification for source seed candidates."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

from nativeforge.services.source_ingestion_seed_loader_service import (
    ACCESS_LOGIN,
    ACCESS_MEMBERS,
    ACCESS_PUBLIC,
)

SCHEMA_VERSION = "nf_source_ingestion_url_quality_v1"

AccessPosture = str
UrlResolver = Callable[[str], dict[str, Any]]

BLOCKED_POSTURES: frozenset[str] = frozenset({ACCESS_MEMBERS, ACCESS_LOGIN})


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _synthetic_resolver(url: str) -> dict[str, Any]:
    """Deterministic test resolver — no network."""
    parsed = urlparse(url)
    ok = parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    return {
        "url": url,
        "resolved": ok,
        "http_status": 200 if ok else 0,
        "synthetic": True,
    }


def classify_access_posture(
    *,
    hint: str,
    resolver_result: dict[str, Any] | None = None,
) -> AccessPosture:
    posture = (hint or "").strip().lower()
    if posture not in {ACCESS_PUBLIC, ACCESS_MEMBERS, ACCESS_LOGIN}:
        raise ValueError(f"unknown access posture hint: {hint!r}")
    return posture


def verify_source_url_quality(
    candidate: dict[str, Any],
    *,
    resolver: UrlResolver | None = None,
) -> dict[str, Any]:
    resolve = resolver or _synthetic_resolver
    url = str(candidate.get("source_url") or "")
    hint = str(candidate.get("access_posture_hint") or ACCESS_PUBLIC)
    posture = classify_access_posture(hint=hint)
    resolved = resolve(url)
    blocked = posture in BLOCKED_POSTURES
    scrape_allowed = (
        posture == ACCESS_PUBLIC
        and resolved.get("resolved") is True
        and not blocked
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "seed_id": candidate.get("seed_id"),
            "canonical_source_id": candidate.get("canonical_source_id"),
            "source_url": url,
            "access_posture": posture,
            "access_posture_blocked": blocked,
            "referral_required": blocked,
            "url_resolved": resolved.get("resolved") is True,
            "resolver": resolved,
            "scrape_allowed_without_operator_activation": False,
            "scrape_allowed_after_activation": scrape_allowed,
            "members_or_login_never_bypassed": blocked or posture == ACCESS_PUBLIC,
        }
    )


def verify_seed_candidate_batch(
    candidates: list[dict[str, Any]],
    *,
    resolver: UrlResolver | None = None,
) -> dict[str, Any]:
    results = [verify_source_url_quality(c, resolver=resolver) for c in candidates]
    blocked = sum(1 for r in results if r["access_posture_blocked"])
    public = sum(1 for r in results if r["access_posture"] == ACCESS_PUBLIC)
    return _json_safe(
        {
            "schema_version": "nf_source_ingestion_url_quality_batch_v1",
            "result_count": len(results),
            "public_count": public,
            "blocked_posture_count": blocked,
            "results": results,
        }
    )
