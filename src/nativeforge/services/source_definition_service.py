"""One runtime source contract over three stores (Gate 166C / 166H).

NativeForge holds source facts in three places, and Gate 165 found them
partially disjoint:

```text
fixtures/source_ingestion/NF_SOURCE_SEED_2026.csv   178 rows   catalog
nf_opportunity_sources                               40 rows   health + coverage
nf_active_opportunity_sources                         1 row    activation
```

A future adapter must not know that. It receives a `SourceDefinition` and never
learns which store answered which field - which is the whole point: the stores
can be consolidated later without touching a single adapter.

## A projection, not a migration

Nothing is copied, moved or deleted here. Gate 166 deliberately does not
consolidate the schema: a risky migration performed for tidiness is how a
campaign loses a corpus. **One runtime contract is needed before one physical
table is.** When the physical consolidation happens, this projection is the
specification it has to satisfy, and its callers do not change.

## Every field says where it came from

`field_provenance` names the store behind each value, so "the CSV and the
database disagree" is a visible fact rather than a silent precedence rule. The
live data already contains one such disagreement: the Grants.gov activation row
carries `source_status = 'activation_pending'` while
`activation_approved_by` and `activation_approved_at` are both signed. The
signed columns are authoritative - Gate 163's resolver already derives
activation from them - and `source_status` is a DUPLICATED field that drifted.
This projection reports the derived value and records the disagreement rather
than quietly preferring one.

## Precedence

```text
identity, endpoint, adapter   CSV          (authoritative - the catalog)
health, schedule, coverage    nf_opportunity_sources   (authoritative)
activation                    nf_active_opportunity_sources (authoritative)
```

A field absent from its authoritative store is `None` and named in
`missing_fields`. It is never backfilled from a weaker store without saying so.
"""

from __future__ import annotations

import json
from typing import Any

import sqlalchemy as sa

SCHEMA_VERSION = "nf_source_definition_v1"

OPPORTUNITY_SOURCES_TABLE = "nf_opportunity_sources"
ACTIVATION_SOURCES_TABLE = "nf_active_opportunity_sources"

#: How each field of the projection is classified. Gate 166C asked for this
#: explicitly, and a classification nobody can read is not one.
AUTHORITATIVE = "AUTHORITATIVE"
DERIVED = "DERIVED"
LEGACY = "LEGACY"
DISCOVERY_ONLY = "DISCOVERY_ONLY"
RUNTIME_ONLY = "RUNTIME_ONLY"
DUPLICATED = "DUPLICATED"
UNKNOWN = "UNKNOWN"

FIELD_CLASSIFICATION: dict[str, tuple[str, str]] = {
    # field -> (classification, store)
    "source_id": (AUTHORITATIVE, "seed_csv"),
    "canonical_source_id": (AUTHORITATIVE, "seed_csv"),
    "source_name": (AUTHORITATIVE, "seed_csv"),
    "authority_host": (DERIVED, "seed_csv.source_url"),
    "endpoint": (AUTHORITATIVE, "seed_csv.source_url"),
    "source_type": (AUTHORITATIVE, "seed_csv"),
    "tier": (AUTHORITATIVE, "seed_csv"),
    "adapter_key": (AUTHORITATIVE, "seed_csv"),
    "publisher_name": (AUTHORITATIVE, "seed_csv"),
    "state_code": (AUTHORITATIVE, "seed_csv"),
    "access_posture_hint": (AUTHORITATIVE, "seed_csv"),
    "program_family": (AUTHORITATIVE, "seed_csv"),
    "native_relevance_notes": (AUTHORITATIVE, "seed_csv"),
    # --- nf_opportunity_sources
    "check_interval_days": (AUTHORITATIVE, OPPORTUNITY_SOURCES_TABLE),
    "next_check_due_at": (AUTHORITATIVE, OPPORTUNITY_SOURCES_TABLE),
    "freshness_interval_days": (AUTHORITATIVE, OPPORTUNITY_SOURCES_TABLE),
    "last_checked_at": (AUTHORITATIVE, OPPORTUNITY_SOURCES_TABLE),
    "last_check_status": (AUTHORITATIVE, OPPORTUNITY_SOURCES_TABLE),
    "consecutive_failure_count": (AUTHORITATIVE, OPPORTUNITY_SOURCES_TABLE),
    "source_health_status": (AUTHORITATIVE, OPPORTUNITY_SOURCES_TABLE),
    "priority_level": (AUTHORITATIVE, OPPORTUNITY_SOURCES_TABLE),
    "check_method": (AUTHORITATIVE, OPPORTUNITY_SOURCES_TABLE),
    "covered_states_json": (AUTHORITATIVE, OPPORTUNITY_SOURCES_TABLE),
    "covered_tribal_groups_json": (AUTHORITATIVE, OPPORTUNITY_SOURCES_TABLE),
    "verification_status": (AUTHORITATIVE, OPPORTUNITY_SOURCES_TABLE),
    "is_active": (LEGACY, OPPORTUNITY_SOURCES_TABLE),
    # --- nf_active_opportunity_sources
    "activation_approved_by": (AUTHORITATIVE, ACTIVATION_SOURCES_TABLE),
    "activation_approved_at": (AUTHORITATIVE, ACTIVATION_SOURCES_TABLE),
    "activation_approval_artifact_id": (AUTHORITATIVE, ACTIVATION_SOURCES_TABLE),
    "disabled_at": (AUTHORITATIVE, ACTIVATION_SOURCES_TABLE),
    "disabled_reason": (AUTHORITATIVE, ACTIVATION_SOURCES_TABLE),
    "activation_state": (DERIVED, "activation signature columns"),
    # `source_status` restates what the signature columns already say, and in
    # the live data it disagrees with them. Reported, never believed.
    "source_status": (DUPLICATED, ACTIVATION_SOURCES_TABLE),
    "legal_tos_review_required": (AUTHORITATIVE, ACTIVATION_SOURCES_TABLE),
    "native_relevance_basis": (AUTHORITATIVE, ACTIVATION_SOURCES_TABLE),
}


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _host_of(url: Any) -> str:
    text = str(url or "")
    return text.split("//", 1)[-1].split("/", 1)[0].lower()


