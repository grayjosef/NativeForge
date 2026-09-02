"""Gate 137B: prepare a verified binding candidate, with `is_demo` derived.

## The defect this exists to close

`tenant_customer_org_binding_repository_service.prepare_insert` takes
`is_demo: bool = False` as a **parameter** and reads no organization row.
Measured in Gate 137A:

```text
insert_binding(organization_id=<the demo org>,
               binding_status="verified_binding",
               is_demo=False)
  -> rows_written               1
  -> production_verified_binding TRUE
  -> blocked_reasons            []
  -> invariant_failures         []
  -> stored: is_demo=0 against a demo organization
```

The demo organization carried a production verified binding, every invariant
passed, and the row landed in a partition the RLS predicate matches for nobody:

```sql
organization_id = current_setting('app.current_org_id')::uuid
AND is_demo = current_setting('app.current_org_is_demo')::boolean
```

`is_demo=0` against a demo organization matches no demo session and no real one.
A row nothing can see is a row nothing can revoke.

Gate 132's membership bootstrap refused to take this parameter and recorded
why:

> "a caller-supplied `is_demo` is a caller-supplied choice of which partition a
> row lands in. Rows go where the organization row says they go."

Gate 120B's binding repository, written eight gates later, took it. And the
workflow above it made the same substitution one level higher -
`is_demo=bool(principal["is_demo_principal"])` - so a principal's
self-description decided an organization's partition.

## What this module does instead

```text
is_demo                derived from organizations.org_type, no parameter
demo -> verified       refused by CLASSIFICATION, not by the caller's label
real org activation    requires the approval object from 137C
verifier               identity id and timestamp, both, per migration 0029
provenance             recorded: who classified, who approved, who verified
```

It prepares. It writes nothing and holds no connection open on its own - the
connection is used to ask the organizations table one question and is the
caller's.

## What the result never carries

No provider subject, no email, no token, no cookie, no customer data. The
verifier is an internal identity id, which is the same thing the row stores.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from nativeforge.services.demo_org_classification_service import classify_organization
from nativeforge.services.tenant_customer_org_binding_repository_service import (
    DEMO_STATUS,
    get_active_binding,
    insert_binding,
    prepare_insert,
)
from nativeforge.services.verified_operational_binding_activation_boundary_service import (  # noqa: E501
    DEMO_ORGANIZATION_ID,
    REAL_ORGANIZATION_ID,
    build_real_org_binding_activation_decision,
)

SCHEMA_VERSION = "nf_verified_operational_binding_preparation_v1"

#: The one status this module prepares. A revocation or a conflict is not a
#: verified operational binding and does not come through here.
VERIFIED_STATUS = "verified_binding"

#: Where the classification came from. Recorded rather than assumed, because
#: "derived" is a claim and a claim should say from what.
CLASSIFICATION_SOURCE = "organizations.org_type"

#: Where the approval came from.
APPROVAL_SOURCE = "verified_operational_binding_activation_boundary_service"

#: Where the verifier came from.
VERIFIER_SOURCE = "nf_identities.id"

DEMO_REFUSED = "demo_organization_cannot_be_a_verified_operational_binding"
LABEL_MISMATCH = "supplied_is_demo_disagrees_with_the_organization_row"
NOT_ACTIVATED = "real_org_binding_activation_not_approved"
NO_VERIFIER = "verified_binding_without_a_verifier_identity"
NO_VERIFIED_AT = "verified_binding_without_a_verified_at"

#: Keys that must never appear in a prepared result. A scan asserts it.
FORBIDDEN_RESULT_KEYS: tuple[str, ...] = (
    "subject",
    "provider_subject",
    "email",
    "id_token",
    "access_token",
    "refresh_token",
    "client_secret",
    "code_verifier",
    "session_cookie_value",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _uuid_shaped(value: Any) -> bool:
    try:
        uuid.UUID(str(value or "").strip())
    except (ValueError, AttributeError, TypeError):
        return False
    return True


def prepare_verified_operational_binding(
    *,
    organization_id: Any = None,
    tenant_id: Any = None,
    customer_org_id: Any = None,
    verified_by_identity_id: Any = None,
    verified_at: Any = None,
    binding_source: Any = "admin_verified",
    binding_confidence: Any = "verified",
    approval: Any = None,
    app_env: str | None = None,
    connection: Any = None,
    org_type_in_database: str | None = None,
    authorized_organization_ids: frozenset[str] | None = None,
    is_demo: Any = None,
    **offered: Any,
) -> dict[str, Any]:
    """Decide whether a verified operational binding may be prepared.

    ``is_demo`` is accepted only so a caller that supplies one can be told it
    was not honoured. It never decides anything: the organization row does, and
    a supplied value that disagrees with the row is a named refusal rather than
    a silent override. That is the difference between this and the repository
    function it wraps.
    """
    requested = str(organization_id or "").strip().lower()
    blocked_reasons: list[str] = []

    # -- 1. classification, from the row ------------------------------------
    classification = classify_organization(
        requested or None,
        connection=connection,
        org_type_in_database=org_type_in_database,
    )
    classified = bool(classification.get("classification_available"))
    derived_is_demo = bool(classification.get("is_demo"))

    if not requested:
        blocked_reasons.append("binding_without_an_organization_id_anchor")
    elif not _uuid_shaped(requested):
        blocked_reasons.append("organization_id_anchor_is_not_uuid_shaped")
    if not classified:
        blocked_reasons.append("organization_could_not_be_classified")

    # The refusal Gate 113 was credited with and did not have: against the
    # organization, not against the caller's word for it.
    if derived_is_demo or requested == DEMO_ORGANIZATION_ID:
        blocked_reasons.append(DEMO_REFUSED)

    # A caller that supplied one learns it was not honoured.
    supplied_is_demo = None if is_demo is None else bool(is_demo)
    if supplied_is_demo is not None and supplied_is_demo != derived_is_demo:
        blocked_reasons.append(LABEL_MISMATCH)

    # -- 2. activation, from 137C -------------------------------------------
    decision = build_real_org_binding_activation_decision(
        organization_id=requested or None,
        approval=approval,
        app_env=app_env,
        connection=connection,
        org_type_in_database=org_type_in_database,
        authorized_organization_ids=authorized_organization_ids,
        **offered,
    )
    activated = bool(decision["approves_real_org_binding_activation"])
    if not activated:
        blocked_reasons.append(NOT_ACTIVATED)
        blocked_reasons.extend(
            f"boundary:{reason}" for reason in decision["blocked_reasons"]
        )

    # -- 3. the verifier pair, before the repository is asked ---------------
    verifier = str(verified_by_identity_id or "").strip()
    moment = str(verified_at or "").strip()
    if not verifier:
        blocked_reasons.append(NO_VERIFIER)
    elif not _uuid_shaped(verifier):
        blocked_reasons.append("verifier_identity_is_not_uuid_shaped")
    if not moment:
        blocked_reasons.append(NO_VERIFIED_AT)

    # -- 4. the repository contract, with is_demo DERIVED -------------------
    contract = prepare_insert(
        organization_id=requested or None,
        tenant_id=tenant_id,
        customer_org_id=customer_org_id,
        organization_profile_id=offered.get("organization_profile_id"),
        binding_status=VERIFIED_STATUS,
        binding_source=binding_source,
        binding_confidence=binding_confidence,
        verified_by_identity_id=verifier or None,
        verified_at=moment or None,
        # Derived. The whole point.
        is_demo=derived_is_demo,
        human_review_required=False,
    )
    blocked_reasons.extend(
        f"contract:{reason}" for reason in contract["blocked_reasons"]
    )

    ready = bool(
        classified
        and not derived_is_demo
        and activated
        and contract["storage_allowed"]
        and not blocked_reasons
    )

    result = {
        "schema_version": SCHEMA_VERSION,
        "binding_ready_to_write": ready,
        "organization_id": requested or None,
        "tenant_id": str(tenant_id or "").strip() or None,
        "customer_org_id": str(customer_org_id or "").strip() or None,
        "binding_status": VERIFIED_STATUS,
        "binding_source": contract["binding_source"],
        "binding_confidence": contract["binding_confidence"],
        # Derived, and reported beside what the caller offered so the
        # difference is visible rather than resolved silently.
        "is_demo_derived": derived_is_demo,
        "is_demo_supplied_by_caller": supplied_is_demo,
        "is_demo_authority": CLASSIFICATION_SOURCE,
        "organization_classified": classified,
        "organization_is_the_demo_org": requested == DEMO_ORGANIZATION_ID,
        "organization_is_the_refused_real_org": requested == REAL_ORGANIZATION_ID,
        # Provenance: four sources, each named.
        "classification_source": CLASSIFICATION_SOURCE,
        "approval_source": APPROVAL_SOURCE,
        "approval_scope": decision["approval_scope"],
        "approval_authorized_by": decision["approval_authorized_by"],
        "verifier_source": VERIFIER_SOURCE,
        "verified_by_identity_id": verifier or None,
        "verified_at": moment or None,
        "membership_source": "not_consulted",
        "membership_source_note": (
            "binder authorization decides by role, not by a membership row; "
            "recorded in 719 as the next gate's work"
        ),
        "binding_provenance": "operator_verified_under_recorded_approval",
        "activation_approved": activated,
        "activation_environment": decision["environment"],
        "production_binding_activation": decision[
            "approves_production_binding_activation"
        ],
        # Constants. Preparing writes nothing and claims nothing.
        "write_performed": False,
        "rows_written": 0,
        "real_customer_rows_written": 0,
        "real_organization_touched": False,
        "production_rollout": False,
        "controlled_customer_pilot": False,
        "demo_status_name": DEMO_STATUS,
        "blocked_reasons": sorted(set(blocked_reasons)),
    }

    for key in FORBIDDEN_RESULT_KEYS:
        if key in result:  # pragma: no cover - constant guard
            raise AssertionError(f"prepared result carries {key!r}")

    return _json_safe(result)


def write_verified_operational_binding(
    *,
    connection: Any = None,
    binding_id: uuid.UUID | None = None,
    created_at: Any = None,
    **fields: Any,
) -> dict[str, Any]:
    """Prepare, then write, with ``is_demo`` derived on the way through.

    The point of routing the write through here rather than calling
    `insert_binding` directly is that `insert_binding` still accepts
    ``is_demo`` from its caller. This is the entry point that does not offer
    that choice: the organization row supplies it, and a caller who supplied
    one is told it was refused.

    Nothing is written unless `prepare_verified_operational_binding` says
    ready, which means the activation approval from 137C is present.
    """
    decision = prepare_verified_operational_binding(connection=connection, **fields)
    blocked_reasons = list(decision["blocked_reasons"])

    if connection is None:
        blocked_reasons.append("no_connection_supplied_so_nothing_was_written")

    write: dict[str, Any] = {"rows_written": 0, "write_performed": False}
    if decision["binding_ready_to_write"] and connection is not None:
        write = insert_binding(
            connection=connection,
            binding_id=binding_id,
            created_at=created_at,
            organization_id=decision["organization_id"],
            tenant_id=decision["tenant_id"],
            customer_org_id=decision["customer_org_id"],
            binding_status=decision["binding_status"],
            binding_source=decision["binding_source"],
            binding_confidence=decision["binding_confidence"],
            verified_by_identity_id=decision["verified_by_identity_id"],
            verified_at=decision["verified_at"],
            # Derived, carried through, never the caller's.
            is_demo=decision["is_demo_derived"],
            human_review_required=False,
        )
        blocked_reasons.extend(
            f"repository:{reason}" for reason in write["blocked_reasons"] or []
        )

    readback: dict[str, Any] = {}
    if write.get("write_performed") and connection is not None:
        # Read it back through the anchored read, so "it can be read by
        # organization_id" is a measured fact about this row rather than a
        # property of the function that wrote it.
        readback = get_active_binding(
            connection=connection,
            organization_id=decision["organization_id"],
            tenant_id=decision["tenant_id"],
            customer_org_id=decision["customer_org_id"],
        )

    written = bool(write.get("write_performed"))

    return _json_safe(
        {
            **decision,
            "operation": "write_verified_operational_binding",
            # Kept separate from the merged list below. A duplicate refused by
            # the repository is a legitimate outcome of a sound preparation,
            # and folding the two together made it read as a broken invariant
            # - `prepared_alongside_blockers` fired on a refusal working
            # exactly as intended.
            "preparation_blocked_reasons": list(decision["blocked_reasons"]),
            "write_performed": written,
            "rows_written": int(write.get("rows_written") or 0),
            "readback_performed": bool(readback.get("read_performed")),
            "readback_production_verified_binding": bool(
                readback.get("production_verified_binding")
            ),
            "readback_is_demo": bool(readback.get("demo_fixture")),
            "verified_operational_binding": bool(
                written and readback.get("production_verified_binding")
            ),
            "blocked_reasons": sorted(set(blocked_reasons)),
        }
    )


def write_invariant_failures(result: dict[str, Any]) -> list[str]:
    """What must never be true of a written verified binding."""
    # The preparation invariants are asked about the preparation, using the
    # blockers preparation itself produced. The write's own refusals are
    # judged below.
    fails = [
        fail
        for fail in preparation_invariant_failures(
            {
                **result,
                "write_performed": False,
                "rows_written": 0,
                # `in`, not `or`. An empty preparation-blocker list is the
                # SUCCESS case and is falsy, so `or` fell straight through to
                # the merged list and the fix did nothing - the duplicate
                # refusal still read as a broken invariant.
                "blocked_reasons": list(
                    result["preparation_blocked_reasons"]
                    if "preparation_blocked_reasons" in result
                    else result.get("blocked_reasons") or []
                ),
            }
        )
        if fail != "preparation_wrote_something"
    ]

    if result.get("verified_operational_binding"):
        if not result.get("write_performed"):
            fails.append("verified_operational_binding_without_a_write")
        if not result.get("readback_performed"):
            fails.append("verified_operational_binding_that_cannot_be_read_back")
        if result.get("readback_is_demo"):
            fails.append("verified_operational_binding_landed_in_the_demo_partition")
        if not result.get("activation_approved"):
            fails.append("verified_operational_binding_without_an_approved_activation")
        if result.get("organization_is_the_refused_real_org"):
            fails.append("verified_operational_binding_for_the_refused_real_org")

    if result.get("write_performed") and not result.get("rows_written"):
        fails.append("write_performed_without_a_row")

    return sorted(set(fails))


def preparation_invariant_failures(result: dict[str, Any]) -> list[str]:
    """What must never be true of a prepared verified binding."""
    fails: list[str] = []

    if result.get("binding_ready_to_write"):
        if result.get("is_demo_derived"):
            fails.append("prepared_a_verified_binding_for_a_demo_organization")
        if result.get("organization_is_the_demo_org"):
            fails.append("prepared_a_verified_binding_for_the_demo_org_id")
        if result.get("organization_is_the_refused_real_org"):
            fails.append("prepared_a_verified_binding_for_the_refused_real_org")
        if not result.get("organization_classified"):
            fails.append("prepared_without_classifying_the_organization")
        if not result.get("activation_approved"):
            fails.append("prepared_without_an_approved_activation")
        if not result.get("verified_by_identity_id"):
            fails.append("prepared_a_verified_binding_without_a_verifier")
        if not result.get("verified_at"):
            fails.append("prepared_a_verified_binding_without_a_verified_at")
        if result.get("blocked_reasons"):
            fails.append("prepared_alongside_blockers")

    if result.get("is_demo_authority") != CLASSIFICATION_SOURCE:
        fails.append(f"is_demo_authority_changed:{result.get('is_demo_authority')}")

    if result.get("write_performed") or result.get("rows_written"):
        fails.append("preparation_wrote_something")
    if result.get("real_customer_rows_written"):
        fails.append("real_customer_rows_written")
    if result.get("real_organization_touched"):
        fails.append("real_organization_touched")
    if result.get("production_rollout"):
        fails.append("production_rollout_claimed")
    if result.get("controlled_customer_pilot"):
        fails.append("controlled_customer_pilot_claimed")

    for key in FORBIDDEN_RESULT_KEYS:
        if key in result:
            fails.append(f"result_carries_a_forbidden_key:{key}")

    if not result.get("binding_ready_to_write") and not result.get("blocked_reasons"):
        fails.append("nothing_prepared_and_nothing_blocked_it")

    return fails
