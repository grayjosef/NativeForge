"""Backend health and readiness routes (Gate 101C).

`/backend/health` and `/backend/readiness`, deliberately not `/health`: the Vite
preview already serves a static stamped `/health` that answers `ok` whether or
not this process exists, and one question must not have two answers.

Neither route starts a collector, fetches a URL, or claims production readiness.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter

from nativeforge.services.backend_health_readiness_service import (
    build_backend_health,
    build_backend_readiness,
)

router = APIRouter(prefix="/backend", tags=["backend-runtime"])


@router.get("/health")
def backend_health() -> dict[str, Any]:
    """Is this process up, and which code is it running?"""
    return build_backend_health(now=datetime.now(UTC).isoformat())


@router.get("/readiness")
def backend_readiness() -> dict[str, Any]:
    """What is this system allowed to do? Every value bridged from its owner."""
    return build_backend_readiness()
