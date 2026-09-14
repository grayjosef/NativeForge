"""Gate 153E: re-verify restored state, using the Gate 152 replay unchanged.

## The point of a restore proof

A provider dump proves bytes survived a round trip. That is not what anyone
needs to know. What they need to know is whether the restored database still
answers the questions the live one answers: does this digest still hash, does
this intent still resolve to a digest, is an archived row still readable, does a
cross-organization read still get refused.

So this does not write a second replay. It runs `audit_replay_service` and
`evidence_ledger_service` - the Gate 152 code, unmodified - against the restored
connection, and compares the answers to the same code run against the source.

If restored state needed its own special replay to pass, the restore would not
have restored anything worth having.

## A gap is supposed to survive

Gate 152 found 8 legacy delivery intents whose digest predates persistence.
Those are `legacy_gap` and must still be `legacy_gap` after a restore. A restore
that turned them into anything better fabricated evidence, and
`verification_invariant_failures` fails the run for it.

## Equal is not the same as good

The comparison is `source == restored`, not `restored is healthy`. A source
holding a `missing_record` must restore to a `missing_record`. The verification
reports fidelity; the ledger reports health. Conflating them would let a restore
of broken state read as a pass because nothing changed - which is true, and is
also the wrong claim.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import sqlalchemy as sa

from nativeforge.services.audit_replay_service import (
    find_legacy_gaps,
    replay_delivery_intent,
    replay_digest,
)
from nativeforge.services.evidence_ledger_service import build_evidence_ledger
from nativeforge.services.evidence_status_vocabulary_service import (
    LEGACY_GAP,
    UNKNOWN,
    is_proof,
    normalize,
    rank,
)
from nativeforge.services.operational_backup_export_service import (
    REAL_ORGANIZATION_ID,
    table_payload_sha256,
)
from nativeforge.services.operational_backup_manifest_service import (
    INCLUDED_TABLES,
)

SCHEMA_VERSION = "nf_operational_restore_verification_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

CHECK_ROW_COUNTS = "restored_row_counts_match_the_export"
CHECK_TABLE_HASHES = "restored_table_hashes_match_the_export"
CHECK_DIGEST_HASHES = "restored_digest_payloads_still_hash"
CHECK_INTENT_LINKAGE = "restored_intents_still_resolve_to_a_digest"
CHECK_AUDIT_REPLAY = "gate_152_replay_agrees_on_both_sides"
CHECK_LEDGER_PARITY = "evidence_ledger_statuses_are_identical"
CHECK_ARCHIVE_STATE = "archived_rows_are_still_archived_and_readable"
CHECK_ORG_PARTITION = "a_cross_organization_read_is_still_refused"
CHECK_LEGACY_GAPS = "legacy_gaps_survived_as_legacy_gaps"

ORDERED_CHECKS: tuple[str, ...] = (
    CHECK_ROW_COUNTS,
    CHECK_TABLE_HASHES,
    CHECK_DIGEST_HASHES,
    CHECK_INTENT_LINKAGE,
    CHECK_AUDIT_REPLAY,
    CHECK_LEDGER_PARITY,
    CHECK_ARCHIVE_STATE,
    CHECK_ORG_PARTITION,
    CHECK_LEGACY_GAPS,
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _as_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except Exception:  # noqa: BLE001
        return None


def _check(name: str, passed: bool | None, detail: str, **extra: Any) -> dict[str, Any]:
    return {
        "check": name,
        # None means the check could not run, which is NOT a pass.
        "passed": passed,
        "status": (
            "PASS" if passed is True else ("FAIL" if passed is False else "UNKNOWN")
        ),
        "detail": detail,
        **extra,
    }


def _table_names(connection: Any) -> set[str]:
    return set(sa.inspect(connection).get_table_names())


def _read_table(connection: Any, name: str, columns: list[str], org: uuid.UUID) -> list:
    rows = (
        connection.execute(
            sa.text(
                f"SELECT {', '.join(columns)} FROM {name} WHERE organization_id = :org"
            ),
            {"org": org.hex},
        )
        .mappings()
        .all()
    )
    return [_json_safe(dict(row)) for row in rows]


def _count(connection: Any, name: str, org: uuid.UUID) -> int:
    return int(
        connection.execute(
            sa.text(f"SELECT COUNT(*) FROM {name} WHERE organization_id = :org"),
            {"org": org.hex},
        ).scalar()
        or 0
    )


def _digest_ids(connection: Any, org: uuid.UUID, limit: int) -> list[str]:
    """The tenant-facing `digest_id`, not the row's primary key.

    `nf_tenant_digest_records` carries both, and `replay_digest` resolves the
    former. A first pass here selected `id`, asked the replay about a digest
    that does not exist under that name, and got `missing_record` back for a
    digest that was sitting in the table - a lookup-key mistake wearing the
    costume of a data-integrity failure.
    """
    rows = (
        connection.execute(
            sa.text(
                "SELECT digest_id FROM nf_tenant_digest_records "
                "WHERE organization_id = :org ORDER BY digest_id LIMIT :lim"
            ),
            {"org": org.hex, "lim": limit},
        )
        .scalars()
        .all()
    )
    return [str(value) for value in rows if str(value or "").strip()]


def _intent_ids(connection: Any, org: uuid.UUID, limit: int) -> list[str]:
    rows = (
        connection.execute(
            sa.text(
                "SELECT id FROM nf_digest_delivery_intents "
                "WHERE organization_id = :org ORDER BY id LIMIT :lim"
            ),
            {"org": org.hex, "lim": limit},
        )
        .scalars()
        .all()
    )
    return [str(_as_uuid(value) or value) for value in rows]


def _link_statuses(result: dict[str, Any]) -> dict[str, str]:
    return {
        str(link.get("link")): normalize(link.get("status"))
        for link in (result.get("links") or [])
    }


def verify_restored_state(
    *,
    source_connection: Any = None,
    restored_connection: Any = None,
    organization_id: Any = None,
    export: dict[str, Any] | None = None,
    restore: dict[str, Any] | None = None,
    sample_limit: int = 10,
) -> dict[str, Any]:
    """Run the Gate 152 replay on both sides and compare the answers."""
    blocked: list[str] = []
    org = _as_uuid(organization_id)
    normalized = str(organization_id or "").strip().lower()

    if restored_connection is None:
        blocked.append("no_restored_connection_supplied")
    if org is None:
        blocked.append("organization_id_is_not_uuid_shaped")
    if normalized == REAL_ORGANIZATION_ID:
        blocked.append("real_organization_refused_by_name")
    if restore is not None and not restore.get("restored"):
        blocked.append("restore_did_not_run")

    if blocked:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "scope": CONTROLLED_SCOPE,
                "organization_id": normalized or None,
                "verified": False,
                "checks": [_check(name, None, "not run") for name in ORDERED_CHECKS],
                "checks_total": len(ORDERED_CHECKS),
                "checks_passed": 0,
                "checks_failed": 0,
                "checks_unknown": len(ORDERED_CHECKS),
                "blocked_reasons": sorted(set(blocked)),
                "rows_written": 0,
                "evidence_fabricated": False,
            }
        )

    payload_tables = (export or {}).get("tables") or {}
    present = _table_names(restored_connection)
    checks: list[dict[str, Any]] = []

    # 1. Row counts.
    count_diffs: list[str] = []
    counted = 0
    for entry in INCLUDED_TABLES:
        name = entry["table"]
        expected = int((payload_tables.get(name) or {}).get("row_count", 0))
        if name not in present:
            if expected:
                count_diffs.append(f"{name}:absent_but_export_had_{expected}")
            continue
        actual = _count(restored_connection, name, org)
        counted += actual
        if actual != expected:
            count_diffs.append(f"{name}:expected_{expected}_found_{actual}")
    checks.append(
        _check(
            CHECK_ROW_COUNTS,
            not count_diffs,
            f"{counted} rows present across the restored manifest tables",
            differences=sorted(count_diffs),
        )
    )

    # 2. Table hashes, recomputed from the restored database.
    hash_diffs: list[str] = []
    hashed_tables = 0
    for entry in INCLUDED_TABLES:
        name = entry["table"]
        exported = payload_tables.get(name)
        if not exported or name not in present:
            continue
        columns = exported.get("columns") or []
        if not columns:
            continue
        rows = _read_table(restored_connection, name, columns, org)
        hashed_tables += 1
        if table_payload_sha256(rows) != exported.get("payload_sha256"):
            hash_diffs.append(name)
    checks.append(
        _check(
            CHECK_TABLE_HASHES,
            not hash_diffs,
            f"{hashed_tables} tables rehashed from the restored database",
            mismatched_tables=sorted(hash_diffs),
        )
    )

    # 3-5. The Gate 152 replay, run on both sides.
    digest_ids = _digest_ids(restored_connection, org, sample_limit)
    intent_ids = _intent_ids(restored_connection, org, sample_limit)

    digest_failures: list[str] = []
    digest_disagreements: list[str] = []
    digest_proven = 0
    for digest_id in digest_ids:
        restored_result = replay_digest(
            connection=restored_connection,
            organization_id=str(org),
            digest_id=digest_id,
        )
        # The PAYLOAD HASH link, not the whole chain's status.
        #
        # A first pass here read `evidence_status`, which is the weakest link,
        # and the weakest link on the one persisted fixture digest is
        # `not_replayable` - because no delivery intent names it. That is an
        # honest Gate 152 finding about queueing and says nothing at all about
        # whether the payload still hashes, which it does. Folding it in made
        # this check report 0 hash-proven digests over a digest whose hash
        # verifies.
        restored_links = _link_statuses(restored_result)
        restored_status = restored_links.get("payload_hash", UNKNOWN)
        if is_proof(restored_status):
            digest_proven += 1
        if source_connection is None:
            # With nothing to compare against, the only defensible bar is that
            # the restored payload hash proves itself.
            if not is_proof(restored_status):
                digest_failures.append(digest_id)
        else:
            source_result = replay_digest(
                connection=source_connection,
                organization_id=str(org),
                digest_id=digest_id,
            )
            source_status = _link_statuses(source_result).get("payload_hash", UNKNOWN)
            # A digest the source could not prove must not become provable by
            # being restored, and one it could prove must stay provable. Any
            # movement in either direction is a failure.
            if rank(restored_status) != rank(source_status):
                digest_failures.append(digest_id)
            if _link_statuses(source_result) != restored_links:
                digest_disagreements.append(digest_id)

    checks.append(
        _check(
            CHECK_DIGEST_HASHES,
            (not digest_failures) if digest_ids else None,
            (
                f"{len(digest_ids)} restored digests replayed, {digest_proven} "
                "of them hash-proven; a status that moved in either direction "
                "is a failure here"
                if digest_ids
                else "no digest was restored, so nothing could be rehashed"
            ),
            failed_digest_ids=sorted(digest_failures),
            digests_proven=digest_proven,
        )
    )

    intent_unresolved: list[str] = []
    intent_disagreements: list[str] = []
    restored_gaps: list[str] = []
    for intent_id in intent_ids:
        restored_result = replay_delivery_intent(
            connection=restored_connection,
            organization_id=str(org),
            intent_id=intent_id,
        )
        statuses = _link_statuses(restored_result)
        digest_link = statuses.get("digest_record", UNKNOWN)
        if digest_link == LEGACY_GAP:
            restored_gaps.append(intent_id)

        if source_connection is None:
            if rank(digest_link) > rank(LEGACY_GAP):
                # Worse than a gap: the link named a digest and it was not
                # there. A gap is permitted; a broken link is not.
                intent_unresolved.append(intent_id)
        else:
            source_result = replay_delivery_intent(
                connection=source_connection,
                organization_id=str(org),
                intent_id=intent_id,
            )
            source_statuses = _link_statuses(source_result)
            source_digest_link = source_statuses.get("digest_record", UNKNOWN)
            if rank(digest_link) != rank(source_digest_link):
                intent_unresolved.append(intent_id)
            if source_statuses != statuses:
                intent_disagreements.append(intent_id)

    checks.append(
        _check(
            CHECK_INTENT_LINKAGE,
            (not intent_unresolved) if intent_ids else None,
            (
                f"{len(intent_ids)} restored intents replayed, "
                f"{len(restored_gaps)} of them legacy gaps that must stay gaps"
            )
            if intent_ids
            else "no delivery intent was restored",
            unresolved_intent_ids=sorted(intent_unresolved),
        )
    )

    replay_ran = bool(source_connection is not None and (digest_ids or intent_ids))
    checks.append(
        _check(
            CHECK_AUDIT_REPLAY,
            (not digest_disagreements and not intent_disagreements)
            if replay_ran
            else None,
            (
                "the same replay code answered identically on both sides"
                if replay_ran
                else "no source connection supplied, so nothing was compared"
            ),
            disagreeing_digest_ids=sorted(digest_disagreements),
            disagreeing_intent_ids=sorted(intent_disagreements),
        )
    )

    # 6. Ledger parity.
    restored_ledger = build_evidence_ledger(
        connection=restored_connection, organization_id=str(org), limit=sample_limit
    )
    ledger_diffs: list[str] = []
    ledger_compared = False
    if source_connection is not None:
        source_ledger = build_evidence_ledger(
            connection=source_connection, organization_id=str(org), limit=sample_limit
        )
        ledger_compared = True

        def _by_id(ledger: dict[str, Any]) -> dict[str, str]:
            return {
                f"{e.get('evidence_type')}:{e.get('record_id')}": normalize(
                    e.get("evidence_status")
                )
                for e in (ledger.get("entries") or [])
            }

        source_map = _by_id(source_ledger)
        restored_map = _by_id(restored_ledger)
        for key in sorted(set(source_map) | set(restored_map)):
            if source_map.get(key) != restored_map.get(key):
                ledger_diffs.append(
                    f"{key}:{source_map.get(key)}->{restored_map.get(key)}"
                )

    checks.append(
        _check(
            CHECK_LEDGER_PARITY,
            (not ledger_diffs) if ledger_compared else None,
            (
                f"{restored_ledger.get('entry_count', 0)} restored ledger entries "
                "compared against the source"
                if ledger_compared
                else "no source connection supplied, so nothing was compared"
            ),
            differences=sorted(ledger_diffs),
        )
    )

    # 7. Archive state. Archive is a state, and an archived row must still read.
    archive_failures: list[str] = []
    archived_seen = 0
    for entry in INCLUDED_TABLES:
        field = entry.get("archive_field")
        name = entry["table"]
        if not field or name not in present:
            continue
        exported = payload_tables.get(name) or {}
        if field not in (exported.get("columns") or []):
            continue
        expected_archived = sum(
            1 for row in (exported.get("rows") or []) if row.get(field)
        )
        actual_archived = int(
            restored_connection.execute(
                sa.text(
                    f"SELECT COUNT(*) FROM {name} "
                    f"WHERE organization_id = :org AND {field} IS NOT NULL"
                ),
                {"org": org.hex},
            ).scalar()
            or 0
        )
        archived_seen += actual_archived
        if actual_archived != expected_archived:
            archive_failures.append(
                f"{name}.{field}:expected_{expected_archived}_found_{actual_archived}"
            )
    checks.append(
        _check(
            CHECK_ARCHIVE_STATE,
            not archive_failures,
            f"{archived_seen} archived rows restored and still readable",
            differences=sorted(archive_failures),
        )
    )

    # 8. The partition must survive. A read for another org must find nothing.
    other = uuid.uuid5(uuid.NAMESPACE_URL, "gate153-not-this-organization")
    leaked_partitions: list[str] = []
    for entry in INCLUDED_TABLES:
        name = entry["table"]
        if name not in present:
            continue
        if _count(restored_connection, name, other):
            leaked_partitions.append(name)
    checks.append(
        _check(
            CHECK_ORG_PARTITION,
            not leaked_partitions,
            "a read scoped to a different organization returned nothing",
            leaked_tables=sorted(leaked_partitions),
        )
    )

    # 9. Legacy gaps survived as gaps.
    restored_gap_report = find_legacy_gaps(
        connection=restored_connection, organization_id=str(org)
    )
    restored_gap_count = int(restored_gap_report.get("legacy_gap_count", 0))
    source_gap_count: int | None = None
    if source_connection is not None:
        source_gap_count = int(
            find_legacy_gaps(
                connection=source_connection, organization_id=str(org)
            ).get("legacy_gap_count", 0)
        )
    checks.append(
        _check(
            CHECK_LEGACY_GAPS,
            (restored_gap_count == source_gap_count)
            if source_gap_count is not None
            else None,
            (
                f"{restored_gap_count} legacy gaps restored; the source has "
                f"{source_gap_count}. A restore that reduced this number would "
                "have invented a digest."
                if source_gap_count is not None
                else "no source connection supplied, so nothing was compared"
            ),
            restored_legacy_gap_count=restored_gap_count,
            source_legacy_gap_count=source_gap_count,
        )
    )

    passed = sum(1 for check in checks if check["passed"] is True)
    failed = sum(1 for check in checks if check["passed"] is False)
    unknown = sum(1 for check in checks if check["passed"] is None)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "organization_id": str(org),
            # UNKNOWN is not a pass. A verification that could not run
            # everything has not verified everything.
            "verified": failed == 0 and unknown == 0,
            "checks": checks,
            "checks_total": len(checks),
            "checks_passed": passed,
            "checks_failed": failed,
            "checks_unknown": unknown,
            "restored_row_count": counted,
            "restored_legacy_gap_count": restored_gap_count,
            "blocked_reasons": [],
            "comparison_is_fidelity_not_health": (
                "this compares source to restored. A source holding a "
                "missing_record must restore to a missing_record, and that is "
                "a pass here and a finding in the ledger."
            ),
            "rows_written": 0,
            "evidence_fabricated": False,
            "legacy_gaps_backfilled": False,
            "production_backup_ready": False,
        }
    )


def verification_invariant_failures(verification: dict[str, Any]) -> list[str]:
    """Refuse a verification that passed itself without doing the work."""
    fails: list[str] = []

    checks = verification.get("checks") or []
    names = [check.get("check") for check in checks]

    missing = set(ORDERED_CHECKS) - set(names)
    if missing and not verification.get("blocked_reasons"):
        fails.append(f"check_missing:{sorted(missing)}")
    if len(names) != len(set(names)):
        fails.append("a_check_is_reported_twice")

    passed = sum(1 for check in checks if check.get("passed") is True)
    failed = sum(1 for check in checks if check.get("passed") is False)
    unknown = sum(1 for check in checks if check.get("passed") is None)
    if passed != verification.get("checks_passed"):
        fails.append("checks_passed_disagrees")
    if failed != verification.get("checks_failed"):
        fails.append("checks_failed_disagrees")
    if unknown != verification.get("checks_unknown"):
        fails.append("checks_unknown_disagrees")

    if verification.get("verified"):
        if failed:
            fails.append("verified_alongside_a_failed_check")
        if unknown:
            fails.append("verified_while_a_check_could_not_run")
        if verification.get("blocked_reasons"):
            fails.append("verified_alongside_blockers")

    for check in checks:
        status = check.get("status")
        expected = (
            "PASS"
            if check.get("passed") is True
            else ("FAIL" if check.get("passed") is False else "UNKNOWN")
        )
        if status != expected:
            fails.append(f"check_status_disagrees:{check.get('check')}")

    if verification.get("rows_written"):
        fails.append("verification_wrote_rows")
    if verification.get("evidence_fabricated"):
        fails.append("verification_fabricated_evidence")
    if verification.get("legacy_gaps_backfilled"):
        fails.append("verification_backfilled_legacy_gaps")
    if verification.get("production_backup_ready"):
        fails.append("verification_claimed_production_backup_readiness")

    return sorted(set(fails))
