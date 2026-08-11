#!/usr/bin/env python3
"""CLI entry for NM/WA operator surfacing offline demo visibility.

Usage:
  python scripts/nm_wa_operator_surfacing_demo_cli.py --format text
  python scripts/nm_wa_operator_surfacing_demo_cli.py \\
      --format html --out /tmp/nf_os_demo.html
  python scripts/nm_wa_operator_surfacing_demo_cli.py \\
      --format json --out /tmp/nf_os_demo.json

Offline synthetic only. No network, no source activation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="NM/WA operator surfacing offline demo CLI (dev/demo only)"
    )
    parser.add_argument(
        "--format",
        choices=("text", "html", "json"),
        default="text",
        help="Output format",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional output path (required for html/json unless writing stdout)",
    )
    args = parser.parse_args(argv)

    from nativeforge.services.nm_wa_operator_surfacing_demo_artifact_service import (
        build_demo_artifact,
        write_demo_artifact,
    )
    from nativeforge.services.nm_wa_operator_surfacing_demo_render_service import (
        build_demo_visibility_payload,
        render_demo_html_report,
        render_demo_text_report,
        write_demo_html_report,
    )

    artifact = build_demo_artifact()
    payload = build_demo_visibility_payload(artifact)

    if args.format == "text":
        text = render_demo_text_report(payload)
        if args.out:
            args.out.write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text)
        return 0

    if args.format == "html":
        if args.out is None:
            sys.stdout.write(render_demo_html_report(payload))
        else:
            write_demo_html_report(args.out, artifact=artifact)
        return 0

    # json
    if args.out is None:
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        write_demo_artifact(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
