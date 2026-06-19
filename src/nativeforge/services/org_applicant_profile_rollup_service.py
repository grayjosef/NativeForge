"""Sprint 209: org/applicant profile rollup across demo corpus."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from nativeforge.services.org_applicant_profile_demo_fixture_service import (
    load_org_applicant_profile_fixtures,
)
from nativeforge.services.org_applicant_profile_hardened_record_service import (
    build_hardened_org_applicant_profile_record,
)

SCHEMA_VERSION = "nf_org_applicant_profile_rollup_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_org_applicant_profile_rollup(
    fixtures: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rows = fixtures if fixtures is not None else load_org_applicant_profile_fixtures()
    records = [build_hardened_org_applicant_profile_record(raw) for raw in rows]
    status_counts = Counter(r["review_status"] for r in records)
    review_count = sum(1 for r in records if r["human_review_required"])
    discoverable_count = sum(1 for r in records if r["discoverable"])
    invention_blocked = sum(
        1
        for r in records
        for fp in r["profile_record"]["field_provenance"]
        if r["profile_record"]["profile_fields"].get(fp["field_name"]) == "UNKNOWN"
    )
    verification_blocked = sum(
        1 for r in records if r["evaluation"]["verified_by_user_guard"]["verification_blocked"]
    )
    mutation_blocked = sum(
        1
        for r in records
        if r["evaluation"]["mutation_guard"]["mutation_requested"]
        and not r["evaluation"]["mutation_guard"]["mutation_applied"]
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "record_count": len(records),
            "review_status_counts": dict(status_counts),
            "human_review_count": review_count,
            "discoverable_count": discoverable_count,
            "verification_blocked_count": verification_blocked,
            "mutation_blocked_count": mutation_blocked,
            "unknown_field_rollup_count": invention_blocked,
            "preview_only": True,
        }
    )
