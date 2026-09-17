"""What Gate 163 will need, as a read model (Gate 162K).

## This grants nothing

No write, no flag, no side effect. `build_activation_packet` reads the recorded
facts and reports whether a source *could* be activated and what is missing if
not. Calling it a thousand times changes nothing.

It exists so Gate 163 inherits a checklist that was written before there was
anything to authorise — a standard shaped by what the guard requires rather
than by what the first candidate source happens to have.

## The packet's job is to be refusable

Every field is evidence or the absence of evidence. A packet that reported only
"ready: false" would be useless to the human who has to go and fix something,
so each unresolved requirement names its own authority:

```text
terms_status         a human reviewer, against the source's actual terms
human_review_status  a human reviewer
activation_status    an operator, recorded with attribution
robots_status        a live fetch of robots.txt - which is Gate 163's FIRST
                     act, before any collection request
```

## The ordering constraint Gate 163 must honour

`robots_status` is unresolvable for every real source in Gate 162, because
answering it requires an HTTP request. So Gate 163's first live call is not a
collection — it is a robots.txt fetch, and its result has to be recorded before
any other request to that host is permitted.

That is the politeness requirement arriving before the traffic it governs, and
the packet says so rather than leaving the sequence to be rediscovered.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.source_authorization_fact_model_service import (
    DECISION_FACTS,
    FACT_NAMES,
    FACT_RECORDED,
)
from nativeforge.services.source_authorization_fixture_registry_service import (
    is_fixture_source,
)
from nativeforge.services.source_live_authorization_service import (
    STATUS_APPROVED,
    authorize_source_for_live_access,
)

SCHEMA_VERSION = "nf_source_activation_packet_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

#: Who has to act, per unresolved requirement. A refusal that does not name an
#: owner is a refusal nobody can clear.
AUTHORITY_FOR_FACT: dict[str, str] = {
    "source_registered": "the registry curator",
    "terms_status": "a human reviewer, against the source's actual terms",
    "human_review_status": "a human reviewer",
    "activation_status": "an operator, recorded with attribution",
    "attribution_status": "derived from the terms decision",
    "collector_status": "an operator, by starting a collector",
    "robots_status": (
        "a live fetch of robots.txt - Gate 163's FIRST act, before any "
        "collection request to that host"
    ),
    "credential_status": "an operator, by configuring a credential",
    "rate_limit_status": "already satisfied by the declared politeness policy",
    "user_agent_status": "already satisfied by the canonical user agent",
    "runtime_status": "the platform, by having the Gates 157-161 lanes ready",
}

#: What Gate 163 must do, in order. Stated here so the sequence is recorded
#: rather than rediscovered.
GATE_163_SEQUENCE: tuple[str, ...] = (
    "a human reads the source's terms and records a signed terms decision",
    "a human records a signed source review decision",
    "an operator records an activation with attribution",
    "a live robots.txt fetch is performed and its result recorded - this is "
    "the first live HTTP request the campaign makes",
    "only then may a collection request to that host be permitted",
    "and the live transport must still be implemented and made dispatchable, "
    "which Gate 161 deliberately did not do",
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def build_activation_packet(
    *,
    connection: Any = None,
    organization_id: Any = None,
    source_id: Any = None,
    now: Any = None,
) -> dict[str, Any]:
    """Everything Gate 163 would need for one source. Writes nothing."""
    decision = authorize_source_for_live_access(
        connection=connection,
        organization_id=organization_id,
        source_id=source_id,
        now=now,
    )
    resolution = decision.get("resolution") or {}
    facts = resolution.get("resolved_facts") or {}

    requirements: list[dict[str, Any]] = []
    for name in FACT_NAMES:
        fact = facts.get(name) or {}
        satisfied = fact.get("fact_status") == FACT_RECORDED
        requirements.append(
            {
                "requirement": name,
                "satisfied": satisfied,
                "fact_status": fact.get("fact_status"),
                "value": fact.get("value"),
                "evidence_ref": fact.get("evidence_ref"),
                "recorded_by": fact.get("recorded_by"),
                "recorded_at": fact.get("recorded_at"),
                "expires_at": fact.get("expires_at"),
                "is_a_human_decision": name in DECISION_FACTS,
                # Only populated when unsatisfied. A satisfied requirement
                # needs no owner.
                "authority": (
                    None if satisfied else AUTHORITY_FOR_FACT.get(name)
                ),
            }
        )

    unresolved = [r for r in requirements if not r["satisfied"]]
    unresolved_decisions = [
        r for r in unresolved if r["is_a_human_decision"]
    ]

    activatable = decision["authorization_status"] == STATUS_APPROVED

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            # ---- identity ------------------------------------------------
            "source_id": decision.get("source_id"),
            "source_registered": bool(resolution.get("source_registered")),
            "is_synthetic_fixture": is_fixture_source(source_id),
            "source_name_fingerprint": resolution.get("source_name_fingerprint"),
            # ---- the checklist --------------------------------------------
            "requirements": requirements,
            "requirement_count": len(requirements),
            "requirements_satisfied": len(requirements) - len(unresolved),
            "unresolved_blockers": [r["requirement"] for r in unresolved],
            "unresolved_human_decisions": [
                r["requirement"] for r in unresolved_decisions
            ],
            # ---- the verdict ----------------------------------------------
            "activatable": activatable,
            "authorization_status": decision["authorization_status"],
            "packet_ready": activatable,
            # ---- what a ready packet still does not do --------------------
            "grants_nothing": True,
            "is_a_read_model": (
                "this reads recorded facts and reports what is missing. It "
                "writes nothing, sets no flag, and calling it changes no "
                "state whatsoever."
            ),
            "live_transport_permitted": False,
            "gate_163_sequence": list(GATE_163_SEQUENCE),
            "robots_must_be_fetched_first": (
                "robots_status is unresolvable for every real source here, "
                "because answering it requires an HTTP request. Gate 163's "
                "first live call is therefore a robots.txt fetch, not a "
                "collection."
            ),
            "live_source_call": False,
            "network_calls": 0,
            "source_monitoring_live": False,
        }
    )


def activation_packet_invariant_failures(packet: dict[str, Any]) -> list[str]:
    """Refuse a packet that grants, or that refuses without naming an owner."""
    fails: list[str] = []

    requirements = packet.get("requirements") or []
    if len(requirements) != len(FACT_NAMES):
        fails.append(
            f"packet_covers_{len(requirements)}_of_{len(FACT_NAMES)}_requirements"
        )

    satisfied = sum(1 for r in requirements if r.get("satisfied"))
    if satisfied != int(packet.get("requirements_satisfied") or 0):
        fails.append("requirements_satisfied_disagrees_with_the_checklist")

    unresolved = [r for r in requirements if not r.get("satisfied")]
    if sorted(r["requirement"] for r in unresolved) != sorted(
        packet.get("unresolved_blockers") or []
    ):
        fails.append("unresolved_blockers_disagrees_with_the_checklist")

    # THE invariant of a read model: every unresolved requirement names who
    # can clear it. A blocker with no owner is a blocker nobody clears.
    for requirement in unresolved:
        if not str(requirement.get("authority") or "").strip():
            fails.append(
                f"an_unresolved_requirement_with_no_authority:"
                f"{requirement.get('requirement')}"
            )

    # A satisfied human decision must be attributable.
    for requirement in requirements:
        if (
            requirement.get("satisfied")
            and requirement.get("is_a_human_decision")
            and not requirement.get("recorded_by")
        ):
            fails.append(
                f"a_satisfied_decision_with_no_signer:"
                f"{requirement.get('requirement')}"
            )

    # activatable and the blockers must agree, both directions.
    activatable = bool(packet.get("activatable"))
    if activatable and unresolved:
        fails.append("activatable_alongside_unresolved_blockers")
    if not activatable and not unresolved:
        fails.append("not_activatable_without_naming_a_blocker")
    if activatable != (packet.get("authorization_status") == STATUS_APPROVED):
        fails.append("activatable_disagrees_with_the_authorization_status")

    if not packet.get("grants_nothing"):
        fails.append("a_packet_that_claims_to_grant_something")
    if not packet.get("gate_163_sequence"):
        fails.append("the_packet_did_not_record_the_ordering_constraint")

    if packet.get("live_transport_permitted"):
        fails.append("the_packet_permitted_a_live_transport")
    for flag in ("live_source_call", "source_monitoring_live"):
        if packet.get(flag):
            fails.append(f"packet_claimed:{flag}")

    return sorted(set(fails))
