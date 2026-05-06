"""Request-scoped organization context (demo vs real)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from nativeforge.lib.demo_isolation import OrgType


@dataclass(frozen=True, slots=True)
class OrgContext:
    """Authenticated user's current org; `org_type` matches demo allowlist (NF-001)."""

    org_id: uuid.UUID
    org_type: OrgType
