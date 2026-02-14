import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

import "@testing-library/jest-dom/vitest";

// Polyfill ResizeObserver for Radix UI components that depend on useSize.
if (typeof globalThis.ResizeObserver === "undefined") {
	globalThis.ResizeObserver = class ResizeObserver {
		observe() {}
		unobserve() {}
		disconnect() {}
	};
}

// Polyfill pointer capture methods for Radix UI Select in jsdom.
// jsdom doesn't implement these, causing "hasPointerCapture is not a function".
if (typeof Element.prototype.hasPointerCapture === "undefined") {
	Element.prototype.hasPointerCapture = () => false;
	Element.prototype.setPointerCapture = () => {};
	Element.prototype.releasePointerCapture = () => {};
}

// Polyfill scrollIntoView for Radix UI Select item focus in jsdom.
if (typeof Element.prototype.scrollIntoView === "undefined") {
	Element.prototype.scrollIntoView = () => {};
}

// Auto-cleanup DOM between tests.
// @testing-library/react auto-cleanup depends on a global afterEach, which
// is not available when vitest globals are disabled (the default).
afterEach(() => {
	cleanup();
});
