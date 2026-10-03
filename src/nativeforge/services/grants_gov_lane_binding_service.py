"""Discovery lanes on the one Grants.gov endpoint (Phase 1A).

Four of the publishers Tranche 2 proved - HUD ONAP, IHS, EPA and CDFI Fund -
do not publish their own machine-readable opportunity feed. Each close report
says so in its own words: *"Grants.gov owns the records."* Their Tranche 2
commits added semantic services (`program_office_roster_service`,
`native_entity_class_service`, `funding_channel_service`) and, for HUD, 193
lines of assistance-listing support inside the Grants.gov adapter itself. None
of them added a transport, because none of them needed one.

So they are not four collectors. They are four **query lanes** on
`https://api.grants.gov/v1/api/search2`, which is already the only entry in
`ADAPTER_CAPABILITIES`. The forecast surface is a fifth lane on the same
endpoint.

## Why a lane needs its own registry row

`source_collector_capability_service` measures capability against a registry
row and requires the adapter's `endpoint_constant` to equal that row's
`source_url` exactly. Every lane here targets the same endpoint, so every lane
can satisfy that check - but each needs its own row, because the row is also
where authorization lives. One row per lane means Mayhem authorizes HUD ONAP
without thereby authorizing EPA, which is the decision the packet asked for.

## Why the parameters live here and not in the CSV

The seed CSV's eleven columns carry no lane fields, and widening a 179-row
schema to express five rows is the wrong trade. `SEED_ALN_BINDINGS` already
set the precedent: bind by `seed_id`, in code, where the binding can carry the
evidence that justifies it.

## What a lane deliberately does NOT do

A lane is a **discovery query**. It decides which records to ask Grants.gov
for. It decides nothing about who may apply, whether a record is Native-
relevant, or whether it is worth pursuing:

```text
ELIGIBILITY != VISIBILITY
ELIGIBILITY != RELEVANCE
ELIGIBILITY != STRATEGIC VALUE
```

This matters concretely and the evidence is in the packet. HUD's `FR-6900-N-74`
is a $5,000,000 ICDBG award that declares applicant type **25 only** and is
returned **zero times out of three** by codes 07/08/11 - so a lane restricted
to the Tribal eligibility codes would never see it. IHS code 25 carries both
Tribe-eligible and Tribe-ineligible Native-serving money, so a lane must not
stamp `tribal = true` on what it retrieves. EPA defers eligibility to its
documents **100%** of the measured sample, so a lane that inferred eligibility
from listing metadata would be inventing it.

None of these lanes sets an eligibility field. They set a query.
"""

from __future__ import annotations

import json
from typing import Any, Final

from nativeforge.services.grants_gov_search_api_adapter_service import (
    FETCH_MODE_LIVE,
    OUTCOME_EMPTY,
    OUTCOME_FETCH_ERROR,
    OUTCOME_HITS,
    SCHEMA_VERSION as ADAPTER_SCHEMA_VERSION,
    SEARCH2_URL,
    _authorization_refusals,
    default_grants_gov_http_post,
)

#: Re-exported so this module can serve as the adapter module for the lane
#: capability keys. `source_collector_capability_service` resolves
#: `endpoint_constant` with `getattr(module, ...)`, and it must equal the
#: registry row's `source_url` exactly - every lane targets the one Grants.gov
#: endpoint, so every lane names this same constant.
__all__ = [
    "SEARCH2_URL",
    "SEED_LANE_BINDINGS",
    "build_grants_gov_lane_search_body",
    "lane_binding",
    "lane_invariant_failures",
    "search_grants_gov_lane",
]

#: Lane adapter keys. Three, not five: IHS, EPA and CDFI differ only by which
#: agency code they ask for, which is a parameter rather than a program.
LANE_AGENCY: Final[str] = "grants_gov_search2_agency"
LANE_ASSISTANCE_LISTING: Final[str] = "grants_gov_search2_assistance_listing"
LANE_FORECAST: Final[str] = "grants_gov_search2_forecast"

