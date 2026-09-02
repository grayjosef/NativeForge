"""Postgres-backed membership directory (Gate 64, completing Gate 62).

Gate 61 delivered ``InMemoryMembershipDirectory`` — a design vehicle, named so
it could not be mistaken for a store. This module is the production-path
version: it reads identity and membership rows from PostgreSQL through the
tables migrations 0023-0027 created, under the RLS policies migration 0027
installed.

**It is production-path code. It is not a live production claim.** No managed
PostgreSQL instance is provisioned for NativeForge, so in every environment that
exists today this adapter fails closed and reports
``production_storage_live=False``. The difference from Gate 61 is that the code
is now real enough to be wrong in a provisioned environment, which is the
prerequisite for ever being right in one.

Design notes worth stating, because each is a place this could have quietly
cheated:

  * **Row access is injected, not imported.** The adapter takes a ``row_source``
    callable rather than opening its own connection. Without one it denies. That
    keeps the trust logic testable without a database while leaving no in-memory
    fallback that could be mistaken for persistence.
  * **Identity is ``(issuer, subject)``, never email.** Two providers can issue
    the same subject string, and email is mutable and re-assignable. Migration
    0023's unique constraint is on ``(issuer, subject)`` and this code matches it.
  * **Trust is derived from the row, never accepted from the caller.** A caller
    can ask about an organization; it cannot assert membership in one.
  * **Every denial produces an audit event.** A silent denial is an
    unobservable one, and the whole point of tenant isolation is being able to
    show it held.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from nativeforge.services.membership_directory_service import (
    ACTING_STATES,
    DENYING_STATES,
    MEMBERSHIP_STATES,
    TRUSTED_MEMBERSHIP_SOURCES,
    TRUSTED_ROLE_SOURCES,
)
from nativeforge.services.org_tenant_seat_model_service import (
    ALL_ROLES,
    INTERNAL_ROLES,
)

SCHEMA_VERSION = "nf_postgres_membership_directory_v1"

IDENTITY_TABLE = "nf_identities"
MEMBERSHIP_TABLE = "nf_org_memberships"

# The migration head this adapter was written against. A runtime database at a
# different revision has a schema this code was never reviewed for, so the
# adapter declines rather than guessing — the same doctrine the active-source
# services use with TARGET_REVISION_ID.
#
# Gate 96 moved this 0027 -> 0028, and the move is a claim that the adapter was
# reviewed against the new schema rather than merely re-pinned to unblock a
# test. The review: 0028's upgrade() performs exactly one create_table
# (nf_raw_source_payloads) and five create_index calls on that same table. It
# touches neither nf_identities nor nf_org_memberships — the only two tables
# this adapter reads — nor organizations. The adapter's schema is unchanged.
#
# Gate 113 moved it 0028 -> 0029, under the same standard. The review: 0029's
# upgrade() performs one create_table (nf_tenant_customer_org_bindings) and two
# create_index calls on that table, then installs an RLS policy on it. It reads
# nf_identities and organizations only as foreign key *targets*, which alters
# neither. Neither nf_org_memberships nor nf_identities gains, loses or changes
# a column, and the 0027 policies this adapter relies on are untouched. The
# adapter's schema is unchanged.
#
# Gate 119 moved it 0029 -> 0030, under the same standard. The review: 0030's
# upgrade() performs one create_table (nf_auth_redirect_states) and two
# create_index calls on that table, and installs no RLS policy at all - the row
# predates authentication, so it carries no organization_id to scope on, the
# same position nf_identities (0023) has held since Gate 62. It reads
# nf_identities only as a foreign key *target* for consumed_by_identity_id,
# which alters it in no way. Neither nf_org_memberships nor nf_identities gains,
# loses or changes a column, and the 0027 policies this adapter relies on are
# untouched. The adapter's schema is unchanged.
#
# Gate 123 moved it 0030 -> 0031, under the same standard. The review: 0031's
# upgrade() performs one create_table (nf_tenant_beta_profiles) and two
# create_index calls on that table, then installs an RLS policy on it. It reads
# organizations and nf_identities only as foreign key *targets*, which alters
# neither. Neither nf_org_memberships nor nf_identities gains, loses or changes
# a column, and the 0027 policies this adapter relies on are untouched. The
# adapter's schema is unchanged.
# Gate 124 moved it 0031 -> 0032, under the same standard. The review: 0032's
# upgrade() performs one create_table (nf_awarded_grants) and three
# create_index calls on that table, then installs an RLS policy on it. It reads
# organizations, nf_identities and nf_tenant_beta_profiles only as foreign key
# *targets*, which alters none of them. Neither nf_org_memberships nor
# nf_identities gains, loses or changes a column, and the 0027 policies this
# adapter relies on are untouched. The adapter's schema is unchanged.
# Gate 125 moved it 0032 -> 0033, under the same standard. The review: 0033's
# upgrade() performs one create_table (nf_award_requirements) and three
# create_index calls on that table, then installs an RLS policy on it. It reads
# organizations, nf_awarded_grants and nf_identities only as foreign key
# *targets*, which alters none of them. Neither nf_org_memberships nor
# nf_identities gains, loses or changes a column, and the 0027 policies this
# adapter relies on are untouched. The adapter's schema is unchanged.
# Gate 126 moved it 0033 -> 0034, under the same standard. The review: 0034's
# upgrade() performs one create_table (nf_award_requirement_proof_events) and
# three create_index calls on that table, then installs an RLS policy on it. It
# reads organizations, nf_award_requirements, nf_awarded_grants and
# nf_identities only as foreign key *targets*, plus one self-reference for
# supersession, which alters none of them. Neither nf_org_memberships nor
# nf_identities gains, loses or changes a column, and the 0027 policies this
# adapter relies on are untouched. The adapter's schema is unchanged.
# Gate 127 moved it 0034 -> 0035, under the same standard. The review: 0035's
# upgrade() performs one create_table (nf_award_documents) and four
# create_index calls on that table, then installs an RLS policy on it. It reads
# organizations, nf_awarded_grants, nf_award_requirements,
# nf_award_requirement_proof_events and nf_identities only as foreign key
# *targets*, which alters none of them. Neither nf_org_memberships nor
# nf_identities gains, loses or changes a column, and the 0027 policies this
# adapter relies on are untouched. The adapter's schema is unchanged.
EXPECTED_MIGRATION_HEAD = "0038"

# Sources of "membership" that are never membership, restated here so the
# production path enforces them rather than inheriting them by assumption.
NEVER_MEMBERSHIP = frozenset(
    {
        "email_domain_only",
        "cloudflare_access",
        "client_header",
        "dev_header",
        "token_claim",
    }
)

# ``unknown`` is a member of ALL_ROLES because the vocabulary needs a value for
# "we do not know". It must never grant anything: an unrecognised role resolving
# to authority is the failure mode the whole deny-by-default design exists to
# prevent.
NON_GRANTING_ROLES = frozenset({"unknown"})

# Everything production_storage_live depends on. Named individually so a report
# can say which one is missing instead of just "not live".
STORAGE_PRECONDITIONS = (
    "approval_token_present",
    "database_url_present",
    "migrations_at_expected_head",
    "rls_proof_passed",
    "backup_restore_posture_documented",
)


_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _is_uuid_shaped(value: Any) -> bool:
    """Can this value survive the ``::uuid`` cast every RLS policy performs?"""
    return bool(_UUID_RE.match(str(value or "").strip()))


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


# ── storage posture ─────────────────────────────────────────────────────────


def postgres_storage_status(
    *,
    approval_token_present: bool = False,
    database_url_present: bool = False,
    migrations_at_expected_head: bool = False,
    rls_proof_passed: bool = False,
    backup_restore_posture_documented: bool = False,
    persistence_proof_artifact: str | None = None,
) -> dict[str, Any]:
    """Report whether production storage may honestly be called live.

    Every precondition is required. This is deliberately an AND across all five:
    a database with no RLS proof is not isolation, an RLS proof with no backup
    posture is not durability, and an approval token on its own is a sentence in
    a chat log. Any single missing precondition keeps the claim false.
    """
    checks = {
        "approval_token_present": bool(approval_token_present),
        "database_url_present": bool(database_url_present),
        "migrations_at_expected_head": bool(migrations_at_expected_head),
        "rls_proof_passed": bool(rls_proof_passed),
        "backup_restore_posture_documented": bool(backup_restore_posture_documented),
    }
    missing = [name for name in STORAGE_PRECONDITIONS if not checks[name]]
    live = not missing

    # Persistence is a further claim on top of live storage: it needs an
    # artifact showing data actually survived, not merely that a store exists.
    persistence_claimed = bool(live and persistence_proof_artifact)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "storage_backend_state": (
                "approved_production_backend" if live else "not_provisioned"
            ),
            **checks,
            "missing_preconditions": missing,
            "production_storage_live": live,
            "customer_persistence_claimed": persistence_claimed,
            "persistence_proof_artifact": persistence_proof_artifact if live else None,
            "expected_migration_head": EXPECTED_MIGRATION_HEAD,
            # Storage being live would still not make login live. Different gate.
            "customer_login_live": False,
        }
    )


def storage_status_invariant_failures(status: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if status.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    live = status.get("production_storage_live")
    if live:
        for name in STORAGE_PRECONDITIONS:
            if not status.get(name):
                fails.append(f"production_live_without:{name}")
        if status.get("missing_preconditions"):
            fails.append("production_live_with_missing_preconditions")
    else:
        if status.get("storage_backend_state") == "approved_production_backend":
            fails.append("approved_backend_state_while_not_live")

    if status.get("customer_persistence_claimed"):
        if not live:
            fails.append("persistence_claimed_without_live_storage")
        if not status.get("persistence_proof_artifact"):
            fails.append("persistence_claimed_without_proof_artifact")

    if status.get("customer_login_live") is not False:
        fails.append("forbidden_claim:customer_login_live")
    return fails


# ── the adapter ─────────────────────────────────────────────────────────────

# A row source runs one parameterised query and returns mapping-like rows. In a
# provisioned environment this is a SQLAlchemy connection wrapper; in tests it is
# a stub. The adapter never constructs one itself, so "no database" is a state it
# cannot accidentally paper over.
RowSource = Callable[[str, Mapping[str, Any]], Sequence[Mapping[str, Any]]]


class PostgresMembershipDirectory:
    """Reads identity and membership from PostgreSQL. Denies without one.

    The adapter assumes the caller has already scoped the session — RLS is
    enforced by the database via ``app.current_org_id``, not by this class. The
    ``organization_id`` predicate here is defence in depth, not the boundary:
    if this code is the only thing standing between two tenants, the deployment
    is already wrong.
    """

    storage_backend_state = "postgres_production_path"

    def __init__(
        self,
        row_source: RowSource | None = None,
        *,
        approval_token_present: bool = False,
        database_url_present: bool = False,
        migrations_at_expected_head: bool = False,
        rls_proof_passed: bool = False,
        backup_restore_posture_documented: bool = False,
    ) -> None:
        self._row_source = row_source
        self._posture = {
            "approval_token_present": approval_token_present,
            "database_url_present": database_url_present,
            "migrations_at_expected_head": migrations_at_expected_head,
            "rls_proof_passed": rls_proof_passed,
            "backup_restore_posture_documented": backup_restore_posture_documented,
        }

    # -- posture ------------------------------------------------------------

    @property
    def configured(self) -> bool:
        """Whether this adapter can reach a database at all."""
        return self._row_source is not None and self._posture["database_url_present"]

    def status(self) -> dict[str, Any]:
        return postgres_storage_status(**self._posture)

    # -- lookups ------------------------------------------------------------

    def _query(
        self, sql: str, params: Mapping[str, Any]
    ) -> Sequence[Mapping[str, Any]]:
        if self._row_source is None:
            return ()
        rows = self._row_source(sql, params)
        return tuple(rows or ())

    def lookup_identity(
        self, *, issuer: str | None, subject: str | None
    ) -> dict[str, Any] | None:
        """Resolve a verified token's ``(issuer, subject)`` to an identity row.

        Email is not a lookup key. It is not unique, it changes, and it can be
        re-assigned to a different human by a domain administrator.
        """
        if not issuer or not subject or not self.configured:
            return None
        rows = self._query(
            f"SELECT id, issuer, subject, email, email_verified "
            f"FROM {IDENTITY_TABLE} WHERE issuer = :issuer AND subject = :subject",
            {"issuer": str(issuer), "subject": str(subject)},
        )
        return dict(rows[0]) if rows else None

    def lookup_membership(
        self, *, identity_id: Any, organization_id: str | None
    ) -> dict[str, Any] | None:
        """Membership for one identity in one organization.

        The parameter is ``organization_id`` because the predicate is
        ``organization_id`` - a Uuid(as_uuid=True) foreign key to
        organizations.id. It was named ``organization_profile_id`` until Gate
        113, which meant a String(128) profile identifier was being bound to a
        UUID column: two identity spaces sharing one variable.

        Nothing surfaced because the directory is unconfigured in normal
        operation and the tests supply a fake row source, so the value never
        reached a real column. Against Postgres the ``::uuid`` comparison would
        raise - the database refusing the conflation, which is a worse place to
        find out than here.
        """
        if not identity_id or not organization_id or not self.configured:
            return None
        if not _is_uuid_shaped(organization_id):
            # Refused rather than coerced. A profile id is not an organization
            # id, and passing one here would either raise in Postgres or match
            # nothing - both worse than a named refusal.
            return None
        rows = self._query(
            f"SELECT id, organization_id, identity_id, state, membership_source, "
            f"role, role_source, approved_by, revoked_at, expires_at "
            f"FROM {MEMBERSHIP_TABLE} "
            f"WHERE identity_id = :identity_id AND organization_id = :org",
            {"identity_id": identity_id, "org": str(organization_id)},
        )
        return dict(rows[0]) if rows else None


# ── resolution ──────────────────────────────────────────────────────────────


def _audit(
    event_type: str,
    *,
    subject: str | None,
    issuer: str | None,
    organization_id: str | None,
    reasons: list[str],
    persisted: bool,
) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "issuer": issuer,
        "subject": subject,
        # Gate 113: the audit records the organization the lookup actually used,
        # not whichever parameter name the caller happened to pass it under.
        "organization_id": organization_id,
        "reasons": list(reasons),
        # Modeled, not stored. Flips only when audit persistence is wired against
        # a provisioned database — see doc 391.
        "persisted": persisted,
    }


def resolve_persisted_membership(
    *,
    identity: Mapping[str, Any],
    organization_id: str | None = None,
    organization_profile_id: str | None = None,
    directory: PostgresMembershipDirectory | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Verified identity -> persisted membership -> trusted role, or a denial.

    ``now`` is caller-supplied so expiry is deterministic under test rather than
    dependent on the wall clock — the same mistake caught in Gate 60's token
    verification, not repeated here.
    """
    reasons: list[str] = []

    # Gate 113. `organization_id` is the parameter that reaches the UUID column.
    # `organization_profile_id` is kept for callers that predate this gate and
    # is deliberately NOT forwarded to that path - a profile id is not an
    # organization id, and silently coercing one is the bug this gate fixes.
    requested_organization_id = organization_id
    if organization_id is None and organization_profile_id is not None:
        if _is_uuid_shaped(organization_profile_id):
            # A UUID arriving under the old name is an organization id wearing
            # the wrong label. Accept it and say so.
            requested_organization_id = organization_profile_id
            reasons.append("organization_supplied_under_the_deprecated_parameter")
        else:
            reasons.append("organization_profile_id_is_not_an_organization_id")

    issuer = identity.get("issuer")
    subject = identity.get("subject")

    # The token must have been verified upstream. This adapter resolves
    # membership; it does not validate signatures, and it must not be reachable
    # by anything that skipped that step.
    if not identity.get("verification_trusted"):
        reasons.append("identity_verification_not_trusted")
    if not subject:
        reasons.append("identity_has_no_subject")
    if not issuer:
        reasons.append("identity_has_no_issuer")
    if not requested_organization_id:
        reasons.append("no_organization_requested")

    if directory is None or not directory.configured:
        reasons.append("no_production_storage_configured")
        status = (
            directory.status() if directory is not None else postgres_storage_status()
        )
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "allowed": False,
                "blocked_reasons": reasons,
                "issuer": issuer,
                "subject": subject,
                "organization_id": requested_organization_id,
                "organization_profile_id": organization_profile_id,
                "trusted_role": None,
                "identity_row_found": False,
                "membership_row_found": False,
                "membership_state": None,
                "membership_source": None,
                "storage_backend_state": status["storage_backend_state"],
                "production_storage_live": status["production_storage_live"],
                "customer_persistence_claimed": status["customer_persistence_claimed"],
                "customer_login_live": False,
                "audit_event": _audit(
                    "tenant_access_denied",
                    subject=subject,
                    issuer=issuer,
                    organization_id=requested_organization_id,
                    reasons=reasons,
                    persisted=False,
                ),
            }
        )

    status = directory.status()
    persisted = bool(status["production_storage_live"])

    identity_row = (
        directory.lookup_identity(issuer=issuer, subject=subject)
        if (issuer and subject)
        else None
    )
    if identity_row is None:
        reasons.append("no_identity_row")

    membership_row = None
    if identity_row is not None and requested_organization_id:
        membership_row = directory.lookup_membership(
            identity_id=identity_row.get("id"),
            organization_id=requested_organization_id,
        )
        if membership_row is None:
            reasons.append("no_membership_row")

    state: str | None = None
    msource: str | None = None
    trusted_role: str | None = None

    if membership_row is not None:
        raw_state = str(membership_row.get("state") or "unknown")
        state = raw_state if raw_state in MEMBERSHIP_STATES else "unknown"
        msource = str(membership_row.get("membership_source") or "none")
        rsource = str(membership_row.get("role_source") or "none")
        role = membership_row.get("role")

        # Derived, not accepted. A row saying "active" while carrying a
        # revocation timestamp is revoked, whatever the column says. The database
        # CHECK constraints should prevent this, but a proof that relies on the
        # data being well-formed is not a proof.
        if membership_row.get("revoked_at"):
            state = "revoked"
        expires_at = membership_row.get("expires_at")
        if expires_at and now and str(now) >= str(expires_at):
            state = "expired"

        if state in DENYING_STATES:
            reasons.append(f"membership_state_denies:{state}")
        elif state not in ACTING_STATES:
            reasons.append("membership_state_not_acting")

        if msource in NEVER_MEMBERSHIP:
            reasons.append(f"membership_source_never_trusted:{msource}")
        elif msource not in TRUSTED_MEMBERSHIP_SOURCES:
            reasons.append(f"membership_source_not_trusted:{msource}")

        if rsource not in TRUSTED_ROLE_SOURCES:
            reasons.append(f"role_source_not_trusted:{rsource}")

        if role not in ALL_ROLES:
            reasons.append("role_not_recognised")
        elif role in NON_GRANTING_ROLES:
            reasons.append(f"role_grants_nothing:{role}")
        elif role in INTERNAL_ROLES:
            reasons.append("internal_role_cannot_hold_customer_authority")

        # Defence in depth behind RLS: if a row for a different organization
        # reached this code, the database boundary already failed. Say so loudly.
        # Gate 113: compared against the organization the lookup actually used.
        # This read `organization_profile_id` until the parameter split, which
        # would have compared every row against None once callers moved to the
        # correct name - the same stale-reference class of bug this gate fixed
        # in the query itself.
        row_org = membership_row.get("organization_id")
        if row_org is not None and str(row_org) != str(requested_organization_id):
            reasons.append("organization_mismatch")

        if not reasons and role in ALL_ROLES and role not in NON_GRANTING_ROLES:
            trusted_role = str(role)

    allowed = not reasons

    event_type = "tenant_access_denied"
    if not allowed and "organization_mismatch" in reasons:
        event_type = "cross_org_access_attempt"

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "allowed": allowed,
            "blocked_reasons": reasons,
            "issuer": issuer,
            "subject": subject,
            "organization_id": requested_organization_id,
            "organization_profile_id": organization_profile_id,
            "trusted_role": trusted_role,
            "identity_row_found": identity_row is not None,
            "membership_row_found": membership_row is not None,
            "membership_state": state,
            "membership_source": msource,
            "storage_backend_state": status["storage_backend_state"],
            "production_storage_live": status["production_storage_live"],
            "customer_persistence_claimed": status["customer_persistence_claimed"],
            # Storage and membership are not login. Gate 69 owns that claim.
            "customer_login_live": False,
            "audit_event": (
                None
                if allowed
                else _audit(
                    event_type,
                    subject=subject,
                    issuer=issuer,
                    organization_id=requested_organization_id,
                    reasons=reasons,
                    persisted=persisted,
                )
            ),
        }
    )


def resolution_invariant_failures(result: Mapping[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    if result.get("allowed"):
        if result.get("blocked_reasons"):
            fails.append("allowed_with_blocked_reasons")
        if not result.get("trusted_role"):
            fails.append("allowed_without_trusted_role")
        if not result.get("identity_row_found"):
            fails.append("allowed_without_identity_row")
        if not result.get("membership_row_found"):
            fails.append("allowed_without_membership_row")
        if result.get("membership_state") not in ACTING_STATES:
            fails.append("allowed_while_membership_not_active")
        if result.get("membership_source") not in TRUSTED_MEMBERSHIP_SOURCES:
            fails.append("allowed_from_untrusted_membership_source")
    else:
        if result.get("trusted_role"):
            fails.append("denied_but_role_returned")
        if not result.get("blocked_reasons"):
            fails.append("denied_without_reason")
        if result.get("audit_event") is None:
            fails.append("denied_without_audit_event")

    if result.get("customer_login_live") is not False:
        fails.append("forbidden_claim:customer_login_live")
    if result.get("customer_persistence_claimed") and not result.get(
        "production_storage_live"
    ):
        fails.append("persistence_claimed_without_live_storage")
    return fails
