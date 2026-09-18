"""Where a human's recorded answer about a source lives (Gate 162C/D).

The table is DECLARED, not reflected. Gate 161's attempt repository settled
this: `sa.Table(..., autoload_with=...)` under SQLite loses `sa.Uuid`, and the
first insert fails on parameter binding rather than on anything meaningful. A
declared table also means the column vocabulary is visible in the code that
uses it.

## This repository cannot approve anything

`record_decision` writes whatever decision it is handed, and the database
refuses an `approved` row without `reviewed_by`, `reviewed_at` and an evidence
fingerprint. There is no `approve_source()` here and there is deliberately no
convenience that fills attribution in for a caller: the only way to record an
approval is to supply who decided it, when, and what they read.

## One decision per source

The unique index is on `(organization_id, source_id)`, so a re-review replaces
the answer. Two live answers about the same terms is a question with no defined
winner, and an append-only history would need a "which one counts" rule that
somebody would eventually get wrong.

The previous answer is not lost silently - `record_decision` reports what it
replaced.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa

SCHEMA_VERSION = "nf_source_authorization_decision_repository_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

TABLE = "nf_source_authorization_decisions"

TERMS = "terms"
HUMAN_REVIEW = "human_review"

#: Which question a row answers. Required on every call and deliberately NOT
#: defaulted - a default would let a caller record a terms answer under the
#: human-review question by forgetting an argument.
LIVE_FETCH = "live_fetch"

#: Gate 163 added `live_fetch`. Migration 0052 matches this.
DECISION_KINDS: frozenset[str] = frozenset({TERMS, HUMAN_REVIEW, LIVE_FETCH})

BLOCK_BAD_KIND = "decision_kind_outside_vocabulary"

APPROVED = "approved"
DENIED = "denied"
NEEDS_REVIEW = "needs_review"
UNKNOWN = "unknown"

DECISIONS: frozenset[str] = frozenset({APPROVED, DENIED, NEEDS_REVIEW, UNKNOWN})

#: The guard's own vocabulary, and which members an approval may carry.
GUARD_STATUSES: frozenset[str] = frozenset(
    {
        "NO_REVIEW_REQUIRED",
        "ATTRIBUTION_REQUIRED",
        "TERMS_REVIEW_REQUIRED",
        "HUMAN_REVIEW_ONLY",
        "UNKNOWN",
        # Human-review rows answer a question the guard has no status for.
        "NOT_APPLICABLE",
    }
)

APPROVAL_PERMITTING_STATUSES: frozenset[str] = frozenset(
    {"NO_REVIEW_REQUIRED", "ATTRIBUTION_REQUIRED"}
)

FACT_STATUSES: frozenset[str] = frozenset(
    {"synthetic_fixture", "demo_fixture", "tenant_supplied", "unknown"}
)

DEMO_ORG = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
REAL_ORG = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")

BLOCK_NO_CONNECTION = "no_connection_supplied"
BLOCK_NO_ORGANIZATION = "no_usable_organization_id"
BLOCK_REAL_ORG = "real_organization_refused_by_name"
BLOCK_NO_SOURCE = "no_source_id_supplied"
BLOCK_BAD_DECISION = "decision_outside_vocabulary"
BLOCK_BAD_GUARD_STATUS = "guard_status_outside_vocabulary"
BLOCK_UNSIGNED_APPROVAL = "an_approval_needs_reviewed_by_and_reviewed_at"
BLOCK_UNEVIDENCED_APPROVAL = "an_approval_needs_an_evidence_fingerprint"
BLOCK_UNSIGNED_DENIAL = "a_denial_needs_reviewed_by"
BLOCK_CONTRADICTORY = "an_approval_cannot_carry_a_blocking_guard_status"
BLOCK_WRITE_FAILED = "the_write_was_refused_by_the_database"

_METADATA = sa.MetaData()

DECISIONS_TABLE = sa.Table(
    TABLE,
    _METADATA,
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
    sa.Column("is_demo", sa.Boolean(), nullable=False),
    sa.Column("source_id", sa.Text(), nullable=False),
    sa.Column("decision", sa.String(length=16), nullable=False),
    sa.Column("decision_kind", sa.String(length=24), nullable=False),
    sa.Column("guard_status", sa.String(length=32), nullable=False),
    sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("reviewed_by", sa.String(length=256), nullable=True),
    sa.Column("review_authority", sa.String(length=128), nullable=True),
    sa.Column("evidence_fingerprint", sa.String(length=64), nullable=True),
    sa.Column("evidence_document_sha256", sa.String(length=64), nullable=True),
    sa.Column("evidence_ref", sa.String(length=512), nullable=True),
    sa.Column("notes_classification", sa.String(length=256), nullable=True),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("re_review_due_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("fact_status", sa.String(length=32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _result(**fields: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "scope": CONTROLLED_SCOPE,
        "recorded": False,
        "decision": None,
        "replaced": None,
        "blocked_reasons": [],
        "invariant_failures": [],
        "sources_approved_by_this_call": 0,
        "live_source_call": False,
        "source_monitoring_live": False,
    }
    base.update(fields)
    base["blocked_reasons"] = sorted(set(base["blocked_reasons"] or []))
    return _json_safe(base)


def _as_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def _as_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _validate(
    *, connection: Any, organization_id: Any, source_id: Any = None
) -> tuple[uuid.UUID | None, list[str]]:
    blocked: list[str] = []
    if connection is None:
        blocked.append(BLOCK_NO_CONNECTION)
    org = _as_uuid(organization_id)
    if org is None:
        blocked.append(BLOCK_NO_ORGANIZATION)
    elif org == REAL_ORG:
        # By name. The standing authorization is demo-org only, and a terms
        # decision against the real organization is exactly the row that would
        # make a real source callable.
        blocked.append(BLOCK_REAL_ORG)
        org = None
    if source_id is not None and not str(source_id or "").strip():
        blocked.append(BLOCK_NO_SOURCE)
    return org, blocked


def _row_to_decision(row: Any) -> dict[str, Any]:
    mapping = row._mapping if hasattr(row, "_mapping") else row
    return _json_safe(
        {
            "source_id": mapping["source_id"],
            "decision_kind": mapping["decision_kind"],
            "decision": mapping["decision"],
            "guard_status": mapping["guard_status"],
            "reviewed_at": mapping["reviewed_at"],
            "reviewed_by": mapping["reviewed_by"],
            "review_authority": mapping["review_authority"],
            "evidence_fingerprint": mapping["evidence_fingerprint"],
            "evidence_document_sha256": mapping["evidence_document_sha256"],
            "evidence_ref": mapping["evidence_ref"],
            "notes_classification": mapping["notes_classification"],
            "expires_at": mapping["expires_at"],
            "re_review_due_at": mapping["re_review_due_at"],
            "fact_status": mapping["fact_status"],
            "created_at": mapping["created_at"],
            "updated_at": mapping["updated_at"],
        }
    )


def get_decision(
    *,
    connection: Any = None,
    organization_id: Any = None,
    source_id: Any = None,
    decision_kind: str | None = None,
) -> dict[str, Any]:
    """The recorded decision for one source, or nothing.

    Returns `record_exists: False` rather than a decision defaulted to
    `unknown`. Gate 162's fact model needs "no row" and "a row saying unknown"
    to stay distinguishable, and a repository that invents the second destroys
    the distinction before the model can see it.
    """
    org, blocked = _validate(
        connection=connection, organization_id=organization_id, source_id=source_id
    )
    if decision_kind not in DECISION_KINDS:
        blocked.append(f"{BLOCK_BAD_KIND}:{decision_kind}")
    if blocked or org is None:
        return _result(blocked_reasons=blocked, record_exists=False, decision=None)

    row = connection.execute(
        sa.select(DECISIONS_TABLE).where(
            sa.and_(
                DECISIONS_TABLE.c.organization_id == org,
                DECISIONS_TABLE.c.source_id == str(source_id),
                DECISIONS_TABLE.c.decision_kind == str(decision_kind),
            )
        )
    ).first()

    return _result(
        recorded=row is not None,
        record_exists=row is not None,
        decision=_row_to_decision(row) if row is not None else None,
    )


def record_decision(
    *,
    connection: Any = None,
    organization_id: Any = None,
    source_id: Any = None,
    decision_kind: str | None = None,
    decision: str = UNKNOWN,
    guard_status: str = "UNKNOWN",
    reviewed_at: Any = None,
    reviewed_by: Any = None,
    review_authority: Any = None,
    evidence_fingerprint: Any = None,
    evidence_document_sha256: Any = None,
    evidence_ref: Any = None,
    notes_classification: Any = None,
    expires_at: Any = None,
    re_review_due_at: Any = None,
    fact_status: str = "synthetic_fixture",
    is_demo: bool = True,
    now: Any = None,
) -> dict[str, Any]:
    """Record one terms decision, replacing any previous answer.

    There is no `approve()` convenience and no default attribution. An approval
    requires a reviewer, a time and an evidence fingerprint, and the database
    refuses one without them - so a caller who wants to approve must have
    something to show.
    """
    org, blocked = _validate(
        connection=connection, organization_id=organization_id, source_id=source_id
    )

    kind = str(decision_kind or "").strip()
    if kind not in DECISION_KINDS:
        blocked.append(f"{BLOCK_BAD_KIND}:{kind}")

    verdict = str(decision or "").strip()
    guard_status = str(guard_status or "").strip()
    if verdict not in DECISIONS:
        blocked.append(f"{BLOCK_BAD_DECISION}:{verdict}")
    if guard_status not in GUARD_STATUSES:
        blocked.append(f"{BLOCK_BAD_GUARD_STATUS}:{guard_status}")
    if str(fact_status or "") not in FACT_STATUSES:
        blocked.append(f"fact_status_outside_vocabulary:{fact_status}")

    moment = _as_datetime(now)
    if moment is None:
        blocked.append("no_clock_supplied")

    signed_at = _as_datetime(reviewed_at)
    signer = str(reviewed_by or "").strip() or None

    # Checked here AND by the database. The service refusal names the problem
    # usefully; the CHECK is what makes the refusal unbypassable.
    if verdict == APPROVED:
        if signer is None or signed_at is None:
            blocked.append(BLOCK_UNSIGNED_APPROVAL)
        if not str(evidence_fingerprint or "").strip():
            blocked.append(BLOCK_UNEVIDENCED_APPROVAL)
        # Only a TERMS approval can contradict the guard; human-review rows
        # carry NOT_APPLICABLE because the guard has no status for that
        # question.
        if kind == TERMS and guard_status not in APPROVAL_PERMITTING_STATUSES:
            blocked.append(f"{BLOCK_CONTRADICTORY}:{guard_status}")
    if verdict == DENIED and signer is None:
        blocked.append(BLOCK_UNSIGNED_DENIAL)

    if blocked or org is None:
        return _result(blocked_reasons=blocked)

    keyed = sa.and_(
        DECISIONS_TABLE.c.organization_id == org,
        DECISIONS_TABLE.c.source_id == str(source_id),
        DECISIONS_TABLE.c.decision_kind == kind,
    )
    existing = connection.execute(sa.select(DECISIONS_TABLE).where(keyed)).first()
    replaced = _row_to_decision(existing) if existing is not None else None

    values = {
        "decision": verdict,
        "guard_status": guard_status,
        "reviewed_at": signed_at,
        "reviewed_by": signer,
        "review_authority": (str(review_authority).strip() or None)
        if review_authority
        else None,
        "evidence_fingerprint": (str(evidence_fingerprint) or None)
        if evidence_fingerprint
        else None,
        "evidence_document_sha256": (str(evidence_document_sha256) or None)
        if evidence_document_sha256
        else None,
        "evidence_ref": (str(evidence_ref)[:512] or None) if evidence_ref else None,
        "notes_classification": (str(notes_classification)[:256] or None)
        if notes_classification
        else None,
        "expires_at": _as_datetime(expires_at),
        "re_review_due_at": _as_datetime(re_review_due_at),
        "fact_status": str(fact_status),
        "updated_at": moment,
    }

    try:
        if existing is not None:
            connection.execute(
                sa.update(DECISIONS_TABLE).where(keyed).values(**values)
            )
        else:
            connection.execute(
                sa.insert(DECISIONS_TABLE).values(
                    id=uuid.uuid4(),
                    organization_id=org,
                    is_demo=bool(is_demo),
                    source_id=str(source_id),
                    decision_kind=kind,
                    created_at=moment,
                    **values,
                )
            )
    except Exception as exc:  # noqa: BLE001 - the refusal is the result
        return _result(
            blocked_reasons=[f"{BLOCK_WRITE_FAILED}:{type(exc).__name__}"],
            replaced=replaced,
        )

    written = connection.execute(sa.select(DECISIONS_TABLE).where(keyed)).first()

    return _result(
        recorded=True,
        decision=_row_to_decision(written) if written is not None else None,
        replaced=replaced,
        sources_approved_by_this_call=1 if verdict == APPROVED else 0,
    )


def list_decisions(
    *,
    connection: Any = None,
    organization_id: Any = None,
    decision_kind: Any = None,
    decision: Any = None,
    limit: int = 500,
) -> dict[str, Any]:
    org, blocked = _validate(connection=connection, organization_id=organization_id)
    if blocked or org is None:
        return _result(blocked_reasons=blocked, decisions=[], count=0)

    query = sa.select(DECISIONS_TABLE).where(
        DECISIONS_TABLE.c.organization_id == org
    )
    if decision_kind is not None:
        query = query.where(DECISIONS_TABLE.c.decision_kind == str(decision_kind))
    if decision is not None:
        query = query.where(DECISIONS_TABLE.c.decision == str(decision))
    rows = connection.execute(
        query.order_by(DECISIONS_TABLE.c.source_id).limit(int(limit))
    ).all()

    return _result(
        recorded=True,
        decisions=[_row_to_decision(row) for row in rows],
        count=len(rows),
    )


def count_decisions(
    *,
    connection: Any = None,
    organization_id: Any = None,
    decision_kind: Any = None,
) -> dict[str, Any]:
    """How many decisions, by verdict. `approved` is the number that matters."""
    org, blocked = _validate(connection=connection, organization_id=organization_id)
    empty = {
        "by_decision": dict.fromkeys(sorted(DECISIONS), 0),
        "by_kind": {
            k: dict.fromkeys(sorted(DECISIONS), 0) for k in sorted(DECISION_KINDS)
        },
        "total": 0,
        "approved": 0,
        "signed_approvals": 0,
        "unsigned_approvals": 0,
    }
    if blocked or org is None:
        return _result(blocked_reasons=blocked, **empty)

    scoped = DECISIONS_TABLE.c.organization_id == org
    if decision_kind is not None:
        scoped = sa.and_(
            scoped, DECISIONS_TABLE.c.decision_kind == str(decision_kind)
        )

    by_decision = dict.fromkeys(sorted(DECISIONS), 0)
    for row in connection.execute(
        sa.select(DECISIONS_TABLE.c.decision, sa.func.count())
        .where(scoped)
        .group_by(DECISIONS_TABLE.c.decision)
    ):
        by_decision[str(row[0])] = int(row[1])

    # Broken out by question too. "1 approved" without saying WHICH question
    # was answered is exactly the ambiguity this gate exists to remove.
    by_kind: dict[str, dict[str, int]] = {
        k: dict.fromkeys(sorted(DECISIONS), 0) for k in sorted(DECISION_KINDS)
    }
    for row in connection.execute(
        sa.select(
            DECISIONS_TABLE.c.decision_kind,
            DECISIONS_TABLE.c.decision,
            sa.func.count(),
        )
        .where(DECISIONS_TABLE.c.organization_id == org)
        .group_by(DECISIONS_TABLE.c.decision_kind, DECISIONS_TABLE.c.decision)
    ):
        by_kind.setdefault(str(row[0]), {})[str(row[1])] = int(row[2])

    signed = int(
        connection.execute(
            sa.select(sa.func.count())
            .select_from(DECISIONS_TABLE)
            .where(
                sa.and_(
                    scoped,
                    DECISIONS_TABLE.c.decision == APPROVED,
                    DECISIONS_TABLE.c.reviewed_by.isnot(None),
                    DECISIONS_TABLE.c.reviewed_at.isnot(None),
                )
            )
        ).scalar()
        or 0
    )
    approved = by_decision.get(APPROVED, 0)

    return _result(
        recorded=True,
        by_decision=by_decision,
        by_kind=by_kind,
        total=sum(by_decision.values()),
        approved=approved,
        signed_approvals=signed,
        # Should always be zero: the database refuses one. Reported so that
        # "the constraint is holding" is a measurement rather than a belief.
        unsigned_approvals=approved - signed,
    )


def decision_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Refuse a result that claims an approval it cannot show evidence for."""
    fails: list[str] = list(result.get("invariant_failures") or [])

    if result.get("recorded") and result.get("blocked_reasons"):
        fails.append("recorded_alongside_blocked_reasons")

    decision = result.get("decision") or {}
    if decision.get("decision") == APPROVED:
        if not decision.get("reviewed_by"):
            fails.append("an_approval_with_no_reviewer")
        if not decision.get("reviewed_at"):
            fails.append("an_approval_with_no_decision_time")
        if not decision.get("evidence_fingerprint"):
            fails.append("an_approval_with_no_evidence")
        if decision.get("decision_kind") == TERMS and decision.get(
            "guard_status"
        ) not in APPROVAL_PERMITTING_STATUSES:
            fails.append(
                f"an_approval_carrying_a_blocking_guard_status:"
                f"{decision.get('guard_status')}"
            )
        if decision.get("decision_kind") not in DECISION_KINDS:
            fails.append(
                f"a_decision_of_no_known_kind:{decision.get('decision_kind')}"
            )

    # The count's own consistency. An unsigned approval in the table would mean
    # the CHECK had stopped holding.
    if int(result.get("unsigned_approvals") or 0):
        fails.append(
            f"unsigned_approvals_exist:{result.get('unsigned_approvals')}"
        )

    for claim in ("live_source_call", "source_monitoring_live"):
        if result.get(claim):
            fails.append(f"decision_repository_claimed:{claim}")

    return sorted(set(fails))
