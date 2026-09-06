"""Gate 143C: is a collector configured well enough to be allowed to run?

## Seven things a collector must declare

```text
source_id                 which source, and it must pass the allowlist
fetch_mode                dry_run | live_fetch — live needs an approval
rate_limit_policy         a declared policy, not "as fast as it goes"
attribution_requirement   ATTRIBUTION_REQUIRED means verbatim, or nothing runs
user_agent_policy         the canonical NativeForge UA, identifiable
raw_payload_storage_policy where the bytes land. Gate 97's modes.
activation_approval       somebody decided. Not a config value.
```

Any one missing and the collector is refused by name. All seven present and it
is still refused unless the source itself passes `source_monitoring_approved_
source_service` — a perfectly configured collector pointed at a source whose
terms nobody has read is the exact thing this gate exists to stop.

## Configuration is not activation

`fetch_mode: live_fetch` is a **request**, not a permission.
`activation_approval` is the permission, and this module cannot manufacture
one. The same separation Gate 141B made for object storage and Gate 142B for
email: five settings being filled in and somebody having decided are different
facts.

## Names, never values

An API key's presence may be reported. Its value may not — not truncated, not
prefixed, not measured. `api_key_values_reported: False` is on every result and
an invariant scans the serialised form for key-shaped markers.

## Nothing is contacted

No socket, no fetch, no robots.txt, no DNS. This module reads a configuration
dict and a registry row and returns booleans.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_source_collector_configuration_preflight_v1"

#: What a collector must declare. Named so a refusal can point at one.
REQUIRED_CONFIG_KEYS: tuple[str, ...] = (
    "source_id",
    "fetch_mode",
    "rate_limit_policy",
    "attribution_requirement",
    "user_agent_policy",
    "raw_payload_storage_policy",
    "activation_approval",
)

FETCH_MODES: frozenset[str] = frozenset({"dry_run", "live_fetch"})

#: The mode that would actually reach a source.
LIVE_FETCH_MODES: frozenset[str] = frozenset({"live_fetch"})

RATE_LIMIT_POLICIES: frozenset[str] = frozenset(
    {"polite_default", "publisher_declared", "conservative", "unknown"}
)
DECLARED_RATE_LIMIT_POLICIES: frozenset[str] = frozenset(
    {"polite_default", "publisher_declared", "conservative"}
)

ATTRIBUTION_REQUIREMENTS: frozenset[str] = frozenset(
    {"not_required", "attribution_required", "unknown"}
)
#: An attribution requirement that is satisfied only by carrying it verbatim.
ATTRIBUTION_NEEDING_VERBATIM: frozenset[str] = frozenset({"attribution_required"})

USER_AGENT_POLICIES: frozenset[str] = frozenset(
    {"nativeforge_canonical", "custom", "absent", "unknown"}
)
ACCEPTABLE_USER_AGENT_POLICIES: frozenset[str] = frozenset({"nativeforge_canonical"})

#: Bridged from Gate 97's body store contract rather than restated.
RAW_PAYLOAD_POLICIES: frozenset[str] = frozenset(
    {
        "local_dev_ignored",
        "database_small_payload_only",
        "s3_compatible_configured",
        "unconfigured",
    }
)
#: The only policy a live collector may run on. Gate 141 reports it false.
LIVE_CAPABLE_PAYLOAD_POLICIES: frozenset[str] = frozenset({"s3_compatible_configured"})

PREFLIGHT_STATES: tuple[str, ...] = (
    "incomplete_configuration",
    "source_not_permitted",
    "configured_dry_run_only",
    "configured_but_unapproved",
    "activation_approved",
)

#: The only state in which a collector could run live. Nothing produces it
#: without an approval and a source that passes the allowlist.
LIVE_CAPABLE_STATES: frozenset[str] = frozenset({"activation_approved"})

#: Markers that must never appear in a preflight result.
CREDENTIAL_SHAPED_MARKERS: tuple[str, ...] = (
    "api_key=",
    "apikey=",
    "Bearer ",
    "-----BEGIN",
    "AKIA",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _norm(value: Any, vocabulary: frozenset[str], *, fallback: str) -> str:
    text = str(value or "").strip().lower()
    return text if text in vocabulary else fallback


def build_collector_preflight(
    *,
    config: dict[str, Any] | None = None,
    source_evaluation: dict[str, Any] | None = None,
    registry: dict[str, dict[str, Any]] | None = None,
    activation_approvals: Any = None,
    available_credentials: Any = None,
    terms_statuses: dict[str, str] | None = None,
    allow_fixture: bool = False,
) -> dict[str, Any]:
    """Is this collector fit to be allowed to run? Deny by default."""
    from nativeforge.services.source_monitoring_approved_source_service import (
        allowlist_invariant_failures,
        evaluate_source,
    )

    declared = dict(config or {})
    blocked: list[str] = []

    missing = [key for key in REQUIRED_CONFIG_KEYS if not declared.get(key)]
    for key in missing:
        blocked.append(f"collector_config_missing:{key}")

    source_id = str(declared.get("source_id") or "").strip()
    fetch_mode = _norm(declared.get("fetch_mode"), FETCH_MODES, fallback="dry_run")
    rate_limit = _norm(
        declared.get("rate_limit_policy"), RATE_LIMIT_POLICIES, fallback="unknown"
    )
    attribution = _norm(
        declared.get("attribution_requirement"),
        ATTRIBUTION_REQUIREMENTS,
        fallback="unknown",
    )
    user_agent = _norm(
        declared.get("user_agent_policy"), USER_AGENT_POLICIES, fallback="unknown"
    )
    payload_policy = _norm(
        declared.get("raw_payload_storage_policy"),
        RAW_PAYLOAD_POLICIES,
        fallback="unconfigured",
    )
    approval = bool(declared.get("activation_approval"))

    # -- the source itself --------------------------------------------------
    evaluation = (
        source_evaluation
        if source_evaluation is not None
        else evaluate_source(
            source_id=source_id,
            registry=registry,
            activation_approvals=activation_approvals,
            available_credentials=available_credentials,
            terms_statuses=terms_statuses,
            allow_fixture=allow_fixture,
        )
    )
    source_permitted = bool(evaluation.get("monitorable"))
    if not source_permitted:
        blocked.extend(
            f"source:{reason}" for reason in evaluation.get("blocked_reasons") or []
        )
    blocked.extend(
        f"source_invariant:{f}" for f in allowlist_invariant_failures(evaluation)
    )

    # -- each declared policy, checked --------------------------------------
    if rate_limit not in DECLARED_RATE_LIMIT_POLICIES:
        blocked.append(f"rate_limit_policy_not_declared:{rate_limit}")
    if user_agent not in ACCEPTABLE_USER_AGENT_POLICIES:
        blocked.append(f"user_agent_policy_not_acceptable:{user_agent}")
    if attribution == "unknown":
        blocked.append("attribution_requirement_is_unknown")
    attribution_verbatim = bool(declared.get("attribution_text_verbatim"))
    if attribution in ATTRIBUTION_NEEDING_VERBATIM and not attribution_verbatim:
        # Gate 94's rule, preserved: an attribution requirement is satisfied by
        # carrying the publisher's own words, not by intending to.
        blocked.append("attribution_required_but_no_verbatim_text_is_carried")

    live_requested = fetch_mode in LIVE_FETCH_MODES
    if live_requested and not approval:
        blocked.append("live_fetch_requested_without_an_activation_approval")
    if live_requested and payload_policy not in LIVE_CAPABLE_PAYLOAD_POLICIES:
        blocked.append(f"raw_payload_storage_not_live_capable:{payload_policy}")
    if live_requested and not source_permitted:
        blocked.append("live_fetch_requested_for_a_source_that_is_not_permitted")
    if approval and not source_permitted:
        blocked.append("activation_approval_does_not_clear_a_source_blocker")

    credential_required = bool(evaluation.get("credential_required"))
    credential_present = bool(declared.get("credential_present"))
    if credential_required and not credential_present:
        blocked.append("source_requires_a_credential_that_is_not_present")

    # -- the state, derived once --------------------------------------------
    if missing:
        state = "incomplete_configuration"
    elif not source_permitted:
        state = "source_not_permitted"
    elif blocked:
        state = "configured_but_unapproved"
    elif not approval:
        state = "configured_but_unapproved"
    elif not live_requested:
        state = "configured_dry_run_only"
    else:
        state = "activation_approved"

    live_capable = state in LIVE_CAPABLE_STATES and not blocked

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "state": state,
            "states": list(PREFLIGHT_STATES),
            "collector_may_run_live": live_capable,
            "required_config_keys": list(REQUIRED_CONFIG_KEYS),
            "declared_config_keys": sorted(
                key for key in REQUIRED_CONFIG_KEYS if declared.get(key)
            ),
            "missing_config_keys": sorted(missing),
            "source_id": source_id or None,
            "source_permitted": source_permitted,
            "source_state": evaluation.get("state"),
            "fetch_mode": fetch_mode,
            "live_fetch_requested": live_requested,
            "rate_limit_policy": rate_limit,
            "attribution_requirement": attribution,
            "attribution_text_verbatim": attribution_verbatim,
            "user_agent_policy": user_agent,
            "canonical_user_agent_required": True,
            "raw_payload_storage_policy": payload_policy,
            "activation_approval": approval,
            "credential_required": credential_required,
            # Presence only. No value, ever.
            "credential_present": credential_present,
            "api_key_values_reported": False,
            # Constants. Nothing here can set any of them.
            "collector_activated": False,
            "fetch_performed": False,
            "network_calls": 0,
            "source_monitoring_live": False,
            "live_source_coverage": False,
            "production_source_monitoring": False,
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def collector_preflight_invariant_failures(result: dict[str, Any]) -> list[str]:
    """What must never be true of a collector preflight result."""
    fails: list[str] = []

    state = result.get("state")
    if state not in PREFLIGHT_STATES:
        fails.append(f"state_not_recognised:{state}")

    if result.get("collector_may_run_live"):
        if state != "activation_approved":
            fails.append(f"live_capable_in_state:{state}")
        for field in (
            "source_permitted",
            "activation_approval",
            "live_fetch_requested",
        ):
            if not result.get(field):
                fails.append(f"live_capable_without:{field}")
        if result.get("blocked_reasons"):
            fails.append("live_capable_alongside_blockers")
        if result.get("rate_limit_policy") not in DECLARED_RATE_LIMIT_POLICIES:
            fails.append("live_capable_without_a_declared_rate_limit")
        if result.get("user_agent_policy") not in ACCEPTABLE_USER_AGENT_POLICIES:
            fails.append("live_capable_without_the_canonical_user_agent")
        if result.get("raw_payload_storage_policy") not in (
            LIVE_CAPABLE_PAYLOAD_POLICIES
        ):
            fails.append("live_capable_without_somewhere_for_the_bytes_to_land")
        if result.get("attribution_requirement") in ATTRIBUTION_NEEDING_VERBATIM:
            if not result.get("attribution_text_verbatim"):
                fails.append("live_capable_without_verbatim_attribution")
        if result.get("credential_required") and not result.get("credential_present"):
            fails.append("live_capable_without_a_required_credential")

    for field in (
        "collector_activated",
        "fetch_performed",
        "source_monitoring_live",
        "live_source_coverage",
        "production_source_monitoring",
        "api_key_values_reported",
    ):
        if result.get(field):
            fails.append(f"claimed:{field}")
    if result.get("network_calls"):
        fails.append("nonzero:network_calls")

    rendered = json.dumps(result)
    for marker in CREDENTIAL_SHAPED_MARKERS:
        if marker in rendered:
            fails.append(f"result_carries_a_credential_shaped_marker:{marker}")

    if not result.get("collector_may_run_live") and not result.get("blocked_reasons"):
        if state != "configured_dry_run_only":
            fails.append("not_live_capable_and_nothing_blocked_it")

    return fails
