"""Customer persistence spine decision (Gate 114D).

The order in which the eight lanes should become real, and what each one is
waiting on. Recommends; applies nothing.

## Why order is a safety question rather than a planning one

Each lane, built out of order, produces a specific dishonest artifact:

```text
digest before auth+persistence+sources    a digest of nothing, delivered to
                                          nobody, describing sources nobody
                                          is watching
awarded before document persistence       an award record whose evidence has
                                          nowhere to live, so the requirements
                                          it tracks cannot be substantiated
onboarding before auth+binding+profile    an onboarding flow that collects a
                                          Tribe's details into no owned row
```

Those are the three constraints the brief names, and they are enforced here as
refusals with reasons rather than as advice in a document.

## The sequence is derived, not listed

`recommended_sequence` is produced by walking the dependency graph below and
reporting, for each lane, whether its prerequisites are met. `ready_to_build_next`
is the first lane whose prerequisites are *all* satisfied — so the order changes
when the world does, and a lane that becomes buildable is noticed rather than
waited for.

## The one thing this service will not do

It will not recommend a lane as operational. Every lane it names is a
recommendation to *build*, and building a lane is not turning it on: the guard
in Gate 114C still decides each write, and every capability still needs customer
auth before any of it operates.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.customer_persistence_capability_service import (
    CAPABILITIES,
    RLS_ANCHOR_COLUMN,
    build_capability_matrix,
)

SCHEMA_VERSION = "nf_customer_persistence_spine_decision_v1"

# The order the brief specifies, and the reason each position is where it is.
# Position is not preference: each entry's prerequisites are what actually
# order the sequence, and this tuple is the tie-break among ready lanes.
SPINE_SEQUENCE: tuple[tuple[str, str, str], ...] = (
    (
        "identity_binding_persistence",
        "write_identity_binding",
        "nothing else can be owned by an organization until a binding says "
        "which organization a tenant label corresponds to",
    ),
    (
        "tenant_profile_persistence",
        "write_tenant_profile",
        "the first row a real customer owns, and the thing every other lane "
        "attaches to",
    ),
    (
        "awarded_grants_persistence",
        "write_awarded_grant",
        "an award is the anchor its requirements hang from",
    ),
    (
        "award_requirements_persistence",
        "write_award_requirement",
        "requirements are meaningless without the award they came from, and "
        "unsubstantiable without somewhere to keep the evidence",
    ),
    (
        "proof_audit_persistence",
        "write_proof_event",
        "a requirement without its proof trail records what was due and not "
        "what was done, and an auditor asks the second question",
    ),
    (
        "document_library_persistence",
        "write_document_library_item",
        "evidence needs a home before anything claims to track compliance",
    ),
    (
        "tenant_digest_persistence",
        "write_digest_record",
        "a digest summarises persisted state over live sources; without both "
        "it summarises fixtures",
    ),
    (
        "source_watchlist_persistence",
        "write_source_watchlist",
        "what a tenant watches is only meaningful once sources are collected",
    ),
    (
        "beta_onboarding_persistence",
        "write_beta_onboarding_record",
        "onboarding is the last thing built and the first thing shown; it "
        "needs everything under it to be real",
    ),
)

# Prerequisites per lane. Each names other capabilities, or one of the four
# non-capability preconditions below.
CUSTOMER_AUTH = "customer_auth"
DOCUMENT_STORAGE = "document_storage"
EMAIL_DELIVERY = "email_delivery"
LIVE_SOURCES = "live_source_collection"

SPINE_PREREQUISITES: dict[str, tuple[str, ...]] = {
    "identity_binding_persistence": (CUSTOMER_AUTH,),
    "tenant_profile_persistence": (CUSTOMER_AUTH, "identity_binding_persistence"),
    "awarded_grants_persistence": (CUSTOMER_AUTH, "tenant_profile_persistence"),
    "award_requirements_persistence": (
        CUSTOMER_AUTH,
        "awarded_grants_persistence",
        DOCUMENT_STORAGE,
    ),
    "proof_audit_persistence": (
        CUSTOMER_AUTH,
        "award_requirements_persistence",
        DOCUMENT_STORAGE,
    ),
    "document_library_persistence": (CUSTOMER_AUTH, DOCUMENT_STORAGE),
    "tenant_digest_persistence": (
        CUSTOMER_AUTH,
        "tenant_profile_persistence",
        LIVE_SOURCES,
    ),
    "source_watchlist_persistence": (CUSTOMER_AUTH, LIVE_SOURCES),
    "beta_onboarding_persistence": (
        CUSTOMER_AUTH,
        "identity_binding_persistence",
        "tenant_profile_persistence",
    ),
}

DECISION_FIELDS: tuple[str, ...] = (
    "recommended_sequence",
    "requires_migrations",
    "requires_repositories",
    "requires_auth",
    "requires_document_storage",
    "requires_email_delivery",
    "ready_to_build_next",
    "blocked_reasons",
    "next_gate_recommendation",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _module_importable(name: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _detect_document_storage() -> bool:
    """Is there somewhere a document's bytes can actually live?

    This asked whether `nativeforge.services.award_document_store_service`
    imports. That is a module-existence proxy, and Gate 114 named the shape when
    it found `customer_persistence_live` probing whether a repositories module
    imports: it "would have flipped to True for an empty file".

    Here the consequence was worse than a wrong flag. `DOCUMENT_STORAGE` is the
    last unmet prerequisite on `award_requirements_persistence` and
    `proof_audit_persistence`, so creating a file with that name would have told
    both lanes their evidence had a home, cleared `operational_out_of_sequence`
    on both, and let `operational_awarded_recommended` go true - with zero bytes
    stored anywhere.

    Two conditions now, and both are real:

    ```text
    metadata has a home   the document lane has a write path
    bytes have a home     detect_body_store_mode() is production-capable
    ```

    Gate 127 built the first. The second is Gate 96's detector, which reports
    `unconfigured`, so this stays false - correctly, because the prerequisite
    means "evidence has somewhere to go" and it does not.
    """
    try:
        from nativeforge.services.award_document_store_persistence_validation_service import (  # noqa: E501
            detect_object_store_configured,
        )
        from nativeforge.services.customer_persistence_capability_service import (
            build_capability,
        )
    except ImportError:  # pragma: no cover - both modules are in this repository
        return False

    lane = build_capability("document_library_persistence")
    return bool(lane.get("write_path_available") and detect_object_store_configured())


def _detect_preconditions() -> dict[str, bool]:
    """The four things that are not capabilities. Each detected separately."""
    from nativeforge.services.tenant_beta_readiness_service import (
        build_tenant_beta_readiness,
    )

    beta = build_tenant_beta_readiness()
    return {
        CUSTOMER_AUTH: bool(beta.get("customer_auth_live")),
        EMAIL_DELIVERY: bool(beta.get("email_delivery_available")),
        LIVE_SOURCES: bool(beta.get("live_source_collection_available")),
        DOCUMENT_STORAGE: _detect_document_storage(),
    }


def build_persistence_spine_decision(
    *,
    capability_matrix: dict[str, Any] | None = None,
    preconditions: dict[str, bool] | None = None,
    signing_key_readiness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The safest order to make persistence real. Recommends; applies nothing."""
    matrix = (
        capability_matrix
        if capability_matrix is not None
        else build_capability_matrix()
    )
    pre = preconditions if preconditions is not None else _detect_preconditions()

    # Gate 119B. `customer_auth_live` already accounts for the signing key, so
    # this changes no decision - it names one. "No customer auth" is true and
    # unactionable; "no signing key, and here is the environment variable" is
    # the same fact an owner can do something about.
    from nativeforge.services.customer_auth_signing_key_readiness_service import (
        build_signing_key_readiness,
    )

    signing = (
        signing_key_readiness
        if signing_key_readiness is not None
        else build_signing_key_readiness()
    )
    signing_ready = bool(signing.get("can_sign_production_session"))

    by_name = {row["capability"]: row for row in matrix.get("rows") or []}

    # A lane counts as satisfied for a downstream lane once it has a write path
    # AND could be operated. A built-but-unusable lane does not unblock the next
    # one - that is how a chain of unusable lanes gets built.
    def satisfied(name: str) -> bool:
        if name in pre:
            return bool(pre[name])
        row = by_name.get(name)
        return bool(row and row.get("operational"))

    blocked_reasons: list[str] = []
    sequence: list[dict[str, Any]] = []

    for position, (capability, operation, why) in enumerate(SPINE_SEQUENCE, start=1):
        row = by_name.get(capability, {})
        prereqs = SPINE_PREREQUISITES[capability]
        unmet = [name for name in prereqs if not satisfied(name)]

        needs_migration = not row.get("schema_available", False)
        needs_repository = not row.get("repository_available", False)

        sequence.append(
            {
                "position": position,
                "capability": capability,
                "guard_operation": operation,
                "why_here": why,
                "schema_available": bool(row.get("schema_available")),
                "repository_available": bool(row.get("repository_available")),
                "rls_backed": bool(row.get("rls_backed")),
                "operational": bool(row.get("operational")),
                "requires_migration": needs_migration,
                "requires_repository": needs_repository,
                "prerequisites": list(prereqs),
                "unmet_prerequisites": unmet,
                # Ready to build means buildable and not yet built. A lane that
                # already operates needs no build recommendation, and listing
                # one would make the sequence read as if nothing had happened.
                "ready_to_build": bool(not unmet and not row.get("operational")),
                # The interesting disagreement: a lane the capability model says
                # can be written, sitting ahead of prerequisites the spine says
                # it needs. Mechanically operable, sequentially premature. This
                # is reported rather than suppressed - the spine exists to
                # notice it, and a decision that stayed silent about it would be
                # the more dangerous artifact.
                "operational_out_of_sequence": bool(row.get("operational") and unmet),
            }
        )

    # The first lane whose prerequisites are all met. Derived by walking the
    # sequence, so it moves on its own when a precondition changes.
    ready = [entry for entry in sequence if entry["ready_to_build"]]
    ready_to_build_next = ready[0]["capability"] if ready else None

    if not pre[CUSTOMER_AUTH]:
        blocked_reasons.append("no_customer_auth_so_no_lane_can_be_operated")
    if not signing_ready:
        blocked_reasons.append(
            "no_session_signing_key_fit_to_sign_so_no_session_can_be_issued"
        )
    if not pre[DOCUMENT_STORAGE]:
        blocked_reasons.append("no_document_storage_for_award_evidence")
    if not pre[LIVE_SOURCES]:
        blocked_reasons.append("no_live_source_collection_for_digest_or_watchlist")
    if not pre[EMAIL_DELIVERY]:
        blocked_reasons.append("no_email_delivery_for_digest_distribution")
    if ready_to_build_next is None:
        blocked_reasons.append("every_lane_is_waiting_on_an_unmet_prerequisite")

    # The three constraints the brief names, checked against the sequence rather
    # than trusted to the ordering. Each is a claim that could otherwise be made
    # by a reader skimming for a green line.
    digest = by_name.get("tenant_digest_persistence", {})
    onboarding = by_name.get("beta_onboarding_persistence", {})

    operational_digest_recommended = bool(digest.get("operational"))

    # "Awarded tracking" is two lanes and two questions, and this line has been
    # wrong about both in turn.
    #
    # Gate 124 found it reading only the awards lane while the invariant below
    # asked about award_requirements_persistence. It did not matter while both
    # lanes were equally empty; building the awards half separated them.
    #
    # Gate 125 found the repaired version still wrong. A lane's `operational`
    # means schema + anchor + RLS + repository + contract + auth. It says
    # nothing about the lane's *product* prerequisites, and award_requirements
    # has one the spine has always named: document_storage. Building the
    # requirements half separated capability-operational from ready-to-operate.
    #
    # `by_name` above is built from the capability matrix, whose rows carry no
    # prerequisites at all — so a conjunct written against it reads None, and
    # `not (None or [])` is True for every lane forever. The sequence entries
    # are what carry `unmet_prerequisites`, and each already derives
    # `operational_out_of_sequence` as exactly "operable, and not yet due".
    sequenced = {entry["capability"]: entry for entry in sequence}
    # Three lanes as of Gate 126. An award, what it obliges, and what was filed
    # against it: an auditor reads all three, so recommending operation on two
    # would recommend a compliance record with no evidence in it.
    awarded_lanes = tuple(
        sequenced.get(name, {})
        for name in (
            "awarded_grants_persistence",
            "award_requirements_persistence",
            "proof_audit_persistence",
        )
    )
    operational_awarded_recommended = bool(
        all(lane.get("operational") for lane in awarded_lanes)
        and not any(lane.get("operational_out_of_sequence") for lane in awarded_lanes)
    )
    beta_onboarding_recommended = bool(onboarding.get("operational"))

    requires_migrations = sorted(
        entry["capability"] for entry in sequence if entry["requires_migration"]
    )
    requires_repositories = sorted(
        entry["capability"] for entry in sequence if entry["requires_repository"]
    )

    out_of_sequence = sorted(
        entry["capability"]
        for entry in sequence
        if entry["operational_out_of_sequence"]
    )
    for capability in out_of_sequence:
        blocked_reasons.append(f"operational_ahead_of_its_prerequisites:{capability}")

    next_gate = _next_gate_recommendation(ready_to_build_next, pre)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "rls_anchor": RLS_ANCHOR_COLUMN,
            "recommended_sequence": sequence,
            "sequence_length": len(sequence),
            "requires_migrations": requires_migrations,
            "requires_repositories": requires_repositories,
            "requires_auth": not pre[CUSTOMER_AUTH],
            # Gate 120B. Reported, not recommended: a repository existing does
            # not change what the next gate should be while auth blocks every
            # lane at once. It changes what that gate will find waiting for it.
            "identity_binding_repository_available": _module_importable(
                "nativeforge.services.tenant_customer_org_binding_repository_service"
            ),
            "verified_binding_workflow_available": _module_importable(
                "nativeforge.services.verified_binding_workflow_service"
            ),
            "verified_operational_binding": False,
            # Gate 121E. The spine has recommended `customer_authentication`
            # since Gate 114 and still does. What changed is that the
            # recommendation now has a checklist behind it: eight named
            # blockers, each with an owner, rather than one unactionable
            # sentence.
            "auth_activation_blocker_names": _auth_activation_blockers(),
            "auth_activation_runbook_available": _module_importable(
                "nativeforge.services.customer_auth_activation_runbook_service"
            ),
            "requires_session_signing_key": not signing_ready,
            "session_signing_key_ready": signing_ready,
            "session_signing_key_source": signing.get("signing_key_source"),
            "requires_document_storage": not pre[DOCUMENT_STORAGE],
            "requires_email_delivery": not pre[EMAIL_DELIVERY],
            "requires_live_source_collection": not pre[LIVE_SOURCES],
            "ready_to_build_next": ready_to_build_next,
            "ready_to_build": [entry["capability"] for entry in ready],
            "capabilities_operational_out_of_sequence": out_of_sequence,
            "blocked_reasons": sorted(set(blocked_reasons)),
            "next_gate_recommendation": next_gate,
            # Recommendations, never permissions.
            "operational_digest_recommended": operational_digest_recommended,
            "operational_awarded_recommended": operational_awarded_recommended,
            "beta_onboarding_recommended": beta_onboarding_recommended,
            "demo_persistence_allowed": True,
            "demo_persistence_label": "demo_fixture",
            # Constants: a decision changes no schema and writes no row.
            "customer_persistence_live": bool(matrix.get("customer_persistence_live")),
            "schema_changed": False,
            "rows_written": 0,
            "persisted": False,
            "fabricated": False,
            "live_fetch_performed": False,
        }
    )


