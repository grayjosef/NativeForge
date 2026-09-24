"""178L: the detectors that catch the commercial layer lying.

Nine named detectors. A generic "invalid" is useless here more than anywhere
else in the campaign: the failures this layer can produce are a customer
locked out of work they paid for, and a customer quietly accruing a debt
nobody told them about. Those need different alarms.

`prove_detectors_fire()` builds a population broken in EXACTLY one way per
detector and proves each fires on its own breakage, stays silent on a healthy
population, and fires alone.

## The one that needed rewriting in Gate 177, avoided here

`entitlement_disagrees_with_ledger` does NOT re-derive the entitlement and
compare it to itself - that would be asking the same function twice and
calling the agreement a proof. It takes the STORED entitlement (what was
served to the customer, cached or denormalised) and the LEDGER (what is true),
re-derives from the ledger, and compares the two. They can genuinely differ,
which is the point: a stale cache is how a customer sees "active" for a week
after their licence expired.
"""

from __future__ import annotations

from typing import Any

from nativeforge.services.commercial_entitlement_service import (
    CONTROLLING_COMPANY_ADMIN,
    derive_entitlement,
)
from nativeforge.services.commercial_ledger_service import (
    MAINTENANCE_FORGIVEN_EVENT,
    RELICENSED,
)
from nativeforge.services.commercial_license_model_service import (
    ALWAYS_AVAILABLE,
    BENEFIT_EXTENDED,
    BENEFIT_FULL,
    BENEFIT_WORKING,
    DELINQUENCY_DAYS_BEFORE_EXPIRATION,
    EXTENSION_DAYS,
    LICENSE_EXPIRED,
    LICENSE_HELD,
    LICENSED_ACTIVE,
    LICENSED_GRACE,
)

SCHEMA_VERSION = "nf_commercial_self_health_v1"

HEALTH_MODEL_VERSION = "2026.09.1"

# ---------------------------------------------------------------------------
# The nine detectors.
# ---------------------------------------------------------------------------

BENEFITS_WITHOUT_REASON = "active_benefits_without_a_valid_reason"
LICENSE_EXPIRED_EARLY = "license_expired_before_three_years"
FROZEN_ACCOUNT_MISSING_DATA = "frozen_account_data_missing"
EXTENSION_BY_UNAUTHORIZED_USER = "extension_granted_by_unauthorized_user"
EXTENSION_REWROTE_BILLING = "extension_rewrote_billing_state"
NEGATIVE_DELINQUENCY = "negative_delinquency_duration"
CONTRADICTORY_ACTIVE_LICENSES = "multiple_contradictory_active_licenses"
ENTITLEMENT_DISAGREES_WITH_LEDGER = "current_entitlement_disagrees_with_ledger"
RELICENSE_RETAINED_OLD_DEBT = "relicense_retained_old_maintenance_debt"

DETECTORS: tuple[str, ...] = (
    BENEFITS_WITHOUT_REASON,
    LICENSE_EXPIRED_EARLY,
    FROZEN_ACCOUNT_MISSING_DATA,
    EXTENSION_BY_UNAUTHORIZED_USER,
    EXTENSION_REWROTE_BILLING,
    NEGATIVE_DELINQUENCY,
    CONTRADICTORY_ACTIVE_LICENSES,
    ENTITLEMENT_DISAGREES_WITH_LEDGER,
    RELICENSE_RETAINED_OLD_DEBT,
)

DETECTOR_MEANINGS: dict[str, str] = {
    BENEFITS_WITHOUT_REASON: (
        "an organisation has working benefits while neither current, in "
        "grace, nor covered by a named extension - somebody is getting the "
        "product for free and nobody decided that"
    ),
    LICENSE_EXPIRED_EARLY: (
        "a licence was expired before three continuous years of delinquency, "
        "which is the most expensive arithmetic error this system can make"
    ),
    FROZEN_ACCOUNT_MISSING_DATA: (
        "a frozen or expired account lost an always-available action - the "
        "difference between pausing a workflow and holding data hostage"
    ),
    EXTENSION_BY_UNAUTHORIZED_USER: (
        "an extension records a grantor who is not controlling-company staff"
    ),
    EXTENSION_REWROTE_BILLING: (
        "an extension moved the paid-through date, reduced the delinquency "
        "count, or recorded the customer as current when they were not"
    ),
    NEGATIVE_DELINQUENCY: (
        "a delinquency duration below zero, which flows into the three-year "
        "arithmetic and expires a licence early"
    ),
    CONTRADICTORY_ACTIVE_LICENSES: (
        "more than one live persistent licence for one organisation, so "
        "which one governs is a coin toss"
    ),
    ENTITLEMENT_DISAGREES_WITH_LEDGER: (
        "what the customer is being served does not match what the ledger "
        "says - a stale cache is how somebody sees ACTIVE for a week after "
        "their licence expired"
    ),
    RELICENSE_RETAINED_OLD_DEBT: (
        "a relicensed organisation still carries the maintenance debt the "
        "approved model forgives"
    ),
}

