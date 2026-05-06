"""Sprint 13: discovery quality scoring + review queue table."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import inspect

from nativeforge.db.models import NfDiscoveryReviewItem, NfGrantSpark, Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import (
    DiscoveryCandidateStatus,
    DiscoveryRecommendedAction,
    DiscoveryReviewItemType,
    DiscoveryReviewQueueStatus,
    FundingDomain,
    GrantAwardType,
    GrantPipelineStage,
    GrantSparkSource,
    OpportunitySourceType,
    OpportunityVerificationStatus,
    SourceReliabilityRating,
)
from nativeforge.services.discovery_quality_service import (
    QUALITY_SCHEMA_VERSION,
    DiscoveryQualityInputs,
    quality_summary_for_grant_spark,
    quality_summary_from_inputs,
)
from nativeforge.services.opportunity_discovery_service import (
    compute_duplicate_key,
    compute_structural_duplicate_fingerprint,
)


def test_structural_fingerprint_is_stable_and_distinct_from_url_based_key() -> None:
    dup_key = compute_duplicate_key(
        source_url="https://Example.gov/path/",
        publisher_name="Pub",
        opportunity_number="ABC",
        opportunity_title="Title Here",
        opportunity_source_type=OpportunitySourceType.federal,
    )
    fp = compute_structural_duplicate_fingerprint(
        agency="Agency",
        publisher_name="Pub",
        opportunity_number="ABC",
        opportunity_title="Title Here",
    )
    assert len(fp) == 64
    assert fp != dup_key


def test_quality_summary_schema_and_determinism() -> None:
    fixed_now = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
    dl = fixed_now + timedelta(days=30)
    inp = DiscoveryQualityInputs(
        reliability_rating=SourceReliabilityRating.high,
        verification_status=OpportunityVerificationStatus.trusted,
        opportunity_title="Tribal climate resilience planning grant",
        agency="Department of Example",
        opportunity_number="EX-100",
        source_id="EX-100",
        url="https://example.gov/grants/ex-100",
        source_url="https://example.gov/grants/ex-100",
        publisher_name="Office of Example",
        application_deadline=dl,
        loi_deadline=None,
        native_relevance_score=72,
        funding_domains_record={FundingDomain.climate_resilience.value},
        funding_domains_registry={
            FundingDomain.climate_resilience.value,
            FundingDomain.infrastructure.value,
        },
        applicant_types_json=["tribal_government"],
        duplicate_cluster_id=None,
        duplicate_of_spark_id=None,
        candidate_status=None,
        freshness_status=None,
    )
    a = quality_summary_from_inputs(inp, now=fixed_now)
    b = quality_summary_from_inputs(inp, now=fixed_now)
    assert a == b
    assert a["quality_schema_version"] == QUALITY_SCHEMA_VERSION
    assert set(a.keys()) >= {
        "quality_schema_version",
        "quality_score",
        "confidence_score",
        "duplicate_risk_score",
        "reason_codes",
        "recommended_action",
        "review_required",
    }
    assert isinstance(a["reason_codes"], list)
    assert a["recommended_action"] in {e.value for e in DiscoveryRecommendedAction}


def test_duplicate_signals_raise_duplicate_risk() -> None:
    now = datetime(2026, 6, 1, tzinfo=UTC)
    cluster = uuid.uuid4()
    clean = DiscoveryQualityInputs(
        reliability_rating=SourceReliabilityRating.high,
        verification_status=OpportunityVerificationStatus.trusted,
        opportunity_title="Strong opportunity title with enough length",
        agency="Agency",
        opportunity_number="X-1",
        source_id="X-1",
        url="https://example.gov/x",
        source_url=None,
        publisher_name="Publisher",
        application_deadline=now + timedelta(days=20),
        loi_deadline=None,
        native_relevance_score=80,
        funding_domains_record=set(),
        funding_domains_registry=set(),
        applicant_types_json=["nonprofit"],
        duplicate_cluster_id=None,
        duplicate_of_spark_id=None,
        candidate_status=None,
        freshness_status=None,
    )
    risky = DiscoveryQualityInputs(
        reliability_rating=SourceReliabilityRating.high,
        verification_status=OpportunityVerificationStatus.trusted,
        opportunity_title="Strong opportunity title with enough length",
        agency="Agency",
        opportunity_number="X-1",
        source_id="X-1",
        url="https://example.gov/x",
        source_url=None,
        publisher_name="Publisher",
        application_deadline=now + timedelta(days=20),
        loi_deadline=None,
        native_relevance_score=80,
        funding_domains_record=set(),
        funding_domains_registry=set(),
        applicant_types_json=["nonprofit"],
        duplicate_cluster_id=cluster,
        duplicate_of_spark_id=None,
        candidate_status=DiscoveryCandidateStatus.duplicate.value,
        freshness_status=None,
    )
    s_clean = quality_summary_from_inputs(clean, now=now)
    s_risk = quality_summary_from_inputs(risky, now=now)
    assert s_risk["duplicate_risk_score"] >= s_clean["duplicate_risk_score"]
    assert "candidate_marked_duplicate" in s_risk["reason_codes"]


def test_nf_discovery_review_items_table_exists_and_roundtrip() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        insp = inspect(s.bind)
        assert insp.has_table("nf_discovery_review_items")
        s.add(Organization(id=oid, org_type="demo"))
        s.flush()
        row = NfDiscoveryReviewItem(
            organization_id=oid,
            is_demo=True,
            review_item_type=DiscoveryReviewItemType.candidate_quality.value,
            review_status=DiscoveryReviewQueueStatus.open.value,
            priority=10,
            reason_codes_json=["missing_deadline"],
            quality_score=55,
            confidence_score=60,
            duplicate_risk_score=22,
            native_relevance_score=40,
            recommended_action=DiscoveryRecommendedAction.needs_human_review.value,
        )
        s.add(row)
        s.commit()
        rid = row.id

    with SessionLocal() as s:
        loaded = s.get(NfDiscoveryReviewItem, rid)
        assert loaded is not None
        assert (
            loaded.review_item_type == DiscoveryReviewItemType.candidate_quality.value
        )
        assert loaded.priority == 10


def test_grant_spark_quality_summary_basic_shape() -> None:
    spark = NfGrantSpark(
        organization_id=uuid.uuid4(),
        is_demo=True,
        source=GrantSparkSource.manual.value,
        source_id="manual-test",
        agency="Agency",
        opportunity_title="Native serving nonprofit capacity building opportunity",
        award_type=GrantAwardType.grant.value,
        verification_status=OpportunityVerificationStatus.operator_reviewed.value,
        opportunity_number="OPP-9",
        url="https://example.gov/opp-9",
        publisher_name="Publisher",
        application_deadline=datetime(2026, 12, 1, tzinfo=UTC),
        native_relevance_score=65,
        applicant_types_json=["native_serving_nonprofit"],
        pipeline_stage=GrantPipelineStage.new.value,
    )
    summary = quality_summary_for_grant_spark(
        spark,
        registry=None,
        now=datetime(2026, 5, 1, tzinfo=UTC),
    )
    assert summary["quality_schema_version"] == QUALITY_SCHEMA_VERSION
    assert 0 <= summary["quality_score"] <= 100
