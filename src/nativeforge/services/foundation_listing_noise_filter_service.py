"""Filter generic nav/boilerplate from foundation HTML listings."""

from __future__ import annotations

import json
import re
from typing import Any

SCHEMA_VERSION = "nf_foundation_listing_noise_filter_v1"

_GENERIC_NAV_TITLE_RE = re.compile(
    r"^(skip to|resources|learn more|home|contact|about|our work|"
    r"grantmaking|grantseeker|funding for individuals|funding for organizations|"
    r"what we fund|grantseekers|grantees|manage your grant|member education|"
    r"press release here|application portal here|all of the recipients|"
    r"grants browse|folder:)\b",
    re.IGNORECASE,
)
_BOILERPLATE_FRAGMENT_RE = re.compile(
    r"\b(skip to content|browse through our curated listing)\b",
    re.IGNORECASE,
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def is_generic_nav_listing(listing: dict[str, Any]) -> bool:
    title = str(listing.get("listing_title") or "").strip()
    if len(title) < 8:
        return True
    if any(x in title for x in ('">', "style=", "class=", ".jpg", "object-fit")):
        return True
    if _GENERIC_NAV_TITLE_RE.search(title):
        return True
    if _BOILERPLATE_FRAGMENT_RE.search(title):
        return True
    if title.lower() in {"fluxx grant opportunity", "learn more", "read more"}:
        return True
    if title.lower().startswith("scholarship faq"):
        return True
    return False


def filter_foundation_listings(
    listings: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for lst in listings:
        if is_generic_nav_listing(lst):
            excluded.append({**lst, "noise_reason": "generic_nav"})
        else:
            included.append(lst)
    return included, excluded
