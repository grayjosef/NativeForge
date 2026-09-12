"""Gate 148B: what kind of data is this, and may it be written before consent?

## Nine classes, and `unknown` is blocked rather than permissive

```text
demo_fixture                      a fixture row, labelled as one
synthetic_test                    hermetic test data
operator_runtime_input            an operator typed it; it names no customer
customer_identifying_data         who a Tribe is
customer_operational_data         what a Tribe is doing
customer_document_body            bytes a Tribe supplied
customer_contact_or_recipient     how to reach a person
provider_identity_secret_or_subject  a subject, a token, a secret
unknown                           nobody has classified it
```

`unknown` is refused. A data class nobody has classified cannot silently inherit
permission from a neighbouring one, so adding a new kind of customer data is a
decision somebody makes rather than an omission that defaults open.

## Why classification is separate from the write guard

The guard answers "may this be written". This module answers "what is it", and
the two are different questions with different owners. A classification that
also decided permission would make every new data class a permission change, and
the campaign has spent a dozen gates separating measurement from decision.

## What is not consent

`demo_fixture` is never customer data, whatever else is true of the row. And
none of a login, a membership, an accepted invite or an operator's note is
consent — each is recorded here as a non-example with the reason, because all
four are about to become available and each one looks like agreement.

## No writes, no external calls

This module reads its arguments and returns a classification. It touches no
database, contacts nothing, and stores nothing.
"""

from __future__ import annotations

import json
import re
from typing import Any

SCHEMA_VERSION = "nf_customer_data_classification_v1"

DEMO_FIXTURE = "demo_fixture"
SYNTHETIC_TEST = "synthetic_test"
OPERATOR_RUNTIME_INPUT = "operator_runtime_input"
CUSTOMER_IDENTIFYING_DATA = "customer_identifying_data"
CUSTOMER_OPERATIONAL_DATA = "customer_operational_data"
CUSTOMER_DOCUMENT_BODY = "customer_document_body"
CUSTOMER_CONTACT_OR_RECIPIENT = "customer_contact_or_recipient"
PROVIDER_IDENTITY_SECRET_OR_SUBJECT = "provider_identity_secret_or_subject"
UNKNOWN = "unknown"

DATA_CLASSES: tuple[str, ...] = (
    DEMO_FIXTURE,
    SYNTHETIC_TEST,
    OPERATOR_RUNTIME_INPUT,
    CUSTOMER_IDENTIFYING_DATA,
    CUSTOMER_OPERATIONAL_DATA,
    CUSTOMER_DOCUMENT_BODY,
    CUSTOMER_CONTACT_OR_RECIPIENT,
    PROVIDER_IDENTITY_SECRET_OR_SUBJECT,
    UNKNOWN,
)

#: The classes that are customer data. Consent applies to exactly these.
CUSTOMER_DATA_CLASSES: frozenset[str] = frozenset(
    {
        CUSTOMER_IDENTIFYING_DATA,
        CUSTOMER_OPERATIONAL_DATA,
        CUSTOMER_DOCUMENT_BODY,
        CUSTOMER_CONTACT_OR_RECIPIENT,
    }
)

#: Never written anywhere, with or without consent. A secret is not a data
#: class somebody can be asked to agree to.
NEVER_STORED_CLASSES: frozenset[str] = frozenset(
    {PROVIDER_IDENTITY_SECRET_OR_SUBJECT}
)

#: Safe before consent, in the controlled demo scope.
PRE_CONSENT_CLASSES: frozenset[str] = frozenset(
    {DEMO_FIXTURE, SYNTHETIC_TEST, OPERATOR_RUNTIME_INPUT}
)

#: Classes needing a capability as well as consent, and which one.
ADDITIONAL_ACTIVATION_REQUIRED: dict[str, str] = {
    CUSTOMER_DOCUMENT_BODY: "object_store_configured",
    CUSTOMER_CONTACT_OR_RECIPIENT: "email_delivery",
}