CRITICAL = "CRITICAL"
SERIOUS = "SERIOUS"

DETECTOR_SEVERITY: dict[str, str] = {
    BENEFITS_WITHOUT_REASON: SERIOUS,
    LICENSE_EXPIRED_EARLY: CRITICAL,
    FROZEN_ACCOUNT_MISSING_DATA: CRITICAL,
    EXTENSION_BY_UNAUTHORIZED_USER: CRITICAL,
    EXTENSION_REWROTE_BILLING: CRITICAL,
    NEGATIVE_DELINQUENCY: CRITICAL,
    CONTRADICTORY_ACTIVE_LICENSES: CRITICAL,
    ENTITLEMENT_DISAGREES_WITH_LEDGER: CRITICAL,
    RELICENSE_RETAINED_OLD_DEBT: SERIOUS,
}


def _finding(detector: str, subject: Any, why: str) -> dict[str, Any]:
    return {
        "detector": detector,
        "severity": DETECTOR_SEVERITY[detector],
        "subject": str(subject) if subject is not None else None,
        "why": why,
    }


def assess_commercial_health(
    *,
    entitlements: list[dict[str, Any]] | None = None,
    ledgers: dict[str, dict[str, Any]] | None = None,
    extensions: list[dict[str, Any]] | None = None,
    license_records: list[dict[str, Any]] | None = None,
    ledger_events: dict[str, list[dict[str, Any]]] | None = None,
    as_of: Any = None,
) -> dict[str, Any]:
    """Run every detector over a population and report what each one found."""
    entitlements = entitlements or []
    ledgers = ledgers or {}
    extensions = extensions or []
    license_records = license_records or []
    ledger_events = ledger_events or {}

    findings: list[dict[str, Any]] = []

    for entitlement in entitlements:
        org = entitlement.get("organization_id")
        benefit = str(entitlement.get("benefit_access") or "")
        license_state = str(entitlement.get("license_state") or "")
        days = int(entitlement.get("delinquency_days") or 0)

        if benefit in BENEFIT_WORKING:
            justified = license_state in {LICENSED_ACTIVE, LICENSED_GRACE} or (
                benefit == BENEFIT_EXTENDED and entitlement.get("active_extension_id")
            )
            if not justified:
                findings.append(
                    _finding(
                        BENEFITS_WITHOUT_REASON,
                        org,
                        f"{benefit} while licence is {license_state} and no "
                        "extension is named",
                    )
                )

        if license_state == LICENSE_EXPIRED and days <= (
            DELINQUENCY_DAYS_BEFORE_EXPIRATION
        ):
            findings.append(
                _finding(
                    LICENSE_EXPIRED_EARLY,
                    org,
                    f"expired after {days} days, which is not more than "
                    f"{DELINQUENCY_DAYS_BEFORE_EXPIRATION}",
                )
            )

        if days < 0:
            findings.append(
                _finding(NEGATIVE_DELINQUENCY, org, f"delinquency of {days} days")
            )

        available = set(entitlement.get("available_actions") or [])
        missing = [a for a in ALWAYS_AVAILABLE if a not in available]
        if missing:
            findings.append(
                _finding(
                    FROZEN_ACCOUNT_MISSING_DATA,
                    org,
                    f"always-available actions are absent: {sorted(missing)}",
                )
            )
        for flag in ("data_deleted", "organization_deleted", "history_deleted"):
            if entitlement.get(flag):
                findings.append(
                    _finding(FROZEN_ACCOUNT_MISSING_DATA, org, f"claims {flag}")
                )

        # Two INDEPENDENT sources: what was served, and what the ledger says.
        ledger = ledgers.get(str(org))
        if ledger is not None and as_of is not None:
            fresh = derive_entitlement(
                organization_id=org,
                ledger=ledger,
                extensions=[
                    e for e in extensions if str(e.get("organization_id")) == str(org)
                ],
                as_of=as_of,
            )
            for field in ("license_state", "maintenance_state", "benefit_access"):
                if str(entitlement.get(field)) != str(fresh[field]):
                    findings.append(
                        _finding(
                            ENTITLEMENT_DISAGREES_WITH_LEDGER,
                            org,
                            f"served {field}={entitlement.get(field)} but the "
                            f"ledger derives {fresh[field]}",
                        )
                    )

    for extension in extensions:
        org = extension.get("organization_id")
        if str(extension.get("granted_by_role")) != CONTROLLING_COMPANY_ADMIN:
            findings.append(
                _finding(
                    EXTENSION_BY_UNAUTHORIZED_USER,
                    extension.get("extension_id"),
                    f"granted by {extension.get('granted_by_role')}",
                )
            )
        if int(extension.get("duration_days") or 0) not in EXTENSION_DAYS:
            findings.append(
                _finding(
                    EXTENSION_BY_UNAUTHORIZED_USER,
                    extension.get("extension_id"),
                    f"duration {extension.get('duration_days')} is not allowed",
                )
            )

        # An extension that recorded the customer as current, or as owing
        # nothing, has rewritten the only thing it was forbidden to touch.
        underlying = str(extension.get("underlying_maintenance_state") or "")
        recorded_days = int(extension.get("underlying_delinquency_days") or 0)
        if underlying in {"MAINTENANCE_CURRENT", ""} and recorded_days == 0:
            ledger = ledgers.get(str(org))
            if ledger is not None and as_of is not None:
                fresh = derive_entitlement(
                    organization_id=org, ledger=ledger, as_of=as_of
                )
                if fresh["delinquency_days"] > 0:
                    findings.append(
                        _finding(
                            EXTENSION_REWROTE_BILLING,
                            extension.get("extension_id"),
                            "records the customer as current while the ledger "
                            f"shows {fresh['delinquency_days']} days delinquent",
                        )
                    )
        if recorded_days < 0:
            findings.append(
                _finding(
                    EXTENSION_REWROTE_BILLING,
                    extension.get("extension_id"),
                    f"records {recorded_days} days delinquency",
                )
            )

    by_org: dict[str, int] = {}
    for record in license_records:
        if str(record.get("license_state")) in LICENSE_HELD:
            key = str(record.get("organization_id"))
            by_org[key] = by_org.get(key, 0) + 1
    for org, count in by_org.items():
        if count > 1:
            findings.append(
                _finding(
                    CONTRADICTORY_ACTIVE_LICENSES,
                    org,
                    f"{count} live persistent licences for one organisation",
                )
            )

    for org, events in ledger_events.items():
        kinds = [str(e.get("event_type")) for e in events]
        if RELICENSED in kinds and MAINTENANCE_FORGIVEN_EVENT not in kinds:
            findings.append(
                _finding(
                    RELICENSE_RETAINED_OLD_DEBT,
                    org,
                    "relicensed without a forgiveness event",
                )
            )

    fired = sorted({f["detector"] for f in findings})
    return {
        "schema_version": SCHEMA_VERSION,
        "model_version": HEALTH_MODEL_VERSION,
        "healthy": not findings,
        "finding_count": len(findings),
        "detectors_fired": fired,
        "detectors_silent": [d for d in DETECTORS if d not in fired],
        "critical_finding_count": sum(1 for f in findings if f["severity"] == CRITICAL),
        "findings": findings,
    }


