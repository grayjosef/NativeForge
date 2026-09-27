import { useCallback, useMemo, useState } from "react";

import { BrandLockup } from "../components/BrandLockup";
import { StateView } from "../components/StateView";
import { StatusBadge } from "../components/ui/primitives";
import type { CustomerState } from "../customerState";

/**
 * Organization onboarding.
 *
 * ## Every field here exists in the schema
 *
 * The wizard writes `TribalProfileBody`, and nothing else: `legal_name`,
 * `entity_type`, `uei`, `ein`, `sam_registration_status`, the two address
 * objects, `service_area_description` and the three contact objects. There is
 * no "annual budget", no "programs served", no "years operating" - all of
 * which would have made the review step look fuller and none of which the
 * backend can store. A field that is collected and dropped is worse than an
 * absent one: the customer believes NativeForge knows something it does not.
 *
 * Funding interests are the one place the brief asks for something the schema
 * does not carry as a first-class column, so they go into
 * `standard_narratives` - which is a JSON column that genuinely exists - and
 * the step says plainly that they are recorded as notes rather than as
 * matching criteria. Presenting them as criteria would imply a matching
 * engine reads them, and none does yet.
 *
 * ## The classification is not collapsed
 *
 * `TribalEntityType` has ten values and the product doctrine is that they are
 * not interchangeable: a federally recognized Tribe, a Tribal college, an
 * Alaska Native village and a Native Hawaiian organization have different
 * eligibility under different programs, and flattening them into "Tribe"
 * would produce confident eligibility answers that are wrong. All ten are
 * offered, each with a sentence saying who it is for.
 *
 * ## Progress survives a reload
 *
 * Kept in `localStorage` under one key, written on every change. A six-step
 * form that loses everything to a mis-click is a form people fill in once and
 * then avoid.
 */

const DRAFT_KEY = "nf.onboarding.draft";

export const ENTITY_TYPES: Array<{ value: string; label: string; help: string }> = [
  {
    value: "federally_recognized_tribe",
    label: "Federally recognized Tribe",
    help: "Listed in the Federal Register as a federally recognized Tribal entity.",
  },
  {
    value: "tribal_government",
    label: "Tribal government",
    help: "A Tribal government or a department, agency or authority of one.",
  },
  {
    value: "tribal_organization",
    label: "Tribal organization",
    help: "An organization controlled, sanctioned or chartered by one or more Tribes.",
  },
  {
    value: "tribal_nonprofit",
    label: "Tribal nonprofit",
    help: "A nonprofit organization established by or under the authority of a Tribe.",
  },
  {
    value: "tribal_college",
    label: "Tribal college or university",
    help: "A Tribal College or University (TCU).",
  },
  {
    value: "alaska_native_corporation",
    label: "Alaska Native corporation",
    help: "A regional or village corporation organized under ANCSA.",
  },
  {
    value: "alaska_native_village",
    label: "Alaska Native village",
    help: "A federally recognized Alaska Native village or Tribal council.",
  },
  {
    value: "native_hawaiian_organization",
    label: "Native Hawaiian organization",
    help: "An organization serving Native Hawaiians, as defined by the funding program.",
  },
  {
    value: "native_serving_nonprofit",
    label: "Native-serving nonprofit",
    help: "A nonprofit serving Native communities without being Tribally chartered.",
  },
  {
    value: "other",
    label: "Other Native-serving entity",
    help: "None of the above describes your organization accurately.",
  },
];

const SAM_STATUSES = [
  { value: "active", label: "Active" },
  { value: "expired", label: "Expired" },
  { value: "unknown", label: "I am not sure" },
];

export interface OnboardingDraft {
  legal_name: string;
  entity_type: string;
  uei: string;
  ein: string;
  sam_registration_status: string;
  city: string;
  state: string;
  service_area_description: string;
  rep_name: string;
  rep_title: string;
  rep_email: string;
  gm_name: string;
  gm_email: string;
  interests: string[];
}

