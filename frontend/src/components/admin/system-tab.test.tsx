/**
 * Tests for the System tab component.
 *
 * REQ-022 §11.2, §10.5: System config management — table display,
 * add form, inline edit (PUT upsert), delete confirmation.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { SystemConfigItem } from "@/types/admin";

import { SystemTab } from "./system-tab";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => {
	const mockFetchConfig = vi.fn();
	const mockUpsertConfig = vi.fn();
	const mockDeleteConfig = vi.fn();
	return { mockFetchConfig, mockUpsertConfig, mockDeleteConfig };
});

vi.mock("@/lib/api/admin", () => ({
	fetchConfig: mocks.mockFetchConfig,
	upsertConfig: mocks.mockUpsertConfig,
	deleteConfig: mocks.mockDeleteConfig,
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
const MOCK_KEY = "signup_grant_credits";
const MOCK_VALUE = "0";

const MOCK_CONFIG: SystemConfigItem[] = [
	{
		key: MOCK_KEY,
		value: MOCK_VALUE,
		description: "Credits granted to new users on signup",
		updated_at: MOCK_TIMESTAMP,
	},
	{
		key: "maintenance_mode",
		value: "false",
		description: "Enable maintenance mode",
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
		expect(screen.getByText(MOCK_KEY)).toBeInTheDocument();
	});
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
	vi.clearAllMocks();
	mocks.mockFetchConfig.mockResolvedValue({ data: MOCK_CONFIG });
});

afterEach(() => {
	cleanup();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SystemTab", () => {
	it("renders loading state initially", () => {
		mocks.mockFetchConfig.mockReturnValue(new Promise(() => {}));
		render(<SystemTab />, { wrapper: Wrapper });
		expect(screen.getByTestId("system-loading")).toBeInTheDocument();
	});

	it("renders config table with data", async () => {
		render(<SystemTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		expect(screen.getByText("maintenance_mode")).toBeInTheDocument();
	});

	it("displays config values", async () => {
		render(<SystemTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		expect(screen.getByText(MOCK_VALUE)).toBeInTheDocument();
		expect(screen.getByText("false")).toBeInTheDocument();
	});

	it("shows descriptions", async () => {
		render(<SystemTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		expect(
			screen.getByText("Credits granted to new users on signup"),
		).toBeInTheDocument();
	});

	it("renders Add Config button", async () => {
		render(<SystemTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		expect(
			screen.getByRole("button", { name: /add config/i }),
		).toBeInTheDocument();
	});

	it("opens add config dialog on button click", async () => {
		const user = userEvent.setup();
		render(<SystemTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		await user.click(screen.getByRole("button", { name: /add config/i }));
		expect(
			screen.getByRole("heading", { name: /add config/i }),
		).toBeInTheDocument();
	});

	it("submits add config form", async () => {
		const user = userEvent.setup();
		mocks.mockUpsertConfig.mockResolvedValue({
			data: {
				key: "new_key",
				value: "new_value",
				description: null,
				updated_at: MOCK_TIMESTAMP,
			},
		});
		render(<SystemTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		await user.click(screen.getByRole("button", { name: /add config/i }));

		await user.type(screen.getByLabelText(/^key$/i), "new_key");
		await user.type(screen.getByLabelText(/^value$/i), "new_value");
		await user.click(screen.getByRole("button", { name: /^save$/i }));

		await waitFor(() => {
			expect(mocks.mockUpsertConfig).toHaveBeenCalledWith("new_key", {
				value: "new_value",
				description: "",
			});
		});
	});

	it("deletes config entry on confirmation", async () => {
		const user = userEvent.setup();
		mocks.mockDeleteConfig.mockResolvedValue(undefined);
		render(<SystemTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		const deleteButtons = screen.getAllByRole("button", { name: /delete/i });
		await user.click(deleteButtons[0]);
		await user.click(screen.getByRole("button", { name: /^confirm$/i }));
		await waitFor(() => {
			expect(mocks.mockDeleteConfig).toHaveBeenCalledWith(MOCK_KEY);
		});
	});

	it("renders empty state when no config entries", async () => {
		mocks.mockFetchConfig.mockResolvedValue({ data: [] });
		render(<SystemTab />, { wrapper: Wrapper });
		await waitFor(() => {
			expect(screen.getByText(/no.*config/i)).toBeInTheDocument();
		});
	});

	it("renders error state on fetch failure", async () => {
		mocks.mockFetchConfig.mockRejectedValue(new Error("Network error"));
		render(<SystemTab />, { wrapper: Wrapper });
		await waitFor(() => {
			expect(screen.getByText(/failed/i)).toBeInTheDocument();
		});
	});
});
