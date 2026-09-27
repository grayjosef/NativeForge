import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { OnboardingPage, draftToBody, stepErrors, EMPTY_DRAFT } from "./OnboardingPage";

/**
 * Onboarding's heading, and the two rules its form exists to keep.
 *
 * The heading test is here because the page had no `h1` at all: every step
 * used an `h2`, and onboarding renders outside the shell whose brand supplies
 * the heading everywhere else. A screen reader landing on the one screen in
 * the product that is nothing but a form found nothing to orient on, and no
 * test noticed for as long as the page has existed.
 */

function noop() {
  return Promise.resolve(true);
}

describe("OnboardingPage", () => {
  it("gives the page a top-level heading", async () => {
    render(<OnboardingPage busy={false} error={null} onSubmit={noop} onEnterWorkspace={vi.fn()} />);
    const heading = await screen.findByRole("heading", { level: 1 });
    expect(heading).toBeInTheDocument();
    expect(heading.textContent).toMatch(/what is your organization called/i);
  });

  it("announces the step a customer is on", async () => {
    render(<OnboardingPage busy={false} error={null} onSubmit={noop} onEnterWorkspace={vi.fn()} />);
    expect(await screen.findByText(/step 1 of 6/i)).toBeInTheDocument();
  });
});

describe("required answers", () => {
  it("will not move past a nameless organization", () => {
    // The legal name goes onto every application package NativeForge
    // prepares, so it is the one thing step one cannot leave blank.
    expect(stepErrors(0, { ...EMPTY_DRAFT })).toHaveLength(1);
    expect(stepErrors(0, { ...EMPTY_DRAFT, legal_name: "Pueblo of Santa Clara" })).toEqual(
      [],
    );
  });

  it("will not move past an unstated classification", () => {
    // Eligibility differs between the ten, so a blank here would make every
    // later eligibility answer a guess.
    expect(stepErrors(1, { ...EMPTY_DRAFT })).toHaveLength(1);
    expect(
      stepErrors(1, { ...EMPTY_DRAFT, entity_type: "federally_recognized_tribe" }),
    ).toEqual([]);
  });
});

describe("draftToBody", () => {
  it("sends null for what the customer left blank, never an empty string", () => {
    /*
     * The backend types most of these `str | None`. An empty string is a
     * value that was supplied: it would be stored, exported, and read back
     * later as though somebody had answered the question with nothing.
     */
    const body = draftToBody({
      ...EMPTY_DRAFT,
      legal_name: "Pueblo of Santa Clara",
      entity_type: "federally_recognized_tribe",
    });
    expect(body.uei).toBeNull();
    expect(body.ein).toBeNull();
    expect(body.service_area_description).toBeNull();
    expect(body.physical_address).toBeNull();
    expect(body.authorized_representative).toBeNull();
    expect(body.grants_manager).toBeNull();
    expect(body.standard_narratives).toBeNull();
  });

  it("keeps what was given", () => {
    const body = draftToBody({
      ...EMPTY_DRAFT,
      legal_name: "  Pueblo of Santa Clara  ",
      entity_type: "tribal_government",
      city: "Española",
      state: "NM",
      rep_name: "Jane Doe",
      rep_title: "Governor",
      rep_email: "jane@example.gov",
      interests: ["Housing"],
    });
    expect(body.legal_name).toBe("Pueblo of Santa Clara");
    expect(body.physical_address).toEqual({ city: "Española", state: "NM" });
    expect(body.authorized_representative).toEqual({
      name: "Jane Doe",
      title: "Governor",
      email: "jane@example.gov",
    });
    expect(body.standard_narratives).toEqual({ funding_interests: ["Housing"] });
  });

  it("sends no contact at all rather than an empty object", () => {
    // A contact record with no name and no address is not a contact, and
    // storing one would make the profile look more complete than it is.
    const body = draftToBody({ ...EMPTY_DRAFT, legal_name: "T", entity_type: "other" });
    expect(body.authorized_representative).toBeNull();
  });
});
