/**
 * Tests for the ResumeContentView component.
 *
 * REQ-026 §6.1: Toggle view (Preview/Edit) with TipTap editor.
 * REQ-026 §6.2: Action buttons per mode.
 * REQ-026 §6.3: Content preview via read-only TipTap.
 * REQ-026 §4.2: Generation options panel integration.
 * REQ-026 §4.7: Regeneration.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
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
	mockShowToast: {
		success: vi.fn(),
		error: vi.fn(),
		info: vi.fn(),
	},
}));

vi.mock("@/lib/api-client", () => ({
	buildUrl: (path: string) => `http://localhost:8000/api/v1${path}`,
}));

vi.mock("@/lib/toast", () => ({
	showToast: mocks.mockShowToast,
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

vi.mock("@/components/editor/generation-options-panel", () => ({
	GenerationOptionsPanel: ({
		onGenerate,
		onCancel,
		isGenerating,
	}: {
		onGenerate: (opts: Record<string, unknown>) => void;
		onCancel: () => void;
		isGenerating: boolean;
	}) => (
		<div
			data-testid="generation-options-panel"
			data-generating={String(isGenerating)}
		>
			<button
				data-testid="mock-generate-btn"
				onClick={() =>
					onGenerate({
						pageLimit: 1,
						emphasis: "balanced",
						includeSections: ["summary", "experience"],
					})
				}
			>
				Generate
			</button>
			<button data-testid="mock-cancel-btn" onClick={onCancel}>
				Cancel
			</button>
		</div>
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

import type { GenerateResumeResponse } from "@/types/resume-generation";

import { ResumeContentView } from "./resume-content-view";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeOnGenerate() {
	return vi.fn().mockResolvedValue({
		markdown_content: "# Generated",
		word_count: 1,
		method: "ai",
		model_used: "claude",
		generation_cost_cents: 5,
	} satisfies GenerateResumeResponse);
}

function renderWithContent(
	markdownContent: string = MARKDOWN_CONTENT,
	overrides?: Partial<{
		isGenerating: boolean;
		onGenerate: ReturnType<typeof makeOnGenerate>;
	}>,
) {
	const onGenerate = overrides?.onGenerate ?? makeOnGenerate();
	return {
		...render(
			<ResumeContentView
				resumeId={RESUME_ID}
				personaId={PERSONA_ID}
				markdownContent={markdownContent}
				isGenerating={overrides?.isGenerating ?? false}
				onGenerate={onGenerate}
			/>,
		),
		onGenerate,
	};
}

function renderWithoutContent(
	overrides?: Partial<{
		isGenerating: boolean;
		onGenerate: ReturnType<typeof makeOnGenerate>;
	}>,
) {
	const onGenerate = overrides?.onGenerate ?? makeOnGenerate();
	return {
		...render(
			<ResumeContentView
				resumeId={RESUME_ID}
				personaId={PERSONA_ID}
				markdownContent={null}
				isGenerating={overrides?.isGenerating ?? false}
				onGenerate={onGenerate}
			/>,
		),
		onGenerate,
	};
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
	mocks.mockShowToast.success.mockReset();
	mocks.mockShowToast.error.mockReset();
	mocks.mockShowToast.info.mockReset();
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

		it("renders enabled Generate with AI button", () => {
			renderWithoutContent();
			expect(
				screen.getByRole("button", { name: /generate with ai/i }),
			).toBeEnabled();
		});

		it("renders enabled Start from Template button", () => {
			renderWithoutContent();
			expect(
				screen.getByRole("button", { name: /start from template/i }),
			).toBeEnabled();
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

	describe("generation flow — AI path", () => {
		it("shows options panel when Generate with AI is clicked", async () => {
			const user = userEvent.setup();
			renderWithoutContent();

			await user.click(
				screen.getByRole("button", { name: /generate with ai/i }),
			);

			expect(
				screen.getByTestId("generation-options-panel"),
			).toBeInTheDocument();
			expect(screen.queryByTestId("no-content-prompt")).not.toBeInTheDocument();
		});

		it("calls onGenerate with 'ai' method when panel Generate is clicked", async () => {
			const user = userEvent.setup();
			const { onGenerate } = renderWithoutContent();

			await user.click(
				screen.getByRole("button", { name: /generate with ai/i }),
			);
			await user.click(screen.getByTestId("mock-generate-btn"));

			expect(onGenerate).toHaveBeenCalledWith("ai", {
				pageLimit: 1,
				emphasis: "balanced",
				includeSections: ["summary", "experience"],
			});
		});

		it("hides options panel after successful generation", async () => {
			const user = userEvent.setup();
			renderWithoutContent();

			await user.click(
				screen.getByRole("button", { name: /generate with ai/i }),
			);
			await user.click(screen.getByTestId("mock-generate-btn"));

			await waitFor(() => {
				expect(
					screen.queryByTestId("generation-options-panel"),
				).not.toBeInTheDocument();
			});
		});

		it("returns to no-content prompt when Cancel is clicked", async () => {
			const user = userEvent.setup();
			renderWithoutContent();

			await user.click(
				screen.getByRole("button", { name: /generate with ai/i }),
			);
			expect(
				screen.getByTestId("generation-options-panel"),
			).toBeInTheDocument();

			await user.click(screen.getByTestId("mock-cancel-btn"));

			expect(
				screen.queryByTestId("generation-options-panel"),
			).not.toBeInTheDocument();
			expect(screen.getByTestId("no-content-prompt")).toBeInTheDocument();
		});
	});

	describe("generation flow — template fill path", () => {
		it("calls onGenerate with template_fill when Start from Template is clicked", async () => {
			const user = userEvent.setup();
			const { onGenerate } = renderWithoutContent();

			await user.click(
				screen.getByRole("button", { name: /start from template/i }),
			);

			expect(onGenerate).toHaveBeenCalledWith("template_fill");
		});
	});

	describe("generation flow — credit fallback", () => {
		it("shows credit fallback toast when AI generation returns null", async () => {
			const user = userEvent.setup();
			const onGenerate = vi.fn().mockResolvedValue(null);
			renderWithoutContent({ onGenerate });

			await user.click(
				screen.getByRole("button", { name: /generate with ai/i }),
			);
			await user.click(screen.getByTestId("mock-generate-btn"));

			await waitFor(() => {
				expect(mocks.mockShowToast.info).toHaveBeenCalledWith(
					expect.stringContaining("Start from Template"),
					expect.any(Object),
				);
			});
		});

		it("keeps options panel open when generation fails", async () => {
			const user = userEvent.setup();
			const onGenerate = vi.fn().mockResolvedValue(null);
			renderWithoutContent({ onGenerate });

			await user.click(
				screen.getByRole("button", { name: /generate with ai/i }),
			);
			await user.click(screen.getByTestId("mock-generate-btn"));

			await waitFor(() => {
				expect(
					screen.getByTestId("generation-options-panel"),
				).toBeInTheDocument();
			});
		});
	});

	describe("generating state", () => {
		it("shows generating overlay when isGenerating and no content", () => {
			renderWithoutContent({ isGenerating: true });
			expect(screen.getByTestId("generating-state")).toBeInTheDocument();
			expect(screen.getByText(/generating your resume/i)).toBeInTheDocument();
		});
	});

	describe("regeneration", () => {
		it("shows Regenerate button in preview mode when content exists", () => {
			renderWithContent();
			expect(
				screen.getByRole("button", { name: /regenerate/i }),
			).toBeInTheDocument();
		});

		it("opens options panel when Regenerate is clicked", async () => {
			const user = userEvent.setup();
			renderWithContent();

			await user.click(screen.getByRole("button", { name: /regenerate/i }));

			expect(
				screen.getByTestId("generation-options-panel"),
			).toBeInTheDocument();
		});

		it("hides editor and shows options panel during regeneration", async () => {
			const user = userEvent.setup();
			renderWithContent();

			await user.click(screen.getByRole("button", { name: /regenerate/i }));

			expect(
				screen.queryByRole("tab", { name: /preview/i }),
			).not.toBeInTheDocument();
			expect(
				screen.getByTestId("generation-options-panel"),
			).toBeInTheDocument();
		});

		it("returns to content view when Cancel is clicked during regeneration", async () => {
			const user = userEvent.setup();
			renderWithContent();

			await user.click(screen.getByRole("button", { name: /regenerate/i }));
			await user.click(screen.getByTestId("mock-cancel-btn"));

			expect(
				screen.queryByTestId("generation-options-panel"),
			).not.toBeInTheDocument();
			expect(screen.getByRole("tab", { name: /preview/i })).toBeInTheDocument();
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
				"noopener,noreferrer",
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
				"noopener,noreferrer",
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

		it("shows Regenerate button in Preview mode", () => {
			renderWithContent();
			expect(
				screen.getByRole("button", { name: /regenerate/i }),
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

	describe("persona reference panel", () => {
		it("renders PersonaReferencePanel with personaId in edit mode", async () => {
			const user = userEvent.setup();
			renderWithContent();
			await switchToEditMode(user);

			const panels = screen.getAllByTestId("persona-reference-panel");
			expect(panels.length).toBeGreaterThanOrEqual(1);
			expect(panels[0]).toHaveAttribute("data-persona-id", PERSONA_ID);
		});

		it("renders persona toggle button for mobile in edit mode", async () => {
			const user = userEvent.setup();
			renderWithContent();
			await switchToEditMode(user);

			expect(
				screen.getByRole("button", { name: /persona/i }),
			).toBeInTheDocument();
		});
	});
});
