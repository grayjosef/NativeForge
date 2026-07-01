"""Tier-3 foundation cohort ranking — native-relevance × platform-cluster leverage."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

from nativeforge.services.seed_catalog_health_service import is_seed_activatable

SCHEMA_VERSION = "nf_tier3_cohort_ranking_v1"

TA3_COHORT1_SEED_IDS: tuple[str, ...] = (
    "nf-seed-2026-t3-005",
    "nf-seed-2026-t3-006",
    "nf-seed-2026-t3-007",
    "nf-seed-2026-t3-008",
    "nf-seed-2026-t3-009",
    "nf-seed-2026-t3-010",
    "nf-seed-2026-t3-011",
    "nf-seed-2026-t3-012",
    "nf-seed-2026-t3-013",
    "nf-seed-2026-t3-034",
    "nf-seed-2026-t3-027",
    "nf-seed-2026-t3-030",
)

# Login-gated / deferred — never ranked for activation.
_EXCLUDED_BUCKETS: frozenset[str] = frozenset(
    {"blocked_login_portal", "members_gated", "dead_url", "login_gated"}
)

# Heuristic native-relevance signals in source_name (targeting research proxy).
_NATIVE_RELEVANCE_KEYWORDS: tuple[tuple[str, int], ...] = (
    ("tribal", 4),
    ("native american", 5),
    ("native ", 3),
    ("indian", 3),
    ("indigenous", 4),
    ("alaska federation", 4),
    ("native hawaiian", 4),
    ("cdf", 3),
    ("scholarship", 2),
    ("agriculture", 2),
    ("health", 2),
    ("emergency", 2),
    ("community grant", 3),
    ("legal", 2),
    ("education", 2),
)

# High-value org clusters called out in operator targeting research.
_CLUSTER_BONUS_DOMAINS: dict[str, int] = {
    "oweesta.org": 8,
    "collegefund.org": 7,
    "indian-affairs.org": 7,
    "firstnations.org": 6,
    "nativepartnership.org": 5,
    "narf.org": 5,
    "indianag.org": 5,
    "indianyouth.org": 4,
    "nativefederation.org": 4,
    "nativehealthinitiative.org": 4,
    "aises.org": 4,
    "nativeamericanbar.org": 3,
    "hawaiiancouncil.org": 5,
    "aihec.org": 4,
    "nhec.net": 4,
    "anapacific.org": 4,
    "kawerak.org": 3,
    "tocaonline.org": 3,
}


def _active_cohort_seed_ids() -> frozenset[str]:
    from nativeforge.services.tier3_org_cluster_config_service import (
        TA3_COHORT_SEED_IDS,
    )

    return frozenset(TA3_COHORT_SEED_IDS)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _domain(source_url: str) -> str:
    return urlparse(source_url).netloc.lower().replace("www.", "")


def _native_relevance_score(source_name: str) -> int:
    name_l = source_name.lower()
    score = 0
    for phrase, pts in _NATIVE_RELEVANCE_KEYWORDS:
        if phrase in name_l:
            score += pts
    return score


def score_tier3_seed_candidate(row: dict[str, Any]) -> dict[str, Any]:
    """Score one tier-3 posture row for cohort selection."""
    seed_id = str(row.get("seed_id") or "")
    source_name = str(row.get("source_name") or "")
    source_url = str(row.get("source_url") or "")
    dom = _domain(source_url)
    native_score = _native_relevance_score(source_name)
    cluster_bonus = _CLUSTER_BONUS_DOMAINS.get(dom, 0)
    activatable = is_seed_activatable(row)
    active = seed_id in _active_cohort_seed_ids()
    total = native_score + cluster_bonus
    return {
        "seed_id": seed_id,
        "source_name": source_name,
        "cluster_domain": dom,
        "native_relevance_score": native_score,
        "cluster_leverage_bonus": cluster_bonus,
        "total_score": total,
        "activatable": activatable,
        "already_in_active_cohort": active,
        "catalog_accounting_bucket": row.get("catalog_accounting_bucket"),
    }


def rank_remaining_activatable_tier3_seeds(
    posture_candidates: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Rank tier-3 seeds not yet in an active cohort; activatable only."""
    if posture_candidates is None:
        from nativeforge.services.source_ingestion_seed_loader_service import (
            load_source_seed_rows,
        )

        rows = load_source_seed_rows()
    else:
        rows = posture_candidates
    ranked: list[dict[str, Any]] = []
    for row in rows:
        if int(row.get("tier") or 0) != 3:
            continue
        bucket = str(row.get("catalog_accounting_bucket") or "")
        if bucket in _EXCLUDED_BUCKETS:
            continue
        if str(row.get("access_posture_hint") or "") != "public":
            continue
        if row.get("url_status") == "dead":
            continue
        if not is_seed_activatable(row):
            continue
        scored = score_tier3_seed_candidate(row)
        if scored["already_in_active_cohort"]:
            continue
        ranked.append(scored)
    ranked.sort(
        key=lambda r: (-r["total_score"], -r["cluster_leverage_bonus"], r["seed_id"])
    )
    return ranked