export const EMPTY_DRAFT: OnboardingDraft = {
  legal_name: "",
  entity_type: "",
  uei: "",
  ein: "",
  sam_registration_status: "unknown",
  city: "",
  state: "",
  service_area_description: "",
  rep_name: "",
  rep_title: "",
  rep_email: "",
  gm_name: "",
  gm_email: "",
  interests: [],
};

/** Program areas customers actually pursue. Recorded as notes, not criteria. */
const INTERESTS = [
  "Housing",
  "Health and behavioral health",
  "Education and language",
  "Public safety and justice",
  "Broadband and infrastructure",
  "Natural resources and environment",
  "Economic development",
  "Elders and social services",
  "Cultural preservation",
  "Emergency management",
];

const STEPS = [
  { id: "organization", title: "Organization" },
  { id: "recognition", title: "Recognition" },
  { id: "area", title: "Service area" },
  { id: "interests", title: "Funding interests" },
  { id: "contacts", title: "Contacts" },
  { id: "review", title: "Review" },
] as const;

export function readDraft(): OnboardingDraft {
  try {
    const raw = window.localStorage.getItem(DRAFT_KEY);
    if (!raw) return { ...EMPTY_DRAFT };
    return { ...EMPTY_DRAFT, ...(JSON.parse(raw) as Partial<OnboardingDraft>) };
  } catch {
    return { ...EMPTY_DRAFT };
  }
}

/**
 * The request body, from the draft.
 *
 * Empty strings become `null` rather than `""`. The backend types most of
 * these as `str | None`, and an empty string is a value that was supplied -
 * it would be stored, exported, and later read back as though somebody had
 * answered the question with nothing.
 */
export function draftToBody(d: OnboardingDraft): Record<string, unknown> {
  const blank = (v: string) => (v.trim() ? v.trim() : null);
  const person = (name: string, email: string, title?: string) => {
    const out: Record<string, string> = {};
    if (name.trim()) out.name = name.trim();
    if (email.trim()) out.email = email.trim();
    if (title?.trim()) out.title = title.trim();
    return Object.keys(out).length > 0 ? out : null;
  };
  const address =
    d.city.trim() || d.state.trim()
      ? {
          ...(d.city.trim() ? { city: d.city.trim() } : {}),
          ...(d.state.trim() ? { state: d.state.trim() } : {}),
        }
      : null;

  return {
    legal_name: d.legal_name.trim(),
    entity_type: d.entity_type,
    uei: blank(d.uei),
    ein: blank(d.ein),
    sam_registration_status: d.sam_registration_status || "unknown",
    physical_address: address,
    service_area_description: blank(d.service_area_description),
    authorized_representative: person(d.rep_name, d.rep_email, d.rep_title),
    grants_manager: person(d.gm_name, d.gm_email),
    standard_narratives:
      d.interests.length > 0 ? { funding_interests: d.interests } : null,
  };
}

/** Which required answers are still missing, by step index. */
export function stepErrors(step: number, d: OnboardingDraft): string[] {
  if (step === 0 && !d.legal_name.trim()) {
    return ["Enter your organization's legal name."];
  }
  if (step === 1 && !d.entity_type) {
    return ["Choose the classification that describes your organization."];
  }
  return [];
}

export interface OnboardingPageProps {
  busy: boolean;
  error: CustomerState | null;
  /** Saves the profile. Resolves true when it was written. */
  onSubmit: (body: Record<string, unknown>) => Promise<boolean>;
  onEnterWorkspace: () => void;
  /** Prefills from an existing profile, when there is one. */
  initial?: Partial<OnboardingDraft>;
}

