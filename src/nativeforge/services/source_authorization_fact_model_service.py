"""The recorded facts the live guard requires (Gate 162B).

Gate 94B's `build_live_network_decision` already names every requirement and
every permitting value. This module invents none of them. It defines what a
RECORD of each requirement looks like, so the guard can be answered from
evidence instead of from a caller's booleans.

## Why the three-state distinction is the whole point

A fact can fail in five different ways, and collapsing them loses the only
information an operator needs:

```text
recorded        a decision exists and permits
denied          a decision exists and refuses
needs_review    a decision exists and defers to a human
missing         NO record exists at all
unknown         a record exists but does not answer
stale           a record answered, and the answer expired
```

All six except `recorded` refuse. That is deliberate and it is not the same as
storing `False`: "nobody has reviewed these terms" and "a reviewer read these
terms and said no" are opposite operational situations with the same effect on
permission, and a boolean cannot tell them apart.

Gate 160 built a guard that refused everything and passed every refusal test.
The inverse failure is a guard that refuses everything for reasons nobody can
distinguish, which is how a fixable blocker stays unfixed for a year.

## Missing is not False

`resolve` never substitutes a default. A fact with no record carries
`fact_status=missing` and `value=None`, and the resolver reports it by name.
Filling it with the guard's refusing value would make the refusal correct and
the diagnosis wrong.

## Freshness

Three facts can go stale: terms, human review, and robots. A terms decision
made against a document that has since changed is not evidence about the
current document. `expires_at` is carried per fact, and an expired affirmative
answer becomes `stale` rather than staying `recorded`.

Credential, rate-limit, user-agent and collector facts are runtime state rather
than decisions, so they are measured fresh each time and carry no expiry.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from nativeforge.services.live_network_guard_service import (
    ACTIVATION_SATISFYING,
    ACTIVATION_STATUSES,
    ALL_TERMS_STATUSES,
    ATTRIBUTION_SATISFYING,
    ATTRIBUTION_STATUSES,
    COLLECTOR_SATISFYING,
    COLLECTOR_STATUSES,
    CREDENTIAL_SATISFYING,
    CREDENTIAL_STATUSES,
    RATE_LIMIT_SATISFYING,
    RATE_LIMIT_STATUSES,
    ROBOTS_SATISFYING,
    ROBOTS_STATUSES,
    TERMS_NON_BLOCKING,
    USER_AGENT_STATUSES,
)

SCHEMA_VERSION = "nf_source_authorization_fact_model_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

# ---------------------------------------------------------------- statuses

#: A decision exists and it permits. The ONLY permitting status.
FACT_RECORDED = "recorded"

#: A decision exists and refuses.
FACT_DENIED = "denied"

#: A decision exists and defers to a human who has not answered.
FACT_NEEDS_REVIEW = "needs_review"

#: No record exists. Distinct from denied, and the distinction is the point.
FACT_MISSING = "missing"

#: A record exists but does not answer the question.
FACT_UNKNOWN = "unknown"

#: A record answered and the answer has expired.
FACT_STALE = "stale"

FACT_STATUSES: tuple[str, ...] = (
    FACT_RECORDED,
    FACT_DENIED,
    FACT_NEEDS_REVIEW,
    FACT_MISSING,
    FACT_UNKNOWN,
    FACT_STALE,
)

#: Exactly one status permits. Written as a frozenset of one rather than as
#: `!= something`, so adding a status cannot accidentally widen permission.
PERMITTING_FACT_STATUSES: frozenset[str] = frozenset({FACT_RECORDED})

#: Why each non-permitting status refuses, in words an operator can act on.
REFUSAL_MEANING: dict[str, str] = {
    FACT_DENIED: (
        "a decision exists and it says no. Changing this needs a new decision."
    ),
    FACT_NEEDS_REVIEW: (
        "a decision exists and defers to a human who has not answered yet"
    ),
    FACT_MISSING: (
        "no record exists. Nobody has decided this, which is not the same as "
        "somebody deciding against it."
    ),
    FACT_UNKNOWN: (
        "a record exists but does not answer the question - usually a column "
        "that was never populated"
    ),
    FACT_STALE: (
        "a record answered and the answer expired. The evidence is about a "
        "document or state that may have changed since."
    ),
}

# ------------------------------------------------------- sources of truth

SOT_REGISTRY = "source_monitoring_approved_source_service.load_registry_rows"
SOT_TERMS = "nf_source_terms_decisions"
SOT_HUMAN_REVIEW = "nf_discovery_review_items[source_verification]"
SOT_ACTIVATION = "nf_active_opportunity_sources.activation_approved_*"
SOT_RUNTIME = "gates 156-161 readiness verifiers"
SOT_CANONICAL_UA = "nativeforge_user_agent_service.canonical_user_agent"
SOT_COLLECTOR = "phase1_collector_activation_policy_service"
SOT_MEASURED = "measured at resolve time"

# ---------------------------------------------------------------- the facts

#: The guard's own ten inputs. Names, vocabularies and permitting values are
#: READ from `live_network_guard_service`, never restated here - a second copy
#: of a vocabulary is a second thing to drift.
#:
#: `collector_type` and `source_id` are shape rather than permission: the guard
#: uses them to decide WHICH requirements apply, not whether they are met.
FACT_SPECS: tuple[dict[str, Any], ...] = (
    {
        "fact_name": "source_registered",
        "guard_input": None,
        "vocabulary": ("registered", "unknown_source"),
        "permitting": ("registered",),
        "source_of_truth": SOT_REGISTRY,
        "decision_authority": None,
        "freshness_required": False,
        "why": (
            "the registry knowing a source is the precondition for every other "
            "fact. It is NOT an approval - 177 sources are registered and none "
            "is approved."
        ),
    },
    {
        "fact_name": "terms_status",
        "guard_input": "terms_status",
        "vocabulary": tuple(sorted(ALL_TERMS_STATUSES)),
        "permitting": tuple(sorted(TERMS_NON_BLOCKING)),
        "source_of_truth": SOT_TERMS,
        "decision_authority": "a human reviewer",
        "freshness_required": True,
        "why": (
            "whether the source's terms permit automated collection. A human "
            "decision; 171 of 177 sources block here because there was nowhere "
            "to record one until this gate."
        ),
    },
    {
        "fact_name": "human_review_status",
        "guard_input": None,
        "vocabulary": ("approved", "rejected", "open", "in_review", "deferred"),
        "permitting": ("approved",),
        "source_of_truth": SOT_HUMAN_REVIEW,
        "decision_authority": "a human reviewer",
        "freshness_required": True,
        "why": (
            "the guard exposes `human_review_required` as an OUTPUT rather than "
            "taking a review verdict as input, so the review decision gates "
            "authorization here instead. 6 of 177 sources block on this."
        ),
    },
    {
        "fact_name": "activation_status",
        "guard_input": "activation_status",
        "vocabulary": tuple(sorted(ACTIVATION_STATUSES)),
        "permitting": tuple(sorted(ACTIVATION_SATISFYING)),
        "source_of_truth": SOT_ACTIVATION,
        "decision_authority": "an operator, recorded with attribution",
        "freshness_required": False,
        "why": (
            "whether an operator activated this source, recorded with who and "
            "when. Already persisted by nf_active_opportunity_sources; this "
            "gate composes it rather than adding a second approval column."
        ),
    },
    {
        "fact_name": "collector_status",
        "guard_input": "collector_status",
        "vocabulary": tuple(sorted(COLLECTOR_STATUSES)),
        "permitting": tuple(sorted(COLLECTOR_SATISFYING)),
        "source_of_truth": SOT_COLLECTOR,
        "decision_authority": None,
        "freshness_required": False,
        "why": "whether a collector for this source is running at all",
    },
    {
        "fact_name": "robots_status",
        "guard_input": "robots_status",
        "vocabulary": tuple(sorted(ROBOTS_STATUSES)),
        "permitting": tuple(sorted(ROBOTS_SATISFYING)),
        "source_of_truth": SOT_MEASURED,
        "decision_authority": None,
        "freshness_required": True,
        "why": (
            "whether robots.txt permits the path. Requires FETCHING robots.txt, "
            "which is itself a live call - so this fact is unresolvable in "
            "Gate 162 and refuses as missing. Gate 163 is where that fetch is "
            "first permitted, and it is the first live call the campaign makes."
        ),
    },
    {
        "fact_name": "credential_status",
        "guard_input": "credential_status",
        "vocabulary": tuple(sorted(CREDENTIAL_STATUSES)),
        "permitting": tuple(sorted(CREDENTIAL_SATISFYING)),
        "source_of_truth": SOT_MEASURED,
        "decision_authority": None,
        "freshness_required": False,
        "why": (
            "whether a required credential is present. Measured from settings; "
            "the VALUE is never read, recorded or reported."
        ),
    },
    {
        "fact_name": "rate_limit_status",
        "guard_input": "rate_limit_status",
        "vocabulary": tuple(sorted(RATE_LIMIT_STATUSES)),
        "permitting": tuple(sorted(RATE_LIMIT_SATISFYING)),
        "source_of_truth": SOT_REGISTRY,
        "decision_authority": None,
        "freshness_required": False,
        "why": (
            "whether a per-host rate limit policy is declared. Politeness is "
            "not optional, so an undeclared policy refuses."
        ),
    },
    {
        "fact_name": "user_agent_status",
        "guard_input": "user_agent_status",
        "vocabulary": tuple(sorted(USER_AGENT_STATUSES)),
        "permitting": ("canonical",),
        "source_of_truth": SOT_CANONICAL_UA,
        "decision_authority": None,
        "freshness_required": False,
        "why": (
            "whether the request would identify itself canonically. Derived by "
            "comparing against the one canonical string, not by a caller "
            "asserting it."
        ),
    },
    {
        "fact_name": "attribution_status",
        "guard_input": "attribution_status",
        "vocabulary": tuple(sorted(ATTRIBUTION_STATUSES)),
        "permitting": tuple(sorted(ATTRIBUTION_SATISFYING)),
        "source_of_truth": SOT_REGISTRY,
        "decision_authority": None,
        "freshness_required": False,
        "why": (
            "whether required attribution is present and verbatim. Applies "
            "where the source's terms demand it."
        ),
    },
    {
        "fact_name": "runtime_status",
        "guard_input": None,
        "vocabulary": ("ready", "not_ready", "unknown"),
        "permitting": ("ready",),
        "source_of_truth": SOT_RUNTIME,
        "decision_authority": None,
        "freshness_required": False,
        "why": (
            "whether the Gates 156-161 runtime can actually carry a collection. "
            "Necessary and emphatically not sufficient: a ready runtime "
            "authorizes nothing, which is the distinction this whole block "
            "exists to keep."
        ),
    },
)

FACT_NAMES: tuple[str, ...] = tuple(spec["fact_name"] for spec in FACT_SPECS)

#: The facts that are per-source human DECISIONS. Only these have an authority.
DECISION_FACTS: tuple[str, ...] = tuple(
    spec["fact_name"] for spec in FACT_SPECS if spec["decision_authority"]
)

#: Facts that expire.
FRESHNESS_FACTS: tuple[str, ...] = tuple(
    spec["fact_name"] for spec in FACT_SPECS if spec["freshness_required"]
)

#: Said once, here, because every artifact and doc in this gate repeats it.
NOT_AN_APPROVAL: tuple[str, ...] = (
    "a registered source is not an approved source",
    "an available adapter is not an approved source",
    "a queued job is not an approved source",
    "a schedulable source is not an approved source",
    "a ready runtime is not an approved source",
    "a successful hermetic execution is not an approved source",
    "an execution proof is not an approved source",
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def spec_for(fact_name: str) -> dict[str, Any] | None:
    for spec in FACT_SPECS:
        if spec["fact_name"] == fact_name:
            return dict(spec)
    return None


def _as_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def build_fact(
    *,
    fact_name: str,
    value: Any = None,
    recorded_at: Any = None,
    recorded_by: Any = None,
    expires_at: Any = None,
    evidence_ref: Any = None,
    now: Any = None,
    record_exists: bool | None = None,
    decision_verdict: Any = None,
) -> dict[str, Any]:
    """One recorded fact, and its status derived from what is actually there.

    `record_exists` distinguishes *no row* from *a row that says nothing*. When
    it is None it is inferred from `value`, which is right for measured facts
    and wrong for decisions - so the resolver passes it explicitly for those.

    `decision_verdict` is the REVIEWER'S OWN ANSWER, and it wins.

    Deriving status from `value` alone lost a real distinction: a reviewer who
    records `denied` naturally carries the guard status
    `TERMS_REVIEW_REQUIRED`, because the terms really do require review and the
    answer really was no. Reading only the guard value reported that refusal as
    `needs_review` - "waiting on a human" - about a source a human had already
    refused.
    """
    spec = spec_for(fact_name)
    if spec is None:
        return _json_safe(
            {
                "fact_name": fact_name,
                "fact_status": FACT_UNKNOWN,
                "value": None,
                "permits": False,
                "refusal_meaning": f"{fact_name} is not a fact this gate models",
                "source_of_truth": None,
            }
        )

    exists = bool(value is not None) if record_exists is None else bool(
        record_exists
    )
    text = None if value is None else str(value)
    permitting = set(spec["permitting"])
    vocabulary = set(spec["vocabulary"])

    moment = _as_datetime(now) or datetime.now(UTC)
    expiry = _as_datetime(expires_at)

    # ---- the status, derived in one place ------------------------------
    #
    # The reviewer's verdict outranks the guard value. See the docstring: a
    # `denied` decision carries a guard status that reads as "needs review",
    # and reading only the guard value turns a refusal into a wait.
    verdict = None if decision_verdict is None else str(decision_verdict)

    if not exists:
        status = FACT_MISSING
    elif verdict == "denied":
        status = FACT_DENIED
    elif verdict == "needs_review":
        status = FACT_NEEDS_REVIEW
    elif verdict == "unknown" and text not in permitting:
        status = FACT_UNKNOWN
    elif text is None or text not in vocabulary:
        # A row exists and its answer is not in the guard's vocabulary. That is
        # `unknown`, not `denied`: a column nobody populated is not a decision.
        status = FACT_UNKNOWN
    elif text in permitting:
        # Affirmative - unless it has expired, and only where expiry applies.
        if spec["freshness_required"] and expiry is not None and expiry <= moment:
            status = FACT_STALE
        else:
            status = FACT_RECORDED
    elif text in {"TERMS_REVIEW_REQUIRED", "HUMAN_REVIEW_ONLY", "open", "in_review"}:
        status = FACT_NEEDS_REVIEW
    elif text in {"UNKNOWN", "unknown", "activation_unknown"}:
        status = FACT_UNKNOWN
    else:
        status = FACT_DENIED

    return _json_safe(
        {
            "fact_name": fact_name,
            "guard_input": spec["guard_input"],
            "value": text,
            "fact_status": status,
            "permits": status in PERMITTING_FACT_STATUSES,
            "refusal_meaning": (
                None if status in PERMITTING_FACT_STATUSES
                else REFUSAL_MEANING.get(status)
            ),
            "source_of_truth": spec["source_of_truth"],
            "decision_authority": spec["decision_authority"],
            "recorded_at": recorded_at,
            "recorded_by": recorded_by,
            "expires_at": expires_at,
            "freshness_required": spec["freshness_required"],
            "evidence_ref": evidence_ref,
            "decision_verdict": verdict,
            "vocabulary": list(spec["vocabulary"]),
            "permitting_values": list(spec["permitting"]),
            "why_this_fact_exists": spec["why"],
        }
    )


def describe_fact_model() -> dict[str, Any]:
    """The whole model, for artifacts and for the docs to quote rather than
    restate."""
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "fact_names": list(FACT_NAMES),
            "fact_count": len(FACT_NAMES),
            "facts": [dict(spec) for spec in FACT_SPECS],
            "fact_statuses": list(FACT_STATUSES),
            "permitting_fact_statuses": sorted(PERMITTING_FACT_STATUSES),
            "refusal_meaning": REFUSAL_MEANING,
            "decision_facts": list(DECISION_FACTS),
            "freshness_facts": list(FRESHNESS_FACTS),
            "not_an_approval": list(NOT_AN_APPROVAL),
            "vocabularies_are_read_from": (
                "live_network_guard_service. This module restates none of them; "
                "a second copy of a vocabulary is a second thing to drift."
            ),
            "missing_is_not_denied": (
                "nobody has decided and somebody decided against are opposite "
                "operational situations with the same effect on permission. A "
                "boolean cannot tell them apart, so this model does not use one."
            ),
            "live_source_call": False,
            "source_monitoring_live": False,
        }
    )


def fact_invariant_failures(fact: dict[str, Any]) -> list[str]:
    """Refuse a fact that permits without evidence, or misreports its status."""
    fails: list[str] = []

    name = fact.get("fact_name")
    status = fact.get("fact_status")

    if status not in FACT_STATUSES:
        fails.append(f"fact_status_outside_vocabulary:{name}:{status}")

    # permits and fact_status must agree, both directions.
    permits = bool(fact.get("permits"))
    if permits != (status in PERMITTING_FACT_STATUSES):
        fails.append(f"permits_disagrees_with_status:{name}:{status}")

    # A permitting fact must carry a value that the guard actually accepts.
    if permits:
        value = fact.get("value")
        allowed = set(fact.get("permitting_values") or ())
        if value is None:
            fails.append(f"a_permitting_fact_with_no_value:{name}")
        elif allowed and value not in allowed:
            fails.append(f"a_permitting_fact_the_guard_would_refuse:{name}:{value}")

    # THE invariant of this module: a decision fact may not permit without
    # attribution. An approval nobody signed is not evidence.
    if permits and name in DECISION_FACTS:
        if not str(fact.get("recorded_by") or "").strip():
            fails.append(f"a_permitting_decision_with_no_recorded_by:{name}")
        if not str(fact.get("recorded_at") or "").strip():
            fails.append(f"a_permitting_decision_with_no_recorded_at:{name}")

    # A refusal must say which kind it is.
    if not permits and not str(fact.get("refusal_meaning") or "").strip():
        fails.append(f"a_refusing_fact_that_does_not_say_why:{name}")

    # Missing means missing. A value alongside it is a contradiction.
    if status == FACT_MISSING and fact.get("value") is not None:
        fails.append(f"a_missing_fact_that_carries_a_value:{name}")

    # A permitting fact whose recorded verdict was a refusal would mean the
    # verdict override had been bypassed.
    if permits and fact.get("decision_verdict") in {"denied", "needs_review"}:
        fails.append(
            f"a_permitting_fact_whose_reviewer_said_"
            f"{fact.get('decision_verdict')}:{name}"
        )

    return sorted(set(fails))
