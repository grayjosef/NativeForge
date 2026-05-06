"""Sprint 1: tribal profile orchestration (repository-backed)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from nativeforge.db.models import NfTribalProfile, Organization, is_demo_for_org_type
from nativeforge.domain.enums import (
    AuditAction,
    SamRegistrationStatus,
    TribalEntityType,
)
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories import tribal_profiles as tp_repo


class DuplicateTribalProfileError(Exception):
    """organization_id already has a tribal profile row."""


def profile_to_dict(profile: NfTribalProfile) -> dict[str, Any]:
    def _d(d: object | None) -> object | None:
        if d is None:
            return None
        if isinstance(d, datetime):
            return d.isoformat()
        if isinstance(d, date):
            return d.isoformat()
        return d

    return {
        "id": str(profile.id),
        "organization_id": str(profile.organization_id),
        "is_demo": profile.is_demo,
        "legal_name": profile.legal_name,
        "entity_type": profile.entity_type,
        "uei": profile.uei,
        "ein": profile.ein,
        "sam_registration_status": profile.sam_registration_status,
        "sam_expiration_date": _d(profile.sam_expiration_date),
        "physical_address": profile.physical_address,
        "mailing_address": profile.mailing_address,
        "service_area_description": profile.service_area_description,
        "authorized_representative": profile.authorized_representative,
        "grants_manager": profile.grants_manager,
        "finance_contact": profile.finance_contact,
        "indirect_cost_rate": profile.indirect_cost_rate,
        "certifications": profile.certifications,
        "standard_narratives": profile.standard_narratives,
        "attachment_index": profile.attachment_index,
        "created_at": _d(profile.created_at),
        "updated_at": _d(profile.updated_at),
    }


@dataclass
class TribalProfilePayload:
    """Normalized body from the API (routes map Pydantic → this)."""

    legal_name: str
    entity_type: TribalEntityType
    uei: str | None = None
    ein: str | None = None
    sam_registration_status: SamRegistrationStatus = SamRegistrationStatus.unknown
    sam_expiration_date: date | None = None
    physical_address: dict | None = None
    mailing_address: dict | None = None
    service_area_description: str | None = None
    authorized_representative: dict | None = None
    grants_manager: dict | None = None
    finance_contact: dict | None = None
    indirect_cost_rate: dict | None = None
    certifications: dict | None = None
    standard_narratives: dict | None = None
    attachment_index: list | dict | None = None


def create_tribal_profile(
    session: Session,
    *,
    org: Organization,
    body: TribalProfilePayload,
    actor_id: uuid.UUID | None,
) -> NfTribalProfile:
    is_demo = is_demo_for_org_type(org.org_type)
    row = NfTribalProfile(
        organization_id=org.id,
        is_demo=is_demo,
        legal_name=body.legal_name,
        entity_type=body.entity_type.value,
        uei=body.uei,
        ein=body.ein,
        sam_registration_status=body.sam_registration_status.value,
        sam_expiration_date=body.sam_expiration_date,
        physical_address=body.physical_address,
        mailing_address=body.mailing_address,
        service_area_description=body.service_area_description,
        authorized_representative=body.authorized_representative,
        grants_manager=body.grants_manager,
        finance_contact=body.finance_contact,
        indirect_cost_rate=body.indirect_cost_rate,
        certifications=body.certifications,
        standard_narratives=body.standard_narratives,
        attachment_index=body.attachment_index,
    )
    session.add(row)
    try:
        session.flush()
    except IntegrityError as e:
        session.rollback()
        raise DuplicateTribalProfileError from e
    tp_repo.append_profile_audit(
        session=session,
        profile=row,
        action=AuditAction.profile_created,
        actor_id=actor_id,
        payload={"legal_name": body.legal_name, "entity_type": body.entity_type.value},
    )
    return row


def update_tribal_profile(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    body: TribalProfilePayload,
    actor_id: uuid.UUID | None,
) -> NfTribalProfile | None:
    row = tp_repo.get_tribal_profile_for_org(
        session=session, org_id=org_id, org_type=org_type
    )
    if row is None:
        return None
    row.legal_name = body.legal_name
    row.entity_type = body.entity_type.value
    row.uei = body.uei
    row.ein = body.ein
    row.sam_registration_status = body.sam_registration_status.value
    row.sam_expiration_date = body.sam_expiration_date
    row.physical_address = body.physical_address
    row.mailing_address = body.mailing_address
    row.service_area_description = body.service_area_description
    row.authorized_representative = body.authorized_representative
    row.grants_manager = body.grants_manager
    row.finance_contact = body.finance_contact
    row.indirect_cost_rate = body.indirect_cost_rate
    row.certifications = body.certifications
    row.standard_narratives = body.standard_narratives
    row.attachment_index = body.attachment_index
    session.flush()
    tp_repo.append_profile_audit(
        session=session,
        profile=row,
        action=AuditAction.profile_updated,
        actor_id=actor_id,
        payload={"legal_name": body.legal_name},
    )
    return row


def get_tribal_profile(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> NfTribalProfile | None:
    return tp_repo.get_tribal_profile_for_org(
        session=session, org_id=org_id, org_type=org_type
    )


def export_tribal_profile(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    actor_id: uuid.UUID | None,
) -> dict[str, Any] | None:
    row = tp_repo.get_tribal_profile_for_org(
        session=session, org_id=org_id, org_type=org_type
    )
    if row is None:
        return None
    tp_repo.append_profile_audit(
        session=session,
        profile=row,
        action=AuditAction.profile_exported,
        actor_id=actor_id,
        payload={"format": "json"},
    )
    return profile_to_dict(row)