def build_tier3_cohort2_seed_ids(
    *,
    max_size: int = 14,
    posture_candidates: list[dict[str, Any]] | None = None,
) -> list[str]:
    """Select top-ranked activatable seeds for cohort-2 (default 14)."""
    ranked = rank_remaining_activatable_tier3_seeds(posture_candidates)
    return [r["seed_id"] for r in ranked[:max_size]]


def build_tier3_cohort3_seed_ids(
    *,
    posture_candidates: list[dict[str, Any]] | None = None,
) -> list[str]:
    """All remaining activatable seeds after cohort-1+2."""
    ranked = rank_remaining_activatable_tier3_seeds(posture_candidates)
    return [r["seed_id"] for r in ranked]


def _domain_clusters_for_seed_ids(
    seed_ids: tuple[str, ...] | list[str],
) -> dict[str, Any]:
    from nativeforge.services.fed_program_activation_binding_service import (
        load_seed_candidate,
    )

    by_domain: dict[str, list[str]] = {}
    for sid in seed_ids:
        src = load_seed_candidate(str(sid))
        dom = _domain(str(src.get("source_url") or ""))
        by_domain.setdefault(dom, []).append(str(sid))
    return {
        dom: {"seed_count": len(ids), "seed_ids": ids}
        for dom, ids in sorted(by_domain.items())
    }


def build_tier3_cohort_ranking_report(
    *,
    cohort2_size: int = 14,
) -> dict[str, Any]:
    ranked = rank_remaining_activatable_tier3_seeds()
    cohort2_ranked_top = [r["seed_id"] for r in ranked[:cohort2_size]]
    from nativeforge.services.tier3_org_cluster_config_service import (
        TA3_COHORT2_SEED_IDS,
        TA3_COHORT3_SEED_IDS,
        TA3_COHORT_SEED_IDS,
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "cohort1_size": len(TA3_COHORT1_SEED_IDS),
            "active_cohort_total": len(TA3_COHORT_SEED_IDS),
            "remaining_activatable_count": len(ranked),
            "cohort2_recommended_size": cohort2_size,
            "cohort2_seed_ids": list(TA3_COHORT2_SEED_IDS),
            "cohort2_ranked_top": cohort2_ranked_top,
            "cohort2_matches_ranked_top": (
                cohort2_ranked_top == list(TA3_COHORT2_SEED_IDS)
            ),
            "cohort3_seed_ids": list(TA3_COHORT3_SEED_IDS),
            "cohort3_size": len(TA3_COHORT3_SEED_IDS),
            "cohort3_domain_clusters": _domain_clusters_for_seed_ids(
                TA3_COHORT3_SEED_IDS
            ),
            "cohort2_domain_clusters": _domain_clusters_for_seed_ids(
                TA3_COHORT2_SEED_IDS
            ),
            "ranked_shortlist": ranked[:25],
            "activatable_exhausted": len(ranked) == 0,
            "excluded_deferred": {
                "blocked_login_portal": [
                    "nf-seed-2026-t3-001",
                    "nf-seed-2026-t3-002",
                    "nf-seed-2026-t3-003",
                    "nf-seed-2026-t3-004",
                    "nf-seed-2026-t3-016",
                    "nf-seed-2026-t3-017",
                ],
                "note": (
                    "NDN Collective, NACF, etc. — honest blocked_login_portal; "
                    "auth block deferred"
                ),
            },
        }
    )
