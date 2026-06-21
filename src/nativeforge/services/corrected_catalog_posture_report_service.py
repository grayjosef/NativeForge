"""Sprint 315: corrected catalog posture after URL path fixes."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.real_resolver_seed_preview_report_service import (
    build_real_resolver_seed_preview_report,
)
from nativeforge.services.real_url_resolver_service import HttpFetcher
from nativeforge.services.source_ingestion_seed_loader_service import (
    load_source_seed_rows,
)
from nativeforge.services.source_seed_url_correction_service import (
    build_seed_url_correction_report,
)

SCHEMA_VERSION = "nf_corrected_catalog_posture_report_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_corrected_catalog_posture_report(
    *,
    fetcher: HttpFetcher | None = None,
    min_interval_seconds: float = 0.0,
) -> dict[str, Any]:
    rows = load_source_seed_rows()
    preview = build_real_resolver_seed_preview_report(
        fetcher=fetcher,
        min_interval_seconds=min_interval_seconds,
    )
    corrections = build_seed_url_correction_report(rows)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "url_corrections": corrections,
            "quality_summary": preview["quality_summary"],
            "baseline_comparison": preview["baseline_comparison"],
            "candidates": preview["candidates"],
            "corrected_catalog": True,
        }
    )
