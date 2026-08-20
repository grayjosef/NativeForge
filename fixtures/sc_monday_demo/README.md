# SC Monday Demo Fixtures

Operator/demo curated pack for the Monday SC customer demo lane.

- `sc_curated_current_opportunity_pack.json` — curated SC + federal opportunities
- Labels: `fixture_demo` / `rule_reference` with `live_ingest_not_claimed=true`
- **Not** automated live ingestion
- **Not** source activation

Regenerate:

```bash
source .venv/bin/activate
python -c "from nativeforge.services.sc_monday_curated_pack_service import write_sc_curated_opportunity_pack; print(write_sc_curated_opportunity_pack())"
```
