"""Gate 155B: what Gates 151-154 moved, and what they deliberately did not.

## Four lanes were CREATED, not flipped

At Gate 150 none of the four durability lanes existed - measured across `src/`
at commit 4d336d1, zero files mentioned any of them. So the delta is four lanes
created and proved, and **nothing that was false became true**.

`lane_delta` records both facts separately, because "four lanes went true"
invites the reading that four blocked things became unblocked. None did.

## Decisions are compared, never recomputed

Gate 150 established this and it holds here: `build_durability_reassessment`
takes each decision from the service that owns it and compares it to the
recorded baseline. A summariser that computed its own verdict would be supplying
its own evidence.

The baseline is Gate 150's, which was Gate 145's unchanged.

## Four conflations this module must not make

```text
operational_backup_restore_ready  is not  production_backup_ready
operational_health_ready          is not  production monitoring
a readiness lane                  is not  an activated capability
a preflight that passes           is not  a live capability
durable in controlled_dev_demo    is not  ready for production
```

The first is the one a reader reaches for: Gate 153 proved a restore and Gate
61/65 still returns SKIP. They are different harnesses answering opposite
questions, and an invariant fails if this module ever reports them as one.

## It decides nothing and activates nothing

No database, no shell, no external call. Every value arrives as an argument and
the three scope verdicts are compared, not computed. `production_rollout` is a
constant `NO_GO` with no branch that returns anything else.
"""

from __future__ import annotations

import json
import re
from typing import Any

SCHEMA_VERSION = "nf_operational_durability_reassessment_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

GO = "GO"
LIMITED_GO = "LIMITED_GO"
NO_GO = "NO_GO"

#: Gate 150's recorded decision, which was Gate 145's unchanged.
GATE_150_BASELINE: dict[str, str] = {
    "internal_demo_beta": GO,
    "controlled_customer_beta": LIMITED_GO,
    "production_rollout": NO_GO,
}

#: The four lanes Gates 151-154 created. None existed at Gate 150.
DURABILITY_LANES: tuple[dict[str, str], ...] = (
    {
        "lane": "tenant_digest_persistence_live",
        "gate": "151",
        "what": "a digest is persisted and reads back with its hash intact",
        "existed_at_gate_150": "no",
    },
    {
        "lane": "audit_replay_ready",
        "gate": "152",
        "what": (
            "recorded evidence replays, and legacy gaps are reported rather "
            "than backfilled"
        ),
        "existed_at_gate_150": "no",
    },
    {
        "lane": "operational_backup_restore_ready",
        "gate": "153",
        "what": (
            "controlled dev/demo state exports, restores into an isolated "
            "database, and still passes the Gate 152 replay"
        ),
        "existed_at_gate_150": "no",
    },
    {
        "lane": "operational_health_ready",
        "gate": "154",
        "what": (
            "service, migration and code-freshness state is modelled, ten "
            "failure modes are named, and the next safe action is derived"
        ),
        "existed_at_gate_150": "no",
    },
)

#: Recorded by Gate 150 as `not_approved`. Every one must still be false.
UNCHANGED_FALSE_LANES: tuple[str, ...] = (
    "controlled_customer_pilot",
    "customer_auth_live",
    "verified_operational_binding",
    "consent_boundary_documented",
    "customer_beta_scope_approved",
    "source_monitoring_live",
    "email_delivery",
    "object_store_configured",
)

