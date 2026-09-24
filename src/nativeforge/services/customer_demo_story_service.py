"""179L/M: a deterministic customer story, and the checklist Design will walk.

## The organisation this runs on

The PROTECTED DEMO organisation, `bbbbbbbb-cccc-dddd-eeee-ffffffffffff`, and
only that one. The real organisation is no-touch, and `build_demo_story`
refuses any other organisation id rather than trusting a caller to pass the
right one. A demo that can be pointed at a real Tribal government by changing
one argument is a demo that eventually will be.

## Deterministic

Same inputs, same bytes, every time. A demo whose content shifts between runs
cannot be used to judge whether a UI change broke something, which is exactly
what 179M asks Claude Design to do with it.

## 179M: a checklist, not a verdict

The smoke checklist enumerates the customer journey and states, for each
step, what the backend must supply and what the customer should experience.
`actual_result` is left as `NOT_YET_WALKED` and `customer_ready` as `null`,
because Claude Code has not navigated a UI - this file is the contract Design
fills in, and pre-filling it with PASS would be inventing the answer to the
question it exists to ask.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from nativeforge.services.customer_decision_service import (
    PURSUING,
    WATCHED,
    build_decision,
)
from nativeforge.services.customer_opportunity_feed_service import (
    ELIGIBILITY_APPEARS_ELIGIBLE,
    ELIGIBILITY_CONDITIONAL,
    RELEVANCE_BROADLY_ELIGIBLE,
    RELEVANCE_NATIVE_SPECIFIC,
    RELEVANCE_NOT_RELEVANT,
    build_feed,
    build_recommendation,
)
from nativeforge.services.customer_surface_service import (
    build_customer_surface,
    build_dashboard,
    build_trust_panel,
)

SCHEMA_VERSION = "nf_customer_demo_story_v1"

STORY_VERSION = "2026.09.1"

#: The protected demo organisation. The only one this module will build on.
DEMO_ORGANIZATION_ID = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"

#: The real organisation, named so the refusal can be explicit rather than
#: implied by an allow-list somebody might widen.
REAL_ORGANIZATION_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

#: Fixed so the story is byte-identical between runs.
STORY_DATE = "2026-09-24"


def _norm(value: Any) -> str:
    return str(value or "").replace("-", "").lower()


def build_demo_story(
    *, organization_id: Any = DEMO_ORGANIZATION_ID, as_of: str = STORY_DATE
) -> dict[str, Any]:
    """179L. One organisation, one week of its working life, deterministic."""
    if _norm(organization_id) == _norm(REAL_ORGANIZATION_ID):
        raise ValueError(
            "the demo story may not be built on the real organisation; it is "
            "no-touch without explicit authorization"
        )
    if _norm(organization_id) != _norm(DEMO_ORGANIZATION_ID):
        raise ValueError(
            f"the demo story runs only on the protected demo organisation "
            f"{DEMO_ORGANIZATION_ID}"
        )

    org = str(organization_id)

    # ---- the four opportunities the story needs --------------------
    strong = build_recommendation(
        organization_id=org,
        canonical_record={
            "canonical_id": "demo:canon:water-001",
            "title": "Tribal Water Infrastructure Assistance",
            "funder_name": "Environmental Protection Agency",
            "close_date": "2026-11-15",
        },
        relevance={
            "relevance_class": RELEVANCE_NATIVE_SPECIFIC,
            "why": (
                "the notice sets this programme aside for federally "
                "recognised Tribes"
            ),
            "evidence_ids": ["demo:ev:set-aside-001"],
        },
        eligibility={
            "eligibility_view": ELIGIBILITY_APPEARS_ELIGIBLE,
            "why": "entity type on file is a federally recognised Tribe",
            "evidence_ids": ["demo:el:entity-001"],
        },
        documents=[
            {
                "document_id": "demo:doc:nofo-001",
                "document_type": "NOFO",
                "page": 14,
                "quote": (
                    "Eligible applicants are federally recognized Indian "
                    "Tribes and Tribal consortia."
                ),
            }
        ],
        changes=[
            {
                "change_type": "DEADLINE_MOVED",
                "observed_at": "2026-09-20",
                "summary": "Amendment 2 moved the closing date to 15 November 2026.",
            }
        ],
    )

    conditional = build_recommendation(
        organization_id=org,
        canonical_record={
            "canonical_id": "demo:canon:broadband-002",
            "title": "Rural Broadband Deployment",
            "funder_name": "Department of Commerce",
            "close_date": "2026-10-30",
        },
        relevance={
            "relevance_class": RELEVANCE_NATIVE_SPECIFIC,
            "why": "Tribal lands are named as a priority deployment area",
            "evidence_ids": ["demo:ev:priority-002"],
        },
        eligibility={
            "eligibility_view": ELIGIBILITY_CONDITIONAL,
            "why": "eligible if a non-federal match can be committed",
            "conditions": ["25% non-federal match required at application"],
            "evidence_ids": ["demo:el:match-002"],
        },
        documents=[
            {
                "document_id": "demo:doc:nofo-002",
                "document_type": "NOFO",
                "page": 22,
                "quote": (
                    "Applicants must provide a non-federal match of at least "
                    "25 percent of total project cost."
                ),
            }
        ],
    )

    irrelevant = build_recommendation(
        organization_id=org,
        canonical_record={
            "canonical_id": "demo:canon:maritime-003",
            "title": "Commercial Maritime Port Modernisation",
            "funder_name": "Department of Transportation",
            "close_date": "2026-12-01",
        },
        relevance={
            "relevance_class": RELEVANCE_NOT_RELEVANT,
            "why": "eligibility is limited to public port authorities",
            "evidence_ids": ["demo:ev:port-only-003"],
        },
        eligibility={
            "eligibility_view": "APPEARS_INELIGIBLE",
            "why": "the applicant class excludes Tribal governments",
            "blockers": ["applicant must be a designated public port authority"],
            "evidence_ids": ["demo:el:port-003"],
        },
    )

    watched_row = build_recommendation(
        organization_id=org,
        canonical_record={
            "canonical_id": "demo:canon:language-004",
            "title": "Native Language Preservation",
            "funder_name": "Administration for Native Americans",
            "close_date": "2027-02-01",
        },
        relevance={
            "relevance_class": RELEVANCE_NATIVE_SPECIFIC,
            "why": "the programme exists for Native language communities",
            "evidence_ids": ["demo:ev:language-004"],
        },
        eligibility={
            "eligibility_view": ELIGIBILITY_APPEARS_ELIGIBLE,
            "why": "entity type and programme area both match",
            "evidence_ids": ["demo:el:language-004"],
        },
        documents=[
            {
                "document_id": "demo:doc:nofo-004",
                "document_type": "NOFO",
                "page": 3,
                "quote": (
                    "Awards support Native American language assessment, "
                    "planning, and implementation."
                ),
            }
        ],
    )

    broad = build_recommendation(
        organization_id=org,
        canonical_record={
            "canonical_id": "demo:canon:workforce-005",
            "title": "Regional Workforce Development",
            "funder_name": "Department of Labor",
            "close_date": "2026-11-01",
        },
        relevance={
            "relevance_class": RELEVANCE_BROADLY_ELIGIBLE,
            "why": "open to units of local and Tribal government",
            "evidence_ids": ["demo:ev:broad-005"],
        },
        eligibility={
            "eligibility_view": ELIGIBILITY_APPEARS_ELIGIBLE,
            "why": "entity type is within the eligible applicant list",
            "evidence_ids": ["demo:el:broad-005"],
        },
    )

    recommendations = [strong, conditional, irrelevant, watched_row, broad]

    # ---- the decisions --------------------------------------------
    decisions = [
        build_decision(
            organization_id=org,
            canonical_id="demo:canon:language-004",
            decision_state=WATCHED,
            actor_id="demo:person:grants-lead",
            decided_at="2026-09-21",
            reason="council asked us to keep an eye on this",
        ),
        build_decision(
            organization_id=org,
            canonical_id="demo:canon:water-001",
            decision_state=PURSUING,
            actor_id="demo:person:grants-lead",
            decided_at="2026-09-22",
            reason="strongest fit this cycle",
        ),
    ]
    by_id = {str(d["canonical_id"]): d for d in decisions}
    for row in recommendations:
        decision = by_id.get(str(row["canonical_id"]))
        if decision:
            row["decision_state"] = decision["decision_state"]

    pursuit = {
        "pursuit_id": "demo:pursuit:water-001",
        "organization_id": org,
        "canonical_id": "demo:canon:water-001",
        "opened_by": "demo:person:grants-lead",
        "opened_at": "2026-09-22",
        "requirements": [
            {
                "requirement_id": "demo:req:sf424",
                "label": "SF-424 application for federal assistance",
                "status": "NOT_STARTED",
            },
            {
                "requirement_id": "demo:req:narrative",
                "label": "Project narrative, 15 pages maximum",
                "status": "NOT_STARTED",
            },
        ],
        "tasks": [
            {
                "task_id": "demo:task:confirm-match",
                "label": "Confirm no match is required for this programme",
                "assigned_to": "demo:person:grants-lead",
                "due": "2026-10-10",
                "status": "OPEN",
            }
        ],
        "deadline": "2026-11-15",
    }

    feed = build_feed(organization_id=org, recommendations=recommendations, as_of=as_of)
    dashboard = build_dashboard(
        organization_id=org,
        recommendations=recommendations,
        decisions=decisions,
        changes=[{"organization_id": org, "change_type": "DEADLINE_MOVED"}],
        coverage_notes=[
            {
                "note": (
                    "two state-level sources in this organisation's region "
                    "are awaiting authorisation and are not being collected"
                )
            }
        ],
        as_of=as_of,
    )
    surface = build_customer_surface(
        organization_id=org,
        role="ORG_ADMIN",
        dashboard=dashboard,
        feed=feed,
    )
    trust = build_trust_panel(
        recommendation=strong,
        source_records=[
            {
                "source_name": "EPA Grants Announcements",
                "publisher": "Environmental Protection Agency",
                "last_observed_at": "2026-09-23",
                "authorization_status": "AUTHORIZED",
            }
        ],
    )

    story = {
        "schema_version": SCHEMA_VERSION,
        "story_version": STORY_VERSION,
        "organization_id": org,
        "organization_is_the_protected_demo": True,
        "real_organization_untouched": True,
        "as_of": as_of,
        "authorized_admin": {
            "identity_id": "demo:person:grants-lead",
            "role": "ORG_SUPER_ADMIN",
            "identity_status": "VERIFIED",
            "affiliation_status": "VERIFIED",
            "authority_status": "MANUALLY_VERIFIED",
        },
        "profile": {
            "legal_name": "Demo Tribal Government",
            "entity_type": "FEDERALLY_RECOGNIZED_TRIBE",
            "funding_sectors": ["water", "broadband", "language"],
            "strategic_priorities": ["language revitalization"],
        },
        "preferences": {
            "org_default_tile_order": [
                "DEADLINES",
                "ACTIVE_PURSUITS",
                "NEW_OPPORTUNITIES",
            ],
            "personal_tile_order": ["NEW_OPPORTUNITIES", "DEADLINES"],
        },
        "license": {
            "license_state": "LICENSED_ACTIVE",
            "maintenance_state": "MAINTENANCE_CURRENT",
            "benefit_access": "BENEFIT_FULL",
        },
        "recommendations": recommendations,
        "decisions": decisions,
        "pursuit": pursuit,
        "feed": feed,
        "dashboard": dashboard,
        "surface": surface,
        "trust_panel": trust,
    }
    story["content_digest"] = hashlib.sha256(
        json.dumps(story, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return story


# ---------------------------------------------------------------------------
# 179M: the checklist Claude Design walks.
# ---------------------------------------------------------------------------

NOT_YET_WALKED = "NOT_YET_WALKED"

RESULTS: tuple[str, ...] = ("PASS", "FRICTION", "DEFECT", "BLOCKED", NOT_YET_WALKED)

_JOURNEY: tuple[dict[str, str], ...] = (
    {
        "step": "SIGN_IN",
        "intended_goal": "the person gets into their own organisation, and only theirs",
        "required_backend_state": "verified identity with an affiliation to this org",
        "route": "/sign-in",
        "expected_customer_experience": (
            "one sign-in, landing in their organisation with its name visible"
        ),
    },
    {
        "step": "ORGANIZATION",
        "intended_goal": "they can see which organisation they are acting for",
        "required_backend_state": "org profile with legal name and entity type",
        "route": "/organization",
        "expected_customer_experience": (
            "the Tribe's own name and mark, not an internal identifier"
        ),
    },
    {
        "step": "ONBOARDING",
        "intended_goal": "a new organisation can reach a useful state unaided",
        "required_backend_state": "authority grant, empty profile",
        "route": "/onboarding",
        "expected_customer_experience": (
            "a short sequence that says why each answer is needed"
        ),
    },
    {
        "step": "PROFILE_PRIORITIES",
        "intended_goal": "the organisation describes itself in its own words",
        "required_backend_state": "profile versions, phrase resolution",
        "route": "/organization/profile",
        "expected_customer_experience": (
            "free text accepted; an unrecognised phrase is flagged for review "
            "rather than silently dropped"
        ),
    },
    {
        "step": "DASHBOARD",
        "intended_goal": "they can see what needs attention today",
        "required_backend_state": "tenant-scoped dashboard read model",
        "route": "/dashboard",
        "expected_customer_experience": "eight tiles, counts that match the lists",
    },
    {
        "step": "RECOMMENDED_OPPORTUNITIES",
        "intended_goal": "they see funding they could actually pursue",
        "required_backend_state": "recommendations sourced from the canonical graph",
        "route": "/opportunities",
        "expected_customer_experience": (
            "a list with a named ordering they can change"
        ),
    },
    {
        "step": "WHY_RELEVANT",
        "intended_goal": "they can tell why an item is in front of them",
        "required_backend_state": "relevance class with evidence ids",
        "route": "/opportunities/{id}",
        "expected_customer_experience": ("a sentence and a citation, not a percentage"),
    },
    {
        "step": "ELIGIBILITY",
        "intended_goal": "they know whether they can apply, or what is unclear",
        "required_backend_state": "eligibility view, conditions, blockers",
        "route": "/opportunities/{id}#eligibility",
        "expected_customer_experience": (
            "conditional says WHAT the condition is; uncertain says so plainly"
        ),
    },
    {
        "step": "DOCUMENT_EVIDENCE",
        "intended_goal": "they can check the claim against the funder's words",
        "required_backend_state": "document citations with page and quote",
        "route": "/opportunities/{id}#evidence",
        "expected_customer_experience": "the quote, the page, the document",
    },
    {
        "step": "WATCH_DISMISS_PURSUE",
        "intended_goal": "their decision sticks and can be undone",
        "required_backend_state": "durable decision with actor and time",
        "route": "/opportunities/{id}",
        "expected_customer_experience": (
            "the decision survives a reload; dismissing is reversible"
        ),
    },
    {
        "step": "PURSUIT",
        "intended_goal": "an application has somewhere to live",
        "required_backend_state": "pursuit with requirements and tasks",
        "route": "/pursuits/{id}",
        "expected_customer_experience": "requirements, tasks, one deadline",
    },
    {
        "step": "REQUIREMENTS",
        "intended_goal": "they know what the funder asks for",
        "required_backend_state": "requirement list from document extraction",
        "route": "/pursuits/{id}#requirements",
        "expected_customer_experience": "each requirement cites where it came from",
    },
    {
        "step": "TASKS",
        "intended_goal": "work can be assigned and tracked",
        "required_backend_state": "tasks with assignee and due date",
        "route": "/pursuits/{id}#tasks",
        "expected_customer_experience": "assignable, with dates that match deadlines",
    },
    {
        "step": "DEADLINES",
        "intended_goal": "nothing closes without warning",
        "required_backend_state": "deadline read model within a window",
        "route": "/deadlines",
        "expected_customer_experience": (
            "days remaining, and an amended date shown as amended"
        ),
    },
    {
        "step": "APPLICATION_PREPARATION",
        "intended_goal": "they can assemble a submission",
        "required_backend_state": "form package, no auto-submission",
        "route": "/pursuits/{id}/prepare",
        "expected_customer_experience": (
            "review-ready output, and no button that submits on their behalf"
        ),
    },
    {
        "step": "TRUST_SOURCE_EVIDENCE",
        "intended_goal": "they can see where all of it came from",
        "required_backend_state": "trust panel: sources, citations, changes, unknowns",
        "route": "/opportunities/{id}#trust",
        "expected_customer_experience": (
            "provenance and known gaps, with no internal identifiers"
        ),
    },
)


def build_ux_smoke_checklist() -> dict[str, Any]:
    """179M. The contract Claude Design fills in by navigating staging.

    `actual_result` and `customer_ready` are deliberately unset. Claude Code
    has not walked a UI, and pre-filling PASS would invent the answer to the
    question this checklist exists to ask.
    """
    items = [
        {
            **step,
            "actual_result": NOT_YET_WALKED,
            "customer_ready": None,
            "evidence_screenshot_needed": True,
            "notes": None,
        }
        for step in _JOURNEY
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "story_version": STORY_VERSION,
        "generated_by": "claude_code",
        "to_be_walked_by": "claude_design",
        "step_count": len(items),
        "results_vocabulary": list(RESULTS),
        "items": items,
        "unwalked_count": sum(1 for i in items if i["actual_result"] == NOT_YET_WALKED),
        "any_result_prefilled": any(
            i["actual_result"] != NOT_YET_WALKED for i in items
        ),
        "any_customer_ready_prefilled": any(
            i["customer_ready"] is not None for i in items
        ),
        "why_unfilled": (
            "Claude Code has not navigated a UI. A checklist that arrived "
            "pre-marked PASS would answer the question it exists to ask"
        ),
    }


def render_ux_checklist_markdown(checklist: dict[str, Any]) -> str:
    """The same checklist, for a human to read and annotate."""
    lines = [
        "# NativeForge — customer UX smoke checklist",
        "",
        f"Generated by {checklist['generated_by']}; to be walked by "
        f"{checklist['to_be_walked_by']}.",
        "",
        "`actual_result` is NOT_YET_WALKED for every step on purpose — see",
        "`why_unfilled`. Mark each PASS / FRICTION / DEFECT / BLOCKED while",
        "navigating staging.",
        "",
    ]
    for item in checklist["items"]:
        lines += [
            f"## {item['step']}",
            "",
            f"- **Goal** — {item['intended_goal']}",
            f"- **Backend must supply** — {item['required_backend_state']}",
            f"- **Route** — `{item['route']}`",
            f"- **Expected** — {item['expected_customer_experience']}",
            f"- **Result** — `{item['actual_result']}`",
            "- **Customer ready** — _unset_",
            "- **Screenshot** — required",
            "",
        ]
    return "\n".join(lines)


def describe_demo_story() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "story_version": STORY_VERSION,
        "demo_organization_id": DEMO_ORGANIZATION_ID,
        "runs_only_on_the_protected_demo_organization": True,
        "refuses_the_real_organization": True,
        "is_deterministic": True,
        "journey_steps": [s["step"] for s in _JOURNEY],
        "journey_step_count": len(_JOURNEY),
        "checklist_results_are_not_prefilled": True,
        "story_date_is_pinned": STORY_DATE,
    }
