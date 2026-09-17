"""Resolve the live guard's inputs from records only (Gate 162E).

## The signature is the security property

```python
resolve_source_authorization_facts(
    *, connection, organization_id, source_id, now
)
```

Four parameters. None of them can assert a fact. There is no `terms_approved`,
no `activation_status`, no `allow_live_fetch`, no `**overrides` — so there is no
argument a caller could pass to make an unapproved source look approved.

That is the whole point of this module, and it is enforced structurally rather
than by validation: a parameter that does not exist cannot be misused. Gate
162's test suite parses this signature and fails if a fact-shaped parameter
ever appears.

Before this gate, the only way to reach the guard's permitted branch was to
hand it ten booleans. The guard was not wrong to accept them — it is a pure
decision function and its caller was supposed to know. Nobody had written the
caller that knows.

## Where each fact comes from, and how strong that is

Facts are not equally good evidence, and flattening them would make this
resolver look stronger than it is. Each carries `derivation_strength`:

```text
recorded_decision   a human signed a row. The strongest, and the only kind
                    that can authorize a source
recorded_registry   a curated file the repository ships
measured_runtime    observed at call time from live state
declared_policy     a constant this repository declares about itself
unresolvable        cannot be answered without doing the thing we are asking
                    permission for
```

`robots_status` is `unresolvable` for a REAL source. Knowing whether
robots.txt permits a path requires fetching robots.txt, which is a live HTTP
call. Gate 162 cannot make one, so every real source refuses on it — and Gate
163, whose job is the first live call, must fetch robots.txt *first* and record
the answer before anything else is permitted. That ordering is not incidental;
it is the politeness requirement arriving before the request it governs.

For a synthetic fixture on a `.invalid` host it resolves to `absent`, because
RFC 2606 guarantees that host cannot exist and therefore serves no robots file.
The first draft returned unresolvable for everything, which left `approved`
unreachable for every source and every refusal in this gate unfalsifiable.

## Missing stays missing

No fact is defaulted. A source with no terms row gets
`fact_status=missing`, not `terms_status=UNKNOWN`. The guard would refuse
either way; an operator reading the refusal needs to know whether to find the
reviewer or find the decision.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import sqlalchemy as sa

from nativeforge.repositories.source_authorization_decision_repository import (
    HUMAN_REVIEW,
    TERMS,
    get_decision,
)
from nativeforge.services.source_authorization_fact_model_service import (
    FACT_MISSING,
    FACT_NAMES,
    FACT_RECORDED,
    build_fact,
    fact_invariant_failures,
)
from nativeforge.services.source_authorization_fixture_registry_service import (
    is_fixture_source,
    merge_fixture_rows,
)
from nativeforge.services.source_runtime_readiness_fact_service import (
    build_runtime_readiness_facts,
)

SCHEMA_VERSION = "nf_source_authorization_fact_resolver_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

# ------------------------------------------------- derivation strengths

STRENGTH_DECISION = "recorded_decision"
STRENGTH_REGISTRY = "recorded_registry"
STRENGTH_MEASURED = "measured_runtime"
STRENGTH_DECLARED = "declared_policy"
STRENGTH_UNRESOLVABLE = "unresolvable"

STRENGTHS: tuple[str, ...] = (
    STRENGTH_DECISION,
    STRENGTH_REGISTRY,
    STRENGTH_MEASURED,
    STRENGTH_DECLARED,
    STRENGTH_UNRESOLVABLE,
)

#: Only a signed decision can authorize a source. The other strengths can
#: block, and can satisfy a technical prerequisite, but none of them is
#: permission.
AUTHORIZING_STRENGTHS: frozenset[str] = frozenset({STRENGTH_DECISION})

STRENGTH_BY_FACT: dict[str, str] = {
    "source_registered": STRENGTH_REGISTRY,
    "terms_status": STRENGTH_DECISION,
    "human_review_status": STRENGTH_DECISION,
    "activation_status": STRENGTH_DECISION,
    "collector_status": STRENGTH_MEASURED,
    # `unresolvable` for a real source - answering it needs the live fetch
    # we want permission for. `measured_runtime` for a .invalid fixture,
    # whose host RFC 2606 guarantees cannot exist.
    "robots_status": STRENGTH_UNRESOLVABLE,
    "credential_status": STRENGTH_MEASURED,
    "rate_limit_status": STRENGTH_DECLARED,
    "user_agent_status": STRENGTH_DECLARED,
    # Downstream of the terms decision, so it inherits that strength.
    "attribution_status": STRENGTH_DECISION,
    "runtime_status": STRENGTH_MEASURED,
}

#: Why robots cannot be answered here. Carried in the output so a reader does
#: not have to find this docstring.
ROBOTS_UNRESOLVABLE = (
    "answering this requires fetching robots.txt from the source, which is the "
    "live HTTP call we are asking permission to make. Gate 162 cannot make "
    "one. Gate 163 must fetch robots.txt first and record the answer before "
    "anything else is permitted."
)

#: The human-review verdict, mapped onto the fact model's vocabulary. The
#: decision table's words and the review-item table's words differ, and the
#: mapping is here rather than in either of them.
HUMAN_REVIEW_TO_FACT: dict[str, str] = {
    "approved": "approved",
    "denied": "rejected",
    "needs_review": "in_review",
    "unknown": "open",
}

ACTIVATION_SOURCES_TABLE = "nf_active_opportunity_sources"


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _fingerprint(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ------------------------------------------------------------- resolvers
#
# Each returns the kwargs `build_fact` needs. None of them takes a caller's
# opinion, and each says where it looked.


def _resolve_source_registered(registry_row: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "value": "registered" if registry_row else "unknown_source",
        "record_exists": registry_row is not None,
        "evidence_ref": (
            registry_row.get("canonical_source_id") if registry_row else None
        ),
    }


def _resolve_recorded_decision(
    *,
    connection: Any,
    organization_id: Any,
    source_id: Any,
    decision_kind: str,
) -> dict[str, Any]:
    """A signed row, or nothing. Never a default."""
    found = get_decision(
        connection=connection,
        organization_id=organization_id,
        source_id=source_id,
        decision_kind=decision_kind,
    )
    row = found.get("decision")
    if not row:
        # `record_exists=False` and no value. The fact model turns this into
        # `missing`, which is what an operator needs to see: nobody decided.
        return {"value": None, "record_exists": False}

    if decision_kind == TERMS:
        # The reviewer's answer already carries the guard's own vocabulary,
        # recorded at decision time so this is a read rather than a mapping
        # somebody remembers.
        value = row.get("guard_status")
    else:
        value = HUMAN_REVIEW_TO_FACT.get(str(row.get("decision")))

    return {
        "value": value,
        "record_exists": True,
        # The reviewer's own answer travels with the fact and outranks the
        # guard value when the two disagree about what happened.
        "decision_verdict": row.get("decision"),
        "recorded_at": row.get("reviewed_at"),
        "recorded_by": row.get("reviewed_by"),
        "expires_at": row.get("expires_at"),
        "evidence_ref": row.get("evidence_ref") or row.get("evidence_fingerprint"),
    }


def _resolve_activation(
    *, connection: Any, organization_id: Any, registry_row: dict[str, Any] | None
) -> dict[str, Any]:
    """Compose `nf_active_opportunity_sources`, which already owns this.

    Joined on `source_name`, because that table has no `source_id` column and
    the file-backed registry has no UUID. A name join is weaker than an id
    join and it is reported as such rather than quietly relied on - Gate 163
    should give these two id spaces a real key before it activates anything.
    """
    if connection is None or not registry_row:
        return {"value": None, "record_exists": False}

    name = registry_row.get("source_name")
    if not name:
        return {"value": None, "record_exists": False}

    try:
        metadata = sa.MetaData()
        table = sa.Table(
            ACTIVATION_SOURCES_TABLE,
            metadata,
            sa.Column("source_name", sa.Text()),
            sa.Column("source_status", sa.Text()),
            sa.Column("activation_approved_by", sa.Text()),
            sa.Column("activation_approved_at", sa.DateTime(timezone=True)),
            sa.Column("activation_approval_artifact_id", sa.Text()),
            sa.Column("disabled_at", sa.DateTime(timezone=True)),
        )
        row = connection.execute(
            sa.select(table).where(table.c.source_name == str(name))
        ).first()
    except Exception:  # noqa: BLE001 - an unreadable table records nothing
        return {"value": None, "record_exists": False}

    if row is None:
        return {"value": None, "record_exists": False}

    mapping = row._mapping
    if mapping.get("disabled_at") is not None:
        value = "activation_revoked"
    elif mapping.get("activation_approved_by") and mapping.get(
        "activation_approved_at"
    ):
        value = "activation_allowed"
    else:
        # A row exists and nobody signed it. `unknown`, not denied.
        value = "activation_unknown"

    return {
        "value": value,
        "record_exists": True,
        "recorded_at": mapping.get("activation_approved_at"),
        "recorded_by": mapping.get("activation_approved_by"),
        "evidence_ref": mapping.get("activation_approval_artifact_id"),
    }


def _resolve_robots(
    source_id: str, registry_row: dict[str, Any] | None
) -> dict[str, Any]:
    """`absent` for a host that cannot exist; unresolvable for a real one.

    For a real source, answering this requires fetching robots.txt - the live
    HTTP call we are asking permission to make - so it stays missing and Gate
    163 must fetch it first.

    For a synthetic fixture on a `.invalid` host, RFC 2606 guarantees the host
    cannot exist, so it serves no robots.txt. The guard's own
    `ROBOTS_SATISFYING` includes `absent` for exactly that case, and no request
    is needed to know it.

    The first draft returned unresolvable for everything, which made `approved`
    unreachable for every source and every refusal in this gate
    unfalsifiable.
    """
    if not registry_row:
        return {"value": None, "record_exists": False}

    if is_fixture_source(source_id):
        url = str(registry_row.get("source_url") or "")
        host = url.split("//", 1)[-1].split("/", 1)[0].lower()
        if host.endswith(".invalid"):
            return {
                "value": "absent",
                "record_exists": True,
                "evidence_ref": f"rfc2606:{host}_cannot_exist",
            }
        # A fixture pointing somewhere real is not a fixture we can answer for.
        return {"value": None, "record_exists": False}

    return {"value": None, "record_exists": False}


def _resolve_collector(
    registry_row: dict[str, Any] | None,
    *,
    source_id: str = "",
    connection: Any = None,
    organization_id: Any = None,
) -> dict[str, Any]:
    """Whether a collector for this source is running. Measured, not asked."""
    if not registry_row:
        return {"value": None, "record_exists": False}

    if is_fixture_source(source_id):
        # For a hermetic fixture, Gate 161's execution envelope IS the
        # collector - it builds the request, dispatches through the boundary
        # and persists the bytes. So the question is whether that envelope is
        # ready, which its own health lane MEASURES.
        try:
            from nativeforge.services.source_collector_execution_health_service import (  # noqa: E501
                build_execution_health,
            )

            # WITH the connection. The lane checks `attempt_table_exists`
            # by reading the table, so without one it reports not-ready and
            # the collector fact refused for a reason unrelated to collectors.
            ready = bool(
                build_execution_health(
                    connection=connection, organization_id=organization_id
                ).get("execution_envelope_ready")
            )
        except Exception:  # noqa: BLE001
            return {"value": None, "record_exists": False}
        return {
            "value": "active" if ready else "not_active",
            "record_exists": True,
            "evidence_ref": (
                "source_collector_execution_health_service:"
                "execution_envelope_ready"
            ),
        }

    try:
        from nativeforge.services.phase1_collector_activation_policy_service import (
            build_phase1_activation_matrix,
        )

        matrix = build_phase1_activation_matrix()
    except Exception:  # noqa: BLE001
        return {"value": None, "record_exists": False}

    # `collectors_active` is a COUNT, and it is zero. A count of zero is a
    # record that nothing is active, which is different from no record.
    active = int(matrix.get("collectors_active") or 0)
    return {
        "value": "active" if active else "not_active",
        "record_exists": True,
        "evidence_ref": "phase1_collector_activation_policy_service",
    }


def _resolve_credential(registry_row: dict[str, Any] | None) -> dict[str, Any]:
    """Whether a required credential is present. The VALUE is never read."""
    if not registry_row:
        return {"value": None, "record_exists": False}

    posture = str(registry_row.get("access_posture_hint") or "").strip().lower()
    if posture == "public":
        # A public source needs none, which satisfies the guard.
        return {
            "value": "not_required",
            "record_exists": True,
            "evidence_ref": "registry:access_posture_hint=public",
        }
    # Anything else needs one and nobody has configured it. Deliberately NOT
    # checking a settings value here: this gate has no credential to check and
    # inventing a "present" answer is the one thing that must not happen.
    return {
        "value": "unknown",
        "record_exists": True,
        "evidence_ref": f"registry:access_posture_hint={posture or 'absent'}",
    }


def _resolve_rate_limit() -> dict[str, Any]:
    """Whether a politeness policy is declared. It is, globally, in the guard."""
    try:
        from nativeforge.services.live_network_guard_service import (
            MIN_REQUEST_INTERVAL_SECONDS,
            PER_HOST_CONCURRENCY,
        )
    except ImportError:
        return {"value": None, "record_exists": False}

    declared = bool(MIN_REQUEST_INTERVAL_SECONDS and PER_HOST_CONCURRENCY)
    return {
        "value": "policy_declared" if declared else "missing",
        "record_exists": True,
        "evidence_ref": (
            f"live_network_guard_service:min_interval="
            f"{MIN_REQUEST_INTERVAL_SECONDS}s,concurrency={PER_HOST_CONCURRENCY}"
        ),
    }


def _resolve_user_agent() -> dict[str, Any]:
    """Derived by comparing against the one canonical string."""
    try:
        from nativeforge.services.live_network_guard_service import (
            canonical_user_agent,
            user_agent_status_for,
        )

        canonical = canonical_user_agent()
        status = user_agent_status_for(canonical)
    except Exception:  # noqa: BLE001
        return {"value": None, "record_exists": False}

    return {
        "value": status,
        "record_exists": True,
        "evidence_ref": "live_network_guard_service.canonical_user_agent",
    }


def _resolve_attribution(terms_fact: dict[str, Any]) -> dict[str, Any]:
    """Derived from the recorded TERMS decision, and from nothing else.

    Whether a source demands attribution is part of what a reviewer decides
    when they read its terms - `ATTRIBUTION_REQUIRED` is a member of the
    guard's own terms vocabulary. So attribution is strictly downstream of
    terms, which is correct: nobody can say whether attribution is required
    until somebody has read the document.

    The first draft called `grants_gov_output_may_be_customer_visible()` with
    no arguments, caught the TypeError, and reported `missing` for every
    source - a refusal that had nothing to do with attribution. That function
    also asks a different question: whether a RENDERED SURFACE carries the
    verbatim notice, which is checked at render time against a trust manifest,
    not here.
    """
    terms_value = terms_fact.get("value")

    if terms_value is None:
        # No terms decision, so it is unknown whether attribution is required.
        return {"value": None, "record_exists": False}

    if terms_value == "ATTRIBUTION_REQUIRED":
        # The terms demand it. Whether a surface actually carries the verbatim
        # notice is a render-time fact, and nobody has recorded one - so this
        # refuses, and names attribution as the thing to go and record.
        return {
            "value": None,
            "record_exists": False,
            "evidence_ref": "terms_decision:ATTRIBUTION_REQUIRED",
        }

    if terms_value == "NO_REVIEW_REQUIRED":
        return {
            "value": "not_required",
            "record_exists": True,
            # The terms reviewer IS the attribution authority: attribution is
            # part of what they decided when they read the terms. A fact that
            # inherits a decision's strength must inherit its signature too,
            # or it claims the weight of a human judgement while being
            # unattributable.
            "recorded_at": terms_fact.get("recorded_at"),
            "recorded_by": terms_fact.get("recorded_by"),
            "evidence_ref": "derived_from_terms_decision:NO_REVIEW_REQUIRED",
        }

    # Any other terms status blocks on its own; attribution is moot and is
    # reported as unknown rather than as satisfied.
    return {
        "value": "unknown",
        "record_exists": True,
        "evidence_ref": f"terms_decision:{terms_value}",
    }


def _resolve_runtime(
    *, connection: Any, organization_id: Any, source_id: str = ""
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Which lanes a collection needs depends on what kind it would be.

    A real source collection needs the whole `REQUIRED_FOR_COLLECTION` set: a
    job store to record the work, a worker to run it, a payload store for the
    bytes, and the execution envelope.

    A hermetic fixture collection needs only the envelope. Requiring a
    scheduler and an orchestration runtime for a one-shot fixture that uses
    neither would make the permitted branch depend on machinery irrelevant to
    it - and would leave `approved` unreachable, which is what the first draft
    of this resolver did.
    """
    facts = build_runtime_readiness_facts(
        connection=connection, organization_id=organization_id
    )

    if is_fixture_source(source_id):
        lane = (facts.get("lanes") or {}).get(
            "collector_execution_envelope_ready"
        ) or {}
        ready = lane.get("status") == "ready"
        return (
            {
                "value": "ready" if ready else "not_ready",
                "record_exists": True,
                "evidence_ref": (
                    "source_runtime_readiness_fact_service:"
                    "collector_execution_envelope_ready"
                ),
            },
            facts,
        )

    return (
        {
            "value": facts["runtime_status"],
            "record_exists": True,
            "evidence_ref": "source_runtime_readiness_fact_service",
        },
        facts,
    )


