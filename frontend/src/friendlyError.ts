/**
 * Superseded by `customerState`. Kept as a re-export so every existing call
 * site becomes safe at once.
 *
 * The mapping used to live here and ended with `return t || GENERIC_SHORT`,
 * which echoed any unmatched message shorter than 180 characters. Most
 * backend failures are shorter than that, so the escape hatch was the common
 * path rather than the rare one, and a raw payload reached the workspace.
 *
 * Re-exporting rather than editing in place was deliberate: there are around
 * fifteen call sites, and fixing the shared function closes all of them in
 * one move instead of leaving a partially migrated surface where some errors
 * are safe and others are not.
 *
 * New code should import `interpretError` and render a state, not a string.
 */
export { friendlyError } from "./customerState";
export type { CustomerState, StateTone } from "./customerState";
export { interpretError, diagnosticsVisible } from "./customerState";
