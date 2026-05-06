#!/usr/bin/env python3
"""
Fail CI if raw SQL references nf_* tables appear outside the repository layer.

See execution/03-demo-isolation-spec.md — raw `FROM nf_*` outside `**/repositories/**`
is forbidden once DDL lands; this script is a no-op until such SQL exists.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
FORBIDDEN = re.compile(r"\bFROM\s+nf_\w+", re.IGNORECASE)


def main() -> int:
    if not SRC.is_dir():
        return 0
    bad: list[Path] = []
    for path in SRC.rglob("*.py"):
        if "repositories" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if FORBIDDEN.search(text):
            bad.append(path)
    if bad:
        print("Raw nf_* SQL references outside src/**/repositories/:", file=sys.stderr)
        for p in sorted(bad):
            print(" ", p.relative_to(ROOT), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
