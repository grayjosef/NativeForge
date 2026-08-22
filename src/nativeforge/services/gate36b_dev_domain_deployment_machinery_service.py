"""Gate 36B: stamped dist validators (loopback demo machinery)."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

BUILD_SHA_META = "nativeforge-build-sha"
BUILD_TIME_META = "nativeforge-build-time"
ARTIFACT_KIND_META = "nativeforge-artifact-kind"
SOURCE_DIRTY_META = "nativeforge-source-dirty"
ARTIFACT_KIND = "dev-domain-demo"
APP_NAME = "nativeforge"

SHA_META_RE = re.compile(
    r'<meta\s+name="nativeforge-build-sha"\s+content="([^"]*)"\s*/?>',
    re.IGNORECASE,
)

FORBIDDEN_HTML_CLAIMS = (
    "controlled customer pilot GO",
    "production rollout GO",
    "login live",
    "pen-test passed",
    "production-ready",
    "production storage",
    "customer persistence",
)

FORBIDDEN_DOC_ALLOWED_PHRASES = (
    "controlled customer pilot GO",
    "production rollout GO",
    "production-ready",
    "login live",
    "production storage",
    "customer persistence",
    "pen-test passed",
)

ALLOWED_CLAIM_MARKERS = (
    "limited external demo",
    "local loopback",
)


class DistNotReady(ValueError):
    """Fail-closed: dist missing or unstamped."""


def count_build_sha_metas(html: str) -> int:
    return len(SHA_META_RE.findall(html))


def validate_html_stamp(html: str) -> None:
    n = count_build_sha_metas(html)
    if n < 1:
        raise DistNotReady("missing nativeforge-build-sha meta")
    if n > 1:
        raise DistNotReady("duplicate nativeforge-build-sha meta")


def strip_existing_identity_metas(html: str) -> str:
    names = (
        BUILD_SHA_META,
        BUILD_TIME_META,
        ARTIFACT_KIND_META,
        SOURCE_DIRTY_META,
    )
    out = html
    for name in names:
        out = re.sub(
            rf'\s*<meta\s+name="{name}"\s+content="[^"]*"\s*/?>',
            "",
            out,
            flags=re.IGNORECASE,
        )
    return out


def stamp_html_document(
    html: str,
    *,
    git_sha: str,
    build_time: str,
    artifact_kind: str = ARTIFACT_KIND,
    source_dirty: bool = False,
) -> str:
    cleaned = strip_existing_identity_metas(html)
    metas = (
        f'<meta name="{BUILD_SHA_META}" content="{git_sha}">\n'
        f'<meta name="{BUILD_TIME_META}" content="{build_time}">\n'
        f'<meta name="{ARTIFACT_KIND_META}" content="{artifact_kind}">\n'
        f'<meta name="{SOURCE_DIRTY_META}" content="'
        f'{"true" if source_dirty else "false"}">'
    )
    lowered = cleaned.lower()
    idx = lowered.find("<head>")
    if idx == -1:
        raise DistNotReady("HTML missing <head> for stamp")
    insert_at = idx + len("<head>")
    stamped = cleaned[:insert_at] + "\n" + metas + cleaned[insert_at:]
    validate_html_stamp(stamped)
    return stamped


def require_stamped_dist(dist: Path) -> None:
    if not dist.is_dir():
        raise DistNotReady(f"dist missing: {dist}")
    manifest = dist / "build-manifest.json"
    if not manifest.is_file():
        raise DistNotReady("build-manifest.json missing")
    if not (dist / "health").is_file():
        raise DistNotReady("/health file missing")
    if not (dist / "version").is_file():
        raise DistNotReady("/version file missing")
    index = dist / "index.html"
    if not index.is_file():
        raise DistNotReady("index.html missing")
    html = index.read_text(encoding="utf-8")
    validate_html_stamp(html)
    for html_path in dist.rglob("*.html"):
        validate_html_stamp(html_path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def write_health_file(dist: Path) -> None:
    (dist / "health").write_text("ok\n", encoding="utf-8")


def write_version_file(
    dist: Path,
    *,
    git_sha: str,
    build_time: str,
    source_dirty: bool,
    artifact_kind: str = ARTIFACT_KIND,
) -> None:
    payload = {
        "app": APP_NAME,
        "artifact_kind": artifact_kind,
        "git_sha": git_sha,
        "build_time": build_time,
        "source_dirty": source_dirty,
    }
    (dist / "version").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )


def write_build_manifest(
    dist: Path,
    *,
    git_sha: str,
    build_time: str,
    source_dirty: bool,
    artifact_kind: str = ARTIFACT_KIND,
) -> None:
    files: list[dict[str, str]] = []
    for path in sorted(dist.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(dist).as_posix()
        if rel == "build-manifest.json":
            continue
        files.append({"path": rel, "sha256": sha256_file(path)})
    manifest = {
        "app": APP_NAME,
        "artifact_kind": artifact_kind,
        "git_sha": git_sha,
        "build_time": build_time,
        "source_dirty": source_dirty,
        "files": files,
    }
    (dist / "build-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )


def stamp_dist_tree(
    dist: Path,
    *,
    git_sha: str,
    build_time: str,
    source_dirty: bool,
    artifact_kind: str = ARTIFACT_KIND,
) -> None:
    if not dist.is_dir():
        raise DistNotReady(f"dist missing: {dist}")
    for html_path in dist.rglob("*.html"):
        raw = html_path.read_text(encoding="utf-8")
        stamped = stamp_html_document(
            raw,
            git_sha=git_sha,
            build_time=build_time,
            artifact_kind=artifact_kind,
            source_dirty=source_dirty,
        )
        html_path.write_text(stamped, encoding="utf-8")
    write_health_file(dist)
    write_version_file(
        dist,
        git_sha=git_sha,
        build_time=build_time,
        source_dirty=source_dirty,
        artifact_kind=artifact_kind,
    )
    write_build_manifest(
        dist,
        git_sha=git_sha,
        build_time=build_time,
        source_dirty=source_dirty,
        artifact_kind=artifact_kind,
    )
    require_stamped_dist(dist)


def claim_boundary_preserved(html: str) -> bool:
    lowered = html.lower()
    for phrase in FORBIDDEN_HTML_CLAIMS:
        if phrase.lower() in lowered:
            return False
    return True


def parse_verifier_output(text: str) -> str:
    last = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("RESULT="):
            last = stripped.split("=", 1)[1].strip()
    if last not in {"PASS", "FAIL"}:
        raise ValueError("verifier output missing RESULT=PASS|FAIL")
    return last


def docs_claim_boundary_ok(doc_text: str) -> bool:
    """Forbidden GO claims must not appear as allowed claims."""
    lowered = doc_text.lower()
    if "allowed claims" in lowered:
        # Split on headings; allowed section must not list forbidden GOs.
        parts = re.split(r"(?i)#+\s*allowed claims", doc_text, maxsplit=1)
        if len(parts) == 2:
            rest = re.split(r"(?i)#+\s*forbidden", parts[1], maxsplit=1)[0]
            blob = rest.lower()
            for phrase in FORBIDDEN_DOC_ALLOWED_PHRASES:
                if phrase.lower() in blob and "not " + phrase.lower() not in blob:
                    if f"do not claim {phrase.lower()}" not in blob:
                        return False
    for marker in ALLOWED_CLAIM_MARKERS:
        if marker in lowered:
            return True
    return "loopback" in lowered
