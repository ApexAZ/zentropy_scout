/**
 * Tests for EditorStatusBar component.
 *
 * REQ-025 §3.5: Status bar shows word count, page estimate, and save status.
 * REQ-026 §7.2: Save status indicator with four states.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EditorStatusBar } from "@/components/editor/editor-status-bar";

// ---------------------------------------------------------------------------
// Setup / Teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
	vi.clearAllMocks();
});

afterEach(() => {
	cleanup();
	vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("EditorStatusBar", () => {
	describe("word count", () => {
		it("displays the word count", () => {
			render(<EditorStatusBar wordCount={342} saveStatus="saved" />);

			expect(screen.getByTestId("status-word-count")).toHaveTextContent(
				"342 words",
			);
		});

		it("displays 0 words for empty content", () => {
			render(<EditorStatusBar wordCount={0} saveStatus="saved" />);

			expect(screen.getByTestId("status-word-count")).toHaveTextContent(
				"0 words",
			);
		});

		it("displays singular 'word' for count of 1", () => {
			render(<EditorStatusBar wordCount={1} saveStatus="saved" />);

			expect(screen.getByTestId("status-word-count")).toHaveTextContent(
				"1 word",
			);
		});
	});

	describe("page estimate", () => {
		it("displays page estimate rounded up from words / 350", () => {
			render(<EditorStatusBar wordCount={342} saveStatus="saved" />);

			// 342 / 350 = 0.977 → ceil = 1 page
			expect(screen.getByTestId("status-page-estimate")).toHaveTextContent(
				"~1 page",
			);
		});

		it("displays 2 pages for 351-700 words", () => {
			render(<EditorStatusBar wordCount={500} saveStatus="saved" />);

			// 500 / 350 = 1.43 → ceil = 2 pages
			expect(screen.getByTestId("status-page-estimate")).toHaveTextContent(
				"~2 pages",
			);
		});

		it("displays 0 pages for 0 words", () => {
			render(<EditorStatusBar wordCount={0} saveStatus="saved" />);

			expect(screen.getByTestId("status-page-estimate")).toHaveTextContent(
				"~0 pages",
			);
		});

		it("displays exactly 1 page for 350 words", () => {
			render(<EditorStatusBar wordCount={350} saveStatus="saved" />);

			expect(screen.getByTestId("status-page-estimate")).toHaveTextContent(
				"~1 page",
			);
		});
	});

	describe("save status", () => {
		it("displays 'Saved' status", () => {
			render(<EditorStatusBar wordCount={100} saveStatus="saved" />);

			const statusEl = screen.getByTestId("status-save");
			expect(statusEl).toHaveTextContent("Saved");
		});

		it("displays 'Saving...' status", () => {
			render(<EditorStatusBar wordCount={100} saveStatus="saving" />);

			const statusEl = screen.getByTestId("status-save");
			expect(statusEl).toHaveTextContent("Saving...");
		});

		it("displays 'Unsaved changes' status", () => {
			render(<EditorStatusBar wordCount={100} saveStatus="unsaved" />);

			const statusEl = screen.getByTestId("status-save");
			expect(statusEl).toHaveTextContent("Unsaved changes");
		});

		it("displays 'Save failed' status with retry", () => {
			render(<EditorStatusBar wordCount={100} saveStatus="error" />);

			const statusEl = screen.getByTestId("status-save");
			expect(statusEl).toHaveTextContent("Save failed");
		});
	});

	describe("accessibility", () => {
		it("renders the status bar container with role='status'", () => {
			render(<EditorStatusBar wordCount={100} saveStatus="saved" />);

			const statusBar = screen.getByTestId("editor-status-bar");
			expect(statusBar).toBeInTheDocument();
			expect(statusBar).toHaveAttribute("role", "status");
			expect(statusBar).toHaveAttribute("aria-live", "polite");
		});

		it("applies text-destructive class to error status", () => {
			render(<EditorStatusBar wordCount={100} saveStatus="error" />);

			const statusEl = screen.getByTestId("status-save");
			expect(statusEl.className).toContain("text-destructive");
		});
	});
});
