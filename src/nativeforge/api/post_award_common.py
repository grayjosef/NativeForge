"""Gate 139: what the four post-award route modules share.

Gate 134E's lesson, one layer up: 207 hand-written organization resolutions
would have been 207 chances to get the cross-tenant check subtly different, so
there is one dependency. Four hand-written fixture-labellings and four
hand-written repository-result translations would be four chances to get *those*
different, so there is one of each here.

## Controlled dev/demo, and the label is not the caller's

Every row these routes write carries:

```text
is_demo      True
fact_status  demo_fixture
```

forced, not accepted. A caller that supplies either gets a named refusal rather
than an override — the same rule Gate 137 arrived at for `is_demo` on bindings,
after Gate 137A found a verified binding written onto the demo organization
because the caller said it was not one.

What makes this safe is not the label alone: `production_write = not
demo_fixture` in every post-award repository, so a fixture-labelled write needs
neither `customer_auth_live` nor a verified operational binding, and cannot
become a production write by relabelling.

## Demo organizations only

These routers use `require_demo_org_session` and there is deliberately no
real-organization counterpart. `tribal_profile_routes` has both because Gate 134
converted it that way; building a real-org path for awarded grants would create
a route to `aaaaaaaa-…` that nobody has authorized, and Gate 137's boundary
exists precisely because that authorization does not exist.

## Two layers, two questions

```text
require_demo_org_session   which organization IS the caller
guard_same_org_404         does the URL agree
```

A session for organization B requesting organization A's URL gets 404 — which
does not confirm that A exists.

## No update, anywhere

The post-award repositories offer create, read, list and archive. There is no
UPDATE path and this module does not add one:

> "An award is a discrete event: a correction is a new row and the mistaken one
> is archived, so the audit trail shows what was believed and when."

So a status change is expressed as archive-plus-create, and the routes say so
rather than exposing a PATCH that would have to invent one.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, status

from nativeforge.api.org_context import OrgContext
from nativeforge.api.tenant_guard import guard_same_org_404

#: Forced onto every row these routes write. Not parameters.
FIXTURE_FACT_STATUS = "demo_fixture"
FIXTURE_IS_DEMO = True

#: The scope every response carries, so a reader never has to infer which kind
#: of "operational" is meant.
CONTROLLED_SCOPE = "controlled_dev_demo"

#: Fields a caller may not set, because they decide whether a write is a
#: production write or which organization's partition a row lands in.
CALLER_MAY_NOT_SET: tuple[str, ...] = (
    "is_demo",
    "fact_status",
    "organization_id",
    "tenant_id",
    "customer_org_id",
    "organization_profile_id",
    "customer_auth_live",
    "verified_operational_binding",
    "object_store_configured",
)

#: A body field naming any of these is a body trying to store a document, which
#: this gate refuses with a reason rather than a 500.
BODY_STORAGE_FIELDS: tuple[str, ...] = (
    "object_key",
    "object_bucket",
    "object_version",
    "content",
    "body",
    "file",
    "bytes",
    "sha256_digest",
    "content_length",
)

BODY_STORAGE_UNAVAILABLE = "document_body_storage_is_not_configured"


def accountable_identity(db: Any, organization_id: uuid.UUID) -> str:
    """Who this row is attributed to, read from the membership row.

    `OrgContext` carries `org_id` and `org_type` and no principal - it answers
    which organization, not which person. So the identity comes from
    `nf_org_memberships` through Gate 138's resolver, which is also what the
    live database's foreign key requires: `created_by_identity_id` references
    `nf_identities`, and Gate 138 found that out by having a synthetic id
    refused.

    Refusing here rather than letting the repository fail on the constraint
    means the caller gets a reason instead of an IntegrityError.
    """
    from nativeforge.services.customer_persistence_activation_service import (
        resolve_accountable_identity,
    )

    identity = resolve_accountable_identity(
        connection=db.connection(), organization_id=str(organization_id)
    )
    if not identity:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "no_active_membership_identity_to_attribute_the_row_to",
                "organization_id": str(organization_id),
            },
        )
    return identity


def same_org(path_org: uuid.UUID, ctx: OrgContext) -> None:
    """The URL's organization must be the session's. 404, never 403."""
    guard_same_org_404(path_org, ctx, object_type="awarded_grant")


def refuse_caller_supplied(body: Any) -> None:
    """A caller may not decide what kind of write this is.

    Refused by name rather than ignored: a caller that offered one should learn
    it was not honoured, which is the rule Gates 110-113 settled for labels and
    Gate 137 restated for `is_demo`.
    """
    offered = _model_fields(body)
    named = sorted(field for field in CALLER_MAY_NOT_SET if field in offered)
    if named:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "field_is_not_the_callers_to_set",
                "fields": named,
                "because": (
                    "these decide whether a write is a production write, or "
                    "which organization's partition a row lands in"
                ),
            },
        )


def object_store_configured() -> bool:
    """Is there anywhere for a document's bytes to live? Measured, not asserted.

    Gate 141 replaced a literal `False` here and at three envelope sites. It was
    correct - the store is unconfigured - and it was a constant, so configuring
    a bucket would have left every route still telling callers there was none.
    Same family Gate 114A removed for `customer_persistence_live`.

    The answer comes from Gate 127's detector, which asks Gate 96's
    `detect_body_store_mode()`. It reads settings; it opens no socket.
    """
    from nativeforge.services.award_document_store_persistence_validation_service import (  # noqa: E501
        detect_object_store_configured,
    )

    return bool(detect_object_store_configured())


def refuse_body_storage(body: Any) -> None:
    """No bytes. The store is unconfigured and the schema refuses a key."""
    offered = _model_fields(body)
    named = sorted(field for field in BODY_STORAGE_FIELDS if field in offered)
    if named:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": BODY_STORAGE_UNAVAILABLE,
                "fields": named,
                "object_store_configured": object_store_configured(),
                "because": (
                    "nf_award_documents refuses an object_key while no store "
                    "is configured; a document row is a reference and nothing "
                    "more"
                ),
            },
        )


def declared_fields(body: Any) -> dict[str, Any]:
    """Only what the model declares, so a stray extra cannot reach a repository.

    The bodies allow extra fields on purpose - pydantic's default is to DROP an
    unknown field silently, and a silent drop is how a caller comes to believe
    `is_demo: false` was honoured. `refuse_caller_supplied` needs to see it in
    order to refuse it by name.

    Allowing them in means they must not be forwarded: every repository takes
    its fields as keyword arguments and an unknown one is a TypeError. So the
    refusal reads the extras and this reads the declarations.
    """
    if body is None:
        return {}
    dumped = getattr(body, "model_dump", None)
    if not callable(dumped):
        return dict(body) if isinstance(body, dict) else {}
    declared = set(getattr(type(body), "model_fields", {}) or {})
    return {
        key: value
        for key, value in dumped(exclude_unset=True).items()
        if key in declared
    }


def _model_fields(body: Any) -> set[str]:
    if body is None:
        return set()
    if isinstance(body, dict):
        return set(body)
    dumped = getattr(body, "model_dump", None)
    if callable(dumped):
        # `exclude_unset`, so a default the caller never mentioned is not
        # reported as something they tried to set.
        return set(dumped(exclude_unset=True))
    return set()


def fixture_fields() -> dict[str, Any]:
    """The labelling, in one place."""
    return {"is_demo": FIXTURE_IS_DEMO, "fact_status": FIXTURE_FACT_STATUS}


def refuse_if_blocked(result: dict[str, Any], *, wrote: str) -> dict[str, Any]:
    """Turn a repository refusal into a 422 that names it.

    The repository's own `blocked_reasons` reach the caller unchanged. They are
    the vocabulary the whole campaign has been building and paraphrasing them
    into an HTTP message would be a second, worse contract.
    """
    if not result.get("rows_written"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": f"{wrote}_was_not_written",
                "blocked_reasons": sorted(result.get("blocked_reasons") or []),
                "scope": CONTROLLED_SCOPE,
            },
        )
    return result


def refuse_if_absent(result: dict[str, Any], *, what: str) -> dict[str, Any]:
    """A read that found nothing is a 404, whichever organization owns it.

    404 rather than 403 for the same reason `guard_same_org_404` uses it: a
    different status for "exists but is not yours" confirms it exists.
    """
    if not result.get("rows_read"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": f"{what}_not_found"},
        )
    return result


def envelope(payload: dict[str, Any], **extra: Any) -> dict[str, Any]:
    """Every response says what kind of thing it is talking about."""
    return {
        **payload,
        "scope": CONTROLLED_SCOPE,
        "fact_status": FIXTURE_FACT_STATUS,
        # Constants. These routes make none of these claims.
        "production_write": False,
        "object_store_contacted": False,
        "document_body_written": False,
        "live_source_called": False,
        "email_sent": False,
        **extra,
    }
