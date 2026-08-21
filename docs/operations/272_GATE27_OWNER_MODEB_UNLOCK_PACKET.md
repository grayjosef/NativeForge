# Gate 27 — Owner Mode B Unlock Packet (Block 59)

## Mode A (default)
Owner inputs absent → `mode=A`, all live claims false.

## Input kinds
repo_safe_artifact | out_of_band_secret | out_of_band_config | external_report |
operator_confirmation | owner_approval | not_allowed_in_repo | unknown

## Rules
- Prompt is not approval
- Secret-like keys rejected from repo-safe artifacts
- Mode B-ready ≠ Mode B executed ≠ pilot GO
