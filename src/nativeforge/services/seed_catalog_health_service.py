"""SH: seed catalog health buckets + activatability (177-row honest accounting)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.domain.enums import SourceHealthStatus

SCHEMA_VERSION = "nf_seed_catalog_health_v1"

BUCKET_ACTIVATABLE = "activatable"
BUCKET_BLOCKED_LOGIN_PORTAL = "blocked_login_portal"
BUCKET_DEAD_URL = "dead_url"
BUCKET_LOGIN_GATED = "login_gated"
BUCKET_MEMBERS_GATED = "members_gated"

CATALOG_BUCKETS: frozenset[str] = frozenset(
    {
        BUCKET_ACTIVATABLE,
        BUCKET_BLOCKED_LOGIN_PORTAL,
        BUCKET_DEAD_URL,
        BUCKET_LOGIN_GATED,
        BUCKET_MEMBERS_GATED,
    }
)

HEALTH_COLUMNS: frozenset[str] = frozenset(
    {
        "source_health_status",
        "resolver_url_status",
        "health_evidence",
        "catalog_accounting_bucket",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def classify_seed_health_from_posture(
    *,
    seed_id: str,
    access_posture_hint: str,
    url_status: str | None,
    access_posture_blocked: bool,
    url_resolved: bool | None = None,
) -> dict[str, str]:
    """Map resolver posture to honest CSV health fields + accounting bucket."""
    if access_posture_hint == "members":
        return {
            "source_health_status": SourceHealthStatus.attention_needed.value,
            "resolver_url_status": url_status or "members",
            "health_evidence": "access_posture_hint=members",
            "catalog_accounting_bucket": BUCKET_MEMBERS_GATED,
        }
    if access_posture_hint == "login" and not access_posture_blocked:
        return {
            "source_health_status": SourceHealthStatus.degraded.value,
            "resolver_url_status": url_status or "login",
            "health_evidence": "access_posture_hint=login",
            "catalog_accounting_bucket": BUCKET_LOGIN_GATED,
        }
    if url_status == "dead" or url_resolved is False:
        return {
            "source_health_status": SourceHealthStatus.failing.value,
            "resolver_url_status": "dead",
            "health_evidence": "resolver:url_dead_or_unresolved",
            "catalog_accounting_bucket": BUCKET_DEAD_URL,
        }
    if access_posture_blocked or url_status == "login":
        return {
            "source_health_status": SourceHealthStatus.attention_needed.value,
            "resolver_url_status": "login",
            "health_evidence": "resolver:login_portal_on_public_hint_corrected",
            "catalog_accounting_bucket": BUCKET_BLOCKED_LOGIN_PORTAL,
        }
    return {
        "source_health_status": SourceHealthStatus.healthy.value,
        "resolver_url_status": url_status or "resolved",
        "health_evidence": "resolver:activatable",
        "catalog_accounting_bucket": BUCKET_ACTIVATABLE,
    }


def corrected_access_posture_hint(
    *,
    original_hint: str,
    catalog_accounting_bucket: str,
) -> str:
    """Honest access_posture_hint after resolver triage."""
    if catalog_accounting_bucket == BUCKET_BLOCKED_LOGIN_PORTAL:
        return "login"
    return original_hint


def is_seed_activatable(candidate: dict[str, Any]) -> bool:
    bucket = str(candidate.get("catalog_accounting_bucket") or "")
    if bucket:
        return bucket == BUCKET_ACTIVATABLE
    if candidate.get("access_posture_hint") != "public":
        return False
    if candidate.get("url_status") == "dead":
        return False
    if candidate.get("access_posture_blocked"):
        return False
    health = str(candidate.get("source_health_status") or "")
    return health in {"", SourceHealthStatus.healthy.value}


def build_catalog_reconciliation_report(
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    counts: dict[str, int] = {b: 0 for b in CATALOG_BUCKETS}
    for cand in candidates:
        bucket = str(cand.get("catalog_accounting_bucket") or BUCKET_ACTIVATABLE)
        if bucket not in counts:
            bucket = BUCKET_ACTIVATABLE
        counts[bucket] += 1
    total = len(candidates)
    accounted = sum(counts.values())
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "catalog_row_count": total,
            "accounted_row_count": accounted,
            "nothing_silently_dropped": accounted == total,
            "bucket_counts": counts,
            "headline": {
                "catalog_programs": total,
                "activatable_now": counts[BUCKET_ACTIVATABLE],
                "blocked_login_portal": counts[BUCKET_BLOCKED_LOGIN_PORTAL],
                "dead_url": counts[BUCKET_DEAD_URL],
                "login_gated": counts[BUCKET_LOGIN_GATED],
                "members_gated": counts[BUCKET_MEMBERS_GATED],
            },
            "reconciliation_equation": (
                f"{total} = {counts[BUCKET_ACTIVATABLE]} activatable + "
                f"{counts[BUCKET_BLOCKED_LOGIN_PORTAL]} blocked_login_portal + "
                f"{counts[BUCKET_DEAD_URL]} dead + "
                f"{counts[BUCKET_LOGIN_GATED]} login + "
                f"{counts[BUCKET_MEMBERS_GATED]} members_gated"
            ),
        }
    )
