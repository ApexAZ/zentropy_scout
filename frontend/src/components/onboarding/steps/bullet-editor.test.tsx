/**
 * Tests for the bullet editor component.
 *
 * REQ-012 §6.3.3: Per-job bullet editing — each job card expands to show
 * accomplishment bullets. Min 1 bullet per job. Add/edit/delete/reorder.
 */

import {
	cleanup,
	fireEvent,
	render,
	screen,
	waitFor,
	within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Bullet } from "@/types/persona";

import { BulletEditor } from "./bullet-editor";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PERSONA_ID = "00000000-0000-4000-a000-000000000001";
const WORK_HISTORY_ID = "wh-001";

const MOCK_BULLET_1: Bullet = {
	id: "b-001",
	work_history_id: WORK_HISTORY_ID,
	text: "Built microservices architecture serving 1M daily requests",
	skills_demonstrated: [],
	metrics: null,
	display_order: 0,
};

const MOCK_BULLET_2: Bullet = {
	id: "b-002",
	work_history_id: WORK_HISTORY_ID,
	text: "Reduced deploy time from 45 minutes to 5 minutes",
	skills_demonstrated: [],
	metrics: "40% reduction",
	display_order: 1,
};

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
		mockApiPatch: vi.fn(),
		mockApiDelete: vi.fn(),
		MockApiError,
	};
});

vi.mock("@/lib/api-client", () => ({
	apiPost: mocks.mockApiPost,
	apiPatch: mocks.mockApiPatch,
	apiDelete: mocks.mockApiDelete,
	ApiError: mocks.MockApiError,
}));

// Mock ReorderableList to avoid DnD complexity in jsdom
let capturedOnReorder: ((items: Bullet[]) => void) | null = null;

