"""Gate 129B: the operating shell — one page that tells the product story.

The demo page has 291 test ids and covers eligibility, pursuit, readiness and
audit in depth. What it did not have is a single surface saying, in order, what
NativeForge does for a Tribal government and which parts of it are live.

## Why every label here is derived

A demo that says "controlled demo data" because someone typed that string is
one edit away from lying. This campaign has now found the same defect in seven
gates: a constant wearing the shape of a measurement.

So every truth label carries `active`, computed from the same services the rest
of the system answers with, and `derived_from` naming the source. When customer
auth goes live, `AUTH NOT LIVE` deactivates because
`customer_auth_live` flipped -- not because anyone remembered to delete it.

## What this service must never do

```text
claim a lane is operational   `operational` comes from the capability matrix
invent row counts             every count is read, and every one is 0
contact anything              no network, no store, no provider
hold customer data            section content is shape and status, not records
```
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_customer_demo_operating_shell_v1"

#: The six labels the demo must show. Names are fixed; `active` is measured.
TRUTH_LABELS: tuple[str, ...] = (
    "CONTROLLED DEMO DATA",
    "AUTH NOT LIVE",
    "LIVE SOURCE MONITORING NOT ACTIVE",
    "EMAIL DELIVERY NOT ACTIVE",
    "OBJECT STORE NOT CONFIGURED",
    "PROVIDER CONFIG REQUIRED FOR LOGIN",
)

#: Ten sections, in the order a buyer should read them. `capability` names the
#: persistence lane that backs a section, or None where the section is a view
#: over work that has no lane of its own.
SECTIONS: tuple[dict[str, Any], ...] = (
    {
        "section_id": "tenant_profile",
        "title": "Tribal tenant profile & eligibility",
        "shows": "who the Tribe is, recognition status, and resulting eligibility",
        "capability": "tenant_profile_persistence",
    },
    {
        "section_id": "source_watchlist",
        "title": "Source watchlist",
        "shows": "which funding sources are watched for this Tribe",
        "capability": "source_watchlist_persistence",
    },
    {
        "section_id": "weekly_digest",
        "title": "Weekly matched NOFO digest",
        "shows": "new and changed notices matched to this Tribe's profile",
        "capability": "tenant_digest_persistence",
    },
    {
        "section_id": "pursuit_pipeline",
        "title": "Pursuit pipeline",
        "shows": "opportunities being worked, with stage and owner",
        "capability": None,
    },
    {
        "section_id": "awarded_grants",
        "title": "Awarded grants workspace",
        "shows": "grants actually won, and the obligations that came with them",
        "capability": "awarded_grants_persistence",
    },
    {
        "section_id": "award_requirements",
        "title": "Award requirements & reporting deadlines",
        "shows": "what each award requires and when it is due",
        "capability": "award_requirements_persistence",
    },
    {
        "section_id": "proof_audit",
        "title": "Proof & audit trail",
        "shows": "what was submitted, when, and what evidence supports it",
        "capability": "proof_audit_persistence",
    },
    {
        "section_id": "document_metadata",
        "title": "Document metadata",
        "shows": "which compliance documents exist, filed when, with what digest",
        "capability": "document_library_persistence",
    },
    {
        "section_id": "readiness_blockers",
        "title": "Readiness & blockers",
        "shows": "what is built, what is live, and what is blocking the rest",
        "capability": None,
    },
    {
        "section_id": "next_actions",
        "title": "Next actions",
        "shows": "the specific next step for each blocked capability",
        "capability": None,
    },
)

SECTION_IDS: tuple[str, ...] = tuple(s["section_id"] for s in SECTIONS)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_customer_demo_operating_shell(
    *,
    capability_matrix: dict[str, Any] | None = None,
    spine: dict[str, Any] | None = None,
    activation_gate: dict[str, Any] | None = None,
    provider_readiness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The operating shell. Every status is read, none is asserted.

    Each input is injectable so a fixture can render the shell for a
    hypothetical environment, and so the true branch of every label is
    reachable in a test. Without that, `active: True` on every label would be
    indistinguishable from six hardcoded strings.
    """
    from nativeforge.services.customer_auth_activation_gate_service import (
        build_customer_auth_activation_gate,
    )
    from nativeforge.services.customer_auth_provider_readiness_service import (
        build_provider_readiness,
    )
    from nativeforge.services.customer_persistence_capability_service import (
        build_capability_matrix,
    )
    from nativeforge.services.customer_persistence_spine_decision_service import (
        build_persistence_spine_decision,
    )

    matrix = capability_matrix or build_capability_matrix()
    decision = spine or build_persistence_spine_decision()
    gate = activation_gate or build_customer_auth_activation_gate()
    provider = provider_readiness or build_provider_readiness()

    lanes = {row["capability"]: row for row in (matrix.get("rows") or [])}

    sections: list[dict[str, Any]] = []
    for spec in SECTIONS:
        lane = lanes.get(spec["capability"]) if spec["capability"] else None
        if lane is not None:
            built = bool(lane.get("write_path_available"))
            operational = bool(lane.get("operational"))
            blocked = list(lane.get("blocked_reasons") or [])
            rows_written = int(lane.get("rows_written") or 0)
            table = lane.get("expected_table")
        else:
            # A section with no persistence lane is a view, not a store. It is
            # never "operational" on its own, and saying so is more honest than
            # borrowing another lane's status.
            built = True
            operational = False
            blocked = ["no_persistence_lane_of_its_own"]
            rows_written = 0
            table = None
        sections.append(
            {
                "section_id": spec["section_id"],
                "title": spec["title"],
                "shows": spec["shows"],
                "capability": spec["capability"],
                "expected_table": table,
                "built": built,
                "operational": operational,
                "blocked_reasons": sorted(blocked),
                "rows_written": rows_written,
                "data_source": "controlled_demo",
            }
        )

    # -- the labels, each derived from something that can change -------------
    customer_auth_live = bool(gate.get("customer_auth_live"))
    rows_written_total = sum(s["rows_written"] for s in sections)
    labels = [
        {
            "label": "CONTROLLED DEMO DATA",
            "active": not bool(decision.get("persisted")) and rows_written_total == 0,
            "derived_from": "spine.persisted, and every lane's rows_written",
        },
        {
            "label": "AUTH NOT LIVE",
            "active": not customer_auth_live,
            "derived_from": "activation_gate.customer_auth_live",
        },
        {
            "label": "LIVE SOURCE MONITORING NOT ACTIVE",
            "active": bool(decision.get("requires_live_source_collection")),
            "derived_from": "spine.requires_live_source_collection",
        },
        {
            "label": "EMAIL DELIVERY NOT ACTIVE",
            "active": bool(decision.get("requires_email_delivery")),
            "derived_from": "spine.requires_email_delivery",
        },
        {
            "label": "OBJECT STORE NOT CONFIGURED",
            "active": bool(decision.get("requires_document_storage")),
            "derived_from": "spine.requires_document_storage",
        },
        {
            "label": "PROVIDER CONFIG REQUIRED FOR LOGIN",
            "active": not bool(provider.get("provider_ready")),
            "derived_from": "provider_readiness.provider_ready",
        },
    ]

    next_actions = [
        {
            "capability": row["capability"],
            "blocked_reasons": row["blocked_reasons"],
        }
        for row in sections
        if not row["operational"] and row["capability"]
    ]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "sections": sections,
            "section_ids": list(SECTION_IDS),
            "section_count": len(sections),
            "truth_labels": labels,
            "active_truth_labels": [x["label"] for x in labels if x["active"]],
            "next_actions": next_actions,
            # Claims this shell refuses to make, kept beside the data so a
            # reader does not have to infer them from an absence.
            "customer_auth_live": customer_auth_live,
            "login_live": bool(gate.get("login_live")),
            "live_source_monitoring_active": not bool(
                decision.get("requires_live_source_collection")
            ),
            "email_delivery_active": not bool(decision.get("requires_email_delivery")),
            "object_store_configured": not bool(
                decision.get("requires_document_storage")
            ),
            "provider_ready": bool(provider.get("provider_ready")),
            "operational_section_count": sum(1 for s in sections if s["operational"]),
            "rows_written": rows_written_total,
            "persisted": bool(decision.get("persisted")),
            "fabricated": False,
            "live_fetch_performed": False,
            "production_ready": False,
        }
    )


