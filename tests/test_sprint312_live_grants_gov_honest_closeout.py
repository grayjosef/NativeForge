"""Sprint 312: NF-11 closeout and gate verification."""

from __future__ import annotations

import json
import uuid

import pytest

from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.lib.settings import get_settings
from nativeforge.services.live_grants_gov_honest_closeout_packet_service import (
    ARTIFACT_TYPE,
    build_live_grants_gov_honest_closeout_packet,
)
from nativeforge.services.live_grants_gov_honest_gate_verification_service import (
    verify_live_grants_gov_honest_gates,
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


def test_nf11_gate_and_closeout(staging_gates: None) -> None:
    with SessionLocal() as s:
        org = s.get(Organization, _DEMO_ORG)
        assert org is not None
        gate = verify_live_grants_gov_honest_gates(session=s, org=org)
        s.commit()
    assert gate["verification_passed"] is True
    packet = build_live_grants_gov_honest_closeout_packet(gate_verification=gate)
    assert packet["artifact_type"] == ARTIFACT_TYPE
    assert packet["honest_labeling"] is True
    assert packet["fixture"] is True
    assert packet["real_fetch"] is False
    json.dumps(packet)
