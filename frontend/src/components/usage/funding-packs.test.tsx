/**
 * Tests for the FundingPacks component.
 *
 * REQ-029 §9.2: Pack selection cards with highlight badge.
 * REQ-029 §9.3: Checkout flow via window.location.href redirect.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { PackItem } from "@/types/usage";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => {
	const mockFetchCreditPacks = vi.fn();
	const mockCreateCheckoutSession = vi.fn();
	const mockShowToast = {
		success: vi.fn(),
		error: vi.fn(),
		warning: vi.fn(),
		info: vi.fn(),
		dismiss: vi.fn(),
	};
	return { mockFetchCreditPacks, mockCreateCheckoutSession, mockShowToast };
});

vi.mock("@/lib/api/credits", () => ({
	fetchCreditPacks: mocks.mockFetchCreditPacks,
	createCheckoutSession: mocks.mockCreateCheckoutSession,
}));

vi.mock("@/lib/toast", () => ({
	showToast: mocks.mockShowToast,
}));

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

const PACK_STARTER: PackItem = {
	id: "pack-1",
	name: "Starter",
	price_cents: 500,
	price_display: "$5.00",
	grant_cents: 500,
	amount_display: "$5.00",
	description: "Get started with Zentropy",
	highlight_label: null,
};

const PACK_POPULAR: PackItem = {
	id: "pack-2",
	name: "Professional",
	price_cents: 1500,
	price_display: "$15.00",
	grant_cents: 1500,
	amount_display: "$15.00",
	description: "Most popular choice",
	highlight_label: "Most Popular",
};

const PACK_PREMIUM: PackItem = {
	id: "pack-3",
	name: "Premium",
	price_cents: 5000,
	price_display: "$50.00",
	grant_cents: 5000,
	amount_display: "$50.00",
	description: "For power users",
	highlight_label: null,
};

const ALL_PACKS = [PACK_STARTER, PACK_POPULAR, PACK_PREMIUM];

const TEST_CHECKOUT_URL = "https://checkout.stripe.com/pay/cs_test_abc";
const TEST_SESSION_ID = "cs_test_abc";

const ADD_FUNDS_MATCHER = /add funds/i;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

let queryClient: QueryClient;

function wrapper({ children }: { children: ReactNode }) {
	return (
		<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
	);
}

// Lazy import to allow mocks to register first
async function renderFundingPacks() {
	const { FundingPacks } = await import("./funding-packs");
	return render(<FundingPacks />, { wrapper });
}

/** Wait for packs to render (sentinel: first pack name visible). */
async function waitForPacks() {
	await waitFor(() => {
		expect(screen.getByText(PACK_STARTER.name)).toBeInTheDocument();
	});
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
	vi.clearAllMocks();
	queryClient = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
});

