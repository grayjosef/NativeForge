"""Tenant / customer org identity binding (Gate 109B).

The relationship between a NativeForge tenant and a customer organization,
recorded rather than computed.

## Why this cannot be a derivation

Gate 108 found `tenant_id` and `customer_org_id` meeting on the awarded record
with nothing relating them. Gate 109A found the situation is worse than that:
there are four identity names in the tree, row-level security keys on the
organization UUID, and `tenant_id` has no column to persist into at all.

A binding is therefore a **record**. Two identifiers are related because somebody
said so and it was checked - never because they look alike, share a prefix, or
have similar names. `system_inferred_blocked` exists in the source vocabulary
precisely so that an attempt to infer one can be recorded as refused rather than
silently succeeding.

The failure this prevents is not hypothetical. Bind the wrong pair and a Tribe
sees another Tribe's awarded grants, their digest suppressions leak across, and
their document library opens to strangers.

## Matching strings are not a binding

Neither are matching names. `build_binding` never compares the two identifiers to
each other, and a caller that passes the same string for both gets no special
treatment - it gets a `conflict`, because one value cannot be two identity spaces
at once.

## Gate 51's derivation is evidence, not verification

`org_tenant_seat_model_service.make_tenant_id` produces `tn_<hash>` from an
*organization profile id*. That is a real relationship and it is recorded as
`binding_source: migration_import` when a caller supplies it - but it relates a
tenant id to a third identifier, not to the `customer_org_id` this binding is
about. It cannot promote a binding to verified on its own.

## Tenant id shape is recorded

Two incompatible shapes coexist:

```text
tn_<16 hex>          derived by Gate 51 from an organization profile id
anything else        free-form, supplied by the Gates 103-108 lanes
```

A binding record says which it holds. Treating them as one kind of thing would
make this contract worse than none, because it would look authoritative while
relating two different things.

## demo_fixture is not production verification

A demo binding lets a demo run. It never satisfies an operational read or write,
and `is_production_verified` is False on every binding that is not
`verified_binding` from an allowed source. The resolution guard enforces the
consequence; this service refuses to let the record claim otherwise.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

SCHEMA_VERSION = "nf_tenant_customer_org_identity_binding_v1"

BINDING_STATUSES = frozenset(
    {
        "unbound",
        "pending_review",
        "demo_fixture",
        "verified_binding",
        "conflict",
        "revoked",
        "unknown",
    }
)

BINDING_SOURCES = frozenset(
    {
        "human_entered",
        "admin_verified",
        "migration_import",
        "demo_fixture",
        "system_inferred_blocked",
        "unknown",
    }
)

# Sources that may support a verified binding. Derived affirmatively: a source
# not named here cannot verify, whatever else is true of the record.
VERIFYING_SOURCES = frozenset({"admin_verified", "migration_import"})

# The only status that permits operational reads and writes.
OPERATIONAL_BINDING_STATUSES = frozenset({"verified_binding"})

# Statuses that block every surface outright.
BLOCKING_BINDING_STATUSES = frozenset({"conflict", "revoked"})

BINDING_CONFIDENCES = frozenset({"none", "demo_only", "asserted", "verified"})

TENANT_ID_SHAPES = frozenset(
    {"gate51_derived", "free_form", "absent", "unknown"}
)

# Gate 51's shape: tn_ followed by 16 hex characters.
_GATE51_TENANT_ID_RE = re.compile(r"^tn_[0-9a-f]{16}$")

DEMO_LABEL = "demo_fixture"

BINDING_FIELDS: tuple[str, ...] = (
    "binding_id",
    "tenant_id",
    "customer_org_id",
    "binding_status",
    "binding_source",
    "binding_confidence",
    "created_at",
    "verified_at",
    "verified_by",
    "human_review_required",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _norm(value: Any, vocabulary: frozenset[str], *, fallback: str) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text in vocabulary else fallback


def classify_tenant_id_shape(tenant_id: Any) -> str:
    """Which kind of tenant id is this? Observed from the value, not declared."""
    text = str(tenant_id or "").strip()
    if not text:
        return "absent"
    if _GATE51_TENANT_ID_RE.match(text):
        return "gate51_derived"
    return "free_form"


def build_binding_id(*, tenant_id: Any, customer_org_id: Any) -> str:
    """Deterministic, and scoped to the pair it binds."""
    return hashlib.sha256(
        "|".join(
            str(part if part is not None else "")
            for part in (tenant_id, customer_org_id)
        ).encode()
    ).hexdigest()


def build_binding(
    *,
    tenant_id: Any = None,
    customer_org_id: Any = None,
    binding_source: Any = None,
    requested_status: Any = None,
    created_at: Any = None,
    verified_at: Any = None,
    verified_by: Any = None,
    demo_label: Any = None,
    revoked: bool = False,
    human_review_acknowledged: bool = False,
) -> dict[str, Any]:
    """Record how a tenant and a customer org are related. Nothing is inferred."""
    source = _norm(binding_source, BINDING_SOURCES, fallback="unknown")
    requested = _norm(requested_status, BINDING_STATUSES, fallback="unbound")

    blocked_reasons: list[str] = []

    has_tenant = bool(str(tenant_id or "").strip())
    has_org = bool(str(customer_org_id or "").strip())
    shape = classify_tenant_id_shape(tenant_id)

    if not has_tenant:
        blocked_reasons.append("binding_without_a_tenant_id")
    if not has_org:
        blocked_reasons.append("binding_without_a_customer_org_id")

    # One value cannot be two identity spaces at once. A caller passing the same
    # string for both has conflated them, which is the exact mistake this
    # contract exists to catch.
    same_value = (
        has_tenant
        and has_org
        and str(tenant_id).strip() == str(customer_org_id).strip()
    )
    if same_value:
        blocked_reasons.append("tenant_id_and_customer_org_id_are_the_same_value")

    if source == "system_inferred_blocked":
        blocked_reasons.append("system_inference_is_not_a_binding")
    if source == "unknown":
        blocked_reasons.append("binding_source_unknown")

    is_demo = source == "demo_fixture" or requested == "demo_fixture"
    if is_demo and str(demo_label or "").strip() != DEMO_LABEL:
        blocked_reasons.append("demo_binding_without_its_label")

    # Verification needs both ids, an allowed source, and an actual verifier.
    verification_supported = (
        has_tenant
        and has_org
        and not same_value
        and source in VERIFYING_SOURCES
        and bool(str(verified_by or "").strip())
        and bool(str(verified_at or "").strip())
    )
    if requested == "verified_binding" and not verification_supported:
        if source not in VERIFYING_SOURCES:
            blocked_reasons.append(f"source_cannot_verify_a_binding:{source}")
        if not (verified_by and verified_at):
            blocked_reasons.append("verified_binding_without_a_verifier")

    # Status is derived. A caller asks; the record decides.
    if revoked:
        status = "revoked"
    elif same_value:
        status = "conflict"
    elif not has_tenant or not has_org:
        status = "unbound"
    elif source == "system_inferred_blocked":
        status = "pending_review"
    elif is_demo:
        status = "demo_fixture" if not blocked_reasons else "pending_review"
    elif verification_supported and requested == "verified_binding":
        status = "verified_binding"
    elif source in {"human_entered", "admin_verified", "migration_import"}:
        # Both ids and a real source, but nobody has checked it yet.
        status = "pending_review"
    else:
        status = "unbound"

    confidence = {
        "verified_binding": "verified",
        "demo_fixture": "demo_only",
        "pending_review": "asserted",
    }.get(status, "none")

    human_review_required = bool(
        (blocked_reasons and not human_review_acknowledged)
        or status in {"pending_review", "conflict", "unknown"}
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "binding_id": build_binding_id(
                tenant_id=tenant_id, customer_org_id=customer_org_id
            ),
            "tenant_id": tenant_id,
            "customer_org_id": customer_org_id,
            "tenant_id_shape": shape,
            "binding_status": status,
            "binding_source": source,
            "binding_confidence": confidence,
            "created_at": created_at,
            "verified_at": verified_at if status == "verified_binding" else None,
            "verified_by": verified_by if status == "verified_binding" else None,
            "demo_label": demo_label if is_demo else None,
            "is_demo_binding": status == "demo_fixture",
            # A demo binding is never production verification.
            "is_production_verified": status == "verified_binding",
            "human_review_required": human_review_required,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Constants: nothing here derives one identity from the other.
            "derived_from_matching_strings": False,
            "derived_from_matching_names": False,
            "system_inferred": False,
            "identities_assumed_equivalent": False,
            "fabricated": False,
            "persisted": False,
            "live_fetch_performed": False,
        }
    )


def summarise_bindings(bindings: list[dict[str, Any]]) -> dict[str, Any]:
    """Counts per status. No global "bound" total - each pair stands alone."""
    by_status = {status: 0 for status in sorted(BINDING_STATUSES)}
    for binding in bindings:
        status = binding.get("binding_status")
        if status in by_status:
            by_status[status] += 1

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "binding_count": len(bindings),
            "by_binding_status": by_status,
            "verified_bindings": by_status["verified_binding"],
            "demo_bindings": by_status["demo_fixture"],
            "blocking_bindings": sum(
                by_status[status] for status in sorted(BLOCKING_BINDING_STATUSES)
            ),
            "needing_human_review": sum(
                1 for b in bindings if b.get("human_review_required")
            ),
            "identities_assumed_equivalent": False,
            "fabricated": False,
        }
    )


def binding_invariant_failures(binding: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if binding.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in BINDING_FIELDS:
        if field not in binding:
            fails.append(f"binding_missing_field:{field}")

    for constant in (
        "derived_from_matching_strings",
        "derived_from_matching_names",
        "system_inferred",
        "identities_assumed_equivalent",
        "fabricated",
        "persisted",
        "live_fetch_performed",
    ):
        if binding.get(constant) is not False:
            fails.append(f"binding_claimed:{constant}")

    if binding.get("binding_status") not in BINDING_STATUSES:
        fails.append("binding_status_out_of_vocabulary")
    if binding.get("binding_source") not in BINDING_SOURCES:
        fails.append("binding_source_out_of_vocabulary")
    if binding.get("binding_confidence") not in BINDING_CONFIDENCES:
        fails.append("binding_confidence_out_of_vocabulary")
    if binding.get("tenant_id_shape") not in TENANT_ID_SHAPES:
        fails.append("tenant_id_shape_out_of_vocabulary")

    status = binding.get("binding_status")

    # A verified binding needs both identities and a source that can verify.
    if status == "verified_binding":
        if not (binding.get("tenant_id") and binding.get("customer_org_id")):
            fails.append("verified_binding_without_both_identities")
        if binding.get("binding_source") not in VERIFYING_SOURCES:
            fails.append("verified_binding_from_a_source_that_cannot_verify")
        if not (binding.get("verified_by") and binding.get("verified_at")):
            fails.append("verified_binding_without_a_verifier")

    # One value can never bind to itself across two identity spaces.
    if (
        binding.get("tenant_id")
        and binding.get("customer_org_id")
        and str(binding["tenant_id"]).strip() == str(binding["customer_org_id"]).strip()
        and status != "conflict"
    ):
        fails.append("identical_identifiers_not_treated_as_a_conflict")

    # A demo binding is labelled, and is never production verification.
    if status == "demo_fixture":
        if binding.get("demo_label") != DEMO_LABEL:
            fails.append("demo_binding_without_its_label")
        if binding.get("is_production_verified"):
            fails.append("demo_binding_claimed_production_verification")

    # is_production_verified must agree with the status.
    if binding.get("is_production_verified") is not (status == "verified_binding"):
        fails.append("production_verification_disagrees_with_the_status")

    # A blocking or unresolved status must route to a person.
    if status in {"pending_review", "conflict"} and not binding.get(
        "human_review_required"
    ):
        fails.append("unresolved_binding_without_human_review")

    # A refusal must name itself.
    if status in {"unbound", "conflict"} and not binding.get("blocked_reasons"):
        fails.append("binding_refusal_without_a_reason")

    # Identity reproducible from the record's own fields.
    expected_id = build_binding_id(
        tenant_id=binding.get("tenant_id"),
        customer_org_id=binding.get("customer_org_id"),
    )
    if binding.get("binding_id") != expected_id:
        fails.append("binding_id_not_derivable_from_its_fields")

    return fails
