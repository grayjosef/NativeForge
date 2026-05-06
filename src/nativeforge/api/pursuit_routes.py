"""Sprint 5 — grant pursuits, tasks, org calendar."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from nativeforge.api.deps_db import (
    get_db_session,
    require_demo_org_db,
    require_real_org_db,
)
from nativeforge.api.org_context import OrgContext
from nativeforge.db.models import NfGrantSpark
from nativeforge.domain.enums import (
    PursuitCalendarKind,
    PursuitTaskStatus,
    PursuitWorkflowStatus,
)
from nativeforge.repositories import organizations as org_repo
from nativeforge.services import pursuit_service as psvc


def _same_org(path_org: uuid.UUID, ctx: OrgContext) -> None:
    if path_org != ctx.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="path org_id does not match authenticated org",
        )


def _parse_iso_datetime(raw: str) -> datetime:
    z = raw.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(z)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


class CreatePursuitBody(BaseModel):
    notes: str | None = Field(default=None, max_length=8192)


class PursuitPatchBody(BaseModel):
    status: PursuitWorkflowStatus | None = None
    notes: str | None = Field(default=None, max_length=8192)


class TaskCreateBody(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    description: str | None = Field(default=None, max_length=8192)
    due_at: datetime | None = None


class TaskPatchBody(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=512)
    description: str | None = Field(default=None, max_length=8192)
    status: PursuitTaskStatus | None = None
    due_at: datetime | None = None


class CalendarCreateBody(BaseModel):
    kind: PursuitCalendarKind
    title: str = Field(min_length=1, max_length=512)
    occurs_at: datetime
    notes: str | None = Field(default=None, max_length=8192)
    pursuit_task_id: uuid.UUID | None = None


demo_pursuit_router = APIRouter(
    prefix="/v1/nf/demo/orgs",
    tags=["pursuits-demo"],
)
real_pursuit_router = APIRouter(
    prefix="/v1/nf/real/orgs",
    tags=["pursuits-real"],
)


def _handle_pursuit_create_exc(exc: Exception) -> None:
    if isinstance(exc, psvc.PursuitAlreadyExistsError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, psvc.SparkNotScoredError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, psvc.GrantSparkNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    raise exc


@demo_pursuit_router.post(
    "/{org_id}/grant-sparks/{spark_id}/pursuit",
    status_code=status.HTTP_201_CREATED,
)
def demo_create_pursuit(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: CreatePursuitBody | None = None,
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    try:
        row = psvc.create_pursuit_from_spark(
            db,
            org=org,
            org_type=ctx.org_type,
            spark_id=spark_id,
            actor_id=actor_id,
            notes=body.notes if body else None,
        )
        db.commit()
        db.refresh(row)
    except (psvc.PursuitAlreadyExistsError, psvc.SparkNotScoredError) as e:
        _handle_pursuit_create_exc(e)
    except psvc.GrantSparkNotFoundError as e:
        _handle_pursuit_create_exc(e)
    spark = db.get(NfGrantSpark, row.grant_spark_id)
    title = spark.opportunity_title if spark else None
    return psvc.pursuit_to_dict(row, spark_title=title)


@demo_pursuit_router.get("/{org_id}/pursuits")
def demo_list_pursuits(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> list[dict[str, Any]]:
    _same_org(org_id, ctx)
    return psvc.list_pursuits(db, org_id=ctx.org_id, org_type=ctx.org_type)


@demo_pursuit_router.get("/{org_id}/pursuits/{pursuit_id}")
def demo_get_pursuit(
    org_id: uuid.UUID,
    pursuit_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    try:
        return psvc.get_pursuit_detail(
            db,
            org_id=ctx.org_id,
            org_type=ctx.org_type,
            pursuit_id=pursuit_id,
        )
    except psvc.PursuitNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@demo_pursuit_router.patch("/{org_id}/pursuits/{pursuit_id}")
def demo_patch_pursuit(
    org_id: uuid.UUID,
    pursuit_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: PursuitPatchBody,
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    raw = body.model_dump(exclude_unset=True)
    patch: dict[str, Any] = {}
    if "status" in raw:
        patch["status"] = raw["status"].value
    if "notes" in raw:
        patch["notes"] = raw["notes"]
    try:
        row = psvc.update_pursuit(
            db,
            org=org,
            org_type=ctx.org_type,
            pursuit_id=pursuit_id,
            patch=patch,
            actor_id=actor_id,
        )
        db.commit()
        db.refresh(row)
    except psvc.PursuitNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    spark = db.get(NfGrantSpark, row.grant_spark_id)
    title = spark.opportunity_title if spark else None
    return psvc.pursuit_to_dict(row, spark_title=title)


@demo_pursuit_router.get("/{org_id}/pursuits/{pursuit_id}/tasks")
def demo_list_tasks(
    org_id: uuid.UUID,
    pursuit_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, list[dict[str, Any]]]:
    _same_org(org_id, ctx)
    from nativeforge.repositories import pursuits as pr

    p = pr.get_grant_pursuit_scoped(
        session=db,
        pursuit_id=pursuit_id,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )
    if p is None:
        raise HTTPException(status_code=404, detail="pursuit not found")
    tasks = pr.list_tasks_for_pursuit(
        session=db,
        pursuit_id=pursuit_id,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )
    return {"tasks": [psvc.task_to_dict(t) for t in tasks]}


@demo_pursuit_router.post(
    "/{org_id}/pursuits/{pursuit_id}/tasks",
    status_code=status.HTTP_201_CREATED,
)
def demo_create_task(
    org_id: uuid.UUID,
    pursuit_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: TaskCreateBody,
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    try:
        row = psvc.create_task(
            db,
            org=org,
            org_type=ctx.org_type,
            pursuit_id=pursuit_id,
            title=body.title,
            description=body.description,
            due_at=body.due_at,
            actor_id=actor_id,
        )
        db.commit()
        db.refresh(row)
    except psvc.PursuitNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return psvc.task_to_dict(row)


@demo_pursuit_router.patch("/{org_id}/pursuits/{pursuit_id}/tasks/{task_id}")
def demo_patch_task(
    org_id: uuid.UUID,
    pursuit_id: uuid.UUID,
    task_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: TaskPatchBody,
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    raw = body.model_dump(exclude_unset=True)
    patch: dict[str, Any] = {}
    if "title" in raw:
        patch["title"] = raw["title"]
    if "description" in raw:
        patch["description"] = raw["description"]
    if "status" in raw:
        patch["status"] = raw["status"].value
    if "due_at" in raw:
        patch["due_at"] = raw["due_at"]
    try:
        row = psvc.update_task(
            db,
            org=org,
            org_type=ctx.org_type,
            pursuit_id=pursuit_id,
            task_id=task_id,
            patch=patch,
            actor_id=actor_id,
        )
        db.commit()
        db.refresh(row)
    except psvc.PursuitTaskNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return psvc.task_to_dict(row)


@demo_pursuit_router.get("/{org_id}/pursuits/{pursuit_id}/calendar")
def demo_pursuit_calendar(
    org_id: uuid.UUID,
    pursuit_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, list[dict[str, Any]]]:
    _same_org(org_id, ctx)
    from nativeforge.repositories import pursuits as pr

    p = pr.get_grant_pursuit_scoped(
        session=db,
        pursuit_id=pursuit_id,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )
    if p is None:
        raise HTTPException(status_code=404, detail="pursuit not found")
    rows = pr.list_calendar_for_pursuit(
        session=db,
        pursuit_id=pursuit_id,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )
    return {"events": [psvc.calendar_event_to_dict(r) for r in rows]}


@demo_pursuit_router.post(
    "/{org_id}/pursuits/{pursuit_id}/calendar",
    status_code=status.HTTP_201_CREATED,
)
def demo_create_calendar(
    org_id: uuid.UUID,
    pursuit_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: CalendarCreateBody,
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    try:
        row = psvc.create_calendar_event(
            db,
            org=org,
            org_type=ctx.org_type,
            pursuit_id=pursuit_id,
            kind=body.kind.value,
            title=body.title,
            occurs_at=body.occurs_at,
            notes=body.notes,
            pursuit_task_id=body.pursuit_task_id,
            actor_id=actor_id,
        )
        db.commit()
        db.refresh(row)
    except psvc.PursuitNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except psvc.PursuitTaskNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return psvc.calendar_event_to_dict(row)


@demo_pursuit_router.get("/{org_id}/calendar")
def demo_org_calendar(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    start: Annotated[str, Query(description="ISO-8601 start (inclusive)")],
    end: Annotated[str, Query(description="ISO-8601 end (inclusive)")],
) -> dict[str, list[dict[str, Any]]]:
    _same_org(org_id, ctx)
    try:
        start_at = _parse_iso_datetime(start)
        end_at = _parse_iso_datetime(end)
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail=f"invalid datetime: {e}",
        ) from e
    if end_at < start_at:
        raise HTTPException(status_code=422, detail="end must be >= start")
    events = psvc.list_org_calendar(
        db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
        start_at=start_at,
        end_at=end_at,
    )
    return {"events": events}


# --- Real org routes (same behavior, real isolation headers) ---


@real_pursuit_router.post(
    "/{org_id}/grant-sparks/{spark_id}/pursuit",
    status_code=status.HTTP_201_CREATED,
)
def real_create_pursuit(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: CreatePursuitBody | None = None,
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    try:
        row = psvc.create_pursuit_from_spark(
            db,
            org=org,
            org_type=ctx.org_type,
            spark_id=spark_id,
            actor_id=actor_id,
            notes=body.notes if body else None,
        )
        db.commit()
        db.refresh(row)
    except (psvc.PursuitAlreadyExistsError, psvc.SparkNotScoredError) as e:
        _handle_pursuit_create_exc(e)
    except psvc.GrantSparkNotFoundError as e:
        _handle_pursuit_create_exc(e)

    spark = db.get(NfGrantSpark, row.grant_spark_id)
    title = spark.opportunity_title if spark else None
    return psvc.pursuit_to_dict(row, spark_title=title)


@real_pursuit_router.get("/{org_id}/pursuits")
def real_list_pursuits(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> list[dict[str, Any]]:
    _same_org(org_id, ctx)
    return psvc.list_pursuits(db, org_id=ctx.org_id, org_type=ctx.org_type)


@real_pursuit_router.get("/{org_id}/pursuits/{pursuit_id}")
def real_get_pursuit(
    org_id: uuid.UUID,
    pursuit_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    try:
        return psvc.get_pursuit_detail(
            db,
            org_id=ctx.org_id,
            org_type=ctx.org_type,
            pursuit_id=pursuit_id,
        )
    except psvc.PursuitNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@real_pursuit_router.patch("/{org_id}/pursuits/{pursuit_id}")
def real_patch_pursuit(
    org_id: uuid.UUID,
    pursuit_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: PursuitPatchBody,
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    raw = body.model_dump(exclude_unset=True)
    patch: dict[str, Any] = {}
    if "status" in raw:
        patch["status"] = raw["status"].value
    if "notes" in raw:
        patch["notes"] = raw["notes"]
    try:
        row = psvc.update_pursuit(
            db,
            org=org,
            org_type=ctx.org_type,
            pursuit_id=pursuit_id,
            patch=patch,
            actor_id=actor_id,
        )
        db.commit()
        db.refresh(row)
    except psvc.PursuitNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    spark = db.get(NfGrantSpark, row.grant_spark_id)
    title = spark.opportunity_title if spark else None
    return psvc.pursuit_to_dict(row, spark_title=title)


@real_pursuit_router.get("/{org_id}/pursuits/{pursuit_id}/tasks")
def real_list_tasks(
    org_id: uuid.UUID,
    pursuit_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, list[dict[str, Any]]]:
    _same_org(org_id, ctx)
    from nativeforge.repositories import pursuits as pr

    p = pr.get_grant_pursuit_scoped(
        session=db,
        pursuit_id=pursuit_id,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )
    if p is None:
        raise HTTPException(status_code=404, detail="pursuit not found")
    tasks = pr.list_tasks_for_pursuit(
        session=db,
        pursuit_id=pursuit_id,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )
    return {"tasks": [psvc.task_to_dict(t) for t in tasks]}


@real_pursuit_router.post(
    "/{org_id}/pursuits/{pursuit_id}/tasks",
    status_code=status.HTTP_201_CREATED,
)
def real_create_task(
    org_id: uuid.UUID,
    pursuit_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: TaskCreateBody,
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    try:
        row = psvc.create_task(
            db,
            org=org,
            org_type=ctx.org_type,
            pursuit_id=pursuit_id,
            title=body.title,
            description=body.description,
            due_at=body.due_at,
            actor_id=actor_id,
        )
        db.commit()
        db.refresh(row)
    except psvc.PursuitNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return psvc.task_to_dict(row)


@real_pursuit_router.patch("/{org_id}/pursuits/{pursuit_id}/tasks/{task_id}")
def real_patch_task(
    org_id: uuid.UUID,
    pursuit_id: uuid.UUID,
    task_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: TaskPatchBody,
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    raw = body.model_dump(exclude_unset=True)
    patch: dict[str, Any] = {}
    if "title" in raw:
        patch["title"] = raw["title"]
    if "description" in raw:
        patch["description"] = raw["description"]
    if "status" in raw:
        patch["status"] = raw["status"].value
    if "due_at" in raw:
        patch["due_at"] = raw["due_at"]
    try:
        row = psvc.update_task(
            db,
            org=org,
            org_type=ctx.org_type,
            pursuit_id=pursuit_id,
            task_id=task_id,
            patch=patch,
            actor_id=actor_id,
        )
        db.commit()
        db.refresh(row)
    except psvc.PursuitTaskNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return psvc.task_to_dict(row)


@real_pursuit_router.get("/{org_id}/pursuits/{pursuit_id}/calendar")
def real_pursuit_calendar(
    org_id: uuid.UUID,
    pursuit_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, list[dict[str, Any]]]:
    _same_org(org_id, ctx)
    from nativeforge.repositories import pursuits as pr

    p = pr.get_grant_pursuit_scoped(
        session=db,
        pursuit_id=pursuit_id,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )
    if p is None:
        raise HTTPException(status_code=404, detail="pursuit not found")
    rows = pr.list_calendar_for_pursuit(
        session=db,
        pursuit_id=pursuit_id,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )
    return {"events": [psvc.calendar_event_to_dict(r) for r in rows]}


@real_pursuit_router.post(
    "/{org_id}/pursuits/{pursuit_id}/calendar",
    status_code=status.HTTP_201_CREATED,
)
def real_create_calendar(
    org_id: uuid.UUID,
    pursuit_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: CalendarCreateBody,
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    try:
        row = psvc.create_calendar_event(
            db,
            org=org,
            org_type=ctx.org_type,
            pursuit_id=pursuit_id,
            kind=body.kind.value,
            title=body.title,
            occurs_at=body.occurs_at,
            notes=body.notes,
            pursuit_task_id=body.pursuit_task_id,
            actor_id=actor_id,
        )
        db.commit()
        db.refresh(row)
    except psvc.PursuitNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except psvc.PursuitTaskNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return psvc.calendar_event_to_dict(row)


@real_pursuit_router.get("/{org_id}/calendar")
def real_org_calendar(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    start: Annotated[str, Query(description="ISO-8601 start (inclusive)")],
    end: Annotated[str, Query(description="ISO-8601 end (inclusive)")],
) -> dict[str, list[dict[str, Any]]]:
    _same_org(org_id, ctx)
    try:
        start_at = _parse_iso_datetime(start)
        end_at = _parse_iso_datetime(end)
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail=f"invalid datetime: {e}",
        ) from e
    if end_at < start_at:
        raise HTTPException(status_code=422, detail="end must be >= start")
    events = psvc.list_org_calendar(
        db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
        start_at=start_at,
        end_at=end_at,
    )
    return {"events": events}
