# SC Pilot fixtures (operator-provided — do not synthesize)

Place operator-sourced files here before running SC pilot staging verify:

- `sc_tribal_profiles.json` — tribes with `recognition_type` (`federal` | `state_only`) + provenance
- `sc_eligibility_rules.json` — per-category `recognition_requirement` with sources

NativeForge will validate schema and refuse to load if either file is missing or invalid.
