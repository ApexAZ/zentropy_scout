/**
 * Tests for DiffView component.
 *
 * REQ-027 §4.1–§4.4: Diff view layout, highlighting, and implementation.
 * REQ-027 §8: Fallback when diff computation fails.
 */

import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
	mockDiffWords: vi.fn(),
	realDiffWords: undefined as
		| ((oldStr: string, newStr: string) => unknown)
		| undefined,
}));

vi.mock("diff", async (importOriginal) => {
	const actual = await importOriginal<typeof import("diff")>();
	mocks.realDiffWords = actual.diffWords;
	return { ...actual, diffWords: mocks.mockDiffWords };
});

import { DiffView } from "./diff-view";

// ---------------------------------------------------------------------------
// Setup / Teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
	vi.clearAllMocks();
	if (!mocks.realDiffWords) {
		throw new Error("realDiffWords not captured from import");
	}
	mocks.mockDiffWords.mockImplementation(mocks.realDiffWords);
});

afterEach(() => {
	cleanup();
	vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("DiffView", () => {
	describe("rendering", () => {
		it("renders side-by-side layout with master and variant panels", () => {
			render(<DiffView masterMarkdown="hello" variantMarkdown="hello" />);

			expect(screen.getByTestId("diff-view")).toBeInTheDocument();
			expect(screen.getByTestId("diff-master-panel")).toBeInTheDocument();
			expect(screen.getByTestId("diff-variant-panel")).toBeInTheDocument();
		});

		it("labels master panel as read-only", () => {
			render(<DiffView masterMarkdown="hello" variantMarkdown="hello" />);

			const masterPanel = screen.getByTestId("diff-master-panel");
			expect(
				within(masterPanel).getByText(/master resume/i),
			).toBeInTheDocument();
			expect(within(masterPanel).getByText(/read-only/i)).toBeInTheDocument();
		});

		it("labels variant panel as tailored variant", () => {
			render(<DiffView masterMarkdown="hello" variantMarkdown="hello" />);

			const variantPanel = screen.getByTestId("diff-variant-panel");
			expect(
				within(variantPanel).getByText(/tailored variant/i),
			).toBeInTheDocument();
		});
	});

	describe("additions", () => {
		it("highlights added text with success background on the variant side", () => {
			render(<DiffView masterMarkdown="hello" variantMarkdown="hello world" />);

			const variantPanel = screen.getByTestId("diff-variant-panel");
			const addedSpan = within(variantPanel).getByText(/world/);
			expect(addedSpan.className).toContain("bg-success");
		});

		it("does not show added text on the master side", () => {
			render(<DiffView masterMarkdown="hello" variantMarkdown="hello world" />);

			const masterPanel = screen.getByTestId("diff-master-panel");
			expect(within(masterPanel).queryByText(/world/)).not.toBeInTheDocument();
		});
	});

	describe("removals", () => {
		it("highlights removed text with destructive strikethrough on the master side", () => {
			render(<DiffView masterMarkdown="hello world" variantMarkdown="hello" />);

			const masterPanel = screen.getByTestId("diff-master-panel");
			const removedSpan = within(masterPanel).getByText(/world/);
			expect(removedSpan.className).toContain("bg-destructive");
			expect(removedSpan.className).toContain("line-through");
		});

		it("does not show removed text on the variant side", () => {
			render(<DiffView masterMarkdown="hello world" variantMarkdown="hello" />);

			const variantPanel = screen.getByTestId("diff-variant-panel");
			expect(within(variantPanel).queryByText(/world/)).not.toBeInTheDocument();
		});
	});

	describe("modifications", () => {
		it("highlights modified text with warning color on both sides", () => {
			render(
				<DiffView masterMarkdown="hello world" variantMarkdown="hello earth" />,
			);

			const masterPanel = screen.getByTestId("diff-master-panel");
			const variantPanel = screen.getByTestId("diff-variant-panel");

			const oldText = within(masterPanel).getByText(/world/);
			const newText = within(variantPanel).getByText(/earth/);

			expect(oldText.className).toContain("bg-warning");
			expect(newText.className).toContain("bg-warning");
		});

		it("does not apply strikethrough to modified text", () => {
			render(
				<DiffView masterMarkdown="hello world" variantMarkdown="hello earth" />,
			);

			const masterPanel = screen.getByTestId("diff-master-panel");
			const oldText = within(masterPanel).getByText(/world/);
			expect(oldText.className).not.toContain("line-through");
		});
	});

	describe("identical content", () => {
		it("renders both documents without highlighting when content is identical", () => {
			render(
				<DiffView masterMarkdown="hello world" variantMarkdown="hello world" />,
			);

			const masterPanel = screen.getByTestId("diff-master-panel");
			const variantPanel = screen.getByTestId("diff-variant-panel");

			expect(within(masterPanel).getByText(/hello world/)).toBeInTheDocument();
			expect(within(variantPanel).getByText(/hello world/)).toBeInTheDocument();

			const allHighlighted = screen
				.getByTestId("diff-view")
				.querySelectorAll(
					"[class*='bg-success'], [class*='bg-destructive'], [class*='bg-warning']",
				);
			expect(allHighlighted).toHaveLength(0);
		});
	});

	describe("empty documents", () => {
		it("handles empty master with all additions highlighted", () => {
			render(<DiffView masterMarkdown="" variantMarkdown="hello world" />);

			const variantPanel = screen.getByTestId("diff-variant-panel");
			const addedSpan = within(variantPanel).getByText(/hello world/);
			expect(addedSpan.className).toContain("bg-success");
		});

		it("handles empty variant with all removals highlighted", () => {
			render(<DiffView masterMarkdown="hello world" variantMarkdown="" />);

			const masterPanel = screen.getByTestId("diff-master-panel");
			const removedSpan = within(masterPanel).getByText(/hello world/);
			expect(removedSpan.className).toContain("bg-destructive");
		});

		it("handles both documents empty without errors", () => {
			render(<DiffView masterMarkdown="" variantMarkdown="" />);

			expect(screen.getByTestId("diff-view")).toBeInTheDocument();
		});
	});

	describe("fallback", () => {
		it("shows both documents without highlighting when diff computation fails", () => {
			mocks.mockDiffWords.mockImplementationOnce(() => {
				throw new Error("Diff failed");
			});

			render(<DiffView masterMarkdown="hello" variantMarkdown="hello world" />);

			expect(screen.getByTestId("diff-view")).toBeInTheDocument();

			const masterPanel = screen.getByTestId("diff-master-panel");
			const variantPanel = screen.getByTestId("diff-variant-panel");

			expect(within(masterPanel).getByText("hello")).toBeInTheDocument();
			expect(within(variantPanel).getByText(/hello world/)).toBeInTheDocument();

			const highlighted = screen
				.getByTestId("diff-view")
				.querySelectorAll(
					"[class*='bg-success'], [class*='bg-destructive'], [class*='bg-warning']",
				);
			expect(highlighted).toHaveLength(0);
		});
	});
});
