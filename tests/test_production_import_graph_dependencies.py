"""Everything the app imports at startup must be in the production image.

This exists because it happened. `httpx` was declared under the `dev` extra,
the image builds `uv sync --frozen --no-dev`, and the day a route imported the
module that uses it the service stopped booting and answered 502 to every
request. Nothing caught it: the suite runs in a virtualenv that has the dev
extras, so every import resolved happily right up until it was deployed.

The gap is specific and worth naming. A dev-only dependency used by test code
is correct. A dev-only dependency reachable from `nativeforge.main` is a
production outage the tests cannot see, because the tests are the reason it is
installed.

## Two distinctions this has to get right, or it is noise

**Declared is not installed.** `pydantic` and `cryptography` appear in no
dependency list here, and are in the image regardless - one comes with
`fastapi`, the other with `pyjwt[crypto]`. So the comparison is against the
resolved closure in `uv.lock`, which is what `uv sync --frozen` installs, not
against the direct dependencies a human typed.

**Imported is not imported at startup.** The PDF adapter names `fitz`,
`pdfplumber` and `pdfminer` inside functions, behind `find_spec` checks,
precisely so a missing backend degrades instead of crashing. A function-local
import cannot fail a boot, so only module-level imports count. That is also
what keeps this honest: `httpx` is module-level in the fetch service, so the
regression it was written for is still caught.
"""

from __future__ import annotations

import ast
import sys
import tomllib
from importlib.metadata import packages_distributions
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
PACKAGE = "nativeforge"
ENTRY = "nativeforge.main"


def _canonical(name: str) -> str:
    """PEP 503 normalisation, so `Pillow` and `pillow` are one name."""
    return name.lower().replace("_", "-").replace(".", "-")


def production_closure() -> set[str]:
    """Every distribution `uv sync --frozen --no-dev` installs.

    Walked from the lock rather than from `[project] dependencies`, because
    the image contains the closure and a check against the direct list would
    fail on every transitive package the application legitimately imports.
    """
    lock = tomllib.loads((REPO_ROOT / "uv.lock").read_text(encoding="utf-8"))
    packages = {_canonical(p["name"]): p for p in lock["package"]}

    root = packages[_canonical(PACKAGE)]
    queue = [_canonical(d["name"]) for d in root.get("dependencies", [])]
    # The dev group is deliberately not seeded: it is exactly what the image
    # does not have.
    closure: set[str] = set()
    while queue:
        name = queue.pop()
        if name in closure:
            continue
        closure.add(name)
        package = packages.get(name)
        if not package:
            continue
        for dep in package.get("dependencies", []):
            queue.append(_canonical(dep["name"]))
        # Extras a dependency was requested with - `psycopg[binary]`,
        # `uvicorn[standard]` - carry their own requirements.
        for extra_deps in (package.get("optional-dependencies") or {}).values():
            for dep in extra_deps:
                queue.append(_canonical(dep["name"]))
    return closure


def allowed_top_level_imports() -> set[str]:
    """Import names belonging to a distribution in the production closure.

    Derived rather than hand-listed, because the mapping is not guessable:
    `Pillow` imports as `PIL`, `pyjwt` as `jwt`. A hand-written table is a
    second source of truth that drifts, which is the shape of the bug this
    file is about.
    """
    closure = production_closure()
    return {
        import_name
        for import_name, dists in packages_distributions().items()
        if any(_canonical(d) in closure for d in dists)
    }


def _module_path(module: str) -> Path | None:
    base = SRC / Path(*module.split("."))
    if (base / "__init__.py").is_file():
        return base / "__init__.py"
    if base.with_suffix(".py").is_file():
        return base.with_suffix(".py")
    return None


def _module_level_imports(path: Path, module: str) -> set[str]:
    """Imports that run when the module is loaded. Nothing nested.

    `ast.walk` would also return imports inside functions, which is the whole
    difference between a package that must be installed and one that may be.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()

    def collect(body: list[ast.stmt]) -> None:
        for node in body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    found.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    parts = module.split(".")[: -node.level] or [PACKAGE]
                    prefix = ".".join(parts)
                    found.add(f"{prefix}.{node.module}" if node.module else prefix)
                elif node.module:
                    found.add(node.module)
            elif isinstance(node, ast.If):
                # `if TYPE_CHECKING:` and friends still execute at import
                # time when the condition holds, so the body is followed.
                collect(node.body)
                collect(node.orelse)
            elif isinstance(node, ast.Try):
                # A guarded import is still attempted at module load. The
                # fallback is the author's business; the attempt is ours.
                collect(node.body)
                for handler in node.handlers:
                    collect(handler.body)
                collect(node.orelse)
                collect(node.finalbody)

    collect(tree.body)
    return found


def startup_import_graph() -> tuple[set[str], set[str]]:
    """(first-party modules reached, third-party top-level names reached)."""
    seen: set[str] = set()
    third_party: set[str] = set()
    queue = [ENTRY]

    while queue:
        module = queue.pop()
        if module in seen:
            continue
        seen.add(module)
        path = _module_path(module)
        if path is None:
            continue
        for imported in _module_level_imports(path, module):
            top = imported.split(".")[0]
            if top == PACKAGE:
                # A first-party import may name a module or an object inside
                # one; take the longest prefix that exists on disk.
                candidate = imported
                while candidate and _module_path(candidate) is None:
                    candidate = candidate.rpartition(".")[0]
                if candidate:
                    queue.append(candidate)
                continue
            if top in sys.stdlib_module_names or top in sys.builtin_module_names:
                continue
            third_party.add(top)

    return seen, third_party


# ------------------------------------------------- the guard's own guards


def test_the_graph_is_actually_walked():
    """A check that reached nothing would pass forever."""
    reached, _ = startup_import_graph()
    assert ENTRY in reached
    # `main` imports dozens of route modules, each importing services. A
    # handful would mean the walk stopped at the first level.
    assert len(reached) > 50, len(reached)


def test_startup_reaches_real_third_party_packages():
    """The collector must collect."""
    _, third_party = startup_import_graph()
    assert {"fastapi", "sqlalchemy", "pydantic"} <= third_party


def test_the_closure_contains_transitive_packages():
    """`pydantic` is nobody's declared dependency and is always installed."""
    closure = production_closure()
    assert "pydantic" in closure
    assert "cryptography" in closure
    # And the dev group is not in it, which is what gives the check its teeth.
    assert "pytest" not in closure
    assert "ruff" not in closure


def test_optional_pdf_backends_are_not_counted_as_startup_imports():
    """They are function-local on purpose, and absent from the image.

    If these ever start counting, this file will fail for a reason that has
    nothing to do with a real outage, and the next person will delete it.
    """
    _, third_party = startup_import_graph()
    assert "fitz" not in third_party
    assert "pdfplumber" not in third_party
    assert "pdfminer" not in third_party


# ----------------------------------------------------------- the check


@pytest.mark.parametrize("dependency", sorted(startup_import_graph()[1]))
def test_every_startup_import_is_a_production_dependency(dependency: str):
    """One case per package, so a failure names the package."""
    assert dependency in allowed_top_level_imports(), (
        f"{dependency!r} is imported at module level somewhere reachable from "
        f"{ENTRY}, but no distribution in uv.lock's production closure "
        "provides it. The image builds with `uv sync --frozen --no-dev`, so "
        "it will not be installed and the service will fail to boot."
    )


def test_httpx_specifically_is_in_the_production_closure():
    """Named on purpose. The regression has a date and a 502."""
    assert "httpx" in production_closure()