LANE_ADAPTER_KEYS: Final[tuple[str, ...]] = (
    LANE_AGENCY,
    LANE_ASSISTANCE_LISTING,
    LANE_FORECAST,
)

#: Rows per page. Bounded on purpose - a lane is a sampling query, not a dump,
#: and an unbounded first request is how a polite client stops being one.
DEFAULT_LANE_ROWS: Final[int] = 100

#: seed_id -> the query that lane issues, plus the evidence for it.
#:
#: `agency` and `cfda` are Grants.gov's own parameters. `evidence` names where
#: the value came from, because an agency code that looks obvious can be wrong:
#: CDFI's `TREAS`, `TREAS-CDFI` and `CDFI` all returned exactly what the
#: nonsense control returned, and the real code `USDOT-CDFI` was found only by
#: reading records.
SEED_LANE_BINDINGS: Final[dict[str, dict[str, Any]]] = {
    "nf-seed-2026-api-grants-gov-forecast": {
        "adapter_key": LANE_FORECAST,
        "opp_statuses": "forecasted",
        "evidence": (
            "868 Wave 1: docType 'forecast' and oppStatus 'forecasted' "
            "confirmed on the wire; 431 forecasted elig-07 reported"
        ),
    },
    "nf-seed-2026-api-grants-gov-hud-onap": {
        "adapter_key": LANE_ASSISTANCE_LISTING,
        "cfda": "14.862",
        "opp_statuses": "posted|forecasted",
        "evidence": (
            "869/873 Tranche 2B: FR-6900-N-74 declares applicant type 25 "
            "only and is returned 0 of 3 times by codes 07/08/11; ALN 14.862 "
            "returns it immediately"
        ),
    },
    "nf-seed-2026-api-grants-gov-ihs": {
        "adapter_key": LANE_AGENCY,
        "agency": "HHS-IHS",
        "opp_statuses": "posted|forecasted",
        "evidence": (
            "870/873 Tranche 2C: complete corpus 245 records, 18 current, "
            "eligibility facet found all 18"
        ),
    },
    "nf-seed-2026-api-grants-gov-epa": {
        "adapter_key": LANE_AGENCY,
        "agency": "EPA",
        "opp_statuses": "posted|forecasted",
        "evidence": (
            "871/873 Tranche 2D: complete corpus 1,491 records; eligibility "
            "deferred to document in 5 of 5 sampled (100%)"
        ),
    },
    "nf-seed-2026-api-grants-gov-cdfi": {
        "adapter_key": LANE_AGENCY,
        "agency": "USDOT-CDFI",
        "opp_statuses": "posted|forecasted",
        "evidence": (
            "872/873 Tranche 2E: TREAS, TREAS-CDFI and CDFI all returned what "
            "the NONSENSE control returned; USDOT-CDFI found by reading "
            "records. 63 records, all archived - zero open is the correct "
            "answer, proven by a negative control"
        ),
    },
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def lane_binding(seed_id: Any) -> dict[str, Any] | None:
    """The lane this seed row is, or None if it is not a lane row."""
    key = str(seed_id or "").strip()
    binding = SEED_LANE_BINDINGS.get(key)
    return dict(binding) if binding else None


def build_grants_gov_lane_search_body(source: dict[str, Any]) -> dict[str, Any]:
    """The query this lane issues, built from the row it is given.

    Signature is positional-single-dict because that is what
    `source_collector_capability_service` calls: it builds a real request for
    the row under test, and a builder that cannot produce one is not a
    capability for that source whatever it can do for others.

    Carries no keyword. Wave 1 removed keyword discovery from the eligibility
    lane because the Tribal-eligible opportunities whose titles never say
    "Tribal" are exactly the ones that matter - of the first 100 sampled
    elig-07 titles, 4 contained Native wording. Re-adding a keyword here would
    quietly reinstate the blind spot in a new place.
    """
    row = dict(source or {})
    binding = lane_binding(row.get("seed_id"))
    if binding is None:
        raise ValueError(
            f"no lane binding for seed_id {row.get('seed_id')!r}; "
            f"known lanes: {sorted(SEED_LANE_BINDINGS)}"
        )

    body: dict[str, Any] = {
        "rows": DEFAULT_LANE_ROWS,
        "startRecordNum": 0,
        "oppStatuses": str(binding.get("opp_statuses") or "posted"),
    }
    if binding.get("agency"):
        body["agencies"] = str(binding["agency"])
    if binding.get("cfda"):
        body["cfda"] = str(binding["cfda"])
    return _json_safe(body)


def lane_invariant_failures(body: dict[str, Any] | None) -> list[str]:
    """What a lane body may never contain.

    Stated as a check rather than a comment because both of these have already
    gone wrong once in this codebase: keyword discovery was the Wave 1 defect,
    and an eligibility filter on a discovery lane is how HUD's $5M ICDBG award
    becomes invisible.
    """
    found = dict(body or {})
    failures: list[str] = []
    if "keyword" in found:
        failures.append("a_lane_must_not_carry_a_keyword")
    if "eligibilities" in found:
        failures.append("a_discovery_lane_must_not_filter_by_eligibility")
    if not found.get("oppStatuses"):
        failures.append("a_lane_must_state_which_statuses_it_asks_for")
    if int(found.get("rows") or 0) <= 0:
        failures.append("a_lane_must_be_bounded")
    return failures


def search_grants_gov_lane(
    source: dict[str, Any],
    *,
    http_post: Any = None,
    fetch_mode: str = FETCH_MODE_LIVE,
) -> dict[str, Any]:
    """Execute one discovery lane for the registry row it is given.

    Shared by every lane adapter key, because the lanes differ by query
    parameter rather than by protocol. The row decides which lane; this
    function decides nothing.

    The refusal handling is not boilerplate. An authorization refusal is
    re-raised unchanged so the guard's own reasons reach the caller, while a
    transport failure returns a labelled outcome. Collapsing the two would
    turn "the guard refused to let us ask" into `hit_count: 0`, which reads
    as "this publisher has nothing" - the Gate 140 defect wearing a new coat.
    """
    do_post = http_post or default_grants_gov_http_post
    body = build_grants_gov_lane_search_body(source)

    def _failed(message: str) -> dict[str, Any]:
        return _json_safe(
            {
                "schema_version": ADAPTER_SCHEMA_VERSION,
                "search_body": body,
                "hit_count": 0,
                "opp_hits": [],
                "search_live": False,
                "fetch_mode": fetch_mode,
                "outcome": OUTCOME_FETCH_ERROR,
                "api_error": message,
                "never_synthesized": True,
            }
        )

    try:
        raw = do_post(SEARCH2_URL, body)
    except _authorization_refusals() as refusal:
        raise refusal
    except Exception as exc:  # noqa: BLE001 - transport failure is not refusal
        return _failed(str(exc))

    if raw.get("errorcode") != 0:
        return _failed(str(raw.get("msg") or raw.get("errorcode")))

    data = raw.get("data") or {}
    hits = [hit for hit in (data.get("oppHits") or []) if isinstance(hit, dict)]
    return _json_safe(
        {
            "schema_version": ADAPTER_SCHEMA_VERSION,
            "search_body": body,
            "hit_count": len(hits),
            "opp_hits": hits,
            "search_live": True,
            "fetch_mode": fetch_mode,
            # An empty lane is a real answer, not a failure. CDFI returns 63
            # archived records and zero open, and a negative control proved
            # that zero is the publisher's answer rather than a broken query.
            "outcome": OUTCOME_HITS if hits else OUTCOME_EMPTY,
            "never_synthesized": True,
        }
    )
