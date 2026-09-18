"""Gate 163: refusal, fetch error and true-empty are three different answers.

The adapter wrapped its transport call in a bare `except Exception` and
returned `hit_count: 0` for everything, so a Gate 77B refusal was
indistinguishable from "Grants.gov has no tribal grants". Each outcome is
tested on its own here.

Makes no network request: every transport is injected.
"""

from __future__ import annotations

import json
import sys

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from nativeforge.services.grants_gov_search_api_adapter_service import (  # noqa: E402
    OUTCOME_EMPTY,
    OUTCOME_FETCH_ERROR,
    OUTCOME_HITS,
    search_grants_gov_opportunities,
)
from nativeforge.services.live_source_transport_service import (  # noqa: E402
    LiveTransportRefused,
)
from nativeforge.services.source_live_warrant_service import (  # noqa: E402
    LiveRequestRefused,
)

SOURCE = {
    "seed_id": "nf-seed-2026-api-grants-gov-search2",
    "source_name": "Grants.gov Search2 API",
    "source_url": "https://api.grants.gov/v1/api/search2",
}

out: dict[str, object] = {}
detail: list[str] = []


# ---- 1. an authorization refusal must RAISE ----------------------------
for label, refusal in (
    ("transport", LiveTransportRefused(["a_live_dispatch_named_no_authorized_source"])),
    (
        "warrant",
        LiveRequestRefused(
            ["live_fetch_is_not_opted_in_for_this_source"],
            warrant={"warrant_kind": "source_collection"},
        ),
    ),
):

    def refuse(url: str, body: dict, _exc: BaseException = refusal) -> dict:
        raise _exc

    try:
        result = search_grants_gov_opportunities(SOURCE, http_post=refuse)
        out[f"a_{label}_refusal_raises"] = False
        detail.append(
            f"a {label} refusal returned a result instead of raising: "
            f"outcome={result.get('outcome')} hit_count={result.get('hit_count')}"
        )
    except (LiveTransportRefused, LiveRequestRefused):
        out[f"a_{label}_refusal_raises"] = True
    except Exception as exc:  # noqa: BLE001
        out[f"a_{label}_refusal_raises"] = False
        detail.append(f"a {label} refusal became {type(exc).__name__}")


# ---- 2. a transport failure is a fetch error, not a refusal -----------
def explode(url: str, body: dict) -> dict:
    raise TimeoutError("the host did not answer")


failed = search_grants_gov_opportunities(SOURCE, http_post=explode)
out["a_network_failure_is_a_fetch_error"] = failed.get("outcome") == OUTCOME_FETCH_ERROR
out["a_network_failure_says_what_went_wrong"] = bool(failed.get("api_error"))
out["a_network_failure_does_not_raise"] = True


# ---- 3. an API-level error is a fetch error too ------------------------
def api_error(url: str, body: dict) -> dict:
    return {"errorcode": 1, "msg": "invalid request"}


errored = search_grants_gov_opportunities(SOURCE, http_post=api_error)
out["an_api_error_is_a_fetch_error"] = errored.get("outcome") == OUTCOME_FETCH_ERROR
out["an_api_error_says_what_went_wrong"] = bool(errored.get("api_error"))


# ---- 4. a valid response with zero results is a TRUE empty ------------
def empty(url: str, body: dict) -> dict:
    return {"errorcode": 0, "data": {"oppHits": []}}


nothing = search_grants_gov_opportunities(SOURCE, http_post=empty)
out["zero_results_is_a_true_empty"] = nothing.get("outcome") == OUTCOME_EMPTY
out["a_true_empty_carries_no_error"] = nothing.get("api_error") is None
out["a_true_empty_was_live"] = bool(nothing.get("search_live"))


# ---- 5. and hits are hits --------------------------------------------
def hit(url: str, body: dict) -> dict:
    return {
        "errorcode": 0,
        "data": {"oppHits": [{"number": "NF-163-PROOF", "title": "proof"}]},
    }


found = search_grants_gov_opportunities(SOURCE, http_post=hit)
out["hits_are_reported_as_hits"] = found.get("outcome") == OUTCOME_HITS
out["hits_are_counted"] = int(found.get("hit_count") or 0) == 1


# ---- 6. the three are distinguishable from each other ----------------
#
# The point of the whole change. Before it, these three returned the same
# shape and a caller could not tell them apart.
outcomes = {
    "fetch_error": failed.get("outcome"),
    "true_empty": nothing.get("outcome"),
    "hits": found.get("outcome"),
}
out["the_outcomes_are_distinct"] = len(set(outcomes.values())) == 3
out["outcomes"] = outcomes

# And the empty case is not reported as an error, which was the specific
# confusion: zero hits used to arrive with `api_error` populated.
out["a_true_empty_is_not_an_error"] = bool(
    nothing.get("outcome") != failed.get("outcome") and nothing.get("api_error") is None
)

for key in (
    "a_transport_refusal_raises",
    "a_warrant_refusal_raises",
    "a_network_failure_is_a_fetch_error",
    "a_network_failure_says_what_went_wrong",
    "an_api_error_is_a_fetch_error",
    "an_api_error_says_what_went_wrong",
    "zero_results_is_a_true_empty",
    "a_true_empty_carries_no_error",
    "a_true_empty_was_live",
    "hits_are_reported_as_hits",
    "hits_are_counted",
    "the_outcomes_are_distinct",
    "a_true_empty_is_not_an_error",
):
    out.setdefault(key, False)

out["detail"] = "; ".join(sorted(set(detail))) if detail else None
print(json.dumps(out, sort_keys=True))