#: Readiness facts that must never be read as the capability beside them.
CONFLATIONS: tuple[dict[str, str], ...] = (
    {
        "readiness": "operational_backup_restore_ready",
        "is_not": "production_backup_ready",
        "why": (
            "Gate 153 exports controlled dev/demo state and reloads it into an "
            "isolated database. The Gate 61/65 harness asks whether a provider "
            "can dump and restore a database, needs a managed instance, and "
            "returns SKIP. Different harnesses, opposite questions."
        ),
    },
    {
        "readiness": "operational_health_ready",
        "is_not": "production monitoring",
        "why": (
            "Gate 154 models state from measured facts. There is no APM, no "
            "alerting, no external monitor, no uptime record and no error "
            "budget, and nothing leaves this host."
        ),
    },
    {
        "readiness": "audit_replay_ready",
        "is_not": "a legally sufficient audit trail",
        "why": (
            "the records this system wrote can be found, joined and checked "
            "against their own hashes. That is not legal standing, and 85 "
            "legacy intents still refer to digests nobody kept."
        ),
    },
    {
        "readiness": "tenant_digest_persistence_live",
        "is_not": "a digest was delivered or read",
        "why": (
            "a digest is stored. Nothing records that a tenant received one, "
            "and email_delivery is false."
        ),
    },
    {
        "readiness": "durable in controlled_dev_demo",
        "is_not": "ready for production",
        "why": (
            "every lane above is scoped to one demo organization holding "
            "fixture data. No customer data exists to be durable."
        ),
    },
)

SAFE_CLAIMS: tuple[str, ...] = (
    "a digest this system wrote can be read back, and its payload hash checked",
    "the evidence chain this system recorded can be replayed",
    "the gaps in that chain are counted and reported, and were not filled in",
    (
        "controlled dev/demo operational state can be exported, restored into "
        "an isolated database, and re-verified there"
    ),
    (
        "this deployment can say which services are up, whether its database "
        "matches its migrations, whether the built frontend matches HEAD, and "
        "whether the running backend predates the code"
    ),
    "ten named operational failure modes are detected and given an exact action",
    "no readiness lane above required a new approval, and none granted one",
)

UNSAFE_CLAIMS: tuple[dict[str, str], ...] = (
    {
        "claim": "NativeForge has backups",
        "why_unsafe": (
            "no managed database instance exists, no backup automation, no "
            "PITR, and no provider restore has ever run. The Gate 61/65 "
            "verifier says so and still returns SKIP."
        ),
        "what_is_true": (
            "controlled dev/demo state can be exported and restored into an "
            "isolated database"
        ),
    },
    {
        "claim": "NativeForge is monitored",
        "why_unsafe": (
            "nothing watches this system. There is no alerting, no external "
            "monitor and no uptime record; a person runs a verifier."
        ),
        "what_is_true": (
            "the deployment can report its own state when asked, and names "
            "what it cannot observe"
        ),
    },
    {
        "claim": "customer data is safe / durable / backed up",
        "why_unsafe": (
            "no customer data exists. Nothing has been made durable for a customer."
        ),
        "what_is_true": "fixture data for one demo organization is durable",
    },
    {
        "claim": "the audit trail would satisfy an auditor",
        "why_unsafe": (
            "replay proves internal consistency, not legal standing, and 85 "
            "legacy intents name digests that were never written"
        ),
        "what_is_true": "records can be joined and checked against their own hashes",
    },
    {
        "claim": "the controlled customer beta is ready to start",
        "why_unsafe": (
            "four approvals are outstanding and none is technical. Gates "
            "151-154 did not touch any of them."
        ),
        "what_is_true": "LIMITED_GO, unchanged since Gate 145",
    },
    {
        "claim": "operational durability moves the product toward production",
        "why_unsafe": (
            "production is blocked on procurement and approvals. Durability "
            "work does not shorten that queue."
        ),
        "what_is_true": (
            "the controlled dev/demo system is materially harder to lose data "
            "in and easier to diagnose"
        ),
    },
)

