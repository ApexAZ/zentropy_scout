/**
 * Tests for the useIsMobile hook.
 *
 * REQ-012 §4.5: Mobile breakpoint at 768px.
 */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useIsMobile } from "./use-is-mobile";

// ---------------------------------------------------------------------------
// matchMedia mock
// ---------------------------------------------------------------------------

interface MockMediaQueryList {
	matches: boolean;
	media: string;
	addEventListener: ReturnType<typeof vi.fn>;
	removeEventListener: ReturnType<typeof vi.fn>;
	onchange: null;
	addListener: ReturnType<typeof vi.fn>;
	removeListener: ReturnType<typeof vi.fn>;
	dispatchEvent: ReturnType<typeof vi.fn>;
}

function createMockMediaQueryList(matches: boolean): MockMediaQueryList {
	return {
		matches,
		media: "(max-width: 767px)",
		addEventListener: vi.fn(),
		removeEventListener: vi.fn(),
		onchange: null,
		addListener: vi.fn(),
		removeListener: vi.fn(),
		dispatchEvent: vi.fn(),
	};
}

// ---------------------------------------------------------------------------
// Setup / Teardown
// ---------------------------------------------------------------------------

let originalMatchMedia: typeof window.matchMedia;

beforeEach(() => {
	originalMatchMedia = window.matchMedia;
});

afterEach(() => {
	window.matchMedia = originalMatchMedia;
	vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useIsMobile", () => {
	it("returns false when viewport is above mobile breakpoint", () => {
		const mql = createMockMediaQueryList(false);
		window.matchMedia = vi.fn().mockReturnValue(mql);

		const { result } = renderHook(() => useIsMobile());

		expect(result.current).toBe(false);
		expect(window.matchMedia).toHaveBeenCalledWith("(max-width: 767px)");
	});

	it("returns true when viewport is at or below 767px", () => {
		const mql = createMockMediaQueryList(true);
		window.matchMedia = vi.fn().mockReturnValue(mql);

		const { result } = renderHook(() => useIsMobile());

		expect(result.current).toBe(true);
	});

	it("updates when viewport changes", () => {
		const mql = createMockMediaQueryList(false);
		window.matchMedia = vi.fn().mockReturnValue(mql);

		const { result } = renderHook(() => useIsMobile());
		expect(result.current).toBe(false);

		// Simulate viewport change to mobile
		act(() => {
			const changeHandler = mql.addEventListener.mock.calls.find(
				(call: unknown[]) => call[0] === "change",
			)?.[1] as ((event: { matches: boolean }) => void) | undefined;
			changeHandler?.({ matches: true });
		});

		expect(result.current).toBe(true);
	});

	it("cleans up listener on unmount", () => {
		const mql = createMockMediaQueryList(false);
		window.matchMedia = vi.fn().mockReturnValue(mql);

		const { unmount } = renderHook(() => useIsMobile());

		expect(mql.addEventListener).toHaveBeenCalledWith(
			"change",
			expect.any(Function),
		);

		unmount();

		expect(mql.removeEventListener).toHaveBeenCalledWith(
			"change",
			expect.any(Function),
		);
	});

	it("returns false when matchMedia is unavailable (SSR)", () => {
		// eslint-disable-next-line @typescript-eslint/no-explicit-any -- SSR simulation requires removing matchMedia
		window.matchMedia = undefined as any;

		const { result } = renderHook(() => useIsMobile());
		expect(result.current).toBe(false);
	});
});
