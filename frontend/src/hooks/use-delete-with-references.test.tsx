/**
 * Tests for the useDeleteWithReferences hook (§6.12).
 *
 * REQ-012 §7.5 / REQ-001 §7b: Deletion reference check state machine.
 */

import { renderHook, act, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ReferencingEntity } from "@/types/deletion";

import { useDeleteWithReferences } from "./use-delete-with-references";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PERSONA_ID = "00000000-0000-4000-a000-000000000001";
const ITEM_ID = "item-001";
const ITEM_LABEL = "Python";

interface TestItem {
	id: string;
	name: string;
}

const TEST_ITEM: TestItem = { id: ITEM_ID, name: ITEM_LABEL };
const REFERENCES_URL = `/personas/${PERSONA_ID}/skills/${ITEM_ID}/references`;
const DELETE_URL = `/personas/${PERSONA_ID}/skills/${ITEM_ID}`;

const MUTABLE_REF: ReferencingEntity = {
	id: "ref-001",
	name: "My Resume",
	type: "base_resume",
	immutable: false,
};

const MUTABLE_REF_2: ReferencingEntity = {
	id: "ref-002",
	name: "Cover Letter Draft",
	type: "cover_letter",
	immutable: false,
};

const IMMUTABLE_REF: ReferencingEntity = {
	id: "ref-003",
	name: "Submitted Resume",
	type: "base_resume",
	immutable: true,
	application_id: "app-001",
	company_name: "Acme Corp",
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
		mockApiGet: vi.fn(),
		mockApiDelete: vi.fn(),
		mockShowToast: {
			success: vi.fn(),
			error: vi.fn(),
			warning: vi.fn(),
			info: vi.fn(),
			dismiss: vi.fn(),
		},
		MockApiError,
	};
});

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
	apiDelete: mocks.mockApiDelete,
	ApiError: mocks.MockApiError,
}));