afterEach(() => {
	cleanup();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("FundingPacks", () => {
	it("renders loading skeleton while fetching packs", async () => {
		mocks.mockFetchCreditPacks.mockReturnValue(new Promise(() => {}));
		await renderFundingPacks();
		expect(screen.getByTestId("funding-packs-skeleton")).toBeInTheDocument();
	});

	it("renders all pack cards from API data", async () => {
		mocks.mockFetchCreditPacks.mockResolvedValue({ data: ALL_PACKS });
		await renderFundingPacks();
		await waitForPacks();
		expect(screen.getByText(PACK_POPULAR.name)).toBeInTheDocument();
		expect(screen.getByText(PACK_PREMIUM.name)).toBeInTheDocument();
	});

	it("displays price and description for each pack", async () => {
		mocks.mockFetchCreditPacks.mockResolvedValue({ data: ALL_PACKS });
		await renderFundingPacks();
		await waitFor(() => {
			expect(screen.getByText(PACK_STARTER.price_display)).toBeInTheDocument();
		});
		expect(screen.getByText(PACK_STARTER.description)).toBeInTheDocument();
		expect(screen.getByText(PACK_POPULAR.price_display)).toBeInTheDocument();
		expect(screen.getByText(PACK_PREMIUM.price_display)).toBeInTheDocument();
	});

	it("shows highlight badge on highlighted pack", async () => {
		mocks.mockFetchCreditPacks.mockResolvedValue({ data: ALL_PACKS });
		await renderFundingPacks();
		await waitFor(() => {
			expect(
				screen.getByText(PACK_POPULAR.highlight_label as string),
			).toBeInTheDocument();
		});
		const badge = screen.getByTestId(`highlight-badge-${PACK_POPULAR.id}`);
		expect(badge).toHaveTextContent(PACK_POPULAR.highlight_label as string);
	});

	it("does not show highlight badge on non-highlighted packs", async () => {
		mocks.mockFetchCreditPacks.mockResolvedValue({ data: ALL_PACKS });
		await renderFundingPacks();
		await waitForPacks();
		expect(
			screen.queryByTestId(`highlight-badge-${PACK_STARTER.id}`),
		).not.toBeInTheDocument();
		expect(
			screen.queryByTestId(`highlight-badge-${PACK_PREMIUM.id}`),
		).not.toBeInTheDocument();
	});

	it("gives highlighted pack visual emphasis via border accent", async () => {
		mocks.mockFetchCreditPacks.mockResolvedValue({ data: ALL_PACKS });
		await renderFundingPacks();
		await waitFor(() => {
			expect(screen.getByText(PACK_POPULAR.name)).toBeInTheDocument();
		});
		const highlightedCard = screen.getByTestId(`pack-card-${PACK_POPULAR.id}`);
		expect(highlightedCard.className).toContain("border-primary");
	});

	it("renders an Add Funds button for each pack", async () => {
		mocks.mockFetchCreditPacks.mockResolvedValue({ data: ALL_PACKS });
		await renderFundingPacks();
		await waitForPacks();
		const buttons = screen.getAllByRole("button", {
			name: ADD_FUNDS_MATCHER,
		});
		expect(buttons).toHaveLength(3);
	});

	// -----------------------------------------------------------------------
	// Checkout flow — nested describe for window.location mock lifecycle
	// -----------------------------------------------------------------------

	describe("checkout flow", () => {
		let originalLocation: Location;
		const mockAssign = vi.fn();

		beforeEach(() => {
			originalLocation = window.location;
			Object.defineProperty(window, "location", {
				writable: true,
				value: { ...originalLocation, assign: mockAssign },
			});
		});

		afterEach(() => {
			mockAssign.mockClear();
			Object.defineProperty(window, "location", {
				writable: true,
				value: originalLocation,
			});
		});

		it("calls checkout API and redirects on Add Funds click", async () => {
			mocks.mockFetchCreditPacks.mockResolvedValue({ data: ALL_PACKS });
			mocks.mockCreateCheckoutSession.mockResolvedValue({
				data: {
					checkout_url: TEST_CHECKOUT_URL,
					session_id: TEST_SESSION_ID,
				},
			});

			const user = userEvent.setup();
			await renderFundingPacks();
			await waitForPacks();

			const starterButton = screen.getAllByRole("button", {
				name: ADD_FUNDS_MATCHER,
			})[0];
			await user.click(starterButton);

			await waitFor(() => {
				expect(mocks.mockCreateCheckoutSession).toHaveBeenCalledWith(
					PACK_STARTER.id,
				);
			});
			expect(mockAssign).toHaveBeenCalledWith(TEST_CHECKOUT_URL);
		});
	});

	it("disables all buttons during checkout loading", async () => {
		mocks.mockFetchCreditPacks.mockResolvedValue({ data: ALL_PACKS });
		// Keep checkout pending to test loading state
		mocks.mockCreateCheckoutSession.mockReturnValue(new Promise(() => {}));

		const user = userEvent.setup();
		await renderFundingPacks();
		await waitForPacks();

		const buttons = screen.getAllByRole("button", {
			name: ADD_FUNDS_MATCHER,
		});
		await user.click(buttons[0]);

		// All buttons should be disabled during checkout
		await waitFor(() => {
			const allButtons = screen.getAllByRole("button");
			const fundingButtons = allButtons.filter(
				(btn) =>
					btn.textContent?.includes("Add Funds") ||
					btn.textContent?.includes("Redirecting"),
			);
			for (const btn of fundingButtons) {
				expect(btn).toBeDisabled();
			}
		});
	});

	it("shows error toast on checkout failure and re-enables buttons", async () => {
		mocks.mockFetchCreditPacks.mockResolvedValue({ data: ALL_PACKS });
		mocks.mockCreateCheckoutSession.mockRejectedValue(
			new Error("Network error"),
		);

		const user = userEvent.setup();
		await renderFundingPacks();
		await waitForPacks();

		const buttons = screen.getAllByRole("button", {
			name: ADD_FUNDS_MATCHER,
		});
		await user.click(buttons[0]);

		await waitFor(() => {
			expect(mocks.mockShowToast.error).toHaveBeenCalledWith(
				"Unable to start checkout. Please try again.",
			);
		});

		// Buttons should be re-enabled after error
		await waitFor(() => {
			const reenabledButtons = screen.getAllByRole("button", {
				name: ADD_FUNDS_MATCHER,
			});
			for (const btn of reenabledButtons) {
				expect(btn).not.toBeDisabled();
			}
		});
	});

	it("renders empty state when no packs returned", async () => {
		mocks.mockFetchCreditPacks.mockResolvedValue({ data: [] });
		await renderFundingPacks();
		await waitFor(() => {
			expect(screen.getByText(/no funding packs/i)).toBeInTheDocument();
		});
	});
});