def operating_shell_invariant_failures(shell: dict[str, Any]) -> list[str]:
    """Refuse a shell that claims more than the system does."""
    fails: list[str] = []

    if list(shell.get("section_ids") or []) != list(SECTION_IDS):
        fails.append("section_set_changed")
    if shell.get("section_count") != len(SECTIONS):
        fails.append("section_count_disagrees")

    labels = {x["label"]: x for x in (shell.get("truth_labels") or [])}
    for name in TRUTH_LABELS:
        if name not in labels:
            fails.append(f"missing_truth_label:{name}")

    for key in ("fabricated", "live_fetch_performed", "production_ready", "persisted"):
        if shell.get(key) is True:
            fails.append(key)

    if int(shell.get("rows_written") or 0) != 0:
        fails.append("rows_written_must_be_zero")

    # A label and the claim beside it must agree. Two answers to one question is
    # the defect this campaign keeps finding, and a demo is where it would be
    # least visible and most costly.
    pairs = (
        ("AUTH NOT LIVE", "customer_auth_live"),
        ("LIVE SOURCE MONITORING NOT ACTIVE", "live_source_monitoring_active"),
        ("EMAIL DELIVERY NOT ACTIVE", "email_delivery_active"),
        ("OBJECT STORE NOT CONFIGURED", "object_store_configured"),
        ("PROVIDER CONFIG REQUIRED FOR LOGIN", "provider_ready"),
    )
    for label_name, claim_key in pairs:
        entry = labels.get(label_name)
        if entry is None:
            continue
        if bool(entry.get("active")) == bool(shell.get(claim_key)):
            fails.append(f"label_disagrees_with_claim:{label_name}")

    # An operational section while auth is down would mean somebody owns rows
    # nobody authenticated to write.
    if shell.get("customer_auth_live") is False:
        for section in shell.get("sections") or []:
            if section.get("operational") is True:
                fails.append(f"operational_without_auth:{section.get('section_id')}")

    return fails
