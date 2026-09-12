"""Gate 148C: is there consent, and is the customer beta scope approved?

## Both are absent, and neither is a code change

```text
consent_boundary_documented    false   nothing in this repository records that
                                       a tenant was told what is collected,
                                       retained, exported and deleted
customer_beta_scope_approved   false   Gate 145's fourth approval
```

Gate 142 named this gap and deliberately did not fill it. Building a consent
model before deciding what consent means here would have produced something
worse than its absence: a record that looks like agreement and is not.

## The gap this closes is one gate ahead, not today

Every post-award repository gates a production write on exactly two things:

```text
production_write and not customer_auth_live               -> blocked
production_write and not verified_operational_binding     -> blocked
```

Both are identity facts. Neither is consent. Gates 146 and 147 exist to make
both true — and on the day they do, a production customer write becomes
permitted with no consent recorded anywhere. The boundary has to exist before
those lanes turn, which is why this gate comes before Gate 150 rather than after.

## Consent is not inferred, and four things that look like it are named

A login, a membership, an accepted invite and an operator's note each become
available as Gates 146-147 land, and each reads as agreement. None is. The
refusals are explicit rather than implied, because an omission here would be
read as permission.

## Layered activations

Three customer data classes need a capability as well as consent, and consent
does not substitute for the capability or vice versa:

```text
customer_document_body           also needs object_store_configured
customer_contact_or_recipient    also needs email_delivery
source monitoring data           also needs source_monitoring_live
```

## It records nothing

`build_consent_boundary` reads its arguments and returns a decision. There is no
connection parameter, no consent table to write to, and `mutation_enabled` is
derived and false unless an explicit approval record exists — which it does not.
"""

from __future__ import annotations

import json
import re
from typing import Any

from nativeforge.services.customer_data_classification_service import (
    ADDITIONAL_ACTIVATION_REQUIRED,
    CUSTOMER_DATA_CLASSES,
    DATA_CLASSES,
    NEVER_STORED_CLASSES,
    NOT_CONSENT,
    PRE_CONSENT_CLASSES,
    UNKNOWN,
)

SCHEMA_VERSION = "nf_customer_beta_consent_boundary_v1"

DEMO_ORGANIZATION_ID = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
REAL_ORGANIZATION_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

#: What an organization is, for this boundary.
ORG_DEMO = "demo"
ORG_FIXTURE = "fixture"
ORG_REAL_CUSTOMER = "real_customer"
ORG_REFUSED_REAL = "refused_real"
ORG_UNKNOWN = "unknown"

#: The fields a consent record must carry. None exists; the shape is declared
#: so its absence is a missing record rather than an undefined concept.
CONSENT_RECORD_FIELDS: tuple[str, ...] = (
    "organization_id",
    "agreed_by",
    "agreed_at",
    "what_is_collected",
    "what_is_retained",
    "retention_period",
    "what_is_exported",
    "how_it_is_deleted",
    "withdrawal_method",
    "document_version",
)

#: The fields a beta scope approval must carry.
BETA_SCOPE_APPROVAL_FIELDS: tuple[str, ...] = (
    "organization_id",
    "approved_by",
    "approved_at",
    "scope",
    "data_classes_permitted",
    "expires_at",
)

CONSENT_ABSENT = "consent_boundary_not_documented"
SCOPE_ABSENT = "customer_beta_scope_not_approved"
NO_REAL_CUSTOMER_ORG = "real_customer_organization_missing"
AUTH_NOT_LIVE = "customer_auth_live_false"
BINDING_ABSENT = "verified_operational_binding_false"
CLASS_UNKNOWN = "data_class_unknown"
CLASS_NEVER_STORED = "data_class_is_never_stored"
ACTIVATION_ABSENT = "required_capability_not_activated"
DEMO_ORG_NOT_A_CUSTOMER = "demo_organization_is_not_a_customer_organization"
REAL_ORG_REFUSED = "organization_is_the_explicitly_refused_real_org"
INFERRED_CONSENT_REFUSED = "consent_was_inferred_rather_than_recorded"

