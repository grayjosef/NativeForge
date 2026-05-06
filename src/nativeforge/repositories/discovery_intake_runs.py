"""nf_discovery_intake_runs / nf_discovery_intake_candidates — org-scoped reads."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from nativeforge.db.models import NfDiscoveryIntakeCandidate, NfDiscoveryIntakeRun
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories.scoping import (
    nf_discovery_intake_run_scope,
    select_discovery_intake_candidate_scoped,
    select_discovery_intake_candidates_for_run,
    select_discovery_intake_runs_for_org_source,
)


def get_discovery_intake_run_scoped(
    *,
    session: Session,
    run_id: uuid.UUID,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> NfDiscoveryIntakeRun | None:
    scope = nf_discovery_intake_run_scope(org_id=org_id, org_type=org_type)
    stmt = select(NfDiscoveryIntakeRun).where(NfDiscoveryIntakeRun.id == run_id, *scope)
    return session.scalar(stmt)


def list_discovery_intake_runs_for_org_source(
    *,
    session: Session,
    org_id: uuid.UUID,
    org_type: OrgType,
    source_registry_id: uuid.UUID,
) -> list[NfDiscoveryIntakeRun]:
    q = select_discovery_intake_runs_for_org_source(
        org_id=org_id,
        org_type=org_type,
        source_registry_id=source_registry_id,
    )
    return list(session.scalars(q))


def latest_discovery_intake_run_for_source(
    *,
    session: Session,
    org_id: uuid.UUID,
    org_type: OrgType,
    source_registry_id: uuid.UUID,
) -> NfDiscoveryIntakeRun | None:
    rows = list_discovery_intake_runs_for_org_source(
        session=session,
        org_id=org_id,
        org_type=org_type,
        source_registry_id=source_registry_id,
    )
    return rows[0] if rows else None


def list_discovery_intake_candidates_for_run(
    *,
    session: Session,
    org_id: uuid.UUID,
    org_type: OrgType,
    intake_run_id: uuid.UUID,
) -> list[NfDiscoveryIntakeCandidate]:
    q = select_discovery_intake_candidates_for_run(
        org_id=org_id,
        org_type=org_type,
        intake_run_id=intake_run_id,
    )
    return list(session.scalars(q))


def get_discovery_intake_candidate_scoped(
    *,
    session: Session,
    candidate_id: uuid.UUID,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> NfDiscoveryIntakeCandidate | None:
    stmt = select_discovery_intake_candidate_scoped(
        org_id=org_id,
        org_type=org_type,
        candidate_id=candidate_id,
    )
    return session.scalar(stmt)
