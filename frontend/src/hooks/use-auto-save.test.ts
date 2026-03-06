/**
 * Tests for the useAutoSave hook.
 *
 * REQ-026 §7.1: Save strategy — debounced auto-save on keystroke.
 * REQ-026 §7.2: Save status indicator states.
 * REQ-026 §7.3: Optimistic concurrency with 409 Conflict handling.
 */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { SaveStatus } from "@/components/editor/editor-status-bar";

// ---------------------------------------------------------------------------
// Mocks (vi.hoisted pattern)
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => {
	const mockApiPatch = vi.fn();

	class MockApiError extends Error {
		readonly code: string;
		readonly status: number;
		constructor(code: string, message: string, status: number) {
			super(message);
			this.name = "ApiError";
			this.code = code;
			this.status = status;
		}
	}

	return { mockApiPatch, MockApiError };
});

vi.mock("@/lib/api-client", () => ({
	apiPatch: mocks.mockApiPatch,
	ApiError: mocks.MockApiError,
}));

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TEST_RESUME_ID = "550e8400-e29b-41d4-a716-446655440000";
const DEBOUNCE_MS = 2000;
const INITIAL_CONTENT = "# Hello";
const CHANGED_CONTENT = "# Hello World";

// ---------------------------------------------------------------------------
// Setup / Teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
	vi.clearAllMocks();
	vi.useFakeTimers();
});