# -------------------------------------------------------------- the resolver


def resolve_source_authorization_facts(
    *,
    connection: Any = None,
    organization_id: Any = None,
    source_id: Any = None,
    now: Any = None,
) -> dict[str, Any]:
    """Every guard input for one source, from records.

    Four parameters, none of which can assert a fact. There is deliberately no
    way to pass a status, a boolean or an override: a parameter that does not
    exist cannot be misused, and Gate 162's tests parse this signature to keep
    it that way.
    """
    try:
        from nativeforge.services.source_monitoring_approved_source_service import (
            load_registry_rows,
        )

        shipped = load_registry_rows()
    except Exception:  # noqa: BLE001 - an unreadable registry knows nothing
        shipped = {}

    # Synthetic fixtures, merged without being asked. Gate 162G explains why:
    # an unreachable permitted branch makes every refusal here unfalsifiable,
    # so something must be able to reach approved - and it must not be one of
    # the 177 real sources. The fixture space is a reserved prefix declared in
    # source code, which is why this is a merge and not a parameter.
    registry = merge_fixture_rows(shipped)

    key = str(source_id or "")
    registry_row = registry.get(key)

    resolved: dict[str, Any] = {}
    failures: list[str] = []

    resolved["source_registered"] = _resolve_source_registered(registry_row)
    resolved["terms_status"] = _resolve_recorded_decision(
        connection=connection,
        organization_id=organization_id,
        source_id=source_id,
        decision_kind=TERMS,
    )
    resolved["human_review_status"] = _resolve_recorded_decision(
        connection=connection,
        organization_id=organization_id,
        source_id=source_id,
        decision_kind=HUMAN_REVIEW,
    )
    resolved["activation_status"] = _resolve_activation(
        connection=connection,
        organization_id=organization_id,
        registry_row=registry_row,
    )
    resolved["collector_status"] = _resolve_collector(
        registry_row,
        source_id=key,
        connection=connection,
        organization_id=organization_id,
    )
    resolved["robots_status"] = _resolve_robots(key, registry_row)
    resolved["credential_status"] = _resolve_credential(registry_row)
    resolved["rate_limit_status"] = _resolve_rate_limit()
    resolved["user_agent_status"] = _resolve_user_agent()
    # AFTER terms, because attribution is derived from the terms decision.
    resolved["attribution_status"] = _resolve_attribution(
        resolved["terms_status"]
    )
    runtime_kwargs, runtime_facts = _resolve_runtime(
        connection=connection, organization_id=organization_id, source_id=key
    )
    resolved["runtime_status"] = runtime_kwargs

    facts: dict[str, Any] = {}
    for name in FACT_NAMES:
        fact = build_fact(fact_name=name, now=now, **resolved[name])
        fact["derivation_strength"] = STRENGTH_BY_FACT[name]
        if name == "robots_status":
            fact["unresolvable_because"] = ROBOTS_UNRESOLVABLE
        facts[name] = fact
        failures.extend(fact_invariant_failures(fact))

    missing = sorted(
        name for name, f in facts.items() if f["fact_status"] == FACT_MISSING
    )
    denied = sorted(
        name for name, f in facts.items() if f["fact_status"] == "denied"
    )
    stale = sorted(name for name, f in facts.items() if f["fact_status"] == "stale")
    needs_review = sorted(
        name for name, f in facts.items() if f["fact_status"] == "needs_review"
    )
    unknown = sorted(
        name for name, f in facts.items() if f["fact_status"] == "unknown"
    )
    satisfied = sorted(
        name for name, f in facts.items() if f["fact_status"] == FACT_RECORDED
    )

    authorization_ready = len(satisfied) == len(FACT_NAMES)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "source_id": key or None,
            "source_registered": registry_row is not None,
            # A fixture is recognised by BOTH its reserved prefix and its
            # declared membership. Reported so a reader of any resolution
            # can tell a synthetic source from a real one at a glance.
            "is_synthetic_fixture": is_fixture_source(key),
            "shipped_registry_count": len(shipped),
            "source_name_fingerprint": _fingerprint(
                (registry_row or {}).get("source_name")
            ),
            "required_facts": list(FACT_NAMES),
            "required_fact_count": len(FACT_NAMES),
            "resolved_facts": facts,
            "facts_satisfied": satisfied,
            "missing_facts": missing,
            "denied_facts": denied,
            "stale_facts": stale,
            "needs_review_facts": needs_review,
            "unknown_facts": unknown,
            "authorization_ready": authorization_ready,
            # Separate from authorization_ready on purpose. Gate 162 has no
            # live transport to permit even if every fact were satisfied, so
            # this is hardcoded False and Gate 163 is where it stops being.
            "live_transport_permitted": False,
            "why_live_transport_stays_refused": (
                "Gate 161's transport boundary has no live implementation and "
                "`live` is not in DISPATCHABLE_KINDS. Authorization and "
                "capability are separate questions, and this gate answers only "
                "the first."
            ),
            "derivation_strengths": dict(STRENGTH_BY_FACT),
            "authorizing_strengths": sorted(AUTHORIZING_STRENGTHS),
            "runtime_facts": runtime_facts,
            "invariant_failures": sorted(set(failures)),
            # ---- what a caller could not do -----------------------------
            "caller_supplied_facts_accepted": 0,
            "resolver_parameters": [
                "connection",
                "organization_id",
                "source_id",
                "now",
            ],
            "no_parameter_can_assert_a_fact": True,
            "live_source_call": False,
            "network_calls": 0,
            "source_monitoring_live": False,
        }
    )