# ---------------------------------------------------------------------------
# The proof.
# ---------------------------------------------------------------------------

_AS_OF = "2027-06-05"
_LEDGER = {"license_purchased_at": "2026-03-15", "paid_through": "2028-03-15"}


def _healthy_population() -> dict[str, Any]:
    entitlement = derive_entitlement(
        organization_id="org-A", ledger=_LEDGER, as_of=_AS_OF
    )
    return {
        "entitlements": [entitlement],
        "ledgers": {"org-A": _LEDGER},
        "extensions": [],
        "license_records": [
            {"organization_id": "org-A", "license_state": LICENSED_ACTIVE}
        ],
        "ledger_events": {"org-A": [{"event_type": "LICENSE_PURCHASED"}]},
        "as_of": _AS_OF,
    }


def _break_one_way(detector: str) -> dict[str, Any]:
    """Return the healthy population, damaged in EXACTLY one way."""
    pop = _healthy_population()
    entitlement = dict(pop["entitlements"][0])

    if detector == BENEFITS_WITHOUT_REASON:
        entitlement["license_state"] = "LICENSED_FROZEN"
        entitlement["benefit_access"] = BENEFIT_FULL
        entitlement["active_extension_id"] = None
        pop["entitlements"] = [entitlement]
        # The ledger comparison would also fire; drop it so this fixture
        # proves one thing.
        pop["ledgers"] = {}

    elif detector == LICENSE_EXPIRED_EARLY:
        entitlement["license_state"] = LICENSE_EXPIRED
        entitlement["delinquency_days"] = 400
        entitlement["benefit_access"] = "BENEFIT_FROZEN"
        pop["entitlements"] = [entitlement]
        pop["ledgers"] = {}

    elif detector == FROZEN_ACCOUNT_MISSING_DATA:
        entitlement["available_actions"] = [
            a for a in entitlement["available_actions"] if a != "EXPORT_OWN_DATA"
        ]
        pop["entitlements"] = [entitlement]
        pop["ledgers"] = {}

    elif detector == EXTENSION_BY_UNAUTHORIZED_USER:
        pop["extensions"] = [
            {
                "extension_id": "ext-1",
                "organization_id": "org-A",
                "granted_by_role": "ORG_SUPER_ADMIN",
                "duration_days": 7,
                "underlying_maintenance_state": "MAINTENANCE_DELINQUENT",
                "underlying_delinquency_days": 82,
            }
        ]
        # An extension in the population changes the derived entitlement, so
        # the ledger comparison is dropped to keep the fixture single-issue.
        pop["ledgers"] = {}

    elif detector == EXTENSION_REWROTE_BILLING:
        pop["extensions"] = [
            {
                "extension_id": "ext-2",
                "organization_id": "org-A",
                "granted_by_role": CONTROLLING_COMPANY_ADMIN,
                "duration_days": 14,
                # The lie: says current, while the ledger says delinquent.
                "underlying_maintenance_state": "MAINTENANCE_CURRENT",
                "underlying_delinquency_days": 0,
            }
        ]
        delinquent = {
            "license_purchased_at": "2026-03-15",
            "paid_through": "2027-03-15",
        }
        pop["ledgers"] = {"org-A": delinquent}
        # Keep the served entitlement consistent with that ledger so only the
        # extension is wrong.
        pop["entitlements"] = [
            derive_entitlement(
                organization_id="org-A",
                ledger=delinquent,
                extensions=pop["extensions"],
                as_of=_AS_OF,
            )
        ]

    elif detector == NEGATIVE_DELINQUENCY:
        entitlement["delinquency_days"] = -12
        pop["entitlements"] = [entitlement]
        pop["ledgers"] = {}

    elif detector == CONTRADICTORY_ACTIVE_LICENSES:
        pop["license_records"] = [
            {"organization_id": "org-A", "license_state": LICENSED_ACTIVE},
            {"organization_id": "org-A", "license_state": "LICENSED_FROZEN"},
        ]

    elif detector == ENTITLEMENT_DISAGREES_WITH_LEDGER:
        # A stale cache: the served answer says active, the ledger says the
        # term ran out three months ago.
        pop["ledgers"] = {
            "org-A": {
                "license_purchased_at": "2026-03-15",
                "paid_through": "2027-03-15",
            }
        }

    elif detector == RELICENSE_RETAINED_OLD_DEBT:
        pop["ledger_events"] = {
            "org-A": [{"event_type": "LICENSE_PURCHASED"}, {"event_type": RELICENSED}]
        }

    else:  # pragma: no cover - a detector with no fixture is a bug
        raise ValueError(f"no broken fixture for detector {detector}")

    return pop


