"""The canonical enforcement path for a live source request (Gate 163).

Gate 77B put four Grants.gov hosts behind an environment flag. That flag is a
legitimate defence and stays enforced: this module makes it
AUTHORIZATION-AWARE rather than routing around it.

```python
grants_gov_flag_blocked = host in GRANTS_GOV_HOSTS and not live_network_allowed()
```

became: blocked unless the flag is set **or** this exact request carries a
warrant that a recorded, signed authorization supports.

## Two warrant kinds, and they are not interchangeable

```text
                        robots_preflight        source_collection
path                    exactly /robots.txt     the source endpoint
method                  GET                     the declared method
live-fetch opt-in       NOT required            REQUIRED
terms signed            required                required
review signed           required                required
activation signed       required                required
attribution satisfied   required                required
robots prerequisite     n/a (this IS it)        required
```

A `robots_preflight` warrant presented for a collection path is refused by
path, and a `source_collection` warrant is refused without the opt-in. The
distinction is enforced per-field, not by trusting a label.

## Bypass is structurally impossible, not discouraged

`live_source_transport_service.build_live_transport` does not accept a
pre-validated warrant. It calls `assert_live_request_permitted` itself, so
there is no code path that produces a live transport without enforcement. A
caller who wants to skip the guard has to write their own HTTP client, which
the hermetic network scan would find as an unapproved import.

That is why the warrant is minted here and nowhere else, and why the minting
function has no "trust me" parameter.

## The environment flag survives as a legacy override

`ENV_ALLOW_LIVE_NETWORK` still works for whatever older paths depend on it. It
is NOT required for the Gate 163 approved-source path, is never set by this
code, and cannot broaden permission to a second source: every check below is
per-source and per-host regardless of the flag.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any
from urllib.parse import urlsplit

SCHEMA_VERSION = "nf_source_live_warrant_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

WARRANT_ROBOTS_PREFLIGHT = "robots_preflight"
WARRANT_SOURCE_COLLECTION = "source_collection"

WARRANT_KINDS: tuple[str, ...] = (
    WARRANT_ROBOTS_PREFLIGHT,
    WARRANT_SOURCE_COLLECTION,
)

#: The ONE source this gate authorized. A constant, not an argument: widening
#: it is an edit somebody reviews.
AUTHORIZED_SOURCE_IDS: frozenset[str] = frozenset(
    {"nf-seed-2026-api-grants-gov-search2"}
)

#: The only path a robots preflight may request.
ROBOTS_PATH = "/robots.txt"

#: Refusal reasons. Each names one unmet condition, so a refusal is always
#: diagnosable rather than a bare no.
REFUSE_NO_WARRANT_KIND = "warrant_kind_missing_or_outside_vocabulary"
REFUSE_NO_SOURCE_ID = "no_authorized_source_id_on_the_warrant"
REFUSE_SOURCE_NOT_AUTHORIZED = "source_id_is_not_an_authorized_source"
REFUSE_HOST_MISMATCH = "request_host_does_not_match_the_recorded_source_authority"
REFUSE_NOT_HTTPS = "only_https_may_be_dispatched"
REFUSE_NO_AUTHORIZATION = "no_recorded_authorization_for_this_source"
REFUSE_TERMS = "terms_decision_is_not_signed_and_permitting"
REFUSE_REVIEW = "human_review_decision_is_not_signed_and_permitting"
REFUSE_ACTIVATION = "activation_approval_is_not_signed_and_permitting"
REFUSE_ATTRIBUTION = "required_attribution_is_not_satisfied"
REFUSE_ROBOTS = "robots_prerequisite_is_not_satisfied"
REFUSE_PREFLIGHT_PATH = "a_robots_preflight_may_request_only_/robots.txt"
REFUSE_PREFLIGHT_METHOD = "a_robots_preflight_must_be_a_GET"
REFUSE_NO_OPT_IN = "live_fetch_is_not_opted_in_for_this_source"
REFUSE_NO_CONNECTION = "no_connection_supplied_so_nothing_could_be_verified"

#: The facts a COLLECTION warrant needs, by name. A preflight needs the three
#: signed decisions and the attribution, but not robots - it is the thing that
#: resolves robots.
COLLECTION_REQUIRED_FACTS: tuple[str, ...] = (
    "terms_status",
    "human_review_status",
    "activation_status",
    "attribution_status",
    "robots_status",
)

PREFLIGHT_REQUIRED_FACTS: tuple[str, ...] = (
    "terms_status",
    "human_review_status",
    "activation_status",
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _host_of(url: Any) -> str:
    try:
        return (urlsplit(str(url)).hostname or "").lower()
    except ValueError:
        return ""


def _path_of(url: Any) -> str:
    try:
        return urlsplit(str(url)).path or "/"
    except ValueError:
        return ""


class LiveRequestRefused(RuntimeError):
    """Raised instead of returning a sentinel.

    There is no useful partial answer to a request we were not allowed to
    make, and a silently empty result would look like a source with no data.
    Gate 77B's own guard raises for the same reason.
    """

    def __init__(self, reasons: list[str], *, warrant: dict[str, Any]) -> None:
        super().__init__("; ".join(reasons))
        self.reasons = list(reasons)
        self.warrant = dict(warrant)


#: Facts whose permitting value must also carry a signature. A decision is
#: evidence only if somebody is accountable for it.
SIGNED_FACTS: frozenset[str] = frozenset(
    {"terms_status", "human_review_status", "activation_status"}
)

FACT_REFUSALS = {
    "terms_status": REFUSE_TERMS,
    "human_review_status": REFUSE_REVIEW,
    "activation_status": REFUSE_ACTIVATION,
    "attribution_status": REFUSE_ATTRIBUTION,
    "robots_status": REFUSE_ROBOTS,
}


def required_facts_for(warrant_kind: Any) -> tuple[str, ...]:
    """Which facts this warrant kind needs. One definition, two callers.

    The pure check below and the decision dict both report this. A second
    literal in either place is a pair of lists that can disagree.
    """
    kind = str(warrant_kind or "").strip()
    return (
        PREFLIGHT_REQUIRED_FACTS
        if kind == WARRANT_ROBOTS_PREFLIGHT
        else COLLECTION_REQUIRED_FACTS
    )


def fact_refusals(
    *,
    facts: dict[str, Any] | None = None,
    warrant_kind: Any = None,
    opted_in: bool = False,
) -> list[str]:
    """Which required facts refuse this warrant kind. Pure.

    Extracted from `evaluate_live_request` so the `:unsigned` branch is
    reachable without a database. Every route into `facts` is the resolver
    reading the decision table, and migration 0048 makes an unsigned approved
    decision unwritable - so this branch guards against something the schema
    already prevents. Correct defence in depth, and exactly the kind of code
    that stays unproven: an unreachable refusal is unfalsifiable.

    One copy of the rule. `evaluate_live_request` calls this rather than
    holding its own version.
    """
    resolved = facts or {}
    kind = str(warrant_kind or "").strip()
    reasons: list[str] = []

    for name in required_facts_for(kind):
        refusal = FACT_REFUSALS[name]
        fact = resolved.get(name) or {}
        if fact.get("fact_status") != "recorded":
            reasons.append(f"{refusal}:{fact.get('fact_status') or 'missing'}")
            continue
        # A decision fact must also be attributable. An approval nobody signed
        # is not evidence, which the fact model enforces and this re-checks at
        # the point of dispatch.
        if name in SIGNED_FACTS and (
            not fact.get("recorded_by") or not fact.get("recorded_at")
        ):
            reasons.append(f"{refusal}:unsigned")

    # A preflight does NOT need the opt-in. A collection does.
    if kind == WARRANT_SOURCE_COLLECTION and not opted_in:
        reasons.append(REFUSE_NO_OPT_IN)

    return reasons


def evaluate_live_request(
    *,
    warrant_kind: Any = None,
    authorized_source_id: Any = None,
    request_url: Any = None,
    method: str = "GET",
    connection: Any = None,
    organization_id: Any = None,
    now: Any = None,
) -> dict[str, Any]:
    """Every condition, measured. Returns a decision; raises nothing.

    Separate from `assert_live_request_permitted` so the negative cases can be
    enumerated in a verifier without catching exceptions, and so the reasons
    are inspectable.
    """
    reasons: list[str] = []

    kind = str(warrant_kind or "").strip()
    if kind not in WARRANT_KINDS:
        reasons.append(REFUSE_NO_WARRANT_KIND)

    source_id = str(authorized_source_id or "").strip()
    if not source_id:
        reasons.append(REFUSE_NO_SOURCE_ID)
    elif source_id not in AUTHORIZED_SOURCE_IDS:
        reasons.append(f"{REFUSE_SOURCE_NOT_AUTHORIZED}:{source_id}")

    url = str(request_url or "")
    host = _host_of(url)
    path = _path_of(url)
    if urlsplit(url).scheme.lower() != "https":
        reasons.append(REFUSE_NOT_HTTPS)

    if connection is None:
        reasons.append(REFUSE_NO_CONNECTION)

    # ---- the recorded source authority -------------------------------
    registry_host = ""
    registry_path = ""
    try:
        from nativeforge.services.source_monitoring_approved_source_service import (
            load_registry_rows,
        )

        row = load_registry_rows().get(source_id) or {}
        registry_host = _host_of(row.get("source_url"))
        registry_path = _path_of(row.get("source_url"))
    except Exception:  # noqa: BLE001 - an unreadable registry authorizes nothing
        row = {}

    if not registry_host:
        reasons.append(REFUSE_NO_AUTHORIZATION)
    elif host != registry_host:
        reasons.append(f"{REFUSE_HOST_MISMATCH}:{host}!={registry_host}")

    # ---- the warrant kind's own shape --------------------------------
    if kind == WARRANT_ROBOTS_PREFLIGHT:
        if path != ROBOTS_PATH:
            reasons.append(f"{REFUSE_PREFLIGHT_PATH}:{path}")
        if str(method).upper() != "GET":
            reasons.append(f"{REFUSE_PREFLIGHT_METHOD}:{method}")
    elif (
        kind == WARRANT_SOURCE_COLLECTION and registry_path and (path != registry_path)
    ):
        reasons.append(
            f"collection_path_does_not_match_the_source:{path}!={registry_path}"
        )

    # ---- the recorded facts ------------------------------------------
    facts: dict[str, Any] = {}
    opted_in = False
    if connection is not None and source_id:
        try:
            from nativeforge.services.source_authorization_fact_resolver_service import (  # noqa: E501
                resolve_source_authorization_facts,
            )

            resolution = resolve_source_authorization_facts(
                connection=connection,
                organization_id=organization_id,
                source_id=source_id,
                now=now or dt.datetime.now(dt.UTC),
            )
            facts = resolution.get("resolved_facts") or {}
        except Exception:  # noqa: BLE001
            reasons.append(REFUSE_NO_AUTHORIZATION)

        try:
            from nativeforge.services.source_live_fetch_opt_in_service import (
                is_live_fetch_opted_in,
            )

            opted_in = bool(
                is_live_fetch_opted_in(
                    connection=connection,
                    organization_id=organization_id,
                    source_id=source_id,
                )
            )
        except Exception:  # noqa: BLE001 - absent opt-in is not opted in
            opted_in = False

    reasons.extend(fact_refusals(facts=facts, warrant_kind=kind, opted_in=opted_in))

    permitted = not reasons

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "permitted": permitted,
            "warrant_kind": kind or None,
            "authorized_source_id": source_id or None,
            "request_url": url or None,
            "request_host": host or None,
            "request_path": path or None,
            "request_method": str(method).upper(),
            "recorded_source_host": registry_host or None,
            "host_matches_the_recorded_authority": bool(
                host and registry_host and host == registry_host
            ),
            "required_facts": list(required_facts_for(kind)),
            "fact_statuses": {
                name: (facts.get(name) or {}).get("fact_status")
                for name in FACT_REFUSALS
            },
            "live_fetch_opted_in": opted_in,
            "live_fetch_opt_in_required": kind == WARRANT_SOURCE_COLLECTION,
            "refusal_reasons": sorted(set(reasons)),
            # Reported so it is visible that the legacy flag was NOT what
            # permitted this - and never silently set by this code.
            "legacy_env_flag_consulted": False,
            "legacy_env_flag_required": False,
            "authorized_source_ids": sorted(AUTHORIZED_SOURCE_IDS),
        }
    )


def assert_live_request_permitted(
    *,
    warrant_kind: Any = None,
    authorized_source_id: Any = None,
    request_url: Any = None,
    method: str = "GET",
    connection: Any = None,
    organization_id: Any = None,
    now: Any = None,
) -> dict[str, Any]:
    """The canonical enforcement path. Raises unless every condition holds.

    There is deliberately no parameter that skips a check and no way to hand
    in a pre-validated warrant: `build_live_transport` calls this itself, so a
    live transport cannot exist without having passed through here.
    """
    decision = evaluate_live_request(
        warrant_kind=warrant_kind,
        authorized_source_id=authorized_source_id,
        request_url=request_url,
        method=method,
        connection=connection,
        organization_id=organization_id,
        now=now,
    )
    if not decision["permitted"]:
        raise LiveRequestRefused(decision["refusal_reasons"], warrant=decision)
    return decision


def warrant_invariant_failures(decision: dict[str, Any]) -> list[str]:
    """Refuse a warrant decision that permitted without every condition."""
    fails: list[str] = []

    if decision.get("permitted") and decision.get("refusal_reasons"):
        fails.append("permitted_alongside_refusal_reasons")
    if not decision.get("permitted") and not decision.get("refusal_reasons"):
        fails.append("refused_without_naming_a_reason")

    if decision.get("warrant_kind") not in (None, *WARRANT_KINDS):
        fails.append(f"warrant_kind_outside_vocabulary:{decision.get('warrant_kind')}")

    if decision.get("permitted"):
        source_id = decision.get("authorized_source_id")
        if source_id not in AUTHORIZED_SOURCE_IDS:
            fails.append(f"permitted_an_unauthorized_source:{source_id}")
        if not decision.get("host_matches_the_recorded_authority"):
            fails.append("permitted_a_host_that_is_not_the_recorded_authority")
        statuses = decision.get("fact_statuses") or {}
        for name in decision.get("required_facts") or ():
            if statuses.get(name) != "recorded":
                fails.append(f"permitted_without_the_fact:{name}")
        if decision.get("live_fetch_opt_in_required") and not decision.get(
            "live_fetch_opted_in"
        ):
            fails.append("permitted_a_collection_without_the_opt_in")
        if decision.get("warrant_kind") == WARRANT_ROBOTS_PREFLIGHT:
            if decision.get("request_path") != ROBOTS_PATH:
                fails.append("permitted_a_preflight_for_another_path")
            if decision.get("request_method") != "GET":
                fails.append("permitted_a_preflight_that_is_not_a_GET")

    # The legacy flag must never be the thing that permitted a Gate 163 path.
    if decision.get("legacy_env_flag_required"):
        fails.append("the_legacy_env_flag_was_required")

    return sorted(set(fails))
