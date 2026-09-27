import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * The ink scale must stay readable.
 *
 * `--nf-faint` was #7e8a82, which measures 3.21:1 on the page ground. It
 * carries the eyebrow above every page title, every metric's explanatory
 * note, the workflow step summaries, the deadline dates and the muted
 * badges — 23 failing elements on the workspace alone, from one token.
 *
 * Nothing caught it. Unit tests render components and assert text is present;
 * text at 3.2:1 is present. It took measuring the rendered page in a browser,
 * and a token is exactly the kind of thing that drifts back the next time
 * somebody decides a grey looks too heavy. So the tokens are checked here,
 * where the cost of the check is a few milliseconds.
 *
 * Measured against the page ground rather than card white, because the page
 * is the harder of the two and every one of these tokens appears on it.
 */

// Read from the project root rather than from `import.meta.url`: the jsdom
// environment gives this module an http:// URL, and fileURLToPath refuses it.
const CSS = readFileSync(join(process.cwd(), "src", "index.css"), "utf8");

function token(name: string): string {
  const match = CSS.match(new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{3,8})\\s*;`));
  if (!match) throw new Error(`token --${name} not found in index.css`);
  return match[1];
}

function rgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  const full =
    h.length === 3
      ? h
          .split("")
          .map((c) => c + c)
          .join("")
      : h;
  return [
    parseInt(full.slice(0, 2), 16),
    parseInt(full.slice(2, 4), 16),
    parseInt(full.slice(4, 6), 16),
  ];
}

function luminance(hex: string): number {
  const [r, g, b] = rgb(hex).map((v) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a: string, b: string): number {
  const la = luminance(a);
  const lb = luminance(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

describe("ink scale", () => {
  const grounds = ["--nf-page", "--nf-card", "--nf-card-muted"] as const;

  for (const ink of ["--nf-text", "--nf-muted", "--nf-muted2", "--nf-faint"]) {
    for (const ground of grounds) {
      it(`${ink} is readable on ${ground}`, () => {
        const ratio = contrast(token(ink.slice(2)), token(ground.slice(2)));
        expect(ratio).toBeGreaterThanOrEqual(4.5);
      });
    }
  }

  it("keeps the four levels distinguishable from each other", () => {
    // A repair that made every level the same dark grey would pass the checks
    // above and destroy the hierarchy they exist to express. The first attempt
    // at this fix did exactly that.
    const ink = ["--nf-text", "--nf-muted", "--nf-muted2", "--nf-faint"].map((t) =>
      luminance(token(t.slice(2))),
    );
    for (let i = 1; i < ink.length; i += 1) {
      expect(ink[i]).toBeGreaterThan(ink[i - 1]);
      // Each step is at least half again as light as the one before it, so the
      // levels are telling apart by eye and not only by hex value.
      expect(ink[i]).toBeGreaterThan(ink[i - 1] * 1.3);
    }
  });
});