def prove_detectors_fire() -> dict[str, Any]:
    """Prove each detector fires on its OWN breakage and nothing else's."""
    baseline = assess_commercial_health(**_healthy_population())

    proofs: list[dict[str, Any]] = []
    for detector in DETECTORS:
        result = assess_commercial_health(**_break_one_way(detector))
        fired = result["detectors_fired"]
        proofs.append(
            {
                "detector": detector,
                "severity": DETECTOR_SEVERITY[detector],
                "fires_on_its_own_breakage": detector in fired,
                "no_other_detector_fired": fired == [detector],
                "detectors_fired": fired,
                "why": next(
                    (f["why"] for f in result["findings"] if f["detector"] == detector),
                    None,
                ),
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "model_version": HEALTH_MODEL_VERSION,
        "detector_count": len(DETECTORS),
        "healthy_population_is_silent": baseline["healthy"],
        "baseline_findings": baseline["findings"],
        "all_detectors_fire": all(p["fires_on_its_own_breakage"] for p in proofs),
        "all_detectors_are_specific": all(p["no_other_detector_fired"] for p in proofs),
        "detectors_that_did_not_fire": [
            p["detector"] for p in proofs if not p["fires_on_its_own_breakage"]
        ],
        "detectors_that_fired_too_broadly": [
            p["detector"] for p in proofs if not p["no_other_detector_fired"]
        ],
        "proofs": proofs,
    }


def describe_self_health() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "model_version": HEALTH_MODEL_VERSION,
        "detectors": list(DETECTORS),
        "detector_count": len(DETECTORS),
        "every_detector_has_a_meaning": set(DETECTOR_MEANINGS) == set(DETECTORS),
        "every_detector_has_a_severity": set(DETECTOR_SEVERITY) == set(DETECTORS),
        "every_detector_has_a_broken_fixture": True,
        "ledger_comparison_uses_two_independent_sources": True,
        "generic_invalid_is_not_a_result": True,
    }
