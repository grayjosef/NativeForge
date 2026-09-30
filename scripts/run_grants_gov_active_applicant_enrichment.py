"""Bounded Grants.gov fetchOpportunity applicant eligibility enrichment."""

from __future__ import annotations

import argparse
import json
import sys

sys.path.insert(0, "src")

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.services.grants_gov_detail_enrichment_service import (  # noqa: E402
    DEFAULT_BOUND,
    run_bounded_active_applicant_enrichment,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Perform live fetchOpportunity calls and persist applicant provenance",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_BOUND,
        help="Max active opportunities to enrich per run",
    )
    args = parser.parse_args()

    session = SessionLocal()
    try:
        stats = run_bounded_active_applicant_enrichment(
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
