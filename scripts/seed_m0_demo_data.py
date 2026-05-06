#!/usr/bin/env python3
"""Insert deterministic M0 operator org rows (organizations table only).

Safe scope:
- Fixed UUIDs documented in docs/m0-demo-runbook.md — no random customer-like data.
- Idempotent: skips rows that already exist; fails if an id exists with wrong org_type.

Requires DATABASE_URL and an applied schema (alembic upgrade head).
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SRC = ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from sqlalchemy import select  # noqa: E402

from nativeforge.db.models import Organization  # noqa: E402
from nativeforge.db.session import SessionLocal  # noqa: E402

# Canonical M0 demo walkthrough IDs (docs/m0-demo-runbook.md).
M0_REAL_ORG_ID = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
M0_DEMO_ORG_ID = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")


def main() -> int:
    pairs: tuple[tuple[uuid.UUID, str], ...] = (
        (M0_REAL_ORG_ID, "real"),
        (M0_DEMO_ORG_ID, "demo"),
    )

    with SessionLocal() as s:
        for oid, org_type in pairs:
            existing = s.scalar(select(Organization).where(Organization.id == oid))
            if existing is None:
                s.add(Organization(id=oid, org_type=org_type))
                print(f"inserted organizations row id={oid} org_type={org_type}")
            elif existing.org_type != org_type:
                print(
                    f"error: org {oid} exists with org_type={existing.org_type!r}, "
                    f"expected {org_type!r}",
                    file=sys.stderr,
                )
                return 1
            else:
                print(f"skip (exists): id={oid} org_type={org_type}")

        s.commit()

    print()
    print("Use these with X-NF-Org-Id and matching API plane:")
    print(f"  real  plane + organizations.org_type=real  -> {M0_REAL_ORG_ID}")
    print(f"  demo  plane + organizations.org_type=demo -> {M0_DEMO_ORG_ID}")
    print()
    print("Example trust manifest (demo):")
    print(
        "  curl -sS -H "
        f"'X-NF-Org-Id: {M0_DEMO_ORG_ID}' "
        f"'http://127.0.0.1:8000/v1/nf/demo/orgs/{M0_DEMO_ORG_ID}/trust/manifest'"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