def resolver_invariant_failures(resolution: dict[str, Any]) -> list[str]:
    """Refuse a resolution that authorizes without signed evidence."""
    fails: list[str] = list(resolution.get("invariant_failures") or [])

    facts = resolution.get("resolved_facts") or {}
    expected = set(resolution.get("required_facts") or ())
    if expected and set(facts) != expected:
        fails.append("resolved_facts_do_not_match_the_required_set")

    # Every fact must be accounted for in exactly one bucket.
    buckets = (
        "facts_satisfied",
        "missing_facts",
        "denied_facts",
        "stale_facts",
        "needs_review_facts",
        "unknown_facts",
    )
    counted: list[str] = []
    for bucket in buckets:
        counted.extend(resolution.get(bucket) or [])
    if sorted(counted) != sorted(facts):
        fails.append("a_fact_was_double_counted_or_unaccounted_for")

    ready = bool(resolution.get("authorization_ready"))

    # ready and the buckets must agree, both directions.
    unsatisfied = sum(
        len(resolution.get(bucket) or [])
        for bucket in buckets
        if bucket != "facts_satisfied"
    )
    if ready and unsatisfied:
        fails.append("authorization_ready_alongside_unsatisfied_facts")
    if not ready and not unsatisfied:
        fails.append("not_ready_without_naming_an_unsatisfied_fact")

    # THE invariant of this module: a source cannot be authorized unless every
    # authorizing-strength fact is a signed decision. A ready runtime, a
    # declared policy and a registry row are prerequisites, never permission.
    if ready:
        strengths = resolution.get("derivation_strengths") or {}
        for name, fact in facts.items():
            if strengths.get(name) not in AUTHORIZING_STRENGTHS:
                continue
            if not fact.get("recorded_by"):
                fails.append(f"authorized_without_a_signer:{name}")
            if not fact.get("recorded_at"):
                fails.append(f"authorized_without_a_decision_time:{name}")

    # No caller input, ever.
    if int(resolution.get("caller_supplied_facts_accepted") or 0):
        fails.append("the_resolver_accepted_a_caller_supplied_fact")
    if not resolution.get("no_parameter_can_assert_a_fact"):
        fails.append("the_resolver_exposes_a_parameter_that_asserts_a_fact")

    # Gate 162 permits no live transport regardless of authorization.
    if resolution.get("live_transport_permitted"):
        fails.append("the_resolver_permitted_a_live_transport")
    for flag in ("live_source_call", "source_monitoring_live"):
        if resolution.get(flag):
            fails.append(f"resolver_claimed:{flag}")

    return sorted(set(fails))
