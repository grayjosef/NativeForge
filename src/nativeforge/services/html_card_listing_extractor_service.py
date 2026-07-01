"""Card-DOM grant listing extraction (Learn More / generic anchor pattern)."""

from __future__ import annotations

import json
import re
from html import unescape
from typing import Any
from urllib.parse import urljoin, urlparse

SCHEMA_VERSION = "nf_html_card_listing_extractor_v1"

_LINK_RE = re.compile(
    r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")
_GRANT_HINT_RE = re.compile(
    r"\b(grant|fellowship|fund|funding|program|rfp|solicitation|award|application)\b",
    re.IGNORECASE,
)
_SKIP_HINT_RE = re.compile(
    r"\b(login|sign in|donate|cart|privacy|cookie|newsletter)\b",
    re.IGNORECASE,
)

_GENERIC_ANCHOR_TEXT_RE = re.compile(
    r"^\s*(learn\s+more|read\s+more|apply\s+now|view\s+details|click\s+here|"
    r"more\s+info|details)\s*$",
    re.IGNORECASE,
)
_HEADING_RE = re.compile(
    r"<h[1-6][^>]*>(.*?)</h[1-6]>",
    re.IGNORECASE | re.DOTALL,
)
_NAV_TITLE_RE = re.compile(
    r"^(skip to|resources|learn more|home|contact|about|breadcrumb|"
    r"funding opportunities|grantmaking|our work|menu)\b",
    re.IGNORECASE,
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _strip_tags(html: str) -> str:
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", html)).strip()


def _clean_card_title(raw: str) -> str:
    title = unescape(raw).strip()
    title = re.sub(r"^\d+\s*[–—\-]\s*Learn More\s*", "", title, flags=re.IGNORECASE)
    title = re.sub(r"^Learn More\s*", "", title, flags=re.IGNORECASE).strip()
    title = re.sub(r"\s+", " ", title)
    return title[:240]


def _nearest_card_context(ctx_html: str) -> str:
    parts = re.split(r"</(?:div|article|section|li)>", ctx_html, flags=re.IGNORECASE)
    return parts[-1] if parts else ctx_html


def _title_from_card_context(ctx_html: str) -> str:
    """Derive grant title from HTML preceding a generic CTA link."""
    ctx_html = _nearest_card_context(ctx_html)
    if '">' in ctx_html or "class=" in ctx_html[-200:]:
        ctx_html = re.sub(r"<[^>]+>", " ", ctx_html[-800:])
    headings = [_strip_tags(h) for h in _HEADING_RE.findall(ctx_html)]
    for heading in reversed(headings):
        clean = unescape(heading).strip()
        if len(clean) >= 12 and not _NAV_TITLE_RE.search(clean):
            if _GRANT_HINT_RE.search(clean) and "<" not in clean:
                return clean[:240]

    text = unescape(_strip_tags(ctx_html))
    segments = re.split(r"\s*[–—\-]\s*", text)
    best = ""
    for segment in reversed(segments):
        segment = segment.strip()
        if len(segment) < 20 or _NAV_TITLE_RE.search(segment):
            continue
        if any(x in segment.lower() for x in ('">', "header", "class=")):
            continue
        if not _GRANT_HINT_RE.search(segment):
            continue
        if "tribes" in segment.lower() or "tribal" in segment.lower():
            if ":" in segment:
                segment = segment.split(":", 1)[-1].strip()
            if len(segment) > len(best):
                best = segment[:240]
        elif not best:
            best = segment[:240]
    if best:
        return _clean_card_title(best)

    lines = [ln.strip() for ln in text.split(".") if ln.strip()]
    for line in reversed(lines):
        if len(line) < 20 or _NAV_TITLE_RE.search(line):
            continue
        if _GRANT_HINT_RE.search(line) and "<" not in line:
            return _clean_card_title(line)
    return ""


def extract_card_dom_listings(
    html: str,
    *,
    base_url: str,
    path_hints: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    """Extract grant rows from card blocks where CTA text is generic (Learn More)."""
    listings: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for match in _LINK_RE.finditer(html):
        href = match.group(1)
        inner = match.group(2)
        anchor_text = _strip_tags(inner)
        if not _GENERIC_ANCHOR_TEXT_RE.match(anchor_text):
            continue
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)
        if parsed.scheme not in ("http", "https"):
            continue
        if _SKIP_HINT_RE.search(anchor_text):
            continue

        ctx_start = max(0, match.start() - 500)
        ctx = html[ctx_start : match.start()]
        title = _title_from_card_context(ctx)
        title = _clean_card_title(title)
        if not title or len(title) < 12:
            continue
        if not re.match(r"^[A-Z0-9\"']", title):
            continue
        if _NAV_TITLE_RE.search(title):
            continue
        hay = f"{title} {parsed.path}"
        if not _GRANT_HINT_RE.search(hay):
            if path_hints and not any(h in (parsed.path or "").lower() for h in path_hints):
                continue
            elif not path_hints:
                continue
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)
        listings.append(
            {
                "listing_title": title[:240],
                "listing_url": full_url,
                "excerpt": title[:500],
                "extraction_method": "card_dom",
            }
        )
    return listings


def merge_anchor_and_card_listings(
    anchor_listings: list[dict[str, Any]],
    card_listings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge anchor + card rows; prefer card title when URL collides."""
    by_url: dict[str, dict[str, Any]] = {}
    for lst in anchor_listings:
        by_url[str(lst["listing_url"])] = dict(lst)
    for lst in card_listings:
        url = str(lst["listing_url"])
        existing = by_url.get(url)
        if existing is None:
            by_url[url] = dict(lst)
            continue
        if lst.get("extraction_method") == "card_dom":
            if _GENERIC_ANCHOR_TEXT_RE.match(str(existing.get("listing_title", ""))):
                by_url[url] = dict(lst)
            elif len(str(lst.get("listing_title", ""))) > len(
                str(existing.get("listing_title", ""))
            ):
                by_url[url] = dict(lst)
    return list(by_url.values())
