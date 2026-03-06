/**
 * Tests for the ResumeContentView component.
 *
 * REQ-026 §6.1: Toggle view (Preview/Edit) with TipTap editor.
 * REQ-026 §6.2: Action buttons per mode.
 * REQ-026 §6.3: Content preview via read-only TipTap.
 */

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const RESUME_ID = "r-1";
const PERSONA_ID = "p-1";
const MARKDOWN_CONTENT = "# Hello World\n\nSome resume content here.";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
	mockUseAutoSave: vi.fn().mockReturnValue({
		saveStatus: "saved" as const,
		hasConflict: false,
	}),
}));

vi.mock("@/lib/api-client", () => ({
	buildUrl: (path: string) => `http://localhost:8000/api/v1${path}`,
}));

vi.mock("@/components/editor/resume-editor", () => ({
	ResumeEditor: ({
		initialContent,
		editable,
		onChange,
	}: {
		initialContent?: string;
		editable?: boolean;
		onChange?: (markdown: string) => void;
	}) => (
		<div
			data-testid="resume-editor"
			data-editable={String(editable ?? true)}
			data-initial-content={initialContent ?? ""}
		>
			<button
				data-testid="trigger-editor-change"
				onClick={() => onChange?.("updated content")}
			>
				trigger-change
			</button>
		</div>
	),
}));

vi.mock("@/components/editor/editor-status-bar", () => ({
	EditorStatusBar: ({
		wordCount,
		saveStatus,
	}: {
		wordCount: number;
		saveStatus: string;
	}) => (
		<div
			data-testid="editor-status-bar"
			data-word-count={wordCount}
			data-save-status={saveStatus}
		/>
	),
}));

vi.mock("@/hooks/use-auto-save", () => ({
	useAutoSave: (opts: Record<string, unknown>) => mocks.mockUseAutoSave(opts),
}));

vi.mock("@/components/editor/persona-reference-panel", () => ({
	PersonaReferencePanel: ({ personaId }: { personaId: string }) => (
		<div data-testid="persona-reference-panel" data-persona-id={personaId} />
	),
}));

vi.mock("@/components/ui/sheet", () => ({
	Sheet: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
	SheetContent: ({ children }: { children: React.ReactNode }) => (
		<div>{children}</div>
	),
	SheetDescription: ({ children }: { children: React.ReactNode }) => (
		<div>{children}</div>
	),
	SheetHeader: ({ children }: { children: React.ReactNode }) => (
		<div>{children}</div>
	),
	SheetTitle: ({ children }: { children: React.ReactNode }) => (
		<div>{children}</div>
	),
	SheetTrigger: ({ children }: { children: React.ReactNode }) => (
		<div>{children}</div>
	),
}));

import { ResumeContentView } from "./resume-content-view";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderWithContent(markdownContent: string = MARKDOWN_CONTENT) {
	return render(
		<ResumeContentView
			resumeId={RESUME_ID}
			personaId={PERSONA_ID}
			markdownContent={markdownContent}
		/>,
	);
}

function renderWithoutContent() {
	return render(
		<ResumeContentView
			resumeId={RESUME_ID}
			personaId={PERSONA_ID}
			markdownContent={null}
		/>,
	);
}

async function switchToEditMode(user: ReturnType<typeof userEvent.setup>) {
	await user.click(screen.getByRole("tab", { name: /edit/i }));
}

// ---------------------------------------------------------------------------
// Setup / Teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
	mocks.mockUseAutoSave.mockReset();
	mocks.mockUseAutoSave.mockReturnValue({
		saveStatus: "saved" as const,
		hasConflict: false,
	});
});

