/**
 * Tests for the ChangeFlagsBanner component (§6.2).
 *
 * REQ-012 §7.6: Warning banner showing count of pending
 * PersonaChangeFlags on the persona overview page.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ChangeFlagsBanner } from "./change-flags-banner";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const BANNER_TESTID = "change-flags-banner";

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

const MOCK_LIST_META = { total: 0, page: 1, per_page: 20, total_pages: 1 };

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

vi.mock("next/link", () => ({
	default: ({
		href,
		children,
		...props
	}: {
		href: string;
		children: ReactNode;
		[key: string]: unknown;
	}) => (
		<a href={href} {...props}>
			{children}
		</a>
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

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ChangeFlagsBanner", () => {
	beforeEach(() => {
		mocks.mockApiGet.mockReset();
	});

	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	it("renders nothing when pending count is 0", async () => {
		mocks.mockApiGet.mockResolvedValue({
			data: [],
			meta: { ...MOCK_LIST_META, total: 0 },
		});

		const Wrapper = createWrapper();
		render(
			<Wrapper>
				<ChangeFlagsBanner />
			</Wrapper>,
		);

		await waitFor(() => {
			expect(mocks.mockApiGet).toHaveBeenCalled();
		});

		expect(screen.queryByTestId(BANNER_TESTID)).not.toBeInTheDocument();
	});

	it("renders nothing during loading", () => {
		mocks.mockApiGet.mockReturnValue(new Promise(() => {}));

		const Wrapper = createWrapper();
		render(
			<Wrapper>
				<ChangeFlagsBanner />
			</Wrapper>,
		);

		expect(screen.queryByTestId(BANNER_TESTID)).not.toBeInTheDocument();
	});

	it("renders banner when pending count is greater than 0", async () => {
		mocks.mockApiGet.mockResolvedValue({
			data: [makeFlag("1"), makeFlag("2"), makeFlag("3")],
			meta: { ...MOCK_LIST_META, total: 3 },
		});

		const Wrapper = createWrapper();
		render(
			<Wrapper>
				<ChangeFlagsBanner />
			</Wrapper>,
		);

		await waitFor(() => {
			expect(screen.getByTestId(BANNER_TESTID)).toBeInTheDocument();
		});
	});

	it("shows singular text for 1 flag", async () => {
		mocks.mockApiGet.mockResolvedValue({
			data: [makeFlag("1")],
			meta: { ...MOCK_LIST_META, total: 1 },
		});

		const Wrapper = createWrapper();
		render(
			<Wrapper>
				<ChangeFlagsBanner />
			</Wrapper>,
		);

		await waitFor(() => {
			expect(screen.getByText("1 change needs review")).toBeInTheDocument();
		});
	});

	it("shows plural text for multiple flags", async () => {
		mocks.mockApiGet.mockResolvedValue({
			data: [makeFlag("1"), makeFlag("2"), makeFlag("3")],
			meta: { ...MOCK_LIST_META, total: 3 },
		});

		const Wrapper = createWrapper();
		render(
			<Wrapper>
				<ChangeFlagsBanner />
			</Wrapper>,
		);

		await waitFor(() => {
			expect(screen.getByText("3 changes need review")).toBeInTheDocument();
		});
	});

	it("contains link to /persona/change-flags", async () => {
		mocks.mockApiGet.mockResolvedValue({
			data: [makeFlag("1")],
			meta: { ...MOCK_LIST_META, total: 1 },
		});

		const Wrapper = createWrapper();
		render(
			<Wrapper>
				<ChangeFlagsBanner />
			</Wrapper>,
		);

		await waitFor(() => {
			const link = screen.getByRole("link", { name: /review/i });
			expect(link).toHaveAttribute("href", "/persona/change-flags");
		});
	});

	it("link has accessible text 'Review'", async () => {
		mocks.mockApiGet.mockResolvedValue({
			data: [makeFlag("1")],
			meta: { ...MOCK_LIST_META, total: 1 },
		});

		const Wrapper = createWrapper();
		render(
			<Wrapper>
				<ChangeFlagsBanner />
			</Wrapper>,
		);

		await waitFor(() => {
			expect(screen.getByRole("link", { name: "Review" })).toBeInTheDocument();
		});
	});

	it("has role='status'", async () => {
		mocks.mockApiGet.mockResolvedValue({
			data: [makeFlag("1")],
			meta: { ...MOCK_LIST_META, total: 1 },
		});

		const Wrapper = createWrapper();
		render(
			<Wrapper>
				<ChangeFlagsBanner />
			</Wrapper>,
		);

		await waitFor(() => {
			expect(screen.getByRole("status")).toBeInTheDocument();
		});
	});

	it("shows warning icon", async () => {
		mocks.mockApiGet.mockResolvedValue({
			data: [makeFlag("1")],
			meta: { ...MOCK_LIST_META, total: 1 },
		});

		const Wrapper = createWrapper();
		const { container } = render(
			<Wrapper>
				<ChangeFlagsBanner />
			</Wrapper>,
		);

		await waitFor(() => {
			expect(screen.getByTestId(BANNER_TESTID)).toBeInTheDocument();
		});

		// Lucide icons render as SVG elements
		const svg = container.querySelector("svg");
		expect(svg).toBeInTheDocument();
	});

	it("calls API with status=Pending", async () => {
		mocks.mockApiGet.mockResolvedValue({
			data: [],
			meta: { ...MOCK_LIST_META, total: 0 },
		});

		const Wrapper = createWrapper();
		render(
			<Wrapper>
				<ChangeFlagsBanner />
			</Wrapper>,
		);

		await waitFor(() => {
			expect(mocks.mockApiGet).toHaveBeenCalledWith("/persona-change-flags", {
				status: "Pending",
			});
		});
	});

	it("renders nothing on API error", async () => {
		mocks.mockApiGet.mockRejectedValue(
			new mocks.MockApiError("NETWORK_ERROR", "Connection failed", 0),
		);

		const Wrapper = createWrapper();
		render(
			<Wrapper>
				<ChangeFlagsBanner />
			</Wrapper>,
		);

		// Wait for the query to settle (error state)
		await waitFor(() => {
			expect(mocks.mockApiGet).toHaveBeenCalled();
		});

		expect(screen.queryByTestId(BANNER_TESTID)).not.toBeInTheDocument();
	});
});
