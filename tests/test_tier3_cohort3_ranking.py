"""Tier-3 cohort-3 ranking and activatable exhaust tests."""

from __future__ import annotations

from nativeforge.services.tier3_cohort_ranking_service import (
    TA3_COHORT1_SEED_IDS,
    build_tier3_cohort3_seed_ids,
    build_tier3_cohort_ranking_report,
    rank_remaining_activatable_tier3_seeds,
)
from nativeforge.services.tier3_org_cluster_config_service import (
    TA3_COHORT2_SEED_IDS,
    TA3_COHORT3_SEED_IDS,
    TA3_COHORT_SEED_IDS,
)


def test_cohort3_size_and_disjoint() -> None:
    assert len(TA3_COHORT3_SEED_IDS) == 9
    assert len(TA3_COHORT_SEED_IDS) == 35
    all_ids = (
        set(TA3_COHORT1_SEED_IDS)
        | set(TA3_COHORT2_SEED_IDS)
        | set(TA3_COHORT3_SEED_IDS)
    )
    assert len(all_ids) == 35
    assert "nf-seed-2026-t3-053" in TA3_COHORT3_SEED_IDS
    assert "nf-seed-2026-t3-001" not in TA3_COHORT_SEED_IDS


def test_activatable_exhausted_after_cohort3() -> None:
    ranked = rank_remaining_activatable_tier3_seeds()
    assert ranked == []
    report = build_tier3_cohort_ranking_report()
    assert report["activatable_exhausted"] is True
    assert report["remaining_activatable_count"] == 0


def test_cohort3_matches_ranked_tail() -> None:
    assert build_tier3_cohort3_seed_ids() == []
