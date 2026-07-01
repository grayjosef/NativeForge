"""Tier-3 cohort-2 ranking and activation tests."""

from __future__ import annotations

from nativeforge.services.tier3_cohort_ranking_service import (
    TA3_COHORT1_SEED_IDS,
    build_tier3_cohort_ranking_report,
    rank_remaining_activatable_tier3_seeds,
)
from nativeforge.services.tier3_org_cluster_config_service import (
    TA3_COHORT2_SEED_IDS,
    TA3_COHORT_SEED_IDS,
)


def test_cohort2_size_and_disjoint_from_cohort1() -> None:
    assert len(TA3_COHORT2_SEED_IDS) == 14
    assert len(TA3_COHORT_SEED_IDS) == (
        len(TA3_COHORT1_SEED_IDS) + len(TA3_COHORT2_SEED_IDS)
    )
    assert not set(TA3_COHORT1_SEED_IDS) & set(TA3_COHORT2_SEED_IDS)


def test_cohort2_includes_priority_clusters() -> None:
    cohort2 = set(TA3_COHORT2_SEED_IDS)
    assert "nf-seed-2026-t3-020" in cohort2  # Oweesta
    assert "nf-seed-2026-t3-014" in cohort2  # AICF
    assert "nf-seed-2026-t3-018" in cohort2  # AAIA
    assert "nf-seed-2026-t3-001" not in cohort2  # NDN blocked


def test_ranking_shortlist_excludes_cohort1() -> None:
    ranked = rank_remaining_activatable_tier3_seeds()
    ids = {r["seed_id"] for r in ranked}
    assert not ids & set(TA3_COHORT1_SEED_IDS)
    assert len(ranked) >= 14


def test_ranking_report_contract() -> None:
    report = build_tier3_cohort_ranking_report()
    assert report["cohort1_size"] == 12
    assert len(report["cohort2_seed_ids"]) == 14
    assert "oweesta.org" in report["cohort2_domain_clusters"]
