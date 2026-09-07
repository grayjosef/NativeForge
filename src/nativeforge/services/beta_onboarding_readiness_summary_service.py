"""Gate 144B: what this deployment can actually do, lane by lane.

## The defect this module is most likely to introduce

Several readiness services take injectable proofs so their permitted branches
stay reachable — `tenant_digest_operational` needs a route smoke,
`document_body_storage_ready` needs a body-route proof. A summary that supplied
those proofs itself would be **grading its own homework**: reporting `true` for
a lane whose evidence it invented.

So every lane here is measured by the lane's own service with **no proof
supplied**, and a lane that cannot establish itself unaided is reported
`readiness_only` or `blocked` — never `operational`. `LANE_EVIDENCE` records,
per lane, what the summary is allowed to conclude on its own.

## Seven statuses, because "not ready" hides six situations

```text
operational               it works now, in controlled_dev_demo
readiness_only            the code is proved; the capability is not activated
preview_only              it produces something, and delivers nothing
blocked                   something specific stops it, and it is named
not_configured            settings are absent
requires_human_approval   a person has to decide, and no code can
production_false          deliberately false, and this gate cannot change it
```

An operator asking "why can't I use this" gets a different answer for each, with
a different owner.

## Nothing here changes a lane

This module reads. It activates nothing, contacts nothing and writes nothing,
and an invariant fails if any lane it reports as false is ever reported true by
it.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_beta_onboarding_readiness_summary_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

OPERATIONAL = "operational"
READINESS_ONLY = "readiness_only"
PREVIEW_ONLY = "preview_only"
BLOCKED = "blocked"
NOT_CONFIGURED = "not_configured"
REQUIRES_HUMAN_APPROVAL = "requires_human_approval"
PRODUCTION_FALSE = "production_false"

LANE_STATUSES: tuple[str, ...] = (
    OPERATIONAL,
    READINESS_ONLY,
    PREVIEW_ONLY,
    BLOCKED,
    NOT_CONFIGURED,
    REQUIRES_HUMAN_APPROVAL,
    PRODUCTION_FALSE,
)

#: Statuses that mean a tenant could use the thing today.
USABLE_STATUSES: frozenset[str] = frozenset({OPERATIONAL, PREVIEW_ONLY})

#: Every lane the cockpit reports, in the order an operator would read them.
LANE_KEYS: tuple[str, ...] = (
    "login",
    "customer_persistence",
    "awarded_grants",
    "tenant_digest",
    "document_metadata",
    "document_body_storage",
    "email_delivery_readiness",
    "email_delivery",
    "source_monitoring_preflight",
    "source_monitoring",
    "object_storage",
    "customer_auth",
    "verified_operational_binding",
    "controlled_customer_pilot",
    "production_rollout",
)

#: What this summary is allowed to conclude on its own, per lane.
#:
#: `self_evidencing` lanes derive fully from their own service with nothing
#: supplied. The rest need evidence a summary cannot honestly produce - a route
#: smoke against a live server, a hermetic adapter proof - so the summary
#: reports what it CAN see and never upgrades them to operational by assuming.
LANE_EVIDENCE: dict[str, str] = {
    "login": "self_evidencing",
    "customer_persistence": "needs_a_database_round_trip",
    "awarded_grants": "needs_a_route_smoke",
    "tenant_digest": "needs_a_route_smoke",
    "document_metadata": "needs_a_route_smoke",
    "document_body_storage": "self_evidencing",
    "email_delivery_readiness": "needs_a_route_smoke",
    "email_delivery": "self_evidencing",
    "source_monitoring_preflight": "self_evidencing",
    "source_monitoring": "self_evidencing",
    "object_storage": "self_evidencing",
    "customer_auth": "self_evidencing",
    "verified_operational_binding": "self_evidencing",
    "controlled_customer_pilot": "self_evidencing",
    "production_rollout": "self_evidencing",
}

#: Lanes this gate may never report as true, whatever it is handed.
NEVER_TRUE_LANES: frozenset[str] = frozenset(
    {
        "email_delivery",
        "source_monitoring",
        "object_storage",
        "customer_auth",
        "verified_operational_binding",
        "controlled_customer_pilot",
        "production_rollout",
    }
)

#: Claims this module never makes.
NOT_APPROVED: tuple[str, ...] = (
    "production_rollout",
    "controlled_customer_pilot",
    "customer_auth_live",
    "source_monitoring_live",
    "email_delivery",
    "object_store_configured",
    "verified_operational_binding",
)

#: The next thing that is safe to do. One action, not a backlog: an operator
#: reading a cockpit needs to know what to do next, not everything that could
#: eventually be done.
NEXT_SAFE_ACTION = {
    "action": "finish_the_controlled_beta_readiness_matrix",
    "why": (
        "every controlled_dev_demo lane that can be proved is proved; the "
        "remaining lanes need a human decision or an external activation, and "
        "neither is a code change"
    ),
    "safe_because": (
        "it activates nothing, contacts nothing and changes no lane's value"
    ),
    "not_this_yet": [
        "activating a controlled customer pilot",
        "binding the real organization",
        "configuring an email provider",
        "configuring an object store",
        "starting a collector",
    ],
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _lane(
    key: str,
    *,
    status: str,
    value: bool,
    scope: str | None,
    summary: str,
    blockers: list[str] | None = None,
    owner: str | None = None,
) -> dict[str, Any]:
    return {
        "lane": key,
        "status": status,
        "value": bool(value),
        "scope": scope,
        "summary": summary,
        "evidence": LANE_EVIDENCE.get(key, "unknown"),
        "blockers": sorted(set(blockers or [])),
        "owner": owner,
        "usable_today": status in USABLE_STATUSES,
    }


def build_beta_onboarding_summary(
    *,
    login_live: bool | None = None,
    customer_persistence_live: bool | None = None,
    awarded_operational_tracking: bool | None = None,
    tenant_digest_operational: bool | None = None,
    document_metadata_operational: bool | None = None,
    email_delivery_readiness: bool | None = None,
    source_monitoring_preflight_ready: bool | None = None,
) -> dict[str, Any]:
    """Every lane, measured. Activates nothing and contacts nothing.

    The seven parameters are the lanes whose own services need evidence this
    summary cannot honestly produce - a route smoke, a database round trip. A
    caller that ran the verifier supplies what it measured; a caller that did
    not gets `readiness_only`, never a guess.
    """
    from nativeforge.services.document_storage_readiness_service import (
        build_document_storage_readiness,
    )
    from nativeforge.services.email_provider_configuration_preflight_service import (
        build_email_provider_preflight,
    )
    from nativeforge.services.source_monitoring_readiness_service import (
        build_source_monitoring_readiness,
    )
    from nativeforge.services.source_scheduler_readiness_service import (
        build_scheduler_readiness,
    )

    # -- the self-evidencing measurements ----------------------------------
    storage = build_document_storage_readiness(metadata_route_smoke=None)
    email = build_email_provider_preflight()
    scheduler = build_scheduler_readiness()
    monitoring = build_source_monitoring_readiness(measure=True)

    lanes: list[dict[str, Any]] = []

    # -- login --------------------------------------------------------------
    login = bool(login_live) if login_live is not None else False
    lanes.append(
        _lane(
            "login",
            status=OPERATIONAL if login else BLOCKED,
            value=login,
            scope=CONTROLLED_SCOPE if login else None,
            summary=(
                "a person can sign in with Google and reach their organization"
                if login
                else "sign-in was not proved by this run"
            ),
            blockers=[] if login else ["no_login_proof_was_supplied"],
            owner=None if login else "the live stack verifier",
        )
    )

    # -- customer persistence ----------------------------------------------
    persistence = (
        bool(customer_persistence_live)
        if customer_persistence_live is not None
        else False
    )
    lanes.append(
        _lane(
            "customer_persistence",
            status=OPERATIONAL if persistence else READINESS_ONLY,
            value=persistence,
            scope=CONTROLLED_SCOPE if persistence else None,
            summary=(
                "tenant rows write, read back and archive, anchored on organization_id"
                if persistence
                else "the round trip needs a database and was not run here"
            ),
            blockers=[] if persistence else ["no_persistence_round_trip_was_run"],
            owner=None if persistence else "the persistence verifier",
        )
    )

    # -- awarded grants ------------------------------------------------------
    awarded = (
        bool(awarded_operational_tracking)
        if awarded_operational_tracking is not None
        else False
    )
    lanes.append(
        _lane(
            "awarded_grants",
            status=OPERATIONAL if awarded else READINESS_ONLY,
            value=awarded,
            scope=CONTROLLED_SCOPE if awarded else None,
            summary=(
                "awards, requirements, proof events and document references "
                "round-trip through authenticated routes"
                if awarded
                else "the four lanes need a route smoke and none was supplied"
            ),
            blockers=[] if awarded else ["no_route_smoke_was_supplied"],
            owner=None if awarded else "the awarded verifier",
        )
    )

    # -- tenant digest -------------------------------------------------------
    digest = (
        bool(tenant_digest_operational)
        if tenant_digest_operational is not None
        else False
    )
    lanes.append(
        _lane(
            "tenant_digest",
            status=OPERATIONAL if digest else READINESS_ONLY,
            value=digest,
            scope=CONTROLLED_SCOPE if digest else None,
            summary=(
                "a weekly digest previews from labelled fixture snapshots, "
                "daily is opt-in, and suppression is audit-backed"
                if digest
                else "the digest needs a route smoke and none was supplied"
            ),
            blockers=[] if digest else ["no_route_smoke_was_supplied"],
            owner=None if digest else "the tenant digest verifier",
        )
    )

    # -- document metadata ---------------------------------------------------
    metadata = (
        bool(document_metadata_operational)
        if document_metadata_operational is not None
        else False
    )
    lanes.append(
        _lane(
            "document_metadata",
            status=OPERATIONAL if metadata else READINESS_ONLY,
            value=metadata,
            scope=CONTROLLED_SCOPE if metadata else None,
            summary=(
                "a document REFERENCE records, reads back and archives; its "
                "bytes live nowhere and every route says so"
                if metadata
                else "the metadata lane needs a route smoke and none was supplied"
            ),
            blockers=[] if metadata else ["no_route_smoke_was_supplied"],
            owner=None if metadata else "the document storage verifier",
        )
    )

    # -- document body storage -----------------------------------------------
    lanes.append(
        _lane(
            "document_body_storage",
            status=NOT_CONFIGURED,
            value=bool(storage["document_body_storage_ready"]),
            scope=None,
            summary=(
                "there is nowhere for a document's bytes to live; the route "
                "refuses by name and names the missing settings"
            ),
            blockers=sorted(
                set(storage["blocked_reasons"])
                | {f"object_storage_setting_absent:{n}" for n in []}
            )
            or ["object_storage_is_not_configured"],
            owner="whoever chooses and configures an object store",
        )
    )

    # -- email delivery readiness --------------------------------------------
    email_ready = (
        bool(email_delivery_readiness)
        if email_delivery_readiness is not None
        else False
    )
    lanes.append(
        _lane(
            "email_delivery_readiness",
            status=OPERATIONAL if email_ready else READINESS_ONLY,
            value=email_ready,
            scope=CONTROLLED_SCOPE if email_ready else None,
            summary=(
                "a digest renders, a recipient validates to a fingerprint, an "
                "intent is recorded and audited - and nothing is sent"
                if email_ready
                else "the rehearsal needs a route smoke and none was supplied"
            ),
            blockers=[] if email_ready else ["no_route_smoke_was_supplied"],
            owner=None if email_ready else "the email readiness verifier",
        )
    )

    # -- actual email delivery -----------------------------------------------
    lanes.append(
        _lane(
            "email_delivery",
            status=NOT_CONFIGURED,
            value=bool(email["email_delivery"]),
            scope=None,
            summary=(
                "no provider is configured and nobody has activated sending; "
                "a rehearsal cannot make this true"
            ),
            blockers=sorted(set(email["blocked_reasons"])),
            owner="whoever chooses a provider and decides to send",
        )
    )

    # -- source monitoring preflight -----------------------------------------
    preflight = (
        bool(source_monitoring_preflight_ready)
        if source_monitoring_preflight_ready is not None
        else bool(monitoring["source_monitoring_preflight_ready"])
    )
    lanes.append(
        _lane(
            "source_monitoring_preflight",
            status=OPERATIONAL if preflight else READINESS_ONLY,
            value=preflight,
            scope=CONTROLLED_SCOPE if preflight else None,
            summary=(
                "every registry source is classified and the system can say "
                "exactly what blocks monitoring each - without calling one"
                if preflight
                else "the preflight needs a collector proof and none was supplied"
            ),
            blockers=[] if preflight else sorted(set(monitoring["blocked_reasons"])),
            owner=None if preflight else "the source monitoring verifier",
        )
    )

    # -- actual source monitoring --------------------------------------------
    monitoring_blockers = [
        f"scheduler_component_absent:{name}"
        for name in (scheduler.get("components_missing") or [])
    ]
    monitoring_blockers.append("terms_review_incomplete")
    lanes.append(
        _lane(
            "source_monitoring",
            status=BLOCKED,
            value=bool(scheduler.get("source_monitoring_live")),
            scope=None,
            summary=(
                "no source is cleared for collection and nothing could run a "
                "check; the runtime mode is a dry run"
            ),
            blockers=monitoring_blockers,
            owner="a human reviewing terms, then a later gate for the scheduler",
        )
    )

    # -- object storage -------------------------------------------------------
    lanes.append(
        _lane(
            "object_storage",
            status=NOT_CONFIGURED,
            value=bool(storage["object_store_configured"]),
            scope=None,
            summary="five settings are absent and no SDK is installed",
            blockers=["object_storage_settings_absent", "no_owner_decision"],
            owner="whoever chooses and configures an object store",
        )
    )

    # -- customer auth --------------------------------------------------------
    lanes.append(
        _lane(
            "customer_auth",
            status=REQUIRES_HUMAN_APPROVAL,
            value=False,
            scope=None,
            summary=(
                "a second real person has to accept a real invite; nothing in "
                "code can stand in for that"
            ),
            blockers=["invite_binding_passed"],
            owner="a second person, and the owner who invites them",
        )
    )

    # -- verified operational binding ------------------------------------------
    lanes.append(
        _lane(
            "verified_operational_binding",
            status=REQUIRES_HUMAN_APPROVAL,
            value=False,
            scope=None,
            summary="Gate 137's two-part owner decision has not been made",
            blockers=["owner_decision_absent"],
            owner="the owner",
        )
    )

    # -- the two that are simply not approved -----------------------------------
    lanes.append(
        _lane(
            "controlled_customer_pilot",
            status=PRODUCTION_FALSE,
            value=False,
            scope=None,
            summary="not approved, and this gate does not approve it",
            blockers=["pilot_not_approved"],
            owner="the owner",
        )
    )
    lanes.append(
        _lane(
            "production_rollout",
            status=PRODUCTION_FALSE,
            value=False,
            scope=None,
            summary="not approved, and no lane above is a production claim",
            blockers=["production_not_approved"],
            owner="the owner",
        )
    )

    by_lane = {lane["lane"]: lane for lane in lanes}
    operational = sorted(k for k, v in by_lane.items() if v["status"] == OPERATIONAL)
    blocked = sorted(k for k, v in by_lane.items() if v["status"] == BLOCKED)
    needs_human = sorted(
        k for k, v in by_lane.items() if v["status"] == REQUIRES_HUMAN_APPROVAL
    )
    not_configured = sorted(
        k for k, v in by_lane.items() if v["status"] == NOT_CONFIGURED
    )

    missing = [key for key in LANE_KEYS if key not in by_lane]
    blocked_reasons = [f"lane_missing:{key}" for key in missing]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "lane_keys": list(LANE_KEYS),
            "lane_statuses": list(LANE_STATUSES),
            "lanes": [by_lane[key] for key in LANE_KEYS if key in by_lane],
            "by_lane": by_lane,
            "operational_lanes": operational,
            "blocked_lanes": blocked,
            "requires_human_approval_lanes": needs_human,
            "not_configured_lanes": not_configured,
            "usable_today_count": sum(1 for lane in lanes if lane["usable_today"]),
            "next_safe_action": dict(NEXT_SAFE_ACTION),
            # Constants. No branch sets any of them.
            "production_rollout": False,
            "controlled_customer_pilot": False,
            "customer_auth_live": False,
            "source_monitoring_live": False,
            "email_delivery": False,
            "object_store_configured": False,
            "verified_operational_binding": False,
            "live_source_calls": 0,
            "emails_sent": 0,
            "object_store_calls": 0,
            "collectors_activated": 0,
            "real_customer_data_written": False,
            "real_organization_touched": False,
            "customer_names_reported": False,
            "eligibility_reported": False,
            "deadlines_reported": False,
            "not_approved": list(NOT_APPROVED),
            "blocked_reasons": sorted(set(blocked_reasons)),
        }
    )


def summary_invariant_failures(result: dict[str, Any]) -> list[str]:
    """What must never be true of a readiness summary."""
    fails: list[str] = []

    by_lane = result.get("by_lane") or {}
    for key in LANE_KEYS:
        if key not in by_lane:
            fails.append(f"lane_missing:{key}")

    for key, lane in by_lane.items():
        if lane.get("status") not in LANE_STATUSES:
            fails.append(f"lane_status_not_recognised:{key}:{lane.get('status')}")
        if lane.get("value") and lane.get("blockers"):
            fails.append(f"lane_true_alongside_blockers:{key}")
        if not lane.get("value") and not lane.get("blockers"):
            fails.append(f"lane_false_with_no_blocker:{key}")
        if lane.get("status") == OPERATIONAL and not lane.get("value"):
            fails.append(f"operational_without_a_value:{key}")
        if lane.get("status") == OPERATIONAL and lane.get("scope") != CONTROLLED_SCOPE:
            fails.append(f"operational_outside_the_scope:{key}")

    # The load-bearing rule of the whole gate.
    for key in NEVER_TRUE_LANES:
        lane = by_lane.get(key) or {}
        if lane.get("value"):
            fails.append(f"a_cockpit_reported_a_forbidden_lane_true:{key}")
        if lane.get("status") == OPERATIONAL:
            fails.append(f"a_forbidden_lane_was_marked_operational:{key}")

    for field in (
        "production_rollout",
        "controlled_customer_pilot",
        "customer_auth_live",
        "source_monitoring_live",
        "email_delivery",
        "object_store_configured",
        "verified_operational_binding",
        "real_customer_data_written",
        "real_organization_touched",
        "customer_names_reported",
        "eligibility_reported",
        "deadlines_reported",
    ):
        if result.get(field):
            fails.append(f"claimed:{field}")
    for field in (
        "live_source_calls",
        "emails_sent",
        "object_store_calls",
        "collectors_activated",
    ):
        if result.get(field):
            fails.append(f"nonzero:{field}")

    action = result.get("next_safe_action") or {}
    for field in ("action", "why", "safe_because"):
        if not action.get(field):
            fails.append(f"next_safe_action_missing:{field}")

    missing = set(NOT_APPROVED) - set(result.get("not_approved") or [])
    if missing:
        fails.append(f"not_approved_list_lost_entries:{sorted(missing)}")

    return fails