#: Each class, what it means, and a worked example either way. The non-examples
#: matter more than the examples: they are where a misclassification happens.
CLASS_DEFINITIONS: dict[str, dict[str, Any]] = {
    DEMO_FIXTURE: {
        "means": "a fixture row, labelled as one and forced by the route",
        "is_customer_data": False,
        "examples": [
            "an awarded grant written by the post-award routes with "
            "fact_status=demo_fixture",
            "a watchlist entry in the demo organization",
        ],
        "not_examples": [
            "a row a Tribe supplied that somebody labelled demo_fixture - the "
            "label is forced by the route, not accepted from a caller"
        ],
    },
    SYNTHETIC_TEST: {
        "means": "data a hermetic test invented; it refers to nobody",
        "is_customer_data": False,
        "examples": ["a fixture organization id used in a test"],
        "not_examples": [
            "a real organization id used in a test, which is the real "
            "organization whatever the test calls it"
        ],
    },
    OPERATOR_RUNTIME_INPUT: {
        "means": "an operator typed it at a terminal and it names no customer",
        "is_customer_data": False,
        "examples": ["a cadence, a role, a period key, a source id"],
        "not_examples": [
            "an address an operator typed, which is contact data whoever typed "
            "it",
            "a Tribe name an operator typed, which is identifying data",
        ],
    },
    CUSTOMER_IDENTIFYING_DATA: {
        "means": "who a Tribe is",
        "is_customer_data": True,
        "examples": [
            "a Tribe name",
            "a real organization name, address or identifier",
            "a person's name at a Tribe",
        ],
        "not_examples": ["the demo organization id, which identifies a fixture"],
    },
    CUSTOMER_OPERATIONAL_DATA: {
        "means": "what a Tribe is doing",
        "is_customer_data": True,
        "examples": [
            "a real awarded grant, its amount, its deadlines",
            "a real pursuit, requirement, proof event or obligation",
            "a real eligibility determination",
        ],
        "not_examples": [
            "the same shapes carrying fact_status=demo_fixture",
            "a public grant notice, which the funder published",
        ],
    },
    CUSTOMER_DOCUMENT_BODY: {
        "means": "bytes a Tribe supplied",
        "is_customer_data": True,
        "examples": ["an uploaded award letter, report or budget"],
        "not_examples": [
            "document metadata with no body, which Gate 141 made operational "
            "on purpose and which is a different class"
        ],
    },
    CUSTOMER_CONTACT_OR_RECIPIENT: {
        "means": "how to reach a person",
        "is_customer_data": True,
        "examples": ["an address", "a phone number", "a delivery recipient"],
        "not_examples": [
            "a recipient fingerprint and domain half, which is what the "
            "delivery table stores instead and which cannot be reached"
        ],
    },
    PROVIDER_IDENTITY_SECRET_OR_SUBJECT: {
        "means": "a provider subject, token, cookie, state, PKCE or secret",
        "is_customer_data": True,
        "examples": ["an OIDC sub", "a session cookie", "a client secret"],
        "not_examples": [
            "a fingerprint derived from one, which is what every table stores"
        ],
    },
    UNKNOWN: {
        "means": "nobody has classified it",
        "is_customer_data": True,
        "examples": ["a new field on a new table nobody has decided about"],
        "not_examples": [],
    },
}

#: Things that are not consent, and the reason each one looks like it is. All
#: four become available as Gates 146-147 land, which is why they are named.
NOT_CONSENT: tuple[dict[str, str], ...] = (
    {
        "looks_like_consent": "a login",
        "actually_says": "a person authenticated",
        "why_not": "authenticating is not agreeing to anything",
    },
    {
        "looks_like_consent": "a membership",
        "actually_says": "somebody was added to an organization",
        "why_not": "an owner added them; the member did not decide",
    },
    {
        "looks_like_consent": "an accepted invite",
        "actually_says": "a person accepted a seat",
        "why_not": "the invite carries a role and an expiry and no terms",
    },
    {
        "looks_like_consent": "an operator note or a verbal yes",
        "actually_says": "somebody wrote something down, or said it",
        "why_not": (
            "it records what an operator believes, not what a Tribe agreed to, "
            "and a verbal yes is not in the system at all"
        ),
    },
)