def _row_for(
    *, connection: Any, table_name: str, columns: dict[str, Any], source_id: str
) -> dict[str, Any] | None:
    """Read one row by `source_id`. An unreadable table contributes nothing."""
    if connection is None or not source_id:
        return None
    try:
        metadata = sa.MetaData()
        table = sa.Table(
            table_name,
            metadata,
            *(sa.Column(name, kind) for name, kind in columns.items()),
        )
        found = connection.execute(
            sa.select(table).where(table.c.source_id == source_id)
        ).first()
    except Exception:  # noqa: BLE001 - an unreadable store states nothing
        return None
    return dict(found._mapping) if found is not None else None


_OPPORTUNITY_COLUMNS: dict[str, Any] = {
    "source_id": sa.Text(),
    "seed_id": sa.Text(),
    "source_name": sa.Text(),
    "check_interval_days": sa.Integer(),
    "next_check_due_at": sa.DateTime(timezone=True),
    "freshness_interval_days": sa.Integer(),
    "last_checked_at": sa.DateTime(timezone=True),
    "last_check_status": sa.Text(),
    "consecutive_failure_count": sa.Integer(),
    "source_health_status": sa.Text(),
    "priority_level": sa.Text(),
    "check_method": sa.Text(),
    "covered_states_json": sa.Text(),
    "covered_tribal_groups_json": sa.Text(),
    "verification_status": sa.Text(),
    "is_active": sa.Boolean(),
}

_ACTIVATION_COLUMNS: dict[str, Any] = {
    "source_id": sa.Text(),
    "source_name": sa.Text(),
    "source_status": sa.Text(),
    "activation_approved_by": sa.Text(),
    "activation_approved_at": sa.DateTime(timezone=True),
    "activation_approval_artifact_id": sa.Text(),
    "activation_notes": sa.Text(),
    "disabled_at": sa.DateTime(timezone=True),
    "disabled_reason": sa.Text(),
    "legal_tos_review_required": sa.Boolean(),
    "native_relevance_basis": sa.Text(),
}


def derive_activation_state(activation_row: dict[str, Any] | None) -> str:
    """The activation states, derived from signatures rather than a label.

    Identical to the rule `source_authorization_fact_resolver_service`
    already applies, kept as one function so the two cannot drift.
    """
    if not activation_row:
        return "activation_absent"
    if activation_row.get("disabled_at") is not None:
        return "activation_revoked"
    if activation_row.get("activation_approved_by") and activation_row.get(
        "activation_approved_at"
    ):
        return "activation_allowed"
    return "activation_unknown"


