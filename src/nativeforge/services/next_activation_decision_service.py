"""Gate 155C: which block comes next, ranked by what is actually blocked.

## The rule that decides it

**Do not recommend another readiness wrapper around a blocker only a person can
clear.** Gates 146-150 already made every customer refusal exact. Describing the
same refusal in more detail is not progress, and four gates of it would look
like momentum while moving nothing.

So a candidate is ranked by how many of its blockers are **absent components**
rather than absent approvals.

## The measurement, not the feeling

```text
candidate                 blockers  human  engineering
customer_activation           4        4        0
source_collection_runtime     7        2        5
email_activation              1        1        0
object_storage_activation     1        1        0
production_infrastructure     1        1        0
additional_durability         0        0        0
```

Source monitoring's five engineering blockers are all the same shape - a
scheduler component that does not exist:

```text
scheduler_component_absent:scheduler_runtime
scheduler_component_absent:background_worker
scheduler_component_absent:periodic_trigger
scheduler_component_absent:persistent_backend
scheduler_component_absent:production_raw_payload_store
```

`backend_lifespan_hook_service` calls itself "the attach point a future
in-process scheduler would use, and a record of the fact that nothing is
attached to it." `scheduler_attached` has been `False` since Gate 102.

## What it must not be allowed to conclude

A scheduler does not make `source_monitoring_live` true and must not. With 171
sources `terms_blocked` and 0 `activation_approved`, a scheduler polls nothing -
which is exactly how it should be proved before any source is approved. It
removes five of the seven reasons monitoring cannot start; the remaining two
stay human.

## It recommends, and recommends only

No database, no shell, no external call, no activation. The recommendation is
derived from supplied blocker counts, so a candidate whose blockers change gets
a different answer without anyone editing a constant - which is what went wrong
with the two next-step constants this campaign has now found stale.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_next_activation_decision_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

HUMAN = "human_or_approval"
ENGINEERING = "absent_component"

#: A candidate whose blockers are all human cannot be advanced by building
#: anything. Recommending it would produce another readiness wrapper.
WRAPPER_RISK = "another_readiness_wrapper_around_a_human_blocker"
ADVANCABLE = "engineering_can_clear_blockers"
NOTHING_BLOCKED = "nothing_is_blocked_here"


def _blocker(name: str, kind: str, detail: str) -> dict[str, str]:
    return {"blocker": name, "kind": kind, "detail": detail}


#: Every candidate, with its blockers classified by who can clear them.
#: Measured from each lane's own verifier, not estimated.
CANDIDATES: tuple[dict[str, Any], ...] = (
    {
        "candidate": "customer_activation",
        "subject": "start the controlled customer beta",
        "blockers": [
            _blocker(
                "customer_auth_live",
                HUMAN,
                "a real person at a customer organization must sign in as "
                "themselves; no code change causes that",
            ),
            _blocker(
                "verified_operational_binding",
                HUMAN,
                "an approval must be signed. Gate 147 built the boundary.",
            ),
            _blocker(
                "consent_and_data_boundary_documented",
                HUMAN,
                "the customer organization must consent; consent cannot be "
                "inferred or pre-supplied",
            ),
            _blocker(
                "customer_beta_scope_approved",
                HUMAN,
                "an approver must approve the scope Gate 150 reassessed",
            ),
        ],
        "customer_value": "highest - it is the product reaching a customer",
        "risk": "high; it is the first time real data would exist",
        "prerequisite": "a real customer organization must exist. None does.",
    },
    {
        "candidate": "source_collection_runtime",
        "subject": "the scheduler that would poll approved sources",
        "blockers": [
            _blocker(
                "terms_review_incomplete",
                HUMAN,
                "171 registry sources are terms_blocked; each needs a decision",
            ),
            _blocker(
                "human_review_only_sources",
                HUMAN,
                "6 sources are human_review_blocked",
            ),
            _blocker(
                "scheduler_component_absent:scheduler_runtime",
                ENGINEERING,
                "no scheduler exists. Gate 102 added the attach point and "
                "recorded that nothing is attached.",
            ),
            _blocker(
                "scheduler_component_absent:background_worker",
                ENGINEERING,
                "nothing runs work outside a request",
            ),
            _blocker(
                "scheduler_component_absent:periodic_trigger",
                ENGINEERING,
                "nothing fires on a schedule",
            ),
            _blocker(
                "scheduler_component_absent:persistent_backend",
                ENGINEERING,
                "no durable queue or job record exists",
            ),
            _blocker(
                "scheduler_component_absent:production_raw_payload_store",
                ENGINEERING,
                "nowhere to put a source response",
            ),
        ],
        "customer_value": (
            "high - a grant intelligence system whose sources are never polled "
            "shows a tenant the same data forever"
        ),
        "risk": (
            "low if built with an empty allowlist: a scheduler with zero "
            "approved sources polls nothing and contacts nothing"
        ),
        "prerequisite": "none. It can be built and proved hermetically today.",
    },
    {
        "candidate": "email_activation",
        "subject": "actually send a digest",
        "blockers": [
            _blocker(
                "no_email_provider_configured",
                HUMAN,
                "an approver, then a provider admin. Configuring a provider "
                "sends mail on someone's behalf.",
            ),
        ],
        "customer_value": "medium - a digest nobody receives is a preview",
        "risk": "medium; the first send is irreversible",
        "prerequisite": "an approval, then provider credentials",
    },
    {
        "candidate": "object_storage_activation",
        "subject": "store document bytes",
        "blockers": [
            _blocker(
                "document_body_storage_is_not_configured",
                HUMAN,
                "an approver, then a provisioning decision. Gate 141 kept bytes "
                "out of the database deliberately.",
            ),
        ],
        "customer_value": "medium - metadata without bytes is a catalogue",
        "risk": "medium; it is where customer documents would live",
        "prerequisite": "an approval, then a provisioned store",
    },
    {
        "candidate": "production_infrastructure",
        "subject": "a managed database instance",
        "blockers": [
            _blocker(
                "no_managed_database_instance",
                HUMAN,
                "procurement. It unblocks the Gate 61/65 backup harness and "
                "the Postgres RLS verifier, both of which return SKIP.",
            ),
        ],
        "customer_value": "low today - nothing is in production",
        "risk": "low to build, high to depend on before it exists",
        "prerequisite": "a purchase",
    },
    {
        "candidate": "additional_durability",
        "subject": "more of what Gates 151-154 did",
        "blockers": [],
        "customer_value": "low - the four lanes are proved",
        "risk": "low, and so is the return",
        "prerequisite": "none, which is the problem: nothing here is blocked",
    },
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _score(candidate: dict[str, Any]) -> dict[str, Any]:
    blockers = candidate.get("blockers") or []
    human = [b for b in blockers if b["kind"] == HUMAN]
    engineering = [b for b in blockers if b["kind"] == ENGINEERING]

    if not blockers:
        verdict = NOTHING_BLOCKED
    elif engineering:
        verdict = ADVANCABLE
    else:
        verdict = WRAPPER_RISK

    return {
        **candidate,
        "blocker_count": len(blockers),
        "human_blocker_count": len(human),
        "engineering_blocker_count": len(engineering),
        "engineering_can_advance": bool(engineering),
        "verdict": verdict,
        # The ranking key: how many blockers engineering can actually clear.
        # Ties break toward fewer human blockers left behind.
        "unlock_score": len(engineering),
    }


def build_next_activation_decision(
    *,
    real_customer_org_exists: bool | None = None,
    second_identity_available: bool | None = None,
    consent_decision_available: bool | None = None,
    candidates: tuple[dict[str, Any], ...] | None = None,
) -> dict[str, Any]:
    """Rank the candidates and name one. Activates nothing."""
    scored = [_score(dict(entry)) for entry in (candidates or CANDIDATES)]
    ranked = sorted(
        scored,
        key=lambda entry: (-entry["unlock_score"], entry["human_blocker_count"]),
    )

    # The branch the gate specifies: if the customer prerequisites are all
    # available NOW, customer activation wins regardless of blocker counts,
    # because a human blocker that a person is standing by to clear is not a
    # blocker in the sense that matters.
    customer_ready = bool(
        real_customer_org_exists
        and second_identity_available
        and consent_decision_available
    )

    if customer_ready:
        chosen = next(
            entry for entry in scored if entry["candidate"] == "customer_activation"
        )
        why = (
            "a real customer organization exists, a second identity is "
            "available, and the consent decision can be made now. The human "
            "blockers are clearable today, so the customer lane outranks any "
            "engineering lane."
        )
        first_gate = "create the real customer organization and bind it"
    else:
        advancable = [e for e in ranked if e["engineering_can_advance"]]
        if not advancable:
            return _json_safe(
                {
                    "schema_version": SCHEMA_VERSION,
                    "scope": CONTROLLED_SCOPE,
                    "customer_prerequisites_available_now": False,
                    "recommended_block": None,
                    "recommended_subject": None,
                    "why": (
                        "every candidate is blocked only by a person or an "
                        "approval. Recommending any of them would produce "
                        "another readiness wrapper."
                    ),
                    "first_gate": None,
                    "ranked_candidates": ranked,
                    "rejected": [],
                    "the_rule": (
                        "do not recommend another readiness wrapper around a "
                        "blocker only a person or an approval can clear"
                    ),
                    "nothing_is_engineering_advancable": True,
                    "anything_activated": False,
                    "activation_mechanism_created": False,
                    "rows_written": 0,
                    "external_call_made": False,
                }
            )
        chosen = advancable[0]
        why = (
            "no real customer organization exists, no second identity is "
            "available and no consent decision can be made, so the customer "
            f"lane cannot move. {chosen['candidate']} is the only candidate "
            f"where engineering can clear blockers - "
            f"{chosen['engineering_blocker_count']} of "
            f"{chosen['blocker_count']} - and every other candidate would "
            "produce another readiness wrapper around a blocker only a person "
            "can clear."
        )
        first_gate = "the scheduler runtime itself, hermetic, with an empty allowlist"

    rejected = [
        {
            "candidate": entry["candidate"],
            "verdict": entry["verdict"],
            "why_not": (
                "nothing here is blocked, so a gate would harden something already hard"
                if entry["verdict"] == NOTHING_BLOCKED
                else (
                    f"all {entry['human_blocker_count']} blockers need a person "
                    "or an approval; building more would describe the same "
                    "refusal in more detail"
                )
            ),
        }
        for entry in ranked
        if entry["candidate"] != chosen["candidate"]
    ]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "customer_prerequisites_available_now": customer_ready,
            "customer_prerequisites": {
                "real_customer_org_exists": bool(real_customer_org_exists),
                "second_identity_available": bool(second_identity_available),
                "consent_decision_available": bool(consent_decision_available),
            },
            "recommended_block": chosen["candidate"],
            "recommended_subject": chosen["subject"],
            "why": why,
            "first_gate": first_gate,
            "ranked_candidates": ranked,
            "rejected": rejected,
            "the_rule": (
                "do not recommend another readiness wrapper around a blocker "
                "only a person or an approval can clear"
            ),
            "ranking_is_derived": (
                "from supplied blocker counts, so a candidate whose blockers "
                "change gets a different answer without anyone editing a "
                "constant. Two next-step constants in this repository have "
                "already gone stale unnoticed."
            ),
            "what_the_recommendation_does_not_mean": [
                "that source_monitoring_live would become true",
                "that any source would be polled; 171 are terms_blocked and 0 "
                "are approved",
                "that the two human source blockers are cleared",
                "that a collector is activated",
                "that anything is activated at all",
            ],
            # Constants. A recommendation recommends.
            "anything_activated": False,
            "activation_mechanism_created": False,
            "rows_written": 0,
            "external_call_made": False,
        }
    )


def next_activation_decision_invariant_failures(
    decision: dict[str, Any],
) -> list[str]:
    """Refuse a recommendation that would build a wrapper, or activate."""
    fails: list[str] = []

    ranked = decision.get("ranked_candidates") or []
    names = [entry.get("candidate") for entry in ranked]
    if len(names) != len(set(names)):
        fails.append("a_candidate_is_ranked_twice")

    chosen = decision.get("recommended_block")
    nothing_advancable = bool(decision.get("nothing_is_engineering_advancable"))
    if not chosen and not nothing_advancable:
        fails.append("no_block_was_recommended")
    if not decision.get("first_gate") and not nothing_advancable:
        fails.append("no_first_gate_was_named")
    if not decision.get("why"):
        fails.append("the_recommendation_carries_no_reason")

    entry = next((e for e in ranked if e.get("candidate") == chosen), None)
    if entry is None and not nothing_advancable:
        fails.append("the_recommended_block_is_not_among_the_candidates")
    else:
        # The rule, enforced: a block whose blockers are all human may only be
        # recommended when the prerequisites are available now.
        if entry.get("verdict") == WRAPPER_RISK and not decision.get(
            "customer_prerequisites_available_now"
        ):
            fails.append(f"recommended_a_wrapper_block:{chosen}")
        if entry.get("verdict") == NOTHING_BLOCKED:
            fails.append(f"recommended_a_block_with_nothing_blocked:{chosen}")

    for flag in (
        "anything_activated",
        "activation_mechanism_created",
        "external_call_made",
    ):
        if decision.get(flag):
            fails.append(f"decision_claimed:{flag}")

    if decision.get("rows_written"):
        fails.append("decision_wrote_rows")

    return sorted(set(fails))
