/**
 * Tests for the RegenerationFeedbackModal component (§9.3).
 *
 * REQ-012 §10.4: Regeneration feedback modal with text input,
 * story exclusion checkboxes, and quick option chips.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const COVER_LETTER_ID = "cl-1";

const MODAL_TITLE = "Regeneration Feedback";
const TEXTAREA_PLACEHOLDER =
	'e.g., "Make it less formal" or "Focus more on technical skills"';
const CHAR_COUNTER_INITIAL = "0/500 characters";
const CANCEL_BUTTON = "Cancel";
const REGENERATE_BUTTON = "Regenerate";
const SHORTER_CHIP = "Shorter";
const MORE_FORMAL_CHIP = "More formal";
const START_FRESH_CHIP = "Start fresh";
const TEXTAREA_NAME = /what would you like changed/i;

const QUICK_OPTIONS = [
	SHORTER_CHIP,
	"Longer",
	MORE_FORMAL_CHIP,
	"Less formal",
	"More technical",
	START_FRESH_CHIP,
];

const MOCK_STORIES = [
	{ id: "story-1", title: "Turned around failing project" },
	{ id: "story-2", title: "Scaled Agile adoption" },
];

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => {
	class MockApiError extends Error {
		code: string;
		status: number;
		constructor(code: string, message: string, status: number) {
			super(message);
			this.name = "ApiError";
			this.code = code;
			this.status = status;
		}
	}
	return {
		mockApiPost: vi.fn(),
		MockApiError,
		mockShowToast: {
			success: vi.fn(),
			error: vi.fn(),
			warning: vi.fn(),
			info: vi.fn(),
			dismiss: vi.fn(),
		},
		mockInvalidateQueries: vi.fn().mockResolvedValue(undefined),
	};
});

vi.mock("@/lib/api-client", () => ({
	apiPost: mocks.mockApiPost,
	ApiError: mocks.MockApiError,
}));

vi.mock("@/lib/toast", () => ({
	showToast: mocks.mockShowToast,
}));

import { RegenerationFeedbackModal } from "./regeneration-feedback-modal";

// ---------------------------------------------------------------------------
// Setup / Teardown
// ---------------------------------------------------------------------------

function createWrapper() {
	const queryClient = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
	queryClient.invalidateQueries = mocks.mockInvalidateQueries;
	return function Wrapper({ children }: { children: ReactNode }) {
		return (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);
	};
}

function renderModal(
	overrides?: Partial<{
		open: boolean;
		onOpenChange: (open: boolean) => void;
		coverLetterId: string;
		usedStories: { id: string; title: string }[];
	}>,
) {
	const onOpenChange = overrides?.onOpenChange ?? vi.fn();
	const Wrapper = createWrapper();
	const result = render(
		<Wrapper>
			<RegenerationFeedbackModal
				open={overrides?.open ?? true}
				onOpenChange={onOpenChange}
				coverLetterId={overrides?.coverLetterId ?? COVER_LETTER_ID}
				usedStories={overrides?.usedStories ?? MOCK_STORIES}
			/>
		</Wrapper>,
	);
	return { ...result, onOpenChange };
}

beforeEach(() => {
	mocks.mockApiPost.mockReset();
	mocks.mockInvalidateQueries.mockReset().mockResolvedValue(undefined);
	Object.values(mocks.mockShowToast).forEach((fn) => fn.mockReset());
});

afterEach(() => {
	cleanup();
	vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("RegenerationFeedbackModal", () => {
	// ----- Rendering -----

	describe("rendering", () => {
		it("renders modal title", () => {
			renderModal();

			expect(screen.getByText(MODAL_TITLE)).toBeInTheDocument();
		});

		it("renders feedback textarea with placeholder", () => {
			renderModal();

			const textarea = screen.getByRole("textbox", {
				name: TEXTAREA_NAME,
			});
			expect(textarea).toBeInTheDocument();
			expect(textarea).toHaveAttribute("placeholder", TEXTAREA_PLACEHOLDER);
		});

		it("renders character counter showing 0/500", () => {
			renderModal();

			expect(screen.getByText(CHAR_COUNTER_INITIAL)).toBeInTheDocument();
		});

		it("renders story exclusion checkboxes for each used story", () => {
			renderModal();

			for (const story of MOCK_STORIES) {
				expect(screen.getByText(story.title)).toBeInTheDocument();
			}

			const checkboxes = screen.getAllByRole("checkbox");
			expect(checkboxes).toHaveLength(MOCK_STORIES.length);
		});

		it("renders all checkboxes unchecked by default", () => {
			renderModal();

			const checkboxes = screen.getAllByRole("checkbox");
			for (const cb of checkboxes) {
				expect(cb).not.toBeChecked();
			}
		});

		it("renders all 6 quick option chips", () => {
			renderModal();

			for (const option of QUICK_OPTIONS) {
				expect(
					screen.getByRole("button", { name: option }),
				).toBeInTheDocument();
			}
		});

		it("renders cancel and regenerate buttons", () => {
			renderModal();

			expect(
				screen.getByRole("button", { name: CANCEL_BUTTON }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("button", { name: REGENERATE_BUTTON }),
			).toBeInTheDocument();
		});

		it("hides story exclusion section when no stories provided", () => {
			renderModal({ usedStories: [] });

			expect(screen.queryByText(/exclude stories/i)).not.toBeInTheDocument();
			expect(screen.queryAllByRole("checkbox")).toHaveLength(0);
		});
	});

	// ----- Quick option chips -----

	describe("quick option chips", () => {
		it("clicking a chip populates the textarea", async () => {
			const user = userEvent.setup();
			renderModal();

			await user.click(screen.getByRole("button", { name: SHORTER_CHIP }));

			const textarea = screen.getByRole("textbox", {
				name: TEXTAREA_NAME,
			});
			expect(textarea).toHaveValue(SHORTER_CHIP);
		});

		it("clicking multiple chips appends with separator", async () => {
			const user = userEvent.setup();
			renderModal();

			await user.click(screen.getByRole("button", { name: SHORTER_CHIP }));
			await user.click(screen.getByRole("button", { name: MORE_FORMAL_CHIP }));

			const textarea = screen.getByRole("textbox", {
				name: TEXTAREA_NAME,
			});
			expect(textarea).toHaveValue(`${SHORTER_CHIP}. ${MORE_FORMAL_CHIP}`);
		});

		it("Start fresh clears the textarea", async () => {
			const user = userEvent.setup();
			renderModal();

			const textarea = screen.getByRole("textbox", {
				name: TEXTAREA_NAME,
			});
			await user.type(textarea, "Some feedback");
			expect(textarea).toHaveValue("Some feedback");

			await user.click(screen.getByRole("button", { name: START_FRESH_CHIP }));

			expect(textarea).toHaveValue("");
		});

		it("Start fresh unchecks all excluded stories", async () => {
			const user = userEvent.setup();
			renderModal();

			// Check a story
			const checkboxes = screen.getAllByRole("checkbox");
			await user.click(checkboxes[0]);
			expect(checkboxes[0]).toBeChecked();

			// Click Start fresh
			await user.click(screen.getByRole("button", { name: START_FRESH_CHIP }));

			// All checkboxes unchecked
			for (const cb of screen.getAllByRole("checkbox")) {
				expect(cb).not.toBeChecked();
			}
		});
	});

	// ----- Textarea interaction -----

	describe("textarea interaction", () => {
		it("updates character counter on typing", async () => {
			const user = userEvent.setup();
			renderModal();

			const textarea = screen.getByRole("textbox", {
				name: TEXTAREA_NAME,
			});
			await user.type(textarea, "Hello");

			expect(screen.getByText("5/500 characters")).toBeInTheDocument();
		});

		it("enforces 500 character maxLength", () => {
			renderModal();

			const textarea = screen.getByRole("textbox", {
				name: TEXTAREA_NAME,
			});
			expect(textarea).toHaveAttribute("maxLength", "500");
		});
	});

	// ----- Story exclusion -----

	describe("story exclusion", () => {
		it("checking a story marks it as excluded", async () => {
			const user = userEvent.setup();
			renderModal();

			const checkboxes = screen.getAllByRole("checkbox");
			await user.click(checkboxes[0]);

			expect(checkboxes[0]).toBeChecked();
			expect(checkboxes[1]).not.toBeChecked();
		});
	});

	// ----- Cancel -----

	describe("cancel", () => {
		it("calls onOpenChange(false) when cancel is clicked", async () => {
			const user = userEvent.setup();
			const { onOpenChange } = renderModal();

			await user.click(screen.getByRole("button", { name: CANCEL_BUTTON }));

			expect(onOpenChange).toHaveBeenCalledWith(false);
		});
	});

	// ----- Submit -----

	describe("submit", () => {
		it("calls API with correct payload", async () => {
			const user = userEvent.setup();
			mocks.mockApiPost.mockResolvedValueOnce({ data: {} });
			renderModal();

			// Type feedback
			const textarea = screen.getByRole("textbox", {
				name: TEXTAREA_NAME,
			});
			await user.type(textarea, "Focus on leadership");

			// Exclude one story
			const checkboxes = screen.getAllByRole("checkbox");
			await user.click(checkboxes[1]);

			// Submit
			await user.click(screen.getByRole("button", { name: REGENERATE_BUTTON }));

			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith(
					`/cover-letters/${COVER_LETTER_ID}/regenerate`,
					{
						feedback_text: "Focus on leadership",
						excluded_story_ids: ["story-2"],
						start_fresh: false,
					},
				);
			});
		});

		it("sends start_fresh flag when Start fresh was clicked", async () => {
			const user = userEvent.setup();
			mocks.mockApiPost.mockResolvedValueOnce({ data: {} });
			renderModal();

			await user.click(screen.getByRole("button", { name: START_FRESH_CHIP }));
			await user.click(screen.getByRole("button", { name: REGENERATE_BUTTON }));

			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith(
					`/cover-letters/${COVER_LETTER_ID}/regenerate`,
					expect.objectContaining({ start_fresh: true }),
				);
			});
		});

		it("shows loading state during regeneration", async () => {
			const user = userEvent.setup();
			mocks.mockApiPost.mockReturnValue(new Promise(() => {}));
			renderModal();

			await user.click(screen.getByRole("button", { name: REGENERATE_BUTTON }));

			await waitFor(() => {
				expect(screen.getByTestId("regenerate-spinner")).toBeInTheDocument();
			});

			const regenButton = screen.getByRole("button", {
				name: /regenerat/i,
			});
			expect(regenButton).toBeDisabled();
		});

		it("shows success toast and closes modal on success", async () => {
			const user = userEvent.setup();
			mocks.mockApiPost.mockResolvedValueOnce({ data: {} });
			const { onOpenChange } = renderModal();

			await user.click(screen.getByRole("button", { name: REGENERATE_BUTTON }));

			await waitFor(() => {
				expect(mocks.mockShowToast.success).toHaveBeenCalledWith(
					"Regeneration started.",
				);
			});
			expect(onOpenChange).toHaveBeenCalledWith(false);
			expect(mocks.mockInvalidateQueries).toHaveBeenCalled();
		});

		it("shows error toast on API failure", async () => {
			const user = userEvent.setup();
			mocks.mockApiPost.mockRejectedValueOnce(
				new mocks.MockApiError("SERVER_ERROR", "Something went wrong", 500),
			);
			const { onOpenChange } = renderModal();

			await user.click(screen.getByRole("button", { name: REGENERATE_BUTTON }));

			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalled();
			});
			// Modal stays open on error
			expect(onOpenChange).not.toHaveBeenCalledWith(false);
		});
	});
});
