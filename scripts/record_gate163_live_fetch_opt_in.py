"""Gate 163Y: record the live-fetch opt-in for ONE source.

The last recorded decision before a real request becomes possible. Everything
else Gate 163 built refuses without it.

Dry-run by default. `--apply` writes.

## What it refuses

Each of these is a way the opt-in could widen beyond what was authorized, so
each is checked before anything is written rather than trusted to the caller:

```text
a source id that is not the authorized one     refused
the exact-one-source assertion not satisfied   refused
authorization not already approved             refused
an opt-in already recorded for another source  refused
no operator handle                             refused
```

The last one matters most: this is per-source by construction, and an opt-in
for a second source would need a second run, a second handle and a second
deliberate act.

## What it does not do

It does not set `ENV_ALLOW_LIVE_NETWORK`, does not enable a global live mode,
and does not touch the terms, human-review or activation decisions. It records
one signed row of one kind for one source.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import sys
import uuid

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.repositories.source_authorization_decision_repository import (  # noqa: E402
    LIVE_FETCH,
    record_decision,
)
from nativeforge.services.source_authority_service import (  # noqa: E402
    resolve_source_authority,
)
from nativeforge.services.source_authorization_fact_resolver_service import (  # noqa: E402
    resolve_source_authorization_facts,
)
from nativeforge.services.source_live_authorization_service import (  # noqa: E402
    authorize_source_for_live_access,
)
from nativeforge.services.source_live_fetch_opt_in_service import (  # noqa: E402
    describe_opt_in_state,
    is_live_fetch_opted_in,
    opt_in_invariant_failures,
)
from nativeforge.services.source_live_warrant_service import (  # noqa: E402
    WARRANT_SOURCE_COLLECTION,
    evaluate_live_request,
)
from nativeforge.services.source_monitoring_approved_source_service import (  # noqa: E402
    load_registry_rows,
)

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
AUTHORIZED = "nf-seed-2026-api-grants-gov-search2"
API_URL = "https://api.grants.gov/v1/api/search2"

SCOPE = (
    "controlled NativeForge grant discovery via the documented public "
    "Grants.gov search2 API"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--operator-handle", required=True)
    parser.add_argument(
        "--single-source-acknowledged",
        action="store_true",
        help="the operator confirms this opts in exactly one source",
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    refusals: list[str] = []
    source_id = str(args.source_id).strip()
    handle = str(args.operator_handle).strip()

    if source_id != AUTHORIZED:
        refusals.append(
            f"source_id is not the authorized source: {source_id!r} != {AUTHORIZED!r}"
        )
    if not handle:
        refusals.append("no operator handle")
    if not args.single_source_acknowledged:
        refusals.append("--single-source-acknowledged was not given")

    session = SessionLocal()
    try:
        # Gate 166B: the source must already be ACTIVATED before it may be
        # opted in. This replaces a membership test against the constant
        # `AUTHORIZED_SOURCE_IDS`, and it cannot be the derived authorized set
        # - that set requires the live_fetch decision, which is the very row
        # this script is about to write. Asking for it here would make the
        # script refuse to do its own job.
        authority = resolve_source_authority(
            connection=session,
            organization_id=DEMO,
            source_id=source_id,
            registered=source_id in load_registry_rows(),
        )
        if authority.get("state") not in ("activated", "live_opted_in"):
            refusals.append(
                "source is not activated, so it may not be opted in: "
                f"state={authority.get('state')} reasons={authority.get('reasons')}"
            )

        # The exact-one-source assertion, re-made here. The phase that proved
        # it ran in a different process, and an opt-in that trusts a previous
        # process is an opt-in nobody checked.
        real_ids = sorted(load_registry_rows())
        unblocked = []
        for candidate in real_ids:
            resolution = resolve_source_authorization_facts(
                connection=session, organization_id=DEMO, source_id=candidate
            )
            pending = sorted(
                name
                for name, fact in (resolution.get("resolved_facts") or {}).items()
                if fact.get("fact_status") != "recorded"
            )
            if pending in ([], ["runtime_status"]):
                unblocked.append(candidate)
        if unblocked != [AUTHORIZED]:
            refusals.append(
                f"exactly-one-source assertion failed: unblocked={unblocked}"
            )

        # And the source must already be APPROVED with fresh runtime evidence.
        authorization = authorize_source_for_live_access(
            connection=session,
            organization_id=DEMO,
            source_id=AUTHORIZED,
            exercise_runtime=True,
        )
        if str(authorization.get("authorization_status") or "") != "approved":
            refusals.append(
                "authorization is not approved: "
                f"{authorization.get('authorization_status')} "
                f"{authorization.get('refusal_reasons')}"
            )

        # No other source may already be opted in.
        state = describe_opt_in_state(connection=session, organization_id=DEMO)
        others = [
            entry["source_id"]
            for entry in state["opted_in_sources"]
            if entry["source_id"] != AUTHORIZED
        ]
        if others:
            refusals.append(f"another source is already opted in: {others}")

        print("=== Gate 163Y live-fetch opt-in")
        print(f"    source_id            {source_id}")
        print(f"    operator             {handle}")
        print(f"    scope                {SCOPE}")
        print(f"    authorization        {authorization.get('authorization_status')}")
        print(f"    unblocked sources    {unblocked}")
        print(f"    already opted in     {state['opted_in_count']}")
        print(f"    mode                 {'APPLY' if args.apply else 'DRY RUN'}")
        print()

        if refusals:
            print("REFUSED:")
            for refusal in refusals:
                print(f"    - {refusal}")
            return 1

        if not args.apply:
            print("Dry run only. Re-run with --apply to record the opt-in.")
            return 0

        now = dt.datetime.now(dt.UTC)
        fingerprint = hashlib.sha256(
            f"gate163:live_fetch_opt_in:{AUTHORIZED}:{handle}".encode()
        ).hexdigest()

        written = record_decision(
            connection=session,
            organization_id=DEMO,
            source_id=AUTHORIZED,
            decision_kind=LIVE_FETCH,
            decision="approved",
            # Migration 0052 requires exactly this for a live_fetch row: the
            # guard said nothing about terms, and recording a terms status
            # would imply it had.
            guard_status="NOT_APPLICABLE",
            reviewed_by=f"operator:{handle}",
            reviewed_at=now,
            review_authority="gate163_human_activation",
            evidence_fingerprint=fingerprint,
            evidence_ref="gate163:operator_live_fetch_opt_in",
            notes_classification="unclassified",
            # A member of FACT_STATUSES, and the same one MAYHEM's terms and
            # human-review decisions for this source carry. An invented value
            # is refused outright, which is how it should be: `operator_decision`
            # looked reasonable and was not in the vocabulary.
            fact_status="tenant_supplied",
            now=now,
        )
        session.commit()

        if written.get("blocked_reasons"):
            print(f"REFUSED BY THE REPOSITORY: {written['blocked_reasons']}")
            return 1

        # ---- read it back, and prove it is the only one ----------------
        opted = is_live_fetch_opted_in(
            connection=session, organization_id=DEMO, source_id=AUTHORIZED
        )
        state = describe_opt_in_state(connection=session, organization_id=DEMO)
        failures = opt_in_invariant_failures(state)

        print("RECORDED.")
        print(f"    opted in             {opted}")
        print(f"    opted_in_count       {state['opted_in_count']}")
        listed = [entry["source_id"] for entry in state["opted_in_sources"]]
        print(f"    opted_in_sources     {listed}")
        print(f"    invariant failures   {failures or 'clean'}")

        # And the collection warrant must now be valid for search2 specifically.
        warrant = evaluate_live_request(
            warrant_kind=WARRANT_SOURCE_COLLECTION,
            authorized_source_id=AUTHORIZED,
            request_url=API_URL,
            method="POST",
            connection=session,
            organization_id=DEMO,
        )
        print(f"    collection warrant   permitted={warrant['permitted']}")
        print(f"    refusal_reasons      {warrant['refusal_reasons'] or 'none'}")

        if not opted or state["opted_in_count"] != 1 or failures:
            return 1
        return 0 if warrant["permitted"] else 1
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