_FORBIDDEN_SHAPES: tuple[tuple[str, str], ...] = (
    ("email_address", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    ("bearer_token", r"\beyJ[A-Za-z0-9_-]{8,}"),
    ("session_cookie", r"nf_session="),
    ("google_client_secret", r"GOCSPX-"),
    ("private_key", r"BEGIN PRIVATE KEY"),
    ("aws_key", r"AKIA"),
)
_PROVIDER_SUBJECT_SHAPE = re.compile(r"\b\d{18,}\b")


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _leaked_shapes(payload: Any) -> list[str]:
    body = json.dumps(payload, default=str, sort_keys=True)
    found = [name for name, pattern in _FORBIDDEN_SHAPES if re.search(pattern, body)]
    if _PROVIDER_SUBJECT_SHAPE.search(body):
        found.append("provider_subject")
    return sorted(set(found))


def build_durability_reassessment(
    *,
    internal_demo_beta: str | None = None,
    controlled_customer_beta: str | None = None,
    tenant_digest_persistence_live: bool | None = None,
    audit_replay_ready: bool | None = None,
    operational_backup_restore_ready: bool | None = None,
    operational_health_ready: bool | None = None,
    production_backup_ready: bool | None = None,
    production_monitoring_active: bool | None = None,
    controlled_customer_pilot: bool | None = None,
    activation_mechanism_exists: bool | None = None,
    customer_auth_live: bool | None = None,
    verified_operational_binding: bool | None = None,
    consent_boundary_documented: bool | None = None,
    customer_beta_scope_approved: bool | None = None,
    source_monitoring_live: bool | None = None,
    email_delivery: bool | None = None,
    object_store_configured: bool | None = None,
    next_block: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare Gate 150's decision to the current one. Decides nothing."""
    measured = {
        "tenant_digest_persistence_live": bool(tenant_digest_persistence_live),
        "audit_replay_ready": bool(audit_replay_ready),
        "operational_backup_restore_ready": bool(operational_backup_restore_ready),
        "operational_health_ready": bool(operational_health_ready),
    }

    still_false = {
        "controlled_customer_pilot": bool(controlled_customer_pilot),
        "customer_auth_live": bool(customer_auth_live),
        "verified_operational_binding": bool(verified_operational_binding),
        "consent_boundary_documented": bool(consent_boundary_documented),
        "customer_beta_scope_approved": bool(customer_beta_scope_approved),
        "source_monitoring_live": bool(source_monitoring_live),
        "email_delivery": bool(email_delivery),
        "object_store_configured": bool(object_store_configured),
    }

    current = {
        "internal_demo_beta": internal_demo_beta or NO_GO,
        "controlled_customer_beta": controlled_customer_beta or NO_GO,
        # Constant. No branch computes anything else.
        "production_rollout": NO_GO,
    }

    decision_delta = {
        scope: {
            "gate_150": GATE_150_BASELINE[scope],
            "now": current[scope],
            "changed": current[scope] != GATE_150_BASELINE[scope],
        }
        for scope in GATE_150_BASELINE
    }

    lanes_created = [
        {**entry, "now": measured[entry["lane"]]} for entry in DURABILITY_LANES
    ]
    lanes_proved = sorted(name for name, value in measured.items() if value)
    lanes_unproved = sorted(name for name, value in measured.items() if not value)
    lanes_wrongly_true = sorted(name for name, value in still_false.items() if value)

    failures: list[str] = []
    for name in lanes_unproved:
        failures.append(f"durability_lane_not_proved:{name}")
    # One entry per lane, in the same spelling the invariant checker uses.
    # A list-formatted duplicate reads like a second, separate problem.
    for name in lanes_wrongly_true:
        failures.append(f"lane_that_must_stay_false_is_true:{name}")
    if production_backup_ready:
        failures.append("production_backup_ready_became_true")
    if production_monitoring_active:
        failures.append("production_monitoring_became_true")
    if activation_mechanism_exists:
        failures.append("an_activation_mechanism_was_created")

    improved = not failures and all(measured.values())

    payload = _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "block": "Gates 151-155, operational durability",
            # Derived from the four lanes. Never supplied.
            "operational_durability_improved": improved,
            "lane_delta": {
                "lanes_created_by_this_block": lanes_created,
                "lanes_created_count": len(lanes_created),
                "lanes_proved": lanes_proved,
                "lanes_not_proved": lanes_unproved,
                "lanes_that_were_false_and_became_true": [],
                "why_that_list_is_empty": (
                    "none of the four lanes existed at Gate 150 - measured "
                    "across src/ at 4d336d1, zero files mentioned any of them. "
                    "They were created and proved. Nothing that was false "
                    "became true."
                ),
                "unchanged_false_lanes": dict(still_false),
                "unchanged_false_count": len(still_false),
            },
            "controlled_dev_demo_durability": {
                "status": "materially improved" if improved else "not established",
                "evidence_can_be_reread": measured["tenant_digest_persistence_live"],
                "evidence_can_be_replayed": measured["audit_replay_ready"],
                "state_can_be_restored_elsewhere": measured[
                    "operational_backup_restore_ready"
                ],
                "deployment_can_report_its_own_state": measured[
                    "operational_health_ready"
                ],
            },
            "production_durability": {
                "production_backup_ready": False,
                "production_monitoring_active": False,
                "status": "unchanged; nothing in this block touched production",
                "blocked_on": "a managed database instance, which is procurement",
                "harness": "scripts/verify_nativeforge_backup_restore.sh (SKIP)",
            },
            "customer_beta_decision": current["controlled_customer_beta"],
            "production_decision": current["production_rollout"],
            "internal_demo_decision": current["internal_demo_beta"],
            "decision_delta": decision_delta,
            "any_decision_changed": any(
                entry["changed"] for entry in decision_delta.values()
            ),
            "why_no_decision_changed": (
                "Gates 151-154 were durability gates, not approval gates. A "
                "block that moved a customer or production decision without a "
                "new external approval would mean one of them had granted "
                "itself something."
            ),
            "conflations": [dict(entry) for entry in CONFLATIONS],
            "safe_claims": list(SAFE_CLAIMS),
            "unsafe_claims": [dict(entry) for entry in UNSAFE_CLAIMS],
            "next_block": dict(next_block or {}),
            "invariant_failures": sorted(set(failures)),
            # Constants. This module reads.
            "rows_written": 0,
            "activation_mechanism_created": False,
            "anything_activated": False,
            "real_organization_touched": False,
            "email_sent": False,
            "live_source_called": False,
            "object_store_contacted": False,
            "leaked_shapes": [],
        }
    )
    payload["leaked_shapes"] = _leaked_shapes(payload)
    return payload


