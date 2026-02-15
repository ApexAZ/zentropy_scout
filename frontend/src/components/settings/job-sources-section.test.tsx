/**
 * Tests for the JobSourcesSection component (§11.2).
 *
 * REQ-012 §12.2: Toggle switches to enable/disable job sources,
 * drag-and-drop reorder, source description tooltips, and
 * grayed-out styling for system-inactive sources.
 */

import {
	cleanup,
	render,
	screen,
	waitFor,
	within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SECTION_TESTID = "job-sources-section";
const LOADING_TESTID = "loading-spinner";
const SOURCE_1_TESTID = "source-item-s-1";
const SOURCE_2_TESTID = "source-item-s-2";
const PERSONA_ID = "p-1";
const JOB_SOURCES_PATH = "/job-sources";
const PREFERENCES_PATH = "/user-source-preferences";

const MOCK_LIST_META = { total: 2, page: 1, per_page: 20, total_pages: 1 };

function makeSource(id: string, overrides?: Record<string, unknown>) {
	return {
		id,
		source_name: `Source ${id}`,
		source_type: "API",
		description: `Description for source ${id}`,
		api_endpoint: null,
		is_active: true,
		display_order: 0,
		...overrides,
	};
}

function makePreference(
	id: string,
	sourceId: string,
	overrides?: Record<string, unknown>,
) {
	return {
		id,
		persona_id: PERSONA_ID,
		source_id: sourceId,
		is_enabled: true,
		display_order: null,
		...overrides,
	};
}

const MOCK_SOURCES_RESPONSE = {
	data: [
		makeSource("s-1", {
			source_name: "LinkedIn",
			description: "Professional networking platform",
			display_order: 0,
		}),
		makeSource("s-2", {
			source_name: "Indeed",
			description: "Job search engine",
			display_order: 1,
		}),
	],
	meta: MOCK_LIST_META,
};

const MOCK_PREFERENCES_RESPONSE = {
	data: [
		makePreference("pref-1", "s-1", { is_enabled: true, display_order: 0 }),
		makePreference("pref-2", "s-2", { is_enabled: false, display_order: 1 }),
	],
	meta: MOCK_LIST_META,
};

const MOCK_EMPTY_RESPONSE = {
	data: [],
	meta: { ...MOCK_LIST_META, total: 0 },
};

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
		mockApiPatch: vi.fn(),
		MockApiError,
		mockShowToast: {
			success: vi.fn(),
			error: vi.fn(),
			warning: vi.fn(),
			info: vi.fn(),
			dismiss: vi.fn(),
		},
	};
});

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
	apiPatch: mocks.mockApiPatch,
	ApiError: mocks.MockApiError,
}));

vi.mock("@/lib/toast", () => ({
	showToast: mocks.mockShowToast,
}));

vi.mock("@/hooks/use-is-mobile", () => ({
	useIsMobile: () => false,
}));

import { JobSourcesSection } from "./job-sources-section";

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

function renderSection() {
	const Wrapper = createWrapper();
	return render(
		<Wrapper>
			<JobSourcesSection personaId={PERSONA_ID} />
		</Wrapper>,
	);
}

function setupMockApi(
	sourcesResponse: unknown = MOCK_SOURCES_RESPONSE,
	preferencesResponse: unknown = MOCK_PREFERENCES_RESPONSE,
) {
	mocks.mockApiGet.mockImplementation((path: string) => {
		if (path === JOB_SOURCES_PATH) return Promise.resolve(sourcesResponse);
		if (path === PREFERENCES_PATH) return Promise.resolve(preferencesResponse);
		return Promise.resolve(MOCK_EMPTY_RESPONSE);
	});
}

beforeEach(() => {
	mocks.mockApiGet.mockReset();
	mocks.mockApiPatch.mockReset();
	Object.values(mocks.mockShowToast).forEach((fn) => fn.mockReset());
});

