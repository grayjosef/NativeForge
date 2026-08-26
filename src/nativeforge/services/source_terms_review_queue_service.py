"""Source terms / legal review queue (Gate 93F).

Gate 90 flagged the rows. Gate 92 counted them. Neither produced a **work
list** — 158 sources carried a blocker with no reviewer, no review status that
could ever change, and no record of the four terms pages whose text could not be
retrieved at all.

This turns those flags into a queue. It does not review anything, and it does
not activate anything: every item leaves with ``review_status: pending`` and
``automation_blocked: True``.

## The four SPA terms pages are queue items, not footnotes

grants.gov, regulations.gov, usaspending.gov and reporter.nih.gov all serve
their terms pages client-side, so the research pass retrieved no policy text
from any of them. **"No terms found" is not "no terms exist."** They are seeded
into the queue as explicit items with ``risk_type: terms_text_unretrievable``,
because an unread policy that nobody is tracking is indistinguishable from a
policy that was read and cleared.

## SAM.gov is a credential item, not a terms item

Its terms are clear: scraping is prohibited, the API is the sanctioned path.
What blocks it is a *credential and role* decision — 10 requests/day without a
SAM role, 1,000 with one. It is seeded separately so the decision has an owner
rather than being filed under "legal".

## Deterministic

Items are sorted by ``(priority, source_id)`` and the id is derived from the
source id, so the same registry produces byte-identical output. Nothing depends
on iteration order, a timestamp, or a random id — the queue is committed as an
artifact and compared against a fresh generation.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_source_terms_review_queue_v1"

RISK_TYPES = frozenset(
    {
        "terms_review_required",
        "human_review_only",
        "login_required",
        "credential_and_role_required",
        "terms_text_unretrievable",
    }
)

REVIEW_STATUSES = frozenset(
    {"pending", "in_review", "approved", "rejected", "deferred"}
)

# Nothing in this gate produces anything but `pending`. An invariant holds it.
TERMINAL_APPROVING_STATUSES = frozenset({"approved"})

QUEUE_TERMS_STATUSES = frozenset({"TERMS_REVIEW_REQUIRED", "HUMAN_REVIEW_ONLY"})

# Priority 1 is most urgent. Derived from the registry's own tier where present.
DEFAULT_PRIORITY = 3

# The four terms pages that are Ember/React SPAs and served no policy text to
# the research pass. Seeded regardless of what the registry says, because their
# absence from the registry's risk columns is precisely the problem.
SPA_TERMS_PAGES: tuple[tuple[str, str, str], ...] = (
    (
        "SPA-TERMS-GRANTS-GOV",
        "Grants.gov site terms",
        "https://www.grants.gov/",
    ),
    (
        "SPA-TERMS-REGULATIONS-GOV",
        "Regulations.gov terms and user notice",
        "https://www.regulations.gov/",
    ),
    (
        "SPA-TERMS-USASPENDING",
        "USAspending.gov about/terms",
        "https://www.usaspending.gov/",
    ),
    (
        "SPA-TERMS-REPORTER-NIH",
        "NIH RePORTER terms of use",
        "https://reporter.nih.gov/",
    ),
)

SAM_CREDENTIAL_ITEM = (
    "SAM-CREDENTIAL-ROLE",
    "SAM.gov API key and role approval",
    "https://sam.gov/profile/details",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _priority_from_tier(tier: Any) -> int:
    text = str(tier or "").strip()
    for n in (1, 2, 3, 4, 5):
        if text in {f"Tier {n}", str(n)}:
            return n
    return DEFAULT_PRIORITY


def _item(
    *,
    source_id: str,
    source_name: Any,
    risk_type: str,
    reason: str,
    priority: int,
    automation_blocked: bool,
    human_review_only: bool,
    credential_required: bool,
    terms_url_or_note: Any,
) -> dict[str, Any]:
    return {
        "review_item_id": f"REVIEW-{source_id}",
        "source_id": source_id,
        "source_name": source_name,
        "risk_type": risk_type,
        "review_status": "pending",
        "review_required_reason": reason,
        "automation_blocked": automation_blocked,
        "human_review_only": human_review_only,
        "credential_required": credential_required,
        "terms_url_or_note": terms_url_or_note,
        "priority": priority,
    }


def build_terms_review_queue(
    *, seeds: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Registry seed rows in, deterministic review queue out."""
    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    for seed in seeds or []:
        source_id = str(seed.get("source_id") or "").strip()
        if not source_id or source_id in seen:
            continue

        terms_status = seed.get("terms_status") or "UNKNOWN"
        human_only = bool(seed.get("human_review_only"))
        login_resolved = str(seed.get("requires_login_resolved") or "").strip()
        if not login_resolved:
            login_resolved = "yes" if seed.get("requires_login") == "Yes" else ""

        # Deny by default: a conditional login is a login until reviewed.
        login_blocks = login_resolved in {"yes", "conditional"}

        if human_only or terms_status == "HUMAN_REVIEW_ONLY":
            risk_type = "human_review_only"
            reason = "terms permit human access only; automation is not available"
        elif terms_status == "TERMS_REVIEW_REQUIRED":
            risk_type = "terms_review_required"
            reason = "terms carry an obligation or restriction needing legal review"
        elif login_blocks:
            risk_type = "login_required"
            reason = f"access is login-gated (resolved: {login_resolved})"
        else:
            continue

        seen.add(source_id)
        items.append(
            _item(
                source_id=source_id,
                source_name=seed.get("source_name"),
                risk_type=risk_type,
                reason=reason,
                priority=_priority_from_tier(seed.get("priority_tier")),
                automation_blocked=True,
                human_review_only=risk_type == "human_review_only",
                credential_required=login_blocks,
                terms_url_or_note=seed.get("url"),
            )
        )

    # The four SPA terms pages, always.
    for source_id, name, url in SPA_TERMS_PAGES:
        if source_id in seen:
            continue
        seen.add(source_id)
        items.append(
            _item(
                source_id=source_id,
                source_name=name,
                risk_type="terms_text_unretrievable",
                reason=(
                    "terms page is client-rendered and served no policy text; "
                    "'no terms found' is not 'no terms exist'"
                ),
                priority=1,
                automation_blocked=True,
                human_review_only=True,
                credential_required=False,
                terms_url_or_note=url,
            )
        )

    # SAM.gov credential and role.
    sam_id, sam_name, sam_url = SAM_CREDENTIAL_ITEM
    if sam_id not in seen:
        seen.add(sam_id)
        items.append(
            _item(
                source_id=sam_id,
                source_name=sam_name,
                risk_type="credential_and_role_required",
                reason=(
                    "scraping is prohibited; API key required and a SAM role is "
                    "needed to move from 10 to 1,000 requests per day"
                ),
                priority=1,
                automation_blocked=True,
                human_review_only=False,
                credential_required=True,
                terms_url_or_note=sam_url,
            )
        )

    items.sort(key=lambda i: (i["priority"], i["source_id"]))

    by_risk = {r: 0 for r in sorted(RISK_TYPES)}
    for item in items:
        by_risk[item["risk_type"]] += 1

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "queue_length": len(items),
            "items": items,
            "by_risk_type": by_risk,
            "pending_count": sum(1 for i in items if i["review_status"] == "pending"),
            "approved_count": 0,
            "automation_blocked_count": sum(
                1 for i in items if i["automation_blocked"]
            ),
            "credential_required_count": sum(
                1 for i in items if i["credential_required"]
            ),
            # Constants for this gate.
            "sources_activated": 0,
            "reviews_performed": 0,
            "fetch_performed": False,
            "fabricated": False,
        }
    )