def _auth_activation_blockers() -> list[str]:
    """The named blockers, or an empty list if the gate cannot be read.

    Reported, never derived from. The spine's recommendation is unchanged by
    this; it is what a reader does after reading the recommendation.
    """
    try:
        from nativeforge.services.customer_auth_activation_gate_service import (
            build_customer_auth_activation_gate,
        )

        return list(
            build_customer_auth_activation_gate().get("activation_blocker_names") or []
        )
    except ImportError:  # pragma: no cover - the module is in this repository
        return []


def _next_gate_recommendation(
    ready_to_build_next: str | None, pre: dict[str, bool]
) -> dict[str, Any]:
    """What the next gate should be, and why that rather than the next lane."""
    if not pre[CUSTOMER_AUTH]:
        return {
            "recommendation": "customer_authentication",
            "why": (
                "every lane in the spine lists customer_auth as a prerequisite, "
                "so no amount of schema moves any of them. Auth is the only "
                "thing that unblocks more than one lane at once."
            ),
            "unblocks": sorted(SPINE_PREREQUISITES),
        }
    if ready_to_build_next:
        return {
            "recommendation": ready_to_build_next,
            "why": "its prerequisites are met and it is earliest in the sequence",
            "unblocks": sorted(
                name
                for name, prereqs in SPINE_PREREQUISITES.items()
                if ready_to_build_next in prereqs
            ),
        }
    return {
        "recommendation": "unknown",
        "why": "no lane has all its prerequisites met and auth is not the blocker",
        "unblocks": [],
    }


