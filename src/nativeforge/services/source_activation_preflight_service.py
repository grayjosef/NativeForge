"""Source activation preflight (Gate 93B).

Decides whether a source may be activated for collection. It never activates
anything, and it never fetches.

## Deny by default, and the default is not "no evidence yet"

``activation_blocked`` is the starting position and every requirement must be
*affirmatively* satisfied to move off it. The allowed set is derived from
satisfied requirements; it is never computed by subtracting blockers from a
permissive default. This is the Gate 79B lesson, and it is the difference
between "we checked and it is fine" and "we have not checked".

An unrecognised status value therefore resolves to the blocking member of its
vocabulary, not to a pass. A typo'd ``terms_status`` blocks.

## Four statuses

``activation_allowed``               every required precondition satisfied
``activation_blocked``               at least one requirement missing
``activation_requires_human_review`` a person must decide, not a rule
``activation_unknown``               inputs insufficient to decide

``activation_unknown`` is separate from ``activation_blocked`` on purpose, and
neither one permits anything. The distinction is for the operator: blocked names
a fixable requirement, unknown names a question nobody has asked yet.

## Human review outranks a satisfied checklist

``HUMAN_REVIEW_ONLY`` produces ``activation_requires_human_review`` even when
every other requirement passes, because the requirement it fails is *"a rule may
decide this"*. A source whose terms permit only human access cannot be
automated by satisfying more automation preconditions.

## Monitoring cannot start from unknown

If ``monitoring_status`` is not affirmatively ``not_started``, scheduling is
refused. A source whose current monitoring state we cannot describe is not a
source we may schedule — starting a monitor on top of an unknown one is how you
get two.

## Two separate answers

``safe_to_schedule`` and ``safe_to_fetch_now`` are distinct, and in Gate 93
``safe_to_fetch_now`` is **always False** regardless of inputs. Nothing fetches
in this gate, so a preflight that could return True for an immediate fetch would
be describing a capability that does not exist. An invariant enforces it.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_source_activation_preflight_v1"

ACTIVATION_STATUSES = frozenset(
    {
        "activation_allowed",
        "activation_blocked",
        "activation_requires_human_review",
        "activation_unknown",
    }
)

# The only status that permits anything. Everything else is a refusal of some
# kind, which keeps the permissive set a single named member.
PERMITTING_STATUSES = frozenset({"activation_allowed"})

# Terms vocabulary, bridged from Gate 90's importer rather than redeclared.
TERMS_BLOCKING = frozenset({"TERMS_REVIEW_REQUIRED", "UNKNOWN"})
TERMS_HUMAN_ONLY = frozenset({"HUMAN_REVIEW_ONLY"})
TERMS_NON_BLOCKING = frozenset({"NO_REVIEW_REQUIRED", "ATTRIBUTION_REQUIRED"})

LEGAL_REVIEW_STATUSES = frozenset(
    {"approved", "rejected", "pending", "not_required", "unknown"}
)
LEGAL_REVIEW_SATISFYING = frozenset({"approved", "not_required"})

CREDENTIAL_STATUSES = frozenset(
    {"present_and_valid", "missing", "expired", "not_required", "unknown"}
)
CREDENTIAL_SATISFYING = frozenset({"present_and_valid", "not_required"})

ATTRIBUTION_STATUSES = frozenset(
    {"present_and_verbatim", "missing", "altered", "not_required", "unknown"}
)
ATTRIBUTION_SATISFYING = frozenset({"present_and_verbatim", "not_required"})

USER_AGENT_STATUSES = frozenset(
    {"policy_declared", "missing", "forbidden_ai_crawler", "not_required", "unknown"}
)
USER_AGENT_SATISFYING = frozenset({"policy_declared", "not_required"})

RATE_LIMIT_STATUSES = frozenset({"policy_declared", "missing", "unknown"})
RATE_LIMIT_SATISFYING = frozenset({"policy_declared"})

STORAGE_STATUSES = frozenset(
    {
        "contract_satisfied",
        "local_implementation_available",
        "production_available",
        "missing",
        "partial",
        "unknown",
    }
)
STORAGE_SATISFYING = frozenset(
    {"contract_satisfied", "local_implementation_available", "production_available"}
)

# Gate 95: a contract is not an implementation. This is a separate
# requirement from the per-source `raw_payload_storage` status above,
# because a source can be configured correctly against a store that does not
# exist - which is what "contract satisfied" meant for all of Gate 93.
STORE_IMPLEMENTATION_STATUSES = frozenset(
    {"none", "local_only", "production", "unknown"}
)
STORE_IMPLEMENTATION_SATISFYING = frozenset({"local_only", "production"})

# Gate 96: a dry-run and a live collection need different stores. A local,
# per-checkout store is enough to scaffold a collector against; it is not
# enough to run one, because a live payload whose bytes live only in one
# developer's checkout is not evidence anyone else can retrieve.
COLLECTION_INTENTS = frozenset({"dry_run", "live_collection"})

# Which store each intent requires. Named per intent rather than derived,
# so widening one does not silently widen the other.
INTENT_STORE_REQUIREMENT: dict[str, frozenset[str]] = {
    "dry_run": frozenset({"local_only", "production"}),
    "live_collection": frozenset({"production"}),
}

SCHEDULER_STATUSES = frozenset({"policy_declared", "missing", "unknown"})
SCHEDULER_SATISFYING = frozenset({"policy_declared"})

MONITORING_STATUSES = frozenset({"not_started", "scheduled", "running", "unknown"})
MONITORING_SCHEDULABLE = frozenset({"not_started"})

# Collector types that cannot run without a credential, and those that put a
# crawler on somebody's host.
CREDENTIALED_COLLECTOR_TYPES = frozenset({"public_api_with_key", "authenticated_feed"})
CRAWLER_COLLECTOR_TYPES = frozenset({"html_crawler", "feed_crawler", "pdf_crawler"})

COLLECTOR_TYPES = (
    frozenset({"bulk_extract", "public_api", "feed", "manual_intake"})
    | CREDENTIALED_COLLECTOR_TYPES
    | CRAWLER_COLLECTOR_TYPES
)

# Every requirement this service knows how to check. Order is the order they
# are reported in, so an operator reads the same list every time.
REQUIREMENT_KEYS: tuple[str, ...] = (
    "terms_cleared",
    "legal_review",
    "attribution",
    "credential",
    "raw_payload_storage",
    "raw_payload_store_implementation",
    "store_supports_collection_intent",
    "rate_limit_policy",
    "user_agent_policy",
    "scheduler_policy",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def detect_store_implementation() -> str:
    """Which raw payload store actually exists in this checkout.

    Detected, not declared. A caller-supplied flag saying "the store exists"
    is the same shape as the corpus flags Gates 87-89 unpicked: a claim about
    a claim. This imports the module and reports what it finds.
    """
    try:
        from nativeforge.services import local_raw_payload_store_service as store
    except ImportError:
        return "none"
    if not hasattr(store, "store_raw_payload"):
        return "none"
    # Gate 96: production requires BOTH the metadata table and a configured
    # body store. Detected, not declared - the readiness service establishes
    # each by importing and inspecting, never by reading a caller flag.
    try:
        from nativeforge.services.raw_payload_production_readiness_service import (
            build_production_readiness,
        )

        if build_production_readiness()["production_raw_payload_store_available"]:
            return "production"
    except ImportError:
        pass
    return "local_only"


def _norm(value: Any, vocabulary: frozenset[str], *, fallback: str) -> str:
    """Deny by default: anything outside the vocabulary becomes the fallback."""
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text in vocabulary else fallback


def build_activation_preflight(
    *,
    source_id: Any,
    source_name: Any = None,
    source_role: Any = None,
    collector_type: Any = None,
    terms_status: Any = None,
    legal_review_status: Any = None,
    credential_status: Any = None,
    attribution_status: Any = None,
    user_agent_status: Any = None,
    rate_limit_status: Any = None,
    storage_status: Any = None,
    scheduler_status: Any = None,
    monitoring_status: Any = None,
    collection_intent: Any = None,
) -> dict[str, Any]:
    """One source in, one activation decision out. Nothing is activated."""
    ctype = _norm(collector_type, COLLECTOR_TYPES, fallback="unknown")

    terms = str(terms_status).strip() if terms_status is not None else "UNKNOWN"
    if terms not in (TERMS_BLOCKING | TERMS_HUMAN_ONLY | TERMS_NON_BLOCKING):
        terms = "UNKNOWN"

    legal = _norm(legal_review_status, LEGAL_REVIEW_STATUSES, fallback="unknown")
    credential = _norm(credential_status, CREDENTIAL_STATUSES, fallback="unknown")
    attribution = _norm(attribution_status, ATTRIBUTION_STATUSES, fallback="unknown")
    user_agent = _norm(user_agent_status, USER_AGENT_STATUSES, fallback="unknown")
    rate_limit = _norm(rate_limit_status, RATE_LIMIT_STATUSES, fallback="unknown")
    storage = _norm(storage_status, STORAGE_STATUSES, fallback="unknown")
    scheduler = _norm(scheduler_status, SCHEDULER_STATUSES, fallback="unknown")
    monitoring = _norm(monitoring_status, MONITORING_STATUSES, fallback="unknown")

    satisfied: list[str] = []
    missing: list[str] = []
    blocked_reasons: list[str] = []

    def record(key: str, ok: bool, reason: str) -> None:
        if ok:
            satisfied.append(key)
        else:
            missing.append(key)
            blocked_reasons.append(reason)

    # 1. Terms. HUMAN_REVIEW_ONLY is handled separately below; here it simply
    #    does not satisfy the requirement.
    record(
        "terms_cleared",
        terms in TERMS_NON_BLOCKING,
        f"terms_status_blocks_activation:{terms}",
    )

    # 2. Legal review, required wherever terms are not already clear.
    legal_required = terms not in TERMS_NON_BLOCKING
    record(
        "legal_review",
        (not legal_required) or legal in LEGAL_REVIEW_SATISFYING,
        f"legal_review_not_approved:{legal}",
    )

    # 3. Attribution. Required when the terms say so, and verbatim or not at all.
    attribution_required = terms == "ATTRIBUTION_REQUIRED" or (
        attribution in {"missing", "altered"}
        and attribution_status is not None
    )
    record(
        "attribution",
        attribution in ATTRIBUTION_SATISFYING
        if attribution_required
        else attribution != "altered",
        f"attribution_not_present_verbatim:{attribution}",
    )

    # 4. Credential, only for collector types that need one - but a collector
    #    type that needs one may not exempt itself by declaring `not_required`.
    #    SAM.gov cannot be a keyed API whose credential is not required, and
    #    letting the row say so would be a self-declared exemption from the
    #    requirement its own collector type creates.
    credential_required = ctype in CREDENTIALED_COLLECTOR_TYPES
    credential_ok = (
        credential == "present_and_valid"
        if credential_required
        else credential in CREDENTIAL_SATISFYING
    )
    record(
        "credential",
        credential_ok,
        f"credential_missing_for_credentialed_collector:{credential}",
    )

    # 5. Raw payload storage. Required for every collector without exception -
    #    a collector that does not retain its evidence produces records nobody
    #    can later distinguish from invention.
    record(
        "raw_payload_storage",
        storage in STORAGE_SATISFYING,
        f"raw_payload_store_contract_unsatisfied:{storage}",
    )

    # 5b. Gate 95: the store must actually exist. A source configured against a
    #     store nobody built is configured against nothing.
    store_implementation = detect_store_implementation()
    record(
        "raw_payload_store_implementation",
        store_implementation in STORE_IMPLEMENTATION_SATISFYING,
        f"raw_payload_store_implementation_missing:{store_implementation}",
    )

    # 5c. Gate 96: the store must support what this source intends to do.
    #     A dry-run may scaffold against the local store; a live collection
    #     needs production storage, because a payload retrievable only from one
    #     checkout is not evidence.
    intent = _norm(collection_intent, COLLECTION_INTENTS, fallback="dry_run")
    accepted_stores = INTENT_STORE_REQUIREMENT[intent]
    record(
        "store_supports_collection_intent",
        store_implementation in accepted_stores,
        f"store_does_not_support_intent:{intent}:{store_implementation}",
    )

    # 6. Rate limit policy. Also required for every collector.
    record(
        "rate_limit_policy",
        rate_limit in RATE_LIMIT_SATISFYING,
        f"rate_limit_policy_missing:{rate_limit}",
    )

    # 7. User-agent policy, required for anything that crawls a host - and, as
    #    with the credential, a crawler may not exempt itself by declaring the
    #    policy `not_required`. A forbidden AI-crawler UA never satisfies it.
    ua_required = ctype in CRAWLER_COLLECTOR_TYPES
    user_agent_ok = (
        user_agent == "policy_declared"
        if ua_required
        else user_agent in USER_AGENT_SATISFYING
    )
    record(
        "user_agent_policy",
        user_agent_ok,
        f"user_agent_policy_missing_for_crawler:{user_agent}",
    )

    # 8. Scheduler policy.
    record(
        "scheduler_policy",
        scheduler in SCHEDULER_SATISFYING,
        f"scheduler_policy_missing:{scheduler}",
    )

    human_review_required = terms in TERMS_HUMAN_ONLY

    # Monitoring may only be scheduled from an affirmatively known idle state.
    monitoring_schedulable = monitoring in MONITORING_SCHEDULABLE
    if not monitoring_schedulable:
        blocked_reasons.append(f"monitoring_state_not_schedulable:{monitoring}")

    # Decide. Human review first: it is a refusal a checklist cannot lift.
    if human_review_required:
        status = "activation_requires_human_review"
    elif missing:
        # If the only thing wrong is that nothing was supplied, say unknown -
        # blocked implies a named, fixable requirement.
        supplied = any(
            v is not None
            for v in (
                terms_status,
                legal_review_status,
                credential_status,
                attribution_status,
                user_agent_status,
                rate_limit_status,
                storage_status,
                scheduler_status,
                monitoring_status,
            )
        )
        status = "activation_blocked" if supplied else "activation_unknown"
    elif not monitoring_schedulable:
        status = "activation_blocked"
    else:
        status = "activation_allowed"

    allowed = status in PERMITTING_STATUSES

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_id": source_id,
            "source_name": source_name,
            "source_role": source_role,
            "collector_type": ctype,
            "activation_status": status,
            "activation_allowed": allowed,
            "blocked_reasons": sorted(set(blocked_reasons)),
            "human_review_required": human_review_required,
            "requirements_satisfied": sorted(satisfied),
            "requirements_missing": sorted(missing),
            "safe_to_schedule": bool(allowed and monitoring_schedulable),
            # Constant for this gate. Nothing fetches, so nothing may say it is
            # safe to fetch right now.
            "safe_to_fetch_now": False,
            # Gate 95. Three distinct facts, never collapsed into one:
            # the contract exists, a local store exists, production does not.
            "raw_payload_store_contract_available": True,
            "local_raw_payload_store_available": store_implementation
            in STORE_IMPLEMENTATION_SATISFYING,
            "production_raw_payload_store_available": store_implementation
            == "production",
            "raw_payload_store_implementation": store_implementation,
            "collection_intent": intent,
            "intent_accepts_store_implementations": sorted(accepted_stores),
            "resolved_inputs": {
                "terms_status": terms,
                "legal_review_status": legal,
                "credential_status": credential,
                "attribution_status": attribution,
                "user_agent_status": user_agent,
                "rate_limit_status": rate_limit,
                "storage_status": storage,
                "scheduler_status": scheduler,
                "monitoring_status": monitoring,
            },
            "activation_performed": False,
            "fetch_performed": False,
            "fabricated": False,
        }
    )


def summarise_preflight(results: list[dict[str, Any]]) -> dict[str, Any]:
    by_status = {s: 0 for s in sorted(ACTIVATION_STATUSES)}
    for r in results:
        status = r.get("activation_status")
        if status in by_status:
            by_status[status] += 1

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "evaluated_count": len(results),
            "by_activation_status": by_status,
            "activation_allowed_count": sum(
                1 for r in results if r.get("activation_allowed")
            ),
            "human_review_required_count": sum(
                1 for r in results if r.get("human_review_required")
            ),
            "safe_to_schedule_count": sum(
                1 for r in results if r.get("safe_to_schedule")
            ),
            "safe_to_fetch_now_count": 0,
            "sources_activated": 0,
            "fetch_performed": False,
            "fabricated": False,
        }
    )


def preflight_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")
    if result.get("activation_performed") is not False:
        fails.append("preflight_claimed_an_activation")
    if result.get("fetch_performed") is not False:
        fails.append("preflight_claimed_a_fetch")

    # Gate 93 constant.
    if result.get("safe_to_fetch_now") is not False:
        fails.append("preflight_claimed_safe_to_fetch_now")

    status = result.get("activation_status")
    if status not in ACTIVATION_STATUSES:
        fails.append("activation_status_out_of_vocabulary")

    # allowed is derived from the single permitting status, never set beside it.
    if result.get("activation_allowed") != (status in PERMITTING_STATUSES):
        fails.append("activation_allowed_disagrees_with_status")

    if result.get("activation_allowed") and result.get("requirements_missing"):
        fails.append("activation_allowed_with_missing_requirements")
    if result.get("activation_allowed") and result.get("blocked_reasons"):
        fails.append("activation_allowed_with_blocked_reasons")

    # Human review cannot be satisfied by passing more automated checks.
    if result.get("human_review_required") and result.get("activation_allowed"):
        fails.append("human_review_source_marked_activation_allowed")
    if result.get("human_review_required") and (
        status != "activation_requires_human_review"
    ):
        fails.append("human_review_required_without_matching_status")

    # A refusal must name itself.
    if status in {"activation_blocked", "activation_requires_human_review"}:
        if not result.get("blocked_reasons") and not result.get(
            "requirements_missing"
        ):
            fails.append("refusal_without_a_reason")

    if result.get("safe_to_schedule") and not result.get("activation_allowed"):
        fails.append("safe_to_schedule_without_activation_allowed")

    # Every requirement is accounted for exactly once.
    satisfied = set(result.get("requirements_satisfied") or [])
    missing = set(result.get("requirements_missing") or [])
    if satisfied & missing:
        fails.append("requirement_both_satisfied_and_missing")
    if satisfied | missing != set(REQUIREMENT_KEYS):
        fails.append("requirement_dropped_from_the_checklist")

    # Blocking terms may never reach allowed.
    resolved = result.get("resolved_inputs") or {}
    if resolved.get("terms_status") in TERMS_BLOCKING and result.get(
        "activation_allowed"
    ):
        fails.append("blocking_terms_status_reached_activation_allowed")
    if resolved.get("terms_status") in TERMS_HUMAN_ONLY and not result.get(
        "human_review_required"
    ):
        fails.append("human_review_only_terms_without_human_review_flag")
    if resolved.get("monitoring_status") not in MONITORING_SCHEDULABLE and result.get(
        "safe_to_schedule"
    ):
        fails.append("scheduled_from_a_non_idle_monitoring_state")

    # A collector type may not exempt itself from the requirement its own type
    # creates. Both of these were reachable before the smoke test caught them.
    if result.get("activation_allowed"):
        ctype = result.get("collector_type")
        if (
            ctype in CREDENTIALED_COLLECTOR_TYPES
            and resolved.get("credential_status") != "present_and_valid"
        ):
            fails.append("credentialed_collector_allowed_without_a_credential")
        if (
            ctype in CRAWLER_COLLECTOR_TYPES
            and resolved.get("user_agent_status") != "policy_declared"
        ):
            fails.append("crawler_allowed_without_a_user_agent_policy")

    # Gate 95: a local store is not a production store, and no result may
    # imply otherwise.
    if result.get("production_raw_payload_store_available") is not False:
        fails.append("preflight_claimed_production_payload_storage")
    if result.get("raw_payload_store_implementation") not in (
        STORE_IMPLEMENTATION_STATUSES
    ):
        fails.append("store_implementation_out_of_vocabulary")
    if result.get("activation_allowed") and result.get(
        "raw_payload_store_implementation"
    ) not in STORE_IMPLEMENTATION_SATISFYING:
        fails.append("activation_allowed_without_a_payload_store_implementation")

    # Gate 96: a live collection may never be allowed on a local-only store.
    if result.get("collection_intent") not in COLLECTION_INTENTS:
        fails.append("collection_intent_out_of_vocabulary")
    if (
        result.get("activation_allowed")
        and result.get("collection_intent") == "live_collection"
        and result.get("raw_payload_store_implementation") != "production"
    ):
        fails.append("live_collection_allowed_on_a_non_production_store")

    # An AI-crawler UA is never a satisfied policy, whatever the collector type.
    if resolved.get("user_agent_status") == "forbidden_ai_crawler" and result.get(
        "activation_allowed"
    ):
        fails.append("activation_allowed_with_forbidden_ai_crawler_user_agent")

    return fails
