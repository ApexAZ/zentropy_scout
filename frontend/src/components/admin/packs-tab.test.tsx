/**
 * Tests for the Packs tab component.
 *
 * REQ-022 §11.2, §10.4: Credit pack management — table display,
 * price formatting, add form, delete confirmation.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { CreditPackItem } from "@/types/admin";

import { PacksTab } from "./packs-tab";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => {
	const mockFetchPacks = vi.fn();
	const mockCreatePack = vi.fn();
	const mockDeletePack = vi.fn();
	return { mockFetchPacks, mockCreatePack, mockDeletePack };
});

vi.mock("@/lib/api/admin", () => ({
	fetchPacks: mocks.mockFetchPacks,
	createPack: mocks.mockCreatePack,
	deletePack: mocks.mockDeletePack,
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
const MOCK_PACK_NAME = "Starter Pack";
const MOCK_PRICE_DISPLAY = "$5.00";

const MOCK_PACKS: CreditPackItem[] = [
	{
		id: "pk-1",
		name: MOCK_PACK_NAME,
		price_cents: 500,
		price_display: MOCK_PRICE_DISPLAY,
		credit_amount: 10000,
		stripe_price_id: null,
		display_order: 0,
		is_active: true,
		description: "Good for getting started",
		highlight_label: null,
		created_at: MOCK_TIMESTAMP,
		updated_at: MOCK_TIMESTAMP,
	},
	{
		id: "pk-2",
		name: "Pro Pack",
		price_cents: 2000,
		price_display: "$20.00",
		credit_amount: 50000,
		stripe_price_id: "price_abc123",
		display_order: 1,
		is_active: true,
		description: "For heavy users",
		highlight_label: "Best Value",
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
		expect(screen.getByText(MOCK_PACK_NAME)).toBeInTheDocument();
	});
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
	vi.clearAllMocks();
	mocks.mockFetchPacks.mockResolvedValue({ data: MOCK_PACKS });
});

afterEach(() => {
	cleanup();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("PacksTab", () => {
	it("renders loading state initially", () => {
		mocks.mockFetchPacks.mockReturnValue(new Promise(() => {}));
		render(<PacksTab />, { wrapper: Wrapper });
		expect(screen.getByTestId("packs-loading")).toBeInTheDocument();
	});

	it("renders pack table with data", async () => {
		render(<PacksTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		expect(screen.getByText("Pro Pack")).toBeInTheDocument();
	});

	it("displays formatted price", async () => {
		render(<PacksTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		expect(screen.getByText(MOCK_PRICE_DISPLAY)).toBeInTheDocument();
		expect(screen.getByText("$20.00")).toBeInTheDocument();
	});

	it("shows credit amounts", async () => {
		render(<PacksTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		expect(screen.getByText("10,000")).toBeInTheDocument();
	});

	it("shows highlight label when present", async () => {
		render(<PacksTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		expect(screen.getByText("Best Value")).toBeInTheDocument();
	});

	it("renders Add Pack button", async () => {
		render(<PacksTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		expect(
			screen.getByRole("button", { name: /add pack/i }),
		).toBeInTheDocument();
	});

	it("opens add pack dialog on button click", async () => {
		const user = userEvent.setup();
		render(<PacksTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		await user.click(screen.getByRole("button", { name: /add pack/i }));
		expect(
			screen.getByRole("heading", { name: /add pack/i }),
		).toBeInTheDocument();
	});

	it("submits add pack form", async () => {
		const user = userEvent.setup();
		mocks.mockCreatePack.mockResolvedValue({
			data: { ...MOCK_PACKS[0], id: "pk-3" },
		});
		render(<PacksTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		await user.click(screen.getByRole("button", { name: /add pack/i }));

		await user.type(screen.getByLabelText(/^name$/i), "Enterprise");
		await user.type(screen.getByLabelText(/price.*cents/i), "5000");
		await user.type(screen.getByLabelText(/credit amount/i), "100000");
		await user.click(screen.getByRole("button", { name: /^create$/i }));

		await waitFor(() => {
			expect(mocks.mockCreatePack).toHaveBeenCalled();
		});
	});

	it("deletes pack on confirmation", async () => {
		const user = userEvent.setup();
		mocks.mockDeletePack.mockResolvedValue(undefined);
		render(<PacksTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		const deleteButtons = screen.getAllByRole("button", { name: /delete/i });
		await user.click(deleteButtons[0]);
		await user.click(screen.getByRole("button", { name: /^confirm$/i }));
		await waitFor(() => {
			expect(mocks.mockDeletePack).toHaveBeenCalledWith("pk-1");
		});
	});

	it("renders empty state when no packs", async () => {
		mocks.mockFetchPacks.mockResolvedValue({ data: [] });
		render(<PacksTab />, { wrapper: Wrapper });
		await waitFor(() => {
			expect(screen.getByText(/no.*pack/i)).toBeInTheDocument();
		});
	});

	it("renders error state on fetch failure", async () => {
		mocks.mockFetchPacks.mockRejectedValue(new Error("Network error"));
		render(<PacksTab />, { wrapper: Wrapper });
		await waitFor(() => {
			expect(screen.getByText(/failed/i)).toBeInTheDocument();
		});
	});
});
