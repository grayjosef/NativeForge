"""Sprint 288: URL quality verification using real resolver + detected posture."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.source_ingestion_seed_loader_service import (
    ACCESS_LOGIN,
    ACCESS_MEMBERS,
    ACCESS_PUBLIC,
)
from nativeforge.services.source_ingestion_url_quality_service import (
    BLOCKED_POSTURES,
    SCHEMA_VERSION,
    UrlResolver,
    classify_access_posture,
)

SYNTHETIC_POSTURE_BASELINE: dict[str, int] = {
    "public": 156,
    "members": 3,
    "login": 18,
    "dead": 0,
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def verify_source_url_quality_real(
    candidate: dict[str, Any],
    *,
    resolver: UrlResolver,
) -> dict[str, Any]:
    url = str(candidate.get("source_url") or "")
    hint = str(candidate.get("access_posture_hint") or ACCESS_PUBLIC)
    resolved_payload = resolver(url)
    detected = str(
        resolved_payload.get("detected_posture") or hint
    ).strip().lower()
    if detected not in {ACCESS_PUBLIC, ACCESS_MEMBERS, ACCESS_LOGIN}:
        detected = classify_access_posture(hint=hint)
    posture = detected
    url_resolved = resolved_payload.get("resolved") is True
    blocked = posture in BLOCKED_POSTURES
    scrape_allowed = (
        posture == ACCESS_PUBLIC and url_resolved and not blocked
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "seed_id": candidate.get("seed_id"),
            "canonical_source_id": candidate.get("canonical_source_id"),
            "source_url": url,
            "access_posture_hint": hint,
            "access_posture": posture,
            "access_posture_blocked": blocked,
            "referral_required": blocked,
            "url_resolved": url_resolved,
            "url_status": (
                "dead"
                if not url_resolved
                else ("resolved" if posture == ACCESS_PUBLIC else posture)
            ),
            "resolver": resolved_payload,
            "real_resolver": True,
            "scrape_allowed_without_operator_activation": False,
            "scrape_allowed_after_activation": scrape_allowed,
            "members_or_login_never_bypassed": True,
        }
    )


def verify_seed_candidate_batch_real(
    candidates: list[dict[str, Any]],
    *,
    resolver_factory: Any,
    fetcher: Any = None,
    min_interval_seconds: float = 0.0,
) -> dict[str, Any]:
    results = []
    for cand in candidates:
        res = resolver_factory(
            cand,
            fetcher=fetcher,
            min_interval_seconds=min_interval_seconds,
        )
        results.append(verify_source_url_quality_real(cand, resolver=res))
    blocked = sum(1 for r in results if r["access_posture_blocked"])
    dead = sum(1 for r in results if not r["url_resolved"])
    posture_counts = {ACCESS_PUBLIC: 0, ACCESS_MEMBERS: 0, ACCESS_LOGIN: 0}
    for row in results:
        p = str(row.get("access_posture") or ACCESS_PUBLIC)
        if p in posture_counts:
            posture_counts[p] += 1
    return _json_safe(
        {
            "schema_version": "nf_real_url_quality_batch_v1",
            "result_count": len(results),
            "public_count": posture_counts[ACCESS_PUBLIC],
            "members_count": posture_counts[ACCESS_MEMBERS],
            "login_count": posture_counts[ACCESS_LOGIN],
            "dead_url_count": dead,
            "blocked_posture_count": blocked,
            "posture_counts": posture_counts,
            "results": results,
            "real_resolver": True,
        }
    )
