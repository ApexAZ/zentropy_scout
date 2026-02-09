import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

import "@testing-library/jest-dom/vitest";

// Auto-cleanup DOM between tests.
// @testing-library/react auto-cleanup depends on a global afterEach, which
// is not available when vitest globals are disabled (the default).
afterEach(() => {
	cleanup();
});
