"""Gate 143B: which sources may be monitored, and which may not, and why.

## What was missing

`live_network_guard_service` decides about **one fetch**, given facts a caller
supplies. Nothing walked the registry and produced the set of sources that would
pass. This does that — and it asks that guard rather than answering again, so
there is one permission model and not two.

## Deny by default falls out of the data

The registry has **no terms column**. `fixtures/source_ingestion/
NF_SOURCE_SEED_2026.csv` carries a url, a tier, an adapter key, an access
posture, a health status and a resolver status — and nothing about what any
source's terms of use say.

So a row's terms status is `UNKNOWN`, and `live_network_guard_service` already
puts `UNKNOWN` in `TERMS_BLOCKING`. Deny by default is not a rule imposed on top
of the registry here; it is what the registry actually supports. A future gate
that adds a terms column has to fill it in per source, reviewed, before anything
changes.

## Six states, because "blocked" hides five different situations

```text
registry_known        in the 177 seed rows. Says nothing about permission.
fixture_allowed       an nf-fixture- id, hermetic tests only, never a host.
terms_blocked         TERMS_REVIEW_REQUIRED or UNKNOWN
human_review_blocked  HUMAN_REVIEW_ONLY — a person must look first
api_key_missing       a credential nobody has
activation_approved   the only state in which monitoring could begin.
                      Nothing produces it, and nothing here can.
```

An operator asking "why can't we monitor this" gets a different answer for each,
and each has a different fix.

## Nothing is fetched

No URL is opened, no robots.txt is read, no DNS is resolved. The url column is
parsed for a **host**, which is used to match the terms review queue's entries,
and is otherwise carried as text. `fetch_performed: False` is on every result
and an invariant fails if it is ever true.
"""

from __future__ import annotations

import csv
import json
from typing import Any
from urllib.parse import urlsplit

SCHEMA_VERSION = "nf_source_monitoring_approved_source_v1"

#: Hermetic-only ids. A fixture source is never a real host and may only be
#: used by a test - `fixture_allowed` is deliberately not `activation_approved`.
FIXTURE_SOURCE_PREFIX = "nf-fixture-"

REGISTRY_KNOWN = "registry_known"
FIXTURE_ALLOWED = "fixture_allowed"
TERMS_BLOCKED = "terms_blocked"
HUMAN_REVIEW_BLOCKED = "human_review_blocked"
API_KEY_MISSING = "api_key_missing"
ACTIVATION_APPROVED = "activation_approved"
UNKNOWN_SOURCE = "unknown_source"

EVALUATION_STATES: tuple[str, ...] = (
    UNKNOWN_SOURCE,
    REGISTRY_KNOWN,
    FIXTURE_ALLOWED,
    TERMS_BLOCKED,
    HUMAN_REVIEW_BLOCKED,
    API_KEY_MISSING,
    ACTIVATION_APPROVED,
)

#: The only state in which live monitoring could begin. Nothing in this module
#: produces it: it needs an approval this module cannot manufacture.
MONITORABLE_STATES: frozenset[str] = frozenset({ACTIVATION_APPROVED})

#: States that mean a person has to act before anything else can.
BLOCKED_STATES: frozenset[str] = frozenset(
    {UNKNOWN_SOURCE, TERMS_BLOCKED, HUMAN_REVIEW_BLOCKED, API_KEY_MISSING}
)

#: Domains that need a credential AND a role nobody has. Matched by DOMAIN,
#: not by exact host: see `_matches_domain` below.
CREDENTIAL_REQUIRED_DOMAINS: frozenset[str] = frozenset({"sam.gov"})

#: Domains whose terms pages are client-rendered and served no policy text. Not
#: "the terms allow it" and not "the terms forbid it" - nobody could read them,
#: which is why a human has to.
#:
#: By domain, because the registry has 128 distinct hosts across 177 rows and
#: `simpler.grants.gov`, `www.grants.gov` and `grants.gov` are one publisher.
#: An exact-match list missed four grants.gov rows on the first probe.
HUMAN_REVIEW_DOMAINS: frozenset[str] = frozenset(
    {
        "grants.gov",
        "regulations.gov",
        "usaspending.gov",
        "reporter.nih.gov",
    }
)

