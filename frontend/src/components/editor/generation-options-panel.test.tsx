/**
 * Tests for GenerationOptionsPanel component.
 *
 * REQ-026 §4.2: Generation options panel with page limit, emphasis,
 * section checkboxes, and Generate Resume button.
 * REQ-026 §4.7: Regeneration pre-fills previous settings.
 */

import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { GenerationOptions } from "@/types/resume-generation";

import { GenerationOptionsPanel } from "./generation-options-panel";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderPanel(
	props?: Partial<{
		onGenerate: (options: GenerationOptions) => void;
		onCancel: () => void;
		isGenerating: boolean;
		defaultOptions: GenerationOptions;
	}>,
) {
	const defaultProps = {
		onGenerate: vi.fn(),
		onCancel: vi.fn(),
		isGenerating: false,
		...props,
	};
	return {
		...render(
			<GenerationOptionsPanel
				onGenerate={defaultProps.onGenerate}
				onCancel={defaultProps.onCancel}
				isGenerating={defaultProps.isGenerating}
				defaultOptions={defaultProps.defaultOptions}
			/>,
		),
		onGenerate: defaultProps.onGenerate,
		onCancel: defaultProps.onCancel,
	};
}

// ---------------------------------------------------------------------------
// Teardown
// ---------------------------------------------------------------------------

afterEach(() => {
	cleanup();
	vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("GenerationOptionsPanel", () => {
	describe("rendering", () => {
		it("renders the panel with title", () => {
			renderPanel();
			expect(screen.getByText("Generation Options")).toBeInTheDocument();
		});

		it("renders page limit select with default of 1 page", () => {
			renderPanel();
			const trigger = screen.getByTestId("page-limit-select");
			expect(trigger).toHaveTextContent("1 page");
		});

		it("renders emphasis select with default of Balanced", () => {
			renderPanel();
			const trigger = screen.getByTestId("emphasis-select");
			expect(trigger).toHaveTextContent("Balanced");
		});

		it("renders section checkboxes with correct defaults", () => {
			renderPanel();
			const panel = screen.getByTestId("generation-options-panel");

			// Checked by default
			expect(
				within(panel).getByRole("checkbox", {
					name: /professional summary/i,
				}),
			).toBeChecked();
			expect(
				within(panel).getByRole("checkbox", {
					name: /work experience/i,
				}),
			).toBeChecked();
			expect(
				within(panel).getByRole("checkbox", { name: /^education$/i }),
			).toBeChecked();
			expect(
				within(panel).getByRole("checkbox", { name: /^skills$/i }),
			).toBeChecked();

			// Unchecked by default
			expect(
				within(panel).getByRole("checkbox", {
					name: /certifications/i,
				}),
			).not.toBeChecked();
			expect(
				within(panel).getByRole("checkbox", {
					name: /volunteer experience/i,
				}),
			).not.toBeChecked();
		});

		it("renders Generate Resume button", () => {
			renderPanel();
			expect(
				screen.getByRole("button", { name: /generate resume/i }),
			).toBeInTheDocument();
		});

		it("renders Cancel button", () => {
			renderPanel();
			expect(
				screen.getByRole("button", { name: /cancel/i }),
			).toBeInTheDocument();
		});
	});

	describe("pre-filled defaults (regeneration)", () => {
		it("pre-fills page limit from defaultOptions", () => {
			renderPanel({
				defaultOptions: {
					pageLimit: 2,
					emphasis: "technical",
					includeSections: ["summary", "experience"],
				},
			});
			expect(screen.getByTestId("page-limit-select")).toHaveTextContent(
				"2 pages",
			);
		});

		it("pre-fills emphasis from defaultOptions", () => {
			renderPanel({
				defaultOptions: {
					pageLimit: 1,
					emphasis: "leadership",
					includeSections: ["summary"],
				},
			});
			expect(screen.getByTestId("emphasis-select")).toHaveTextContent(
				"Leadership",
			);
		});

		it("pre-fills section checkboxes from defaultOptions", () => {
			renderPanel({
				defaultOptions: {
					pageLimit: 1,
					emphasis: "balanced",
					includeSections: ["summary", "certifications"],
				},
			});
			const panel = screen.getByTestId("generation-options-panel");

			expect(
				within(panel).getByRole("checkbox", {
					name: /professional summary/i,
				}),
			).toBeChecked();
			expect(
				within(panel).getByRole("checkbox", {
					name: /work experience/i,
				}),
			).not.toBeChecked();
			expect(
				within(panel).getByRole("checkbox", {
					name: /certifications/i,
				}),
			).toBeChecked();
		});
	});

	describe("interactions", () => {
		it("toggles a section checkbox on click", async () => {
			const user = userEvent.setup();
			renderPanel();
			const panel = screen.getByTestId("generation-options-panel");

			const certCheckbox = within(panel).getByRole("checkbox", {
				name: /certifications/i,
			});
			expect(certCheckbox).not.toBeChecked();

			await user.click(certCheckbox);
			expect(certCheckbox).toBeChecked();

			await user.click(certCheckbox);
			expect(certCheckbox).not.toBeChecked();
		});

		it("calls onGenerate with current options when Generate is clicked", async () => {
			const user = userEvent.setup();
			const { onGenerate } = renderPanel();

			await user.click(
				screen.getByRole("button", { name: /generate resume/i }),
			);

			expect(onGenerate).toHaveBeenCalledWith({
				pageLimit: 1,
				emphasis: "balanced",
				includeSections: ["summary", "experience", "education", "skills"],
			});
		});

		it("calls onGenerate with toggled sections", async () => {
			const user = userEvent.setup();
			const { onGenerate } = renderPanel();
			const panel = screen.getByTestId("generation-options-panel");

			// Uncheck skills, check certifications
			await user.click(
				within(panel).getByRole("checkbox", { name: /^skills$/i }),
			);
			await user.click(
				within(panel).getByRole("checkbox", {
					name: /certifications/i,
				}),
			);

			await user.click(
				screen.getByRole("button", { name: /generate resume/i }),
			);

			expect(onGenerate).toHaveBeenCalledWith(
				expect.objectContaining({
					includeSections: expect.arrayContaining([
						"summary",
						"experience",
						"education",
						"certifications",
					]),
				}),
			);
			const callArg = vi.mocked(onGenerate).mock.calls[0][0];
			expect(callArg.includeSections).not.toContain("skills");
		});

		it("calls onCancel when Cancel is clicked", async () => {
			const user = userEvent.setup();
			const { onCancel } = renderPanel();

			await user.click(screen.getByRole("button", { name: /cancel/i }));

			expect(onCancel).toHaveBeenCalledOnce();
		});
	});

	describe("loading state", () => {
		it("disables Generate button when isGenerating is true", () => {
			renderPanel({ isGenerating: true });
			expect(
				screen.getByRole("button", { name: /generating/i }),
			).toBeDisabled();
		});

		it("shows Generating text when isGenerating is true", () => {
			renderPanel({ isGenerating: true });
			expect(
				screen.getByRole("button", { name: /generating/i }),
			).toBeInTheDocument();
		});

		it("disables Cancel button when isGenerating is true", () => {
			renderPanel({ isGenerating: true });
			expect(screen.getByRole("button", { name: /cancel/i })).toBeDisabled();
		});
	});
});
