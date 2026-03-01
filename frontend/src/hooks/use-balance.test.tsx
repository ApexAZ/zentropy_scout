/**
 * Tests for the useBalance hook.
 *
 * REQ-020 §9.1: Balance display in navigation bar — hook fetches
 * current balance from GET /api/v1/usage/balance.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ApiResponse } from "@/types/api";
import type { BalanceResponse } from "@/types/usage";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => {
	const mockApiGet = vi.fn();
	return { mockApiGet };
});

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function createWrapper() {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: { retry: false },
		},
	});
	return function Wrapper({ children }: { children: ReactNode }) {
		return (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);
	};
}

function makeBalanceResponse(
	balanceUsd = "10.500000",
): ApiResponse<BalanceResponse> {
	return {
		data: {
			balance_usd: balanceUsd,
			as_of: "2026-02-28T12:00:00Z",
		},
	};
}

// ---------------------------------------------------------------------------
// Lazy import (must come after vi.mock)
// ---------------------------------------------------------------------------

async function importHook() {
	return import("./use-balance");
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
	vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useBalance", () => {
	it("returns balance from API", async () => {
		mocks.mockApiGet.mockResolvedValue(makeBalanceResponse("10.500000"));
		const { useBalance } = await importHook();

		const { result } = renderHook(() => useBalance(), {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(result.current.balance).toBe("10.500000");
		});
	});

	it("returns undefined while loading", async () => {
		mocks.mockApiGet.mockReturnValue(new Promise(() => {}));
		const { useBalance } = await importHook();

		const { result } = renderHook(() => useBalance(), {
			wrapper: createWrapper(),
		});

		expect(result.current.balance).toBeUndefined();
		expect(result.current.isLoading).toBe(true);
	});

	it("returns error when API fails", async () => {
		mocks.mockApiGet.mockRejectedValue(new Error("Network error"));
		const { useBalance } = await importHook();

		const { result } = renderHook(() => useBalance(), {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(result.current.error?.message).toBe("Network error");
		});
	});

	it("calls apiGet with /usage/balance path", async () => {
		mocks.mockApiGet.mockResolvedValue(makeBalanceResponse());
		const { useBalance } = await importHook();

		renderHook(() => useBalance(), {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(mocks.mockApiGet).toHaveBeenCalledWith("/usage/balance");
		});
	});

	it("returns balance for zero-balance user", async () => {
		mocks.mockApiGet.mockResolvedValue(makeBalanceResponse("0.000000"));
		const { useBalance } = await importHook();

		const { result } = renderHook(() => useBalance(), {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(result.current.balance).toBe("0.000000");
		});
	});

	it("returns balance for large balance", async () => {
		mocks.mockApiGet.mockResolvedValue(makeBalanceResponse("9999.999999"));
		const { useBalance } = await importHook();

		const { result } = renderHook(() => useBalance(), {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(result.current.balance).toBe("9999.999999");
		});
	});
});