#: Each blocker, what kind of thing clears it, and who owns it.
BLOCKER_OWNERS: dict[str, dict[str, str]] = {
    CONSENT_ABSENT: {
        "kind": "a_document_then_a_record",
        "owner": "Mayhem, then each tenant",
        "clears_by": (
            "deciding what NativeForge collects, retains, exports and deletes, "
            "writing it down, and recording that a tenant agreed to it"
        ),
    },
    SCOPE_ABSENT: {
        "kind": "recorded_decision",
        "owner": "Mayhem",
        "clears_by": "approving the controlled customer beta scope",
    },
    NO_REAL_CUSTOMER_ORG: {
        "kind": "a_customer",
        "owner": "nobody in this repository",
        "clears_by": (
            "a real customer organization existing. There is none in this "
            "deployment other than the refused one - Gate 147's finding"
        ),
    },
    AUTH_NOT_LIVE: {
        "kind": "an_event",
        "owner": "the second person, then the operator",
        "clears_by": "the second-person invite event; see Gate 146",
    },
    BINDING_ABSENT: {
        "kind": "five_refusals",
        "owner": "Mayhem, and only after a real customer organization exists",
        "clears_by": "the verified binding approval boundary; see Gate 147",
    },
    CLASS_UNKNOWN: {
        "kind": "classification",
        "owner": "whoever adds the data",
        "clears_by": (
            "classifying it. An unclassified class is refused rather than "
            "inheriting permission from a neighbour."
        ),
    },
    CLASS_NEVER_STORED: {
        "kind": "never_clears",
        "owner": "nobody",
        "clears_by": (
            "nothing. A provider subject, token, cookie, state, PKCE verifier "
            "or secret is not a data class anybody can be asked to agree to."
        ),
    },
    ACTIVATION_ABSENT: {
        "kind": "capability_activation",
        "owner": "Mayhem",
        "clears_by": (
            "activating the capability the class needs - object storage for "
            "document bodies, email delivery for recipients. Consent does not "
            "substitute for it, and it does not substitute for consent."
        ),
    },
    DEMO_ORG_NOT_A_CUSTOMER: {
        "kind": "never_clears",
        "owner": "nobody",
        "clears_by": (
            "nothing. Gate 145's fifth conflation: the demo organization is "
            "not a customer organization."
        ),
    },
    REAL_ORG_REFUSED: {
        "kind": "never_clears_without_a_reviewed_code_change",
        "owner": "Mayhem",
        "clears_by": "nothing available here",
    },
    INFERRED_CONSENT_REFUSED: {
        "kind": "never_clears",
        "owner": "nobody",
        "clears_by": (
            "nothing. A login, a membership, an invite and an operator's note "
            "are not consent, and offering one as consent is refused by name."
        ),
    },
}

#: Keys a caller might offer as consent. Refused by name rather than ignored,
#: so somebody learns their reasoning was rejected.
INFERRED_CONSENT_KEYS: tuple[str, ...] = (
    "login",
    "logged_in",
    "membership",
    "is_member",
    "invite",
    "invite_accepted",
    "operator_note",
    "verbal_consent",
    "verbally_agreed",
    "implied_consent",
    "assumed_consent",
)

#: Claims this module never makes.
NOT_APPROVED: tuple[str, ...] = (
    "controlled_customer_pilot",
    "production_rollout",
    "customer_auth_live",
    "verified_operational_binding",
    "email_delivery",
    "object_store_configured",
    "source_monitoring_live",
)

