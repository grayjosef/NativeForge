"""Gate 154B: one health model for controlled_dev_demo, from supplied facts.

## It measures nothing itself, deliberately

Every input arrives as an argument. This module opens no socket, starts no
subprocess and reads no file, so there is no path by which it could contact a
monitoring service, and none by which a health read could hang a request.

That is a constraint, not a limitation being apologised for: the facts it needs
already have owners. `backend_health_readiness_service` knows the git identity,
`systemctl` knows whether a unit is up, a verifier knows its own result. This
composes what they report and says what it means together.

## Unknown is a status, and it is not a pass

```text
operational   it works now, in controlled_dev_demo
degraded      it works, and something about it is wrong or stale
blocked       something specific stops it, and it is named
skipped       it correctly did not run; the Gate 61/65 harness lives here
unknown       nobody has determined it
```

A fact that was not supplied is `unknown`. It is never `operational`, and
`operational_health_ready` is false while any REQUIRED component is unknown -
because a health model that reports green for the things it forgot to look at
is worse than no health model.

## The three code identities

```text
repo HEAD          what the working tree is at
backend git_sha    what /backend/health reports
stamp git_sha      what the built SPA carries
```

Gate 154A proved `/backend/health` measures the REPOSITORY at request time, not
the process: a tracked edit flipped `source_dirty` with no restart. So a backend
sha that equals HEAD proves nothing about the running process, and this model
does not treat it as proof.

What it can say comes from time, not from a sha:

```text
process started BEFORE the HEAD commit   -> definitely stale
process started after, tree clean        -> probably current, and PROBABLY is
                                            the honest word: nothing records
                                            which commit the process loaded
tree dirty, edits OLDER than the start   -> operational, with a caveat. The
                                            running code is HEAD plus those
                                            edits, which is a complete answer.
tree dirty, edits NEWER than the start   -> definitely stale
tree dirty, edit time not supplied       -> unknown; nobody looked
```

A first draft made any dirty tree `unknown`, which closed the lane. That is not
what is known: a developer machine is dirty most of the time, and an edit made
before the process started is an edit the process contains.

## Production is a constant here

`production_monitoring_active` has no branch that computes it. The repository
already contains `gate32_observability_service.resolve_observability`, which
returns `production_monitoring: true` when a caller passes the right keyword
arguments. This module cannot be asked for that claim, and an invariant fails if
the key is ever anything but false.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_operational_health_model_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

OPERATIONAL = "operational"
DEGRADED = "degraded"
BLOCKED = "blocked"
SKIPPED = "skipped"
UNKNOWN = "unknown"

HEALTH_STATUSES: tuple[str, ...] = (
    OPERATIONAL,
    DEGRADED,
    BLOCKED,
    SKIPPED,
    UNKNOWN,
)

#: Lower is healthier. A model is as good as its worst REQUIRED component,
#: and `unknown` ranks below `blocked`: a named blocker is better understood
#: than a thing nobody looked at.
STATUS_RANK: dict[str, int] = {
    OPERATIONAL: 0,
    DEGRADED: 1,
    SKIPPED: 2,
    BLOCKED: 3,
    UNKNOWN: 4,
}

#: Components that must be known for the lane to be ready. A component outside
#: this set may be unknown without blocking - `skipped` verifiers, for one.
REQUIRED_COMPONENTS: tuple[str, ...] = (
    "backend_service",
    "preview_service",
    "tunnel_service",
    "migration_head",
    "frontend_stamp",
    "backend_code_freshness",
)

#: Lanes that are false BY DESIGN in controlled_dev_demo. Each is false
#: because a person has not decided something, not because anything broke.
#: A lane false and absent from this set is a real blocker - nobody declared
#: that one was supposed to be false.
EXPECTED_FALSE_LANES: frozenset[str] = frozenset(
    {
        "customer_auth_live",
        "verified_operational_binding",
        "consent_boundary_ready",
        "customer_beta_scope_approved",
        "source_monitoring_live",
        "email_delivery",
        "object_store_configured",
        "controlled_customer_pilot",
        "production_rollout",
        "production_backup_ready",
        "production_monitoring",
    }
)

AWAITING_HUMAN = "awaiting_human_decision"

#: Named states this model can report for the drift questions. Each is a
#: distinct operator situation with a distinct next action.
STALE_STAMP_MATCHES = "frontend_stamp_matches_head"
STALE_STAMP_OLDER = "frontend_stamp_is_older_than_head"
STALE_STAMP_MISSING = "frontend_stamp_is_absent_or_unstamped"
STALE_STAMP_UNKNOWN = "frontend_stamp_not_reported"

BACKEND_CODE_CURRENT = "backend_probably_running_head"
BACKEND_CODE_STALE = "backend_started_before_head_was_committed"
BACKEND_CODE_DIRTY = "backend_code_unknown_because_tree_is_dirty"
BACKEND_CODE_UNCOMMITTED = "backend_running_head_plus_uncommitted_edits"
BACKEND_CODE_EDITED_SINCE_START = "tracked_code_changed_after_the_process_started"
BACKEND_CODE_UNKNOWN = "backend_code_freshness_not_reported"

MIGRATION_MATCHES = "database_is_at_the_repository_head"
MIGRATION_BEHIND = "database_is_behind_the_repository_head"
MIGRATION_AHEAD = "database_is_ahead_of_the_repository_head"
MIGRATION_UNKNOWN = "migration_state_not_reported"


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _component(
    name: str,
    *,
    status: str,
    detail: str,
    blocker: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    normalized = status if status in STATUS_RANK else UNKNOWN
    return {
        "component": name,
        "status": normalized,
        "detail": detail,
        "blocker": blocker,
        "required": name in REQUIRED_COMPONENTS,
        **extra,
    }


def _service_component(name: str, state: Any) -> dict[str, Any]:
    """`systemctl is-active` output, or None when nobody asked."""
    if state is None:
        return _component(
            name,
            status=UNKNOWN,
            detail="no service state was supplied",
            blocker=f"{name}_state_unknown",
        )
    value = str(state).strip().lower()
    if value == "active":
        return _component(name, status=OPERATIONAL, detail="active", unit_state=value)
    return _component(
        name,
        status=BLOCKED,
        detail=f"unit reports {value}",
        blocker=f"{name}_not_active",
        unit_state=value,
    )


def _migration_component(repo_head: Any, database_current: Any) -> dict[str, Any]:
    if not repo_head or not database_current:
        return _component(
            "migration_head",
            status=UNKNOWN,
            detail="repository head or database revision was not supplied",
            blocker="migration_state_unknown",
            state=MIGRATION_UNKNOWN,
            repo_head=repo_head,
            database_current=database_current,
        )

    repo = str(repo_head).strip()
    current = str(database_current).strip()
    if repo == current:
        return _component(
            "migration_head",
            status=OPERATIONAL,
            detail=f"both at {repo}",
            state=MIGRATION_MATCHES,
            repo_head=repo,
            database_current=current,
        )
    # Revisions here are zero-padded and ordered, so a string compare is a
    # real comparison rather than a coincidence.
    state = MIGRATION_BEHIND if current < repo else MIGRATION_AHEAD
    return _component(
        "migration_head",
        status=BLOCKED,
        detail=f"repository at {repo}, database at {current}",
        blocker=state,
        state=state,
        repo_head=repo,
        database_current=current,
    )


def _stamp_component(repo_head_sha: Any, stamp_sha: Any) -> dict[str, Any]:
    if not stamp_sha:
        return _component(
            "frontend_stamp",
            status=BLOCKED if repo_head_sha else UNKNOWN,
            detail=(
                "no build sha was reported; a plain `npm run build` removes the "
                "stamp that `build_frontend_stamped.sh` writes"
            ),
            blocker=STALE_STAMP_MISSING,
            state=STALE_STAMP_MISSING,
        )
    if not repo_head_sha:
        return _component(
            "frontend_stamp",
            status=UNKNOWN,
            detail="a stamp was reported but there is nothing to compare it to",
            blocker="repo_head_sha_unknown",
            state=STALE_STAMP_UNKNOWN,
            stamp_sha=str(stamp_sha)[:12],
        )

    head = str(repo_head_sha).strip()
    stamp = str(stamp_sha).strip()
    if head == stamp:
        return _component(
            "frontend_stamp",
            status=OPERATIONAL,
            detail=f"stamped at {stamp[:12]}, which is HEAD",
            state=STALE_STAMP_MATCHES,
            stamp_sha=stamp[:12],
        )
    # Degraded, not blocked: the preview serves, it serves the wrong commit.
    # strict-public does not catch this - it only checks the tag exists.
    return _component(
        "frontend_stamp",
        status=DEGRADED,
        detail=(
            f"stamped at {stamp[:12]}, HEAD is {head[:12]}. strict-public "
            "passes on this because it only checks that the tag exists."
        ),
        blocker=STALE_STAMP_OLDER,
        state=STALE_STAMP_OLDER,
        stamp_sha=stamp[:12],
        head_sha=head[:12],
    )


def _backend_code_component(
    *,
    process_started_at: Any,
    head_committed_at: Any,
    source_dirty: Any,
    newest_tracked_change_at: Any = None,
) -> dict[str, Any]:
    """Freshness from TIME, because the sha cannot answer it.

    Gate 154A proved `/backend/health` reports the repository at request time.
    Comparing its `git_sha` to HEAD would always agree and would prove nothing,
    so this compares when the process started to when the code last changed.
    """
    if source_dirty:
        # A dirty tree is not automatically unknown. What matters is whether
        # the process started before or after the newest uncommitted edit.
        if not newest_tracked_change_at or not process_started_at:
            return _component(
                "backend_code_freshness",
                status=UNKNOWN,
                detail=(
                    "the tracked tree is dirty and nobody supplied when it was "
                    "last edited, so freshness cannot be established"
                ),
                blocker=BACKEND_CODE_DIRTY,
                state=BACKEND_CODE_DIRTY,
            )
        edited = str(newest_tracked_change_at)
        started = str(process_started_at)
        if edited > started:
            return _component(
                "backend_code_freshness",
                status=BLOCKED,
                detail=(
                    f"tracked code changed at {edited}, after the process "
                    f"started at {started}. The process cannot contain it."
                ),
                blocker=BACKEND_CODE_EDITED_SINCE_START,
                state=BACKEND_CODE_EDITED_SINCE_START,
                newest_tracked_change_at=edited,
                process_started_at=started,
            )
        return _component(
            "backend_code_freshness",
            status=OPERATIONAL,
            detail=(
                f"the tree has uncommitted edits, last changed {edited}, and "
                f"the process started after them at {started}. The running "
                "code is HEAD plus those edits - known, and not a commit."
            ),
            state=BACKEND_CODE_UNCOMMITTED,
            running_uncommitted_code=True,
            newest_tracked_change_at=edited,
            process_started_at=started,
        )
    if not process_started_at or not head_committed_at:
        return _component(
            "backend_code_freshness",
            status=UNKNOWN,
            detail="process start time or HEAD commit time was not supplied",
            blocker=BACKEND_CODE_UNKNOWN,
            state=BACKEND_CODE_UNKNOWN,
        )

    started = str(process_started_at)
    committed = str(head_committed_at)
    if started < committed:
        return _component(
            "backend_code_freshness",
            status=BLOCKED,
            detail=(
                f"process started {started}, HEAD committed {committed}. The "
                "running process cannot contain HEAD."
            ),
            blocker=BACKEND_CODE_STALE,
            state=BACKEND_CODE_STALE,
            process_started_at=started,
            head_committed_at=committed,
        )
    return _component(
        "backend_code_freshness",
        status=OPERATIONAL,
        detail=(
            f"process started {started}, after HEAD was committed {committed}, "
            "with a clean tree. PROBABLY current - nothing records which commit "
            "the process actually loaded."
        ),
        state=BACKEND_CODE_CURRENT,
        proof_strength="inferred_from_time_not_from_a_recorded_commit",
        process_started_at=started,
        head_committed_at=committed,
    )


def _lane_component(name: str, value: Any) -> dict[str, Any]:
    if value is None:
        return _component(
            f"lane:{name}",
            status=UNKNOWN,
            detail="lane value was not supplied",
            lane=name,
        )
    if value:
        return _component(
            f"lane:{name}",
            status=OPERATIONAL,
            detail=f"{name} is true for {CONTROLLED_SCOPE}",
            lane=name,
            value=True,
        )
    if name in EXPECTED_FALSE_LANES:
        # False on purpose. Not a health problem, and not this model's to fix.
        return _component(
            f"lane:{name}",
            status=SKIPPED,
            detail=f"{name} is false by design; a person has to decide",
            lane=name,
            value=False,
            awaiting_human_decision=True,
            awaiting=f"lane_false:{name}",
        )
    return _component(
        f"lane:{name}",
        status=BLOCKED,
        detail=f"{name} is false and was never declared as expected-false",
        blocker=f"lane_false:{name}",
        lane=name,
        value=False,
    )


def _verifier_component(name: str, result: Any, expected: Any) -> dict[str, Any]:
    """A verifier result, read against what that verifier is SUPPOSED to say.

    A `SKIP` from the Gate 61/65 production backup harness is the correct
    answer and must not be reported as a problem. A `SKIP` from a readiness
    verifier would be one.
    """
    if result is None:
        return _component(
            f"verifier:{name}",
            status=UNKNOWN,
            detail="this verifier was not run, or its result was not supplied",
            verifier=name,
            expected_result=expected,
        )
    seen = str(result).strip().upper()
    want = str(expected or "PASS").strip().upper()
    if seen == want:
        status = SKIPPED if seen == "SKIP" else OPERATIONAL
        return _component(
            f"verifier:{name}",
            status=status,
            detail=f"returned {seen}, which is what it is expected to return",
            verifier=name,
            result=seen,
            expected_result=want,
        )
    return _component(
        f"verifier:{name}",
        status=BLOCKED,
        detail=f"returned {seen}, expected {want}",
        blocker=f"verifier_result_unexpected:{name}",
        verifier=name,
        result=seen,
        expected_result=want,
    )


def build_operational_health_model(
    *,
    backend_service_state: Any = None,
    preview_service_state: Any = None,
    tunnel_service_state: Any = None,
    repo_head_sha: Any = None,
    head_committed_at: Any = None,
    source_dirty: Any = None,
    newest_tracked_change_at: Any = None,
    backend_process_started_at: Any = None,
    frontend_stamp_sha: Any = None,
    repo_migration_head: Any = None,
    database_migration_current: Any = None,
    lanes: dict[str, Any] | None = None,
    verifier_results: dict[str, Any] | None = None,
    verifier_expectations: dict[str, Any] | None = None,
    artifact_freshness: dict[str, Any] | None = None,
    extra_blockers: list[str] | None = None,
) -> dict[str, Any]:
    """Compose supplied facts into one health model. Measures nothing."""
    components: list[dict[str, Any]] = [
        _service_component("backend_service", backend_service_state),
        _service_component("preview_service", preview_service_state),
        _service_component("tunnel_service", tunnel_service_state),
        _migration_component(repo_migration_head, database_migration_current),
        _stamp_component(repo_head_sha, frontend_stamp_sha),
        _backend_code_component(
            process_started_at=backend_process_started_at,
            head_committed_at=head_committed_at,
            source_dirty=source_dirty,
            newest_tracked_change_at=newest_tracked_change_at,
        ),
    ]

    for name in sorted(lanes or {}):
        components.append(_lane_component(name, (lanes or {})[name]))

    expectations = verifier_expectations or {}
    for name in sorted(verifier_results or {}):
        components.append(
            _verifier_component(
                name, (verifier_results or {})[name], expectations.get(name)
            )
        )

    by_status: dict[str, int] = {status: 0 for status in HEALTH_STATUSES}
    for entry in components:
        by_status[entry["status"]] += 1

    required = [entry for entry in components if entry["required"]]
    required_unknown = [
        entry["component"] for entry in required if entry["status"] == UNKNOWN
    ]

    blockers = sorted(
        {
            *(
                str(entry["blocker"])
                for entry in components
                if entry["blocker"] and entry["status"] in (BLOCKED, DEGRADED, UNKNOWN)
            ),
            *(extra_blockers or []),
        }
    )

    # Kept apart from blockers on purpose: an operator can act on a blocker
    # and cannot act on any of these.
    awaiting_human = sorted(
        str(entry["awaiting"]) for entry in components if entry.get("awaiting")
    )

    # The model is as good as its worst REQUIRED component.
    overall = (
        max((entry["status"] for entry in required), key=lambda s: STATUS_RANK[s])
        if required
        else UNKNOWN
    )

    # Any blocker closes the lane, not just one on a REQUIRED component.
    #
    # A first draft weighed only required components, so an unexpected result
    # from a verifier - the Gate 61/65 production backup harness returning PASS
    # when it is expected to SKIP - was named in `blockers` and then ignored by
    # the verdict. `required` governs how much UNKNOWN is tolerated; it was
    # never meant to decide which faults count.
    ready = overall == OPERATIONAL and not required_unknown and not blockers

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            # Derived from the components. Never supplied.
            "operational_health_ready": ready,
            "overall_status": overall,
            "components": components,
            "component_count": len(components),
            "by_status": by_status,
            "required_components": list(REQUIRED_COMPONENTS),
            "required_unknown": sorted(required_unknown),
            "blockers": blockers,
            "awaiting_human_decision": awaiting_human,
            "awaiting_human_count": len(awaiting_human),
            "a_lane_false_by_design_is_not_a_health_problem": (
                "customer_auth_live, verified_operational_binding and the rest "
                "of EXPECTED_FALSE_LANES are false because a person has not "
                "decided. Counting those as blockers would keep this lane shut "
                "forever and send an operator to fix something unbroken."
            ),
            "artifact_freshness": dict(artifact_freshness or {}),
            "unknown_is_not_a_pass": (
                "a component nobody supplied is unknown, never operational, and "
                "a required unknown keeps the lane closed"
            ),
            # Constants. This module measures nothing and contacts nothing.
            "production_monitoring_active": False,
            "external_monitoring_configured": False,
            "alerting_configured": False,
            "shell_executed": False,
            "external_call_made": False,
            "email_sent": False,
            "live_source_called": False,
            "object_store_contacted": False,
            "real_organization_touched": False,
            "rows_written": 0,
        }
    )


def health_model_invariant_failures(model: dict[str, Any]) -> list[str]:
    """Refuse a model that went green without looking, or claimed monitoring."""
    fails: list[str] = []

    components = model.get("components") or []
    names = [entry.get("component") for entry in components]
    if len(names) != len(set(names)):
        fails.append("a_component_is_reported_twice")

    for entry in components:
        if entry.get("status") not in STATUS_RANK:
            fails.append(
                f"component_status_outside_vocabulary:{entry.get('component')}"
            )

    counted = {status: 0 for status in HEALTH_STATUSES}
    for entry in components:
        if entry.get("status") in counted:
            counted[entry["status"]] += 1
    if counted != (model.get("by_status") or {}):
        fails.append("by_status_disagrees_with_the_components")

    if model.get("component_count") != len(components):
        fails.append("component_count_disagrees")

    missing = set(REQUIRED_COMPONENTS) - set(names)
    if missing:
        fails.append(f"required_component_absent:{sorted(missing)}")

    if model.get("operational_health_ready"):
        if model.get("blockers"):
            fails.append("ready_alongside_blockers")
        if model.get("required_unknown"):
            fails.append("ready_while_a_required_component_is_unknown")
        if model.get("overall_status") != OPERATIONAL:
            fails.append("ready_while_overall_status_is_not_operational")
        for entry in components:
            if entry.get("required") and entry.get("status") != OPERATIONAL:
                fails.append(
                    f"ready_while_required_is_not_operational:{entry.get('component')}"
                )

    for flag in (
        "production_monitoring_active",
        "external_monitoring_configured",
        "alerting_configured",
        "shell_executed",
        "external_call_made",
        "email_sent",
        "live_source_called",
        "object_store_contacted",
        "real_organization_touched",
    ):
        if model.get(flag):
            fails.append(f"model_claimed:{flag}")

    if model.get("rows_written"):
        fails.append("model_wrote_rows")

    return sorted(set(fails))
