import { describe, expect, it } from "vitest";

import { cn } from "./utils";

describe("cn", () => {
	it("merges class names", () => {
		expect(cn("foo", "bar")).toBe("foo bar");
	});

	it("handles conditional classes", () => {
		expect(cn("foo", false && "bar", "baz")).toBe("foo baz");
	});

	it("resolves Tailwind conflicts with last-wins", () => {
		expect(cn("px-2 py-1", "px-4")).toBe("py-1 px-4");
	});

	it("returns empty string when given no arguments", () => {
		expect(cn()).toBe("");
	});
});
