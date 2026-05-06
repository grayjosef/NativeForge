"""Pure mapping helpers for the Discovery operator workbench decision pack."""

from __future__ import annotations

import uuid

from nativeforge.domain.enums import (
    CoverageRecommendationAction,
    DiscoveryReviewItemType,
    OperatorDecisionAction,
    OperatorDecisionItemType,
    OperatorDecisionSeverity,
)


def decision_id(org_id: uuid.UUID, *parts: str) -> str:
    key = "|".join(str(p) for p in (str(org_id),) + parts)
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"nativeforge/operator_decision:{key}"))


def map_coverage_action_to_operator(raw: str) -> str:
    m: dict[str, str] = {
        CoverageRecommendationAction.add_source.value: (
            OperatorDecisionAction.expand_coverage.value
        ),
        CoverageRecommendationAction.verify_source.value: (
            OperatorDecisionAction.verify.value
        ),
        CoverageRecommendationAction.increase_check_frequency.value: (
            OperatorDecisionAction.check_source.value
        ),
        CoverageRecommendationAction.review_source_quality.value: (
            OperatorDecisionAction.improve_source_quality.value
        ),
        CoverageRecommendationAction.replace_source.value: (
            OperatorDecisionAction.resolve_failure.value
        ),
        CoverageRecommendationAction.expand_domain_coverage.value: (
            OperatorDecisionAction.expand_coverage.value
        ),
        CoverageRecommendationAction.expand_geographic_coverage.value: (
            OperatorDecisionAction.expand_coverage.value
        ),
        CoverageRecommendationAction.monitor_only.value: (
            OperatorDecisionAction.monitor.value
        ),
    }
    return m.get(raw, OperatorDecisionAction.monitor.value)


def severity_from_coverage(sev: str) -> str:
    try:
        return OperatorDecisionSeverity(str(sev)).value
    except ValueError:
        return OperatorDecisionSeverity.medium.value


def review_queue_item_type(review_item_type: str) -> str:
    if review_item_type == DiscoveryReviewItemType.source_verification.value:
        return OperatorDecisionItemType.source_verification.value
    if review_item_type in (
        DiscoveryReviewItemType.candidate_quality.value,
        DiscoveryReviewItemType.duplicate_review.value,
    ):
        return OperatorDecisionItemType.quality_risk.value
    return OperatorDecisionItemType.review_item.value
