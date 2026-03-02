/**
 * Tests for the Routing tab component.
 *
 * REQ-022 §11.2, §10.3: Task routing management — table display,
 * add form with provider/task_type/model, delete confirmation.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { TaskRoutingItem } from "@/types/admin";

import { RoutingTab } from "./routing-tab";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => {
	const mockFetchRouting = vi.fn();
	const mockCreateRouting = vi.fn();
	const mockDeleteRouting = vi.fn();
	return { mockFetchRouting, mockCreateRouting, mockDeleteRouting };
});

vi.mock("@/lib/api/admin", () => ({
	fetchRouting: mocks.mockFetchRouting,
	createRouting: mocks.mockCreateRouting,
	deleteRouting: mocks.mockDeleteRouting,
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
const MOCK_TASK_TYPE = "extraction";
const MOCK_MODEL = "claude-3-5-haiku-20241022";
const MOCK_DISPLAY_NAME = "Claude 3.5 Haiku";

const MOCK_ROUTING: TaskRoutingItem[] = [
	{
		id: "r-1",
		provider: "claude",
		task_type: MOCK_TASK_TYPE,
		model: MOCK_MODEL,
		model_display_name: MOCK_DISPLAY_NAME,
		created_at: MOCK_TIMESTAMP,
		updated_at: MOCK_TIMESTAMP,
	},
	{
		id: "r-2",
		provider: "claude",
		task_type: "_default",
		model: "claude-sonnet-4-20250514",
		model_display_name: "Claude Sonnet 4",
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
		expect(screen.getByText(MOCK_TASK_TYPE)).toBeInTheDocument();
	});
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
	vi.clearAllMocks();
	mocks.mockFetchRouting.mockResolvedValue({ data: MOCK_ROUTING });
});

afterEach(() => {
	cleanup();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("RoutingTab", () => {
	it("renders loading state initially", () => {
		mocks.mockFetchRouting.mockReturnValue(new Promise(() => {}));
		render(<RoutingTab />, { wrapper: Wrapper });
		expect(screen.getByTestId("routing-loading")).toBeInTheDocument();
	});

	it("renders routing table with data", async () => {
		render(<RoutingTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		expect(screen.getByText(MOCK_MODEL)).toBeInTheDocument();
		expect(screen.getByText("_default")).toBeInTheDocument();
	});

	it("displays provider column", async () => {
		render(<RoutingTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		expect(screen.getAllByText("claude")).toHaveLength(2);
	});

	it("shows model display name", async () => {
		render(<RoutingTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		expect(screen.getByText(MOCK_DISPLAY_NAME)).toBeInTheDocument();
	});

	it("renders Add Routing button", async () => {
		render(<RoutingTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		expect(
			screen.getByRole("button", { name: /add routing/i }),
		).toBeInTheDocument();
	});

	it("opens add routing dialog on button click", async () => {
		const user = userEvent.setup();
		render(<RoutingTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		await user.click(screen.getByRole("button", { name: /add routing/i }));
		expect(
			screen.getByRole("heading", { name: /add routing/i }),
		).toBeInTheDocument();
	});

	it("submits add routing form", async () => {
		const user = userEvent.setup();
		mocks.mockCreateRouting.mockResolvedValue({
			data: { ...MOCK_ROUTING[0], id: "r-3" },
		});
		render(<RoutingTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		await user.click(screen.getByRole("button", { name: /add routing/i }));

		await user.click(screen.getByLabelText(/provider/i));
		await user.click(screen.getByRole("option", { name: /claude/i }));
		await waitFor(() => {
			expect(screen.getByLabelText(/provider/i)).toHaveTextContent("claude");
		});
		await user.type(screen.getByLabelText(/task type/i), "summarization");
		await user.type(screen.getByLabelText(/^model$/i), MOCK_MODEL);
		await user.click(screen.getByRole("button", { name: /^create$/i }));

		await waitFor(() => {
			expect(mocks.mockCreateRouting).toHaveBeenCalled();
		});
	});

	it("deletes routing entry on confirmation", async () => {
		const user = userEvent.setup();
		mocks.mockDeleteRouting.mockResolvedValue(undefined);
		render(<RoutingTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		const deleteButtons = screen.getAllByRole("button", { name: /delete/i });
		await user.click(deleteButtons[0]);
		await user.click(screen.getByRole("button", { name: /^confirm$/i }));
		await waitFor(() => {
			expect(mocks.mockDeleteRouting).toHaveBeenCalledWith("r-1");
		});
	});

	it("renders empty state when no routing entries", async () => {
		mocks.mockFetchRouting.mockResolvedValue({ data: [] });
		render(<RoutingTab />, { wrapper: Wrapper });
		await waitFor(() => {
			expect(screen.getByText(/no routing/i)).toBeInTheDocument();
		});
	});

	it("renders error state on fetch failure", async () => {
		mocks.mockFetchRouting.mockRejectedValue(new Error("Network error"));
		render(<RoutingTab />, { wrapper: Wrapper });
		await waitFor(() => {
			expect(screen.getByText(/failed/i)).toBeInTheDocument();
		});
	});
});
