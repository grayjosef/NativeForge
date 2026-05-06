# NativeForge Source Connector Architecture

Sprint 22 defines how **future** connectors attach to the existing Discovery Engine **without** live network I/O in code paths shipped this sprint.

---

## Lifecycle (target state)

```text
source registry row
  → source check run
  → connector dry run
  → raw source payload
  → normalized opportunity candidate
  → duplicate key generation
  → Native relevance scoring
  → quality scoring (existing engine)
  → review queue creation
  → operator decision pack
  → evidence pack
```

Dry-run mode is mandatory before promotion: connectors emit payloads and metrics without persisting Grant Sparks until operators approve.

---

## Connector types

| Type | Description |
|------|-------------|
| `api_connector` | Structured HTTP APIs (future; respects auth & contracts) |
| `html_page_monitor` | Scheduled fetch + extract (robots-aware; future) |
| `rss_feed` | Syndicated XML / Atom summaries |
| `downloaded_csv` | Operator-supplied file drops |
| `manual_upload` | Curated rows via operator tooling |
| `email_alert_parser_later` | Parsed alerts (explicitly deferred) |
| `foundation_page_monitor` | Foundation-specific HTML patterns |
| `state_portal_monitor` | State portal adapters |

Sprint 22 ships **interfaces + static fixtures only**.

---

## Core payloads (conceptual)

1. **`ConnectorSourceConfig`** — binds a connector run to registry metadata (publisher, lane, priority hints).
2. **`ConnectorRunContext`** — run id, `dry_run` flag, timestamps, schema versions.
3. **`RawOpportunityPayload`** — immutable-ish snapshot of parsed fields + provenance.
4. **`NormalizedOpportunityCandidate`** — canonical fields aligned with discovery intake + duplicate key + scoring results.
5. **`ConnectorDryRunResult`** — candidates, errors, telemetry for operator review.

---

## Non-negotiables

```text
robots.txt respected
rate limits
no credential scraping
no bypassing access controls
no submission automation
no external calls in tests
dry-run mode first
all source payloads get provenance metadata
all accepted candidates go through existing intake/review/evidence path
```

Additional engineering constraints for Sprint 22 shell code:

- No imports of `requests`, `httpx`, `aiohttp`, `urllib.request`, or `socket` in connector modules.
- Tests prove **offline** behavior via in-memory fixtures.

---

## Integration with Discovery intake

Normalized candidates convert to **structured intake candidate dicts** compatible with `process_structured_candidates` / Sprint 12 APIs via `to_discovery_intake_candidate_payload` (optional helper).

The connector layer **does not** write to the database; services and APIs retain persistence ownership.

---

## Evidence and audit

Each payload carries provenance suitable for **discovery evidence packs**:

- Connector identifier and version.
- Dry-run vs. live mode (future).
- Source registry id reference.
- Capture timestamp and normalization schema version.

---

## Operational promotion

Connectors graduate through the **HITP approval block** (`nativeforge-native-relevant-source-architecture.md`): policy review, robots compliance, rate-limit budgets, and operator sign-off recorded in the action ledger.