afterEach(() => {
	vi.useRealTimers();
	vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function loadHook() {
	const mod = await import("@/hooks/use-auto-save");
	return mod.useAutoSave;
}

async function renderAutoSave(initialContent = INITIAL_CONTENT) {
	const useAutoSave = await loadHook();
	return renderHook(
		({ content }: { content: string }) =>
			useAutoSave({ content, resumeId: TEST_RESUME_ID }),
		{ initialProps: { content: initialContent } },
	);
}

function mockSuccessfulSave() {
	mocks.mockApiPatch.mockResolvedValue({
		data: { id: TEST_RESUME_ID, updated_at: "2026-03-05T10:01:00Z" },
	});
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useAutoSave", () => {
	describe("initial state", () => {
		it("starts with 'saved' status when no content changes", async () => {
			const { result } = await renderAutoSave();

			expect(result.current.saveStatus).toBe("saved" satisfies SaveStatus);
		});

		it("does not make API calls on mount", async () => {
			await renderAutoSave();

			await act(() => vi.advanceTimersByTimeAsync(DEBOUNCE_MS + 100));
			expect(mocks.mockApiPatch).not.toHaveBeenCalled();
		});
	});

	describe("debounced save", () => {
		it("sets status to 'unsaved' when content changes", async () => {
			const { result, rerender } = await renderAutoSave();

			rerender({ content: CHANGED_CONTENT });

			expect(result.current.saveStatus).toBe("unsaved" satisfies SaveStatus);
		});

		it("does not save before debounce timer expires", async () => {
			const { rerender } = await renderAutoSave();

			rerender({ content: CHANGED_CONTENT });
			await act(() => vi.advanceTimersByTimeAsync(DEBOUNCE_MS - 100));

			expect(mocks.mockApiPatch).not.toHaveBeenCalled();
		});

		it("saves after debounce timer expires", async () => {
			mockSuccessfulSave();
			const { rerender } = await renderAutoSave();

			rerender({ content: CHANGED_CONTENT });
			await act(() => vi.advanceTimersByTimeAsync(DEBOUNCE_MS + 100));

			expect(mocks.mockApiPatch).toHaveBeenCalledWith(
				`/base-resumes/${TEST_RESUME_ID}`,
				{ markdown_content: CHANGED_CONTENT },
			);
		});

		it("resets debounce timer on each content change", async () => {
			const { rerender } = await renderAutoSave();

			rerender({ content: "# Hello W" });
			await act(() => vi.advanceTimersByTimeAsync(1500));

			rerender({ content: CHANGED_CONTENT });
			await act(() => vi.advanceTimersByTimeAsync(1500));

			// 1500 + 1500 = 3000ms total, but timer was reset at 1500
			// so only 1500ms since last change — should NOT have saved
			expect(mocks.mockApiPatch).not.toHaveBeenCalled();
		});
	});

	describe("save status transitions", () => {
		it("transitions to 'saving' during save", async () => {
			let resolveSave!: (value: unknown) => void;
			mocks.mockApiPatch.mockReturnValue(
				new Promise((resolve) => {
					resolveSave = resolve;
				}),
			);

			const { result, rerender } = await renderAutoSave();

			rerender({ content: CHANGED_CONTENT });
			await act(() => vi.advanceTimersByTimeAsync(DEBOUNCE_MS + 100));

			expect(result.current.saveStatus).toBe("saving" satisfies SaveStatus);

			await act(async () => {
				resolveSave({
					data: {
						id: TEST_RESUME_ID,
						updated_at: "2026-03-05T10:01:00Z",
					},
				});
			});

			expect(result.current.saveStatus).toBe("saved" satisfies SaveStatus);
		});

		it("transitions to 'error' on save failure", async () => {
			mocks.mockApiPatch.mockRejectedValue(
				new mocks.MockApiError("INTERNAL_ERROR", "Server error", 500),
			);

			const { result, rerender } = await renderAutoSave();

			rerender({ content: CHANGED_CONTENT });
			await act(() => vi.advanceTimersByTimeAsync(DEBOUNCE_MS + 100));

			expect(result.current.saveStatus).toBe("error" satisfies SaveStatus);
		});

		it("sets hasConflict on 409 response", async () => {
			mocks.mockApiPatch.mockRejectedValue(
				new mocks.MockApiError("CONFLICT", "Resume modified elsewhere", 409),
			);

			const { result, rerender } = await renderAutoSave();

			rerender({ content: CHANGED_CONTENT });
			await act(() => vi.advanceTimersByTimeAsync(DEBOUNCE_MS + 100));

			expect(result.current.saveStatus).toBe("error" satisfies SaveStatus);
			expect(result.current.hasConflict).toBe(true);
		});
	});

	describe("beforeunload", () => {
		it("adds beforeunload listener when unsaved", async () => {
			const addSpy = vi.spyOn(window, "addEventListener");
			const { rerender } = await renderAutoSave();

			rerender({ content: CHANGED_CONTENT });

			expect(addSpy).toHaveBeenCalledWith("beforeunload", expect.any(Function));
		});

		it("removes beforeunload listener on unmount", async () => {
			const removeSpy = vi.spyOn(window, "removeEventListener");
			const { rerender, unmount } = await renderAutoSave();

			rerender({ content: CHANGED_CONTENT });
			unmount();

			expect(removeSpy).toHaveBeenCalledWith(
				"beforeunload",
				expect.any(Function),
			);
		});
	});

	describe("disabled", () => {
		it("does not save when enabled is false", async () => {
			const useAutoSave = await loadHook();
			const { rerender } = renderHook(
				({ content, enabled }: { content: string; enabled: boolean }) =>
					useAutoSave({
						content,
						resumeId: TEST_RESUME_ID,
						enabled,
					}),
				{
					initialProps: {
						content: INITIAL_CONTENT,
						enabled: false,
					},
				},
			);

			rerender({ content: CHANGED_CONTENT, enabled: false });
			await act(() => vi.advanceTimersByTimeAsync(DEBOUNCE_MS + 100));

			expect(mocks.mockApiPatch).not.toHaveBeenCalled();
		});
	});

	describe("cleanup", () => {
		it("clears debounce timer on unmount", async () => {
			const { rerender, unmount } = await renderAutoSave();

			rerender({ content: CHANGED_CONTENT });
			unmount();

			await act(() => vi.advanceTimersByTimeAsync(DEBOUNCE_MS + 100));
			expect(mocks.mockApiPatch).not.toHaveBeenCalled();
		});
	});
});
