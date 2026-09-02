"""Gate 138B: persistence measured by a round trip, not by five import checks.

## What the capability matrix could not tell you

`customer_persistence_capability_service` reads the models file, the migrations
and the import table. It has never written a row, and says so honestly:

```text
build_capability_matrix -> rows_written: 0, persisted: False   (constants)
```

So it answers *could this lane work* and reports it as `write_path_available`.
A lane with all five components and a broken INSERT would report the same
thing. This module answers *does it*, by doing it.

```text
write   a fixture-labelled row, through the lane's own repository
read    back by organization_id, through the lane's own anchored read
refuse  the same read for a different organization
archive it again, so the proof leaves no live row behind
```

Four steps, per lane, and a lane is round-trip-proved only if all four behave.
Anything less is reported as the step it got to.

## Why this does not need `customer_auth_live`

`CAPABILITY_REQUIRES_AUTH` is `True` for all nine lanes, and
`build_capability` folds it in as

```python
operational = write_path_available and (customer_auth_live or not required)
```

with the blocker named `no_customer_auth_so_nobody_owns_the_row`. That blocker
reaches for *somebody is accountable for this row* — and the repositories
underneath already draw the line in the right place:

```python
# awarded_grants_repository_service.prepare_award_write
demo_fixture = bool(is_demo) or validation["fact_status"] == "demo_fixture"
production_write = not demo_fixture
if production_write and not customer_auth_live:
    blocked_reasons.append("production_award_write_requires_live_customer_auth")
```

`production_write`, specifically. A fixture-labelled write into the demo
organization is not one, and needs neither `customer_auth_live` nor a verified
operational binding. The capability matrix's blanket requirement did not make
that distinction, so it reported every lane dead for a reason that applies only
to production writes.

Measured against the dev database, the fact the blocker actually wants:

```text
org_binding_passed           TRUE   an identity resolves to an organization
                                    through a membership row
callback_session_validated   TRUE   a real session was validated
role_mapping_passed          TRUE   the role comes from nf_org_memberships
```

Somebody is accountable. `customer_auth_live` is false because
`invite_binding_passed` is false, which is about how a *second* member was
authorized and says nothing about whether the first owns their own rows.

Same shape Gate 134F found one layer up, and the same remedy: ask for the fact
directly, and keep `customer_auth_live` a **sufficient** condition rather than a
necessary one. `or`, never replacement.

## Four separate claims, never collapsed

```text
repository_persistence_available   the lane's repository round-trips
route_persistence_available        a route reaches it with a session org
customer_persistence_live          controlled dev/demo, from a round trip
production_persistence_ready       needs customer_auth_live AND a verified
                                   operational binding. False, and stays so.
```

Five of six ready lanes have no routes. Repository-live is not
customer-usable, and this reports that per lane rather than averaging it into
one word.

## What it will not do

No object store is contacted and no document body is written — the document
lane records a reference and `object_store_configured` stays false. No live
grant source is called. No email. No real organization: the fixture label and
the demo classification are both required, and the real organization is refused
by name.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from typing import Any

import sqlalchemy as sa

from nativeforge.services import award_document_store_repository_service as _docs
from nativeforge.services import (
    award_requirement_proof_audit_repository_service as _proof,
)
from nativeforge.services import award_requirements_repository_service as _reqs
from nativeforge.services import awarded_grants_repository_service as _awards
from nativeforge.services import tenant_profile_repository_service as _profiles
from nativeforge.services.verified_operational_binding_activation_boundary_service import (  # noqa: E501
    REAL_ORGANIZATION_ID,
)

SCHEMA_VERSION = "nf_customer_persistence_activation_v1"

#: The scope this module can reach. One value, and it is in every result so a
#: reader never has to infer which kind of "live" is meant.
CONTROLLED_SCOPE = "controlled_dev_demo"

#: The fact_status every row this module writes carries. A fixture-labelled row
#: is not customer data, and this is what makes `production_write` false in
#: every repository underneath.
FIXTURE_FACT_STATUS = "demo_fixture"

#: Lanes, in the order the brief names them. The id is the capability matrix's
#: where one matches, so the two surfaces can be compared without a mapping
#: living in a reader's head.
LANES: tuple[str, ...] = (
    "tenant_profile_persistence",
    "awarded_grants_persistence",
    "award_requirements_persistence",
    "proof_audit_persistence",
    "document_library_persistence",
)

#: Which route module reaches each lane with a session-derived organization.
#: Absent means repository-live and route-missing, which is reported rather
#: than smoothed over.
LANE_ROUTES: dict[str, str | None] = {
    "tenant_profile_persistence": "api/tribal_profile_routes.py",
    "awarded_grants_persistence": None,
    "award_requirements_persistence": None,
    "proof_audit_persistence": None,
    "document_library_persistence": None,
}

#: Values that may never authorize a persistence write, however labelled.
FORBIDDEN_AUTHORITY_KEYS: tuple[str, ...] = (
    "tenant_id",
    "customer_org_id",
    "organization_profile_id",
    "profile_id",
    "subject",
    "email",
)

NO_ACCOUNTABLE_IDENTITY = "no_active_membership_identity_to_attribute_the_row_to"

NOT_DEMO = "organization_is_not_a_demo_organization"
REAL_ORG_REFUSED = "organization_is_the_explicitly_refused_real_org"
NOT_FIXTURE = "persistence_proof_must_be_fixture_labelled"
NO_PRINCIPAL = "no_accountable_principal_resolves_to_this_organization"

STEPS: tuple[str, ...] = ("write", "read", "cross_org_refused", "cleanup")


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _uuid_shaped(value: Any) -> bool:
    try:
        uuid.UUID(str(value or "").strip())
    except (ValueError, AttributeError, TypeError):
        return False
    return True


def resolve_accountable_identity(
    *, connection: Any = None, organization_id: Any = None
) -> str | None:
    """Which identity is accountable for a row in this organization?

    Read from `nf_org_memberships`, not supplied.

    Found by the live database refusing the first run:
    `created_by_identity_id` is a foreign key to `nf_identities`, and a
    synthetic id has no row to point at. The throwaway SQLite database had no
    such target table and accepted it, so the proof passed there and failed
    where it mattered.

    The constraint was right and so is what it forces: the principal
    accountable for the row is the identity the row should name. Deriving it
    also means the proof cannot run in an organization that has nobody in it.
    """
    if connection is None or not str(organization_id or "").strip():
        return None
    try:
        row = (
            connection.execute(
                sa.text(
                    "SELECT identity_id FROM nf_org_memberships "
                    "WHERE organization_id = :o AND state = 'active' "
                    "AND revoked_at IS NULL "
                    "ORDER BY CASE WHEN role = 'org_owner' THEN 0 ELSE 1 END, "
                    "created_at LIMIT 1"
                ),
                {"o": uuid.UUID(str(organization_id).strip()).hex},
            )
            .mappings()
            .first()
        )
    except Exception:
        return None
    if row is None:
        return None
    try:
        return str(uuid.UUID(str(row["identity_id"])))
    except (ValueError, AttributeError, TypeError):
        return None


def _fixture_ids(seed: str, lane: str) -> dict[str, uuid.UUID]:
    """Deterministic ids, so an artifact built from a run is byte-stable.

    Keyed on the LANE as well as the seed. The first version keyed on the seed
    alone, so every lane reused one award id - the awarded-grants lane wrote
    and archived it, then the requirements lane tried to insert the same
    primary key and the round trip died on an IntegrityError rather than
    reporting a step.

    Four of the five lanes hang off an award, so they each need their own.
    """
    namespace = uuid.UUID("00000000-0000-0000-0000-0000000138a0")
    return {
        name: uuid.uuid5(namespace, f"{seed}:{lane}:{name}")
        for name in ("profile", "award", "requirement", "proof_event", "document")
    }


# ---------------------------------------------------------------------------
# the accountable principal
# ---------------------------------------------------------------------------


def build_accountable_principal_evidence(
    *,
    connection: Any = None,
    binding_evidence: dict[str, Any] | None = None,
    role_mapping_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Is anybody accountable for a row in this deployment?

    The fact `no_customer_auth_so_nobody_owns_the_row` reaches for, asked
    directly. Derived from rows through Gate 132's and Gate 133's evidence
    services, both of which read `nf_identities` and `nf_org_memberships`.

    Both are injectable so the negative branch is reachable without emptying
    a database, and absent evidence means absent - false, not assumed.
    """
    binding = binding_evidence
    roles = role_mapping_evidence

    if connection is not None:
        if binding is None:
            from nativeforge.services.customer_auth_binding_evidence_service import (
                build_binding_evidence,
            )

            binding = build_binding_evidence(connection=connection)
        if roles is None:
            from nativeforge.services.customer_auth_role_mapping_evidence_service import (  # noqa: E501
                build_role_mapping_evidence,
            )

            roles = build_role_mapping_evidence(connection=connection)

    binding = binding or {}
    roles = roles or {}

    blocked: list[str] = []
    org_binding = bool(binding.get("org_binding_passed"))
    session_validated = bool(binding.get("callback_session_validated"))
    role_mapped = bool(roles.get("role_mapping_passed"))

    if not org_binding:
        blocked.append("no_identity_resolves_to_an_organization")
    if not session_validated:
        blocked.append("no_session_has_ever_been_validated")
    if not role_mapped:
        blocked.append("no_role_comes_from_a_membership_row")
    # Gate 133's two refusals, restated as requirements rather than assumed.
    if roles and roles.get("cookie_claim_can_override_membership"):
        blocked.append("a_cookie_claim_can_override_a_membership_row")
    if roles and roles.get("email_domain_can_map_a_role"):
        blocked.append("an_email_domain_can_map_a_role")

    accountable = bool(org_binding and session_validated and role_mapped)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "accountable_principal_available": accountable and not blocked,
            "org_binding_passed": org_binding,
            "callback_session_validated": session_validated,
            "role_mapping_passed": role_mapped,
            "role_mapping_source": roles.get("role_mapping_source"),
            "identity_rows": int(binding.get("identity_rows") or 0),
            "active_membership_rows": int(binding.get("active_membership_rows") or 0),
            "evidence_supplied": bool(binding or roles),
            # Named so nobody reads this as the broader claim.
            "customer_auth_live": False,
            "is_not_customer_auth_live": True,
            "blocked_reasons": sorted(set(blocked)),
        }
    )


