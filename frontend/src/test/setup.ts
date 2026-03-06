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

// Polyfill getClientRects for ProseMirror (TipTap) cursor positioning in jsdom.
// ProseMirror calls getClientRects() on text nodes and elements to compute
// cursor coordinates. jsdom does not implement layout, so we return a stub rect.
const stubRect = {
	top: 0,
	right: 0,
	bottom: 0,
	left: 0,
	width: 0,
	height: 0,
	x: 0,
	y: 0,
	toJSON: () => ({}),
};
const stubDOMRectList = Object.assign([stubRect], {
	item: (_index: number) => stubRect,
});

if (typeof HTMLElement.prototype.getClientRects === "undefined") {
	HTMLElement.prototype.getClientRects = () =>
		stubDOMRectList as unknown as DOMRectList;
}

if (typeof Range.prototype.getClientRects === "undefined") {
	Range.prototype.getClientRects = () =>
		stubDOMRectList as unknown as DOMRectList;
}

if (typeof Range.prototype.getBoundingClientRect === "undefined") {
	Range.prototype.getBoundingClientRect = () => stubRect as DOMRect;
}

// Auto-cleanup DOM between tests.
// @testing-library/react auto-cleanup depends on a global afterEach, which
// is not available when vitest globals are disabled (the default).
afterEach(() => {
	cleanup();
});
