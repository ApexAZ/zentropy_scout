/**
 * Tests for the CultureSignals component (§7.10).
 *
 * REQ-012 §8.3: Culture text display with quoted italic style.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { CultureSignals } from "./culture-signals";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SECTION_TESTID = "culture-signals";
const NOT_AVAILABLE_TESTID = "culture-not-available";
const TEXT_TESTID = "culture-text";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderCulture(cultureText: string | null, className?: string) {
	return render(
		<CultureSignals cultureText={cultureText} className={className} />,
	);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("CultureSignals", () => {
	afterEach(() => {
		cleanup();
	});

	it("renders 'No culture signals' badge when null", () => {
		renderCulture(null);

		expect(screen.getByTestId(NOT_AVAILABLE_TESTID)).toBeInTheDocument();
		expect(screen.getByTestId(NOT_AVAILABLE_TESTID)).toHaveTextContent(
			"No culture signals",
		);
	});

	it("does not render culture text when null", () => {
		renderCulture(null);

		expect(screen.queryByTestId(TEXT_TESTID)).not.toBeInTheDocument();
	});

	it("renders culture text in paragraph element", () => {
		renderCulture("We value collaboration and innovation.");

		const text = screen.getByTestId(TEXT_TESTID);
		expect(text).toHaveTextContent("We value collaboration and innovation.");
		expect(text.tagName).toBe("P");
	});

	it("wraps culture text in quotation marks", () => {
		renderCulture("Fast-paced environment");

		const text = screen.getByTestId(TEXT_TESTID);
		expect(text.textContent).toBe("\u201CFast-paced environment\u201D");
	});

	it("merges custom className", () => {
		renderCulture("Team first.", "mt-4");

		const section = screen.getByTestId(SECTION_TESTID);
		expect(section).toHaveClass("mt-4");
	});
});
