"""Gate 163: the negative proofs for the authorization-aware Gate 77B guard.

Every one of these must be REFUSED. A guard that permits the right case and
has never been shown to refuse the wrong ones has not been tested - and this
is the guard standing between a recorded authorization and a real HTTP request
to a government API.

The last two are the ones that matter most:

```text
global ENV flag absent + valid recorded authorization  -> PERMITTED
                          (the flag is not what permits the Gate 163 path)
direct live transport bypassing the guard              -> IMPOSSIBLE
                          (build_live_transport takes no pre-validated
                           authorization; it calls the enforcement itself)
```

Writes nothing. Makes no network request: every case is refused before a
socket could exist, and the permitted case only builds a transport without
dispatching it.
"""

from __future__ import annotations

import inspect
import json
import os
import sys
import uuid

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.services.hermetic_test_guard_service import (  # noqa: E402
    ENV_ALLOW_LIVE_NETWORK,
    live_network_allowed,
)
from nativeforge.services.live_source_transport_service import (  # noqa: E402
    LiveTransportRefused,
    build_live_transport,
)
from nativeforge.services.source_live_warrant_service import (  # noqa: E402
    WARRANT_ROBOTS_PREFLIGHT,
    WARRANT_SOURCE_COLLECTION,
    evaluate_live_request,
    warrant_invariant_failures,
)

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
AUTHORIZED = "nf-seed-2026-api-grants-gov-search2"
API_URL = "https://api.grants.gov/v1/api/search2"
ROBOTS_URL = "https://api.grants.gov/robots.txt"

out: dict[str, object] = {}
detail: list[str] = []

