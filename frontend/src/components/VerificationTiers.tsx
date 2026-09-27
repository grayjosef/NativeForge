import { StatusBadge, type BadgeTone } from "./ui/primitives";

/**
 * The three things NativeForge can separately know about an organization.
 *
 * ## Why three, and never one
 *
 * A single "Verified ✓" would be the most commercially flattering thing this
 * product could display and the least true. Knowing who a person is says
 * nothing about which organization they work for, and working for a Tribe
 * says nothing about being authorized to commit it to a federal application.
 * Those are three separate evidentiary questions, they fail independently,
 * and `tribal_authority_model_service` refuses to persist a field named
 * `verified`, `is_verified` or `authority_verified` precisely so that the
 * collapse cannot happen in storage either.
 *
 * This component is the customer-facing half of that rule.
 *
 * ## What the tiers actually report today
 *
 * Honest, and mostly negative:
 *
 * - **Identity** is unverified until a customer signs in through a provider.
 *   Production reports `provider_configured: false`, so today it is unknown
 *   for everybody rather than assumed.
 * - **Affiliation** is self-declared from the organization profile. A
 *   profile that exists is a claim, not a confirmation.
 * - **Authority** has no scalable verification path. Saying otherwise would
 *   be the exact claim the authority model refuses to store.
 *
 * "Not verified" is shown as a neutral state, not a failure. Nothing has gone
 * wrong; the evidence simply is not in yet, and dressing that in red would
 * teach customers to ignore red.
 */

export type TierState = "verified" | "self_declared" | "unverified" | "in_review";

const TIER_LABEL: Record<TierState, string> = {
  verified: "Verified",
  self_declared: "Self-declared",
  unverified: "Not verified",
  in_review: "In review",
};

const TIER_TONE: Record<TierState, BadgeTone> = {
  verified: "positive",
  self_declared: "info",
  unverified: "muted",
  in_review: "warn",
};

export interface Tier {
  id: string;
  name: string;
  state: TierState;
  /** What this tier would mean if it were satisfied, in one sentence. */
  detail: string;
}

export function VerificationTiers({ tiers }: { tiers: Tier[] }) {
  return (
    <ul className="nf-tiers">
      {tiers.map((t) => (
        <li key={t.id} className="nf-tier" data-state={t.state}>
          <div className="nf-tier-head">
            <span className="nf-tier-name">{t.name}</span>
            <StatusBadge tone={TIER_TONE[t.state]}>{TIER_LABEL[t.state]}</StatusBadge>
          </div>
          <p className="nf-tier-detail">{t.detail}</p>
        </li>
      ))}
    </ul>
  );
}

/**
 * The tiers as they stand for one organization.
 *
 * Takes what is known rather than deciding it: `identityVerified` comes from
 * the auth session, `hasProfile` from the profile record. Authority is
 * constant today because there is no path that could change it, and a
 * parameter implying otherwise would invite a caller to pass `true`.
 */
export function buildTiers(input: {
  identityVerified: boolean;
  hasProfile: boolean;
}): Tier[] {
  return [
    {
      id: "identity",
      name: "Identity",
      state: input.identityVerified ? "verified" : "unverified",
      detail: input.identityVerified
        ? "Confirmed by your organization's identity provider at sign-in."
        : "Confirmed when you sign in with your organization's Microsoft or Google account.",
    },
    {
      id: "affiliation",
      name: "Affiliation",
      state: input.hasProfile ? "self_declared" : "unverified",
      detail: input.hasProfile
        ? "Your organization profile states this affiliation. NativeForge has not independently confirmed it."
        : "Established when your organization profile is complete.",
    },
    {
      id: "authority",
      name: "Authority to commit",
      state: "unverified",
      detail:
        "Confirming that a person may commit an organization to a federal application requires documentary review. NativeForge does not assert it.",
    },
  ];
}
