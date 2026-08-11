"""Sprint 037: smoke rejects live ingestion / external URL flags."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_surfacing_demo_artifact_service import (
    build_demo_artifact,
)
from nativeforge.services.nm_wa_smoke_runner_service import (
    run_nm_wa_operator_surfacing_smoke,
)


def test_reject_live_ingestion_flag() -> None:
    a = build_demo_artifact()
    a["live_ingestion"] = True
    r = run_nm_wa_operator_surfacing_smoke(artifact=a)
    assert r["overall_status"] == "FAIL"
    assert "live_ingestion_or_source_activation" in r["failures"]