def durability_reassessment_invariant_failures(
    reassessment: dict[str, Any],
) -> list[str]:
    """Refuse a reassessment that claimed more than the evidence supports."""
    fails: list[str] = list(reassessment.get("invariant_failures") or [])

    delta = reassessment.get("lane_delta") or {}
    if delta.get("lanes_created_count") != len(DURABILITY_LANES):
        fails.append("lane_delta_lost_a_created_lane")
    # The claim this block is most likely to overstate.
    if delta.get("lanes_that_were_false_and_became_true"):
        fails.append("claimed_a_false_lane_became_true")

    for name in UNCHANGED_FALSE_LANES:
        if (delta.get("unchanged_false_lanes") or {}).get(name):
            fails.append(f"lane_that_must_stay_false_is_true:{name}")

    if reassessment.get("production_decision") != NO_GO:
        fails.append("production_rollout_is_not_no_go")
    if reassessment.get("any_decision_changed"):
        fails.append("a_decision_changed_without_a_new_approval")

    production = reassessment.get("production_durability") or {}
    if production.get("production_backup_ready"):
        fails.append("production_backup_ready_became_true")
    if production.get("production_monitoring_active"):
        fails.append("production_monitoring_became_true")

    # The two lanes a reader is most likely to merge.
    pairs = {
        (entry.get("readiness"), entry.get("is_not"))
        for entry in (reassessment.get("conflations") or [])
    }
    if ("operational_backup_restore_ready", "production_backup_ready") not in pairs:
        fails.append("the_backup_conflation_warning_was_removed")
    if ("operational_health_ready", "production monitoring") not in pairs:
        fails.append("the_monitoring_conflation_warning_was_removed")

    if reassessment.get("operational_durability_improved"):
        for name in delta.get("lanes_not_proved") or []:
            fails.append(f"improved_while_a_lane_is_unproved:{name}")

    for flag in (
        "activation_mechanism_created",
        "anything_activated",
        "real_organization_touched",
        "email_sent",
        "live_source_called",
        "object_store_contacted",
    ):
        if reassessment.get(flag):
            fails.append(f"reassessment_claimed:{flag}")

    if reassessment.get("rows_written"):
        fails.append("reassessment_wrote_rows")

    for name in reassessment.get("leaked_shapes") or []:
        fails.append(f"leaked:{name}")

    return sorted(set(fails))