#: Access postures that are not a public source, whatever the terms say.
NON_PUBLIC_POSTURES: frozenset[str] = frozenset({"login", "members"})

#: Resolver statuses that mean the url does not reach a source.
UNUSABLE_RESOLVER_STATUSES: frozenset[str] = frozenset({"dead", "login"})

#: What every evaluation carries. Declared so a test asserts a real result
#: against it rather than against a reader's memory.
EVALUATION_FIELDS: tuple[str, ...] = (
    "source_id",
    "state",
    "monitorable",
    "registry_known",
    "terms_status",
    "human_review_required",
    "credential_required",
    "access_posture",
    "resolver_url_status",
    "source_health_status",
    "activation_approved",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _host(url: Any) -> str:
    try:
        return (urlsplit(str(url or "")).hostname or "").lower()
    except ValueError:
        return ""


def _matches_domain(host: str, domains: frozenset[str]) -> str | None:
    """Which listed domain does this host belong to, if any?

    `simpler.grants.gov` belongs to `grants.gov`; `notgrants.gov` does not.
    The label boundary matters - a suffix test without it would match
    `evilgrants.gov` too.
    """
    text = str(host or "").strip().lower().rstrip(".")
    if not text:
        return None
    for domain in domains:
        if text == domain or text.endswith(f".{domain}"):
            return domain
    return None


def _normalise_id(source_id: Any) -> str:
    """`nf-seed-2026-fed-001` and `nf:source:nf-seed-2026-fed-001` are one row."""
    text = str(source_id or "").strip()
    if text.startswith("nf:source:"):
        return text[len("nf:source:") :]
    return text


def load_registry_rows() -> dict[str, dict[str, Any]]:
    """The 177 seed rows, by seed id. Reads a file; opens no socket.

    A bare `except` here would be the Gate 140 defect again - the watchlist's
    registry check swallowed a wrong function name and refused every source
    while looking like a working guard. This raises.
    """
    from nativeforge.services.source_ingestion_seed_schema_service import (
        seed_csv_path,
    )

    path = seed_csv_path()
    rows: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            seed_id = str(row.get("seed_id") or "").strip()
            if seed_id:
                rows[seed_id] = dict(row)
    return rows


#: Terms statuses a completed review can produce. Bridged from
#: `live_network_guard_service` rather than restated, so the two cannot drift
#: about which of them permits anything.
def _permitting_terms_statuses() -> frozenset[str]:
    from nativeforge.services.live_network_guard_service import TERMS_NON_BLOCKING

    return TERMS_NON_BLOCKING


def _terms_status_for(host: str) -> tuple[str, list[str]]:
    """What is known about this host's terms. Usually nothing.

    The registry has no terms column, so `UNKNOWN` is the honest answer for
    every source that is not on one of the two named lists - and
    `live_network_guard_service` already classifies `UNKNOWN` as blocking.
    """
    domain = _matches_domain(host, HUMAN_REVIEW_DOMAINS)
    if domain:
        return "HUMAN_REVIEW_ONLY", [
            "terms_page_is_client_rendered_and_served_no_policy_text:" + domain
        ]
    return "UNKNOWN", ["registry_has_no_terms_column_for_this_source"]


def evaluate_source(
    *,
    source_id: Any,
    registry: dict[str, dict[str, Any]] | None = None,
    activation_approvals: Any = None,
    available_credentials: Any = None,
    terms_statuses: dict[str, str] | None = None,
    allow_fixture: bool = False,
) -> dict[str, Any]:
    """May this source be monitored? Deny by default. Fetches nothing.

    ``activation_approvals`` and ``terms_statuses`` are injectable so
    `activation_approved` is a REACHABLE state. They are also the shape the
    real process has: a human reviews a source's terms and records the result,
    and somebody approves that source for activation.

    Runtime supplies neither, so runtime gets `UNKNOWN` for every row and
    `UNKNOWN` is blocking.
    """
    identifier = _normalise_id(source_id)
    approvals = {str(a).strip() for a in (activation_approvals or []) if str(a).strip()}
    credentials = {
        str(c).strip().lower() for c in (available_credentials or []) if str(c).strip()
    }
    blocked: list[str] = []

    # -- a fixture source, for hermetic tests only --------------------------
    if identifier.startswith(FIXTURE_SOURCE_PREFIX):
        if not allow_fixture:
            blocked.append("fixture_sources_are_not_permitted_outside_hermetic_tests")
        else:
            # Out of scope rather than refused: a fixture proves the evaluation
            # path and is never a host anything could monitor.
            blocked.append("fixture_sources_are_never_monitored")
        return _result(
            source_id=identifier,
            state=FIXTURE_ALLOWED if allow_fixture else UNKNOWN_SOURCE,
            registry_known=False,
            terms_status="not_applicable_fixture",
            human_review_required=False,
            credential_required=False,
            access_posture="fixture",
            resolver_url_status="fixture",
            source_health_status="fixture",
            source_url=None,
            host="",
            activation_approved=False,
            blocked=blocked,
        )

    rows = registry if registry is not None else load_registry_rows()
    row = rows.get(identifier)
    if row is None:
        return _result(
            source_id=identifier,
            state=UNKNOWN_SOURCE,
            registry_known=False,
            terms_status="UNKNOWN",
            human_review_required=False,
            credential_required=False,
            access_posture=None,
            resolver_url_status=None,
            source_health_status=None,
            source_url=None,
            host="",
            activation_approved=False,
            blocked=["source_id_is_not_in_the_source_registry"],
        )

    url = row.get("source_url")
    host = _host(url)
    reviewed = (terms_statuses or {}).get(identifier)
    if reviewed:
        # A recorded review wins over "nobody has looked" - but only for the
        # statuses the guard already treats as non-blocking. A review that came
        # back TERMS_REVIEW_REQUIRED still blocks.
        terms = str(reviewed).strip()
        terms_reasons = (
            []
            if terms in _permitting_terms_statuses()
            else [f"recorded_terms_review_does_not_permit_collection:{terms}"]
        )
    else:
        terms, terms_reasons = _terms_status_for(host)
    posture = str(row.get("access_posture_hint") or "unknown").strip().lower()
    resolver = str(row.get("resolver_url_status") or "unknown").strip().lower()
    health = str(row.get("source_health_status") or "unknown").strip().lower()

    credential_domain = _matches_domain(host, CREDENTIAL_REQUIRED_DOMAINS)
    credential_required = credential_domain is not None
    credential_present = credential_required and credential_domain in credentials
    human_review = terms == "HUMAN_REVIEW_ONLY"

    if terms not in _permitting_terms_statuses():
        blocked.extend(terms_reasons)

    if credential_required and not credential_present:
        blocked.append("source_requires_an_api_key_and_a_role_that_are_not_present")
    if posture in NON_PUBLIC_POSTURES:
        blocked.append(f"access_posture_is_not_public:{posture}")
    if resolver in UNUSABLE_RESOLVER_STATUSES:
        blocked.append(f"resolver_url_status_is_not_usable:{resolver}")

    approved = identifier in approvals or row.get("canonical_source_id") in approvals

    # -- the state, derived once, most specific first -----------------------
    if credential_required and not credential_present:
        state = API_KEY_MISSING
    elif human_review:
        state = HUMAN_REVIEW_BLOCKED
    elif terms not in _permitting_terms_statuses():
        state = TERMS_BLOCKED
    elif approved and not blocked:
        state = ACTIVATION_APPROVED
    else:
        state = REGISTRY_KNOWN

    if state == ACTIVATION_APPROVED and blocked:
        # Belt and braces: an approval never overrides a blocker.
        state = REGISTRY_KNOWN
        blocked.append("activation_approval_does_not_clear_a_blocker")
    if not approved and state not in BLOCKED_STATES:
        blocked.append("no_activation_approval_for_this_source")

    return _result(
        source_id=identifier,
        state=state,
        registry_known=True,
        terms_status=terms,
        human_review_required=human_review,
        credential_required=credential_required,
        access_posture=posture,
        resolver_url_status=resolver,
        source_health_status=health,
        source_url=url,
        host=host,
        activation_approved=approved,
        blocked=blocked,
    )


def _result(
    *,
    source_id: str,
    state: str,
    registry_known: bool,
    terms_status: str,
    human_review_required: bool,
    credential_required: bool,
    access_posture: Any,
    resolver_url_status: Any,
    source_health_status: Any,
    source_url: Any,
    host: str,
    activation_approved: bool,
    blocked: list[str],
) -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_id": source_id,
            "state": state,
            "states": list(EVALUATION_STATES),
            "monitorable": state in MONITORABLE_STATES and not blocked,
            "registry_known": registry_known,
            "terms_status": terms_status,
            "human_review_required": human_review_required,
            "credential_required": credential_required,
            "access_posture": access_posture,
            "resolver_url_status": resolver_url_status,
            "source_health_status": source_health_status,
            # The url and host are carried as TEXT. Neither was opened.
            "source_url": source_url,
            "source_host": host,
            "activation_approved": activation_approved,
            # Constants. Nothing in this module can set any of them.
            "fetch_performed": False,
            "robots_fetched": False,
            "dns_resolved": False,
            "network_calls": 0,
            "collector_activated": False,
            "source_monitoring_live": False,
            "live_source_coverage": False,
            "api_key_values_reported": False,
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def evaluate_registry(
    *,
    registry: dict[str, dict[str, Any]] | None = None,
    activation_approvals: Any = None,
    available_credentials: Any = None,
    terms_statuses: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Every registry row, classified. Fetches nothing."""
    rows = registry if registry is not None else load_registry_rows()
    evaluations = [
        evaluate_source(
            source_id=seed_id,
            registry=rows,
            activation_approvals=activation_approvals,
            available_credentials=available_credentials,
            terms_statuses=terms_statuses,
        )
        for seed_id in sorted(rows)
    ]

    by_state: dict[str, int] = dict.fromkeys(EVALUATION_STATES, 0)
    for evaluation in evaluations:
        by_state[evaluation["state"]] = by_state.get(evaluation["state"], 0) + 1

    monitorable = [e["source_id"] for e in evaluations if e["monitorable"]]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "registry_row_count": len(rows),
            "evaluated_count": len(evaluations),
            "by_state": by_state,
            "monitorable_source_ids": sorted(monitorable),
            "monitorable_count": len(monitorable),
            "terms_blocked_count": by_state.get(TERMS_BLOCKED, 0),
            "human_review_blocked_count": by_state.get(HUMAN_REVIEW_BLOCKED, 0),
            "api_key_missing_count": by_state.get(API_KEY_MISSING, 0),
            "activation_approved_count": by_state.get(ACTIVATION_APPROVED, 0),
            # Constants.
            "fetch_performed": False,
            "network_calls": 0,
            "collector_activated": False,
            "source_monitoring_live": False,
            "live_source_coverage": False,
            "blocked_reasons": [],
        }
    )


def allowlist_invariant_failures(result: dict[str, Any]) -> list[str]:
    """What must never be true of an allowlist result."""
    fails: list[str] = []

    state = result.get("state")
    if state is not None and state not in EVALUATION_STATES:
        fails.append(f"state_not_recognised:{state}")

    if result.get("monitorable"):
        if state != ACTIVATION_APPROVED:
            fails.append(f"monitorable_in_state:{state}")
        if result.get("blocked_reasons"):
            fails.append("monitorable_alongside_blockers")
        if result.get("human_review_required"):
            fails.append("monitorable_while_a_human_must_review_it")
        if result.get("terms_status") not in _permitting_terms_statuses():
            fails.append(f"monitorable_with_terms:{result.get('terms_status')}")
        if result.get("credential_required") and state != ACTIVATION_APPROVED:
            fails.append("monitorable_without_the_required_credential")

    # A fixture source may never be treated as a real one.
    if state == FIXTURE_ALLOWED and result.get("monitorable"):
        fails.append("a_fixture_source_was_marked_monitorable")

    for field in (
        "fetch_performed",
        "robots_fetched",
        "dns_resolved",
        "collector_activated",
        "source_monitoring_live",
        "live_source_coverage",
        "api_key_values_reported",
    ):
        if result.get(field):
            fails.append(f"claimed:{field}")
    if result.get("network_calls"):
        fails.append("nonzero:network_calls")

    for evaluation in result.get("evaluations") or []:
        fails.extend(allowlist_invariant_failures(evaluation))

    if state is not None and not result.get("monitorable"):
        if not result.get("blocked_reasons"):
            fails.append("not_monitorable_and_nothing_blocked_it")

    return fails
