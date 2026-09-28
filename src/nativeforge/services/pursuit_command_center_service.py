"""Assemble the individual pursuit command center from canonical records.

The workflow is the Workspace sequence (profile → opportunity → NOFO →
score → pursuit → SF-424 → trust), derived from the same persisted objects
that sequence already uses. This module does not invent a second stage
column. A discovered opportunity that has no pursuit must not look like an
active chase.

Funder relationship intelligence reuses 0068 contacts and 0069 interactions.
Agency matching for institutional memory is exact (normalized whitespace and
case), never a fuzzy merge of people.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nativeforge.db.models import (
    NfFormPackage,
    NfGrantPursuit,
    NfGrantSpark,
    NfPursuitCalendarEvent,
    NfPursuitTask,
    NfSparkRequirement,
    NfSparkScore,
    NfTribalProfile,
)
from nativeforge.services import funder_interaction_service as interactions
from nativeforge.services import opportunity_apply_path_service as apply_path

SCHEMA_VERSION = "nf_pursuit_command_center_v1"

STAGE_VIEWS: dict[str, str] = {
    "profile": "organization",
    "spark": "opportunities",
    "nofo": "documents",
    "score": "documents",
    "pursuit": "pursuits",
    "forms": "pursuits",
    "trust": "trust",
}

_MONTH = (
    r"(?:January|February|March|April|May|June|July|August|"
    r"September|October|November|December)"
)
_QUESTION_DUE = re.compile(
    rf"questions?.{{0,160}}(?:due|submitted|received|no later than).{{0,40}}"
    rf"({_MONTH} \d{{1,2}}, \d{{4}})",
    re.I,
)
_QUESTION_METHOD = re.compile(
    r"(?:send|submit|email)\s+questions?\s+to\s+"
    r"([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})",
    re.I,
)
_WEBINAR = re.compile(r"\bwebinar\b", re.I)
_CONFERENCE = re.compile(
    r"applicant conference|pre-application (?:meeting|conference)", re.I
)
_OFFICE_HOURS = re.compile(r"office hours", re.I)
_FAQ = re.compile(r"\bFAQs?\b", re.I)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


def extract_engagement_facts(notice_text: str) -> list[dict[str, Any]]:
    """Facts about asking questions. Absence is not a deadline."""
    text = notice_text or ""
    facts: list[dict[str, Any]] = []
    due = _QUESTION_DUE.search(text)
    if due:
        facts.append(
            {
                "kind": "questions_due",
                "label": "Questions due",
                "value": due.group(1),
                "source": "stored notice text",
            }
        )
    method = _QUESTION_METHOD.search(text)
    if method:
        facts.append(
            {
                "kind": "question_submission_method",
                "label": "Send questions to",
                "value": method.group(1),
                "source": "stored notice text",
            }
        )
    if _WEBINAR.search(text):
        facts.append(
            {
                "kind": "webinar",
                "label": "Webinar",
                "value": "Mentioned in the notice",
                "source": "stored notice text",
            }
        )
    if _CONFERENCE.search(text):
        facts.append(
            {
                "kind": "applicant_conference",
                "label": "Applicant conference",
                "value": "Mentioned in the notice",
                "source": "stored notice text",
            }
        )
    if _OFFICE_HOURS.search(text):
        facts.append(
            {
                "kind": "office_hours",
                "label": "Office hours",
                "value": "Mentioned in the notice",
                "source": "stored notice text",
            }
        )
    if _FAQ.search(text):
        facts.append(
            {
                "kind": "faq",
                "label": "FAQ",
                "value": "Mentioned in the notice",
                "source": "stored notice text",
            }
        )
    return facts


def _stage(
    stage_id: str,
    short: str,
    label: str,
    *,
    complete: bool,
    locked: bool,
    blocked: bool,
    summary: str,
) -> dict[str, Any]:
    if complete:
        status = "complete"
    elif locked:
        status = "not_applicable"
    elif blocked:
        status = "blocked"
    else:
        status = "not_started"
    view = STAGE_VIEWS.get(stage_id) if status != "not_applicable" else None
    return {
        "id": stage_id,
        "short_label": short,
        "label": label,
        "status": status,
        "summary": summary,
        "view": view,
    }


def _mark_current(stages: list[dict[str, Any]]) -> str | None:
    current_id = None
    for stage in stages:
        if stage["status"] == "complete":
            continue
        if stage["status"] == "not_applicable":
            continue
        if stage["status"] == "blocked":
            current_id = stage["id"]
            break
        stage["status"] = "current"
        current_id = stage["id"]
        break
    return current_id


def build_pursuit_stages(
    *,
    has_profile: bool,
    has_req: bool,
    has_score: bool,
    disqualified: bool,
    has_pursuit: bool,
    has_form: bool,
    blocked_tasks: bool,
) -> tuple[list[dict[str, Any]], str | None]:
    """Same seven stages the Workspace and the command center both show."""
    stages = [
        _stage(
            "profile",
            "Profile",
            "Organization profile",
            complete=has_profile,
            locked=False,
            blocked=False,
            summary="On file" if has_profile else "Needed before a pursuit can start",
        ),
        _stage(
            "spark",
            "Opportunity",
            "Opportunity review",
            complete=True,
            locked=not has_profile,
            blocked=False,
            summary="This record",
        ),
        _stage(
            "nofo",
            "Requirements",
            "Requirements",
            complete=has_req,
            locked=False,
            blocked=False,
            summary="Checklist ready" if has_req else "Extract when ready",
        ),
        _stage(
            "score",
            "Eligibility",
            "Eligibility / fit",
            complete=has_score and not disqualified,
            locked=not has_req,
            blocked=disqualified,
            summary=(
                "Review flags"
                if disqualified
                else "Scored"
                if has_score
                else "Run when ready"
            ),
        ),
        _stage(
            "pursuit",
            "Pursuit",
            "Pursuit decision",
            complete=has_pursuit,
            locked=not has_score,
            blocked=False,
            summary="Active" if has_pursuit else "Open when ready",
        ),
        _stage(
            "forms",
            "Package",
            "Application package",
            complete=has_form,
            locked=not has_pursuit,
            blocked=blocked_tasks,
            summary=(
                "Blocked"
                if blocked_tasks
                else "Preview ready"
                if has_form
                else "Create when ready"
            ),
        ),
        _stage(
            "trust",
            "Review",
            "Review / trust",
            complete=False,
            locked=not has_form,
            blocked=False,
            summary="Refresh in Trust" if has_form else "After the package",
        ),
    ]
    return stages, _mark_current(stages)


def assemble_command_center(
    *,
    session: Session,
    organization_id: uuid.UUID | str,
    grant_spark_id: uuid.UUID | str,
) -> dict[str, Any] | None:
    org = uuid.UUID(str(organization_id))
    spark_id = uuid.UUID(str(grant_spark_id))
    spark = session.get(NfGrantSpark, spark_id)
    if spark is None or spark.organization_id != org:
        return None

    has_profile = session.scalar(
        select(func.count())
        .select_from(NfTribalProfile)
        .where(NfTribalProfile.organization_id == org)
    )
    req_count = (
        session.scalar(
            select(func.count())
            .select_from(NfSparkRequirement)
            .where(
                NfSparkRequirement.organization_id == org,
                NfSparkRequirement.grant_spark_id == spark_id,
            )
        )
        or 0
    )
    score = session.scalar(
        select(NfSparkScore)
        .where(
            NfSparkScore.organization_id == org,
            NfSparkScore.grant_spark_id == spark_id,
        )
        .order_by(NfSparkScore.created_at.desc())
        .limit(1)
    )
    pursuit = session.scalar(
        select(NfGrantPursuit).where(
            NfGrantPursuit.organization_id == org,
            NfGrantPursuit.grant_spark_id == spark_id,
        )
    )
    form_pkg = None
    tasks: list[NfPursuitTask] = []
    calendar: list[NfPursuitCalendarEvent] = []
    if pursuit is not None:
        form_pkg = session.scalar(
            select(NfFormPackage).where(
                NfFormPackage.organization_id == org,
                NfFormPackage.grant_pursuit_id == pursuit.id,
            )
        )
        tasks = list(
            session.scalars(
                select(NfPursuitTask)
                .where(
                    NfPursuitTask.organization_id == org,
                    NfPursuitTask.grant_pursuit_id == pursuit.id,
                )
                .order_by(NfPursuitTask.sort_order, NfPursuitTask.created_at)
            )
        )
        calendar = list(
            session.scalars(
                select(NfPursuitCalendarEvent)
                .where(
                    NfPursuitCalendarEvent.organization_id == org,
                    NfPursuitCalendarEvent.grant_pursuit_id == pursuit.id,
                )
                .order_by(NfPursuitCalendarEvent.occurs_at)
            )
        )

    disqualified = bool(score and getattr(score, "disqualified", False))
    blocked_tasks = [t for t in tasks if t.status == "blocked"]
    open_tasks = [t for t in tasks if t.status not in {"done", "cancelled"}]
    now = datetime.now(tz=UTC)
    overdue = []
    for task in open_tasks:
        due = task.due_at
        if due is None:
            continue
        if due.tzinfo is None:
            due = due.replace(tzinfo=UTC)
        if due < now:
            overdue.append(task)

    has_profile_row = int(has_profile or 0) > 0
    has_score = score is not None
    has_pursuit = pursuit is not None
    has_form = form_pkg is not None
    has_req = int(req_count) > 0

    stages, current_id = build_pursuit_stages(
        has_profile=has_profile_row,
        has_req=has_req,
        has_score=has_score,
        disqualified=disqualified,
        has_pursuit=has_pursuit,
        has_form=has_form,
        blocked_tasks=bool(blocked_tasks),
    )

    mode = "active_pursuit" if has_pursuit else "discovered"
    if mode == "discovered":
        for stage in stages:
            if (
                stage["id"] in {"pursuit", "forms", "trust"}
                and stage["status"] != "complete"
            ):
                stage["view"] = None

    next_action = _next_action(
        has_profile=has_profile_row,
        has_req=has_req,
        has_score=has_score,
        has_pursuit=has_pursuit,
        has_form=has_form,
        open_task=open_tasks[0] if open_tasks else None,
        blocked=blocked_tasks[0] if blocked_tasks else None,
    )

    apply = apply_path.read_apply_path(
        connection=session.connection(),
        organization_id=org,
        grant_spark_id=spark_id,
    )
    contacts = list(apply.get("contacts") or [])
    extraction_performed = bool(apply.get("extraction_performed"))
    if extraction_performed and not contacts:
        contact_empty = "No grant contact information was identified in the available source materials."
    elif not extraction_performed:
        contact_empty = (
            "NativeForge has not yet read this notice for contacts. "
            "Absence here does not mean the notice names nobody."
        )
    else:
        contact_empty = None

    engagement = extract_engagement_facts(spark.raw_nofo_text or "")
    program_contact = next((c for c in contacts if c.get("role") == "program"), None)
    if (
        program_contact
        and program_contact.get("email")
        and not any(f["kind"] == "question_submission_method" for f in engagement)
    ):
        engagement.append(
            {
                "kind": "designated_question_contact",
                "label": "Program contact",
                "value": program_contact.get("email"),
                "source": program_contact.get("source_section") or "extracted contact",
            }
        )

    recorded = interactions.list_interactions(
        connection=session.connection(),
        organization_id=org,
        grant_spark_id=spark_id,
    )
    memory = _institutional_memory(
        session=session,
        organization_id=org,
        spark=spark,
    )

    deadlines = _deadlines(spark, calendar, apply.get("submission"))

    return {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "opportunity": {
            "id": str(spark.id),
            "title": spark.opportunity_title,
            "agency": spark.agency,
            "program_name": spark.program_name,
            "source": spark.source,
            "pipeline_stage": spark.pipeline_stage,
            "application_deadline": _iso(spark.application_deadline),
            "loi_deadline": _iso(spark.loi_deadline),
        },
        "pursuit": (
            {
                "id": str(pursuit.id),
                "status": pursuit.status,
            }
            if pursuit
            else None
        ),
        "workflow": {
            "derived": True,
            "shown": mode == "active_pursuit",
            "current_stage_id": current_id if mode == "active_pursuit" else None,
            "stages": stages,
        },
        "next_action": next_action,
        "open_work": {
            "open_count": len(open_tasks),
            "blocked_count": len(blocked_tasks),
            "overdue_count": len(overdue),
            "tasks": [_task(t) for t in open_tasks],
            "blockers": [_task(t) for t in blocked_tasks],
            "overdue": [_task(t) for t in overdue],
        },
        "deadlines": deadlines,
        "contacts": {
            "items": contacts,
            "extraction_performed": extraction_performed,
            "empty_message": contact_empty,
        },
        "question_intelligence": {
            "facts": engagement,
            "found": bool(engagement),
        },
        "interactions": recorded,
        "institutional_memory": memory,
        "submission": apply.get("submission"),
    }


def _task(task: NfPursuitTask) -> dict[str, Any]:
    return {
        "id": str(task.id),
        "title": task.title,
        "status": task.status,
        "due_at": _iso(task.due_at),
        "owner_label": None,
        "owner_membership_id": str(task.owner_membership_id)
        if getattr(task, "owner_membership_id", None)
        else None,
    }


def _next_action(
    *,
    has_profile: bool,
    has_req: bool,
    has_score: bool,
    has_pursuit: bool,
    has_form: bool,
    open_task: NfPursuitTask | None,
    blocked: NfPursuitTask | None,
) -> dict[str, Any]:
    if blocked is not None:
        return {
            "headline": "A task is blocked",
            "detail": blocked.title,
            "action_id": "pursuit",
            "view": "pursuits",
            "owner_label": None,
        }
    if not has_profile:
        return {
            "headline": "Set up the organization profile",
            "detail": "The pursuit workflow starts with who you are.",
            "action_id": "profile",
            "view": "organization",
            "owner_label": None,
        }
    if not has_req:
        return {
            "headline": "Read the notice for requirements",
            "detail": "Extract the checklist before scoring or opening a pursuit.",
            "action_id": "nofo_extract",
            "view": "documents",
            "owner_label": None,
        }
    if not has_score:
        return {
            "headline": "Score this opportunity",
            "detail": "Eligibility and fit are scored from the checklist.",
            "action_id": "score",
            "view": "documents",
            "owner_label": None,
        }
    if not has_pursuit:
        return {
            "headline": "Start this as a pursuit",
            "detail": "That creates tasks and calendar anchors for this grant.",
            "action_id": "pursuit",
            "view": "pursuits",
            "owner_label": None,
        }
    if open_task is not None:
        return {
            "headline": open_task.title,
            "detail": "Next open task on this pursuit.",
            "action_id": "task",
            "view": "pursuits",
            "owner_label": None,
        }
    if not has_form:
        return {
            "headline": "Create the SF-424 preview",
            "detail": "Internal package for staff review — not a filing.",
            "action_id": "sf424",
            "view": "pursuits",
            "owner_label": None,
        }
    return {
        "headline": "Review the package",
        "detail": "Trust Center holds the exportable review record.",
        "action_id": "trust",
        "view": "trust",
        "owner_label": None,
    }


def _deadlines(
    spark: NfGrantSpark,
    calendar: list[NfPursuitCalendarEvent],
    submission: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if spark.application_deadline:
        items.append(
            {
                "kind": "application_deadline",
                "label": "Application deadline",
                "occurs_at": _iso(spark.application_deadline),
                "source": "opportunity record",
            }
        )
    if spark.loi_deadline:
        items.append(
            {
                "kind": "loi_deadline",
                "label": "Letter of interest",
                "occurs_at": _iso(spark.loi_deadline),
                "source": "opportunity record",
            }
        )
    if submission and submission.get("deadline_at"):
        if not any(i["kind"] == "application_deadline" for i in items):
            items.append(
                {
                    "kind": "application_deadline",
                    "label": "Application deadline",
                    "occurs_at": submission["deadline_at"],
                    "source": submission.get("source_section") or "submission path",
                }
            )
    seen = {i["kind"] for i in items}
    for event in calendar:
        if event.kind in seen:
            continue
        items.append(
            {
                "kind": event.kind,
                "label": event.title,
                "occurs_at": _iso(event.occurs_at),
                "source": "pursuit calendar",
            }
        )
        seen.add(event.kind)
    return items


def _institutional_memory(
    *,
    session: Session,
    organization_id: uuid.UUID,
    spark: NfGrantSpark,
) -> dict[str, Any]:
    agency_norm = interactions.normalize_agency(spark.agency)
    if not agency_norm:
        return {"prior_pursuits": [], "prior_contacts": [], "prior_interactions": []}

    others = list(
        session.scalars(
            select(NfGrantSpark).where(
                NfGrantSpark.organization_id == organization_id,
                NfGrantSpark.id != spark.id,
            )
        )
    )
    related = [
        other
        for other in others
        if interactions.normalize_agency(other.agency) == agency_norm
    ]
    prior_pursuits = []
    for other in related:
        pursuit = session.scalar(
            select(NfGrantPursuit).where(
                NfGrantPursuit.organization_id == organization_id,
                NfGrantPursuit.grant_spark_id == other.id,
            )
        )
        if pursuit is None:
            continue
        prior_pursuits.append(
            {
                "grant_spark_id": str(other.id),
                "title": other.opportunity_title,
                "source": other.source,
                "pursuit_id": str(pursuit.id),
                "pursuit_status": pursuit.status,
            }
        )

    prior_contacts: list[dict[str, Any]] = []
    seen_reach = set()
    for other in related:
        path = apply_path.read_apply_path(
            connection=session.connection(),
            organization_id=organization_id,
            grant_spark_id=other.id,
        )
        for contact in path.get("contacts") or []:
            key = (
                str(contact.get("email") or "").lower(),
                str(contact.get("phone") or ""),
                str(contact.get("name") or "").lower(),
            )
            if key in seen_reach or not any(key):
                continue
            seen_reach.add(key)
            prior_contacts.append(
                {
                    "name": contact.get("name"),
                    "role": contact.get("role"),
                    "email": contact.get("email"),
                    "from_opportunity": other.opportunity_title,
                    "provenance_kind": contact.get("provenance_kind"),
                }
            )

    prior_interactions = interactions.list_interactions(
        connection=session.connection(),
        organization_id=organization_id,
        funder_agency=spark.agency,
        exclude_spark_id=spark.id,
    )
    return {
        "funder_agency": spark.agency,
        "prior_pursuits": prior_pursuits,
        "prior_contacts": prior_contacts,
        "prior_interactions": prior_interactions,
    }
