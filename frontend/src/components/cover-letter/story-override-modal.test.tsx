/**
 * Tests for the StoryOverrideModal component (§9.4).
 *
 * REQ-012 §10.5: Story override modal with selected/available stories
 * and relevance scores.
 */

import {
	cleanup,
	render,
	screen,
	waitFor,
	within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const COVER_LETTER_ID = "cl-1";

const MODAL_TITLE = "Select Stories";
const SELECTED_HEADING = "Currently selected:";
const AVAILABLE_HEADING = "Available:";
const CANCEL_BUTTON = "Cancel";
const REGENERATE_BUTTON = "Regenerate with selection";

const SELECTED_STORIES_TESTID = "selected-stories";
const AVAILABLE_STORIES_TESTID = "available-stories";
const STORY_TITLE_TESTID = "story-title";
const REGENERATE_SPINNER_TESTID = "regenerate-spinner";

const MOCK_STORIES = [
	{
		id: "story-1",
		title: "Turned around failing project",
		relevance_score: 92,
	},
	{ id: "story-2", title: "Scaled Agile adoption", relevance_score: 87 },
	{ id: "story-3", title: "Built CI/CD pipeline", relevance_score: 71 },
	{ id: "story-4", title: "Mentored junior engineers", relevance_score: 65 },
	{ id: "story-5", title: "Migrated legacy system", relevance_score: 58 },
];

const SELECTED_IDS = ["story-1", "story-2"];

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

import { StoryOverrideModal } from "./story-override-modal";

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
		stories: { id: string; title: string; relevance_score: number }[];
		selectedStoryIds: string[];
	}>,
) {
	const onOpenChange = overrides?.onOpenChange ?? vi.fn();
	const Wrapper = createWrapper();
	const result = render(
		<Wrapper>
			<StoryOverrideModal
				open={overrides?.open ?? true}
				onOpenChange={onOpenChange}
				coverLetterId={overrides?.coverLetterId ?? COVER_LETTER_ID}
				stories={overrides?.stories ?? MOCK_STORIES}
				selectedStoryIds={overrides?.selectedStoryIds ?? SELECTED_IDS}
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

describe("StoryOverrideModal", () => {
	// ----- Rendering -----

	describe("rendering", () => {
		it("renders modal title", () => {
			renderModal();

			expect(screen.getByText(MODAL_TITLE)).toBeInTheDocument();
		});

		it("renders 'Currently selected' heading when selected stories exist", () => {
			renderModal();

			expect(screen.getByText(SELECTED_HEADING)).toBeInTheDocument();
		});

		it("renders 'Available' heading when available stories exist", () => {
			renderModal();

			expect(screen.getByText(AVAILABLE_HEADING)).toBeInTheDocument();
		});

		it("renders selected stories with relevance scores", () => {
			renderModal();

			const selectedSection = screen.getByTestId(SELECTED_STORIES_TESTID);

			expect(
				within(selectedSection).getByText(MOCK_STORIES[0].title),
			).toBeInTheDocument();
			expect(within(selectedSection).getByText("92pt")).toBeInTheDocument();
			expect(
				within(selectedSection).getByText(MOCK_STORIES[1].title),
			).toBeInTheDocument();
			expect(within(selectedSection).getByText("87pt")).toBeInTheDocument();
		});

		it("renders available stories with relevance scores", () => {
			renderModal();

			const availableSection = screen.getByTestId(AVAILABLE_STORIES_TESTID);

			expect(
				within(availableSection).getByText(MOCK_STORIES[2].title),
			).toBeInTheDocument();
			expect(within(availableSection).getByText("71pt")).toBeInTheDocument();
			expect(
				within(availableSection).getByText(MOCK_STORIES[3].title),
			).toBeInTheDocument();
			expect(within(availableSection).getByText("65pt")).toBeInTheDocument();
			expect(
				within(availableSection).getByText(MOCK_STORIES[4].title),
			).toBeInTheDocument();
			expect(within(availableSection).getByText("58pt")).toBeInTheDocument();
		});

		it("hides 'Currently selected' section when no stories selected", () => {
			renderModal({ selectedStoryIds: [] });

			expect(screen.queryByText(SELECTED_HEADING)).not.toBeInTheDocument();
			expect(
				screen.queryByTestId(SELECTED_STORIES_TESTID),
			).not.toBeInTheDocument();
		});

		it("hides 'Available' section when all stories are selected", () => {
			renderModal({
				selectedStoryIds: MOCK_STORIES.map((s) => s.id),
			});

			expect(screen.queryByText(AVAILABLE_HEADING)).not.toBeInTheDocument();
			expect(
				screen.queryByTestId(AVAILABLE_STORIES_TESTID),
			).not.toBeInTheDocument();
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

		it("sorts stories by relevance score descending within each group", () => {
			renderModal();

			const selectedSection = screen.getByTestId(SELECTED_STORIES_TESTID);
			const selectedTitles = within(selectedSection)
				.getAllByTestId(STORY_TITLE_TESTID)
				.map((el) => el.textContent);

			// story-1 (92pt) before story-2 (87pt)
			expect(selectedTitles).toEqual([
				MOCK_STORIES[0].title,
				MOCK_STORIES[1].title,
			]);

			const availableSection = screen.getByTestId(AVAILABLE_STORIES_TESTID);
			const availableTitles = within(availableSection)
				.getAllByTestId(STORY_TITLE_TESTID)
				.map((el) => el.textContent);

			// 71pt, 65pt, 58pt
			expect(availableTitles).toEqual([
				MOCK_STORIES[2].title,
				MOCK_STORIES[3].title,
				MOCK_STORIES[4].title,
			]);
		});

		it("renders selected stories with checked checkboxes", () => {
			renderModal();

			const selectedSection = screen.getByTestId(SELECTED_STORIES_TESTID);
			const checkboxes = within(selectedSection).getAllByRole("checkbox");

			for (const cb of checkboxes) {
				expect(cb).toBeChecked();
			}
		});

		it("renders available stories with unchecked checkboxes", () => {
			renderModal();

			const availableSection = screen.getByTestId(AVAILABLE_STORIES_TESTID);
			const checkboxes = within(availableSection).getAllByRole("checkbox");

			for (const cb of checkboxes) {
				expect(cb).not.toBeChecked();
			}
		});
	});

	// ----- Interaction -----

	describe("interaction", () => {
		it("unchecking a selected story moves it to available", async () => {
			const user = userEvent.setup();
			renderModal();

			const selectedSection = screen.getByTestId(SELECTED_STORIES_TESTID);
			const checkboxes = within(selectedSection).getAllByRole("checkbox");

			// Uncheck story-1
			await user.click(checkboxes[0]);

			// story-1 should now appear in available section
			const availableSection = screen.getByTestId(AVAILABLE_STORIES_TESTID);
			expect(
				within(availableSection).getByText(MOCK_STORIES[0].title),
			).toBeInTheDocument();

			// Only story-2 should remain in selected
			const updatedSelected = screen.getByTestId(SELECTED_STORIES_TESTID);
			const selectedTitles = within(updatedSelected)
				.getAllByTestId(STORY_TITLE_TESTID)
				.map((el) => el.textContent);
			expect(selectedTitles).toEqual([MOCK_STORIES[1].title]);
		});

		it("checking an available story moves it to selected", async () => {
			const user = userEvent.setup();
			renderModal();

			const availableSection = screen.getByTestId(AVAILABLE_STORIES_TESTID);
			const checkboxes = within(availableSection).getAllByRole("checkbox");

			// Check story-3 (Built CI/CD pipeline - 71pt)
			await user.click(checkboxes[0]);

			// story-3 should now appear in selected section
			const selectedSection = screen.getByTestId(SELECTED_STORIES_TESTID);
			expect(
				within(selectedSection).getByText(MOCK_STORIES[2].title),
			).toBeInTheDocument();
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
		it("calls API with selected story IDs", async () => {
			const user = userEvent.setup();
			mocks.mockApiPost.mockResolvedValueOnce({ data: {} });
			renderModal();

			await user.click(screen.getByRole("button", { name: REGENERATE_BUTTON }));

			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith(
					`/cover-letters/${COVER_LETTER_ID}/regenerate`,
					{
						selected_story_ids: expect.arrayContaining(["story-1", "story-2"]),
					},
				);
			});
			// Should have exactly the selected IDs
			const payload = mocks.mockApiPost.mock.calls[0][1];
			expect(payload.selected_story_ids).toHaveLength(2);
		});

		it("sends updated story IDs after toggling selections", async () => {
			const user = userEvent.setup();
			mocks.mockApiPost.mockResolvedValueOnce({ data: {} });
			renderModal();

			// Add story-3 to selection
			const availableSection = screen.getByTestId(AVAILABLE_STORIES_TESTID);
			const availableCheckboxes =
				within(availableSection).getAllByRole("checkbox");
			await user.click(availableCheckboxes[0]); // story-3

			// Submit
			await user.click(screen.getByRole("button", { name: REGENERATE_BUTTON }));

			await waitFor(() => {
				const payload = mocks.mockApiPost.mock.calls[0][1];
				expect(payload.selected_story_ids).toHaveLength(3);
				expect(payload.selected_story_ids).toContain("story-3");
			});
		});

		it("shows loading state during submission", async () => {
			const user = userEvent.setup();
			mocks.mockApiPost.mockReturnValue(new Promise(() => {}));
			renderModal();

			await user.click(screen.getByRole("button", { name: REGENERATE_BUTTON }));

			await waitFor(() => {
				expect(
					screen.getByTestId(REGENERATE_SPINNER_TESTID),
				).toBeInTheDocument();
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

		it("disables regenerate button when no stories are selected", async () => {
			const user = userEvent.setup();
			renderModal({ selectedStoryIds: [] });

			const regenButton = screen.getByRole("button", {
				name: REGENERATE_BUTTON,
			});
			expect(regenButton).toBeDisabled();

			// Should not call API
			await user.click(regenButton);
			expect(mocks.mockApiPost).not.toHaveBeenCalled();
		});
	});
});