vi.mock("@/components/ui/reorderable-list", () => ({
	ReorderableList: ({
		items,
		renderItem,
		onReorder,
		label,
	}: {
		items: Bullet[];
		renderItem: (
			item: Bullet,
			dragHandle: React.ReactNode | null,
		) => React.ReactNode;
		onReorder: (items: Bullet[]) => void;
		label: string;
	}) => {
		capturedOnReorder = onReorder;
		return (
			<div aria-label={label} data-testid="bullet-reorderable-list">
				{items.map((item) => (
					<div key={item.id} data-testid={`bullet-${item.id}`}>
						{renderItem(item, null)}
					</div>
				))}
			</div>
		);
	},
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderEditor(overrides?: {
	initialBullets?: Bullet[];
	onBulletsChange?: (bullets: Bullet[]) => void;
}) {
	const user = userEvent.setup();
	const onBulletsChange = overrides?.onBulletsChange ?? vi.fn();
	render(
		<BulletEditor
			personaId={PERSONA_ID}
			workHistoryId={WORK_HISTORY_ID}
			initialBullets={overrides?.initialBullets ?? []}
			onBulletsChange={onBulletsChange}
		/>,
	);
	return { user, onBulletsChange };
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
	vi.clearAllMocks();
	capturedOnReorder = null;
});

afterEach(() => {
	cleanup();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("BulletEditor", () => {
	// -----------------------------------------------------------------------
	// Rendering
	// -----------------------------------------------------------------------

	describe("rendering", () => {
		it("shows empty state when no bullets exist", () => {
			renderEditor();
			expect(screen.getByText(/no bullets yet/i)).toBeInTheDocument();
			expect(
				screen.getByRole("button", { name: /add bullet/i }),
			).toBeInTheDocument();
		});

		it("shows bullet items when bullets exist", () => {
			renderEditor({ initialBullets: [MOCK_BULLET_1, MOCK_BULLET_2] });
			expect(screen.getByText(MOCK_BULLET_1.text)).toBeInTheDocument();
			expect(screen.getByText(MOCK_BULLET_2.text)).toBeInTheDocument();
		});

		it("shows metrics badge when metrics is present", () => {
			renderEditor({ initialBullets: [MOCK_BULLET_2] });
			expect(screen.getByText("40% reduction")).toBeInTheDocument();
		});

		it("does not show metrics when null", () => {
			renderEditor({ initialBullets: [MOCK_BULLET_1] });
			expect(screen.queryByText("40% reduction")).not.toBeInTheDocument();
		});

		it("shows add bullet button in list view", () => {
			renderEditor({ initialBullets: [MOCK_BULLET_1] });
			expect(
				screen.getByRole("button", { name: /add bullet/i }),
			).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Add flow
	// -----------------------------------------------------------------------

	describe("add flow", () => {
		it("shows form when add button clicked", async () => {
			const { user } = renderEditor();
			await user.click(screen.getByRole("button", { name: /add bullet/i }));
			expect(screen.getByLabelText(/bullet text/i)).toBeInTheDocument();
			expect(screen.getByLabelText(/metrics/i)).toBeInTheDocument();
		});

		it("saves new bullet and adds to list", async () => {
			const onBulletsChange = vi.fn();
			const newBullet: Bullet = {
				id: "b-new",
				work_history_id: WORK_HISTORY_ID,
				text: "Led team of 5 engineers",
				skills_demonstrated: [],
				metrics: null,
				display_order: 0,
			};
			mocks.mockApiPost.mockResolvedValueOnce({ data: newBullet });

			const { user } = renderEditor({ onBulletsChange });
			await user.click(screen.getByRole("button", { name: /add bullet/i }));
			await user.type(
				screen.getByLabelText(/bullet text/i),
				"Led team of 5 engineers",
			);
			await user.click(screen.getByRole("button", { name: /^save$/i }));

			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith(
					`/personas/${PERSONA_ID}/work-history/${WORK_HISTORY_ID}/bullets`,
					expect.objectContaining({
						text: "Led team of 5 engineers",
						display_order: 0,
					}),
				);
			});

			await waitFor(() => {
				expect(onBulletsChange).toHaveBeenCalledWith([newBullet]);
			});

			// Form should close after save
			expect(screen.queryByLabelText(/bullet text/i)).not.toBeInTheDocument();
		});

		it("includes metrics when provided", async () => {
			const newBullet: Bullet = {
				id: "b-new",
				work_history_id: WORK_HISTORY_ID,
				text: "Improved system performance",
				skills_demonstrated: [],
				metrics: "50% faster",
				display_order: 0,
			};
			mocks.mockApiPost.mockResolvedValueOnce({ data: newBullet });

			const { user } = renderEditor();
			await user.click(screen.getByRole("button", { name: /add bullet/i }));
			await user.type(
				screen.getByLabelText(/bullet text/i),
				"Improved system performance",
			);
			await user.type(screen.getByLabelText(/metrics/i), "50% faster");
			await user.click(screen.getByRole("button", { name: /^save$/i }));

			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith(
					expect.any(String),
					expect.objectContaining({
						text: "Improved system performance",
						metrics: "50% faster",
					}),
				);
			});
		});

		it("shows error on save failure", async () => {
			mocks.mockApiPost.mockRejectedValueOnce(new Error("fail"));

			const { user } = renderEditor();
			await user.click(screen.getByRole("button", { name: /add bullet/i }));
			await user.type(screen.getByLabelText(/bullet text/i), "Some text");
			await user.click(screen.getByRole("button", { name: /^save$/i }));

			await waitFor(() => {
				expect(screen.getByTestId("bullet-submit-error")).toBeInTheDocument();
			});
		});

		it("cancels add and returns to list", async () => {
			const { user } = renderEditor();
			await user.click(screen.getByRole("button", { name: /add bullet/i }));
			expect(screen.getByLabelText(/bullet text/i)).toBeInTheDocument();

			await user.click(screen.getByRole("button", { name: /cancel/i }));
			expect(screen.queryByLabelText(/bullet text/i)).not.toBeInTheDocument();
		});

		it("assigns correct display_order to new bullet", async () => {
			const newBullet: Bullet = {
				id: "b-new",
				work_history_id: WORK_HISTORY_ID,
				text: "Third bullet",
				skills_demonstrated: [],
				metrics: null,
				display_order: 2,
			};
			mocks.mockApiPost.mockResolvedValueOnce({ data: newBullet });

			const { user } = renderEditor({
				initialBullets: [MOCK_BULLET_1, MOCK_BULLET_2],
			});
			await user.click(screen.getByRole("button", { name: /add bullet/i }));
			await user.type(screen.getByLabelText(/bullet text/i), "Third bullet");
			await user.click(screen.getByRole("button", { name: /^save$/i }));

			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith(
					expect.any(String),
					expect.objectContaining({ display_order: 2 }),
				);
			});
		});
	});

	// -----------------------------------------------------------------------
	// Edit flow
	// -----------------------------------------------------------------------

	describe("edit flow", () => {
		it("shows form with pre-filled values when edit clicked", async () => {
			const { user } = renderEditor({
				initialBullets: [MOCK_BULLET_2],
			});

			const bulletEl = screen.getByTestId(`bullet-${MOCK_BULLET_2.id}`);
			await user.click(within(bulletEl).getByRole("button", { name: /edit/i }));

			expect(screen.getByLabelText(/bullet text/i)).toHaveValue(
				MOCK_BULLET_2.text,
			);
			expect(screen.getByLabelText(/metrics/i)).toHaveValue("40% reduction");
		});

		it("saves edited bullet and updates list", async () => {
			const onBulletsChange = vi.fn();
			const updatedBullet: Bullet = {
				...MOCK_BULLET_1,
				text: "Updated accomplishment text",
			};
			mocks.mockApiPatch.mockResolvedValueOnce({ data: updatedBullet });

			const { user } = renderEditor({
				initialBullets: [MOCK_BULLET_1],
				onBulletsChange,
			});

			const bulletEl = screen.getByTestId(`bullet-${MOCK_BULLET_1.id}`);
			await user.click(within(bulletEl).getByRole("button", { name: /edit/i }));

			const textInput = screen.getByLabelText(/bullet text/i);
			await user.clear(textInput);
			await user.type(textInput, "Updated accomplishment text");
			await user.click(screen.getByRole("button", { name: /^save$/i }));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/personas/${PERSONA_ID}/work-history/${WORK_HISTORY_ID}/bullets/${MOCK_BULLET_1.id}`,
					expect.objectContaining({
						text: "Updated accomplishment text",
					}),
				);
			});

			await waitFor(() => {
				expect(onBulletsChange).toHaveBeenCalledWith([updatedBullet]);
			});
		});

		it("cancels edit and returns to list with original values", async () => {
			const { user } = renderEditor({
				initialBullets: [MOCK_BULLET_1],
			});

			const bulletEl = screen.getByTestId(`bullet-${MOCK_BULLET_1.id}`);
			await user.click(within(bulletEl).getByRole("button", { name: /edit/i }));
			expect(screen.getByLabelText(/bullet text/i)).toBeInTheDocument();

			await user.click(screen.getByRole("button", { name: /cancel/i }));

			expect(screen.queryByLabelText(/bullet text/i)).not.toBeInTheDocument();
			expect(screen.getByText(MOCK_BULLET_1.text)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Delete flow
	// -----------------------------------------------------------------------

	describe("delete flow", () => {
		it("deletes bullet and removes from list", async () => {
			const onBulletsChange = vi.fn();
			mocks.mockApiDelete.mockResolvedValueOnce({});

			const { user } = renderEditor({
				initialBullets: [MOCK_BULLET_1, MOCK_BULLET_2],
				onBulletsChange,
			});

			const bulletEl = screen.getByTestId(`bullet-${MOCK_BULLET_1.id}`);
			await user.click(
				within(bulletEl).getByRole("button", { name: /delete/i }),
			);

			await waitFor(() => {
				expect(mocks.mockApiDelete).toHaveBeenCalledWith(
					`/personas/${PERSONA_ID}/work-history/${WORK_HISTORY_ID}/bullets/${MOCK_BULLET_1.id}`,
				);
			});

			await waitFor(() => {
				expect(onBulletsChange).toHaveBeenCalledWith([MOCK_BULLET_2]);
			});
		});

		it("keeps bullet and shows error on delete failure", async () => {
			const onBulletsChange = vi.fn();
			mocks.mockApiDelete.mockRejectedValueOnce(new Error("fail"));

			const { user } = renderEditor({
				initialBullets: [MOCK_BULLET_1],
				onBulletsChange,
			});

			const bulletEl = screen.getByTestId(`bullet-${MOCK_BULLET_1.id}`);
			await user.click(
				within(bulletEl).getByRole("button", { name: /delete/i }),
			);

			await waitFor(() => {
				expect(mocks.mockApiDelete).toHaveBeenCalled();
			});

			// Bullet should still be visible after failure
			expect(screen.getByText(MOCK_BULLET_1.text)).toBeInTheDocument();
			// onBulletsChange should NOT have been called
			expect(onBulletsChange).not.toHaveBeenCalled();
			// Error message should be shown
			expect(screen.getByTestId("bullet-submit-error")).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Reordering
	// -----------------------------------------------------------------------

	describe("reordering", () => {
		it("reorders bullets and patches display_order", async () => {
			const onBulletsChange = vi.fn();
			mocks.mockApiPatch.mockResolvedValue({});

			renderEditor({
				initialBullets: [MOCK_BULLET_1, MOCK_BULLET_2],
				onBulletsChange,
			});

			expect(capturedOnReorder).not.toBeNull();

			// Simulate swapping bullet order
			const reordered = [
				{ ...MOCK_BULLET_2, display_order: 1 },
				{ ...MOCK_BULLET_1, display_order: 0 },
			];
			capturedOnReorder!(reordered);

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalled();
			});

			expect(onBulletsChange).toHaveBeenCalledWith(reordered);
		});

		it("rolls back on reorder failure", async () => {
			const onBulletsChange = vi.fn();
			mocks.mockApiPatch.mockRejectedValueOnce(new Error("fail"));

			renderEditor({
				initialBullets: [MOCK_BULLET_1, MOCK_BULLET_2],
				onBulletsChange,
			});

			const reordered = [
				{ ...MOCK_BULLET_2, display_order: 1 },
				{ ...MOCK_BULLET_1, display_order: 0 },
			];
			capturedOnReorder!(reordered);

			// Optimistic update fires first
			expect(onBulletsChange).toHaveBeenCalledWith(reordered);

			// After failure, rollback fires
			await waitFor(() => {
				expect(onBulletsChange).toHaveBeenCalledWith([
					MOCK_BULLET_1,
					MOCK_BULLET_2,
				]);
			});
		});
	});

	// -----------------------------------------------------------------------
	// Validation
	// -----------------------------------------------------------------------

	describe("validation", () => {
		it("requires bullet text", async () => {
			const { user } = renderEditor();
			await user.click(screen.getByRole("button", { name: /add bullet/i }));

			// Submit without filling text
			await user.click(screen.getByRole("button", { name: /^save$/i }));

			await waitFor(() => {
				expect(
					screen.getAllByText(/text is required/i).length,
				).toBeGreaterThanOrEqual(1);
			});

			// API should not have been called
			expect(mocks.mockApiPost).not.toHaveBeenCalled();
		});

		it("enforces max length on text field", async () => {
			const { user } = renderEditor();
			await user.click(screen.getByRole("button", { name: /add bullet/i }));

			// Use fireEvent.change for long text to avoid userEvent.type timeout
			const longText = "a".repeat(2001);
			fireEvent.change(screen.getByLabelText(/bullet text/i), {
				target: { value: longText },
			});
			await user.click(screen.getByRole("button", { name: /^save$/i }));

			await waitFor(() => {
				expect(screen.getAllByText(/too long/i).length).toBeGreaterThanOrEqual(
					1,
				);
			});

			expect(mocks.mockApiPost).not.toHaveBeenCalled();
		});
	});
});
