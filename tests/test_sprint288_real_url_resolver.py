"""Sprint 287-288: real URL resolver and quality verification."""

from __future__ import annotations

from nativeforge.services.real_url_quality_service import (
    SYNTHETIC_POSTURE_BASELINE,
    verify_source_url_quality_real,
)
from nativeforge.services.real_url_resolver_service import (
    detect_access_posture_from_signals,
    reset_real_url_resolver_rate_limit,
    resolve_url_real,
)
from nativeforge.services.source_ingestion_seed_loader_service import (
    load_source_seed_rows,
    seed_row_to_discovery_candidate,
)


def _mock_fetch(url: str, method: str) -> dict[str, object]:
    if "invalid" in url:
        return {"http_status": 404, "body_snippet": "", "final_url": url}
    if "login" in url:
        return {
            "http_status": 200,
            "body_snippet": "sign in required",
            "final_url": url,
        }
    return {"http_status": 200, "body_snippet": "public grants", "final_url": url}


def test_detect_login_posture() -> None:
    posture = detect_access_posture_from_signals(http_status=401, body_snippet="")
    assert posture == "login"


def test_resolve_url_real_dead() -> None:
    reset_real_url_resolver_rate_limit()
    result = resolve_url_real(
        "https://invalid.example.com/dead",
        fetcher=_mock_fetch,
        min_interval_seconds=0,
    )
    assert result["url_status"] == "dead"
    assert result["real"] is True


def test_verify_real_quality_uses_detected_posture() -> None:
    row = seed_row_to_discovery_candidate(load_source_seed_rows()[0])

    def resolver(url: str) -> dict[str, object]:
        return resolve_url_real(
            url,
            hint=row["access_posture_hint"],
            fetcher=_mock_fetch,
            min_interval_seconds=0,
        )

    qual = verify_source_url_quality_real(row, resolver=resolver)
    assert qual["real_resolver"] is True
    assert SYNTHETIC_POSTURE_BASELINE["public"] == 156