#: Field-name tokens that indicate a class. Matched against the field name
#: split on underscores and other separators, NOT as substrings and NOT with
#: `\b`: in `recipient_email` there is no word boundary before `email`, because
#: `_` is a word character. The first version used `\b(email|...)\b` and
#: therefore matched nothing at all on every underscore-separated field name in
#: this codebase, which is all of them - a guard that silently never fired.
#:
#: Tokens also avoid the substring problem this campaign has hit repeatedly: a
#: token match is exact, so `subject` matches `provider_subject` and not
#: `subject_line`... which is why `subject_line` is listed as a safe token too.
_FIELD_HINTS: tuple[tuple[str, frozenset[str]], ...] = (
    (
        PROVIDER_IDENTITY_SECRET_OR_SUBJECT,
        frozenset(
            {"subject", "sub", "token", "cookie", "pkce", "secret", "verifier"}
        ),
    ),
    (
        CUSTOMER_CONTACT_OR_RECIPIENT,
        frozenset({"email", "address", "recipient", "phone", "contact", "mailto"}),
    ),
    (
        CUSTOMER_DOCUMENT_BODY,
        frozenset({"body", "bytes", "content", "file", "blob", "attachment"}),
    ),
    (
        CUSTOMER_IDENTIFYING_DATA,
        frozenset({"tribe", "tribal", "applicant", "person", "legal"}),
    ),
)

#: Tokens that make a sensitive-looking field safe, because they name the
#: derived half rather than the value.
_DERIVED_SAFE_TOKENS: frozenset[str] = frozenset(
    {"fingerprint", "digest", "hash", "domain", "omitted", "redacted", "count", "id"}
)

#: Field names whose tokens overlap a sensitive class but which are not it.
#: `subject_line` is a digest's subject, not a provider subject.
_SAFE_FIELD_NAMES: frozenset[str] = frozenset(
    {"subject_line", "content_type", "file_name", "body_present"}
)


def _tokens(field: str) -> frozenset[str]:
    return frozenset(part for part in re.split(r"[^a-z0-9]+", field) if part)

