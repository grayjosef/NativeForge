import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

/**
 * Unmount what a test rendered, after every test.
 *
 * Testing Library registers this itself — but only when the runner exposes
 * `afterEach` as a global, and this project runs vitest without globals. So
 * nothing was ever unmounted: each test in a file rendered on top of the last
 * one, and the moment a second test looked for the same control it got
 * "Found multiple elements" and failed for a reason with nothing to do with
 * the code under test.
 *
 * It went unnoticed because every existing test file either rendered once or
 * happened to query something different each time.
 */
afterEach(cleanup);
