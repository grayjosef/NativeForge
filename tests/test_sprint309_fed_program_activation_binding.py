"""Sprint 309: fed program activation binding."""

from __future__ import annotations

import json
from pathlib import Path

from nativeforge.services.fed_program_activation_binding_service import (
    NF11_FALLBACK_SEED_ID,
    NF11_PRIMARY_SEED_ID,
    resolve_live_activation_seed,
)


def _mock_post(url: str, body: dict[str, object]) -> dict[str, object]:
    fixtures = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "source_ingestion"
    )
    if "search2" in url:
        if body.get("cfda") == "15.020":
            return {
                "errorcode": 0,
                "msg": "Webservice Succeeds",
                "data": {"oppHits": [], "hitCount": 0},
            }
        tedc = fixtures / "grants_gov_search2_bia_tedc_hit.json"
        return json.loads(tedc.read_text(encoding="utf-8"))
    return {"errorcode": 1, "msg": "unknown", "data": {}}


def test_fed001_empty_falls_back_to_tedc() -> None:
    binding = resolve_live_activation_seed(http_post=_mock_post)
    assert binding["primary_empty"] is True
    assert binding["fallback_used"] is True
    assert binding["seed_id"] == NF11_FALLBACK_SEED_ID


def test_fed001_primary_when_hits() -> None:
    def _primary_hit(url: str, body: dict[str, object]) -> dict[str, object]:
        if "search2" in url and body.get("cfda") == "15.020":
            return {
                "errorcode": 0,
                "msg": "ok",
                "data": {
                    "oppHits": [
                        {
                            "id": "99",
                            "number": "BIA-ATG-2026",
                            "title": "Aid to Tribal Governments",
                            "agencyCode": "DOI-BIA",
                            "cfdaList": ["15.020"],
                        }
                    ]
                },
            }
        return {"errorcode": 0, "msg": "ok", "data": {"oppHits": []}}

    binding = resolve_live_activation_seed(http_post=_primary_hit)
    assert binding["seed_id"] == NF11_PRIMARY_SEED_ID
    assert binding["fallback_used"] is False
