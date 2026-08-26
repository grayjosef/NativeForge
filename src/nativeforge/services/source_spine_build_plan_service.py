"""Phase 1 source spine build plan (Gate 92D).

Declares the five sources the collector layer is built on, in order, **without
activating any of them.**

## Build order is not priority tier

The v2 registry's ``priority_tier`` is a backlog priority across 381 rows. It is
not a build order, and building 381 collectors is not the plan. These five come
first because nothing else works without them.

## The constraints here are legal and operational, not preferences

Each one exists because the research found a case that breaks the naive model,
and several are the difference between a bug and a legal problem:

* **Grants.gov daily XML extract is the corpus of record**, and it is retained
  for **7 days only**. A failed fetch is a paging-level alert, not a retry - a
  missed day is unrecoverable. It is the only source carrying Estimated Synopsis
  Post Date, Fiscal Year, Archive Date, the 18,000-char description and the
  4,000-char eligibility text.
* **Search2 is a delta accelerator, never the corpus of record.** It gives
  hourly deltas and ``synopsisModifiedFields[]`` - a literal list of what the
  agency changed - which nothing else in the federal ecosystem provides.
* **Grants.gov attribution is a build requirement.** The exact sentence must
  appear on any UI surface using the API.
* **SAM.gov prohibits scraping outright** and the rate limit is the binding
  constraint: 10 requests/day without a SAM role, 1,000/day with one.
* **USAspending is prior-award intelligence, not current-deadline discovery.**

## Nothing here collects

Every entry carries ``collector_status: not_built`` and at least one
activation blocker. This is a plan, and a plan that could run is a collector.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_source_spine_build_plan_v1"

# Verbatim. This string is a build requirement on any UI surface using the
# Grants.gov API, and an invariant checks it character for character.
GRANTS_GOV_ATTRIBUTION = (
    "This product uses the Grants.gov API but is not endorsed or certified by "
    "the U.S. Department of Health and Human Services."
)

SOURCE_ROLES = frozenset(
    {
        "corpus_of_record",
        "delta_accelerator",
        "notice_feed",
        "program_catalog",
        "prior_award_intelligence",
    }
)

COLLECTION_METHODS = frozenset(
    {"bulk_extract", "public_api", "public_api_with_key", "feed"}
)

COLLECTOR_STATUSES = frozenset({"not_built", "in_progress", "built", "blocked"})

LEGAL_TERMS_STATUSES = frozenset(
    {
        "attribution_required",
        "api_key_and_role_required",
        "no_review_required",
        "terms_review_required",
    }
)

# Grants.gov extract retention. A missed day cannot be recovered, which is why
# a failure pages rather than retries.
GRANTS_GOV_EXTRACT_RETENTION_DAYS = 7

# SAM.gov daily request ceilings. The role is the difference between a usable
# collector and 10 calls a day.
SAM_RATE_LIMIT_NO_ROLE_PER_DAY = 10
SAM_RATE_LIMIT_WITH_ROLE_PER_DAY = 1000

# Every collector must retain these four. They are what makes an extraction
# auditable later - the same rule Gates 87-88 arrived at for the corpus.
REQUIRED_RETENTION_FIELDS: tuple[str, ...] = (
    "must_store_raw_payload",
    "must_store_retrieved_at",
    "must_store_source_hash",
    "must_store_attribution",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _entry(
    *,
    source_id: str,
    source_name: str,
    source_role: str,
    build_order: int,
    collection_method: str,
    auth_required: bool,
    rate_limit_notes: str,
    legal_terms_status: str,
    activation_blocked_reasons: list[str],
    attribution_text: str | None = None,
    retention_notes: str | None = None,
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "source_name": source_name,
        "source_role": source_role,
        "build_order": build_order,
        "collection_method": collection_method,
        "auth_required": auth_required,
        "rate_limit_notes": rate_limit_notes,
        "legal_terms_status": legal_terms_status,
        "collector_status": "not_built",
        "activation_blocked_reasons": list(activation_blocked_reasons),
        # All four required, on every source.
        "must_store_raw_payload": True,
        "must_store_retrieved_at": True,
        "must_store_source_hash": True,
        "must_store_attribution": bool(attribution_text),
        "attribution_text": attribution_text,
        "retention_notes": retention_notes,
    }


def build_phase1_spine_plan() -> dict[str, Any]:
    """The five Phase 1 sources, in build order."""
    sources = [
        _entry(
            source_id="GRANTS-GOV-EXTRACT",
            source_name="Grants.gov daily XML extract",
            source_role="corpus_of_record",
            build_order=1,
            collection_method="bulk_extract",
            auth_required=False,
            rate_limit_notes=(
                "One file per day, published ~04:40 ET, ~78 MB. Retained "
                f"{GRANTS_GOV_EXTRACT_RETENTION_DAYS} days only - a missed day "
                "is unrecoverable, so a failed fetch pages a human rather than "
                "retrying into the retention window."
            ),
            legal_terms_status="attribution_required",
            attribution_text=GRANTS_GOV_ATTRIBUTION,
            retention_notes=(
                "Only source carrying Estimated Synopsis Post Date, Fiscal Year, "
                "Archive Date, the 18,000-char description and the 4,000-char "
                "Additional Information on Eligibility."
            ),
            activation_blocked_reasons=[
                "collector_not_built",
                "attribution_surface_not_implemented",
            ],
        ),
        _entry(
            source_id="GRANTS-GOV-SEARCH2",
            source_name="Grants.gov Search2 + fetchOpportunity",
            source_role="delta_accelerator",
            build_order=2,
            collection_method="public_api",
            auth_required=False,
            rate_limit_notes=(
                "No auth. Hourly deltas. fetchOpportunity returns "
                "synopsisModifiedFields[] / forecastModifiedFields[] - render "
                "the named change to users, not 'something changed'."
            ),
            legal_terms_status="attribution_required",
            attribution_text=GRANTS_GOV_ATTRIBUTION,
            retention_notes=(
                "Delta accelerator and amendment forensics. NOT the corpus of "
                "record - the daily extract is."
            ),
            activation_blocked_reasons=[
                "collector_not_built",
                "attribution_surface_not_implemented",
            ],
        ),
        _entry(
            source_id="FEDERAL-REGISTER-API",
            source_name="Federal Register API including Public Inspection",
            source_role="notice_feed",
            build_order=3,
            collection_method="public_api",
            auth_required=False,
            rate_limit_notes=(
                "No key, documented. Public Inspection endpoints exist and are "
                "documented; the 1-3 business day lead time they buy is the "
                "dossier's inference, not its documentation. Pagination is "
                "capped at the first 2,000 results - partition every backfill "
                "by date range."
            ),
            legal_terms_status="no_review_required",
            retention_notes=(
                "conditions[agencies][]=indian-affairs-bureau is a better "
                "instrument for BIA than bia.gov itself."
            ),
            activation_blocked_reasons=["collector_not_built"],
        ),
        _entry(
            source_id="SAM-GOV-ASSISTANCE-LISTINGS",
            source_name="SAM.gov Assistance Listings API",
            source_role="program_catalog",
            build_order=4,
            collection_method="public_api_with_key",
            auth_required=True,
            rate_limit_notes=(
                f"{SAM_RATE_LIMIT_NO_ROLE_PER_DAY} requests/day for a "
                "non-federal user with no SAM role; "
                f"{SAM_RATE_LIMIT_WITH_ROLE_PER_DAY}/day with a role. The rate "
                "limit is the binding constraint - obtain a role before "
                "building anything on it."
            ),
            legal_terms_status="api_key_and_role_required",
            retention_notes=(
                "ALN semantics and tribal eligibility codes. SAM.gov prohibits "
                "automated data gathering and web scraping outright; detection "
                "results in loss of access. API with key only."
            ),
            activation_blocked_reasons=[
                "collector_not_built",
                "api_key_not_obtained",
                "sam_role_not_obtained",
                "scraping_prohibited_api_only",
            ],
        ),
        _entry(
            source_id="USASPENDING-API-V2",
            source_name="USAspending API v2",
            source_role="prior_award_intelligence",
            build_order=5,
            collection_method="public_api",
            auth_required=False,
            rate_limit_notes="No key documented in the research pass.",
            legal_terms_status="no_review_required",
            retention_notes=(
                "Prior-award intelligence and recurring-program patterns. NOT "
                "current-deadline discovery - never surface a USAspending "
                "record as an open opportunity."
            ),
            activation_blocked_reasons=["collector_not_built"],
        ),
    ]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "phase": 1,
            "source_count": len(sources),
            "build_order": [s["source_id"] for s in sources],
            "sources": sources,
            "corpus_of_record_id": "GRANTS-GOV-EXTRACT",
            "grants_gov_attribution": GRANTS_GOV_ATTRIBUTION,
            "sam_scraping_prohibited": True,
            "sam_rate_limit_no_role_per_day": SAM_RATE_LIMIT_NO_ROLE_PER_DAY,
            "sam_rate_limit_with_role_per_day": SAM_RATE_LIMIT_WITH_ROLE_PER_DAY,
            "grants_gov_extract_retention_days": GRANTS_GOV_EXTRACT_RETENTION_DAYS,
            "grants_gov_missed_day_is_unrecoverable": True,
            # Constants for this gate.
            "collectors_built": 0,
            "collectors_active": 0,
            "urls_fetched": 0,
            "monitoring_started": False,
            "live_coverage_claimed": False,
            "fabricated": False,
        }
    )


def spine_invariant_failures(plan: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if plan.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if plan.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    for constant in ("monitoring_started", "live_coverage_claimed"):
        if plan.get(constant) is not False:
            fails.append(f"plan_claimed:{constant}")
    for counter in ("collectors_built", "collectors_active", "urls_fetched"):
        if plan.get(counter):
            fails.append(f"plan_reported_nonzero:{counter}")

    # The attribution is a build requirement and must survive verbatim.
    if plan.get("grants_gov_attribution") != GRANTS_GOV_ATTRIBUTION:
        fails.append("grants_gov_attribution_altered")
    if plan.get("sam_scraping_prohibited") is not True:
        fails.append("sam_scraping_prohibition_dropped")

    sources = plan.get("sources") or []
    orders = [s.get("build_order") for s in sources]
    if orders != sorted(orders) or orders != list(range(1, len(sources) + 1)):
        fails.append("build_order_is_not_a_contiguous_sequence")

    for source in sources:
        sid = source.get("source_id")
        if source.get("source_role") not in SOURCE_ROLES:
            fails.append(f"source_role_out_of_vocabulary:{sid}")
        if source.get("collection_method") not in COLLECTION_METHODS:
            fails.append(f"collection_method_out_of_vocabulary:{sid}")
        if source.get("collector_status") not in COLLECTOR_STATUSES:
            fails.append(f"collector_status_out_of_vocabulary:{sid}")
        if source.get("collector_status") != "not_built":
            fails.append(f"collector_claimed_built:{sid}")
        if source.get("legal_terms_status") not in LEGAL_TERMS_STATUSES:
            fails.append(f"legal_terms_status_out_of_vocabulary:{sid}")
        if not source.get("activation_blocked_reasons"):
            fails.append(f"source_without_activation_blocker:{sid}")

        # Retention rules apply to every collector without exception.
        for field in REQUIRED_RETENTION_FIELDS[:3]:
            if source.get(field) is not True:
                fails.append(f"retention_requirement_dropped:{sid}:{field}")

        # A Grants.gov source must carry the attribution, verbatim.
        if sid and sid.startswith("GRANTS-GOV"):
            if source.get("attribution_text") != GRANTS_GOV_ATTRIBUTION:
                fails.append(f"grants_gov_source_without_attribution:{sid}")
            if source.get("must_store_attribution") is not True:
                fails.append(f"grants_gov_attribution_not_required:{sid}")

        # SAM.gov must be API-with-key and must name the scraping prohibition.
        if sid == "SAM-GOV-ASSISTANCE-LISTINGS":
            if source.get("collection_method") != "public_api_with_key":
                fails.append("sam_not_marked_api_with_key")
            if source.get("auth_required") is not True:
                fails.append("sam_not_marked_auth_required")
            if not any(
                "scraping_prohibited" in str(r)
                for r in source.get("activation_blocked_reasons") or []
            ):
                fails.append("sam_scraping_prohibition_not_blocked")

    # Exactly one corpus of record, and it is the extract.
    corpus = [s for s in sources if s.get("source_role") == "corpus_of_record"]
    if len(corpus) != 1:
        fails.append("expected_exactly_one_corpus_of_record")
    elif corpus[0].get("source_id") != plan.get("corpus_of_record_id"):
        fails.append("corpus_of_record_id_mismatch")

    # Search2 must never be the corpus of record.
    for source in sources:
        if source.get("source_id") == "GRANTS-GOV-SEARCH2":
            if source.get("source_role") != "delta_accelerator":
                fails.append("search2_is_not_marked_a_delta_accelerator")

    return fails