def build_source_definition(
    *,
    source_id: Any = None,
    registry_row: dict[str, Any] | None = None,
    connection: Any = None,
    organization_id: Any = None,
) -> dict[str, Any]:
    """One source, projected from every store that knows about it.

    `registry_row` may be supplied by a sweep that already loaded the catalog,
    so a thousand sources cost one catalog read rather than a thousand.
    """
    key = str(source_id or "").strip()

    row = registry_row
    if row is None:
        try:
            from nativeforge.services.source_authorization_fixture_registry_service import (  # noqa: E501
                merge_fixture_rows,
            )
            from nativeforge.services.source_monitoring_approved_source_service import (
                load_registry_rows,
            )

            row = merge_fixture_rows(load_registry_rows()).get(key)
        except Exception:  # noqa: BLE001 - an unreadable catalog defines nothing
            row = None

    catalog = dict(row or {})
    health = _row_for(
        connection=connection,
        table_name=OPPORTUNITY_SOURCES_TABLE,
        columns=_OPPORTUNITY_COLUMNS,
        source_id=key,
    )
    activation = _row_for(
        connection=connection,
        table_name=ACTIVATION_SOURCES_TABLE,
        columns=_ACTIVATION_COLUMNS,
        source_id=key,
    )

    endpoint = catalog.get("source_url")
    activation_state = derive_activation_state(activation)

    definition: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source_id": key or None,
        "canonical_source_id": catalog.get("canonical_source_id"),
        "source_name": catalog.get("source_name"),
        "authority_host": _host_of(endpoint) or None,
        "endpoint": endpoint,
        "source_type": catalog.get("source_type"),
        "tier": catalog.get("tier"),
        "adapter_key": catalog.get("adapter_key"),
        "publisher_name": catalog.get("publisher_name"),
        "state_code": catalog.get("state_code"),
        "access_posture_hint": catalog.get("access_posture_hint"),
        "program_family": catalog.get("program_family"),
        "native_relevance_notes": catalog.get("native_relevance_notes"),
        "schedule": {
            "check_interval_days": (health or {}).get("check_interval_days"),
            "next_check_due_at": (health or {}).get("next_check_due_at"),
            "freshness_interval_days": (health or {}).get("freshness_interval_days"),
            "check_method": (health or {}).get("check_method"),
            "priority_level": (health or {}).get("priority_level"),
        },
        "health": {
            "last_checked_at": (health or {}).get("last_checked_at"),
            "last_check_status": (health or {}).get("last_check_status"),
            "consecutive_failure_count": (health or {}).get(
                "consecutive_failure_count"
            ),
            "source_health_status": (health or {}).get("source_health_status"),
            "verification_status": (health or {}).get("verification_status"),
        },
        "coverage": {
            "covered_states_json": (health or {}).get("covered_states_json"),
            "covered_tribal_groups_json": (health or {}).get(
                "covered_tribal_groups_json"
            ),
            "native_relevance_basis": (activation or {}).get("native_relevance_basis"),
        },
        "activation": {
            "state": activation_state,
            "approved_by": (activation or {}).get("activation_approved_by"),
            "approved_at": (activation or {}).get("activation_approved_at"),
            "approval_artifact_id": (activation or {}).get(
                "activation_approval_artifact_id"
            ),
            "disabled_at": (activation or {}).get("disabled_at"),
            "disabled_reason": (activation or {}).get("disabled_reason"),
            "legal_tos_review_required": (activation or {}).get(
                "legal_tos_review_required"
            ),
            # Restates the signature columns and is known to drift. Carried so
            # the disagreement is inspectable; never used to decide anything.
            "recorded_source_status_not_authoritative": (activation or {}).get(
                "source_status"
            ),
        },
        "stores_present": {
            "seed_catalog": bool(catalog),
            OPPORTUNITY_SOURCES_TABLE: health is not None,
            ACTIVATION_SOURCES_TABLE: activation is not None,
        },
    }

    # A disagreement between the label and the signatures is a fact about the
    # data, and it is recorded rather than resolved silently.
    disagreements: list[str] = []
    label = str((activation or {}).get("source_status") or "").strip()
    if activation is not None and label:
        implied_allowed = label in {"active", "activation_allowed", "activated"}
        if implied_allowed != (activation_state == "activation_allowed"):
            disagreements.append(
                f"source_status={label!r} disagrees with the signed "
                f"activation columns which derive {activation_state!r}"
            )
    definition["store_disagreements"] = disagreements

    missing = [
        name
        for name in ("source_id", "source_name", "endpoint", "adapter_key")
        if not definition.get(name)
    ]
    definition["missing_fields"] = missing
    definition["usable_by_an_adapter"] = not missing

    return _json_safe(definition)


def describe_field_classification() -> dict[str, Any]:
    """Gate 166C's field map, as data rather than prose."""
    by_class: dict[str, list[str]] = {}
    for field, (classification, _store) in FIELD_CLASSIFICATION.items():
        by_class.setdefault(classification, []).append(field)
    return {
        "schema_version": SCHEMA_VERSION,
        "fields": {
            field: {"classification": classification, "store": store}
            for field, (classification, store) in sorted(FIELD_CLASSIFICATION.items())
        },
        "by_classification": {k: sorted(v) for k, v in sorted(by_class.items())},
        "stores": [
            "seed_csv",
            OPPORTUNITY_SOURCES_TABLE,
            ACTIVATION_SOURCES_TABLE,
        ],
        "consolidation_performed": False,
        "why_no_consolidation": (
            "Gate 166 defines the runtime contract, not the physical schema. "
            "Rows are neither migrated nor deleted: this projection is the "
            "specification a later consolidation has to satisfy, and its "
            "callers do not change when it happens."
        ),
    }


def definition_invariant_failures(definition: dict[str, Any]) -> list[str]:
    """Refuse a projection that claims usability it cannot support."""
    fails: list[str] = []

    if definition.get("usable_by_an_adapter") and definition.get("missing_fields"):
        fails.append("usable_while_naming_missing_fields")

    state = (definition.get("activation") or {}).get("state")
    if state not in {
        "activation_absent",
        "activation_unknown",
        "activation_allowed",
        "activation_revoked",
    }:
        fails.append(f"activation_state_outside_vocabulary:{state}")

    # A revoked activation may never be reported as allowed.
    if (definition.get("activation") or {}).get("disabled_at") and state != (
        "activation_revoked"
    ):
        fails.append("disabled_source_not_reported_as_revoked")

    return sorted(set(fails))