afterEach(() => {
	cleanup();
	vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("JobSourcesSection", () => {
	describe("loading state", () => {
		it("shows loading spinner while fetching", () => {
			mocks.mockApiGet.mockReturnValue(new Promise(() => {}));

			renderSection();

			expect(screen.getByTestId(LOADING_TESTID)).toBeInTheDocument();
		});
	});

	describe("error state", () => {
		it("shows failed state on API error", async () => {
			mocks.mockApiGet.mockRejectedValue(
				new mocks.MockApiError("NETWORK_ERROR", "Connection failed", 0),
			);

			renderSection();

			await waitFor(() => {
				expect(screen.getByRole("alert")).toBeInTheDocument();
			});
		});
	});

	describe("empty state", () => {
		it("shows empty message when no sources exist", async () => {
			setupMockApi(MOCK_EMPTY_RESPONSE, MOCK_EMPTY_RESPONSE);

			renderSection();

			await waitFor(() => {
				expect(screen.getByRole("status")).toBeInTheDocument();
			});
			expect(
				screen.getByText("No job sources", { exact: true }),
			).toBeInTheDocument();
		});
	});

	describe("rendering sources", () => {
		it("renders the section container", async () => {
			setupMockApi();

			renderSection();

			await waitFor(() => {
				expect(screen.getByTestId(SECTION_TESTID)).toBeInTheDocument();
			});
		});

		it("renders each source name", async () => {
			setupMockApi();

			renderSection();

			await waitFor(() => {
				expect(screen.getByText("LinkedIn")).toBeInTheDocument();
			});
			expect(screen.getByText("Indeed")).toBeInTheDocument();
		});

		it("renders source items with correct test IDs", async () => {
			setupMockApi();

			renderSection();

			await waitFor(() => {
				expect(screen.getByTestId(SOURCE_1_TESTID)).toBeInTheDocument();
			});
			expect(screen.getByTestId(SOURCE_2_TESTID)).toBeInTheDocument();
		});

		it("shows switch in checked state when preference is_enabled is true", async () => {
			setupMockApi();

			renderSection();

			await waitFor(() => {
				expect(screen.getByTestId(SOURCE_1_TESTID)).toBeInTheDocument();
			});

			const item1 = screen.getByTestId(SOURCE_1_TESTID);
			const switch1 = within(item1).getByRole("switch");
			expect(switch1).toHaveAttribute("data-state", "checked");
		});

		it("shows switch in unchecked state when preference is_enabled is false", async () => {
			setupMockApi();

			renderSection();

			await waitFor(() => {
				expect(screen.getByTestId(SOURCE_2_TESTID)).toBeInTheDocument();
			});

			const item2 = screen.getByTestId(SOURCE_2_TESTID);
			const switch2 = within(item2).getByRole("switch");
			expect(switch2).toHaveAttribute("data-state", "unchecked");
		});

		it("grays out inactive sources with disabled switch", async () => {
			setupMockApi({
				data: [
					makeSource("s-1", {
						source_name: "Inactive Source",
						is_active: false,
					}),
				],
				meta: { ...MOCK_LIST_META, total: 1 },
			});

			renderSection();

			await waitFor(() => {
				expect(screen.getByTestId(SOURCE_1_TESTID)).toBeInTheDocument();
			});

			const item = screen.getByTestId(SOURCE_1_TESTID);
			expect(item).toHaveClass("opacity-50");

			const switchEl = within(item).getByRole("switch");
			expect(switchEl).toBeDisabled();
		});
	});

	describe("tooltip description", () => {
		it("shows description in tooltip on hover", async () => {
			const user = userEvent.setup();
			setupMockApi();

			renderSection();

			await waitFor(() => {
				expect(screen.getByText("LinkedIn")).toBeInTheDocument();
			});

			await user.hover(screen.getByText("LinkedIn"));

			await waitFor(() => {
				expect(screen.getByRole("tooltip")).toBeInTheDocument();
			});
			expect(screen.getByRole("tooltip")).toHaveTextContent(
				"Professional networking platform",
			);
		});
	});

	describe("toggle behavior", () => {
		it("calls PATCH with is_enabled false when toggling off", async () => {
			const user = userEvent.setup();
			mocks.mockApiPatch.mockResolvedValue({ data: {} });
			setupMockApi();

			renderSection();

			await waitFor(() => {
				expect(screen.getByTestId(SOURCE_1_TESTID)).toBeInTheDocument();
			});

			const item1 = screen.getByTestId(SOURCE_1_TESTID);
			const switchEl = within(item1).getByRole("switch");
			await user.click(switchEl);

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`${PREFERENCES_PATH}/pref-1`,
					{ is_enabled: false },
				);
			});
		});

		it("calls PATCH with is_enabled true when toggling on", async () => {
			const user = userEvent.setup();
			mocks.mockApiPatch.mockResolvedValue({ data: {} });
			setupMockApi();

			renderSection();

			await waitFor(() => {
				expect(screen.getByTestId(SOURCE_2_TESTID)).toBeInTheDocument();
			});

			const item2 = screen.getByTestId(SOURCE_2_TESTID);
			const switchEl = within(item2).getByRole("switch");
			await user.click(switchEl);

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`${PREFERENCES_PATH}/pref-2`,
					{ is_enabled: true },
				);
			});
		});

		it("shows success toast after toggle", async () => {
			const user = userEvent.setup();
			mocks.mockApiPatch.mockResolvedValue({ data: {} });
			setupMockApi();

			renderSection();

			await waitFor(() => {
				expect(screen.getByTestId(SOURCE_1_TESTID)).toBeInTheDocument();
			});

			const item1 = screen.getByTestId(SOURCE_1_TESTID);
			await user.click(within(item1).getByRole("switch"));

			await waitFor(() => {
				expect(mocks.mockShowToast.success).toHaveBeenCalled();
			});
		});

		it("shows error toast on toggle failure", async () => {
			const user = userEvent.setup();
			mocks.mockApiPatch.mockRejectedValue(
				new mocks.MockApiError("SERVER_ERROR", "Internal error", 500),
			);
			setupMockApi();

			renderSection();

			await waitFor(() => {
				expect(screen.getByTestId(SOURCE_1_TESTID)).toBeInTheDocument();
			});

			const item1 = screen.getByTestId(SOURCE_1_TESTID);
			await user.click(within(item1).getByRole("switch"));

			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalled();
			});
		});
	});

	describe("reorder behavior", () => {
		it("renders list with drag handles", async () => {
			setupMockApi();

			renderSection();

			await waitFor(() => {
				expect(screen.getByTestId(SOURCE_1_TESTID)).toBeInTheDocument();
			});

			const dragHandles = screen.getAllByLabelText("Drag to reorder");
			expect(dragHandles.length).toBeGreaterThanOrEqual(2);
		});

		it("renders reorderable list with correct ARIA label", async () => {
			setupMockApi();

			renderSection();

			await waitFor(() => {
				expect(screen.getByTestId(SOURCE_1_TESTID)).toBeInTheDocument();
			});

			expect(
				screen.getByRole("list", { name: "job sources" }),
			).toBeInTheDocument();
		});
	});

	describe("sources without preferences", () => {
		it("defaults to enabled for sources with no preference", async () => {
			setupMockApi(MOCK_SOURCES_RESPONSE, MOCK_EMPTY_RESPONSE);

			renderSection();

			await waitFor(() => {
				expect(screen.getByTestId(SOURCE_1_TESTID)).toBeInTheDocument();
			});

			const item1 = screen.getByTestId(SOURCE_1_TESTID);
			const switchEl = within(item1).getByRole("switch");
			expect(switchEl).toHaveAttribute("data-state", "checked");
		});
	});

	describe("API calls", () => {
		it("fetches job sources from /job-sources", async () => {
			setupMockApi();

			renderSection();

			await waitFor(() => {
				expect(mocks.mockApiGet).toHaveBeenCalledWith(JOB_SOURCES_PATH);
			});
		});

		it("fetches preferences from /user-source-preferences", async () => {
			setupMockApi();

			renderSection();

			await waitFor(() => {
				expect(mocks.mockApiGet).toHaveBeenCalledWith(PREFERENCES_PATH);
			});
		});
	});
});
