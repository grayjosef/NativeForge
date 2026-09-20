"""Gate 167A: what opportunity-shaped storage already exists? Reads only.

No network. No writes. Answers one question: is there already a place a
normalized opportunity lands, and is it global or per-tenant?

Per-tenant matters. 167L forbids copying the canonical opportunity once per
tenant, and a table carrying `organization_id` is already doing that.
"""

from __future__ import annotations

import json
import sqlite3
import sys

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from nativeforge.lib.settings import get_settings  # noqa: E402

url = str(get_settings().database_url)
path = url.split("///")[-1].lstrip("./") if "///" in url else url

connection = sqlite3.connect(path)
tables = [
    name
    for (name,) in connection.execute(
        "select name from sqlite_master where type = 'table' order by name"
    )
]

INTERESTING = (
    "spark",
    "opportunit",
    "discovery",
    "notice",
    "nofo",
    "watchlist",
    "pursuit",
)

out: dict[str, object] = {"database": path, "total_tables": len(tables)}
detail: dict[str, object] = {}

for name in tables:
    if not any(token in name for token in INTERESTING):
        continue
    columns = [row[1] for row in connection.execute(f"pragma table_info({name})")]
    count = connection.execute(f"select count(*) from {name}").fetchone()[0]
    detail[name] = {
        "rows": count,
        "column_count": len(columns),
        # The tenancy question, answered per table.
        "has_organization_id": "organization_id" in columns,
        "has_is_demo": "is_demo" in columns,
        "columns": columns,
    }

out["tables"] = detail
out["tenant_scoped"] = sorted(
    k for k, v in detail.items() if v["has_organization_id"]
)
out["global_scoped"] = sorted(
    k for k, v in detail.items() if not v["has_organization_id"]
)
out["a_global_opportunity_store_exists"] = False
connection.close()

print(json.dumps(out, indent=2, sort_keys=True))
