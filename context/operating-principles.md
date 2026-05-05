# Operating Principles

These rules apply to every step of the build. Cursor reads this file before starting work. Every PR is reviewed against it. Violations block merge.

## Hard rules (no exceptions)

- **Do not implement before audit.** No NativeForge code is written until `01-audit-prompt.md` has produced `audit-output.md` and a human has signed off on the architecture-boundary decision.
- **Do not commit secrets.** No API keys, no DB credentials, no signing keys, no tokens of any kind in the repo. Use the existing secret management mechanism the audit identifies.
- **Do not touch production secrets.** Even if you have access. The build environment uses development credentials only.
- **Do not create demo data in real orgs.** Every demo write goes through a route gated to demo orgs only. The CI tests in `03-demo-isolation-spec.md` enforce this.
- **Do not broadly refactor ContractForge.** Refactor scope is limited to the smallest change required to enable a specific NativeForge feature. Larger generalizations are deferred to a post-M1 cleanup pass.
- **Do not skip review gates.** Every AI-generated output and every form package goes through the server-enforced review state machine. The UI does not bypass the backend.
- **Do not auto-submit anything.** No background process or scheduled task moves a record to a `submitted` state. Submission is always a deliberate human action.

## Strong defaults (override only with documented reason)

- **Prefer additive changes.** Add new tables, new routes, new components. Modify existing ones only when the audit shows they're battle-tested and the modification is small and reviewed.
- **Validate after each small change.** Run tests. Run lints. Read your own diff. If the validation step is skipped, the change is not done.
- **Preserve ContractForge behavior.** A change that breaks a ContractForge test is treated as a regression, not an acceptable cost. If the test is wrong, fix the test in a separate PR.
- **All AI outputs require human review gates.** Server-enforced. The frontend can hide the gate; it cannot remove it.
- **All fake data must be explicitly demo-scoped.** No "well it's just a fixture" excuses. Fixtures live in demo orgs and are loaded by routes the test framework calls explicitly.
- **Templated explanations, not freeform LLM.** Wherever an LLM might explain a deterministic output (e.g., a score), the structure is templated and the LLM only fills slots or rephrases.
- **Scoped imports.** A NativeForge file imports nothing from ContractForge directly. Cross-product code lives in shared packages (`forge-*` or unprefixed shared).
- **No pan-Indian generalization in any template, prompt, or default copy.** Every cultural claim is tribe-specific or it doesn't ship.

## When in doubt

- If a change touches both products, stop and ask whether the shared abstraction is real or premature.
- If a feature could plausibly be done with copy-paste, do that, mark it as duplicated, and move on. Generalize after the third instance, not the second.
- If a test fails and you don't understand why, do not change the test. Find the actual cause.
- If you're about to write a comment that says "TODO: handle X edge case," handle it now. Or write a ticket. Do not commit a known gap with a comment.
- If the audit says a component is unverified scaffolding, treat it as scaffolding. Do not generalize from it.
- If a request from the human contradicts these principles, surface the contradiction and ask. Do not silently violate.

## Reporting

After every significant unit of work, Cursor reports:

- What was changed (file paths, line ranges, test names).
- What tests were added or modified.
- What tests pass.
- Any operating principle that was relevant to the decision (especially any near-violation that was avoided).
- Any open question that the human needs to answer before the next unit.

Reports are written to the PR description, not to chat. Chat is for synchronous coordination; PR descriptions are the durable record.
