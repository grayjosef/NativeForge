"""Reproject Gate 173 for the active corpus (material input fingerprint)."""

from __future__ import annotations

import argparse
import json
import sys

sys.path.insert(0, "src")

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.services.gate173_active_corpus_projection_service import (  # noqa: E402
    DEFAULT_BOUND,
    run_bounded_active_relevance_reassessment,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist reassessed Gate 173 assessments",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_BOUND,
        help="Max active opportunities per run",
    )
    args = parser.parse_args()

    session = SessionLocal()
    try:
        stats = run_bounded_active_relevance_reassessment(
            session.connection(),
            limit=int(args.limit),
            dry_run=not args.apply,
        )
        print(json.dumps(stats, indent=2, sort_keys=True, default=str))
        if args.apply:
            session.commit()
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