session = SessionLocal()
try:

    def refused(label: str, **kwargs) -> bool:
        kwargs.setdefault("connection", session)
        kwargs.setdefault("organization_id", DEMO)
        decision = evaluate_live_request(**kwargs)
        # A deliberately-invalid warrant kind trips the vocabulary invariant
        # by design. Only collect invariant failures for cases whose inputs
        # are themselves well-formed, or a passing phase reports a detail
        # line about its own test input.
        for failure in warrant_invariant_failures(decision):
            if not failure.startswith("warrant_kind_outside_vocabulary"):
                detail.append(failure)
        if decision["permitted"]:
            detail.append(f"{label}: PERMITTED but should have been refused")
        return not decision["permitted"]

    # ---- the enumerated negatives ------------------------------------
    out["grants_gov_with_no_source_id_is_refused"] = refused(
        "no source id",
        warrant_kind=WARRANT_SOURCE_COLLECTION,
        authorized_source_id=None,
        request_url=API_URL,
        method="POST",
    )
    out["grants_gov_with_a_wrong_source_id_is_refused"] = refused(
        "wrong source id",
        warrant_kind=WARRANT_SOURCE_COLLECTION,
        authorized_source_id="nf-seed-2026-fed-001",
        request_url=API_URL,
        method="POST",
    )
    out["grants_gov_with_a_wrong_host_is_refused"] = refused(
        "wrong host",
        warrant_kind=WARRANT_SOURCE_COLLECTION,
        authorized_source_id=AUTHORIZED,
        request_url="https://www.grants.gov/v1/api/search2",
        method="POST",
    )
    out["a_preflight_warrant_cannot_request_search2"] = refused(
        "preflight warrant on the API path",
        warrant_kind=WARRANT_ROBOTS_PREFLIGHT,
        authorized_source_id=AUTHORIZED,
        request_url=API_URL,
        method="POST",
    )
    out["a_preflight_warrant_cannot_use_post"] = refused(
        "preflight with POST",
        warrant_kind=WARRANT_ROBOTS_PREFLIGHT,
        authorized_source_id=AUTHORIZED,
        request_url=ROBOTS_URL,
        method="POST",
    )
    out["another_grants_gov_registry_row_is_refused"] = refused(
        "another grants.gov row",
        warrant_kind=WARRANT_SOURCE_COLLECTION,
        authorized_source_id="nf-seed-2026-fed-017",
        request_url="https://www.grants.gov/search-results-detail/361960",
        method="GET",
    )
    out["another_source_entirely_is_refused"] = refused(
        "another source",
        warrant_kind=WARRANT_SOURCE_COLLECTION,
        authorized_source_id="nf-seed-2026-t3-065",
        request_url="https://nativephilanthropy.org",
        method="GET",
    )
    out["an_unknown_warrant_kind_is_refused"] = refused(
        "unknown warrant kind",
        warrant_kind="just_this_once",
        authorized_source_id=AUTHORIZED,
        request_url=API_URL,
        method="POST",
    )
    out["http_instead_of_https_is_refused"] = refused(
        "http",
        warrant_kind=WARRANT_ROBOTS_PREFLIGHT,
        authorized_source_id=AUTHORIZED,
        request_url="http://api.grants.gov/robots.txt",
        method="GET",
    )
    out["no_connection_means_nothing_is_verifiable_and_it_is_refused"] = refused(
        "no connection",
        warrant_kind=WARRANT_ROBOTS_PREFLIGHT,
        authorized_source_id=AUTHORIZED,
        request_url=ROBOTS_URL,
        method="GET",
        connection=None,
    )

    # ---- collection without the opt-in -------------------------------
    collection = evaluate_live_request(
        warrant_kind=WARRANT_SOURCE_COLLECTION,
        authorized_source_id=AUTHORIZED,
        request_url=API_URL,
        method="POST",
        connection=session,
        organization_id=DEMO,
    )
    detail.extend(warrant_invariant_failures(collection))
    out["collection_without_the_opt_in_is_refused"] = bool(
        not collection["permitted"]
        and "live_fetch_is_not_opted_in_for_this_source"
        in collection["refusal_reasons"]
    )
    out["collection_requires_the_opt_in"] = bool(
        collection["live_fetch_opt_in_required"]
    )

    # ---- the PERMITTED case, without the legacy flag -----------------
    flag_present = ENV_ALLOW_LIVE_NETWORK in os.environ
    out["legacy_env_flag_is_absent"] = not live_network_allowed()
    # Informational, not a requirement. The flag being ABSENT is the
    # point; asserting its presence true had the polarity backwards.
    out["legacy_env_flag_in_environment_informational"] = flag_present

    preflight = evaluate_live_request(
        warrant_kind=WARRANT_ROBOTS_PREFLIGHT,
        authorized_source_id=AUTHORIZED,
        request_url=ROBOTS_URL,
        method="GET",
        connection=session,
        organization_id=DEMO,
    )
    detail.extend(warrant_invariant_failures(preflight))
    out["a_valid_preflight_is_permitted_without_the_env_flag"] = bool(
        preflight["permitted"] and not live_network_allowed()
    )
    if not preflight["permitted"]:
        detail.append(f"preflight refused: {preflight['refusal_reasons']}")
    out["the_permitted_path_does_not_require_the_legacy_flag"] = bool(
        not preflight["legacy_env_flag_required"]
    )

    # ---- bypass is structurally impossible ---------------------------
    #
    # Asserted on the SIGNATURE, not in prose: `build_live_transport` must not
    # accept a pre-validated authorization, and must call the enforcement.
    params = set(inspect.signature(build_live_transport).parameters)
    out["build_live_transport_takes_no_prevalidated_authorization"] = bool(
        "authorization" not in params
    )
    out["build_live_transport_requires_a_warrant_kind"] = bool(
        "warrant_kind" in params
    )
    source = inspect.getsource(build_live_transport)
    out["build_live_transport_calls_the_enforcement_path"] = bool(
        "assert_live_request_permitted" in source
    )

    # And it actually refuses when handed an unauthorized source.
    try:
        build_live_transport(
            authorized_source_id="nf-seed-2026-fed-001",
            authorized_url="https://www.bia.gov/topic/grants",
            warrant_kind=WARRANT_SOURCE_COLLECTION,
            connection=session,
            organization_id=DEMO,
        )
        out["build_live_transport_refuses_an_unauthorized_source"] = False
        detail.append("build_live_transport BUILT a transport for a wrong source")
    except LiveTransportRefused:
        out["build_live_transport_refuses_an_unauthorized_source"] = True

    # And it BUILDS for the authorized preflight - so the permitting branch is
    # reachable and the refusals above are falsifiable.
    try:
        transport = build_live_transport(
            authorized_source_id=AUTHORIZED,
            authorized_url=ROBOTS_URL,
            warrant_kind=WARRANT_ROBOTS_PREFLIGHT,
            connection=session,
            organization_id=DEMO,
        )
        out["build_live_transport_builds_for_the_authorized_preflight"] = bool(
            callable(transport)
        )
        # Built, never called. No request is made by this phase.
        del transport
    except LiveTransportRefused as refusal:
        out["build_live_transport_builds_for_the_authorized_preflight"] = False
        detail.append(f"authorized preflight refused: {refusal.reasons}")
finally:
    session.close()

for key in (
    "grants_gov_with_no_source_id_is_refused",
    "grants_gov_with_a_wrong_source_id_is_refused",
    "grants_gov_with_a_wrong_host_is_refused",
    "a_preflight_warrant_cannot_request_search2",
    "a_preflight_warrant_cannot_use_post",
    "another_grants_gov_registry_row_is_refused",
    "another_source_entirely_is_refused",
    "an_unknown_warrant_kind_is_refused",
    "http_instead_of_https_is_refused",
    "no_connection_means_nothing_is_verifiable_and_it_is_refused",
    "collection_without_the_opt_in_is_refused",
    "collection_requires_the_opt_in",
    "legacy_env_flag_is_absent",
    "a_valid_preflight_is_permitted_without_the_env_flag",
    "the_permitted_path_does_not_require_the_legacy_flag",
    "build_live_transport_takes_no_prevalidated_authorization",
    "build_live_transport_requires_a_warrant_kind",
    "build_live_transport_calls_the_enforcement_path",
    "build_live_transport_refuses_an_unauthorized_source",
    "build_live_transport_builds_for_the_authorized_preflight",
):
    out.setdefault(key, False)

out["detail"] = "; ".join(sorted(set(detail))) if detail else None
print(json.dumps(out, sort_keys=True))
