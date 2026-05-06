"""HTTP Layer 3: DB-backed org type + Sprint 0 nf routes."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app


def test_demo_route_403_for_real_org_in_db(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_id = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=real_id, org_type="real"))
        s.commit()

    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    client = TestClient(create_app())
    r = client.post(
        f"/v1/nf/demo/orgs/{real_id}/review-artifacts",
        headers={"X-NF-Org-Id": str(real_id)},
    )
    assert r.status_code == 403
