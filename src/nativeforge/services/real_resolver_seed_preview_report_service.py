"""Sprint 290: real-resolver seed preview report for all 177 candidates."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from nativeforge.services.real_resolver_baseline_comparison_service import (
    build_real_vs_synthetic_baseline_comparison,
)
from nativeforge.services.real_url_quality_service import (
    verify_seed_candidate_batch_real,
)
from nativeforge.services.real_url_resolver_service import (
    HttpFetcher,
    build_real_url_resolver_for_candidate,
)
from nativeforge.services.source_ingestion_seed_loader_service import (
    build_source_seed_candidate_bundle,
)

SCHEMA_VERSION = "nf_real_resolver_seed_preview_report_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_real_resolver_seed_preview_report(
    *,
    fetcher: HttpFetcher | None = None,
    candidate_filter: Callable[[dict[str, Any]], bool] | None = None,
    min_interval_seconds: float = 0.0,
) -> dict[str, Any]:
    bundle = build_source_seed_candidate_bundle()
    candidates = bundle["candidates"]
    if candidate_filter is not None:
        candidates = [c for c in candidates if candidate_filter(c)]
    quality = verify_seed_candidate_batch_real(
        candidates,
        resolver_factory=build_real_url_resolver_for_candidate,
        fetcher=fetcher,
        min_interval_seconds=min_interval_seconds,
    )
    dead_ids = [
        str(r["seed_id"])
        for r in quality["results"]
        if not r.get("url_resolved")
    ]
    blocked = [
        {
            "seed_id": r.get("seed_id"),
            "access_posture": r.get("access_posture"),
            "reason": f"{r.get('access_posture')} — BLOCKED/referral",
        }
        for r in quality["results"]
        if r.get("access_posture_blocked")
    ]
    candidate_rows = []
    for cand, qual in zip(candidates, quality["results"], strict=True):
        candidate_rows.append(
            {
                "seed_id": cand["seed_id"],
                "canonical_source_id": cand["canonical_source_id"],
                "source_name": cand["source_name"],
                "source_url": cand["source_url"],
                "tier": cand["tier"],
                "adapter_key": cand["adapter_key"],
                "access_posture_hint": cand["access_posture_hint"],
                "access_posture": qual["access_posture"],
                "url_status": qual["url_status"],
                "access_posture_blocked": qual["access_posture_blocked"],
                "is_active": False,
            }
        )
    summary = {
        "result_count": quality["result_count"],
        "public_count": quality["public_count"],
        "members_count": quality["members_count"],
        "login_count": quality["login_count"],
        "dead_url_count": quality["dead_url_count"],
        "dead_url_seed_ids": dead_ids,
        "blocked_posture_count": quality["blocked_posture_count"],
        "blocked_referrals": blocked,
        "posture_counts": quality["posture_counts"],
    }
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "seed_row_count": bundle["seed_row_count"],
            "candidate_count": len(candidate_rows),
            "tier_counts": bundle["tier_counts"],
            "quality_summary": summary,
            "baseline_comparison": build_real_vs_synthetic_baseline_comparison(
                real_quality_summary=summary,
            ),
            "candidates": candidate_rows,
            "real_resolver": True,
            "all_candidates_inactive": True,
        }
    )