export function OnboardingPage(props: OnboardingPageProps) {
  const { busy, error, onSubmit, onEnterWorkspace, initial } = props;

  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState<OnboardingDraft>(() => ({
    ...readDraft(),
    ...(initial ?? {}),
  }));
  const [showErrors, setShowErrors] = useState(false);
  const [done, setDone] = useState(false);

  const set = useCallback(<K extends keyof OnboardingDraft>(key: K, value: OnboardingDraft[K]) => {
    setDraft((prev) => {
      const next = { ...prev, [key]: value };
      try {
        window.localStorage.setItem(DRAFT_KEY, JSON.stringify(next));
      } catch {
        /* a draft that cannot be saved is still a draft being filled in */
      }
      return next;
    });
  }, []);

  const errors = useMemo(() => stepErrors(step, draft), [step, draft]);

  const next = () => {
    if (errors.length > 0) {
      setShowErrors(true);
      return;
    }
    setShowErrors(false);
    setStep((s) => Math.min(s + 1, STEPS.length - 1));
  };

  const back = () => {
    setShowErrors(false);
    setStep((s) => Math.max(s - 1, 0));
  };

  const submit = async () => {
    const ok = await onSubmit(draftToBody(draft));
    if (ok) {
      setDone(true);
      try {
        window.localStorage.removeItem(DRAFT_KEY);
      } catch {
        /* the profile is saved; a leftover draft is harmless */
      }
    }
  };

  if (done) {
    return (
      <div className="nf-onboard">
        <div className="nf-onboard-card nf-onboard-card--done">
          <BrandLockup size={44} />
          <h2 className="nf-onboard-title">Your organization is set up</h2>
          <p className="nf-onboard-lead">
            NativeForge can now evaluate opportunities against {draft.legal_name.trim()} and prepare
            application packages for your review.
          </p>
          <button type="button" className="nf-btn nf-btn-primary" onClick={onEnterWorkspace}>
            Enter NativeForge
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="nf-onboard">
      <div className="nf-onboard-card">
        <div className="nf-onboard-head">
          <BrandLockup size={32} />
          <p className="nf-onboard-step">
            Step {step + 1} of {STEPS.length} · {STEPS[step].title}
          </p>
        </div>

        <ol className="nf-onboard-track" aria-label="Setup progress">
          {STEPS.map((s, i) => (
            <li
              key={s.id}
              className="nf-onboard-tick"
              data-state={i < step ? "done" : i === step ? "current" : "todo"}
              aria-current={i === step ? "step" : undefined}
            >
              <span className="nf-visually-hidden">
                {s.title}: {i < step ? "complete" : i === step ? "current" : "not started"}
              </span>
            </li>
          ))}
        </ol>

        {error ? <StateView state={error} /> : null}
        {showErrors && errors.length > 0 ? (
          <StateView
            state={{ tone: "blocked", title: "One thing first", body: errors[0] }}
            inline
          />
        ) : null}

        {step === 0 ? (
          <section className="nf-onboard-body">
            <h2 className="nf-onboard-title">What is your organization called?</h2>
            <p className="nf-onboard-lead">
              Use the legal name exactly as it appears on federal registrations. It goes onto every
              application package NativeForge prepares.
            </p>
            <div className="nf-field">
              <label htmlFor="ob-name">Legal name</label>
              <input
                id="ob-name"
                className="nf-input"
                value={draft.legal_name}
                onChange={(e) => set("legal_name", e.target.value)}
                autoComplete="organization"
              />
            </div>
            <div className="nf-field-row">
              <div className="nf-field">
                <label htmlFor="ob-uei">UEI</label>
                <input
                  id="ob-uei"
                  className="nf-input"
                  value={draft.uei}
                  onChange={(e) => set("uei", e.target.value)}
                  placeholder="Optional"
                />
                <p className="nf-field-help">Unique Entity Identifier from SAM.gov.</p>
              </div>
              <div className="nf-field">
                <label htmlFor="ob-ein">EIN</label>
                <input
                  id="ob-ein"
                  className="nf-input"
                  value={draft.ein}
                  onChange={(e) => set("ein", e.target.value)}
                  placeholder="Optional"
                />
              </div>
            </div>
          </section>
        ) : null}

        {step === 1 ? (
          <section className="nf-onboard-body">
            <h2 className="nf-onboard-title">How is your organization recognized?</h2>
            <p className="nf-onboard-lead">
              Eligibility differs between these, so NativeForge keeps them distinct rather than
              treating every Native-serving organization the same way.
            </p>
            <div className="nf-radio-list" role="radiogroup" aria-label="Organization classification">
              {ENTITY_TYPES.map((t) => (
                <label key={t.value} className="nf-radio" data-checked={draft.entity_type === t.value}>
                  <input
                    type="radio"
                    name="entity_type"
                    value={t.value}
                    checked={draft.entity_type === t.value}
                    onChange={() => set("entity_type", t.value)}
                  />
                  <span className="nf-radio-text">
                    <span className="nf-radio-label">{t.label}</span>
                    <span className="nf-radio-help">{t.help}</span>
                  </span>
                </label>
              ))}
            </div>
            <div className="nf-field">
              <label htmlFor="ob-sam">SAM.gov registration</label>
              <select
                id="ob-sam"
                className="nf-select"
                value={draft.sam_registration_status}
                onChange={(e) => set("sam_registration_status", e.target.value)}
              >
                {SAM_STATUSES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
              <p className="nf-field-help">
                Recorded as you state it. NativeForge does not check SAM.gov on your behalf.
              </p>
            </div>
          </section>
        ) : null}

        {step === 2 ? (
          <section className="nf-onboard-body">
            <h2 className="nf-onboard-title">Who do you serve, and from where?</h2>
            <p className="nf-onboard-lead">
              Many federal programs are scoped geographically. This is what NativeForge will quote
              back to you when it explains a geographic eligibility rule.
            </p>
            <div className="nf-field-row">
              <div className="nf-field">
                <label htmlFor="ob-city">City</label>
                <input
                  id="ob-city"
                  className="nf-input"
                  value={draft.city}
                  onChange={(e) => set("city", e.target.value)}
                />
              </div>
              <div className="nf-field">
                <label htmlFor="ob-state">State or territory</label>
                <input
                  id="ob-state"
                  className="nf-input"
                  value={draft.state}
                  onChange={(e) => set("state", e.target.value)}
                />
              </div>
            </div>
            <div className="nf-field">
              <label htmlFor="ob-area">Service area</label>
              <textarea
                id="ob-area"
                className="nf-textarea"
                rows={4}
                value={draft.service_area_description}
                onChange={(e) => set("service_area_description", e.target.value)}
                placeholder="Reservation, counties, villages or communities served"
              />
            </div>
          </section>
        ) : null}

        {step === 3 ? (
          <section className="nf-onboard-body">
            <h2 className="nf-onboard-title">What do you pursue funding for?</h2>
            <p className="nf-onboard-lead">
              Stored with your profile as notes for your team. NativeForge does not yet use these to
              filter opportunities, and will say so rather than implying otherwise.
            </p>
            <div className="nf-check-grid">
              {INTERESTS.map((interest) => {
                const on = draft.interests.includes(interest);
                return (
                  <label key={interest} className="nf-check" data-checked={on}>
                    <input
                      type="checkbox"
                      checked={on}
                      onChange={() =>
                        set(
                          "interests",
                          on
                            ? draft.interests.filter((x) => x !== interest)
                            : [...draft.interests, interest],
                        )
                      }
                    />
                    <span>{interest}</span>
                  </label>
                );
              })}
            </div>
          </section>
        ) : null}

        {step === 4 ? (
          <section className="nf-onboard-body">
            <h2 className="nf-onboard-title">Who signs, and who manages the work?</h2>
            <p className="nf-onboard-lead">
              The authorized representative is the person who may commit your organization. Naming
              them here records a claim; NativeForge does not treat it as verified authority.
            </p>
            <div className="nf-field-row">
              <div className="nf-field">
                <label htmlFor="ob-rep">Authorized representative</label>
                <input
                  id="ob-rep"
                  className="nf-input"
                  value={draft.rep_name}
                  onChange={(e) => set("rep_name", e.target.value)}
                />
              </div>
              <div className="nf-field">
                <label htmlFor="ob-rep-title">Title</label>
                <input
                  id="ob-rep-title"
                  className="nf-input"
                  value={draft.rep_title}
                  onChange={(e) => set("rep_title", e.target.value)}
                />
              </div>
            </div>
            <div className="nf-field">
              <label htmlFor="ob-rep-email">Representative email</label>
              <input
                id="ob-rep-email"
                type="email"
                className="nf-input"
                value={draft.rep_email}
                onChange={(e) => set("rep_email", e.target.value)}
              />
            </div>
            <div className="nf-field-row">
              <div className="nf-field">
                <label htmlFor="ob-gm">Grants manager</label>
                <input
                  id="ob-gm"
                  className="nf-input"
                  value={draft.gm_name}
                  onChange={(e) => set("gm_name", e.target.value)}
                />
              </div>
              <div className="nf-field">
                <label htmlFor="ob-gm-email">Grants manager email</label>
                <input
                  id="ob-gm-email"
                  type="email"
                  className="nf-input"
                  value={draft.gm_email}
                  onChange={(e) => set("gm_email", e.target.value)}
                />
              </div>
            </div>
          </section>
        ) : null}

        {step === 5 ? (
          <section className="nf-onboard-body">
            <h2 className="nf-onboard-title">Check this over</h2>
            <p className="nf-onboard-lead">
              Anything left blank stays blank. NativeForge will report it as unknown rather than
              guessing.
            </p>
            <dl className="nf-review">
              <ReviewRow label="Legal name" value={draft.legal_name} onEdit={() => setStep(0)} />
              <ReviewRow
                label="Classification"
                value={ENTITY_TYPES.find((t) => t.value === draft.entity_type)?.label ?? ""}
                onEdit={() => setStep(1)}
              />
              <ReviewRow label="UEI" value={draft.uei} onEdit={() => setStep(0)} />
              <ReviewRow label="EIN" value={draft.ein} onEdit={() => setStep(0)} />
              <ReviewRow
                label="SAM.gov"
                value={SAM_STATUSES.find((s) => s.value === draft.sam_registration_status)?.label ?? ""}
                onEdit={() => setStep(1)}
              />
              <ReviewRow
                label="Location"
                value={[draft.city, draft.state].filter(Boolean).join(", ")}
                onEdit={() => setStep(2)}
              />
              <ReviewRow
                label="Service area"
                value={draft.service_area_description}
                onEdit={() => setStep(2)}
              />
              <ReviewRow
                label="Funding interests"
                value={draft.interests.join(", ")}
                onEdit={() => setStep(3)}
              />
              <ReviewRow
                label="Authorized representative"
                value={[draft.rep_name, draft.rep_title, draft.rep_email].filter(Boolean).join(" · ")}
                onEdit={() => setStep(4)}
              />
              <ReviewRow
                label="Grants manager"
                value={[draft.gm_name, draft.gm_email].filter(Boolean).join(" · ")}
                onEdit={() => setStep(4)}
              />
            </dl>
            <p className="nf-onboard-note">
              <StatusBadge tone="info">Self-declared</StatusBadge> This profile is what your
              organization states about itself. NativeForge records it as a claim and does not
              present it as independently verified.
            </p>
          </section>
        ) : null}

        <div className="nf-onboard-actions">
          <button
            type="button"
            className="nf-btn nf-btn-ghost"
            onClick={back}
            disabled={step === 0 || busy}
          >
            Back
          </button>
          {step < STEPS.length - 1 ? (
            <button type="button" className="nf-btn nf-btn-primary" onClick={next} disabled={busy}>
              Continue
            </button>
          ) : (
            <button
              type="button"
              className="nf-btn nf-btn-primary"
              onClick={() => void submit()}
              disabled={busy}
            >
              {busy ? "Saving…" : "Save and enter NativeForge"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function ReviewRow({
  label,
  value,
  onEdit,
}: {
  label: string;
  value: string;
  onEdit: () => void;
}) {
  const given = value.trim();
  return (
    <div className="nf-review-row">
      <dt>{label}</dt>
      <dd>
        <span data-empty={given ? undefined : "true"}>{given || "Not provided"}</span>
        <button type="button" className="nf-link-btn" onClick={onEdit}>
          Edit
        </button>
      </dd>
    </div>
  );
}