# ---------------------------------------------------------------------------
# one lane, four steps
# ---------------------------------------------------------------------------


def _lane_round_trip(
    lane: str,
    *,
    connection: Any,
    organization_id: str,
    other_organization_id: str,
    identity_id: str,
    ids: dict[str, uuid.UUID],
    now: datetime,
) -> dict[str, Any]:
    """Write, read, refuse a cross-org read, archive. Per lane, in that order."""
    # `fact_status` is a single column on the four award lanes and does not
    # exist on the profile lane, which carries a fact status per field instead
    # (`recognition_status_fact_status`, and three more). One dict for both
    # lanes raised TypeError on the first run - the labelling is the same
    # intent expressed by two different schemas, and pretending otherwise
    # would have meant adding a parameter to a repository to suit this module.
    fixture = {"fact_status": FIXTURE_FACT_STATUS, "is_demo": True}
    profile_fixture = {"is_demo": True}
    steps: dict[str, Any] = dict.fromkeys(STEPS, False)
    blocked: list[str] = []
    rows_written = rows_read = cross_org_rows = rows_archived = 0
    scaffold_written = scaffold_archived = 0
    this_row_read = False

    def note(result: dict[str, Any], prefix: str) -> None:
        blocked.extend(f"{prefix}:{r}" for r in result.get("blocked_reasons") or [])

    if lane == "tenant_profile_persistence":
        wrote = _profiles.upsert_tenant_profile(
            connection=connection,
            profile_id=ids["profile"],
            now=now,
            organization_id=organization_id,
            tenant_id_label="nf-gate138-fixture-tenant",
            customer_org_id_label="nf-gate138-fixture-customer",
            recognition_status="federally_recognized",
            recognition_status_fact_status=FIXTURE_FACT_STATUS,
            operating_states=["NM"],
            operating_states_fact_status=FIXTURE_FACT_STATUS,
            applicant_classes=["federally_recognized_tribe"],
            applicant_classes_fact_status=FIXTURE_FACT_STATUS,
            digest_frequency="none",
            profile_status="active",
            created_by_identity_id=identity_id,
            **profile_fixture,
        )
        note(wrote, "write")
        rows_written = int(wrote.get("rows_written") or 0)
        read = _profiles.list_tenant_profiles(
            connection=connection, organization_id=organization_id
        )
        cross = _profiles.list_tenant_profiles(
            connection=connection, organization_id=other_organization_id
        )
        rows_read = int(read.get("rows_read") or 0)
        cross_org_rows = int(cross.get("rows_read") or 0)
        # Before the archive. Three lanes read `include_archived=False` by
        # default, so asking after cleanup found nothing and the step failed
        # for a row that had round-tripped perfectly well.
        this_row_read = bool(rows_written) and _read_back_this_row(
            lane,
            connection=connection,
            organization_id=organization_id,
            ids=ids,
        )
        if rows_written:
            cleaned = _profiles.archive_tenant_profile(
                connection=connection, organization_id=organization_id, now=now
            )
            rows_archived = int(cleaned.get("rows_written") or 0)

    elif lane in {
        "awarded_grants_persistence",
        "award_requirements_persistence",
        "proof_audit_persistence",
        "document_library_persistence",
    }:
        # Every one of these hangs off an award, so the award is written first
        # and archived last whichever lane is under test. The rows the lane
        # does not own are its scaffolding, and are reported separately.
        award = _awards.create_awarded_grant(
            connection=connection,
            award_id=ids["award"],
            now=now,
            organization_id=organization_id,
            award_number=f"NF-G138-{lane[:12].upper()}",
            award_title="Gate 138 fixture award",
            funder_name="Gate 138 fixture funder",
            award_status="active_award",
            award_amount="1000.00",
            award_currency="USD",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 12, 31),
            awarded_at=date(2026, 1, 1),
            active_obligation_status="no_obligations_established",
            requirements_extraction_status="not_attempted",
            created_by_identity_id=identity_id,
            **fixture,
        )
        scaffolding = [("award", award)]

        if lane == "awarded_grants_persistence":
            note(award, "write")
            rows_written = int(award.get("rows_written") or 0)
            read = _awards.list_awarded_grants(
                connection=connection, organization_id=organization_id
            )
            cross = _awards.list_awarded_grants(
                connection=connection, organization_id=other_organization_id
            )
            scaffolding = []
        else:
            requirement = _reqs.create_award_requirement(
                connection=connection,
                requirement_id=ids["requirement"],
                now=now,
                organization_id=organization_id,
                awarded_grant_id=str(ids["award"]),
                requirement_type="financial_report",
                requirement_title="Gate 138 fixture requirement",
                requirement_status="not_started",
                requirement_source="human_entered",
                requirement_due_date=date(2026, 6, 30),
                due_date_status="verified",
                proof_status="not_submitted",
                submission_status="not_submitted",
                recurrence_rule="one_time",
                created_by_identity_id=identity_id,
                **fixture,
            )
            if lane == "award_requirements_persistence":
                note(requirement, "write")
                rows_written = int(requirement.get("rows_written") or 0)
                read = _reqs.list_requirements_for_organization(
                    connection=connection, organization_id=organization_id
                )
                cross = _reqs.list_requirements_for_organization(
                    connection=connection, organization_id=other_organization_id
                )
            elif lane == "proof_audit_persistence":
                scaffolding.append(("requirement", requirement))
                event = _proof.create_proof_event(
                    connection=connection,
                    event_id=ids["proof_event"],
                    now=now,
                    organization_id=organization_id,
                    award_requirement_id=str(ids["requirement"]),
                    awarded_grant_id=str(ids["award"]),
                    event_type="mark_submitted",
                    event_status="not_submitted",
                    proof_summary="Gate 138 fixture proof event",
                    proof_source="human_entered",
                    created_by_identity_id=identity_id,
                    **fixture,
                )
                note(event, "write")
                rows_written = int(event.get("rows_written") or 0)
                read = _proof.list_proof_events_for_organization(
                    connection=connection, organization_id=organization_id
                )
                cross = _proof.list_proof_events_for_organization(
                    connection=connection, organization_id=other_organization_id
                )
            else:
                scaffolding.append(("requirement", requirement))
                document = _docs.create_award_document(
                    connection=connection,
                    document_id=ids["document"],
                    now=now,
                    organization_id=organization_id,
                    awarded_grant_id=str(ids["award"]),
                    document_kind="financial_report",
                    # A reference, never a body. `object_store_configured`
                    # stays false and no bytes are read or written.
                    document_status="reference_recorded",
                    document_title="Gate 138 fixture document reference",
                    document_source="human_entered",
                    retention_class="retain_7_days",
                    created_by_identity_id=identity_id,
                    **fixture,
                )
                note(document, "write")
                rows_written = int(document.get("rows_written") or 0)
                read = _docs.list_documents_for_organization(
                    connection=connection, organization_id=organization_id
                )
                cross = _docs.list_documents_for_organization(
                    connection=connection, organization_id=other_organization_id
                )

        rows_read = int(read.get("rows_read") or 0)
        cross_org_rows = int(cross.get("rows_read") or 0)
        this_row_read = bool(rows_written) and _read_back_this_row(
            lane,
            connection=connection,
            organization_id=organization_id,
            ids=ids,
        )

        # -- cleanup, in reverse dependency order ---------------------------
        #
        # The lane's own row AND its scaffolding. The first version archived
        # only the lane's row, and the live-database count check found three
        # awards and two requirements left live afterwards - the scaffolding
        # each dependent lane had written to hang its row off.
        #
        # A proof that leaves rows behind is not a clean proof, and the
        # invariant that was supposed to catch it compared totals rather than
        # rows, so five leftovers summed to "some were archived" and passed.
        if rows_written:
            rows_archived = _archive_award_lane(
                lane,
                connection=connection,
                organization_id=organization_id,
                ids=ids,
                now=now,
            )
        for label, result in scaffolding:
            note(result, f"scaffold_{label}")
            if result.get("rows_written"):
                scaffold_written += int(result["rows_written"])
                scaffold_archived += _archive_scaffold(
                    label,
                    connection=connection,
                    organization_id=organization_id,
                    ids=ids,
                    now=now,
                )
    else:  # pragma: no cover - LANES is closed
        blocked.append(f"lane_not_recognised:{lane}")
        read = cross = {}

    steps["write"] = rows_written == 1
    steps["read"] = this_row_read
    steps["cross_org_refused"] = cross_org_rows == 0
    # Every row this lane wrote, including the scaffolding it needed.
    steps["cleanup"] = bool(
        rows_archived >= 1 and scaffold_archived == scaffold_written
    )

    proved = all(steps.values())
    if not proved:
        blocked.extend(f"step_failed:{name}" for name, ok in steps.items() if not ok)

    return _json_safe(
        {
            "lane": lane,
            "round_trip_proved": proved,
            "steps": dict(steps),
            "rows_written": rows_written,
            "rows_read": rows_read,
            "this_row_read_back_by_id": this_row_read,
            "cross_org_rows_read": cross_org_rows,
            "rows_archived": rows_archived,
            "scaffold_rows_written": scaffold_written,
            "scaffold_rows_archived": scaffold_archived,
            "fact_status": FIXTURE_FACT_STATUS,
            "route_module": LANE_ROUTES.get(lane),
            "route_persistence_available": bool(LANE_ROUTES.get(lane)),
            "object_store_contacted": False,
            "document_body_written": False,
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def _read_back_this_row(
    lane: str,
    *,
    connection: Any,
    organization_id: str,
    ids: dict[str, uuid.UUID],
) -> bool:
    """Did the row THIS run wrote come back, anchored on the organization?

    The list-based read step was `rows_read >= 1`, which is a count. Against a
    live database carrying archived rows from earlier runs it read 15 for five
    writes and still passed - so it was proving that the table had rows, not
    that this row round-tripped.

    These are the id-specific reads, and every one of them is anchored on
    `organization_id` as well, so a hit is both the right row and the right
    organization.
    """
    if lane == "tenant_profile_persistence":
        got = _profiles.get_tenant_profile(
            connection=connection, organization_id=organization_id
        )
        # The profile lane is one-live-per-organization, so the anchored read
        # is already specific and there is no id to pass.
        return bool(got.get("rows_read"))
    if lane == "awarded_grants_persistence":
        got = _awards.get_awarded_grant(
            connection=connection,
            organization_id=organization_id,
            award_id=str(ids["award"]),
        )
    elif lane == "award_requirements_persistence":
        got = _reqs.get_award_requirement(
            connection=connection,
            organization_id=organization_id,
            requirement_id=str(ids["requirement"]),
        )
    elif lane == "proof_audit_persistence":
        got = _proof.get_proof_event(
            connection=connection,
            organization_id=organization_id,
            event_id=str(ids["proof_event"]),
        )
    elif lane == "document_library_persistence":
        got = _docs.get_award_document(
            connection=connection,
            organization_id=organization_id,
            document_id=str(ids["document"]),
        )
    else:  # pragma: no cover - LANES is closed
        return False
    return bool(got.get("rows_read"))


def _archive_scaffold(
    label: str,
    *,
    connection: Any,
    organization_id: str,
    ids: dict[str, uuid.UUID],
    now: datetime,
) -> int:
    """Archive a row a lane wrote only so it had something to hang off."""
    if label == "award":
        result = _awards.archive_awarded_grant(
            connection=connection,
            organization_id=organization_id,
            award_id=str(ids["award"]),
            now=now,
        )
    elif label == "requirement":
        result = _reqs.archive_award_requirement(
            connection=connection,
            organization_id=organization_id,
            requirement_id=str(ids["requirement"]),
            now=now,
        )
    else:  # pragma: no cover - scaffolding is one of two things
        return 0
    return int(result.get("rows_written") or 0)


def _archive_award_lane(
    lane: str,
    *,
    connection: Any,
    organization_id: str,
    ids: dict[str, uuid.UUID],
    now: datetime,
) -> int:
    """Archive the row the lane owns. Archival, because there is no delete.

    These are audit surfaces. Adding a hard delete for a smoke test's
    convenience would be the wrong primitive to introduce, so the proof leaves
    an archived row rather than no row - which is the brief's "mark it as a
    test artifact" branch, chosen because the repositories only offer that one.
    """
    if lane == "awarded_grants_persistence":
        result = _awards.archive_awarded_grant(
            connection=connection,
            organization_id=organization_id,
            award_id=str(ids["award"]),
            now=now,
        )
    elif lane == "award_requirements_persistence":
        result = _reqs.archive_award_requirement(
            connection=connection,
            organization_id=organization_id,
            requirement_id=str(ids["requirement"]),
            now=now,
        )
    elif lane == "proof_audit_persistence":
        result = _proof.archive_proof_event(
            connection=connection,
            organization_id=organization_id,
            event_id=str(ids["proof_event"]),
            now=now,
        )
    else:
        result = _docs.archive_award_document(
            connection=connection,
            organization_id=organization_id,
            document_id=str(ids["document"]),
            now=now,
        )
    return int(result.get("rows_written") or 0)


# ---------------------------------------------------------------------------
# every lane, and the roll-up
# ---------------------------------------------------------------------------


def prove_customer_persistence(
    *,
    connection: Any = None,
    organization_id: Any = None,
    other_organization_id: str = "cccccccc-dddd-eeee-ffff-00000000d138",
    identity_id: Any = None,
    lanes: tuple[str, ...] = LANES,
    now: datetime | None = None,
    seed: str | None = None,
    binding_evidence: dict[str, Any] | None = None,
    role_mapping_evidence: dict[str, Any] | None = None,
    org_type_in_database: str | None = None,
    **offered: Any,
) -> dict[str, Any]:
    """Drive the round trip for every lane and report what each one proved."""
    moment = now or datetime.now(UTC)
    requested = str(organization_id or "").strip().lower()
    blocked: list[str] = []

    # A fresh seed per run by default, and a fixed one only when a caller asks.
    #
    # The ids are derived from the seed so an artifact built from one run is
    # byte-stable. Defaulting the seed to a constant made the live smoke
    # un-re-runnable: the second run collided with the first run's ARCHIVED row
    # on the primary key and died on an IntegrityError.
    #
    # Determinism belongs to the artifact, which runs against a database it
    # builds and throws away. A proof against a live database has to be
    # runnable twice.
    run_seed = str(seed) if seed else f"gate138-{uuid.uuid4().hex[:16]}"

    # -- 1. a label is never authority --------------------------------------
    for key in FORBIDDEN_AUTHORITY_KEYS:
        if str(offered.get(key) or "").strip():
            blocked.append(f"not_an_authority_for_persistence:{key}")

    if not requested:
        blocked.append("persistence_without_an_organization_id_anchor")
    elif not _uuid_shaped(requested):
        blocked.append("organization_id_anchor_is_not_uuid_shaped")
    if requested == REAL_ORGANIZATION_ID:
        blocked.append(REAL_ORG_REFUSED)

    # -- 2. demo, derived from the row --------------------------------------
    from nativeforge.services.demo_org_classification_service import (
        classify_organization,
    )

    classification = classify_organization(
        requested or None,
        connection=connection,
        org_type_in_database=org_type_in_database,
    )
    classified = bool(classification.get("classification_available"))
    is_demo = bool(classification.get("is_demo"))
    if not classified:
        blocked.append("organization_could_not_be_classified")
    elif not is_demo:
        # Controlled dev/demo means demo. A real organization's persistence is
        # a production write and needs the two gates that are still false.
        blocked.append(NOT_DEMO)

    # -- 3. somebody is accountable -----------------------------------------
    principal = build_accountable_principal_evidence(
        connection=connection,
        binding_evidence=binding_evidence,
        role_mapping_evidence=role_mapping_evidence,
    )
    accountable = bool(principal["accountable_principal_available"])
    if not accountable:
        blocked.append(NO_PRINCIPAL)
        blocked.extend(f"principal:{r}" for r in principal["blocked_reasons"])

    # Derived from the membership row. Supplied only so a hermetic test can
    # reach the branch without building a memberships table.
    identity = str(identity_id or "").strip() or (
        resolve_accountable_identity(  # noqa: E501
            connection=connection, organization_id=requested or None
        )
        or ""
    )
    if not identity:
        blocked.append(NO_ACCOUNTABLE_IDENTITY)

    # -- 4. the round trips --------------------------------------------------
    results: list[dict[str, Any]] = []
    if not blocked and connection is not None:
        for lane in lanes:
            results.append(
                _lane_round_trip(
                    lane,
                    connection=connection,
                    organization_id=requested,
                    other_organization_id=other_organization_id,
                    identity_id=identity,
                    ids=_fixture_ids(run_seed, lane),
                    now=moment,
                )
            )
    elif connection is None:
        blocked.append("no_connection_supplied_so_nothing_was_proved")

    proved = [r for r in results if r["round_trip_proved"]]
    repository_live = sorted(r["lane"] for r in proved)
    route_live = sorted(r["lane"] for r in proved if r["route_persistence_available"])
    lane_blocked = sorted(r["lane"] for r in results if not r["round_trip_proved"])

    live = bool(proved and not blocked)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "customer_persistence_live": live,
            "scope": CONTROLLED_SCOPE if live else "none",
            "organization_id": requested or None,
            "organization_is_demo": is_demo,
            "organization_classified": classified,
            "accountable_principal_available": accountable,
            "accountable_principal_evidence": principal,
            "accountable_identity_resolved": bool(identity),
            "accountable_identity_source": "nf_org_memberships",
            "lanes_tested": list(lanes),
            "lanes_round_trip_proved": repository_live,
            "repository_persistence_live_lanes": repository_live,
            "route_persistence_live_lanes": route_live,
            "route_missing_lanes": sorted(
                r["lane"] for r in results if not r["route_persistence_available"]
            ),
            "blocked_lanes": lane_blocked,
            "lane_results": results,
            "rows_written": sum(r["rows_written"] for r in results),
            "rows_read": sum(r["rows_read"] for r in results),
            "cross_org_rows_read": sum(r["cross_org_rows_read"] for r in results),
            "rows_archived": sum(r["rows_archived"] for r in results),
            "scaffold_rows_written": sum(
                r.get("scaffold_rows_written", 0) for r in results
            ),
            "scaffold_rows_archived": sum(
                r.get("scaffold_rows_archived", 0) for r in results
            ),
            "rows_left_live": sum(
                (r["rows_written"] - r["rows_archived"])
                + (
                    r.get("scaffold_rows_written", 0)
                    - r.get("scaffold_rows_archived", 0)
                )
                for r in results
            ),
            "fact_status_written": FIXTURE_FACT_STATUS,
            "seed_fixed_by_caller": bool(seed),
            # Constants. Everything this module refuses to become.
            "customer_auth_live": False,
            "production_persistence_ready": False,
            "production_rows_written": 0,
            "real_customer_data_written": False,
            "real_organization_touched": False,
            "object_store_contacted": False,
            "object_store_configured": False,
            "document_bodies_written": 0,
            "live_grant_sources_called": False,
            "collectors_activated": False,
            "email_sent": False,
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def persistence_activation_invariant_failures(result: dict[str, Any]) -> list[str]:
    """What must never be true of a persistence proof."""
    fails: list[str] = []

    if result.get("customer_persistence_live"):
        if result.get("scope") != CONTROLLED_SCOPE:
            fails.append(f"persistence_live_outside_scope:{result.get('scope')}")
        if not result.get("organization_is_demo"):
            fails.append("persistence_live_for_a_non_demo_organization")
        if result.get("organization_id") == REAL_ORGANIZATION_ID:
            fails.append("persistence_live_for_the_refused_real_org")
        if not result.get("accountable_principal_available"):
            fails.append("persistence_live_without_an_accountable_principal")
        if "accountable_identity_resolved" in result and not result.get(
            "accountable_identity_resolved"
        ):
            fails.append("persistence_live_without_an_identity_to_attribute_rows_to")
        if not result.get("lanes_round_trip_proved"):
            fails.append("persistence_live_without_a_proved_round_trip")
        if not result.get("rows_written"):
            fails.append("persistence_live_without_writing_a_row")
        if not result.get("rows_read"):
            fails.append("persistence_live_without_reading_one_back")
        if not all(
            lane.get("this_row_read_back_by_id")
            for lane in result.get("lane_results") or []
        ):
            fails.append("persistence_live_without_reading_the_written_row_by_id")
        if result.get("blocked_reasons"):
            fails.append("persistence_live_alongside_blockers")

    if result.get("cross_org_rows_read"):
        fails.append("a_cross_organization_read_returned_rows")

    if result.get("fact_status_written") != FIXTURE_FACT_STATUS:
        fails.append(f"fact_status_changed:{result.get('fact_status_written')}")

    for field in (
        "customer_auth_live",
        "production_persistence_ready",
        "real_customer_data_written",
        "real_organization_touched",
        "object_store_contacted",
        "object_store_configured",
        "live_grant_sources_called",
        "collectors_activated",
        "email_sent",
    ):
        if result.get(field):
            fails.append(f"claimed:{field}")
    for field in ("production_rows_written", "document_bodies_written"):
        if result.get(field):
            fails.append(f"nonzero:{field}")

    # Per-row, not per-total. The first version compared `rows_written` to
    # `rows_archived` and read five leftovers as "some were archived".
    if result.get("rows_left_live"):
        fails.append(f"rows_left_live_after_the_proof:{result.get('rows_left_live')}")
    if result.get("rows_written") and not result.get("rows_archived"):
        fails.append("rows_were_written_and_none_were_cleaned_up")

    if not result.get("customer_persistence_live") and not result.get(
        "blocked_reasons"
    ):
        fails.append("nothing_proved_and_nothing_blocked_it")

    return fails
