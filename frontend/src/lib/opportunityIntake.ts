/**
 * Bringing in an opportunity the customer already has.
 *
 * A discovery engine finds opportunities. A pursuit operating system also has
 * to accept the ones a customer arrives with - a grant they heard about at a
 * conference, a notice a funder emailed them, an application they are already
 * halfway through. Without this they keep those in a spreadsheet and
 * NativeForge manages half their portfolio.
 *
 * ## One model, no silo
 *
 * An intake produces exactly the body the ordinary create endpoint takes, so
 * a customer-added opportunity is the same kind of thing as a discovered one
 * and every surface works on it. `source: "manual"` records where it came
 * from; it does not put it in a different product.
 */

/**
 * Where the customer already is, in their words and in the schema's.
 *
 * The right-hand column is `GrantPipelineStage`, which is the repository's
 * canonical lifecycle. Nothing new is invented here.
 *
 * Two of these collapse. "Not awarded" and "Withdrawn" both map to
 * `not_pursuing`, because that is the only terminal stage the enum has, and
 * for an award-compliance product the difference between losing and standing
 * down is not nothing. The customer's own wording is kept in the notes so the
 * distinction survives in the record even though the stage cannot express it.
 */
export const INTAKE_STAGES: Array<{
  id: string;
  label: string;
  help: string;
  stage: string;
}> = [
  {
    id: "known",
    label: "We know about it, but haven't started",
    help: "Track it and watch the deadline.",
    stage: "new",
  },
  {
    id: "evaluating",
    label: "We're deciding whether to go for it",
    help: "NativeForge will check eligibility and pull out the requirements.",
    stage: "evaluating",
  },
  {
    id: "pursuing",
    label: "We're already pursuing it",
    help: "Bring the work you have done so far into NativeForge.",
    stage: "pursuing",
  },
  {
    id: "drafting",
    label: "The application is in progress",
    help: "Track requirements, deadlines and what is still outstanding.",
    stage: "drafting",
  },
  {
    id: "submitted",
    label: "We've already submitted it",
    help: "Keep the record and watch for amendments and decisions.",
    stage: "submitted",
  },
  {
    id: "awarded",
    label: "We were awarded",
    help: "Hold the award record alongside the application.",
    stage: "awarded",
  },
  {
    id: "not_awarded",
    label: "We were not awarded",
    help: "Kept as history. NativeForge records this as closed.",
    stage: "not_pursuing",
  },
  {
    id: "withdrawn",
    label: "We withdrew",
    help: "Kept as history. NativeForge records this as closed.",
    stage: "not_pursuing",
  },
];

export interface IntakeDraft {
  title: string;
  funder: string;
  program: string;
  opportunityNumber: string;
  url: string;
  deadline: string;
  noticeText: string;
  stageId: string;
  notes: string;
}

export const EMPTY_INTAKE: IntakeDraft = {
  title: "",
  funder: "",
  program: "",
  opportunityNumber: "",
  url: "",
  deadline: "",
  noticeText: "",
  stageId: "known",
  notes: "",
};

