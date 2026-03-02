/**
 * Tests for the Models tab component.
 *
 * REQ-022 §11.2: Model registry management — table display,
 * add form, toggle active, delete confirmation.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ModelRegistryItem } from "@/types/admin";

import { ModelsTab } from "./models-tab";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => {
	const mockFetchModels = vi.fn();
	const mockCreateModel = vi.fn();
	const mockUpdateModel = vi.fn();
	const mockDeleteModel = vi.fn();
	return { mockFetchModels, mockCreateModel, mockUpdateModel, mockDeleteModel };
});

vi.mock("@/lib/api/admin", () => ({
	fetchModels: mocks.mockFetchModels,
	createModel: mocks.mockCreateModel,
	updateModel: mocks.mockUpdateModel,
	deleteModel: mocks.mockDeleteModel,
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
const MOCK_DISPLAY_NAME = "Claude 3.5 Haiku";

const MOCK_MODELS: ModelRegistryItem[] = [
	{
		id: "m-1",
		provider: "claude",
		model: "claude-3-5-haiku-20241022",
		display_name: MOCK_DISPLAY_NAME,
		model_type: "llm",
		is_active: true,
		created_at: MOCK_TIMESTAMP,
		updated_at: MOCK_TIMESTAMP,
	},
	{
		id: "m-2",
		provider: "openai",
		model: "gpt-4o-mini",
		display_name: "GPT-4o Mini",
		model_type: "llm",
		is_active: false,
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
		expect(screen.getByText(MOCK_DISPLAY_NAME)).toBeInTheDocument();
	});
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
	vi.clearAllMocks();
	mocks.mockFetchModels.mockResolvedValue({ data: MOCK_MODELS });
});

afterEach(() => {
	cleanup();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ModelsTab", () => {
	it("renders loading state initially", () => {
		mocks.mockFetchModels.mockReturnValue(new Promise(() => {}));
		render(<ModelsTab />, { wrapper: Wrapper });
		expect(screen.getByTestId("models-loading")).toBeInTheDocument();
	});

	it("renders model table with data", async () => {
		render(<ModelsTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		expect(screen.getByText("GPT-4o Mini")).toBeInTheDocument();
	});

	it("displays provider column", async () => {
		render(<ModelsTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		expect(screen.getByText("claude")).toBeInTheDocument();
		expect(screen.getByText("openai")).toBeInTheDocument();
	});

	it("shows active status for active models", async () => {
		render(<ModelsTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		const rows = screen.getAllByRole("row");
		// First data row (Claude) should show Active
		expect(rows[1]).toHaveTextContent("Active");
	});

	it("shows inactive status for inactive models", async () => {
		render(<ModelsTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		const rows = screen.getAllByRole("row");
		// Second data row (GPT-4o Mini) should show Inactive
		expect(rows[2]).toHaveTextContent("Inactive");
	});

	it("renders Add Model button", async () => {
		render(<ModelsTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		expect(
			screen.getByRole("button", { name: /add model/i }),
		).toBeInTheDocument();
	});

	it("opens add model dialog on button click", async () => {
		const user = userEvent.setup();
		render(<ModelsTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		await user.click(screen.getByRole("button", { name: /add model/i }));
		expect(
			screen.getByRole("heading", { name: /add model/i }),
		).toBeInTheDocument();
	});

	it("submits add model form", async () => {
		const user = userEvent.setup();
		mocks.mockCreateModel.mockResolvedValue({
			data: {
				id: "m-3",
				provider: "gemini",
				model: "gemini-2.0-flash",
				display_name: "Gemini 2.0 Flash",
				model_type: "llm",
				is_active: true,
				created_at: MOCK_TIMESTAMP,
				updated_at: MOCK_TIMESTAMP,
			},
		});
		render(<ModelsTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		await user.click(screen.getByRole("button", { name: /add model/i }));

		await user.click(screen.getByLabelText(/provider/i));
		await user.click(screen.getByRole("option", { name: /gemini/i }));
		// Wait for Select value to reflect the selection
		await waitFor(() => {
			expect(screen.getByLabelText(/provider/i)).toHaveTextContent("gemini");
		});
		await user.type(screen.getByLabelText(/^model$/i), "gemini-2.0-flash");
		await user.type(screen.getByLabelText(/display name/i), "Gemini 2.0 Flash");
		await user.click(screen.getByLabelText(/model type/i));
		await user.click(screen.getByRole("option", { name: /llm/i }));
		// Wait for Select value to reflect the selection
		await waitFor(() => {
			expect(screen.getByLabelText(/model type/i)).toHaveTextContent("llm");
		});
		await user.click(screen.getByRole("button", { name: /^create$/i }));

		await waitFor(() => {
			expect(mocks.mockCreateModel).toHaveBeenCalledWith({
				provider: "gemini",
				model: "gemini-2.0-flash",
				display_name: "Gemini 2.0 Flash",
				model_type: "llm",
			});
		});
		// Wait for mutation onSuccess to finish (dialog closes, query invalidates)
		await waitFor(() => {
			expect(
				screen.queryByRole("heading", { name: /add model/i }),
			).not.toBeInTheDocument();
		});
	});

	it("toggles model active status", async () => {
		const user = userEvent.setup();
		mocks.mockUpdateModel.mockResolvedValue({
			data: { ...MOCK_MODELS[0], is_active: false },
		});
		render(<ModelsTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		const toggleButtons = screen.getAllByRole("button", {
			name: /toggle active/i,
		});
		await user.click(toggleButtons[0]);
		await waitFor(() => {
			expect(mocks.mockUpdateModel).toHaveBeenCalledWith("m-1", {
				is_active: false,
			});
		});
	});

	it("opens delete confirmation dialog", async () => {
		const user = userEvent.setup();
		render(<ModelsTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		const deleteButtons = screen.getAllByRole("button", { name: /delete/i });
		await user.click(deleteButtons[0]);
		expect(screen.getByText(/are you sure/i)).toBeInTheDocument();
	});

	it("deletes model on confirmation", async () => {
		const user = userEvent.setup();
		mocks.mockDeleteModel.mockResolvedValue(undefined);
		render(<ModelsTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		const deleteButtons = screen.getAllByRole("button", { name: /delete/i });
		await user.click(deleteButtons[0]);
		await user.click(screen.getByRole("button", { name: /^confirm$/i }));
		await waitFor(() => {
			expect(mocks.mockDeleteModel).toHaveBeenCalledWith("m-1");
		});
	});

	it("renders empty state when no models", async () => {
		mocks.mockFetchModels.mockResolvedValue({ data: [] });
		render(<ModelsTab />, { wrapper: Wrapper });
		await waitFor(() => {
			expect(screen.getByText(/no models/i)).toBeInTheDocument();
		});
	});

	it("renders error state on fetch failure", async () => {
		mocks.mockFetchModels.mockRejectedValue(new Error("Network error"));
		render(<ModelsTab />, { wrapper: Wrapper });
		await waitFor(() => {
			expect(screen.getByText(/failed/i)).toBeInTheDocument();
		});
	});
});
