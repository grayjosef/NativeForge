"""HTTP Layer 3 smoke tests for demo vs real routes (NF-001)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app


def test_demo_only_route_403_for_real_org(monkeypatch: pytest.MonkeyPatch) -> None:
    real_org = uuid.uuid4()
    monkeypatch.setenv("NF_DEMO_ORG_IDS", "")
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    client = TestClient(create_app())
    r = client.get("/v1/isolation/demo-only", headers={"X-NF-Org-Id": str(real_org)})
    assert r.status_code == 403


def test_demo_only_route_200_for_demo_org(monkeypatch: pytest.MonkeyPatch) -> None:
    demo_org = uuid.uuid4()
    monkeypatch.setenv("NF_DEMO_ORG_IDS", str(demo_org))
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    client = TestClient(create_app())
    r = client.get("/v1/isolation/demo-only", headers={"X-NF-Org-Id": str(demo_org)})
    assert r.status_code == 200
    assert r.json()["scope"] == "demo"


def test_real_only_route_403_for_demo_org(monkeypatch: pytest.MonkeyPatch) -> None:
    demo_org = uuid.uuid4()
    monkeypatch.setenv("NF_DEMO_ORG_IDS", str(demo_org))
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    client = TestClient(create_app())
    r = client.get("/v1/isolation/real-only", headers={"X-NF-Org-Id": str(demo_org)})
    assert r.status_code == 403


def test_real_only_route_200_for_real_org(monkeypatch: pytest.MonkeyPatch) -> None:
    real_org = uuid.uuid4()
    monkeypatch.setenv("NF_DEMO_ORG_IDS", "")
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    client = TestClient(create_app())
    r = client.get("/v1/isolation/real-only", headers={"X-NF-Org-Id": str(real_org)})
    assert r.status_code == 200
    assert r.json()["scope"] == "real"


def test_headers_disabled_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    oid = uuid.uuid4()
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "false")
    get_settings.cache_clear()
    client = TestClient(create_app())
    r = client.get("/v1/isolation/demo-only", headers={"X-NF-Org-Id": str(oid)})
    assert r.status_code == 503


def test_missing_org_header_returns_400(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    client = TestClient(create_app())
    r = client.get("/v1/isolation/demo-only")
    assert r.status_code == 400


def test_invalid_org_uuid_returns_422(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    client = TestClient(create_app())
    r = client.get("/v1/isolation/demo-only", headers={"X-NF-Org-Id": "not-a-uuid"})
    assert r.status_code == 422
