"""Global live-network guard (Gate 94B).

Every outbound request in ``src/nativeforge`` passes through here first. The
guard decides; it never fetches.

## Deny by default

``allow_live_fetch`` defaults to ``False``. Every status defaults to its
blocking member. An unrecognised value resolves to the blocking member of its
vocabulary rather than to a pass, so a typo blocks and a new status nobody has
taught the guard about blocks.

The allowed set is derived from satisfied requirements. It is never computed by
subtracting blockers from a permissive default — the Gate 79B rule, applied to
the last thing in the codebase that could still reach the internet.

## Purpose, because not every request is a collection

Gate 94A found six egress sites, and two of them are not source collection at
all: a Slack operational alert and an OIDC JWKS fetch. Asking whether a JWKS
URL has cleared ``TERMS_REVIEW_REQUIRED`` is a category error, and a guard that
demanded it would either block identity verification forever or be given a
bypass — and a bypass is how this problem started.

So each purpose carries its own requirements:

``source_collection``       terms, activation, collector, robots, credential
``source_discovery``        terms and robots; no collector needs to be active
``identity_verification``   https, and a configured issuer
``operational_alert``       explicit live mode and a configured endpoint

Deny by default applies to all four. A purpose outside the vocabulary blocks
with no requirements satisfiable, which is the only safe answer to "I want to
make a request for a reason you have never heard of".

## Nobody self-exempts

The Gate 93 defect was a caller declaring a requirement ``not_required`` when
its own collector type created that requirement. Here the requirement set is
derived from ``purpose`` and ``collector_type`` — both structural — and the
caller supplies only *evidence* that a requirement is met. There is no input
that means "skip this one".

``allow_live_fetch=True`` is necessary but never sufficient: it is one input
among many and cannot carry a decision on its own.

## Robots failure is not permission

``robots_status`` distinguishes what the old fetcher collapsed:

```text
allowed            robots.txt fetched and permits this path
disallowed         robots.txt fetched and forbids it
absent             404 — conventionally no restrictions
fetch_failed       timeout, 5xx, connection error
unknown            not checked
```

Only ``allowed`` and ``absent`` permit a crawl. ``fetch_failed`` blocks: a host
whose robots.txt times out is a host under load, which is precisely when a
crawler should not proceed.

## Wrapping Gate 77B, not replacing it

For Grants.gov the guard calls Gate 77B's ``assert_live_network_allowed``,
which raises unless ``NATIVEFORGE_ALLOW_LIVE_GRANTS_GOV_TESTS=1``. That flag
stays authoritative and this guard only adds requirements on top. There is no
path through this module that reaches Grants.gov with the flag unset.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlsplit

from nativeforge.services.hermetic_test_guard_service import (
    LiveNetworkBlockedError,
    live_network_allowed,
)
from nativeforge.services.nativeforge_user_agent_service import (
    NATIVEFORGE_USER_AGENT,
)
from nativeforge.services.nativeforge_user_agent_service import (
    user_agent_violations as canonical_user_agent_violations,
)
from nativeforge.services.source_crawler_governance_service import (
    BLACKLISTED_HOSTS,
    CIRCUIT_BREAKER_CONSECUTIVE_FAILURES,
    MIN_REQUEST_INTERVAL_SECONDS,
    PER_HOST_CONCURRENCY,
    evaluate_fetch_permission,
)

SCHEMA_VERSION = "nf_live_network_guard_v1"

PURPOSES = frozenset(
    {
        "source_collection",
        "source_discovery",
        "identity_verification",
        "operational_alert",
    }
)

# Purposes that put a crawler on somebody else's host.
CRAWLING_PURPOSES = frozenset({"source_collection", "source_discovery"})

DECISION_STATUSES = frozenset(
    {
        "allowed",
        "blocked",
        "requires_human_review",
        "unknown",
    }
)

# The single permitting member, so the allowed set is one named value.
PERMITTING_STATUSES = frozenset({"allowed"})

TERMS_BLOCKING = frozenset({"TERMS_REVIEW_REQUIRED", "UNKNOWN"})
TERMS_HUMAN_ONLY = frozenset({"HUMAN_REVIEW_ONLY"})
TERMS_NON_BLOCKING = frozenset({"NO_REVIEW_REQUIRED", "ATTRIBUTION_REQUIRED"})
ALL_TERMS_STATUSES = TERMS_BLOCKING | TERMS_HUMAN_ONLY | TERMS_NON_BLOCKING

ACTIVATION_STATUSES = frozenset(
    {
        "activation_allowed",
        "activation_blocked",
        "activation_requires_human_review",
        "activation_unknown",
    }
)
ACTIVATION_SATISFYING = frozenset({"activation_allowed"})

COLLECTOR_STATUSES = frozenset({"not_active", "activating", "active", "halted"})
COLLECTOR_SATISFYING = frozenset({"active"})

ROBOTS_STATUSES = frozenset(
    {"allowed", "disallowed", "absent", "fetch_failed", "unknown"}
)
# 404 conventionally means no restrictions. A timeout means we do not know.
ROBOTS_SATISFYING = frozenset({"allowed", "absent"})

CREDENTIAL_STATUSES = frozenset(
    {"present_and_valid", "missing", "expired", "not_required", "unknown"}
)
CREDENTIAL_SATISFYING = frozenset({"present_and_valid", "not_required"})

ATTRIBUTION_STATUSES = frozenset(
    {"present_and_verbatim", "missing", "altered", "not_required", "unknown"}
)
ATTRIBUTION_SATISFYING = frozenset({"present_and_verbatim", "not_required"})

RATE_LIMIT_STATUSES = frozenset({"policy_declared", "missing", "unknown"})
RATE_LIMIT_SATISFYING = frozenset({"policy_declared"})

USER_AGENT_STATUSES = frozenset(
    {"canonical", "non_canonical", "forbidden_ai_crawler", "not_required", "unknown"}
)

HTTP_METHODS = frozenset({"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"})

CREDENTIALED_COLLECTOR_TYPES = frozenset({"public_api_with_key", "authenticated_feed"})

# Requirements each purpose imposes. Structural: the caller does not choose.
PURPOSE_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "source_collection": (
        "live_fetch_opt_in",
        "https_scheme",
        "host_permitted",
        "user_agent_canonical",
        "rate_limit_policy",
        "terms_cleared",
        "activation_allowed",
        "collector_active",
        "robots_permits",
        "credential",
    ),
    "source_discovery": (
        "live_fetch_opt_in",
        "https_scheme",
        "host_permitted",
        "user_agent_canonical",
        "rate_limit_policy",
        "terms_cleared",
        "robots_permits",
    ),
    "identity_verification": (
        "live_fetch_opt_in",
        "https_scheme",
        "host_permitted",
        "issuer_configured",
    ),
    "operational_alert": (
        "live_fetch_opt_in",
        "https_scheme",
        "host_permitted",
        "endpoint_configured",
    ),
}

# Hosts that route through Gate 77B's hermetic guard rather than this one.
GRANTS_GOV_HOSTS = frozenset(
    {"api.grants.gov", "api.staging.grants.gov", "www.grants.gov", "grants.gov"}
)


class LiveNetworkPermissionError(RuntimeError):
    """Raised when a live request was refused. Names the caller and reason."""


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _norm(value: Any, vocabulary: frozenset[str], *, fallback: str) -> str:
    """Deny by default: anything outside the vocabulary becomes the fallback."""
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text in vocabulary else fallback


def _host(url: Any) -> str:
    return (urlsplit(str(url or "")).netloc or "").lower().split("@")[-1].split(":")[0]


def _scheme(url: Any) -> str:
    return (urlsplit(str(url or "")).scheme or "").lower()


def build_live_network_decision(
    *,
    purpose: Any,
    target_url: Any,
    caller: Any,
    source_id: Any = None,
    method: Any = "GET",
    allow_live_fetch: bool = False,
    terms_status: Any = None,
    activation_status: Any = None,
    collector_status: Any = None,
    robots_status: Any = None,
    credential_status: Any = None,
    rate_limit_status: Any = None,
    user_agent_status: Any = None,
    attribution_status: Any = None,
    collector_type: Any = None,
    issuer_configured: bool = False,
    endpoint_configured: bool = False,
    consecutive_failures: int = 0,
) -> dict[str, Any]:
    """Decide whether one live request may proceed. Never performs it."""
    p = _norm(purpose, PURPOSES, fallback="")
    url = str(target_url or "")
    host = _host(url)
    scheme = _scheme(url)
    verb = str(method or "GET").strip().upper()
    caller_name = str(caller or "").strip() or "unknown"

    terms = _norm(terms_status, ALL_TERMS_STATUSES, fallback="UNKNOWN")
    activation = _norm(
        activation_status, ACTIVATION_STATUSES, fallback="activation_unknown"
    )
    collector = _norm(collector_status, COLLECTOR_STATUSES, fallback="not_active")
    robots = _norm(robots_status, ROBOTS_STATUSES, fallback="unknown")
    credential = _norm(credential_status, CREDENTIAL_STATUSES, fallback="unknown")
    rate_limit = _norm(rate_limit_status, RATE_LIMIT_STATUSES, fallback="unknown")
    user_agent = _norm(user_agent_status, USER_AGENT_STATUSES, fallback="unknown")
    attribution = _norm(attribution_status, ATTRIBUTION_STATUSES, fallback="unknown")

    satisfied: list[str] = []
    missing: list[str] = []
    blocked_reasons: list[str] = []

    def record(key: str, ok: bool, reason: str) -> None:
        if ok:
            satisfied.append(key)
        else:
            missing.append(key)
            blocked_reasons.append(reason)

    # A purpose we do not recognise has no satisfiable requirement set.
    if not p:
        return _decision(
            purpose=str(purpose or ""),
            url=url,
            host=host,
            method=verb,
            caller=caller_name,
            source_id=source_id,
            status="blocked",
            satisfied=[],
            missing=["recognised_purpose"],
            blocked_reasons=[f"purpose_out_of_vocabulary:{purpose!r}"],
            human_review=False,
            resolved={},
            attribution=attribution,
            terms=terms,
        )

    required = PURPOSE_REQUIREMENTS[p]

    if "live_fetch_opt_in" in required:
        record(
            "live_fetch_opt_in",
            allow_live_fetch is True,
            "live_fetch_not_opted_in",
        )

    if "https_scheme" in required:
        # Checked before any request is made, not inside one.
        record(
            "https_scheme",
            scheme == "https",
            f"scheme_not_https:{scheme or 'none'}",
        )

    if "host_permitted" in required:
        # Blacklist and robots-disallowed paths, from Gate 92 governance.
        permission = evaluate_fetch_permission(
            url=url, user_agent=NATIVEFORGE_USER_AGENT
        )
        record(
            "host_permitted",
            bool(permission.get("permitted")),
            "host_or_path_not_permitted:"
            + ",".join(permission.get("denial_reasons") or ["unknown"]),
        )

    if "user_agent_canonical" in required:
        record(
            "user_agent_canonical",
            user_agent == "canonical",
            f"user_agent_not_canonical:{user_agent}",
        )

    if "rate_limit_policy" in required:
        record(
            "rate_limit_policy",
            rate_limit in RATE_LIMIT_SATISFYING,
            f"rate_limit_policy_missing:{rate_limit}",
        )

    if "terms_cleared" in required:
        record(
            "terms_cleared",
            terms in TERMS_NON_BLOCKING,
            f"terms_status_blocks:{terms}",
        )

    if "activation_allowed" in required:
        record(
            "activation_allowed",
            activation in ACTIVATION_SATISFYING,
            f"activation_not_allowed:{activation}",
        )

    if "collector_active" in required:
        record(
            "collector_active",
            collector in COLLECTOR_SATISFYING,
            f"collector_not_active:{collector}",
        )

    if "robots_permits" in required:
        # A robots fetch that failed is not permission.
        record(
            "robots_permits",
            robots in ROBOTS_SATISFYING,
            f"robots_does_not_permit:{robots}",
        )

    if "credential" in required:
        ctype = str(collector_type or "").strip()
        credential_required = ctype in CREDENTIALED_COLLECTOR_TYPES
        # A collector type that needs a key may not declare it not_required.
        ok = (
            credential == "present_and_valid"
            if credential_required
            else credential in CREDENTIAL_SATISFYING
        )
        record("credential", ok, f"credential_missing:{credential}")

    if "issuer_configured" in required:
        record("issuer_configured", issuer_configured is True, "issuer_not_configured")

    if "endpoint_configured" in required:
        record(
            "endpoint_configured",
            endpoint_configured is True,
            "endpoint_not_configured",
        )

    # Attribution gates whether Grants.gov output may be surfaced. It does not
    # gate the request, so it is reported rather than folded into `allowed`.
    requires_attribution = host in GRANTS_GOV_HOSTS
    attribution_satisfied = attribution in ATTRIBUTION_SATISFYING

    # Circuit breaker, consulted before the request rather than after it fails.
    breaker_tripped = consecutive_failures >= CIRCUIT_BREAKER_CONSECUTIVE_FAILURES
    if breaker_tripped:
        blocked_reasons.append(
            f"circuit_breaker_open:{consecutive_failures}"
            f">={CIRCUIT_BREAKER_CONSECUTIVE_FAILURES}"
        )

    # Gate 77B stays authoritative for Grants.gov.
    grants_gov_flag_blocked = host in GRANTS_GOV_HOSTS and not live_network_allowed()
    if grants_gov_flag_blocked:
        blocked_reasons.append("gate77b_hermetic_guard_blocks_grants_gov")

    human_review_required = terms in TERMS_HUMAN_ONLY

    if human_review_required:
        status = "requires_human_review"
    elif missing or breaker_tripped or grants_gov_flag_blocked:
        status = "blocked"
    else:
        status = "allowed"

    return _decision(
        purpose=p,
        url=url,
        host=host,
        method=verb,
        caller=caller_name,
        source_id=source_id,
        status=status,
        satisfied=satisfied,
        missing=missing,
        blocked_reasons=blocked_reasons,
        human_review=human_review_required,
        resolved={
            "terms_status": terms,
            "activation_status": activation,
            "collector_status": collector,
            "robots_status": robots,
            "credential_status": credential,
            "rate_limit_status": rate_limit,
            "user_agent_status": user_agent,
            "attribution_status": attribution,
            "scheme": scheme,
            "method": verb,
            "allow_live_fetch": bool(allow_live_fetch),
            "consecutive_failures": int(consecutive_failures),
        },
        attribution=attribution,
        terms=terms,
        required=list(required),
        requires_attribution=requires_attribution,
        attribution_satisfied=attribution_satisfied,
    )


def _decision(
    *,
    purpose: str,
    url: str,
    host: str,
    method: str,
    caller: str,
    source_id: Any,
    status: str,
    satisfied: list[str],
    missing: list[str],
    blocked_reasons: list[str],
    human_review: bool,
    resolved: dict[str, Any],
    attribution: str,
    terms: str,
    required: list[str] | None = None,
    requires_attribution: bool = False,
    attribution_satisfied: bool = False,
) -> dict[str, Any]:
    allowed = status in PERMITTING_STATUSES
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "purpose": purpose,
            "source_id": source_id,
            "target_url": url,
            "host": host,
            "method": method,
            "caller": caller,
            "allowed": allowed,
            "decision_status": status,
            "blocked_reasons": sorted(set(blocked_reasons)),
            "human_review_required": human_review,
            "requires_terms_review": (
                terms in TERMS_BLOCKING or terms in TERMS_HUMAN_ONLY
            ),
            "requires_activation": "activation_allowed" in (required or []),
            "requires_attribution": requires_attribution,
            "attribution_satisfied": attribution_satisfied,
            "may_surface_customer_data": (not requires_attribution)
            or attribution_satisfied,
            "requires_credential": "credential" in (required or []),
            "required_requirements": list(required or []),
            "requirements_satisfied": sorted(satisfied),
            "requirements_missing": sorted(missing),
            "resolved_inputs": resolved,
            # Governance constants, reported so a caller cannot claim looser.
            "min_request_interval_seconds": MIN_REQUEST_INTERVAL_SECONDS,
            "per_host_concurrency": PER_HOST_CONCURRENCY,
            "canonical_user_agent": NATIVEFORGE_USER_AGENT,
            "audit_event": {
                "event": "live_network_decision",
                "caller": caller,
                "purpose": purpose,
                "host": host,
                "method": method,
                "source_id": source_id,
                "decision_status": status,
                "blocked_reasons": sorted(set(blocked_reasons)),
            },
            # This module decides. It never fetches.
            "fetch_performed": False,
            "fabricated": False,
        }
    )


def assert_live_network_allowed(**kwargs: Any) -> dict[str, Any]:
    """Raise unless the request is permitted. Returns the decision when it is.

    Raises rather than returning a sentinel, following Gate 77B: there is no
    useful partial answer to a request we were not allowed to make, and a
    silent empty result is indistinguishable from a genuine empty response -
    which is how the corpus fixture got overwritten with a placeholder.
    """
    decision = build_live_network_decision(**kwargs)
    if not decision["allowed"]:
        raise LiveNetworkPermissionError(
            "live network request refused. "
            f"caller={decision['caller']} purpose={decision['purpose']} "
            f"host={decision['host'] or 'unknown'} "
            f"status={decision['decision_status']} "
            f"reasons={','.join(decision['blocked_reasons']) or 'unspecified'}"
        )
    return decision


def require_live_network_permission(**kwargs: Any) -> dict[str, Any]:
    """Non-raising form. Returns the decision; callers must check `allowed`."""
    return build_live_network_decision(**kwargs)


def guard_invariant_failures(decision: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if decision.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if decision.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")
    if decision.get("fetch_performed") is not False:
        fails.append("guard_claimed_a_fetch")

    status = decision.get("decision_status")
    if status not in DECISION_STATUSES:
        fails.append("decision_status_out_of_vocabulary")
    if decision.get("allowed") != (status in PERMITTING_STATUSES):
        fails.append("allowed_disagrees_with_decision_status")

    if decision.get("allowed"):
        if decision.get("requirements_missing"):
            fails.append("allowed_with_missing_requirements")
        if decision.get("blocked_reasons"):
            fails.append("allowed_with_blocked_reasons")
        if decision.get("human_review_required"):
            fails.append("allowed_while_requiring_human_review")
        # Deny by default: an allowed request must have opted in explicitly.
        if decision.get("resolved_inputs", {}).get("allow_live_fetch") is not True:
            fails.append("allowed_without_live_fetch_opt_in")
        # And must be https.
        if decision.get("resolved_inputs", {}).get("scheme") != "https":
            fails.append("allowed_over_a_non_https_scheme")

    if not decision.get("allowed") and not decision.get("blocked_reasons"):
        fails.append("refusal_without_a_reason")

    # Governance constants may not be reported looser than Gate 92's floors.
    if decision.get("min_request_interval_seconds", 0) < MIN_REQUEST_INTERVAL_SECONDS:
        fails.append("request_interval_below_floor")
    if decision.get("per_host_concurrency") != PER_HOST_CONCURRENCY:
        fails.append("per_host_concurrency_relaxed")
    if decision.get("canonical_user_agent") != NATIVEFORGE_USER_AGENT:
        fails.append("non_canonical_user_agent_in_decision")

    resolved = decision.get("resolved_inputs") or {}

    # A blacklisted host may never be allowed.
    if decision.get("host") in BLACKLISTED_HOSTS and decision.get("allowed"):
        fails.append("blacklisted_host_allowed")

    # Robots failure is never permission.
    if resolved.get("robots_status") in {"fetch_failed", "unknown", "disallowed"}:
        if "robots_permits" in (decision.get("required_requirements") or []):
            if decision.get("allowed"):
                fails.append(
                    f"allowed_despite_robots:{resolved.get('robots_status')}"
                )

    # Human review cannot be lifted by satisfying automated requirements.
    if decision.get("human_review_required") and decision.get("allowed"):
        fails.append("human_review_source_allowed")

    # Grants.gov output may not be surfaced without the notice.
    if decision.get("requires_attribution") and decision.get(
        "may_surface_customer_data"
    ):
        if not decision.get("attribution_satisfied"):
            fails.append("grants_gov_surfaced_without_attribution")

    # A decision must name its caller.
    if not decision.get("caller"):
        fails.append("decision_without_a_caller")
    audit = decision.get("audit_event") or {}
    if audit.get("caller") != decision.get("caller"):
        fails.append("audit_event_caller_mismatch")

    return fails


def canonical_user_agent() -> str:
    """The one string every fetcher must present."""
    return NATIVEFORGE_USER_AGENT


def user_agent_status_for(user_agent: Any) -> str:
    """Classify a UA against the canonical string, for guard input."""
    violations = canonical_user_agent_violations(user_agent)
    if not violations:
        return "canonical"
    if any(v.startswith("ai_crawler_user_agent:") for v in violations):
        return "forbidden_ai_crawler"
    if violations == ["user_agent_is_not_the_canonical_string"]:
        return "non_canonical"
    return "unknown"


__all__ = [
    "LiveNetworkBlockedError",
    "LiveNetworkPermissionError",
    "assert_live_network_allowed",
    "build_live_network_decision",
    "canonical_user_agent",
    "guard_invariant_failures",
    "require_live_network_permission",
    "user_agent_status_for",
]
