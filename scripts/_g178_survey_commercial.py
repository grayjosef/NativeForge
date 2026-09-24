"""Gate 178A: what commercial machinery exists, and what must never be built.

Gate 178 encodes an APPROVED model. It does not design one. So this survey's
first job is to establish what is canonical and what is a draft, because the
repository contains both and confusing them would mean shipping the wrong
price.

```text
docs/operations/570_...PRICING_REQUIREMENT.md
    "These figures are the operator's drafts, recorded verbatim as drafts"
    Starter $14,995 / Professional 5 $34,999 / Founding Tribe Beta $24,999 ...

Gate 178 prompt (approved, canonical)
    persistent licence $32,999, first 12 months maintenance included,
    $4,999/year thereafter, 3 continuous years delinquent = expiry
```

Doc 570 says of itself that it holds drafts. The gate prompt is the approved
model. This survey records both and asserts which one is canonical, so that
nobody later reads 570's `$34,999` as the price.

Three questions decide Gate 178's shape:

```text
1. does any commercial state exist yet, or is this entirely new?
2. is there anything that already conflates FEATURE entitlement with
   COMMERCIAL entitlement? They are different questions and sharing a word
   is how they get shared code.
3. is any structure capable of DELETING a delinquent organisation's data?
   The approved model forbids it, and a survey that only looks for what
   exists will not find a capability that must not exist.
```

No network. No writes.
"""

from __future__ import annotations

import ast
import json
import pathlib
import re
import socket
import sqlite3
import sys

sys.path.insert(0, "src")
sys.path.insert(0, ".")

