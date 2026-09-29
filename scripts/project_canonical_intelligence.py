"""Project canonical graph into Gate 173–175 intelligence tables (no network)."""

from __future__ import annotations

import argparse
import json
import sys

sys.path.insert(0, "src")

from nativeforge.db.session import SessionLocal
from nativeforge.services.canonical_intelligence_projection_service import (
    project_all_canonical_opportunities,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    session = SessionLocal()
    try:
        out = project_all_canonical_opportunities(
            session.connection(),
            limit=args.limit,
            dry_run=args.dry_run,
        )
        if not args.dry_run:
            session.commit()
        print(json.dumps(out, default=str, indent=2))
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
