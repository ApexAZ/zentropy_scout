/**
 * Tests for the useCrudStep hook.
 *
 * REQ-012 §6.3.3–§6.3.7: Shared CRUD state management for onboarding steps.
 */

import { renderHook, act, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { UseCrudStepConfig } from "./use-crud-step";
import { useCrudStep } from "./use-crud-step";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PERSONA_ID = "00000000-0000-4000-a000-000000000001";
const COLLECTION = "certifications";

interface TestEntity {
	id: string;
	display_order: number;
	name: string;
}

interface TestFormData {
	name: string;
}

const ENTITY_A: TestEntity = { id: "e-1", display_order: 0, name: "Alpha" };
const ENTITY_B: TestEntity = { id: "e-2", display_order: 1, name: "Beta" };

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
	mockApiGet: vi.fn(),
	mockApiPost: vi.fn(),
	mockApiPatch: vi.fn(),
	mockApiDelete: vi.fn(),
}));

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
	apiPost: mocks.mockApiPost,
	apiPatch: mocks.mockApiPatch,
	apiDelete: mocks.mockApiDelete,
}));

vi.mock("@/lib/form-errors", () => ({
	toFriendlyError: (err: Error) => err.message,
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const defaultConfig = {
	personaId: PERSONA_ID,
	collection: COLLECTION,
	toFormValues: (entity: TestEntity): TestFormData => ({ name: entity.name }),
	toRequestBody: (data: TestFormData) => ({ name: data.name }),
};

function renderCrudHook(
	overrides?: Partial<UseCrudStepConfig<TestEntity, TestFormData>>,
) {
	return renderHook(() =>
		useCrudStep<TestEntity, TestFormData>({
			...defaultConfig,
			...overrides,
		}),
	);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useCrudStep", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		mocks.mockApiGet.mockResolvedValue({ data: [ENTITY_A, ENTITY_B] });
	});

	// -----------------------------------------------------------------------
	// Fetch on mount
	// -----------------------------------------------------------------------

	describe("fetch on mount", () => {
		it("fetches entries from the collection endpoint", async () => {
			const { result } = renderCrudHook();

			await waitFor(() => {
				expect(result.current.isLoading).toBe(false);
			});

			expect(mocks.mockApiGet).toHaveBeenCalledWith(
				`/personas/${PERSONA_ID}/certifications`,
			);
			expect(result.current.entries).toEqual([ENTITY_A, ENTITY_B]);
		});

		it("sets isLoading to false when personaId is null", async () => {
			const { result } = renderCrudHook({ personaId: null });

			await waitFor(() => {
				expect(result.current.isLoading).toBe(false);
			});

			expect(mocks.mockApiGet).not.toHaveBeenCalled();
		});

		it("sets isLoading to false when fetch fails", async () => {
			mocks.mockApiGet.mockRejectedValue(new Error("Network error"));

			const { result } = renderCrudHook();

			await waitFor(() => {
				expect(result.current.isLoading).toBe(false);
			});

			expect(result.current.entries).toEqual([]);
		});

		it("fetches secondary collection when secondaryFetch is provided", async () => {
			const onData = vi.fn();
			mocks.mockApiGet.mockImplementation((url: string) => {
				if (url.includes("skills")) {
					return Promise.resolve({ data: [{ id: "s-1" }] });
				}
				return Promise.resolve({ data: [ENTITY_A] });
			});

			const { result } = renderCrudHook({
				collection: "achievement-stories",
				secondaryFetch: { collection: "skills", onData },
			});

			await waitFor(() => {
				expect(result.current.isLoading).toBe(false);
			});

			expect(mocks.mockApiGet).toHaveBeenCalledTimes(2);
			expect(onData).toHaveBeenCalledWith([{ id: "s-1" }]);
		});
	});

	// -----------------------------------------------------------------------
	// Add flow
	// -----------------------------------------------------------------------

	describe("add flow", () => {
		it("switches to add mode", async () => {
			const { result } = renderCrudHook();

			await waitFor(() => {
				expect(result.current.isLoading).toBe(false);
			});

			act(() => {
				result.current.handleAdd();
			});

			expect(result.current.viewMode).toBe("add");
			expect(result.current.editingEntry).toBeNull();
			expect(result.current.submitError).toBeNull();
		});

		it("saves a new entry and returns to list", async () => {
			const newEntity: TestEntity = {
				id: "e-3",
				display_order: 2,
				name: "Gamma",
			};
			mocks.mockApiPost.mockResolvedValue({ data: newEntity });

			const { result } = renderCrudHook();

			await waitFor(() => {
				expect(result.current.isLoading).toBe(false);
			});

			act(() => {
				result.current.handleAdd();
			});

			await act(async () => {
				await result.current.handleSaveNew({ name: "Gamma" });
			});

			expect(mocks.mockApiPost).toHaveBeenCalledWith(
				`/personas/${PERSONA_ID}/certifications`,
				{ name: "Gamma", display_order: 2 },
			);
			expect(result.current.entries).toHaveLength(3);
			expect(result.current.viewMode).toBe("list");
		});

		it("sets submitError on save failure", async () => {
			mocks.mockApiPost.mockRejectedValue(new Error("Validation failed"));

			const { result } = renderCrudHook();

			await waitFor(() => {
				expect(result.current.isLoading).toBe(false);
			});

			act(() => {
				result.current.handleAdd();
			});

			await act(async () => {
				await result.current.handleSaveNew({ name: "Bad" });
			});

			expect(result.current.submitError).toBe("Validation failed");
			expect(result.current.viewMode).toBe("add");
		});
	});

	// -----------------------------------------------------------------------
	// Edit flow
	// -----------------------------------------------------------------------

	describe("edit flow", () => {
		it("switches to edit mode with the entry", async () => {
			const { result } = renderCrudHook();

			await waitFor(() => {
				expect(result.current.isLoading).toBe(false);
			});

			act(() => {
				result.current.handleEdit(ENTITY_A);
			});

			expect(result.current.viewMode).toBe("edit");
			expect(result.current.editingEntry).toBe(ENTITY_A);
		});

		it("saves an edited entry and returns to list", async () => {
			const updated = { ...ENTITY_A, name: "Updated" };
			mocks.mockApiPatch.mockResolvedValue({ data: updated });

			const { result } = renderCrudHook();

			await waitFor(() => {
				expect(result.current.isLoading).toBe(false);
			});

			act(() => {
				result.current.handleEdit(ENTITY_A);
			});

			await act(async () => {
				await result.current.handleSaveEdit({ name: "Updated" });
			});

			expect(mocks.mockApiPatch).toHaveBeenCalledWith(
				`/personas/${PERSONA_ID}/certifications/e-1`,
				{ name: "Updated" },
			);
			expect(result.current.entries[0].name).toBe("Updated");
			expect(result.current.viewMode).toBe("list");
		});
	});

	// -----------------------------------------------------------------------
	// Delete flow
	// -----------------------------------------------------------------------

	describe("delete flow", () => {
		it("sets deleteTarget on delete request", async () => {
			const { result } = renderCrudHook();

			await waitFor(() => {
				expect(result.current.isLoading).toBe(false);
			});

			act(() => {
				result.current.handleDeleteRequest(ENTITY_A);
			});

			expect(result.current.deleteTarget).toBe(ENTITY_A);
		});

		it("deletes entry and clears target on confirm", async () => {
			mocks.mockApiDelete.mockResolvedValue(undefined);

			const { result } = renderCrudHook();

			await waitFor(() => {
				expect(result.current.isLoading).toBe(false);
			});

			act(() => {
				result.current.handleDeleteRequest(ENTITY_A);
			});

			await act(async () => {
				await result.current.handleDeleteConfirm();
			});

			expect(mocks.mockApiDelete).toHaveBeenCalledWith(
				`/personas/${PERSONA_ID}/certifications/e-1`,
			);
			expect(result.current.entries).toHaveLength(1);
			expect(result.current.deleteTarget).toBeNull();
		});

		it("clears deleteTarget on cancel", async () => {
			const { result } = renderCrudHook();

			await waitFor(() => {
				expect(result.current.isLoading).toBe(false);
			});

			act(() => {
				result.current.handleDeleteRequest(ENTITY_A);
			});

			act(() => {
				result.current.handleDeleteCancel();
			});

			expect(result.current.deleteTarget).toBeNull();
		});

		it("sets deleteError when hasDeleteError is true", async () => {
			mocks.mockApiDelete.mockRejectedValue(new Error("In use"));

			const { result } = renderCrudHook({
				...defaultConfig,
				hasDeleteError: true,
			} as typeof defaultConfig);

			await waitFor(() => {
				expect(result.current.isLoading).toBe(false);
			});

			act(() => {
				result.current.handleDeleteRequest(ENTITY_A);
			});

			await act(async () => {
				await result.current.handleDeleteConfirm();
			});

			expect(result.current.deleteError).toBe("In use");
		});

		it("does not set deleteError when hasDeleteError is false", async () => {
			mocks.mockApiDelete.mockRejectedValue(new Error("In use"));

			const { result } = renderCrudHook();

			await waitFor(() => {
				expect(result.current.isLoading).toBe(false);
			});

			act(() => {
				result.current.handleDeleteRequest(ENTITY_A);
			});

			await act(async () => {
				await result.current.handleDeleteConfirm();
			});

			expect(result.current.deleteError).toBeNull();
		});

		it("clears deleteError on next delete request when hasDeleteError is true", async () => {
			mocks.mockApiDelete.mockRejectedValue(new Error("In use"));

			const { result } = renderCrudHook({
				...defaultConfig,
				hasDeleteError: true,
			} as typeof defaultConfig);

			await waitFor(() => {
				expect(result.current.isLoading).toBe(false);
			});

			act(() => {
				result.current.handleDeleteRequest(ENTITY_A);
			});

			await act(async () => {
				await result.current.handleDeleteConfirm();
			});

			expect(result.current.deleteError).toBe("In use");

			act(() => {
				result.current.handleDeleteRequest(ENTITY_B);
			});

			expect(result.current.deleteError).toBeNull();
		});
	});

	// -----------------------------------------------------------------------
	// Cancel
	// -----------------------------------------------------------------------

	describe("cancel", () => {
		it("returns to list view and clears editing state", async () => {
			const { result } = renderCrudHook();

			await waitFor(() => {
				expect(result.current.isLoading).toBe(false);
			});

			act(() => {
				result.current.handleEdit(ENTITY_A);
			});

			act(() => {
				result.current.handleCancel();
			});

			expect(result.current.viewMode).toBe("list");
			expect(result.current.editingEntry).toBeNull();
			expect(result.current.submitError).toBeNull();
		});
	});

	// -----------------------------------------------------------------------
	// Reorder
	// -----------------------------------------------------------------------

	describe("reorder", () => {
		it("optimistically reorders entries", async () => {
			mocks.mockApiPatch.mockResolvedValue({});

			const { result } = renderCrudHook();

			await waitFor(() => {
				expect(result.current.isLoading).toBe(false);
			});

			const reordered = [ENTITY_B, ENTITY_A];

			act(() => {
				result.current.handleReorder(reordered);
			});

			expect(result.current.entries[0].id).toBe("e-2");
			expect(result.current.entries[1].id).toBe("e-1");
		});

		it("patches only changed display_order values", async () => {
			mocks.mockApiPatch.mockResolvedValue({});

			const { result } = renderCrudHook();

			await waitFor(() => {
				expect(result.current.isLoading).toBe(false);
			});

			const reordered = [ENTITY_B, ENTITY_A];

			act(() => {
				result.current.handleReorder(reordered);
			});

			// Both entries changed position
			expect(mocks.mockApiPatch).toHaveBeenCalledWith(
				`/personas/${PERSONA_ID}/certifications/e-2`,
				{ display_order: 0 },
			);
			expect(mocks.mockApiPatch).toHaveBeenCalledWith(
				`/personas/${PERSONA_ID}/certifications/e-1`,
				{ display_order: 1 },
			);
		});

		it("rolls back on reorder failure", async () => {
			mocks.mockApiPatch.mockRejectedValue(new Error("Server error"));

			const { result } = renderCrudHook();

			await waitFor(() => {
				expect(result.current.isLoading).toBe(false);
			});

			act(() => {
				result.current.handleReorder([ENTITY_B, ENTITY_A]);
			});

			// Immediately after reorder, state reflects the new order
			expect(result.current.entries[0].id).toBe("e-2");

			// After Promise.all rejects, entries should roll back
			await waitFor(() => {
				expect(result.current.entries[0].id).toBe("e-1");
			});
		});

		it("does nothing when personaId is null", async () => {
			const { result } = renderCrudHook({ personaId: null });

			await waitFor(() => {
				expect(result.current.isLoading).toBe(false);
			});

			act(() => {
				result.current.handleReorder([]);
			});

			expect(mocks.mockApiPatch).not.toHaveBeenCalled();
		});
	});
});
