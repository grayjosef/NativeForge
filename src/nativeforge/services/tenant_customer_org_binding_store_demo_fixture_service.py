"""Binding store demo fixtures (Gate 113G).

Nine labelled cases, one per outcome the binding store must reach.

## Six refusals, three storable rows, one operational binding

```text
                                    stored  operational
verified_binding_with_verifier        yes       yes
verified_binding_without_verifier      no        no   "verified" as assertion
tenant_id_as_anchor                    no        no   a label as the authority
customer_org_id_as_anchor              no        no   the other label
organization_profile_id_as_anchor      no        no   a real id, wrong space
demo_fixture_binding                  yes        no   demo scope, never product
demo_anchor_value                      no        no   a demo cannot anchor
conflict_binding                       no        no   two claims on one label
revoked_binding                       yes        no   withdrawn, kept on record
```

**Stored and operational are not the same column, and this fixture set exists
largely to keep them apart.** A revoked binding is stored precisely so the
withdrawal is on the record; a demo binding is stored inside the demo scope. Two
rows the table will happily hold, neither of which authorises anything. A single
`accepted` boolean would have blurred exactly the distinction that matters, and
the first version of this file did.

The three anchor cases are worth reading together. All three supply a non-null
organization-ish identifier, all three are refused, and only one of them looks
wrong at a glance. `organization_profile_id` is a real column on a real table
holding a real value — it is simply not the column RLS enforces on, and a store
that accepted it would write rows no policy could see.

## The operational case is a fixture, not evidence

`verified_binding_with_verifier` is the one case that reaches an operational
posture, so the matrix can demonstrate that acceptance is reachable at all — a
store that refuses everything is a constant, not a contract. It is labelled
`demo_fixture` and reports `customer_persistence_live: false`.

Stated plainly, as in Gates 111 and 112: it shows what a verified binding
*would* be permitted to do. It is not evidence that any verified binding
exists, no row was written, and nobody authenticated to produce it.

## Nothing here is stored

`build_binding_record` computes a decision about a record. It does not insert
one, the table created by revision 0029 is empty, and every fixture reports
`rows_written: 0`. The organization UUIDs correspond to no organization
anywhere and the tenant and customer labels are invented.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.tenant_customer_org_binding_store_service import (
    build_binding_record,
    read_bindings_for_organization,
    revoke_binding,
)
from nativeforge.services.tenant_customer_org_identity_binding_service import (
    DEMO_LABEL,
)

SCHEMA_VERSION = "nf_tenant_customer_org_binding_store_demo_fixture_v1"

FIXTURE_LABEL = "demo_fixture"

# Invented. These UUIDs are valid in shape and correspond to no organization.
DEMO_ORGANIZATION_ID = "00000000-0000-4000-8000-000000000113"
DEMO_OTHER_ORGANIZATION_ID = "00000000-0000-4000-8000-000000000114"
DEMO_VERIFIER_IDENTITY_ID = "00000000-0000-4000-8000-0000000001b1"

# A demo-shaped organization value, to prove a demo identity cannot anchor.
DEMO_ANCHOR_VALUE = "nf-demo-org-113"

# Labels. Not identities, not foreign keys, not anchors.
DEMO_TENANT_ID = "nf-demo-tenant-113"
DEMO_CUSTOMER_ORG_ID = "nf-demo-customer-org-113"
DEMO_PROFILE_ID = "nf-demo-org-profile-113"

DEMO_VERIFIED_AT = "2026-08-29T00:00:00Z"

# Every outcome the store must be able to reach. A fixture set missing one of
# these leaves a branch of the store undemonstrated, which is how an unreachable
# refusal survives review.
REQUIRED_STORE_CASES: frozenset[str] = frozenset(
    {
        "verified_binding_with_verifier",
        "verified_binding_without_verifier",
        "tenant_id_as_anchor",
        "customer_org_id_as_anchor",
        "organization_profile_id_as_anchor",
        "demo_fixture_binding",
        "demo_anchor_value",
        "conflict_binding",
        "revoked_binding",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_demo_store_cases() -> list[dict[str, Any]]:
    """Nine labelled cases, each stating both permissions it expects.

    Two expectations rather than one, because the store grants two things and a
    case that only names ``storage_allowed`` cannot catch a revoked binding that
    started being writable again.
    """
    return [
        {
            "case": "verified_binding_with_verifier",
            "fixture_label": FIXTURE_LABEL,
            "why": (
                "the only shape the store accepts: anchored on organization_id, "
                "verified by a named identity at a named time"
            ),
            "expect_storage_allowed": True,
            "expect_write_allowed": True,
            "record": {
                "organization_id": DEMO_ORGANIZATION_ID,
                "tenant_id": DEMO_TENANT_ID,
                "customer_org_id": DEMO_CUSTOMER_ORG_ID,
                "binding_status": "verified_binding",
                "binding_source": "admin_verified",
                "verified_by_identity_id": DEMO_VERIFIER_IDENTITY_ID,
                "verified_at": DEMO_VERIFIED_AT,
            },
        },
        {
            "case": "verified_binding_without_verifier",
            "fixture_label": FIXTURE_LABEL,
            "why": (
                "the word verified with nobody behind it - refused here and by "
                "ck_nf_binding_verified_needs_verifier in the schema"
            ),
            "expect_storage_allowed": False,
            "expect_write_allowed": False,
            "record": {
                "organization_id": DEMO_ORGANIZATION_ID,
                "tenant_id": DEMO_TENANT_ID,
                "customer_org_id": DEMO_CUSTOMER_ORG_ID,
                "binding_status": "verified_binding",
                "binding_source": "admin_verified",
            },
        },
        {
            "case": "tenant_id_as_anchor",
            "fixture_label": FIXTURE_LABEL,
            "why": "a tenant label cannot be the row's organization",
            "expect_storage_allowed": False,
            "expect_write_allowed": False,
            "record": {
                "tenant_id": DEMO_TENANT_ID,
                "customer_org_id": DEMO_CUSTOMER_ORG_ID,
                "binding_status": "verified_binding",
                "binding_source": "admin_verified",
                "verified_by_identity_id": DEMO_VERIFIER_IDENTITY_ID,
                "verified_at": DEMO_VERIFIED_AT,
            },
        },
        {
            "case": "customer_org_id_as_anchor",
            "fixture_label": FIXTURE_LABEL,
            "why": "a customer label cannot be the row's organization either",
            "expect_storage_allowed": False,
            "expect_write_allowed": False,
            "record": {
                "customer_org_id": DEMO_CUSTOMER_ORG_ID,
                "tenant_id": DEMO_TENANT_ID,
                "binding_status": "verified_binding",
                "binding_source": "admin_verified",
                "verified_by_identity_id": DEMO_VERIFIER_IDENTITY_ID,
                "verified_at": DEMO_VERIFIED_AT,
            },
        },
        {
            "case": "organization_profile_id_as_anchor",
            "fixture_label": FIXTURE_LABEL,
            "why": (
                "the near-miss: a real identifier from a real column, in the "
                "wrong identity space. RLS casts to ::uuid and this is not one"
            ),
            "expect_storage_allowed": False,
            "expect_write_allowed": False,
            "record": {
                "organization_profile_id": DEMO_PROFILE_ID,
                "tenant_id": DEMO_TENANT_ID,
                "customer_org_id": DEMO_CUSTOMER_ORG_ID,
                "binding_status": "verified_binding",
                "binding_source": "admin_verified",
                "verified_by_identity_id": DEMO_VERIFIER_IDENTITY_ID,
                "verified_at": DEMO_VERIFIED_AT,
            },
        },
        {
            "case": "demo_fixture_binding",
            "fixture_label": FIXTURE_LABEL,
            "why": (
                "a demo binding is not a small verified one; it carries no "
                "verifier and never becomes operational"
            ),
            "expect_storage_allowed": True,
            "expect_write_allowed": True,
            "record": {
                "organization_id": DEMO_ORGANIZATION_ID,
                "tenant_id": DEMO_TENANT_ID,
                "customer_org_id": DEMO_CUSTOMER_ORG_ID,
                "binding_status": "demo_fixture",
                "binding_source": "demo_fixture",
                "is_demo": True,
                "demo_label": DEMO_LABEL,
            },
        },
        {
            "case": "demo_anchor_value",
            "fixture_label": FIXTURE_LABEL,
            "why": "a demo organization value can anchor nothing, whatever the status",
            "expect_storage_allowed": False,
            "expect_write_allowed": False,
            "record": {
                "organization_id": DEMO_ANCHOR_VALUE,
                "tenant_id": DEMO_TENANT_ID,
                "customer_org_id": DEMO_CUSTOMER_ORG_ID,
                "binding_status": "verified_binding",
                "binding_source": "admin_verified",
                "verified_by_identity_id": DEMO_VERIFIER_IDENTITY_ID,
                "verified_at": DEMO_VERIFIED_AT,
            },
        },
        {
            "case": "conflict_binding",
            "fixture_label": FIXTURE_LABEL,
            "why": (
                "two organizations claiming one tenant label is a question for "
                "a person, not a row to write"
            ),
            "expect_storage_allowed": False,
            "expect_write_allowed": False,
            "record": {
                "organization_id": DEMO_OTHER_ORGANIZATION_ID,
                "tenant_id": DEMO_TENANT_ID,
                "customer_org_id": DEMO_CUSTOMER_ORG_ID,
                "binding_status": "conflict",
                "binding_source": "human_entered",
            },
        },
        {
            "case": "revoked_binding",
            "fixture_label": FIXTURE_LABEL,
            "why": (
                "a withdrawn relationship stops authorising anything, and the "
                "row survives for the audit trail"
            ),
            "expect_storage_allowed": True,
            "expect_write_allowed": False,
            "record": {
                "organization_id": DEMO_ORGANIZATION_ID,
                "tenant_id": DEMO_TENANT_ID,
                "customer_org_id": DEMO_CUSTOMER_ORG_ID,
                "binding_status": "revoked",
                "binding_source": "admin_verified",
                "revoked_at": DEMO_VERIFIED_AT,
                "revoked_by_identity_id": DEMO_VERIFIER_IDENTITY_ID,
            },
        },
    ]


def measure_store_cases(cases: list[dict[str, Any]]) -> set[str]:
    """Which cases the supplied set demonstrates.

    Takes its input rather than reading the module's own list, so a test can
    hand it a set with a case removed and observe the coverage gap.
    """
    return {str(c.get("case")) for c in cases if c.get("case")}


def build_store_demo_fixture_set() -> dict[str, Any]:
    """The nine cases, each run through the store, plus a revoke and a read."""
    cases = build_demo_store_cases()
    covered = measure_store_cases(cases)

    rows: list[dict[str, Any]] = []
    for case in cases:
        record = build_binding_record(**case["record"])
        rows.append(
            {
                "case": case["case"],
                "fixture_label": FIXTURE_LABEL,
                "expect_storage_allowed": case["expect_storage_allowed"],
                "expect_write_allowed": case["expect_write_allowed"],
                "storage_allowed": record["storage_allowed"],
                "write_allowed": record["write_allowed"],
                "read_allowed": record["read_allowed"],
                "binding_status": record["binding_status"],
                "is_demo": record["is_demo"],
                "rls_anchor": record["rls_anchor"],
                "organization_id_shape": record["organization_id_shape"],
                "human_review_required": record["human_review_required"],
                "blocked_reasons": record["blocked_reasons"],
                # A row that can carry an operational customer binding: stored,
                # writable, verified, and not a demo. Three of these cases are
                # storable and only one of them is that.
                "operational": bool(
                    record["storage_allowed"]
                    and record["write_allowed"]
                    and record["binding_status"] == "verified_binding"
                    and not record["is_demo"]
                ),
                "agrees_with_expectation": (
                    bool(record["storage_allowed"])
                    is bool(case["expect_storage_allowed"])
                    and bool(record["write_allowed"])
                    is bool(case["expect_write_allowed"])
                ),
            }
        )

    # Revocation preserves history rather than deleting it. Demonstrated on the
    # one record the store accepted.
    accepted = build_binding_record(**cases[0]["record"])
    revoked = revoke_binding(
        record=accepted,
        revoked_by_identity_id=DEMO_VERIFIER_IDENTITY_ID,
        revoked_at=DEMO_VERIFIED_AT,
    )

    # A read anchored on the authority, and one anchored on a profile id.
    permitted_read = read_bindings_for_organization(
        organization_id=DEMO_ORGANIZATION_ID
    )
    refused_read = read_bindings_for_organization(organization_id=DEMO_PROFILE_ID)

    disagreements = [r["case"] for r in rows if not r["agrees_with_expectation"]]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixture_label": FIXTURE_LABEL,
            "demo_organization_id": DEMO_ORGANIZATION_ID,
            "demo_tenant_id": DEMO_TENANT_ID,
            "demo_customer_org_id": DEMO_CUSTOMER_ORG_ID,
            "demo_profile_id": DEMO_PROFILE_ID,
            "cases": cases,
            "case_count": len(cases),
            "rows": rows,
            "store_cases_covered": sorted(covered),
            "store_cases_missing": sorted(REQUIRED_STORE_CASES - covered),
            "cases_disagreeing_with_expectation": disagreements,
            "storable_case_count": sum(1 for r in rows if r["storage_allowed"]),
            "refused_case_count": sum(1 for r in rows if not r["storage_allowed"]),
            "operational_case_count": sum(1 for r in rows if r["operational"]),
            "revocation": {
                "revoked_status": revoked["binding_status"],
                "rows_deleted": revoked["rows_deleted"],
                "history_preserved": revoked["history_preserved"],
            },
            "permitted_read_allowed": permitted_read["read_allowed"],
            "refused_read_allowed": refused_read["read_allowed"],
            "refused_read_reasons": refused_read["blocked_reasons"],
            # Constants: invented labels, no verifier, no row, no database.
            "customer_persistence_live": False,
            "customer_auth_live": False,
            "real_customer_data": False,
            "rows_written": 0,
            "persisted": False,
            "identities_assumed_equivalent": False,
            "fabricated": False,
            "live_fetch_performed": False,
        }
    )


def store_demo_invariant_failures(fixture: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if fixture.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for constant in (
        "customer_persistence_live",
        "customer_auth_live",
        "real_customer_data",
        "persisted",
        "identities_assumed_equivalent",
        "fabricated",
        "live_fetch_performed",
    ):
        if fixture.get(constant) is not False:
            fails.append(f"store_demo_claimed:{constant}")

    if fixture.get("rows_written") != 0:
        fails.append("store_demo_wrote_rows")

    if fixture.get("fixture_label") != FIXTURE_LABEL:
        fails.append("fixture_set_not_labelled")

    for case in fixture.get("cases") or []:
        if case.get("fixture_label") != FIXTURE_LABEL:
            fails.append(f"unlabelled_demo_case:{case.get('case')}")

    for case in fixture.get("store_cases_missing") or []:
        fails.append(f"store_case_not_covered:{case}")

    # The store's behaviour must match what each case says it expects. A fixture
    # set that quietly tolerates a changed answer proves nothing.
    for case in fixture.get("cases_disagreeing_with_expectation") or []:
        fails.append(f"store_disagreed_with_the_fixture:{case}")

    rows = fixture.get("rows") or []

    # Exactly one case may reach an operational posture. Zero would make
    # acceptance unreachable and every refusal meaningless; more than one means
    # a demo or revoked row started carrying authority it must never carry.
    #
    # Storable is a weaker and larger set on purpose: a revoked binding is
    # stored precisely so the withdrawal is on the record, and a demo binding is
    # stored inside the demo scope. Neither is operational.
    if fixture.get("operational_case_count") != 1:
        fails.append("store_demo_operational_case_count_is_not_one")

    if not fixture.get("storable_case_count"):
        fails.append("store_demo_stores_nothing_at_all")

    for row in rows:
        anchor_shape = row.get("organization_id_shape")

        # Nothing but the authority column may ever be the anchor.
        if row.get("rls_anchor") not in {"organization_id", None}:
            fails.append(f"demo_row_anchored_on_a_label:{row.get('case')}")

        # Any stored row is anchored on a real UUID.
        if row.get("storage_allowed"):
            if anchor_shape != "uuid":
                fails.append(f"accepted_row_without_a_uuid_anchor:{row.get('case')}")
            if row.get("blocked_reasons"):
                fails.append(f"accepted_row_with_blocked_reasons:{row.get('case')}")

        # An operational row is verified and is not a demo. This is the conjunct
        # that keeps a demo fixture from becoming a customer binding by being
        # stored in the same table.
        if row.get("operational"):
            if row.get("binding_status") != "verified_binding":
                fails.append(f"operational_row_that_is_not_verified:{row.get('case')}")
            if row.get("is_demo"):
                fails.append(f"operational_row_that_is_a_demo:{row.get('case')}")

        # A revoked binding is storable and never writable.
        if row.get("binding_status") == "revoked" and row.get("write_allowed"):
            fails.append(f"revoked_row_still_writable:{row.get('case')}")

        # A demo binding is never operational, however it was stored.
        if row.get("is_demo") and row.get("operational"):
            fails.append(f"demo_row_reported_operational:{row.get('case')}")

        # A refusal must name itself.
        if not row.get("storage_allowed") and not row.get("blocked_reasons"):
            fails.append(f"demo_row_refused_without_a_reason:{row.get('case')}")

        # A write never outruns storage permission.
        if row.get("write_allowed") and not row.get("storage_allowed"):
            fails.append(f"demo_row_write_without_storage:{row.get('case')}")

    # Revocation preserves the record.
    revocation = fixture.get("revocation") or {}
    if revocation.get("rows_deleted") != 0:
        fails.append("store_demo_revocation_deleted_rows")
    if not revocation.get("history_preserved"):
        fails.append("store_demo_revocation_lost_history")
    if revocation.get("revoked_status") != "revoked":
        fails.append("store_demo_revocation_left_the_status_unchanged")

    # A profile id may not read the store, and the refusal must be named.
    if fixture.get("refused_read_allowed"):
        fails.append("profile_id_permitted_a_store_read")
    if not fixture.get("refused_read_allowed") and not fixture.get(
        "refused_read_reasons"
    ):
        fails.append("store_read_refused_without_a_reason")

    return fails