def spine_decision_invariant_failures(decision: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if decision.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in DECISION_FIELDS:
        if field not in decision:
            fails.append(f"spine_decision_missing_field:{field}")

    for constant in (
        "schema_changed",
        "persisted",
        "fabricated",
        "live_fetch_performed",
    ):
        if decision.get(constant) is not False:
            fails.append(f"spine_decision_claimed:{constant}")

    if decision.get("rows_written") != 0:
        fails.append("spine_decision_wrote_rows")

    if decision.get("rls_anchor") != RLS_ANCHOR_COLUMN:
        fails.append("spine_anchored_on_a_label")

    sequence = decision.get("recommended_sequence") or []
    if len(sequence) != len(SPINE_SEQUENCE):
        fails.append("spine_sequence_does_not_cover_every_capability")

    covered = {entry.get("capability") for entry in sequence}
    for name in CAPABILITIES:
        if name not in covered:
            fails.append(f"spine_sequence_omits:{name}")

    # Positions are 1..n in order, so a reordered sequence is observable.
    for index, entry in enumerate(sequence, start=1):
        if entry.get("position") != index:
            fails.append(f"spine_sequence_out_of_order_at:{entry.get('capability')}")

    # Identity binding is first. Every lane that owns customer data needs to
    # know which organization owns it, and that is what a binding establishes.
    if sequence and sequence[0].get("capability") != "identity_binding_persistence":
        fails.append("spine_does_not_start_with_identity_binding")

    # The three constraints the brief names.
    by_name = {entry.get("capability"): entry for entry in sequence}

    digest = by_name.get("tenant_digest_persistence", {})
    if decision.get("operational_digest_recommended"):
        for required in ("customer_auth", "tenant_profile_persistence"):
            if required in (digest.get("unmet_prerequisites") or []):
                fails.append(f"digest_recommended_operational_without:{required}")
        if "live_source_collection" in (digest.get("unmet_prerequisites") or []):
            fails.append("digest_recommended_operational_without_sources")

    awarded = by_name.get("award_requirements_persistence", {})
    if decision.get("operational_awarded_recommended") and "document_storage" in (
        awarded.get("unmet_prerequisites") or []
    ):
        fails.append("awarded_recommended_operational_without_document_persistence")

    onboarding = by_name.get("beta_onboarding_persistence", {})
    if decision.get("beta_onboarding_recommended"):
        for required in (
            "customer_auth",
            "identity_binding_persistence",
            "tenant_profile_persistence",
        ):
            if required in (onboarding.get("unmet_prerequisites") or []):
                fails.append(f"onboarding_recommended_without:{required}")

    # A lane cannot be ready to build while a prerequisite is unmet, and a lane
    # that already operates is not waiting to be built.
    for entry in sequence:
        if entry.get("ready_to_build") and entry.get("unmet_prerequisites"):
            fails.append(
                f"ready_to_build_with_unmet_prerequisites:{entry.get('capability')}"
            )
        if entry.get("ready_to_build") and entry.get("operational"):
            fails.append(
                f"ready_to_build_but_already_operational:{entry.get('capability')}"
            )

    # A lane operating ahead of its prerequisites is a real state, not an
    # impossible one - the capability model answers "can this be written" and
    # the spine answers "should it be yet". What must never happen is the
    # decision failing to say so.
    reported = set(decision.get("capabilities_operational_out_of_sequence") or [])
    for entry in sequence:
        capability = entry.get("capability")
        premature = bool(entry.get("operational") and entry.get("unmet_prerequisites"))
        if premature and capability not in reported:
            fails.append(f"operational_out_of_sequence_unreported:{capability}")
        if entry.get("operational_out_of_sequence") is not premature:
            fails.append(f"out_of_sequence_flag_disagrees_with_the_entry:{capability}")
    for capability in reported:
        if f"operational_ahead_of_its_prerequisites:{capability}" not in (
            decision.get("blocked_reasons") or []
        ):
            fails.append(f"out_of_sequence_without_a_blocked_reason:{capability}")

    # The named next lane must actually be ready.
    nxt = decision.get("ready_to_build_next")
    if nxt is not None:
        entry = by_name.get(nxt)
        if entry is None:
            fails.append(f"ready_to_build_next_is_not_in_the_sequence:{nxt}")
        elif not entry.get("ready_to_build"):
            fails.append(f"ready_to_build_next_is_not_ready:{nxt}")

    # Demo persistence is permitted only under its label.
    if decision.get("demo_persistence_allowed") and (
        decision.get("demo_persistence_label") != "demo_fixture"
    ):
        fails.append("demo_persistence_allowed_without_its_label")

    # A refusal must name itself.
    if (
        decision.get("blocked_reasons") == []
        and decision.get("customer_persistence_live") is False
    ):
        fails.append("persistence_not_live_without_a_reason")

    return fails
