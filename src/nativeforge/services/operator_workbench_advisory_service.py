"""Sprint 228+: read-only operator workbench advisory bundle (synthetic fixtures only).

PRESENTATIONAL wiring — delegates to existing Stage 5–10 services without changing
scoring, relevance, matching logic, or human gates.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from nativeforge.services.eligibility_fit_assessment_demo_fixture_service import (
    load_applicant_profile_fixtures,
    load_opportunity_fixtures,
)
from nativeforge.services.funding_opportunity_intake_demo_fixture_service import (
    load_demo_fixture_corpus,
)
from nativeforge.services.matching_readiness_demo_fixture_service import (
    load_matching_readiness_demo_pairs,
    resolve_demo_pair,
)
from nativeforge.services.matching_readiness_record_service import (
    build_matching_readiness_record,
)
from nativeforge.services.native_relevance_classification_demo_fixture_service import (
    load_demo_classification_fixtures,
)
from nativeforge.services.native_relevance_classification_record_service import (
    build_native_relevance_classification_record,
)
from nativeforge.services.org_applicant_profile_demo_fixture_service import (
    load_org_applicant_profile_fixtures,
)
from nativeforge.services.org_applicant_profile_hardened_record_service import (
    build_hardened_org_applicant_profile_record,
)

SCHEMA_VERSION = "nf_operator_workbench_advisory_bundle_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_native_relevance_advisory_preview(limit: int = 6) -> dict[str, Any]:
    fixtures = load_demo_classification_fixtures()[:limit]
    previews = [build_native_relevance_classification_record(f) for f in fixtures]
    return _json_safe(
        {
            "schema_version": "nf_operator_workbench_native_relevance_preview_v1",
            "preview_count": len(previews),
            "previews": previews,
            "advisory_only": True,
            "synthetic_fixtures_only": True,
        }
    )


def build_org_applicant_profile_advisory_preview(limit: int = 5) -> dict[str, Any]:
    fixtures = load_org_applicant_profile_fixtures()[:limit]
    previews = [build_hardened_org_applicant_profile_record(f) for f in fixtures]
    return _json_safe(
        {
            "schema_version": "nf_operator_workbench_org_applicant_profile_preview_v1",
            "preview_count": len(previews),
            "previews": previews,
            "advisory_only": True,
            "synthetic_fixtures_only": True,
        }
    )


def build_matching_readiness_advisory_preview(limit: int = 6) -> dict[str, Any]:
    pairs = load_matching_readiness_demo_pairs()[:limit]
    records = []
    for pair in pairs:
        opp, profile = resolve_demo_pair(pair)
        records.append(build_matching_readiness_record(opp, profile, pair_meta=pair))
    return _json_safe(
        {
            "schema_version": "nf_operator_workbench_matching_readiness_preview_v1",
            "preview_count": len(records),
            "records": records,
            "advisory_only": True,
            "synthetic_fixtures_only": True,
            "canonical_fit_layer": "eligibility_fit_assessment_*",
        }
    )


def build_real_grant_workbench_advisory_preview() -> dict[str, Any]:
    from nativeforge.services.real_grant_workbench_queue_service import (
        build_real_grant_workbench_queues,
    )

    queues = build_real_grant_workbench_queues()
    return _json_safe(
        {
            "schema_version": "nf_operator_workbench_real_grant_queues_preview_v1",
            "queues": queues,
            "from_real_source_text": True,
            "honest_labeling": True,
            "synthetic_fixtures_only": False,
            "workbench_reviewable": True,
        }
    )


def build_intake_advisory_preview(limit: int = 4) -> dict[str, Any]:
    from nativeforge.services.funding_opportunity_intake_hardened_record_service import (  # noqa: E501
        build_hardened_opportunity_record,
    )

    fixtures = load_demo_fixture_corpus()[:limit]
    previews = [
        build_hardened_opportunity_record(
            raw,
            fixture_key=str(raw.get("fixture_key") or f"idx_{i}"),
            batch_candidates=fixtures,
        )
        for i, raw in enumerate(fixtures)
    ]
    return _json_safe(
        {
            "schema_version": "nf_operator_workbench_intake_preview_v1",
            "preview_count": len(previews),
            "previews": previews,
            "advisory_only": True,
            "synthetic_fixtures_only": True,
        }
    )


def build_operator_workbench_advisory_bundle(
    *,
    org_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Full Stage 11 advisory bundle for operator workbench UX."""
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "org_id": str(org_id) if org_id else None,
            "preview_only": True,
            "no_live_ingestion": True,
            "synthetic_fixtures_only": True,
            "no_scoring_logic_changes": True,
            "canonical_layers": {
                "stage5": "funding_opportunity_intake_*",
                "stage6": "native_relevance_classification_*",
                "stage7_org_profile": "org_applicant_profile_*",
                "stage7_fit": "eligibility_fit_assessment_*",
                "stages8_10": "matching_readiness_*",
            },
            "intake_preview": build_intake_advisory_preview(),
            "native_relevance_preview": build_native_relevance_advisory_preview(),
            "org_applicant_profile_preview": (
                build_org_applicant_profile_advisory_preview()
            ),
            "matching_readiness_preview": build_matching_readiness_advisory_preview(),
            "fixture_counts": {
                "opportunity_fixtures": len(load_opportunity_fixtures()),
                "profile_fixtures": len(load_applicant_profile_fixtures()),
                "matching_pairs": len(load_matching_readiness_demo_pairs()),
            },
        }
    )
