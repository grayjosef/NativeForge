"""Gate 153B: which tables may be exported, and why each one may or may not.

## Classified by meaning, with a declared reason per table

Not by scanning column names. A first pass at this did scan names, against a
list including `state`, and flagged two tables that hold a row lifecycle state:

```text
nf_org_memberships.state            VARCHAR(32), value 'active'
nf_authority_proof_records.state    VARCHAR(32), Gate 52 lifecycle
```

Excluding membership rows because a column is called `state` would be the
substring-versus-meaning mistake this campaign keeps finding, committed by the
tool built to prevent an information leak. So every entry below carries an
explicit reason a person wrote, and the name-matcher survives only as
`review_hint_columns` - a prompt to look, never a gate.

## What is excluded, and why each one really is unsafe

```text
nf_identities              a real address and a provider subject
nf_auth_redirect_states    an oauth state hash and a PKCE verifier
nf_auth_validation_events  auth-flow evidence, and no org partition
organizations              includes the real organization; a restore
                           precondition, not a payload
alembic_version            schema state; recorded as metadata instead
```

## Field-level exclusions, on tables that are otherwise included

A table can be safe to export while one of its columns is not. Those are named
per table rather than globally, because a global list is how `state` became a
problem.

## No writes, no external calls, no database

`build_backup_manifest` is a pure function of the constants below. It does not
inspect a live schema: a manifest that changed with the database could not be
reviewed, and the point of a manifest is that somebody reads it once and the
export obeys it.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_operational_backup_manifest_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

#: The migration head this manifest was written against. A restore compares.
MANIFEST_MIGRATION_HEAD = "0055"

#: Columns worth a second look on any table. A REVIEW HINT, never a gate:
#: `state` matches both an OAuth state and a row lifecycle state, and only a
#: person can say which a given column is.
REVIEW_HINT_COLUMNS: tuple[str, ...] = (
    "email",
    "subject",
    "recipient",
    "address",
    "token",
    "cookie",
    "state",
    "verifier",
    "secret",
    "body",
    "content",
    "bytes",
)

#: Values that must never appear in an export, whatever column carries them.
#: Checked against the exported payload rather than against column names.
FORBIDDEN_VALUE_KINDS: tuple[str, ...] = (
    "email_address",
    "provider_subject",
    "bearer_token",
    "session_cookie",
    "oauth_state",
    "pkce_verifier",
    "client_secret",
    "document_body",
    "object_bytes",
)


def _table(
    name: str,
    *,
    gate: str,
    why: str,
    primary_key: tuple[str, ...] = ("id",),
    org_partition: str = "organization_id",
    demo_marker: str | None = "is_demo",
    hash_fields: tuple[str, ...] = (),
    archive_field: str | None = None,
    excluded_fields: tuple[str, ...] = (),
    link_fields: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "table": name,
        "included": True,
        "gate": gate,
        "why_included": why,
        "primary_key": list(primary_key),
        "org_partition": org_partition,
        "demo_marker": demo_marker,
        "hash_fields": list(hash_fields),
        "archive_field": archive_field,
        "excluded_fields": list(excluded_fields),
        "link_fields": list(link_fields),
    }


#: The operational state a restore must preserve for the Gate 152 replay to
#: still work. Eleven tables, every one org-partitioned.
INCLUDED_TABLES: tuple[dict[str, Any], ...] = (
    _table(
        "nf_tenant_digest_records",
        gate="151",
        why="the digest a delivery intent names, and the hash that proves it",
        hash_fields=("payload_sha256",),
        archive_field="archived_at",
        link_fields=("digest_id",),
    ),
    _table(
        "nf_digest_delivery_intents",
        gate="142",
        why="the intent, its counts, and the two links a replay follows",
        archive_field="cancelled_at",
        link_fields=("digest_id", "audit_event_id"),
        # The table has no address column at all. `recipient_fingerprint` and
        # `recipient_domain` are the derived halves and are safe to export;
        # they are named here so a reader can see the distinction was made
        # rather than missed.
        excluded_fields=(),
    ),
    _table(
        "nf_audit_events",
        gate="65",
        why="the third link in the replay chain; an action, not a payload",
        link_fields=("id",),
    ),
    _table(
        "nf_source_watchlist_entries",
        gate="140",
        why="what a tenant asked to watch; no source is contacted by a restore",
    ),
    _table(
        "nf_tenant_pursuit_suppressions",
        gate="140",
        why="a suppression and its audit trail",
    ),
    _table(
        "nf_awarded_grants",
        gate="139",
        why="the award a compliance record hangs from",
    ),
    _table(
        "nf_award_requirements",
        gate="125",
        why="what an award obliges",
    ),
    _table(
        "nf_award_requirement_proof_events",
        gate="126",
        why="what was filed against a requirement",
    ),
    _table(
        "nf_award_documents",
        gate="127",
        why=(
            "document METADATA. The table has no body column - Gate 141 kept "
            "bytes out of the database entirely - so there is nothing here to "
            "exclude."
        ),
    ),
    _table(
        "nf_tenant_beta_profiles",
        gate="123",
        why="how a tenant asked NativeForge to behave",
    ),
    _table(
        "nf_tenant_customer_org_bindings",
        gate="113",
        why="which organization a binding names, and its state",
        archive_field="revoked_at",
    ),
)


def _excluded(name: str, *, reason: str, detail: str) -> dict[str, Any]:
    return {
        "table": name,
        "included": False,
        "exclusion_reason": reason,
        "detail": detail,
    }


#: Named individually, each with the actual reason. Not "it matched a word".
EXCLUDED_TABLES: tuple[dict[str, Any], ...] = (
    _excluded(
        "nf_identities",
        reason="carries_the_two_values_this_campaign_protects",
        detail=(
            "email is a real address and subject is the provider subject. "
            "Fifteen gates have kept both out of logs, artifacts and terminals; "
            "a backup is not the place to put them back."
        ),
    ),
    _excluded(
        "nf_auth_redirect_states",
        reason="oauth_state_and_pkce_verifier",
        detail=(
            "state_hash, pkce_verifier_hash, pkce_verifier_encrypted and "
            "code_challenge. No organization_id either, so it is unscopeable "
            "as well as unsafe."
        ),
    ),
    _excluded(
        "nf_auth_validation_events",
        reason="auth_flow_evidence_without_an_org_partition",
        detail="no organization_id, so an export could not be scoped",
    ),
    _excluded(
        "organizations",
        reason="a_restore_precondition_not_a_payload",
        detail=(
            "includes the real organization. A restore target must already "
            "have the organization row; recreating it from a backup would be "
            "how the real org arrives somewhere it was never authorized."
        ),
    ),
    _excluded(
        "alembic_version",
        reason="schema_state_not_data",
        detail="recorded as export metadata and compared on restore",
    ),
    _excluded(
        "nf_org_memberships",
        reason="membership_is_identity_adjacent",
        detail=(
            "NOT because a column is called `state` - that column holds "
            "'active', a row lifecycle state. It is excluded because a "
            "membership joins an identity to an organization, and identities "
            "are excluded, so restoring memberships would produce rows "
            "pointing at people the backup does not contain."
        ),
    ),
    _excluded(
        "nf_raw_source_payloads",
        reason="source_response_evidence",
        detail="no organization_id; and a restore must contact no source",
    ),
    _excluded(
        "nf_evidence_intake_records",
        reason="no_org_partition",
        detail="no organization_id, so an export could not be scoped",
    ),
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def build_backup_manifest() -> dict[str, Any]:
    """The manifest. Deterministic, and reads no schema."""
    included = [dict(entry) for entry in INCLUDED_TABLES]
    excluded = [dict(entry) for entry in EXCLUDED_TABLES]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "migration_head": MANIFEST_MIGRATION_HEAD,
            "included_tables": included,
            "included_count": len(included),
            "excluded_tables": excluded,
            "excluded_count": len(excluded),
            "table_names": sorted(entry["table"] for entry in included),
            "forbidden_value_kinds": list(FORBIDDEN_VALUE_KINDS),
            "review_hint_columns": list(REVIEW_HINT_COLUMNS),
            "review_hints_are_not_a_gate": (
                "`state` matches both an OAuth state and a row lifecycle "
                "state. A name-matching scan flagged nf_org_memberships and "
                "nf_authority_proof_records on exactly that, and both hold "
                "lifecycle values. Every inclusion and exclusion here is a "
                "reason a person wrote."
            ),
            "classified_by": "meaning, per table",
            "reads_a_live_schema": False,
            "why_not": (
                "a manifest that changed with the database could not be "
                "reviewed; the point of a manifest is that somebody reads it "
                "once and the export obeys it"
            ),
            "production_backup_ready": False,
            "production_backup_is_a_different_harness": (
                "scripts/verify_nativeforge_backup_restore.sh, which needs a "
                "managed instance and returns SKIP until one exists"
            ),
        }
    )


def manifest_invariant_failures(manifest: dict[str, Any]) -> list[str]:
    """Refuse a manifest that lost a reason or included something unsafe."""
    fails: list[str] = []

    included = manifest.get("included_tables") or []
    excluded = manifest.get("excluded_tables") or []

    if manifest.get("included_count") != len(included):
        fails.append("included_count_disagrees")
    if manifest.get("excluded_count") != len(excluded):
        fails.append("excluded_count_disagrees")

    names = [entry.get("table") for entry in included]
    if len(names) != len(set(names)):
        fails.append("a_table_is_included_twice")

    overlap = {entry.get("table") for entry in included} & {
        entry.get("table") for entry in excluded
    }
    if overlap:
        fails.append(f"table_both_included_and_excluded:{sorted(overlap)}")

    for entry in included:
        if not entry.get("why_included"):
            fails.append(f"included_without_a_reason:{entry.get('table')}")
        if not entry.get("org_partition"):
            fails.append(f"included_without_an_org_partition:{entry.get('table')}")
        if not entry.get("primary_key"):
            fails.append(f"included_without_a_primary_key:{entry.get('table')}")

    for entry in excluded:
        if not entry.get("exclusion_reason"):
            fails.append(f"excluded_without_a_reason:{entry.get('table')}")
        if not entry.get("detail"):
            fails.append(f"excluded_without_a_detail:{entry.get('table')}")

    # The three that must never be exported, whatever else changes.
    must_exclude = {
        "nf_identities",
        "nf_auth_redirect_states",
        "organizations",
    }
    missing = must_exclude - {entry.get("table") for entry in excluded}
    if missing:
        fails.append(f"must_be_excluded_and_is_not:{sorted(missing)}")
    wrongly_included = must_exclude & {entry.get("table") for entry in included}
    if wrongly_included:
        fails.append(f"unsafe_table_included:{sorted(wrongly_included)}")

    if manifest.get("production_backup_ready"):
        fails.append("manifest_claimed_production_backup_readiness")

    return sorted(set(fails))
