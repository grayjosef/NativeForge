"""Sprint 295-296: gate verification and closeout."""

from __future__ import annotations

import json
import uuid

import pytest

from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.lib.settings import get_settings
from nativeforge.services.real_resolver_validation_closeout_packet_service import (
    ARTIFACT_TYPE,
    build_real_resolver_validation_closeout_packet,
)
from nativeforge.services.real_resolver_validation_gate_verification_service import (
    verify_real_resolver_validation_gates,
)

_DEMO_ORG = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")


@pytest.fixture
def staging_gates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NF_APP_ENV", "staging")
    monkeypatch.setenv("NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED", "true")
    monkeypatch.setenv("NF_REAL_RESOLVER_VALIDATION_PLAN_APPROVED", "true")
    get_settings.cache_clear()
    with SessionLocal() as s:
        if s.get(Organization, _DEMO_ORG) is None:
            s.add(Organization(id=_DEMO_ORG, org_type="demo"))
            s.commit()


def test_gate_verification_and_closeout(staging_gates: None) -> None:
    with SessionLocal() as s:
        org = s.get(Organization, _DEMO_ORG)
        assert org is not None
        gate = verify_real_resolver_validation_gates(session=s, org=org)
        s.commit()
    assert gate["verification_passed"] is True
    packet = build_real_resolver_validation_closeout_packet(gate_verification=gate)
    assert packet["artifact_type"] == ARTIFACT_TYPE
    assert packet["fed001_seed_id"] == "nf-seed-2026-fed-001"
    json.dumps(packet)
