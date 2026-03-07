/**
 * Tests for TemplatePicker component.
 *
 * REQ-025 §6.3: Template picker UI — grid of template cards with
 * selection state, default pre-selected, fetched from GET /resume-templates.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TEMPLATE_ID_1 = "tmpl-1";
const TEMPLATE_ID_2 = "tmpl-2";
const TEMPLATES_API_PATH = "/resume-templates";

// ---------------------------------------------------------------------------
// Factories
// ---------------------------------------------------------------------------

function makeTemplate(id: string, overrides?: Record<string, unknown>) {
	return {
		id,
		name: `Template ${id}`,
		description: `Description for ${id}`,
		markdown_content: `# Template ${id}`,
		is_system: true,
		user_id: null,
		display_order: 0,
		created_at: "2026-01-01T00:00:00Z",
		updated_at: "2026-01-01T00:00:00Z",
		...overrides,
	};
}

const MOCK_TEMPLATES_RESPONSE = {
	templates: [
		makeTemplate(TEMPLATE_ID_1, {
			name: "Clean & Minimal",
			description: "A clean, minimal resume layout",
			display_order: 0,
		}),
		makeTemplate(TEMPLATE_ID_2, {
			name: "Professional",
			description: "A professional resume layout",
			display_order: 1,
		}),
	],
};

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => {
	return {
		mockApiGet: vi.fn(),
	};
});

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
}));

import { TemplatePicker } from "./template-picker";

// ---------------------------------------------------------------------------
// Setup / Teardown
// ---------------------------------------------------------------------------

function createWrapper() {
	const queryClient = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
	return function Wrapper({ children }: { children: ReactNode }) {
		return (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);
	};
}

function renderPicker(props?: { selectedId?: string; onSelect?: () => void }) {
	const Wrapper = createWrapper();
	const defaultProps = {
		selectedId: null as string | null,
		onSelect: vi.fn(),
		...props,
	};
	return {
		...render(
			<Wrapper>
				<TemplatePicker
					selectedId={defaultProps.selectedId}
					onSelect={defaultProps.onSelect}
				/>
			</Wrapper>,
		),
		onSelect: defaultProps.onSelect,
	};
}

beforeEach(() => {
	mocks.mockApiGet.mockReset();
});

afterEach(() => {
	cleanup();
	vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("TemplatePicker", () => {
	describe("loading state", () => {
		it("shows loading spinner while templates load", () => {
			mocks.mockApiGet.mockReturnValue(new Promise(() => {}));
			renderPicker();
			expect(screen.getByTestId("template-picker-loading")).toBeInTheDocument();
		});
	});

	describe("template cards", () => {
		it("renders template cards after loading", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_TEMPLATES_RESPONSE);
			renderPicker();
			await waitFor(() => {
				expect(screen.getByText("Clean & Minimal")).toBeInTheDocument();
			});
			expect(screen.getByText("Professional")).toBeInTheDocument();
		});

		it("displays template descriptions", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_TEMPLATES_RESPONSE);
			renderPicker();
			await waitFor(() => {
				expect(
					screen.getByText("A clean, minimal resume layout"),
				).toBeInTheDocument();
			});
		});

		it("fetches templates from /resume-templates", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_TEMPLATES_RESPONSE);
			renderPicker();
			await waitFor(() => {
				expect(mocks.mockApiGet).toHaveBeenCalledWith(TEMPLATES_API_PATH);
			});
		});
	});

	describe("selection", () => {
		it("highlights the selected template card", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_TEMPLATES_RESPONSE);
			renderPicker({ selectedId: TEMPLATE_ID_1 });
			await waitFor(() => {
				expect(screen.getByText("Clean & Minimal")).toBeInTheDocument();
			});
			const selectedCard = screen.getByTestId(`template-card-${TEMPLATE_ID_1}`);
			expect(selectedCard).toHaveAttribute("aria-pressed", "true");
		});

		it("does not highlight unselected template cards", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_TEMPLATES_RESPONSE);
			renderPicker({ selectedId: TEMPLATE_ID_1 });
			await waitFor(() => {
				expect(screen.getByText("Professional")).toBeInTheDocument();
			});
			const unselectedCard = screen.getByTestId(
				`template-card-${TEMPLATE_ID_2}`,
			);
			expect(unselectedCard).toHaveAttribute("aria-pressed", "false");
		});

		it("calls onSelect when a template card is clicked", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue(MOCK_TEMPLATES_RESPONSE);
			const { onSelect } = renderPicker();
			await waitFor(() => {
				expect(screen.getByText("Professional")).toBeInTheDocument();
			});
			await user.click(screen.getByTestId(`template-card-${TEMPLATE_ID_2}`));
			expect(onSelect).toHaveBeenCalledWith(TEMPLATE_ID_2);
		});
	});

	describe("empty state", () => {
		it("shows message when no templates are available", async () => {
			mocks.mockApiGet.mockResolvedValue({ templates: [] });
			renderPicker();
			await waitFor(() => {
				expect(screen.getByText(/no templates available/i)).toBeInTheDocument();
			});
		});
	});
});
