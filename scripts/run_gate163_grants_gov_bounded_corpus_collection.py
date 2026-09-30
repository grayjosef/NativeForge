"""Gate 163 / Block 5B: bounded Grants.gov Search2 → corpus → sparks.

Dry-run by default. With ``--apply``:

1. Demo-org RLS context
2. Warrant + live-fetch check (fail closed)
3. One broad Search2 POST (posted|forecasted, no applicant-class filter)
4. Raw payload persistence
5. Canonical graph + nf_grant_sparks projection
6. Active-source success stamps

``--pass`` selects attempt_number for idempotence proof (1 or 2).
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from nativeforge.db.rls import (  # noqa: E402
    apply_org_rls_gucs,
    reapply_org_rls_after_commit,
)
from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.services.grants_gov_live_corpus_collection_service import (  # noqa: E402
    DEFAULT_BOUNDED_ROWS,
    run_grants_gov_bounded_live_collection,
)

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
SOURCE = "nf-seed-2026-api-grants-gov-search2"
JOB_ID = "gate163-grants-gov-bounded-corpus"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="network + persist")
    parser.add_argument(
        "--pass",
        dest="pass_number",
        type=int,
        default=1,
        choices=(1, 2),
        help="collection pass (attempt_number)",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=DEFAULT_BOUNDED_ROWS,
        help="Search2 rows (bounded batch size)",
    )
    args = parser.parse_args()

    session = SessionLocal()
    try:
        apply_org_rls_gucs(session, DEMO, "demo")
        if args.apply:
            reapply_org_rls_after_commit(session, DEMO, "demo")
        result = run_grants_gov_bounded_live_collection(
            session,
            session,
            organization_id=DEMO,
            org_type="demo",
            source_id=SOURCE,
            job_id=JOB_ID,
            attempt_number=int(args.pass_number),
            rows=int(args.rows),
            dry_run=not args.apply,
        )

        print("=== Grants.gov bounded corpus collection")
        print(f"    source_id     {SOURCE}")
        print(f"    pass          {args.pass_number}")
        print(f"    rows          {args.rows}")
        print(f"    search_body   {json.dumps(result.search_body, sort_keys=True)}")
        print(f"    permitted     {result.permitted}")
        print(f"    dispatched    {result.dispatched}")
        print(f"    http_status   {result.http_status}")
        if result.refusal:
            print(f"    refusal       {result.refusal.reasons}")
        if result.metrics:
            print(f"    metrics       {json.dumps(result.metrics, sort_keys=True)}")
        if result.canonical_metrics:
            subset = {
                k: result.canonical_metrics.get(k)
                for k in (
                    "observations_inserted",
                    "observations_idempotent",
                    "observations_versioned",
                    "observations_rejected",
                    "canonical_created",
                )
            }
            print(f"    canonical     {json.dumps(subset, sort_keys=True)}")
        print(f"    payload_sha   {result.payload_sha256}")
        print(f"    attempt_id    {result.attempt_id}")

        if result.refusal:
            return 1
        if not args.apply:
            print()
            print("DRY RUN. Re-run with --apply to collect.")
            return 0

        if not result.persistence_committed:
            print()
            print("PERSISTENCE NOT FINALIZED — refusing exit 0.", file=sys.stderr)
            return 1
        reapply_org_rls_after_commit(session, DEMO, "demo")
        print()
        print("COMMITTED.")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