_FORBIDDEN_SHAPES: tuple[tuple[str, str], ...] = (
    ("email_address", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    ("bearer_token", r"\beyJ[A-Za-z0-9_-]{8,}"),
    ("session_cookie", r"nf_session="),
    ("set_cookie", r"(?i)set-cookie:"),
    ("google_client_secret", r"GOCSPX-"),
    ("private_key", r"BEGIN PRIVATE KEY"),
    ("aws_key", r"AKIA"),
)
_PROVIDER_SUBJECT_SHAPE = re.compile(r"\b\d{18,}\b")


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _leaked_shapes(payload: dict[str, Any]) -> list[str]:
    body = json.dumps(payload, default=str, sort_keys=True)
    found = [name for name, pattern in _FORBIDDEN_SHAPES if re.search(pattern, body)]
    if _PROVIDER_SUBJECT_SHAPE.search(body):
        found.append("provider_subject")
    return sorted(set(found))


def _record_shape_failures(
    record: Any, required: tuple[str, ...], label: str
) -> list[str]:
    if not isinstance(record, dict):
        return [f"{label}_is_not_a_record"]
    return sorted(
        f"{label}_missing_field:{field}"
        for field in required
        if not str(record.get(field) or "").strip()
    )


def classify_organization(
    *,
    organization_id: Any = None,
    org_type_in_database: str | None = None,
) -> dict[str, Any]:
    """Demo, fixture, real customer, refused-real or unknown. From the database."""
    normalized = str(organization_id or "").strip().lower()
    declared = str(org_type_in_database or "").strip().lower() or None

    if normalized == DEMO_ORGANIZATION_ID:
        kind, source = ORG_DEMO, "module_constant"
    elif normalized == REAL_ORGANIZATION_ID:
        kind, source = ORG_REFUSED_REAL, "module_constant"
    elif declared == "demo":
        kind, source = ORG_FIXTURE, "database"
    elif declared == "real":
        kind, source = ORG_REAL_CUSTOMER, "database"
    else:
        kind, source = ORG_UNKNOWN, "unavailable"

    return {
        "organization_id": normalized or None,
        "organization_kind": kind,
        "organization_kind_source": source,
    }


def build_consent_boundary(
    *,
    organization_id: Any = None,
    org_type_in_database: str | None = None,
    data_class: str | None = None,
    consent_record: dict[str, Any] | None = None,
    beta_scope_approval: dict[str, Any] | None = None,
    customer_auth_live: bool | None = None,
    verified_operational_binding: bool | None = None,
    object_store_configured: bool | None = None,
    email_delivery: bool | None = None,
    source_monitoring_live: bool | None = None,
    **offered: Any,
) -> dict[str, Any]:
    """May customer data of this class be written for this organization?

    `consent_boundary_documented`, `customer_beta_scope_approved` and
    `write_permitted` are **not** parameters. All three are derived, so a caller
    cannot assert the thing this module exists to measure — the structural rule
    Gates 145, 146 and 147 applied to their own headline flags.
    """
    org = classify_organization(
        organization_id=organization_id, org_type_in_database=org_type_in_database
    )
    requested_class = str(data_class or "").strip().lower() or UNKNOWN
    if requested_class not in DATA_CLASSES:
        requested_class = UNKNOWN

    # Anything offered as consent that is not a consent record is refused by
    # name. An omission here would be read as permission.
    inferred = sorted(key for key in offered if key in INFERRED_CONSENT_KEYS)

    consent_failures = (
        _record_shape_failures(consent_record, CONSENT_RECORD_FIELDS, "consent")
        if consent_record is not None
        else ["consent_record_absent"]
    )
    scope_failures = (
        _record_shape_failures(
            beta_scope_approval, BETA_SCOPE_APPROVAL_FIELDS, "beta_scope"
        )
        if beta_scope_approval is not None
        else ["beta_scope_approval_absent"]
    )

    consent_boundary_documented = not consent_failures
    customer_beta_scope_approved = not scope_failures

    is_customer_data = requested_class in CUSTOMER_DATA_CLASSES
    is_pre_consent_safe = requested_class in PRE_CONSENT_CLASSES

    capabilities = {
        "object_store_configured": bool(object_store_configured),
        "email_delivery": bool(email_delivery),
        "source_monitoring_live": bool(source_monitoring_live),
    }
    required_activation = ADDITIONAL_ACTIVATION_REQUIRED.get(requested_class)

    blockers: list[str] = []

    if inferred:
        blockers.append(INFERRED_CONSENT_REFUSED)

    if requested_class == UNKNOWN:
        blockers.append(CLASS_UNKNOWN)
    if requested_class in NEVER_STORED_CLASSES:
        blockers.append(CLASS_NEVER_STORED)

    if is_customer_data:
        if not consent_boundary_documented:
            blockers.append(CONSENT_ABSENT)
        if not customer_beta_scope_approved:
            blockers.append(SCOPE_ABSENT)
        if not customer_auth_live:
            blockers.append(AUTH_NOT_LIVE)
        if not verified_operational_binding:
            blockers.append(BINDING_ABSENT)
        if org["organization_kind"] == ORG_DEMO:
            blockers.append(DEMO_ORG_NOT_A_CUSTOMER)
        if org["organization_kind"] == ORG_REFUSED_REAL:
            blockers.append(REAL_ORG_REFUSED)
        if org["organization_kind"] in {ORG_UNKNOWN, ORG_FIXTURE, ORG_DEMO}:
            blockers.append(NO_REAL_CUSTOMER_ORG)
        if required_activation and not capabilities.get(required_activation):
            blockers.append(ACTIVATION_ABSENT)

    blockers = sorted(set(blockers))

    # Derived, never supplied.
    write_permitted = bool(not blockers and (is_pre_consent_safe or is_customer_data))
    mutation_enabled = bool(
        write_permitted and is_customer_data and consent_boundary_documented
    )

    next_action: dict[str, Any] | None = None
    for name in (
        CLASS_NEVER_STORED,
        CLASS_UNKNOWN,
        INFERRED_CONSENT_REFUSED,
        NO_REAL_CUSTOMER_ORG,
        DEMO_ORG_NOT_A_CUSTOMER,
        REAL_ORG_REFUSED,
        CONSENT_ABSENT,
        SCOPE_ABSENT,
        AUTH_NOT_LIVE,
        BINDING_ABSENT,
        ACTIVATION_ABSENT,
    ):
        if name in blockers:
            next_action = {"blocker": name, **BLOCKER_OWNERS[name]}
            break

    payload = _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            **org,
            "data_class": requested_class,
            "is_customer_data": is_customer_data,
            "is_pre_consent_safe": is_pre_consent_safe,
            # The two headline facts, derived.
            "consent_boundary_documented": consent_boundary_documented,
            "customer_beta_scope_approved": customer_beta_scope_approved,
            "write_permitted": write_permitted,
            "mutation_enabled": mutation_enabled,
            "mutation_performed": False,
            "rows_written": 0,
            # Evidence, so a reader can check a claim rather than take one.
            "consent_record_supplied": consent_record is not None,
            "consent_shape_failures": consent_failures,
            "consent_record_fields_required": list(CONSENT_RECORD_FIELDS),
            "beta_scope_approval_supplied": beta_scope_approval is not None,
            "beta_scope_shape_failures": scope_failures,
            "beta_scope_fields_required": list(BETA_SCOPE_APPROVAL_FIELDS),
            "customer_auth_live": bool(customer_auth_live),
            "verified_operational_binding": bool(verified_operational_binding),
            "capabilities": capabilities,
            "required_activation": required_activation,
            "inferred_consent_keys_refused": inferred,
            "not_consent": [dict(entry) for entry in NOT_CONSENT],
            "blockers": blockers,
            "blocker_owners": {name: BLOCKER_OWNERS[name] for name in blockers},
            "next_human_action": next_action,
            "not_approved": list(NOT_APPROVED),
            # Constants. This module records nothing and activates nothing.
            "consent_recorded_by_this_module": False,
            "beta_approved_by_this_module": False,
            "controlled_customer_pilot": False,
            "production_rollout": False,
            "real_organization_touched": False,
            "leaked_shapes": [],
        }
    )
    payload["leaked_shapes"] = _leaked_shapes(payload)
    return payload


