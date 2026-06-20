"""Sprint 291: human-gated single seed activation."""

from __future__ import annotations

import uuid

import pytest

from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.services.seed_source_human_activation_service import (
    NF9_AUTHORIZED_SEED_ID,
    activate_single_seed_source_human_gate,
)

_DEMO_ORG = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
_CONFIRM = {
    "operator_handle": "test-operator",
    "human_activation_acknowledged": True,
    "public_only_acknowledged": True,
    "single_source_only_acknowledged": True,
}


@pytest.fixture
def demo_org() -> Organization:
    with SessionLocal() as s:
        org = s.get(Organization, _DEMO_ORG)
        if org is None:
            org = Organization(id=_DEMO_ORG, org_type="demo")
            s.add(org)
            s.commit()
        return org


def test_activate_fed001_only(demo_org: Organization) -> None:
    with SessionLocal() as s:
        org = s.get(Organization, _DEMO_ORG)
        assert org is not None
        result = activate_single_seed_source_human_gate(
            s,
            org=org,
            seed_id=NF9_AUTHORIZED_SEED_ID,
            operator_confirmation=_CONFIRM,
        )
        s.commit()
        assert result["exactly_one_active"] is True
        assert result["seed_id"] == NF9_AUTHORIZED_SEED_ID


def test_rejects_unauthorized_seed(demo_org: Organization) -> None:
    with SessionLocal() as s:
        org = s.get(Organization, _DEMO_ORG)
        assert org is not None
        with pytest.raises(PermissionError):
            activate_single_seed_source_human_gate(
                s,
                org=org,
                seed_id="nf-seed-2026-fed-002",
                operator_confirmation=_CONFIRM,
            )