#: Field names that look sensitive but are the derived, safe half. Checked
#: before the hints above, because `recipient_fingerprint` is not a recipient
#: and `email_domain` is not an address - the distinction Gate 142 built the
#: delivery table around.
_DERIVED_SAFE = re.compile(
    r"\b\w*(fingerprint|digest|hash|domain|omitted|redacted|count|_id)\b"
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def classify(
    *,
    fact_status: str | None = None,
    is_demo: bool | None = None,
    field_name: str | None = None,
    declared_class: str | None = None,
) -> dict[str, Any]:
    """Classify one piece of data. Deny-by-default: anything unclear is unknown.

    `declared_class` is a caller's claim and is honoured only when it names a
    class this module knows. It cannot turn customer data into a fixture: a
    declared `demo_fixture` is only accepted alongside a `fact_status` or
    `is_demo` that agrees, because the label being forced rather than accepted
    is what makes the post-award routes safe.
    """
    status = str(fact_status or "").strip().lower() or None
    declared = str(declared_class or "").strip().lower() or None
    field = str(field_name or "").strip().lower() or None

    reasons: list[str] = []
    data_class = UNKNOWN

    # A fixture is a fixture only when the row itself says so.
    row_says_fixture = bool(status == DEMO_FIXTURE or is_demo)

    if declared == DEMO_FIXTURE and not row_says_fixture:
        reasons.append("declared_demo_fixture_without_the_row_agreeing")
        declared = None

    if declared in DATA_CLASSES and declared != UNKNOWN:
        data_class = declared
        reasons.append(f"declared:{declared}")
    elif row_says_fixture:
        data_class = DEMO_FIXTURE
        reasons.append("row_is_labelled_a_fixture")
    elif field:
        tokens = _tokens(field)
        if field in _SAFE_FIELD_NAMES:
            data_class = OPERATOR_RUNTIME_INPUT
            reasons.append("field_name_is_a_known_safe_name")
        elif tokens & _DERIVED_SAFE_TOKENS:
            # The derived half of a sensitive value. Not the value.
            data_class = OPERATOR_RUNTIME_INPUT
            reasons.append("field_name_is_a_derived_safe_form")
        else:
            for candidate, hint_tokens in _FIELD_HINTS:
                if tokens & hint_tokens:
                    data_class = candidate
                    reasons.append(f"field_name_matched:{candidate}")
                    break
            else:
                # Deny by default. An unrecognised field is unknown, which is
                # blocked - not quietly assumed to be operator input.
                reasons.append("field_name_matched_nothing")
    elif status == "tenant_supplied":
        data_class = CUSTOMER_OPERATIONAL_DATA
        reasons.append("fact_status_is_tenant_supplied")
    else:
        reasons.append("nothing_identified_a_class")

    definition = CLASS_DEFINITIONS[data_class]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "data_class": data_class,
            "is_customer_data": bool(definition["is_customer_data"]),
            "is_pre_consent_safe": data_class in PRE_CONSENT_CLASSES,
            "is_never_stored": data_class in NEVER_STORED_CLASSES,
            "requires_additional_activation": ADDITIONAL_ACTIVATION_REQUIRED.get(
                data_class
            ),
            "means": definition["means"],
            "reasons": reasons,
            # Constants. This module decides nothing about permission.
            "write_permitted_by_this_module": False,
            "consent_recorded_by_this_module": False,
        }
    )


def classification_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Refuse a classification that contradicts itself."""
    fails: list[str] = []

    data_class = result.get("data_class")
    if data_class not in DATA_CLASSES:
        fails.append(f"unknown_data_class_name:{data_class}")
        return fails

    expected = bool(CLASS_DEFINITIONS[data_class]["is_customer_data"])
    if bool(result.get("is_customer_data")) != expected:
        fails.append(f"is_customer_data_disagrees_with_the_class:{data_class}")

    if result.get("is_pre_consent_safe") and result.get("is_customer_data"):
        fails.append("customer_data_marked_pre_consent_safe")

    if data_class == UNKNOWN and result.get("is_pre_consent_safe"):
        fails.append("unknown_class_marked_pre_consent_safe")

    if result.get("write_permitted_by_this_module"):
        fails.append("classification_module_permitted_a_write")
    if result.get("consent_recorded_by_this_module"):
        fails.append("classification_module_recorded_consent")

    return sorted(set(fails))


def build_data_class_catalogue() -> dict[str, Any]:
    """Every class, its meaning, and both kinds of example. Deterministic."""
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "data_classes": list(DATA_CLASSES),
            "customer_data_classes": sorted(CUSTOMER_DATA_CLASSES),
            "pre_consent_classes": sorted(PRE_CONSENT_CLASSES),
            "never_stored_classes": sorted(NEVER_STORED_CLASSES),
            "additional_activation_required": dict(ADDITIONAL_ACTIVATION_REQUIRED),
            "definitions": {
                name: dict(definition)
                for name, definition in CLASS_DEFINITIONS.items()
            },
            "not_consent": [dict(entry) for entry in NOT_CONSENT],
            "unknown_is_blocked": True,
            "why_unknown_is_blocked": (
                "a data class nobody has classified cannot silently inherit "
                "permission from a neighbouring one; adding a new kind of "
                "customer data is a decision somebody makes rather than an "
                "omission that defaults open"
            ),
        }
    )