def consent_boundary_invariant_failures(decision: dict[str, Any]) -> list[str]:
    """Refuse a decision that claims more than its evidence supports."""
    fails: list[str] = []

    if decision.get("write_permitted") and decision.get("blockers"):
        fails.append("write_permitted_alongside_blockers")

    if decision.get("is_customer_data") and decision.get("write_permitted"):
        if not decision.get("consent_boundary_documented"):
            fails.append("customer_data_write_without_consent")
        if not decision.get("customer_beta_scope_approved"):
            fails.append("customer_data_write_without_beta_scope")
        if not decision.get("customer_auth_live"):
            fails.append("customer_data_write_without_live_customer_auth")
        if not decision.get("verified_operational_binding"):
            fails.append("customer_data_write_without_a_verified_binding")

    if decision.get("data_class") == UNKNOWN and decision.get("write_permitted"):
        fails.append("unknown_data_class_permitted")

    if decision.get("data_class") in NEVER_STORED_CLASSES and decision.get(
        "write_permitted"
    ):
        fails.append("never_stored_class_permitted")

    if decision.get("inferred_consent_keys_refused") and decision.get(
        "consent_boundary_documented"
    ):
        fails.append("consent_documented_from_an_inferred_key")

    if decision.get("mutation_enabled") and not decision.get("write_permitted"):
        fails.append("mutation_enabled_without_a_permitted_write")

    for flag in (
        "mutation_performed",
        "consent_recorded_by_this_module",
        "beta_approved_by_this_module",
        "controlled_customer_pilot",
        "production_rollout",
        "real_organization_touched",
    ):
        if decision.get(flag):
            fails.append(f"module_claimed_to_have:{flag}")

    if decision.get("rows_written"):
        fails.append("consent_boundary_wrote_rows")

    for name in decision.get("leaked_shapes") or []:
        fails.append(f"leaked:{name}")

    return sorted(set(fails))
