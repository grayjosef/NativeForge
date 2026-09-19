"""Gate 164E survey: which artifact builders read developer-machine state?

Gate 163 found five by accident, when a regen tried to bake local Auth0
configuration into committed evidence. Reading 69 writers to find the rest
would be guessing; this measures it.

Each writer is run twice, in two ambient environments, and the outputs are
diffed:

```text
A   repo cwd, local .env present      (a developer's machine)
B   temp cwd, no .env, DB absolute    (something closer to a clean checkout)
```

A builder whose output differs between them is reading ambient state, whatever
its imports look like. A builder whose output is identical is hermetic with
respect to the two things that vary here - which is not a proof of hermeticity
in general, and is reported as such.

Run as a child process so cwd and `.env` discovery really differ: pydantic
reads `.env` relative to the working directory, so importing twice in one
process would not vary it.

Makes no network request: it writes artifacts to temporary directories.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import pathlib
import sys

sys.path.insert(0, "src")


def discover_writers() -> list[tuple[str, str]]:
    """Every `write_*_artifacts` in the services package, by module and name.

    Resolved from THIS FILE, not from the working directory.

    The cwd-relative version silently found zero writers whenever the survey
    ran from a temp directory - which was the entire point of the "no .env"
    variant. Comparing a full run against an empty one reported every writer
    as ambient-sensitive, and that is where "68 cwd/.env-sensitive builders"
    came from. It was the harness, not the code.
    """
    root = pathlib.Path(__file__).resolve().parents[1] / "src/nativeforge/services"
    found: list[tuple[str, str]] = []
    for path in sorted(root.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.startswith("def write_") and "artifacts" in line:
                name = line[len("def ") :].split("(", 1)[0].strip()
                found.append((f"nativeforge.services.{path.stem}", name))
    return found


def run_all(out_root: str) -> dict[str, object]:
    """Call every writer into `out_root`, and digest what each one wrote."""
    results: dict[str, object] = {}
    for module_name, function_name in discover_writers():
        key = f"{module_name.rsplit('.', 1)[-1]}:{function_name}"
        try:
            module = importlib.import_module(module_name)
            writer = getattr(module, function_name)
            writer(repo_root=out_root)
        except Exception as exc:  # noqa: BLE001 - a writer that cannot run is data
            results[key] = {"error": f"{type(exc).__name__}: {exc}"[:160]}
            continue

        directory = getattr(module, "ARTIFACT_DIR", None)
        if not directory:
            results[key] = {"error": "no ARTIFACT_DIR"}
            continue
        target = pathlib.Path(out_root) / directory
        digests: dict[str, str] = {}
        if target.is_dir():
            for path in sorted(target.rglob("*")):
                if path.is_file():
                    digests[str(path.relative_to(target))] = hashlib.sha256(
                        path.read_bytes()
                    ).hexdigest()
        results[key] = {"artifact_dir": directory, "files": digests}
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-root", required=True)
    args = parser.parse_args()
    print(json.dumps(run_all(args.out_root), sort_keys=True))
