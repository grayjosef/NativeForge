# SC Pilot fixtures (operator-provided — do not synthesize)

Place operator-sourced files here before running SC pilot staging verify:

- `sc_tribal_profiles.json` — tribes with:
  - `recognition_type` (`federal` | `state_only`)
  - `incorporated`, `has_501c3` (`true` | `false` | `unknown`)
  - `fiscal_sponsor_available` (boolean, optional)
  - provenance (`public_inferred` from Part 1)
- `sc_eligibility_rules.json` — per-category:
  - `recognition_requirement` (including `federal_required_for_tribal_pathway`)
  - condition flags: `requires_incorporation`, `requires_501c3`, `individual_only`
  - `dual_pathway.nonprofit_alternative` for USDA CF / EDA grants

NativeForge validates schema and refuses to load if either file is missing or invalid.