vi.mock("@/lib/toast", () => ({
	showToast: mocks.mockShowToast,
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeHookOptions(overrides?: {
	onDeleted?: (id: string) => void;
	queryClient?: { invalidateQueries: ReturnType<typeof vi.fn> };
	queryKey?: readonly unknown[];
}) {
	return {
		personaId: PERSONA_ID,
		itemType: "skill" as const,
		collection: "skills",
		getItemLabel: (item: TestItem) => item.name,
		onDeleted: overrides?.onDeleted ?? vi.fn(),
		queryClient: overrides?.queryClient as never,
		queryKey: overrides?.queryKey,
	};
}

function makeNoRefsResponse() {
	return {
		data: {
			has_references: false,
			has_immutable_references: false,
			references: [],
		},
	};
}

function makeMutableRefsResponse(refs: ReferencingEntity[] = [MUTABLE_REF]) {
	return {
		data: {
			has_references: true,
			has_immutable_references: false,
			references: refs,
		},
	};
}

function makeImmutableRefsResponse(
	refs: ReferencingEntity[] = [IMMUTABLE_REF],
) {
	return {
		data: {
			has_references: true,
			has_immutable_references: true,
			references: refs,
		},
	};
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useDeleteWithReferences", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	// -----------------------------------------------------------------------
	// Initial state
	// -----------------------------------------------------------------------

	it("starts in idle state with null target", () => {
		const { result } = renderHook(() =>
			useDeleteWithReferences<TestItem>(makeHookOptions()),
		);

		expect(result.current.flowState).toBe("idle");
		expect(result.current.deleteTarget).toBeNull();
		expect(result.current.deleteError).toBeNull();
		expect(result.current.references).toEqual([]);
		expect(result.current.hasImmutableReferences).toBe(false);
	});

	// -----------------------------------------------------------------------
	// Reference check flow
	// -----------------------------------------------------------------------

	it("sets checking state and calls apiGet when requestDelete is called", async () => {
		mocks.mockApiGet.mockReturnValue(new Promise(() => {})); // never resolves
		const { result } = renderHook(() =>
			useDeleteWithReferences<TestItem>(makeHookOptions()),
		);

		act(() => {
			result.current.requestDelete(TEST_ITEM);
		});

		expect(result.current.flowState).toBe("checking");
		expect(result.current.deleteTarget).toEqual(TEST_ITEM);
		expect(mocks.mockApiGet).toHaveBeenCalledWith(REFERENCES_URL);
	});

	it("handles 404 fallback by deleting immediately", async () => {
		mocks.mockApiGet.mockRejectedValue(
			new mocks.MockApiError("NOT_FOUND", "Not found", 404),
		);
		mocks.mockApiDelete.mockResolvedValue(undefined);
		const onDeleted = vi.fn();

		const { result } = renderHook(() =>
			useDeleteWithReferences<TestItem>(makeHookOptions({ onDeleted })),
		);

		act(() => {
			result.current.requestDelete(TEST_ITEM);
		});

		await waitFor(() => {
			expect(mocks.mockApiDelete).toHaveBeenCalledWith(
				`/personas/${PERSONA_ID}/skills/${ITEM_ID}`,
			);
		});

		await waitFor(() => {
			expect(onDeleted).toHaveBeenCalledWith(ITEM_ID);
		});
	});

	it("resets to idle on non-404 reference check error", async () => {
		mocks.mockApiGet.mockRejectedValue(
			new mocks.MockApiError("SERVER_ERROR", "Server error", 500),
		);

		const { result } = renderHook(() =>
			useDeleteWithReferences<TestItem>(makeHookOptions()),
		);

		act(() => {
			result.current.requestDelete(TEST_ITEM);
		});

		await waitFor(() => {
			expect(result.current.flowState).toBe("idle");
		});
		expect(result.current.deleteTarget).toBeNull();
	});

	// -----------------------------------------------------------------------
	// No references — immediate delete
	// -----------------------------------------------------------------------

	it("deletes immediately when no references found", async () => {
		mocks.mockApiGet.mockResolvedValue(makeNoRefsResponse());
		mocks.mockApiDelete.mockResolvedValue(undefined);
		const onDeleted = vi.fn();

		const { result } = renderHook(() =>
			useDeleteWithReferences<TestItem>(makeHookOptions({ onDeleted })),
		);

		act(() => {
			result.current.requestDelete(TEST_ITEM);
		});

		await waitFor(() => {
			expect(mocks.mockApiDelete).toHaveBeenCalledWith(
				`/personas/${PERSONA_ID}/skills/${ITEM_ID}`,
			);
		});

		await waitFor(() => {
			expect(result.current.flowState).toBe("idle");
		});
	});

	it("shows success toast on immediate delete", async () => {
		mocks.mockApiGet.mockResolvedValue(makeNoRefsResponse());
		mocks.mockApiDelete.mockResolvedValue(undefined);

		const { result } = renderHook(() =>
			useDeleteWithReferences<TestItem>(makeHookOptions()),
		);

		act(() => {
			result.current.requestDelete(TEST_ITEM);
		});

		await waitFor(() => {
			expect(mocks.mockShowToast.success).toHaveBeenCalledWith(
				`"${ITEM_LABEL}" deleted successfully.`,
			);
		});
	});

	it("calls onDeleted callback on immediate delete", async () => {
		mocks.mockApiGet.mockResolvedValue(makeNoRefsResponse());
		mocks.mockApiDelete.mockResolvedValue(undefined);
		const onDeleted = vi.fn();

		const { result } = renderHook(() =>
			useDeleteWithReferences<TestItem>(makeHookOptions({ onDeleted })),
		);

		act(() => {
			result.current.requestDelete(TEST_ITEM);
		});

		await waitFor(() => {
			expect(onDeleted).toHaveBeenCalledWith(ITEM_ID);
		});
	});

	it("invalidates query cache on immediate delete", async () => {
		mocks.mockApiGet.mockResolvedValue(makeNoRefsResponse());
		mocks.mockApiDelete.mockResolvedValue(undefined);
		const mockQueryClient = {
			invalidateQueries: vi.fn().mockResolvedValue(undefined),
		};
		const queryKey = ["personas", PERSONA_ID, "skills"] as const;

		const { result } = renderHook(() =>
			useDeleteWithReferences<TestItem>(
				makeHookOptions({
					queryClient: mockQueryClient,
					queryKey,
				}),
			),
		);

		act(() => {
			result.current.requestDelete(TEST_ITEM);
		});

		await waitFor(() => {
			expect(mockQueryClient.invalidateQueries).toHaveBeenCalledWith({
				queryKey: [...queryKey],
			});
		});
	});

	// -----------------------------------------------------------------------
	// Mutable references
	// -----------------------------------------------------------------------

	it("sets mutable-refs state when mutable references found", async () => {
		mocks.mockApiGet.mockResolvedValue(makeMutableRefsResponse());

		const { result } = renderHook(() =>
			useDeleteWithReferences<TestItem>(makeHookOptions()),
		);

		act(() => {
			result.current.requestDelete(TEST_ITEM);
		});

		await waitFor(() => {
			expect(result.current.flowState).toBe("mutable-refs");
		});
		expect(result.current.references).toEqual([MUTABLE_REF]);
		expect(result.current.hasImmutableReferences).toBe(false);
	});

	it("stores all references when multiple mutable refs found", async () => {
		mocks.mockApiGet.mockResolvedValue(
			makeMutableRefsResponse([MUTABLE_REF, MUTABLE_REF_2]),
		);

		const { result } = renderHook(() =>
			useDeleteWithReferences<TestItem>(makeHookOptions()),
		);

		act(() => {
			result.current.requestDelete(TEST_ITEM);
		});

		await waitFor(() => {
			expect(result.current.references).toHaveLength(2);
		});
	});

	// -----------------------------------------------------------------------
	// Immutable references
	// -----------------------------------------------------------------------

	it("sets immutable-block state when immutable references found", async () => {
		mocks.mockApiGet.mockResolvedValue(makeImmutableRefsResponse());

		const { result } = renderHook(() =>
			useDeleteWithReferences<TestItem>(makeHookOptions()),
		);

		act(() => {
			result.current.requestDelete(TEST_ITEM);
		});

		await waitFor(() => {
			expect(result.current.flowState).toBe("immutable-block");
		});
		expect(result.current.hasImmutableReferences).toBe(true);
		expect(result.current.references).toEqual([IMMUTABLE_REF]);
	});

	it("provides application_id and company_name for immutable refs", async () => {
		mocks.mockApiGet.mockResolvedValue(makeImmutableRefsResponse());

		const { result } = renderHook(() =>
			useDeleteWithReferences<TestItem>(makeHookOptions()),
		);

		act(() => {
			result.current.requestDelete(TEST_ITEM);
		});

		await waitFor(() => {
			expect(result.current.references[0].application_id).toBe("app-001");
			expect(result.current.references[0].company_name).toBe("Acme Corp");
		});
	});

	// -----------------------------------------------------------------------
	// Remove all and delete
	// -----------------------------------------------------------------------

	it("sets deleting state during removeAllAndDelete", async () => {
		mocks.mockApiGet.mockResolvedValue(makeMutableRefsResponse());
		let resolveDelete: () => void;
		mocks.mockApiDelete.mockReturnValue(
			new Promise<void>((resolve) => {
				resolveDelete = resolve;
			}),
		);

		const { result } = renderHook(() =>
			useDeleteWithReferences<TestItem>(makeHookOptions()),
		);

		act(() => {
			result.current.requestDelete(TEST_ITEM);
		});

		await waitFor(() => {
			expect(result.current.flowState).toBe("mutable-refs");
		});

		let deletePromise: Promise<void>;
		act(() => {
			deletePromise = result.current.removeAllAndDelete();
		});

		expect(result.current.flowState).toBe("deleting");

		await act(async () => {
			resolveDelete!();
			await deletePromise!;
		});

		expect(result.current.flowState).toBe("idle");
	});

	it("calls apiDelete and shows toast on removeAllAndDelete", async () => {
		mocks.mockApiGet.mockResolvedValue(makeMutableRefsResponse());
		mocks.mockApiDelete.mockResolvedValue(undefined);

		const { result } = renderHook(() =>
			useDeleteWithReferences<TestItem>(makeHookOptions()),
		);

		act(() => {
			result.current.requestDelete(TEST_ITEM);
		});

		await waitFor(() => {
			expect(result.current.flowState).toBe("mutable-refs");
		});

		await act(async () => {
			await result.current.removeAllAndDelete();
		});

		expect(mocks.mockApiDelete).toHaveBeenCalledWith(DELETE_URL);
		expect(mocks.mockShowToast.success).toHaveBeenCalled();
	});

	it("returns to idle after removeAllAndDelete succeeds", async () => {
		mocks.mockApiGet.mockResolvedValue(makeMutableRefsResponse());
		mocks.mockApiDelete.mockResolvedValue(undefined);
		const onDeleted = vi.fn();

		const { result } = renderHook(() =>
			useDeleteWithReferences<TestItem>(makeHookOptions({ onDeleted })),
		);

		act(() => {
			result.current.requestDelete(TEST_ITEM);
		});

		await waitFor(() => {
			expect(result.current.flowState).toBe("mutable-refs");
		});

		await act(async () => {
			await result.current.removeAllAndDelete();
		});

		expect(result.current.flowState).toBe("idle");
		expect(onDeleted).toHaveBeenCalledWith(ITEM_ID);
	});

	// -----------------------------------------------------------------------
	// Review each
	// -----------------------------------------------------------------------

	it("transitions to review-each and initializes selections", async () => {
		mocks.mockApiGet.mockResolvedValue(
			makeMutableRefsResponse([MUTABLE_REF, MUTABLE_REF_2]),
		);

		const { result } = renderHook(() =>
			useDeleteWithReferences<TestItem>(makeHookOptions()),
		);

		act(() => {
			result.current.requestDelete(TEST_ITEM);
		});

		await waitFor(() => {
			expect(result.current.flowState).toBe("mutable-refs");
		});

		act(() => {
			result.current.expandReviewEach();
		});

		expect(result.current.flowState).toBe("review-each");
		expect(result.current.reviewSelections).toEqual({
			[MUTABLE_REF.id]: true,
			[MUTABLE_REF_2.id]: true,
		});
	});

	it("toggles individual review selections", async () => {
		mocks.mockApiGet.mockResolvedValue(
			makeMutableRefsResponse([MUTABLE_REF, MUTABLE_REF_2]),
		);

		const { result } = renderHook(() =>
			useDeleteWithReferences<TestItem>(makeHookOptions()),
		);

		act(() => {
			result.current.requestDelete(TEST_ITEM);
		});

		await waitFor(() => {
			expect(result.current.flowState).toBe("mutable-refs");
		});

		act(() => {
			result.current.expandReviewEach();
		});

		act(() => {
			result.current.toggleReviewSelection(MUTABLE_REF.id);
		});

		expect(result.current.reviewSelections[MUTABLE_REF.id]).toBe(false);
		expect(result.current.reviewSelections[MUTABLE_REF_2.id]).toBe(true);
	});

	it("defaults all selections to checked", async () => {
		mocks.mockApiGet.mockResolvedValue(
			makeMutableRefsResponse([MUTABLE_REF, MUTABLE_REF_2]),
		);

		const { result } = renderHook(() =>
			useDeleteWithReferences<TestItem>(makeHookOptions()),
		);

		act(() => {
			result.current.requestDelete(TEST_ITEM);
		});

		await waitFor(() => {
			expect(result.current.flowState).toBe("mutable-refs");
		});

		act(() => {
			result.current.expandReviewEach();
		});

		expect(Object.values(result.current.reviewSelections).every(Boolean)).toBe(
			true,
		);
	});

	// -----------------------------------------------------------------------
	// Confirm review and delete
	// -----------------------------------------------------------------------

	it("calls apiDelete on confirmReviewAndDelete", async () => {
		mocks.mockApiGet.mockResolvedValue(makeMutableRefsResponse());
		mocks.mockApiDelete.mockResolvedValue(undefined);

		const { result } = renderHook(() =>
			useDeleteWithReferences<TestItem>(makeHookOptions()),
		);

		act(() => {
			result.current.requestDelete(TEST_ITEM);
		});

		await waitFor(() => {
			expect(result.current.flowState).toBe("mutable-refs");
		});

		act(() => {
			result.current.expandReviewEach();
		});

		await act(async () => {
			await result.current.confirmReviewAndDelete();
		});

		expect(mocks.mockApiDelete).toHaveBeenCalledWith(DELETE_URL);
	});

	it("returns to idle after confirmReviewAndDelete succeeds", async () => {
		mocks.mockApiGet.mockResolvedValue(makeMutableRefsResponse());
		mocks.mockApiDelete.mockResolvedValue(undefined);

		const { result } = renderHook(() =>
			useDeleteWithReferences<TestItem>(makeHookOptions()),
		);

		act(() => {
			result.current.requestDelete(TEST_ITEM);
		});

		await waitFor(() => {
			expect(result.current.flowState).toBe("mutable-refs");
		});

		act(() => {
			result.current.expandReviewEach();
		});

		await act(async () => {
			await result.current.confirmReviewAndDelete();
		});

		expect(result.current.flowState).toBe("idle");
	});

	// -----------------------------------------------------------------------
	// Cancel
	// -----------------------------------------------------------------------

	it("resets all state when cancel is called", async () => {
		mocks.mockApiGet.mockResolvedValue(makeMutableRefsResponse());

		const { result } = renderHook(() =>
			useDeleteWithReferences<TestItem>(makeHookOptions()),
		);

		act(() => {
			result.current.requestDelete(TEST_ITEM);
		});

		await waitFor(() => {
			expect(result.current.flowState).toBe("mutable-refs");
		});

		act(() => {
			result.current.cancel();
		});

		expect(result.current.flowState).toBe("idle");
		expect(result.current.deleteTarget).toBeNull();
		expect(result.current.deleteError).toBeNull();
		expect(result.current.references).toEqual([]);
	});

	// -----------------------------------------------------------------------
	// Error handling
	// -----------------------------------------------------------------------

	it("sets deleteError on delete failure", async () => {
		mocks.mockApiGet.mockResolvedValue(makeMutableRefsResponse());
		mocks.mockApiDelete.mockRejectedValue(
			new mocks.MockApiError("SERVER_ERROR", "Delete failed", 500),
		);

		const { result } = renderHook(() =>
			useDeleteWithReferences<TestItem>(makeHookOptions()),
		);

		act(() => {
			result.current.requestDelete(TEST_ITEM);
		});

		await waitFor(() => {
			expect(result.current.flowState).toBe("mutable-refs");
		});

		await act(async () => {
			await result.current.removeAllAndDelete();
		});

		expect(result.current.deleteError).toBeTruthy();
		expect(result.current.flowState).toBe("mutable-refs");
	});
});
