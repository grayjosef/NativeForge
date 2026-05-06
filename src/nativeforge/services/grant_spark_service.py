"""Sprint 2: Grant Spark orchestration (repository-backed)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from nativeforge.db.models import NfGrantSpark, Organization, is_demo_for_org_type
from nativeforge.domain.enums import (
    GrantAwardType,
    GrantPipelineStage,
    GrantSparkSource,
    OrganizationOrgType,
)
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories import grant_sparks as gs_repo
from nativeforge.services.grant_spark_catalog import (
    DEMO_GRANT_SPARK_CATALOG,
    demo_spark_primary_key,
)


class DuplicateGrantSparkError(Exception):
    """Unique (organization_id, source, source_id) violation."""


def spark_to_dict(row: NfGrantSpark) -> dict[str, Any]:
    def _num(v: object | None) -> float | None:
        if v is None:
            return None
        if isinstance(v, Decimal):
            return float(v)
        return float(v)  # type: ignore[arg-type]

    def _d(d: object | None) -> str | None:
        if d is None:
            return None
        if isinstance(d, datetime):
            return d.isoformat()
        if isinstance(d, date):
            return d.isoformat()
        return str(d)

    return {
        "id": str(row.id),
        "organization_id": str(row.organization_id),
        "is_demo": row.is_demo,
        "source": row.source,
        "source_id": row.source_id,
        "agency": row.agency,
        "sub_agency": row.sub_agency,
        "program_name": row.program_name,
        "opportunity_title": row.opportunity_title,
        "opportunity_number": row.opportunity_number,
        "cfda_assistance_listing": row.cfda_assistance_listing,
        "url": row.url,
        "funding_floor": _num(row.funding_floor),
        "funding_ceiling": _num(row.funding_ceiling),
        "total_program_funding": _num(row.total_program_funding),
        "expected_awards": row.expected_awards,
        "award_type": row.award_type,
        "match_required": row.match_required,
        "match_percent": _num(row.match_percent),
        "match_waiver_available": row.match_waiver_available,
        "indirect_cost_allowable": row.indirect_cost_allowable,
        "posted_date": _d(row.posted_date),
        "loi_deadline": _d(row.loi_deadline),
        "application_deadline": _d(row.application_deadline),
        "performance_period_start": _d(row.performance_period_start),
        "performance_period_end": _d(row.performance_period_end),
        "raw_nofo_text": row.raw_nofo_text,
        "raw_nofo_url": row.raw_nofo_url,
        "eligibility_tags": row.eligibility_tags,
        "tribal_eligible": row.tribal_eligible,
        "pipeline_stage": row.pipeline_stage,
        "ingested_at": _d(row.ingested_at),
        "created_at": _d(row.created_at),
        "updated_at": _d(row.updated_at),
    }


@dataclass
class GrantSparkPayload:
    source: GrantSparkSource
    source_id: str
    agency: str
    opportunity_title: str
    award_type: GrantAwardType
    sub_agency: str | None = None
    program_name: str | None = None
    opportunity_number: str | None = None
    cfda_assistance_listing: str | None = None
    url: str | None = None
    funding_floor: Decimal | None = None
    funding_ceiling: Decimal | None = None
    total_program_funding: Decimal | None = None
    expected_awards: int | None = None
    match_required: bool = False
    match_percent: Decimal | None = None
    match_waiver_available: bool = False
    indirect_cost_allowable: bool = True
    posted_date: date | None = None
    loi_deadline: datetime | None = None
    application_deadline: datetime | None = None
    performance_period_start: date | None = None
    performance_period_end: date | None = None
    raw_nofo_text: str | None = None
    raw_nofo_url: str | None = None
    eligibility_tags: list[str] | None = None
    tribal_eligible: bool = False
    pipeline_stage: GrantPipelineStage = GrantPipelineStage.new


def create_grant_spark(
    session: Session,
    *,
    org: Organization,
    body: GrantSparkPayload,
) -> NfGrantSpark:
    is_demo = is_demo_for_org_type(org.org_type)
    row = NfGrantSpark(
        organization_id=org.id,
        is_demo=is_demo,
        source=body.source.value,
        source_id=body.source_id,
        agency=body.agency,
        sub_agency=body.sub_agency,
        program_name=body.program_name,
        opportunity_title=body.opportunity_title,
        opportunity_number=body.opportunity_number,
        cfda_assistance_listing=body.cfda_assistance_listing,
        url=body.url,
        funding_floor=body.funding_floor,
        funding_ceiling=body.funding_ceiling,
        total_program_funding=body.total_program_funding,
        expected_awards=body.expected_awards,
        award_type=body.award_type.value,
        match_required=body.match_required,
        match_percent=body.match_percent,
        match_waiver_available=body.match_waiver_available,
        indirect_cost_allowable=body.indirect_cost_allowable,
        posted_date=body.posted_date,
        loi_deadline=body.loi_deadline,
        application_deadline=body.application_deadline,
        performance_period_start=body.performance_period_start,
        performance_period_end=body.performance_period_end,
        raw_nofo_text=body.raw_nofo_text,
        raw_nofo_url=body.raw_nofo_url,
        eligibility_tags=body.eligibility_tags,
        tribal_eligible=body.tribal_eligible,
        pipeline_stage=body.pipeline_stage.value,
        ingested_at=datetime.now(UTC),
    )
    session.add(row)
    try:
        session.flush()
    except IntegrityError as e:
        session.rollback()
        raise DuplicateGrantSparkError from e
    return row


def update_grant_spark(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    spark_id: uuid.UUID,
    body: GrantSparkPayload,
) -> NfGrantSpark | None:
    row = gs_repo.get_grant_spark_scoped(
        session=session,
        spark_id=spark_id,
        org_id=org_id,
        org_type=org_type,
    )
    if row is None:
        return None
    row.source = body.source.value
    row.source_id = body.source_id
    row.agency = body.agency
    row.sub_agency = body.sub_agency
    row.program_name = body.program_name
    row.opportunity_title = body.opportunity_title
    row.opportunity_number = body.opportunity_number
    row.cfda_assistance_listing = body.cfda_assistance_listing
    row.url = body.url
    row.funding_floor = body.funding_floor
    row.funding_ceiling = body.funding_ceiling
    row.total_program_funding = body.total_program_funding
    row.expected_awards = body.expected_awards
    row.award_type = body.award_type.value
    row.match_required = body.match_required
    row.match_percent = body.match_percent
    row.match_waiver_available = body.match_waiver_available
    row.indirect_cost_allowable = body.indirect_cost_allowable
    row.posted_date = body.posted_date
    row.loi_deadline = body.loi_deadline
    row.application_deadline = body.application_deadline
    row.performance_period_start = body.performance_period_start
    row.performance_period_end = body.performance_period_end
    row.raw_nofo_text = body.raw_nofo_text
    row.raw_nofo_url = body.raw_nofo_url
    row.eligibility_tags = body.eligibility_tags
    row.tribal_eligible = body.tribal_eligible
    row.pipeline_stage = body.pipeline_stage.value
    session.flush()
    return row


def list_sparks(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> list[NfGrantSpark]:
    return gs_repo.list_grant_sparks_for_org(
        session=session, org_id=org_id, org_type=org_type
    )


def get_spark(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    spark_id: uuid.UUID,
) -> NfGrantSpark | None:
    return gs_repo.get_grant_spark_scoped(
        session=session,
        spark_id=spark_id,
        org_id=org_id,
        org_type=org_type,
    )


def seed_demo_catalog(session: Session, *, org: Organization) -> dict[str, int]:
    """Insert the 12-row demo catalog for a demo org; idempotent by deterministic PK."""
    if org.org_type != OrganizationOrgType.demo.value:
        raise ValueError("seed_demo_catalog requires a demo organization")
    now = datetime.now(UTC)
    inserted = 0
    skipped = 0
    for template in DEMO_GRANT_SPARK_CATALOG:
        pk = demo_spark_primary_key(
            org.id,
            source=template["source"],
            source_id=template["source_id"],
        )
        if session.get(NfGrantSpark, pk) is not None:
            skipped += 1
            continue
        excerpt = template.get("raw_nofo_text") or (
            f"Demo excerpt for {template['opportunity_title']}."
        )
        row = NfGrantSpark(
            id=pk,
            organization_id=org.id,
            is_demo=True,
            source=template["source"],
            source_id=template["source_id"],
            agency=template["agency"],
            sub_agency=template.get("sub_agency"),
            program_name=template.get("program_name"),
            opportunity_title=template["opportunity_title"],
            opportunity_number=template.get("opportunity_number"),
            cfda_assistance_listing=template.get("cfda_assistance_listing"),
            url=template.get("url"),
            funding_floor=template.get("funding_floor"),
            funding_ceiling=template.get("funding_ceiling"),
            total_program_funding=template.get("total_program_funding"),
            expected_awards=template.get("expected_awards"),
            award_type=template["award_type"],
            match_required=template.get("match_required", False),
            match_percent=template.get("match_percent"),
            match_waiver_available=template.get("match_waiver_available", False),
            indirect_cost_allowable=template.get("indirect_cost_allowable", True),
            posted_date=template.get("posted_date"),
            loi_deadline=template.get("loi_deadline"),
            application_deadline=template.get("application_deadline"),
            performance_period_start=template.get("performance_period_start"),
            performance_period_end=template.get("performance_period_end"),
            raw_nofo_text=excerpt,
            raw_nofo_url=template.get("raw_nofo_url"),
            eligibility_tags=template.get("eligibility_tags"),
            tribal_eligible=template.get("tribal_eligible", True),
            pipeline_stage=GrantPipelineStage.new.value,
            ingested_at=now,
        )
        session.add(row)
        inserted += 1
    session.flush()
    return {"inserted": inserted, "skipped": skipped}