/** Normalised for comparison: case, punctuation and spacing are not identity. */
export function normaliseTitle(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^\w\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/** A URL without the parts that differ between two links to the same page. */
export function normaliseUrl(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return "";
  try {
    const url = new URL(trimmed);
    // Tracking parameters and fragments are not identity, and a trailing
    // slash is not a different page.
    url.hash = "";
    for (const key of [...url.searchParams.keys()]) {
      if (key.toLowerCase().startsWith("utm_")) url.searchParams.delete(key);
    }
    const path = url.pathname.replace(/\/+$/, "");
    return `${url.host.toLowerCase()}${path}${url.search}`.toLowerCase();
  } catch {
    return trimmed.toLowerCase();
  }
}

function str(value: unknown): string {
  return typeof value === "string" ? value : value != null ? String(value) : "";
}

export interface MatchResult {
  /** The opportunity this one already is, when NativeForge is confident. */
  existing: Record<string, unknown> | null;
  /** Why it matched, in customer terms. */
  reason: string | null;
}

/**
 * Whether this organization is already tracking this opportunity.
 *
 * Checked in order of how much the evidence is worth: the same link, then the
 * same opportunity number, then the same title from the same funder.
 *
 * Title alone is deliberately not enough. "Community Development Block Grant"
 * is the name of a dozen distinct competitions across as many agencies, and
 * merging two of them would hide a deadline the customer is working to.
 *
 * This is tenant-scoped. It answers "are we already tracking this", not "does
 * this exist in the world" - matching against a global opportunity graph is a
 * larger piece of work and this does not pretend to be it.
 */
export function findExisting(
  draft: IntakeDraft,
  tracked: Record<string, unknown>[],
): MatchResult {
  const url = normaliseUrl(draft.url);
  if (url) {
    const byUrl = tracked.find(
      (row) => normaliseUrl(str(row.url)) === url || normaliseUrl(str(row.source_url)) === url,
    );
    if (byUrl) {
      return { existing: byUrl, reason: "the same link" };
    }
  }

  const number = draft.opportunityNumber.trim().toLowerCase();
  if (number) {
    const byNumber = tracked.find(
      (row) => str(row.opportunity_number).trim().toLowerCase() === number,
    );
    if (byNumber) {
      return { existing: byNumber, reason: "the same opportunity number" };
    }
  }

  const title = normaliseTitle(draft.title);
  const funder = normaliseTitle(draft.funder);
  if (title && funder) {
    const byTitle = tracked.find(
      (row) =>
        normaliseTitle(str(row.opportunity_title)) === title &&
        normaliseTitle(str(row.agency)) === funder,
    );
    if (byTitle) {
      return { existing: byTitle, reason: "the same title from the same funder" };
    }
  }

  return { existing: null, reason: null };
}

/**
 * The body the ordinary create endpoint takes.
 *
 * `source_id` has to be unique per organization and the customer has no
 * reason to invent one, so it is derived: the opportunity number when there
 * is one, otherwise a random identifier. Deriving it from the title would
 * make two genuinely different competitions with the same name collide.
 */
export function draftToCreateBody(draft: IntakeDraft): Record<string, unknown> {
  const stage =
    INTAKE_STAGES.find((s) => s.id === draft.stageId)?.stage ?? "new";
  const customerWording = INTAKE_STAGES.find((s) => s.id === draft.stageId)?.label ?? "";

  const notes = [
    draft.notes.trim(),
    // The customer's own words, kept because the lifecycle cannot tell
    // "not awarded" from "withdrawn" and both are worth knowing later.
    customerWording ? `Added by the organization as: ${customerWording}` : "",
  ]
    .filter(Boolean)
    .join("\n\n");

  const number = draft.opportunityNumber.trim();

  return {
    source: "manual",
    source_id: number || `customer-${crypto.randomUUID()}`,
    agency: draft.funder.trim() || "Not stated",
    opportunity_title: draft.title.trim(),
    award_type: "grant",
    program_name: draft.program.trim() || null,
    opportunity_number: number || null,
    url: draft.url.trim() || null,
    application_deadline: draft.deadline ? `${draft.deadline}T23:59:00Z` : null,
    // The notice the customer pasted. NativeForge reads this; it has not
    // fetched anything.
    raw_nofo_text: draft.noticeText.trim() || null,
    pipeline_stage: stage,
    eligibility_tags: notes ? [notes] : null,
  };
}

/**
 * What came back from asking NativeForge to read a link.
 *
 * Three endings, not two. `fetched` says whether the page was opened at all;
 * `readable` says whether there was anything in it to read. Collapsing them
 * would show a scanned PDF as an opportunity with no contacts, which is a
 * different and much worse statement than "nobody could read this".
 */
export interface UrlReadResult {
  fetched: boolean;
  readable: boolean;
  /** A sentence for the customer. Empty when there is nothing to caveat. */
  message: string;
  finalUrl: string;
  noticeText: string;
  /** The parsed deadline, when the notice gave a date. `YYYY-MM-DD`. */
  deadline: string;
}

function s(value: unknown): string {
  return typeof value === "string" ? value : value != null ? String(value) : "";
}

/** The API's shape, narrowed to what the wizard uses. */
export function parseUrlRead(payload: Record<string, unknown>): UrlReadResult {
  const extracted = (payload.extracted ?? {}) as Record<string, unknown>;
  const submission = (extracted.submission ?? null) as Record<string, unknown> | null;
  const deadlineAt = submission ? s(submission.deadline_at) : "";

  return {
    fetched: payload.fetched === true,
    readable: payload.readable === true,
    message: s(payload.message),
    finalUrl: s(payload.final_url),
    noticeText: s(payload.notice_text),
    // Date only. The wizard's deadline field is a date, and the time of day
    // stays in the notice text where the wording that produced it is.
    deadline: deadlineAt ? deadlineAt.slice(0, 10) : "",
  };
}

/**
 * Fold a reading into the draft, without overwriting the customer.
 *
 * Only blank fields are filled. Someone who typed a deadline from the funder's
 * email has better information than a date parsed out of a web page, and
 * silently replacing it would be the kind of help nobody asked for - the sort
 * that is discovered after the deadline passes.
 *
 * The link itself is updated to the final URL, because following redirects to
 * the page that was actually read is the address worth keeping.
 */
export function applyUrlRead(draft: IntakeDraft, read: UrlReadResult): IntakeDraft {
  if (!read.readable) return draft;
  return {
    ...draft,
    url: read.finalUrl || draft.url,
    noticeText: draft.noticeText.trim() ? draft.noticeText : read.noticeText,
    deadline: draft.deadline || read.deadline,
  };
}

/**
 * The document route's shape, narrowed to the same result the link produces.
 *
 * `read` is false for two different endings - a file nothing here can read,
 * and a file that was read and had nothing in it - so the presence of the
 * `reading` block is what separates them. Without that the wizard would tell
 * somebody who uploaded a scanned PDF that NativeForge would not accept their
 * file, which is not what happened.
 */
export function parseDocumentRead(payload: Record<string, unknown>): UrlReadResult {
  const extracted = (payload.extracted ?? {}) as Record<string, unknown>;
  const submission = (extracted.submission ?? null) as Record<string, unknown> | null;
  const deadlineAt = submission ? s(submission.deadline_at) : "";

  return {
    fetched: payload.reading !== undefined,
    readable: payload.read === true,
    message: s(payload.message),
    finalUrl: "",
    noticeText: s(payload.notice_text),
    deadline: deadlineAt ? deadlineAt.slice(0, 10) : "",
  };
}

/** A browser `File`, as the API wants it. Never touches the network. */
export async function fileToDocumentBody(
  file: File,
  read: (f: File) => Promise<string> = readAsDataUrl,
): Promise<{ filename: string; contentType: string; contentBase64: string }> {
  const dataUrl = await read(file);
  const comma = dataUrl.indexOf(",");
  return {
    filename: file.name,
    // A browser leaves the type blank for formats it does not recognise. The
    // server decides what it can read; guessing from the extension here would
    // be a second opinion nobody asked for.
    contentType: file.type || "application/octet-stream",
    contentBase64: comma >= 0 ? dataUrl.slice(comma + 1) : "",
  };
}

function readAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error ?? new Error("could not read the file"));
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.readAsDataURL(file);
  });
}
