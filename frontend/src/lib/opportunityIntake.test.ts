import { describe, expect, it } from "vitest";

import {
  EMPTY_INTAKE,
  INTAKE_STAGES,
  draftToCreateBody,
  findExisting,
  normaliseTitle,
  normaliseUrl,
  type IntakeDraft,
} from "./opportunityIntake";

function draft(overrides: Partial<IntakeDraft> = {}): IntakeDraft {
  return { ...EMPTY_INTAKE, ...overrides };
}

const TRACKED = [
  {
    id: "aaa",
    opportunity_title: "Indian Community Development Block Grant",
    agency: "HUD",
    opportunity_number: "FR-6700-N-21",
    url: "https://www.grants.gov/view?oppId=349871",
  },
  {
    id: "bbb",
    opportunity_title: "Community Development Block Grant",
    agency: "Bureau of Indian Affairs",
    opportunity_number: "BIA-2026-001",
    url: "",
  },
];

// ------------------------------------------------------------ lifecycle

describe("stage mapping", () => {
  it("uses only stages the schema has", () => {
    // `GrantPipelineStage`. Inventing a competing lifecycle is the failure
    // this is guarding against: two vocabularies for "where are we with
    // this" that drift apart and disagree.
    const canonical = new Set([
      "new",
      "evaluating",
      "pursuing",
      "drafting",
      "submitted",
      "awarded",
      "not_pursuing",
    ]);
    for (const entry of INTAKE_STAGES) {
      expect(canonical.has(entry.stage)).toBe(true);
    }
  });

  it("keeps the customer's wording when two choices collapse to one stage", () => {
    // "Not awarded" and "withdrew" both map to `not_pursuing`, because that
    // is the only terminal stage the enum has. Losing and standing down are
    // not the same thing, so the words survive in the record even though the
    // stage cannot express the difference.
    const lost = draftToCreateBody(draft({ title: "T", stageId: "not_awarded" }));
    const withdrew = draftToCreateBody(draft({ title: "T", stageId: "withdrawn" }));

    expect(lost.pipeline_stage).toBe("not_pursuing");
    expect(withdrew.pipeline_stage).toBe("not_pursuing");
    expect(String(lost.eligibility_tags)).toContain("not awarded");
    expect(String(withdrew.eligibility_tags)).toContain("withdrew");
  });

  it("starts an unstated opportunity at the beginning", () => {
    expect(draftToCreateBody(draft({ title: "T" })).pipeline_stage).toBe("new");
  });
});

// ------------------------------------------------------------- the body

describe("draftToCreateBody", () => {
  it("produces the ordinary create body, so there is no import silo", () => {
    const body = draftToCreateBody(
      draft({
        title: "Indian Housing Block Grant",
        funder: "HUD",
        program: "IHBG Competitive",
        opportunityNumber: "FR-1234",
        deadline: "2026-11-16",
        url: "https://example.gov/opp",
        noticeText: "How to Apply\n\nSubmit at https://www.grants.gov/apply.",
        stageId: "pursuing",
      }),
    );

    expect(body.source).toBe("manual");
    expect(body.opportunity_title).toBe("Indian Housing Block Grant");
    expect(body.agency).toBe("HUD");
    expect(body.opportunity_number).toBe("FR-1234");
    expect(body.application_deadline).toBe("2026-11-16T23:59:00Z");
    expect(body.pipeline_stage).toBe("pursuing");
    expect(String(body.raw_nofo_text)).toContain("How to Apply");
  });

  it("says a funder was not stated rather than leaving it blank", () => {
    // `agency` is NOT NULL in the schema. An empty string would store a
    // funder whose name is nothing, which reads as a funder rather than as
    // an absence.
    expect(draftToCreateBody(draft({ title: "T" })).agency).toBe("Not stated");
  });

  it("leaves genuinely absent fields null rather than empty", () => {
    const body = draftToCreateBody(draft({ title: "T" }));
    expect(body.program_name).toBeNull();
    expect(body.opportunity_number).toBeNull();
    expect(body.url).toBeNull();
    expect(body.application_deadline).toBeNull();
    expect(body.raw_nofo_text).toBeNull();
  });

  it("does not derive the source id from the title", () => {
    // Two genuinely different competitions share a name often enough that
    // deriving identity from it would make them collide.
    const a = draftToCreateBody(draft({ title: "Community Development Block Grant" }));
    const b = draftToCreateBody(draft({ title: "Community Development Block Grant" }));
    expect(a.source_id).not.toBe(b.source_id);
  });

  it("uses the opportunity number as the source id when there is one", () => {
    expect(draftToCreateBody(draft({ title: "T", opportunityNumber: "FR-9" })).source_id).toBe(
      "FR-9",
    );
  });
});

