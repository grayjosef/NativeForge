"""Guard: ContractForge table names must not appear in NativeForge sources."""

from __future__ import annotations

from pathlib import Path

FORBIDDEN_SUBSTRINGS = (
    "org_contract_scoring",
    '"contracts"',
    "'contracts'",
    "FROM contracts",
    "bid_recommendation",
)


def test_nf_sources_avoid_contractforge_table_names() -> None:
    root = Path(__file__).resolve().parents[1]
    paths = list((root / "src" / "nativeforge").rglob("*.py"))
    offenders: list[str] = []
    for p in paths:
        text = p.read_text(encoding="utf-8")
        lower = text.lower()
        for bad in FORBIDDEN_SUBSTRINGS:
            if bad.lower() in lower:
                offenders.append(f"{p.relative_to(root)}: contains {bad!r}")
    assert offenders == [], "\n".join(offenders)
