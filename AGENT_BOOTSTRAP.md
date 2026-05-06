You are working on NativeForge, a sovereignty-first tribal grant pursuit and compliance platform extending the existing contract-iq codebase. "ContractForge" is the product name; the actual repo/folder is `contract-iq`. Same thing, not renaming.

REPO LAYOUT ON THIS MACBOOK:
- /Users/home/Code/NativeForge   ← this repo. You are here. Research, brief, execution docs.
- /Users/home/Code/contract-iq   ← the codebase you are auditing. READ ONLY.

PATH PREFIX NOTE: the brief and execution docs reference paths prefixed `nativeforge-research/<path>`. That's a legacy artifact. Treat it as the current repo root. So `nativeforge-research/source/foo.md` is `source/foo.md` from where you are now.

READ ORDER, before any audit work:
  1. context/operating-principles.md   (the rules — every action reviewed against them)
  2. context/product-thesis.md
  3. context/m0-demo-narrative.md
  4. context/five-pillars.md
  5. context/guardrails-and-risks.md
  6. execution/README.md
  7ution/01-audit-prompt.md

EXECUTE THE AUDIT:

The file execution/01-audit-prompt.md contains a code block that is your operating instructions for the audit. Run that prompt against the contract-iq codebase at /Users/home/Code/contract-iq.

Deliverable: a single markdown file at audit-output.md in this repo root (the NativeForge repo). Section structure is defined in the audit prompt — follow it exactly.

INCREMENTAL OUTPUT: write audit-output.md section by section as you complete each one. Do not wait until the end. If the run is interrupted, partial work must survive on disk.

HARD RULES (do not violate):
- READ ONLY. No code written. No migrations. No modifications to /Users/home/Code/contract-iq.
- No commits to either repo.
- Every claim in audit-output.md cites a file path and line range from contract-iq. No "appears to" without citation.
- Do not advance past Step 1 of the build brief. When audit-output.md is complete, stop and hand control back to the human. Steps 2 through 7 are for subsequent runafter sign-off.

WHEN STUCK:
- If a required section has nothing to report (e.g., contract-iq has no AI/LLM usage), say so with proof. Run the relevant grep and cite "no matches" from its output.
- If something contradicts the brief's assumptions (e.g., contract-iq's tenancy model is incompatible with the demo isolation spec), surface it in the "Open questions for the human" section. Do not silently work around it.
- If you genuinely cannot proceed for any reason, write what you have to audit-output.md, mark unfinished sections clearly, and stop.

The human is going offline. Run the audit autonomously. Surface a single comprehensive audit-output.md and stop.
