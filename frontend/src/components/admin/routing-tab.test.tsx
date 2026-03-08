/**
 * Tests for the Routing tab component.
 *
 * REQ-028 §6.1: Fixed 10-row editable routing table — one row per TaskType,
 * inline provider/model dropdowns, no add/delete buttons.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ModelRegistryItem, TaskRoutingItem } from "@/types/admin";

import { RoutingTab } from "./routing-tab";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => {
	const mockFetchRouting = vi.fn();
	const mockFetchModels = vi.fn();
	const mockCreateRouting = vi.fn();
	const mockUpdateRouting = vi.fn();
	const mockDeleteRouting = vi.fn();
	const mockTestRouting = vi.fn();
	return {
		mockFetchRouting,
		mockFetchModels,
		mockCreateRouting,
		mockUpdateRouting,
		mockDeleteRouting,
		mockTestRouting,
	};
});

vi.mock("@/lib/api/admin", () => ({
	fetchRouting: mocks.mockFetchRouting,
	fetchModels: mocks.mockFetchModels,
	createRouting: mocks.mockCreateRouting,
	updateRouting: mocks.mockUpdateRouting,
	deleteRouting: mocks.mockDeleteRouting,
	testRouting: mocks.mockTestRouting,
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
const MODEL_SONNET = "claude-sonnet-4-20250514";
const MODEL_HAIKU = "claude-3-5-haiku-20241022";
const MODEL_GPT4O = "gpt-4o";
const EXTRACTION_ROUTING_ID = "r-1";
const EXTRACTION_TASK_TYPE = "extraction";
const TEST_BTN_EXTRACTION = "test-btn-extraction";
const TEST_RESULT_EXTRACTION = "test-result-extraction";

function mockModel(
	id: string,
	provider: string,
	model: string,
	displayName: string,
	modelType = "llm",
): ModelRegistryItem {
	return {
		id,
		provider,
		model,
		display_name: displayName,
		model_type: modelType,
		is_active: true,
		created_at: MOCK_TIMESTAMP,
		updated_at: MOCK_TIMESTAMP,
	};
}

function mockTestResponse(latencyMs = 250) {
	return {
		data: {
			provider: "claude",
			model: MODEL_HAIKU,
			response: "Hello",
			latency_ms: latencyMs,
			input_tokens: 10,
			output_tokens: 5,
		},
	};
}

const MOCK_MODELS: ModelRegistryItem[] = [
	mockModel("m-1", "claude", MODEL_SONNET, "Claude Sonnet 4"),
	mockModel("m-2", "claude", MODEL_HAIKU, "Claude 3.5 Haiku"),
	mockModel("m-3", "openai", MODEL_GPT4O, "GPT-4o"),
	mockModel(
		"m-4",
		"openai",
		"text-embedding-3-small",
		"Text Embedding 3 Small",
		"embedding",
	),
	mockModel("m-5", "gemini", "gemini-2.0-flash", "Gemini 2.0 Flash"),
];

const MOCK_ROUTING: TaskRoutingItem[] = [
	{
		id: EXTRACTION_ROUTING_ID,
		provider: "claude",
		task_type: EXTRACTION_TASK_TYPE,
		model: MODEL_HAIKU,
		model_display_name: "Claude 3.5 Haiku",
		created_at: MOCK_TIMESTAMP,
		updated_at: MOCK_TIMESTAMP,
	},
	{
		id: "r-2",
		provider: "claude",
		task_type: "chat_response",
		model: MODEL_SONNET,
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

async function waitForTableLoaded() {
	await waitFor(() => {
		expect(screen.getByText("Extraction")).toBeInTheDocument();
	});
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
	vi.clearAllMocks();
	mocks.mockFetchRouting.mockResolvedValue({ data: MOCK_ROUTING });
	mocks.mockFetchModels.mockResolvedValue({ data: MOCK_MODELS });
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

	it("renders error state on fetch failure", async () => {
		mocks.mockFetchRouting.mockRejectedValue(new Error("Network error"));
		render(<RoutingTab />, { wrapper: Wrapper });
		await waitFor(() => {
			expect(screen.getByText(/failed/i)).toBeInTheDocument();
		});
	});

	it("renders all 10 task type rows", async () => {
		render(<RoutingTab />, { wrapper: Wrapper });
		await waitForTableLoaded();
		const expectedLabels = [
			"Chat Response",
			"Onboarding",
			"Skill Extraction",
			"Extraction",
			"Ghost Detection",
			"Score Rationale",
			"Cover Letter",
			"Resume Tailoring",
			"Story Selection",
			"Resume Parsing",
		];
		for (const label of expectedLabels) {
			expect(screen.getByText(label)).toBeInTheDocument();
		}
	});

	it("shows configured provider and model for existing routing entries", async () => {
		render(<RoutingTab />, { wrapper: Wrapper });
		await waitForTableLoaded();
		const providerTrigger = screen.getByTestId("provider-select-extraction");
		expect(providerTrigger).toHaveTextContent("claude");
		const modelTrigger = screen.getByTestId("model-select-extraction");
		expect(modelTrigger).toHaveTextContent("Claude 3.5 Haiku");
	});

	it("shows placeholder for unconfigured rows", async () => {
		render(<RoutingTab />, { wrapper: Wrapper });
		await waitForTableLoaded();
		const providerTrigger = screen.getByTestId(
			"provider-select-skill_extraction",
		);
		expect(providerTrigger).toHaveTextContent("Select provider");
	});

	it("disables model dropdown when no provider selected", async () => {
		render(<RoutingTab />, { wrapper: Wrapper });
		await waitForTableLoaded();
		const modelTrigger = screen.getByTestId("model-select-skill_extraction");
		expect(modelTrigger).toBeDisabled();
	});

	it("shows models filtered by provider in model dropdown", async () => {
		const user = userEvent.setup();
		render(<RoutingTab />, { wrapper: Wrapper });
		await waitForTableLoaded();
		// Extraction is configured with claude — model dropdown shows claude models
		await user.click(screen.getByTestId("model-select-extraction"));
		expect(
			screen.getByRole("option", { name: /Claude Sonnet 4/i }),
		).toBeInTheDocument();
		expect(
			screen.getByRole("option", { name: /Claude 3.5 Haiku/i }),
		).toBeInTheDocument();
		// Should NOT show openai or gemini models
		expect(
			screen.queryByRole("option", { name: /GPT-4o/i }),
		).not.toBeInTheDocument();
		// Should NOT show embedding models
		expect(
			screen.queryByRole("option", { name: /Text Embedding/i }),
		).not.toBeInTheDocument();
	});

	it("updates routing via PATCH when model changes on configured row", async () => {
		const user = userEvent.setup();
		mocks.mockUpdateRouting.mockResolvedValue({
			data: { ...MOCK_ROUTING[0], model: MODEL_SONNET },
		});
		render(<RoutingTab />, { wrapper: Wrapper });
		await waitForTableLoaded();
		// Change model for extraction row (currently haiku -> sonnet)
		await user.click(screen.getByTestId("model-select-extraction"));
		await user.click(screen.getByRole("option", { name: /Claude Sonnet 4/i }));
		await waitFor(() => {
			expect(mocks.mockUpdateRouting).toHaveBeenCalledWith(
				EXTRACTION_ROUTING_ID,
				{ model: MODEL_SONNET },
			);
		});
	});

	it("creates routing when selecting provider and model on unconfigured row", async () => {
		const user = userEvent.setup();
		mocks.mockCreateRouting.mockResolvedValue({ data: {} });
		render(<RoutingTab />, { wrapper: Wrapper });
		await waitForTableLoaded();
		// Select provider for unconfigured row
		await user.click(screen.getByTestId("provider-select-skill_extraction"));
		await user.click(screen.getByRole("option", { name: /openai/i }));
		// Now select model
		await user.click(screen.getByTestId("model-select-skill_extraction"));
		await user.click(screen.getByRole("option", { name: /GPT-4o/i }));
		await waitFor(() => {
			expect(mocks.mockCreateRouting).toHaveBeenCalledWith({
				provider: "openai",
				task_type: "skill_extraction",
				model: MODEL_GPT4O,
			});
		});
	});

	it("deletes and recreates routing when provider changes on configured row", async () => {
		const user = userEvent.setup();
		mocks.mockDeleteRouting.mockResolvedValue(undefined);
		mocks.mockCreateRouting.mockResolvedValue({ data: {} });
		render(<RoutingTab />, { wrapper: Wrapper });
		await waitForTableLoaded();
		// Change provider for extraction (currently claude -> openai)
		await user.click(screen.getByTestId("provider-select-extraction"));
		await user.click(screen.getByRole("option", { name: /openai/i }));
		// Select new model
		await user.click(screen.getByTestId("model-select-extraction"));
		await user.click(screen.getByRole("option", { name: /GPT-4o/i }));
		await waitFor(() => {
			expect(mocks.mockDeleteRouting).toHaveBeenCalledWith(
				EXTRACTION_ROUTING_ID,
			);
			expect(mocks.mockCreateRouting).toHaveBeenCalledWith({
				provider: "openai",
				task_type: EXTRACTION_TASK_TYPE,
				model: MODEL_GPT4O,
			});
		});
	});

	it("does not show Add Routing or delete buttons", async () => {
		render(<RoutingTab />, { wrapper: Wrapper });
		await waitForTableLoaded();
		expect(
			screen.queryByRole("button", { name: /add routing/i }),
		).not.toBeInTheDocument();
		expect(
			screen.queryByRole("button", { name: /delete/i }),
		).not.toBeInTheDocument();
	});

	// -----------------------------------------------------------------------
	// Test button (REQ-028 §6.2)
	// -----------------------------------------------------------------------

	it("renders a Test column header and test buttons for configured rows", async () => {
		render(<RoutingTab />, { wrapper: Wrapper });
		await waitForTableLoaded();
		expect(
			screen.getByRole("columnheader", { name: "Test" }),
		).toBeInTheDocument();
		// Configured rows (extraction, chat_response) should have enabled test buttons
		expect(screen.getByTestId(TEST_BTN_EXTRACTION)).toBeEnabled();
		expect(screen.getByTestId("test-btn-chat_response")).toBeEnabled();
	});

	it("disables test button for rows with no provider configured", async () => {
		render(<RoutingTab />, { wrapper: Wrapper });
		await waitForTableLoaded();
		// skill_extraction has no routing entry
		expect(screen.getByTestId("test-btn-skill_extraction")).toBeDisabled();
	});

	it("calls testRouting with task_type on test button click", async () => {
		const user = userEvent.setup();
		mocks.mockTestRouting.mockResolvedValue(mockTestResponse());
		render(<RoutingTab />, { wrapper: Wrapper });
		await waitForTableLoaded();
		await user.click(screen.getByTestId(TEST_BTN_EXTRACTION));
		await waitFor(() => {
			expect(mocks.mockTestRouting).toHaveBeenCalledWith({
				task_type: EXTRACTION_TASK_TYPE,
				prompt: "Hello, this is a routing test.",
			});
		});
	});

	it("shows success badge with latency on successful test", async () => {
		const user = userEvent.setup();
		mocks.mockTestRouting.mockResolvedValue(mockTestResponse(342.5));
		render(<RoutingTab />, { wrapper: Wrapper });
		await waitForTableLoaded();
		await user.click(screen.getByTestId(TEST_BTN_EXTRACTION));
		await waitFor(() => {
			const badge = screen.getByTestId(TEST_RESULT_EXTRACTION);
			expect(badge).toHaveTextContent("343ms");
			expect(badge.className).toMatch(/success/);
		});
	});

	it("shows error badge with message on failed test", async () => {
		const user = userEvent.setup();
		mocks.mockTestRouting.mockRejectedValue(
			new Error("Provider not configured"),
		);
		render(<RoutingTab />, { wrapper: Wrapper });
		await waitForTableLoaded();
		await user.click(screen.getByTestId(TEST_BTN_EXTRACTION));
		await waitFor(() => {
			const badge = screen.getByTestId(TEST_RESULT_EXTRACTION);
			expect(badge).toHaveTextContent("Provider not configured");
			expect(badge.className).toMatch(/destructive/);
		});
	});

	it("shows loading spinner while test is in progress", async () => {
		const user = userEvent.setup();
		mocks.mockTestRouting.mockReturnValue(new Promise(() => {}));
		render(<RoutingTab />, { wrapper: Wrapper });
		await waitForTableLoaded();
		await user.click(screen.getByTestId(TEST_BTN_EXTRACTION));
		await waitFor(() => {
			expect(screen.getByTestId("test-loading-extraction")).toBeInTheDocument();
		});
	});
});
