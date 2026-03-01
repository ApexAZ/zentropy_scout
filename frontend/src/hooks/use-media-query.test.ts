/**
 * Tests for the generic useMediaQuery hook.
 *
 * REQ-012 §5.1: Responsive breakpoint detection.
 */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useMediaQuery } from "./use-media-query";

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

function createMockMediaQueryList(
	matches: boolean,
	media: string,
): MockMediaQueryList {
	return {
		matches,
		media,
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
// Constants
// ---------------------------------------------------------------------------

const TEST_QUERY = "(min-width: 1024px)";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useMediaQuery", () => {
	it("returns true when query matches", () => {
		const mql = createMockMediaQueryList(true, TEST_QUERY);
		window.matchMedia = vi.fn().mockReturnValue(mql);

		const { result } = renderHook(() => useMediaQuery(TEST_QUERY));

		expect(result.current).toBe(true);
		expect(window.matchMedia).toHaveBeenCalledWith(TEST_QUERY);
	});

	it("returns false when query does not match", () => {
		const mql = createMockMediaQueryList(false, TEST_QUERY);
		window.matchMedia = vi.fn().mockReturnValue(mql);

		const { result } = renderHook(() => useMediaQuery(TEST_QUERY));

		expect(result.current).toBe(false);
	});

	it("updates on media query change event", () => {
		const mql = createMockMediaQueryList(false, TEST_QUERY);
		window.matchMedia = vi.fn().mockReturnValue(mql);

		const { result } = renderHook(() => useMediaQuery(TEST_QUERY));
		expect(result.current).toBe(false);

		act(() => {
			const changeHandler = mql.addEventListener.mock.calls.find(
				(call: unknown[]) => call[0] === "change",
			)?.[1] as ((event: { matches: boolean }) => void) | undefined;
			changeHandler?.({ matches: true });
		});

		expect(result.current).toBe(true);
	});

	it("cleans up listener on unmount", () => {
		const mql = createMockMediaQueryList(false, TEST_QUERY);
		window.matchMedia = vi.fn().mockReturnValue(mql);

		const { unmount } = renderHook(() => useMediaQuery(TEST_QUERY));

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

	it("returns false for SSR (no window.matchMedia)", () => {
		window.matchMedia = undefined as unknown as typeof window.matchMedia;

		const { result } = renderHook(() => useMediaQuery(TEST_QUERY));
		expect(result.current).toBe(false);
	});
});
