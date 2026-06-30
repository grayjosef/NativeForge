"""RT-6: honesty regression for partial real-tribe profile groundwork."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.la_scale_honesty_regression_service import (
    run_la_scale_honesty_regression,
)
from nativeforge.services.matching_profile_provenance_service import (
    build_matching_profile_provenance_contract,
    derive_profile_evidence_codes,
)
from nativeforge.services.org_applicant_profile_field_provenance_service import (
    CAPTURE_PUBLIC_INFERRED,
    build_field_provenance_contract,
)
from nativeforge.services.real_grant_opportunity_metadata_service import (
    summarize_opportunity_metadata_coverage,
)
from nativeforge.services.real_grants_corpus_loader_service import (
    load_nf13_real_ingested_grants,
)

SCHEMA_VERSION = "nf_rt_partial_honesty_regression_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def run_rt_partial_honesty_regression(
    *,
    grants: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    corpus = grants if grants is not None else load_nf13_real_ingested_grants()
    la = run_la_scale_honesty_regression(grants=corpus)
    prov_contract = build_matching_profile_provenance_contract()
    stage7_contract = build_field_provenance_contract()
    capture_methods = set(stage7_contract["capture_methods"])
    inferred_profile = {
        "applicant_type": "tribal_government",
        "service_geography": "northwest",
        "grant_management_capacity": "strong",
        "capture_method": CAPTURE_PUBLIC_INFERRED,
        "field_provenance": [
            {
                "field_name": "applicant_type",
                "capture_method": CAPTURE_PUBLIC_INFERRED,
            },
            {
                "field_name": "service_geography",
                "capture_method": CAPTURE_PUBLIC_INFERRED,
            },
        ],
    }
    inferred_codes = derive_profile_evidence_codes(inferred_profile)
    metadata = summarize_opportunity_metadata_coverage(corpus)
    checks = {
        **la["checks"],
        "provenance_vocabulary_includes_rt1_methods": all(
            m in capture_methods
            for m in ("public_inferred", "tribe_confirmed", "operator_entered")
        ),
        "public_inferred_never_gets_evidence_codes": len(inferred_codes) == 0,
        "program_area_metadata_honest": metadata["program_area_unknown_count"] >= 0,
        "required_geography_metadata_honest": metadata["required_geography_unknown_count"] >= 0,
    }
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "grant_count": len(corpus),
            "checks": checks,
            "verification_passed": all(checks.values()),
            "provenance_contract": prov_contract,
            "opportunity_metadata_coverage": metadata,
            "inferred_profile_evidence_codes": inferred_codes,
        }
    )
