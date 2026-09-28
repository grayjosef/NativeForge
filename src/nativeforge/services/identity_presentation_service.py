"""Safe display fields from a verified identity.

A Google or Microsoft ID token may carry a name and a profile-photo URL.
Those are already-trusted claims from the verifier, and they are the only
source this module will present. It does not fetch Graph, does not store
tokens, and it will not hand a browser an arbitrary URL just because a claim
named itself ``picture``.

``email`` stays out. The session cookie omits it on purpose; a display name
is not a back door for putting an address in every response.
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

SCHEMA_VERSION = "nf_identity_presentation_v1"

DISPLAY_NAME_MAX = 80
PICTURE_URL_MAX = 180

# Host suffixes a provider photo may come from. Anything else is dropped,
# including data: URLs, http://, and open redirects dressed as a picture.
_PICTURE_HOST_SUFFIXES = (
    "googleusercontent.com",
    "ggpht.com",
    "google.com",
    "gstatic.com",
    "graph.microsoft.com",
    "microsoftonline.com",
    "microsoft.com",
    "live.net",
    "office.com",
    "office.net",
)

_WS = re.compile(r"\s+")
_BAD_NAME = re.compile(r"[<>\r\n]")


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def present_display_name(
    *,
    name: Any = None,
    given_name: Any = None,
    family_name: Any = None,
) -> str | None:
    """A short, printable name. Empty and unsafe values become None."""
    raw = str(name or "").strip()
    if not raw:
        parts = [str(given_name or "").strip(), str(family_name or "").strip()]
        raw = " ".join(p for p in parts if p)
    raw = _WS.sub(" ", raw).strip()
    if not raw or len(raw) > DISPLAY_NAME_MAX:
        return None
    if _BAD_NAME.search(raw) or "@" in raw:
        return None
    return raw


def present_picture_url(value: Any = None) -> str | None:
    """HTTPS profile-photo URL on an allowlisted host, or None."""
    raw = str(value or "").strip()
    if not raw or len(raw) > PICTURE_URL_MAX:
        return None
    parsed = urlparse(raw)
    if parsed.scheme != "https":
        return None
    if parsed.username or parsed.password:
        return None
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        return None
    if not any(
        host == suffix or host.endswith("." + suffix)
        for suffix in _PICTURE_HOST_SUFFIXES
    ):
        return None
    if parsed.fragment:
        return None
    return raw


def present_identity_provider(issuer: Any = None) -> str | None:
    """``google``, ``microsoft``, or None. Never a raw issuer URL."""
    text = str(issuer or "").strip().lower()
    if not text:
        return None
    if "google" in text:
        return "google"
    if "microsoft" in text or "windows.net" in text or "live.com" in text:
        return "microsoft"
    return None


def presentation_from_claims(claims: dict[str, Any] | None) -> dict[str, Any]:
    """Reduce verified OIDC claims to the three fields the chrome may show."""
    blob = claims or {}
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "display_name": present_display_name(
                name=blob.get("name"),
                given_name=blob.get("given_name"),
                family_name=blob.get("family_name"),
            ),
            "picture_url": present_picture_url(blob.get("picture")),
            "identity_provider": present_identity_provider(
                blob.get("iss") or blob.get("issuer")
            ),
        }
    )
