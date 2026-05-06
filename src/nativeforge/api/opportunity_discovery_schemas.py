"""Pydantic request/response bodies for Discovery Engine routes."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from nativeforge.domain.enums import (
    DiscoveryIntakeMode,
    DiscoveryRecommendedAction,
    DiscoveryReviewQueueStatus,
    ExpectedOpportunityFrequency,
    FundingInstrument,
    GrantAwardType,
    GrantPipelineStage,
    GrantSparkSource,
    OpportunitySourceType,
    OpportunityVerificationStatus,
    SourceCheckMethod,
    SourceCheckMode,
    SourceCheckRunStatus,
    SourcePriorityLevel,
    SourceReliabilityRating,
)

NF_OPERATOR_ACTIONS_LEDGER_LIST_SCHEMA_VERSION = "nf_operator_actions_ledger_list_v1"


class OpportunitySourceCreateBody(BaseModel):
    source_name: str = Field(min_length=1, max_length=512)
    source_type: OpportunitySourceType
    source_url: str | None = Field(default=None, max_length=2048)
    publisher_name: str | None = Field(default=None, max_length=512)
    description: str | None = None
    geographic_scope_json: dict | list | None = None
    native_relevance_notes: str | None = None
    reliability_rating: SourceReliabilityRating = SourceReliabilityRating.unknown
    freshness_interval_days: int | None = Field(default=None, ge=1, le=3650)
    verification_status: OpportunityVerificationStatus = (
        OpportunityVerificationStatus.unverified
    )
    is_active: bool = True
    scope_global: bool = False
    funding_domains_json: list[str] | None = None
    applicant_types_json: list | dict | None = None
    covered_states_json: list[str] | None = None
    covered_regions_json: list | None = None
    covered_tribal_groups_json: list[str] | None = None
    coverage_notes: str | None = None
    check_method: SourceCheckMethod = SourceCheckMethod.unknown
    expected_opportunity_frequency: ExpectedOpportunityFrequency = (
        ExpectedOpportunityFrequency.unknown
    )
    priority_level: SourcePriorityLevel = SourcePriorityLevel.medium


class DiscoverySparkCreateBody(BaseModel):
    source: GrantSparkSource
    source_id: str = Field(min_length=1, max_length=256)
    agency: str = Field(min_length=1, max_length=512)
    opportunity_title: str = Field(min_length=1, max_length=512)
    award_type: GrantAwardType
    opportunity_source_type: OpportunitySourceType
    sub_agency: str | None = Field(default=None, max_length=512)
    program_name: str | None = Field(default=None, max_length=512)
    opportunity_number: str | None = Field(default=None, max_length=128)
    cfda_assistance_listing: str | None = Field(default=None, max_length=64)
    url: str | None = Field(default=None, max_length=2048)
    source_url: str | None = Field(default=None, max_length=2048)
    publisher_name: str | None = Field(default=None, max_length=512)
    posted_date: date | None = None
    loi_deadline: datetime | None = None
    application_deadline: datetime | None = None
    performance_period_start: date | None = None
    performance_period_end: date | None = None
    raw_nofo_text: str | None = None
    raw_nofo_url: str | None = Field(default=None, max_length=2048)
    eligibility_tags: list[str] | None = None
    eligibility_tags_json: dict | list | None = None
    geographic_scope_json: dict | list | None = None
    applicant_types_json: list | dict | None = None
    funding_instrument: FundingInstrument | None = None
    tribal_eligible: bool = False
    pipeline_stage: GrantPipelineStage = GrantPipelineStage.new
    source_registry_id: uuid.UUID | None = None
    verification_status: OpportunityVerificationStatus | None = None
    discovered_at: datetime | None = None
    last_verified_at: datetime | None = None
    duplicate_cluster_id: uuid.UUID | None = None
    stale_after_days: int = Field(default=90, ge=1, le=3650)


class DiscoveryIntakeRunCreateBody(BaseModel):
    intake_mode: DiscoveryIntakeMode
    operator_note: str | None = Field(default=None, max_length=4096)


class StructuredCandidatesBatchBody(BaseModel):
    candidates: list[dict[str, Any]]


class ReviewItemPatchBody(BaseModel):
    review_status: DiscoveryReviewQueueStatus | None = None
    review_notes: str | None = Field(default=None, max_length=65536)
    assigned_to: str | None = Field(default=None, max_length=512)
    recommended_action: DiscoveryRecommendedAction | None = None
    priority: int | None = Field(default=None, ge=-(10**9), le=10**9)


class SourceCheckRunCreateBody(BaseModel):
    check_mode: SourceCheckMode
    operator_notes: str | None = Field(default=None, max_length=65536)
    checked_for_period_start: datetime | None = None
    checked_for_period_end: datetime | None = None


class OperatorActionCreateManualBody(BaseModel):
    decision_id: str = Field(min_length=1, max_length=256)
    action_title: str = Field(min_length=1, max_length=512)
    operator_action: str | None = None
    item_type: str = Field(min_length=1, max_length=64)
    severity: str = Field(min_length=1, max_length=32)
    action: str = Field(min_length=1, max_length=64)
    assigned_to: str | None = Field(default=None, max_length=512)
    due_at: datetime | None = None
    operator_notes: str | None = None
    action_summary: str | None = None
    source_registry_id: uuid.UUID | None = None
    review_item_id: uuid.UUID | None = None
    intake_run_id: uuid.UUID | None = None


class OperatorActionFromDecisionBody(BaseModel):
    decision_item: dict[str, Any]
    assigned_to: str | None = Field(default=None, max_length=512)
    due_at: datetime | None = None
    operator_notes: str | None = None
    force_new: bool = False


class OperatorActionLedgerPatchBody(BaseModel):
    status: str | None = Field(default=None, max_length=32)
    assigned_to: str | None = Field(default=None, max_length=512)
    due_at: datetime | None = None
    operator_notes: str | None = None
    resolution_notes: str | None = None
    resolution_code: str | None = Field(default=None, max_length=80)
    deferred_until: datetime | None = None


class SourceCheckRunPatchBody(BaseModel):
    check_status: SourceCheckRunStatus
    opportunities_seen_count: int = 0
    new_candidates_count: int = 0
    accepted_count: int = 0
    duplicate_count: int = 0
    rejected_count: int = 0
    review_items_created_count: int = 0
    error_code: str | None = Field(default=None, max_length=128)
    error_message: str | None = None
    operator_notes: str | None = Field(default=None, max_length=65536)
    result_summary: dict[str, Any] | None = None
