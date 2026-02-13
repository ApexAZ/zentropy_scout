/**
 * Tests for the main route group layout (§6.2).
 *
 * REQ-012 §3.2: Layout passes pendingFlagsCount to AppShell for
 * the global nav badge indicator.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import MainLayout from "./layout";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MOCK_LIST_META = { total: 0, page: 1, per_page: 20, total_pages: 1 };

function makeFlag(id: string) {
	return {
		id,
		persona_id: "00000000-0000-4000-a000-000000000001",
		change_type: "skill_added" as const,
		item_id: `item-${id}`,
		item_description: `Added skill ${id}`,
		status: "Pending" as const,
		resolution: null,
		resolved_at: null,
		created_at: "2026-01-15T00:00:00Z",
	};
}

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
		MockApiError,
	};
});

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
	ApiError: mocks.MockApiError,
}));

vi.mock("@/components/layout/onboarding-gate", () => ({
	OnboardingGate: ({ children }: { children: ReactNode }) => (
		<div data-testid="onboarding-gate">{children}</div>
	),
}));

vi.mock("@/components/layout/app-shell", () => ({
	AppShell: ({
		children,
		pendingFlagsCount,
	}: {
		children: ReactNode;
		pendingFlagsCount?: number;
	}) => (
		<div
			data-testid="app-shell"
			data-pending-flags-count={pendingFlagsCount ?? 0}
		>
			{children}
		</div>
	),
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

function renderLayout(
	children: ReactNode = <div data-testid="child">Hello</div>,
) {
	const Wrapper = createWrapper();
	return render(
		<Wrapper>
			<MainLayout>{children}</MainLayout>
		</Wrapper>,
	);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("MainLayout", () => {
	beforeEach(() => {
		mocks.mockApiGet.mockReset();
	});

	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	it("renders children inside AppShell", async () => {
		mocks.mockApiGet.mockResolvedValue({
			data: [],
			meta: { ...MOCK_LIST_META, total: 0 },
		});

		renderLayout();

		await waitFor(() => {
			expect(screen.getByTestId("app-shell")).toBeInTheDocument();
		});

		expect(screen.getByTestId("child")).toBeInTheDocument();
	});

	it("passes pendingFlagsCount=0 when no flags exist", async () => {
		mocks.mockApiGet.mockResolvedValue({
			data: [],
			meta: { ...MOCK_LIST_META, total: 0 },
		});

		renderLayout();

		await waitFor(() => {
			expect(mocks.mockApiGet).toHaveBeenCalled();
		});

		const shell = screen.getByTestId("app-shell");
		expect(shell).toHaveAttribute("data-pending-flags-count", "0");
	});

	it("passes correct count when flags exist", async () => {
		mocks.mockApiGet.mockResolvedValue({
			data: [makeFlag("1"), makeFlag("2")],
			meta: { ...MOCK_LIST_META, total: 2 },
		});

		renderLayout();

		await waitFor(() => {
			const shell = screen.getByTestId("app-shell");
			expect(shell).toHaveAttribute("data-pending-flags-count", "2");
		});
	});

	it("defaults to 0 on API error", async () => {
		mocks.mockApiGet.mockRejectedValue(
			new mocks.MockApiError("NETWORK_ERROR", "Connection failed", 0),
		);

		renderLayout();

		await waitFor(() => {
			expect(mocks.mockApiGet).toHaveBeenCalled();
		});

		const shell = screen.getByTestId("app-shell");
		expect(shell).toHaveAttribute("data-pending-flags-count", "0");
	});

	it("calls API with status=Pending", async () => {
		mocks.mockApiGet.mockResolvedValue({
			data: [],
			meta: { ...MOCK_LIST_META, total: 0 },
		});

		renderLayout();

		await waitFor(() => {
			expect(mocks.mockApiGet).toHaveBeenCalledWith("/persona-change-flags", {
				status: "Pending",
			});
		});
	});

	it("defaults to 0 during loading", () => {
		mocks.mockApiGet.mockReturnValue(new Promise(() => {}));

		renderLayout();

		const shell = screen.getByTestId("app-shell");
		expect(shell).toHaveAttribute("data-pending-flags-count", "0");
	});
});