afterEach(() => {
	cleanup();
	vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ResumeContentView", () => {
	describe("countWords (via EditorStatusBar)", () => {
		it("shows correct word count for multi-word content", async () => {
			const user = userEvent.setup();
			renderWithContent("hello world foo bar");
			await switchToEditMode(user);

			expect(screen.getByTestId("editor-status-bar")).toHaveAttribute(
				"data-word-count",
				"4",
			);
		});

		it("counts single word correctly", async () => {
			const user = userEvent.setup();
			renderWithContent("hello");
			await switchToEditMode(user);

			expect(screen.getByTestId("editor-status-bar")).toHaveAttribute(
				"data-word-count",
				"1",
			);
		});

		it("updates word count when editor content changes", async () => {
			const user = userEvent.setup();
			renderWithContent(MARKDOWN_CONTENT);
			await switchToEditMode(user);

			// Trigger onChange with "updated content" (2 words)
			await user.click(screen.getByTestId("trigger-editor-change"));

			expect(screen.getByTestId("editor-status-bar")).toHaveAttribute(
				"data-word-count",
				"2",
			);
		});
	});

	describe("no-content state", () => {
		it("shows no-content prompt when markdownContent is null", () => {
			renderWithoutContent();
			expect(screen.getByTestId("no-content-prompt")).toBeInTheDocument();
			expect(screen.getByText(/generate your resume/i)).toBeInTheDocument();
		});

		it("shows prominent icon in no-content state", () => {
			renderWithoutContent();
			const prompt = screen.getByTestId("no-content-prompt");
			const svg = prompt.querySelector("svg");
			expect(svg).toBeInTheDocument();
		});

		it("renders disabled Generate with AI button", () => {
			renderWithoutContent();
			expect(
				screen.getByRole("button", { name: /generate with ai/i }),
			).toBeDisabled();
		});

		it("renders disabled Start from Template button", () => {
			renderWithoutContent();
			expect(
				screen.getByRole("button", { name: /start from template/i }),
			).toBeDisabled();
		});

		it("does not render toggle tabs", () => {
			renderWithoutContent();
			expect(
				screen.queryByRole("tab", { name: /preview/i }),
			).not.toBeInTheDocument();
		});

		it("does not render TipTap editor", () => {
			renderWithoutContent();
			expect(screen.queryByTestId("resume-editor")).not.toBeInTheDocument();
		});
	});

	describe("toggle view", () => {
		it("defaults to Preview mode", () => {
			renderWithContent();
			expect(screen.getByRole("tab", { name: /preview/i })).toHaveAttribute(
				"data-state",
				"active",
			);
		});

		it("renders read-only editor in Preview mode", () => {
			renderWithContent();
			const editor = screen.getByTestId("resume-editor");
			expect(editor).toHaveAttribute("data-editable", "false");
		});

		it("passes markdownContent to editor", () => {
			renderWithContent();
			const editor = screen.getByTestId("resume-editor");
			expect(editor).toHaveAttribute("data-initial-content", MARKDOWN_CONTENT);
		});

		it("switches to Edit mode on tab click", async () => {
			const user = userEvent.setup();
			renderWithContent();
			await switchToEditMode(user);

			expect(screen.getByRole("tab", { name: /edit/i })).toHaveAttribute(
				"data-state",
				"active",
			);
		});

		it("renders editable editor in Edit mode", async () => {
			const user = userEvent.setup();
			renderWithContent();
			await switchToEditMode(user);

			const editor = screen.getByTestId("resume-editor");
			expect(editor).toHaveAttribute("data-editable", "true");
		});

		it("shows EditorStatusBar in Edit mode", async () => {
			const user = userEvent.setup();
			renderWithContent();
			await switchToEditMode(user);

			expect(screen.getByTestId("editor-status-bar")).toBeInTheDocument();
		});

		it("does not show EditorStatusBar in Preview mode", () => {
			renderWithContent();
			expect(screen.queryByTestId("editor-status-bar")).not.toBeInTheDocument();
		});

		it("switches back to Preview via Done Editing button", async () => {
			const user = userEvent.setup();
			renderWithContent();
			await switchToEditMode(user);

			await user.click(screen.getByRole("button", { name: /done editing/i }));

			expect(screen.getByRole("tab", { name: /preview/i })).toHaveAttribute(
				"data-state",
				"active",
			);
		});
	});

	describe("export buttons", () => {
		it("renders Export PDF button with correct URL", () => {
			const windowOpen = vi
				.spyOn(window, "open")
				.mockImplementation(() => null);
			renderWithContent();

			const btn = screen.getByRole("button", { name: /export pdf/i });
			btn.click();

			expect(windowOpen).toHaveBeenCalledWith(
				`http://localhost:8000/api/v1/base-resumes/${RESUME_ID}/export/pdf`,
				"_blank",
			);
			windowOpen.mockRestore();
		});

		it("renders Export DOCX button with correct URL", () => {
			const windowOpen = vi
				.spyOn(window, "open")
				.mockImplementation(() => null);
			renderWithContent();

			const btn = screen.getByRole("button", { name: /export docx/i });
			btn.click();

			expect(windowOpen).toHaveBeenCalledWith(
				`http://localhost:8000/api/v1/base-resumes/${RESUME_ID}/export/docx`,
				"_blank",
			);
			windowOpen.mockRestore();
		});

		it("shows export buttons in both Preview and Edit modes", async () => {
			const user = userEvent.setup();
			renderWithContent();

			// Preview mode
			expect(
				screen.getByRole("button", { name: /export pdf/i }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("button", { name: /export docx/i }),
			).toBeInTheDocument();

			// Edit mode
			await switchToEditMode(user);

			expect(
				screen.getByRole("button", { name: /export pdf/i }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("button", { name: /export docx/i }),
			).toBeInTheDocument();
		});
	});

	describe("action buttons per mode", () => {
		it("shows Edit button in Preview mode", () => {
			renderWithContent();
			expect(
				screen.getByRole("button", { name: /^edit$/i }),
			).toBeInTheDocument();
		});

		it("shows Generate with AI button in Preview mode", () => {
			renderWithContent();
			expect(
				screen.getByRole("button", { name: /generate with ai/i }),
			).toBeInTheDocument();
		});

		it("clicking Edit button switches to Edit mode", async () => {
			const user = userEvent.setup();
			renderWithContent();

			await user.click(screen.getByRole("button", { name: /^edit$/i }));

			expect(screen.getByRole("tab", { name: /edit/i })).toHaveAttribute(
				"data-state",
				"active",
			);
		});

		it("shows Done Editing in Edit mode instead of Edit button", async () => {
			const user = userEvent.setup();
			renderWithContent();
			await switchToEditMode(user);

			expect(
				screen.getByRole("button", { name: /done editing/i }),
			).toBeInTheDocument();
			expect(
				screen.queryByRole("button", { name: /^edit$/i }),
			).not.toBeInTheDocument();
		});
	});

	describe("auto-save integration", () => {
		it("calls useAutoSave with resumeId and content", () => {
			renderWithContent();
			expect(mocks.mockUseAutoSave).toHaveBeenCalledWith(
				expect.objectContaining({
					resumeId: RESUME_ID,
					content: MARKDOWN_CONTENT,
				}),
			);
		});

		it("disables auto-save in Preview mode", () => {
			renderWithContent();
			expect(mocks.mockUseAutoSave).toHaveBeenCalledWith(
				expect.objectContaining({ enabled: false }),
			);
		});

		it("enables auto-save in Edit mode", async () => {
			const user = userEvent.setup();
			renderWithContent();
			await switchToEditMode(user);

			expect(mocks.mockUseAutoSave).toHaveBeenCalledWith(
				expect.objectContaining({ enabled: true }),
			);
		});

		it("updates content when editor onChange fires", async () => {
			const user = userEvent.setup();
			renderWithContent();
			await switchToEditMode(user);

			await user.click(screen.getByTestId("trigger-editor-change"));

			expect(mocks.mockUseAutoSave).toHaveBeenCalledWith(
				expect.objectContaining({ content: "updated content" }),
			);
		});
	});
});