_NETWORK = {"attempts": 0}


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("gate178 survey makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

REPO = pathlib.Path(__file__).resolve().parents[1]
SERVICES = REPO / "src" / "nativeforge" / "services"
PACKAGE = REPO / "src" / "nativeforge"
DB = REPO / "nativeforge.local.db"

#: The APPROVED model. Encoded here so the survey can assert the repository
#: contains no contradicting canonical claim.
CANONICAL = {
    "persistent_license_price_usd": 32999,
    "included_maintenance_months": 12,
    "annual_maintenance_price_usd": 4999,
    "delinquency_years_before_expiration": 3,
    "extension_days": (7, 14, 30),
}

#: Figures doc 570 records ABOUT ITSELF as drafts, as whole dollars. Listed so
#: the survey can prove none is used as a PRICE.
#:
#: Checked as numeric LITERALS rather than as text. Searching the source for
#: "2,999" matched inside "$32,999" - the canonical price setting off a
#: draft-price alarm - and "34,999" matched the docstring that exists to say
#: that figure is a draft we do not use. A figure named in prose as a thing we
#: are not doing is the opposite of a figure encoded as a price.
DRAFT_DOLLARS = (14995, 34999, 49999, 24999, 8999, 6999, 2999)

#: The same figures in integer cents, which is how a price would be stored.
DRAFT_CENTS = tuple(d * 100 for d in DRAFT_DOLLARS)

COMMERCIAL_TABLE_PATTERN = re.compile(
    r"licen|entitle|billing|invoice|subscription|maintenance|price|pricing|"
    r"commercial|payment|delinquen",
    re.I,
)

#: Capabilities the approved model FORBIDS. A survey that only looks for what
#: exists cannot find a dangerous capability, so these are searched for by
#: name.
FORBIDDEN_CAPABILITIES = {
    "delete_organization": re.compile(
        r"def\s+delete_organization|DROP\s+TABLE\s+organizations|"
        r"DELETE\s+FROM\s+organizations",
        re.I,
    ),
    "purge_delinquent_data": re.compile(
        r"purge_delinquent|delete_delinquent|wipe_tenant|purge_tenant", re.I
    ),
    "rewrite_billing_history": re.compile(
        r"rewrite_ledger|delete_invoice|update\s+.*paid_through.*where", re.I
    ),
}

SOURCES = {p.stem: p.read_text(encoding="utf-8") for p in SERVICES.glob("*.py")}
PACKAGE_SOURCES = {
    str(p.relative_to(PACKAGE)): p.read_text(encoding="utf-8")
    for p in PACKAGE.rglob("*.py")
}
WHOLE = "\n".join(PACKAGE_SOURCES.values())


def main() -> int:
    out: dict[str, object] = {"schema_version": "nf_gate178_survey_v1"}

    # ---- question 1: does any commercial state exist? ---------------
    tables: dict[str, object] = {}
    if DB.exists():
        conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        try:
            names = [
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
                )
            ]
            commercial = [n for n in names if COMMERCIAL_TABLE_PATTERN.search(n)]
            for name in commercial:
                rows = conn.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
                cols = [r[1] for r in conn.execute(f"PRAGMA table_info({name})")]
                tables[name] = {"rows": rows, "columns": len(cols)}
            out["total_tables"] = len(names)
            out["commercial_tables"] = commercial
        finally:
            conn.close()
    else:
        out["total_tables"] = 0
        out["commercial_tables"] = []

    out["commercial_table_detail"] = tables
    out["commercial_state_exists"] = bool(tables)
    out["gate178_is_entirely_new_state"] = not tables

    # ---- question 2: feature entitlement vs commercial entitlement --
    feature_module = "tenant_beta_feature_entitlement_service"
    feature_body = SOURCES.get(feature_module, "")
    out["feature_entitlement_module_exists"] = bool(feature_body)
    # A module about BETA FEATURES is not about money. If it mentioned
    # licences or payment it would be doing two jobs under one word.
    out["feature_entitlement_mentions_money"] = bool(
        re.search(
            r"licen[cs]e|invoice|payment|delinquen|maintenance_fee", feature_body, re.I
        )
    )
    out["feature_and_commercial_entitlement_are_distinct"] = not out[
        "feature_entitlement_mentions_money"
    ]

    modules_named_entitlement = sorted(
        name for name in SOURCES if "entitlement" in name
    )
    out["modules_named_entitlement"] = modules_named_entitlement

    # ---- question 3: can anything delete a delinquent org's data? ---
    forbidden_hits: dict[str, list[str]] = {}
    for label, pattern in FORBIDDEN_CAPABILITIES.items():
        hits = sorted(
            name for name, body in PACKAGE_SOURCES.items() if pattern.search(body)
        )
        if hits:
            forbidden_hits[label] = hits
    out["forbidden_capability_hits"] = forbidden_hits
    out["nothing_can_delete_a_delinquent_organization"] = not forbidden_hits

    # ---- canonical versus draft -------------------------------------
    out["canonical_model"] = CANONICAL
    forbidden = set(DRAFT_DOLLARS) | set(DRAFT_CENTS)
    draft_in_code: dict[str, list[int]] = {}
    for name, body in PACKAGE_SOURCES.items():
        try:
            tree = ast.parse(body)
        except SyntaxError:  # pragma: no cover - a broken module is its own bug
            continue
        found = sorted(
            {
                node.value
                for node in ast.walk(tree)
                if isinstance(node, ast.Constant)
                and isinstance(node.value, int)
                and not isinstance(node.value, bool)
                and node.value in forbidden
            }
        )
        if found:
            draft_in_code[name] = found

    out["draft_figures_present_in_code"] = draft_in_code
    out["draft_figures_are_not_in_code"] = not draft_in_code
    out["draft_figures_checked_as_literals_not_text"] = True
    out["modules_parsed_for_literals"] = len(PACKAGE_SOURCES)

    doc570 = REPO / (
        "docs/operations/570_PRODUCT_TENANT_BETA_AWARDED_GRANTS_PRICING_REQUIREMENT.md"
    )
    doc_text = doc570.read_text(encoding="utf-8") if doc570.exists() else ""
    out["doc570_present"] = bool(doc_text)
    # Doc 570 labels its own figures as drafts. Recording that the label is
    # there is what keeps somebody from reading them as the price later.
    out["doc570_labels_its_figures_as_drafts"] = bool(
        re.search(r"recorded verbatim as drafts|drafted by the operator", doc_text)
    )
    out["doc570_contains_canonical_price"] = "32,999" in doc_text or "32999" in doc_text
    out["canonical_price_already_encoded_anywhere"] = bool(re.search(r"32,?999", WHOLE))

    # ---- what 178 must build ----------------------------------------
    out["gate178_must_build"] = sorted(
        item
        for item, needed in {
            "commercial_state_tables": not out["commercial_state_exists"],
            "license_state_model": True,
            "maintenance_state_model": True,
            "benefit_access_derivation": True,
            "temporary_benefit_extensions": True,
            "entitlement_history_ledger": True,
            "three_year_expiration_measurement": True,
            "relicensing_and_forgiveness": True,
        }.items()
        if needed
    )

    out["network_requests"] = _NETWORK["attempts"]
    out["wrote_nothing"] = True
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
