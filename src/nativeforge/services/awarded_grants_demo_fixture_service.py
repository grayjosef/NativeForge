"""Awarded Grants demo fixtures (Gate 108H).

Four labelled awards and nine requirements, built to demonstrate the contract's
**refusals** rather than a tidy happy path.

## Every case here is a case the system must decline to guess

```text
award 1  documented       verified dates, human-entered and evidence-extracted
award 2  unknown dates    obligations real, dates never established
award 3  unsupported      an award package nobody could read
award 4  projected only   a burden guessed from the notice, no award-specific
                          evidence - not an obligation
```

Plus one overdue requirement, one due soon, one closeout, and one proof of
submission labelled `demo_fixture` everywhere it appears.

## A fixed clock

`REFERENCE_NOW` is a constant. Overdue and due-soon are computed against it, so
the demo shows the same thing in March as in November and the artifacts are
byte-identical between runs. A demo that reads the wall clock stops
demonstrating overdue the week after it is built.

## No real Tribe, no real award

Tenant and award identifiers are invented and labelled. Nothing here is a real
award number, a real agency decision, or a real reporting requirement, and the
proof reference is a demo placeholder carrying its label rather than a
plausible-looking receipt id.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.award_requirement_model_service import (
    build_award_requirement,
)
from nativeforge.services.award_requirement_proof_audit_service import (
    DEMO_PROOF_LABEL,
    record_proof_action,
)
from nativeforge.services.award_requirements_calendar_service import (
    build_requirements_calendar,
)
from nativeforge.services.awarded_grant_record_service import (
    build_awarded_grant_record,
)

SCHEMA_VERSION = "nf_awarded_grants_demo_fixture_v1"

FIXTURE_LABEL = "demo_fixture"
DEMO_TENANT_ID = "nf-demo-tenant-01"
DEMO_CUSTOMER_ORG_ID = "nf-demo-org-01"

# Fixed clock. Overdue and due-soon are measured against this, never the wall.
REFERENCE_NOW = "2026-03-01"

# The cases the fixture set must demonstrate. Asserted by test, so a future edit
# that quietly drops one fails rather than silently narrowing the demo.
REQUIRED_DEMO_CASES: frozenset[str] = frozenset(
    {
        "documented_award",
        "unknown_due_dates",
        "unsupported_document_type",
        "projected_burden_only",
        "overdue_requirement",
        "due_soon_requirement",
        "closeout_requirement",
        "proof_of_submission",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _award(
    *,
    source_opportunity_id: str,
    award_number: str | None,
    title: str,
    agency: str,
    extraction: str,
    start: str | None = None,
    end: str | None = None,
    amount: Any = None,
    status: str = "active_award",
) -> dict[str, Any]:
    record = build_awarded_grant_record(
        tenant_id=DEMO_TENANT_ID,
        customer_org_id=DEMO_CUSTOMER_ORG_ID,
        source_opportunity_id=source_opportunity_id,
        pursuit_record_id=f"pur-{source_opportunity_id}",
        award_title=title,
        funding_agency=agency,
        award_number=award_number,
        award_start_date=start,
        award_end_date=end,
        total_award_amount=amount,
        award_status=status,
        requirements_extraction_status=extraction,
    )
    return {**record, "fixture_label": FIXTURE_LABEL}


def build_demo_awards() -> list[dict[str, Any]]:
    """Four awards, each demonstrating a different thing the system refuses."""
    return [
        _award(
            source_opportunity_id="demo-opp-001",
            award_number="DEMO-AW-001",
            title="Demo tribal water infrastructure award",
            agency="Demo Federal Agency",
            extraction="evidence_extracted",
            start="2026-01-01",
            end="2026-12-31",
            amount=450000,
        ),
        _award(
            source_opportunity_id="demo-opp-002",
            award_number="DEMO-AW-002",
            title="Demo language preservation award",
            agency="Demo Federal Agency",
            extraction="human_entered",
            start="2026-02-01",
            end="2027-01-31",
            amount=180000,
        ),
        _award(
            source_opportunity_id="demo-opp-003",
            award_number="DEMO-AW-003",
            title="Demo housing rehabilitation award",
            agency="Demo Federal Agency",
            extraction="unsupported_document_type",
            start="2026-01-15",
            end="2026-11-30",
            amount=95000,
        ),
        _award(
            source_opportunity_id="demo-opp-004",
            award_number=None,
            title="Demo award recorded from the letter only",
            agency="Demo Federal Agency",
            extraction="not_attempted",
            status="draft_award_record",
        ),
    ]


def build_demo_requirements() -> list[dict[str, Any]]:
    """Nine requirements across the four awards."""
    awards = {a["source_opportunity_id"]: a for a in build_demo_awards()}
    a1 = awards["demo-opp-001"]["award_id"]
    a2 = awards["demo-opp-002"]["award_id"]
    a3 = awards["demo-opp-003"]["award_id"]
    a4 = awards["demo-opp-004"]["award_id"]

    def req(**kwargs: Any) -> dict[str, Any]:
        return {
            **build_award_requirement(tenant_id=DEMO_TENANT_ID, **kwargs),
            "fixture_label": FIXTURE_LABEL,
        }

    return [
        # Overdue against the fixed clock.
        req(
            award_id=a1,
            requirement_type="narrative_report",
            requirement_title="Q4 performance narrative",
            requirement_status="not_started",
            due_date="2026-01-30",
            due_date_status="verified",
            recurrence="quarterly",
            extraction_status="evidence_extracted",
            source_document_id="demo-doc-001",
            source_evidence_ref="demo-doc-001#p4",
            assigned_owner="Demo grants officer",
            internal_reminder_schedule=["2026-01-16", "2026-01-23"],
        ),
        # Due soon against the fixed clock.
        req(
            award_id=a1,
            requirement_type="financial_report",
            requirement_title="Federal financial report",
            requirement_status="in_progress",
            due_date="2026-03-20",
            due_date_status="verified",
            recurrence="quarterly",
            extraction_status="evidence_extracted",
            source_document_id="demo-doc-001",
            source_evidence_ref="demo-doc-001#p7",
            assigned_owner="Demo finance lead",
            internal_reminder_schedule=["2026-03-06"],
        ),
        # Submitted, with a demo-labelled proof.
        req(
            award_id=a1,
            requirement_type="board_or_council_resolution",
            requirement_title="Council resolution accepting the award",
            requirement_status="submitted",
            due_date="2026-02-10",
            due_date_status="verified",
            extraction_status="human_entered",
            assigned_owner="Demo council liaison",
            proof_of_submission_status="proof_attached",
            proof_of_submission_ref="demo-proof-0001",
        ),
        # Closeout, dated.
        req(
            award_id=a1,
            requirement_type="closeout",
            requirement_title="Final closeout package",
            requirement_status="not_started",
            due_date="2027-03-31",
            due_date_status="verified",
            extraction_status="evidence_extracted",
            source_document_id="demo-doc-001",
            source_evidence_ref="demo-doc-001#p12",
            assigned_owner="Demo grants officer",
        ),
        # Real obligation, date never established.
        req(
            award_id=a2,
            requirement_type="audit",
            requirement_title="Single audit if threshold met",
            requirement_status="not_started",
            due_date_status="unknown",
            extraction_status="human_entered",
            assigned_owner="Demo finance lead",
        ),
        # Real obligation, date is an estimate and must never count down.
        req(
            award_id=a2,
            requirement_type="performance_measure",
            requirement_title="Mid-year performance measures",
            requirement_status="not_started",
            due_date="2026-08-01",
            due_date_status="estimated",
            extraction_status="human_entered",
        ),
        # Unreadable award package.
        req(
            award_id=a3,
            requirement_type="unknown",
            requirement_title="Requirements from an unreadable award package",
            due_date_status="unsupported",
            extraction_status="unsupported_document_type",
            source_document_id="demo-doc-003",
        ),
        # Projected from the notice. Not an obligation.
        req(
            award_id=a4,
            requirement_type="financial_report",
            requirement_title="Projected quarterly financial reporting",
            due_date_status="unknown",
            recurrence="quarterly",
            extraction_status="projected_from_nofo",
        ),
        # Match documentation, unassigned, to show the unassigned count.
        req(
            award_id=a2,
            requirement_type="match_documentation",
            requirement_title="Non-federal match documentation",
            requirement_status="not_started",
            due_date_status="unknown",
            extraction_status="human_entered",
        ),
    ]


def build_demo_proof_events() -> list[dict[str, Any]]:
    """One proof of submission, labelled demo_fixture everywhere it appears."""
    requirements = build_demo_requirements()
    resolution = next(
        r
        for r in requirements
        if r["requirement_type"] == "board_or_council_resolution"
    )
    submitted = record_proof_action(
        tenant_id=DEMO_TENANT_ID,
        award_id=resolution["award_id"],
        requirement_id=resolution["requirement_id"],
        action="mark_submitted",
        status_before="in_progress",
        proof_ref="demo-proof-0001",
        proof_label=DEMO_PROOF_LABEL,
        at="2026-02-09",
        actor="Demo council liaison",
    )
    return [{**submitted, "fixture_label": FIXTURE_LABEL}]


def build_demo_calendars() -> list[dict[str, Any]]:
    """One calendar per award, against the fixed clock."""
    requirements = build_demo_requirements()
    calendars = []
    for award in build_demo_awards():
        calendars.append(
            {
                **build_requirements_calendar(
                    tenant_id=DEMO_TENANT_ID,
                    award_id=award["award_id"],
                    requirements=requirements,
                    reference_date=REFERENCE_NOW,
                ),
                "award_title": award["award_title"],
                "fixture_label": FIXTURE_LABEL,
            }
        )
    return calendars


def measure_demo_cases(
    *,
    awards: list[dict[str, Any]],
    requirements: list[dict[str, Any]],
    proof_events: list[dict[str, Any]],
    calendars: list[dict[str, Any]],
) -> set[str]:
    """Which cases the supplied data actually demonstrates.

    Separated out and given its inputs so the measurement can be tested. The
    real fixture covers every case, so a function that simply returned
    `REQUIRED_DEMO_CASES` would look correct - feeding it data that is missing a
    case is the only way to prove it counts rather than asserts.
    """
    cases: set[str] = set()
    if any(
        a.get("requirements_extraction_status") == "evidence_extracted"
        for a in awards
    ):
        cases.add("documented_award")
    if any(r.get("due_date_status") == "unknown" for r in requirements):
        cases.add("unknown_due_dates")
    if any(
        r.get("extraction_status") == "unsupported_document_type"
        for r in requirements
    ):
        cases.add("unsupported_document_type")
    if any(r.get("extraction_status") == "projected_from_nofo" for r in requirements):
        cases.add("projected_burden_only")
    if any(
        item.get("overdue")
        for c in calendars
        for item in (c.get("calendar_items") or [])
    ):
        cases.add("overdue_requirement")
    if any(
        item.get("due_soon")
        for c in calendars
        for item in (c.get("calendar_items") or [])
    ):
        cases.add("due_soon_requirement")
    if any(r.get("requirement_type") == "closeout" for r in requirements):
        cases.add("closeout_requirement")
    if any(e.get("proof_is_demo_fixture") for e in proof_events):
        cases.add("proof_of_submission")
    return cases


def build_demo_fixture_set() -> dict[str, Any]:
    """Everything, plus the case coverage it claims."""
    awards = build_demo_awards()
    requirements = build_demo_requirements()
    proof_events = build_demo_proof_events()
    calendars = build_demo_calendars()

    # Coverage is measured from the built data, never asserted.
    cases = measure_demo_cases(
        awards=awards,
        requirements=requirements,
        proof_events=proof_events,
        calendars=calendars,
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixture_label": FIXTURE_LABEL,
            "tenant_id": DEMO_TENANT_ID,
            "customer_org_id": DEMO_CUSTOMER_ORG_ID,
            "reference_now": REFERENCE_NOW,
            "awards": awards,
            "requirements": requirements,
            "proof_events": proof_events,
            "calendars": calendars,
            "award_count": len(awards),
            "requirement_count": len(requirements),
            "demo_cases_covered": sorted(cases),
            "demo_cases_missing": sorted(REQUIRED_DEMO_CASES - cases),
            # Constants: invented data, labelled as such, from no real source.
            "real_customer_data": False,
            "real_award_numbers": False,
            "fabricated_requirements": False,
            "live_fetch_performed": False,
        }
    )


def demo_fixture_invariant_failures(fixture: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if fixture.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for constant in (
        "real_customer_data",
        "real_award_numbers",
        "fabricated_requirements",
        "live_fetch_performed",
    ):
        if fixture.get(constant) is not False:
            fails.append(f"demo_fixture_claimed:{constant}")

    if fixture.get("fixture_label") != FIXTURE_LABEL:
        fails.append("fixture_set_not_labelled")

    # Every record carries the label, not just the set.
    for group in ("awards", "requirements", "proof_events", "calendars"):
        for record in fixture.get(group) or []:
            if record.get("fixture_label") != FIXTURE_LABEL:
                fails.append(f"unlabelled_demo_record_in:{group}")
                break

    # The set must demonstrate every case it exists to demonstrate.
    for case in fixture.get("demo_cases_missing") or []:
        fails.append(f"demo_case_not_covered:{case}")

    # A projection in the fixture is never an obligation.
    for requirement in fixture.get("requirements") or []:
        if requirement.get("extraction_status") == "projected_from_nofo" and (
            requirement.get("is_active_obligation")
        ):
            fails.append("demo_projection_treated_as_obligation")

    # Proof in the fixture is always labelled as demo.
    for event in fixture.get("proof_events") or []:
        if event.get("proof_ref") and not event.get("proof_is_demo_fixture"):
            fails.append("demo_proof_without_its_label")

    return fails
