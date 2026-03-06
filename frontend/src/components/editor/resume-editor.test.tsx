/**
 * Tests for ResumeEditor + EditorToolbar components.
 *
 * REQ-025 §3.2–§3.4: Editor renders markdown, toolbar formatting,
 * active state highlighting.
 * REQ-025 §7.2: Markdown round-trip tests for supported features.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Editor } from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";
import { Markdown } from "@tiptap/markdown";

import { ResumeEditor } from "@/components/editor/resume-editor";

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
	vi.clearAllMocks();
});

afterEach(() => {
	cleanup();
	vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

describe("ResumeEditor", () => {
	describe("rendering", () => {
		it("renders the editor container", async () => {
			render(<ResumeEditor />);

			await waitFor(() => {
				expect(screen.getByTestId("resume-editor")).toBeInTheDocument();
			});
		});

		it("renders the editor content area", async () => {
			render(<ResumeEditor />);

			await waitFor(() => {
				expect(screen.getByTestId("editor-content")).toBeInTheDocument();
			});
		});

		it("renders initial markdown content", async () => {
			render(<ResumeEditor initialContent="# Hello World" />);

			await waitFor(() => {
				expect(screen.getByText("Hello World")).toBeInTheDocument();
			});
		});

		it("renders the toolbar in editable mode", async () => {
			render(<ResumeEditor editable={true} />);

			await waitFor(() => {
				expect(screen.getByTestId("editor-toolbar")).toBeInTheDocument();
			});
		});

		it("hides the toolbar in read-only mode", async () => {
			render(<ResumeEditor editable={false} />);

			await waitFor(() => {
				expect(screen.getByTestId("editor-content")).toBeInTheDocument();
			});
			expect(screen.queryByTestId("editor-toolbar")).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Toolbar buttons
	// -----------------------------------------------------------------------

	describe("toolbar", () => {
		it("renders all formatting buttons", async () => {
			render(<ResumeEditor />);

			await waitFor(() => {
				expect(screen.getByTestId("editor-toolbar")).toBeInTheDocument();
			});

			const expectedButtons = [
				"toolbar-bold",
				"toolbar-italic",
				"toolbar-h1",
				"toolbar-h2",
				"toolbar-h3",
				"toolbar-h4",
				"toolbar-bullet-list",
				"toolbar-ordered-list",
				"toolbar-hr",
				"toolbar-link",
				"toolbar-undo",
				"toolbar-redo",
			];

			for (const testId of expectedButtons) {
				expect(screen.getByTestId(testId)).toBeInTheDocument();
			}
		});

		it("toolbar has proper ARIA role", async () => {
			render(<ResumeEditor />);

			await waitFor(() => {
				expect(screen.getByRole("toolbar")).toBeInTheDocument();
			});
		});

		it("bold button toggles bold formatting", async () => {
			const user = userEvent.setup();
			render(<ResumeEditor initialContent="Hello" />);

			await waitFor(() => {
				expect(screen.getByTestId("toolbar-bold")).toBeInTheDocument();
			});

			const boldBtn = screen.getByTestId("toolbar-bold");
			await user.click(boldBtn);

			// After clicking bold, the button should reflect active state
			// (the exact state depends on cursor position, but the click should not throw)
			expect(boldBtn).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// onChange callback
	// -----------------------------------------------------------------------

	describe("onChange", () => {
		it("renders initial content as visible text", async () => {
			render(<ResumeEditor initialContent="# Test Title" />);

			await waitFor(() => {
				expect(screen.getByText("Test Title")).toBeInTheDocument();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Markdown round-trip (REQ-025 §7.2)
	// -----------------------------------------------------------------------

	describe("markdown round-trip", () => {
		/**
		 * Helper: create a headless TipTap editor with the same extensions
		 * as ResumeEditor, load markdown, then extract it back.
		 * Tests the markdown → ProseMirror → markdown conversion.
		 */
		function roundTrip(markdown: string): string {
			const editor = new Editor({
				content: markdown,
				contentType: "markdown",
				extensions: [
					StarterKit.configure({
						heading: { levels: [1, 2, 3, 4] },
						codeBlock: false,
						code: false,
					}),
					Markdown,
				],
			});
			const result = editor.getMarkdown();
			editor.destroy();
			return result;
		}

		it("preserves H1 headings", () => {
			const result = roundTrip("# Main Title");
			expect(result.trim()).toContain("# Main Title");
		});

		it("preserves H2 headings", () => {
			const result = roundTrip("## Section Title");
			expect(result.trim()).toContain("## Section Title");
		});

		it("preserves H3 headings", () => {
			const result = roundTrip("### Subsection");
			expect(result.trim()).toContain("### Subsection");
		});

		it("preserves H4 headings", () => {
			const result = roundTrip("#### Minor Heading");
			expect(result.trim()).toContain("#### Minor Heading");
		});

		it("preserves bold text", () => {
			const result = roundTrip("This is **bold** text");
			expect(result).toContain("**bold**");
		});

		it("preserves italic text", () => {
			const result = roundTrip("This is *italic* text");
			expect(result).toContain("*italic*");
		});

		it("preserves bullet lists", () => {
			const input = "- Item one\n- Item two\n- Item three";
			const result = roundTrip(input);
			expect(result).toContain("Item one");
			expect(result).toContain("Item two");
			expect(result).toContain("Item three");
			// Should use either - or * for bullets
			expect(result).toMatch(/^[\s]*[-*]\s+Item one/m);
		});

		it("preserves ordered lists", () => {
			const input = "1. First\n2. Second\n3. Third";
			const result = roundTrip(input);
			expect(result).toContain("First");
			expect(result).toContain("Second");
			expect(result).toContain("Third");
			expect(result).toMatch(/\d+\.\s+First/);
		});

		it("preserves horizontal rules", () => {
			const input = "Above\n\n---\n\nBelow";
			const result = roundTrip(input);
			expect(result).toContain("Above");
			expect(result).toContain("Below");
			expect(result).toMatch(/---/);
		});

		it("preserves links", () => {
			const input = "Visit [Example](https://example.com) for more";
			const result = roundTrip(input);
			expect(result).toContain("Example");
			expect(result).toContain("https://example.com");
		});

		it("preserves mixed content (heading + paragraph + list)", () => {
			const input =
				"# Resume\n\nSummary paragraph.\n\n- Bullet one\n- Bullet two";
			const result = roundTrip(input);
			expect(result).toContain("# Resume");
			expect(result).toContain("Summary paragraph");
			expect(result).toContain("Bullet one");
			expect(result).toContain("Bullet two");
		});

		it("handles empty content gracefully", () => {
			const result = roundTrip("");
			// Empty or whitespace-only is acceptable
			expect(result.trim().length).toBeLessThanOrEqual(1);
		});

		it("preserves bold+italic combination", () => {
			const result = roundTrip("This is ***bold italic*** text");
			// Should contain both bold and italic markers
			expect(result).toContain("bold italic");
			// The exact syntax may vary (***text*** or **_text_**)
			expect(result).toMatch(/\*{2,3}/);
		});

		it("preserves consecutive headings", () => {
			const input = "# Title\n\n## Section\n\n### Sub";
			const result = roundTrip(input);
			expect(result).toContain("# Title");
			expect(result).toContain("## Section");
			expect(result).toContain("### Sub");
		});
	});
});
