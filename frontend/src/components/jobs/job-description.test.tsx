/**
 * Tests for the JobDescription component (§7.10).
 *
 * REQ-012 §8.3: Full job description text display.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { JobDescription } from "./job-description";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SECTION_TESTID = "job-description";
const TEXT_TESTID = "description-text";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderDescription(description: string, className?: string) {
	return render(
		<JobDescription description={description} className={className} />,
	);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("JobDescription", () => {
	afterEach(() => {
		cleanup();
	});

	it("renders description text in paragraph element", () => {
		renderDescription("We are looking for a senior engineer.");

		const text = screen.getByTestId(TEXT_TESTID);
		expect(text).toHaveTextContent("We are looking for a senior engineer.");
		expect(text.tagName).toBe("P");
	});

	it("renders section heading 'Description'", () => {
		renderDescription("Some description.");

		const section = screen.getByTestId(SECTION_TESTID);
		expect(section).toHaveTextContent("Description");
	});

	it("has whitespace-pre-line class on text element", () => {
		renderDescription("Line one\nLine two");

		const text = screen.getByTestId(TEXT_TESTID);
		expect(text).toHaveClass("whitespace-pre-line");
	});

	it("renders empty string without crashing", () => {
		renderDescription("");

		expect(screen.getByTestId(SECTION_TESTID)).toBeInTheDocument();
		expect(screen.getByTestId(TEXT_TESTID)).toBeInTheDocument();
	});

	it("merges custom className", () => {
		renderDescription("Description text.", "mt-4");

		const section = screen.getByTestId(SECTION_TESTID);
		expect(section).toHaveClass("mt-4");
	});
});