// -------------------------------------------------------- normalisation

describe("normalisation", () => {
  it("ignores case, punctuation and spacing in a title", () => {
    expect(normaliseTitle("Indian  Community-Development Block Grant!")).toBe(
      "indian community development block grant",
    );
  });

  it("ignores tracking parameters, fragments and a trailing slash in a URL", () => {
    const plain = normaliseUrl("https://www.grants.gov/view?oppId=1");
    expect(normaliseUrl("https://www.grants.gov/view?oppId=1&utm_source=email")).toBe(plain);
    expect(normaliseUrl("https://WWW.GRANTS.GOV/view?oppId=1#section-4")).toBe(plain);
    expect(normaliseUrl("https://www.grants.gov/view/?oppId=1")).not.toBe("");
  });

  it("does not throw on something that is not a URL", () => {
    expect(normaliseUrl("not a url at all")).toBe("not a url at all");
    expect(normaliseUrl("")).toBe("");
  });
});

// ----------------------------------------------------------- duplicates

describe("findExisting", () => {
  it("matches the same link even with different tracking parameters", () => {
    const match = findExisting(
      draft({ title: "x", url: "https://www.grants.gov/view?oppId=349871&utm_medium=x" }),
      TRACKED,
    );
    expect(match.existing?.id).toBe("aaa");
    expect(match.reason).toBe("the same link");
  });

  it("matches the same opportunity number", () => {
    const match = findExisting(draft({ title: "x", opportunityNumber: "bia-2026-001" }), TRACKED);
    expect(match.existing?.id).toBe("bbb");
  });

  it("matches a title only when the funder matches too", () => {
    /*
     * The rule that matters. "Community Development Block Grant" is the name
     * of several distinct competitions across as many agencies; merging two
     * of them would hide a deadline the customer is working to.
     */
    const sameTitleOtherFunder = findExisting(
      draft({ title: "Community Development Block Grant", funder: "HUD" }),
      TRACKED,
    );
    expect(sameTitleOtherFunder.existing).toBeNull();

    const bothMatch = findExisting(
      draft({
        title: "community development block grant",
        funder: "Bureau of Indian Affairs",
      }),
      TRACKED,
    );
    expect(bothMatch.existing?.id).toBe("bbb");
  });

  it("does not match on a title alone when no funder was given", () => {
    const match = findExisting(
      draft({ title: "Indian Community Development Block Grant" }),
      TRACKED,
    );
    expect(match.existing).toBeNull();
  });

  it("finds nothing in an empty list", () => {
    expect(findExisting(draft({ title: "x", url: "https://a.example" }), []).existing).toBeNull();
  });

  it("prefers the link over the title when both could match", () => {
    // Evidence is ranked: the same link is a stronger claim than the same
    // words, so it decides.
    const match = findExisting(
      draft({
        title: "Community Development Block Grant",
        funder: "Bureau of Indian Affairs",
        url: "https://www.grants.gov/view?oppId=349871",
      }),
      TRACKED,
    );
    expect(match.existing?.id).toBe("aaa");
    expect(match.reason).toBe("the same link");
  });
});