def queue_invariant_failures(queue: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if queue.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if queue.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")
    if queue.get("fetch_performed") is not False:
        fails.append("queue_claimed_a_fetch")
    for counter in ("sources_activated", "reviews_performed", "approved_count"):
        if queue.get(counter):
            fails.append(f"queue_reported_nonzero:{counter}")

    items = queue.get("items") or []
    ids = [i.get("source_id") for i in items]
    if len(ids) != len(set(ids)):
        fails.append("duplicate_source_in_queue")

    # Deterministic ordering.
    keys = [(i.get("priority"), i.get("source_id")) for i in items]
    if keys != sorted(keys):
        fails.append("queue_is_not_deterministically_ordered")

    for item in items:
        sid = item.get("source_id")
        if item.get("risk_type") not in RISK_TYPES:
            fails.append(f"risk_type_out_of_vocabulary:{sid}")
        if item.get("review_status") not in REVIEW_STATUSES:
            fails.append(f"review_status_out_of_vocabulary:{sid}")
        # Nothing in this gate may leave the queue approved.
        if item.get("review_status") in TERMINAL_APPROVING_STATUSES:
            fails.append(f"queue_item_pre_approved:{sid}")
        # A queued item is by definition not automatable yet.
        if item.get("automation_blocked") is not True:
            fails.append(f"queued_item_not_automation_blocked:{sid}")
        if item.get("risk_type") == "human_review_only" and not item.get(
            "human_review_only"
        ):
            fails.append(f"human_review_only_item_without_flag:{sid}")
        if not item.get("review_required_reason"):
            fails.append(f"queue_item_without_a_reason:{sid}")

    # The four SPA pages and the SAM credential item are mandatory members.
    present = set(ids)
    for source_id, _, _ in SPA_TERMS_PAGES:
        if source_id not in present:
            fails.append(f"spa_terms_page_missing_from_queue:{source_id}")
    if SAM_CREDENTIAL_ITEM[0] not in present:
        fails.append("sam_credential_item_missing_from_queue")

    return fails
