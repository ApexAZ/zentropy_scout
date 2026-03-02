/**
 * Tests for the Pricing tab component.
 *
 * REQ-022 §11.2, §11.5: Pricing config management — table display,
 * current badge, add/edit form with live cost preview.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { PricingConfigItem } from "@/types/admin";

import { PricingTab } from "./pricing-tab";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => {
	const mockFetchPricing = vi.fn();
	const mockCreatePricing = vi.fn();
	const mockDeletePricing = vi.fn();
	return {
		mockFetchPricing,
		mockCreatePricing,
		mockDeletePricing,
	};
});

vi.mock("@/lib/api/admin", () => ({
	fetchPricing: mocks.mockFetchPricing,
	createPricing: mocks.mockCreatePricing,
	deletePricing: mocks.mockDeletePricing,
}));

vi.mock("@/lib/toast", () => ({
	showToast: {
		success: vi.fn(),
		error: vi.fn(),
		warning: vi.fn(),
		info: vi.fn(),
		dismiss: vi.fn(),
	},
}));

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

const MOCK_TIMESTAMP = "2026-03-01T00:00:00Z";
const MOCK_MODEL_ID = "claude-3-5-haiku-20241022";
const MOCK_EFFECTIVE_DATE_CURRENT = "2026-01-01";
const MOCK_EFFECTIVE_DATE_FUTURE = "2026-04-01";

const MOCK_PRICING: PricingConfigItem[] = [
	{
		id: "p-1",
		provider: "claude",
		model: MOCK_MODEL_ID,
		input_cost_per_1k: "0.000800",
		output_cost_per_1k: "0.004000",
		margin_multiplier: "3.00",
		effective_date: MOCK_EFFECTIVE_DATE_CURRENT,
		is_current: true,
		created_at: MOCK_TIMESTAMP,
		updated_at: MOCK_TIMESTAMP,
	},
	{
		id: "p-2",
		provider: "claude",
		model: MOCK_MODEL_ID,
		input_cost_per_1k: "0.001000",
		output_cost_per_1k: "0.005000",
		margin_multiplier: "2.50",
		effective_date: MOCK_EFFECTIVE_DATE_FUTURE,
		is_current: false,
		created_at: MOCK_TIMESTAMP,
		updated_at: MOCK_TIMESTAMP,
	},
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function createQueryClient() {
	return new QueryClient({
		defaultOptions: {
			queries: { retry: false },
			mutations: { retry: false },
		},
	});
}

function Wrapper({ children }: Readonly<{ children: ReactNode }>) {
	const queryClient = createQueryClient();
	return (
		<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
	);
}

async function waitForDataLoaded() {
	await waitFor(() => {
		expect(screen.getByText(MOCK_EFFECTIVE_DATE_CURRENT)).toBeInTheDocument();
	});
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
	vi.clearAllMocks();
	mocks.mockFetchPricing.mockResolvedValue({ data: MOCK_PRICING });
});

afterEach(() => {
	cleanup();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("PricingTab", () => {
	it("renders loading state initially", () => {
		mocks.mockFetchPricing.mockReturnValue(new Promise(() => {}));
		render(<PricingTab />, { wrapper: Wrapper });
		expect(screen.getByTestId("pricing-loading")).toBeInTheDocument();
	});

	it("renders pricing table with data", async () => {
		render(<PricingTab />, { wrapper: Wrapper });
		await waitFor(() => {
			expect(screen.getAllByText("claude")).toHaveLength(2);
		});
		expect(screen.getByText(MOCK_EFFECTIVE_DATE_CURRENT)).toBeInTheDocument();
		expect(screen.getByText(MOCK_EFFECTIVE_DATE_FUTURE)).toBeInTheDocument();
	});

	it("displays Current badge for current pricing", async () => {
		render(<PricingTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		expect(screen.getByText("Current")).toBeInTheDocument();
	});

	it("shows margin multiplier", async () => {
		render(<PricingTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		expect(screen.getByText("3.00")).toBeInTheDocument();
	});

	it("shows effective dates", async () => {
		render(<PricingTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		expect(screen.getByText(MOCK_EFFECTIVE_DATE_FUTURE)).toBeInTheDocument();
	});

	it("renders Add Pricing button", async () => {
		render(<PricingTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		expect(
			screen.getByRole("button", { name: /add pricing/i }),
		).toBeInTheDocument();
	});

	it("opens add pricing dialog on button click", async () => {
		const user = userEvent.setup();
		render(<PricingTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		await user.click(screen.getByRole("button", { name: /add pricing/i }));
		expect(
			screen.getByRole("heading", { name: /add pricing/i }),
		).toBeInTheDocument();
	});

	it("shows live cost preview in add dialog", async () => {
		const user = userEvent.setup();
		render(<PricingTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		await user.click(screen.getByRole("button", { name: /add pricing/i }));
		await user.type(screen.getByLabelText(/input cost/i), "0.001");
		await user.type(screen.getByLabelText(/output cost/i), "0.005");
		await user.type(screen.getByLabelText(/margin/i), "3.0");

		// Cost preview should show calculated values
		expect(screen.getByTestId("cost-preview")).toBeInTheDocument();
	});

	it("submits add pricing form", async () => {
		const user = userEvent.setup();
		mocks.mockCreatePricing.mockResolvedValue({
			data: { ...MOCK_PRICING[0], id: "p-3" },
		});
		render(<PricingTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		await user.click(screen.getByRole("button", { name: /add pricing/i }));

		await user.click(screen.getByLabelText(/provider/i));
		await user.click(screen.getByRole("option", { name: /claude/i }));
		// Wait for Select value to reflect the selection
		await waitFor(() => {
			expect(screen.getByLabelText(/provider/i)).toHaveTextContent("claude");
		});
		await user.type(screen.getByLabelText(/^model$/i), MOCK_MODEL_ID);
		await user.type(screen.getByLabelText(/input cost/i), "0.001");
		await user.type(screen.getByLabelText(/output cost/i), "0.005");
		await user.type(screen.getByLabelText(/margin/i), "3.0");
		await user.type(screen.getByLabelText(/effective date/i), "2026-05-01");
		await user.click(screen.getByRole("button", { name: /^create$/i }));

		await waitFor(() => {
			expect(mocks.mockCreatePricing).toHaveBeenCalled();
		});
	});

	it("deletes pricing entry on confirmation", async () => {
		const user = userEvent.setup();
		mocks.mockDeletePricing.mockResolvedValue(undefined);
		render(<PricingTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		const deleteButtons = screen.getAllByRole("button", { name: /delete/i });
		await user.click(deleteButtons[0]);
		await user.click(screen.getByRole("button", { name: /^confirm$/i }));
		await waitFor(() => {
			expect(mocks.mockDeletePricing).toHaveBeenCalledWith("p-1");
		});
	});

	it("renders empty state when no pricing entries", async () => {
		mocks.mockFetchPricing.mockResolvedValue({ data: [] });
		render(<PricingTab />, { wrapper: Wrapper });
		await waitFor(() => {
			expect(screen.getByText(/no pricing/i)).toBeInTheDocument();
		});
	});

	it("renders error state on fetch failure", async () => {
		mocks.mockFetchPricing.mockRejectedValue(new Error("Network error"));
		render(<PricingTab />, { wrapper: Wrapper });
		await waitFor(() => {
			expect(screen.getByText(/failed/i)).toBeInTheDocument();
		});
	});
});
