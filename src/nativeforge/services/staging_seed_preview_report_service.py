"""Sprint 274-275: full seed-preview candidate report with URL quality flags."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from nativeforge.services.source_ingestion_seed_loader_service import (
    ACCESS_LOGIN,
    ACCESS_MEMBERS,
    ACCESS_PUBLIC,
    build_source_seed_candidate_bundle,
)
from nativeforge.services.source_ingestion_url_quality_service import (
    UrlResolver,
    verify_seed_candidate_batch,
)

SCHEMA_VERSION = "nf_staging_seed_preview_report_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _url_status(resolved: bool) -> str:
    return "resolved" if resolved else "dead"


def _summarize_quality_results(
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    dead_urls: list[str] = []
    blocked_referrals: list[dict[str, Any]] = []
    posture_counts = {ACCESS_PUBLIC: 0, ACCESS_MEMBERS: 0, ACCESS_LOGIN: 0}
    for row in results:
        posture = str(row.get("access_posture") or ACCESS_PUBLIC)
        if posture in posture_counts:
            posture_counts[posture] += 1
        if not row.get("url_resolved"):
            sid = str(row.get("seed_id") or row.get("canonical_source_id") or "")
            dead_urls.append(sid)
        if row.get("access_posture_blocked"):
            blocked_referrals.append(
                {
                    "seed_id": row.get("seed_id"),
                    "canonical_source_id": row.get("canonical_source_id"),
                    "access_posture": posture,
                    "referral_required": True,
                    "reason": f"{posture} posture — BLOCKED/referral only",
                }
            )
    return {
        "dead_url_count": len(dead_urls),
        "dead_url_seed_ids": dead_urls,
        "blocked_posture_count": len(blocked_referrals),
        "blocked_referrals": blocked_referrals,
        "posture_counts": posture_counts,
    }


def build_staging_seed_preview_report(
    *,
    resolver: UrlResolver | None = None,
    candidate_filter: Callable[[dict[str, Any]], bool] | None = None,
) -> dict[str, Any]:
    """Report all 177 seed candidates with URL-quality + access-posture results."""
    bundle = build_source_seed_candidate_bundle()
    candidates = bundle["candidates"]
    if candidate_filter is not None:
        candidates = [c for c in candidates if candidate_filter(c)]
    quality = verify_seed_candidate_batch(candidates, resolver=resolver)
    results = quality["results"]
    summary = _summarize_quality_results(results)
    candidate_rows = []
    for cand, qual in zip(candidates, results, strict=True):
        candidate_rows.append(
            {
                "seed_id": cand["seed_id"],
                "canonical_source_id": cand["canonical_source_id"],
                "source_name": cand["source_name"],
                "source_url": cand["source_url"],
                "tier": cand["tier"],
                "adapter_key": cand["adapter_key"],
                "access_posture_hint": cand["access_posture_hint"],
                "url_status": _url_status(bool(qual.get("url_resolved"))),
                "access_posture": qual["access_posture"],
                "access_posture_blocked": qual["access_posture_blocked"],
                "referral_required": qual["referral_required"],
                "is_active": False,
                "human_activation_required": True,
            }
        )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "seed_row_count": bundle["seed_row_count"],
            "candidate_count": len(candidate_rows),
            "tier_counts": bundle["tier_counts"],
            "quality_summary": {
                "result_count": quality["result_count"],
                "public_count": quality["public_count"],
                "blocked_posture_count": quality["blocked_posture_count"],
                **summary,
            },
            "candidates": candidate_rows,
            "all_candidates_inactive": True,
            "no_activation_performed": True,
        }
    )
