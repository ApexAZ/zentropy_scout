/**
 * Tests for the custom filters section component.
 *
 * REQ-012 §6.3.8: Custom non-negotiable filter CRUD — add, edit, delete.
 * Displays list of filters with cards, inline form for add/edit,
 * and confirmation dialog for delete.
 */

import {
	cleanup,
	render,
	screen,
	waitFor,
	within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { CustomNonNegotiable } from "@/types/persona";

import { CustomFiltersSection } from "./custom-filters-section";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_PERSONA_ID = "00000000-0000-4000-a000-000000000001";

const MOCK_FILTER_1: CustomNonNegotiable = {
	id: "filter-001",
	persona_id: DEFAULT_PERSONA_ID,
	filter_name: "No defense contractors",
	filter_type: "Exclude",
	filter_field: "company_name",
	filter_value: "Raytheon",
};

const MOCK_FILTER_2: CustomNonNegotiable = {
	id: "filter-002",
	persona_id: DEFAULT_PERSONA_ID,
	filter_name: "Require remote mention",
	filter_type: "Require",
	filter_field: "description",
	filter_value: "remote",
};

const MOCK_LIST_RESPONSE = {
	data: [MOCK_FILTER_1, MOCK_FILTER_2],
	meta: { total: 2, page: 1, per_page: 20 },
};

const MOCK_EMPTY_LIST_RESPONSE = {
	data: [],
	meta: { total: 0, page: 1, per_page: 20 },
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
		mockApiPost: vi.fn(),
		mockApiPatch: vi.fn(),
		mockApiDelete: vi.fn(),
		MockApiError,
	};
});

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
	apiPost: mocks.mockApiPost,
	apiPatch: mocks.mockApiPatch,
	apiDelete: mocks.mockApiDelete,
	ApiError: mocks.MockApiError,
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function renderAndWaitForLoad() {
	const user = userEvent.setup();
	render(<CustomFiltersSection personaId={DEFAULT_PERSONA_ID} />);
	await waitFor(() => {
		expect(
			screen.queryByTestId("loading-custom-filters"),
		).not.toBeInTheDocument();
	});
	return user;
}

async function fillFilterForm(
	user: ReturnType<typeof userEvent.setup>,
	overrides?: Partial<{
		filterName: string;
		filterType: string;
		filterField: string;
		filterFieldCustom: string;
		filterValue: string;
	}>,
) {
	const values = {
		filterName: "No Amazon",
		filterType: "Exclude",
		filterField: "company_name",
		filterFieldCustom: "",
		filterValue: "Amazon",
		...overrides,
	};

	await user.type(screen.getByLabelText(/filter name/i), values.filterName);
	await user.click(screen.getByRole("radio", { name: values.filterType }));
	await user.selectOptions(
		screen.getByLabelText(/field to check/i),
		values.filterField,
	);
	if (values.filterFieldCustom) {
		await user.type(
			screen.getByLabelText(/custom field name/i),
			values.filterFieldCustom,
		);
	}
	await user.type(screen.getByLabelText(/value to match/i), values.filterValue);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("CustomFiltersSection", () => {
	beforeEach(() => {
		mocks.mockApiGet.mockReset();
		mocks.mockApiPost.mockReset();
		mocks.mockApiPatch.mockReset();
		mocks.mockApiDelete.mockReset();
	});

	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	// -----------------------------------------------------------------------
	// Rendering & loading
	// -----------------------------------------------------------------------

	describe("rendering", () => {
		it("shows loading spinner while fetching filters", () => {
			mocks.mockApiGet.mockReturnValue(new Promise(() => {}));
			render(<CustomFiltersSection personaId={DEFAULT_PERSONA_ID} />);
			expect(screen.getByTestId("loading-custom-filters")).toBeInTheDocument();
		});

		it("renders section heading and add button after loading", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_LIST_RESPONSE);
			await renderAndWaitForLoad();

			expect(screen.getByText("Custom Filters")).toBeInTheDocument();
			expect(screen.getByText(/add filter/i)).toBeInTheDocument();
		});

		it("fetches custom non-negotiables on mount", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_LIST_RESPONSE);
			await renderAndWaitForLoad();

			expect(mocks.mockApiGet).toHaveBeenCalledWith(
				`/personas/${DEFAULT_PERSONA_ID}/custom-non-negotiables`,
			);
		});
	});

	// -----------------------------------------------------------------------
	// Empty state
	// -----------------------------------------------------------------------

	describe("empty state", () => {
		beforeEach(() => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_LIST_RESPONSE);
		});

		it("shows empty message when no filters exist", async () => {
			await renderAndWaitForLoad();
			expect(screen.getByText(/no custom filters yet/i)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Card display
	// -----------------------------------------------------------------------

	describe("card display", () => {
		beforeEach(() => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
		});

		it("shows filter name and type badge for each entry", async () => {
			await renderAndWaitForLoad();

			expect(screen.getByText("No defense contractors")).toBeInTheDocument();
			expect(screen.getByText("Require remote mention")).toBeInTheDocument();
			expect(screen.getByText("Exclude")).toBeInTheDocument();
			expect(screen.getByText("Require")).toBeInTheDocument();
		});

		it("shows filter field and value metadata", async () => {
			await renderAndWaitForLoad();

			expect(screen.getByText(/company_name/)).toBeInTheDocument();
			expect(screen.getByText(/Raytheon/)).toBeInTheDocument();
			// Filter 2 metadata: "description · remote"
			const filter2Card = screen.getAllByTestId("custom-filter-card")[1];
			expect(within(filter2Card).getByText(/description/)).toBeInTheDocument();
		});

		it("shows edit and delete buttons for each card", async () => {
			await renderAndWaitForLoad();

			expect(
				screen.getByLabelText(/edit no defense contractors/i),
			).toBeInTheDocument();
			expect(
				screen.getByLabelText(/delete no defense contractors/i),
			).toBeInTheDocument();
			expect(
				screen.getByLabelText(/edit require remote mention/i),
			).toBeInTheDocument();
			expect(
				screen.getByLabelText(/delete require remote mention/i),
			).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Add flow
	// -----------------------------------------------------------------------

	describe("add flow", () => {
		beforeEach(() => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_LIST_RESPONSE);
		});

		it("opens form when clicking add filter", async () => {
			const user = await renderAndWaitForLoad();
			await user.click(screen.getByText(/add filter/i));

			expect(screen.getByTestId("custom-filter-form")).toBeInTheDocument();
		});

		it("submits new filter via POST and returns to list", async () => {
			const newFilter: CustomNonNegotiable = {
				id: "filter-new",
				persona_id: DEFAULT_PERSONA_ID,
				filter_name: "No Amazon",
				filter_type: "Exclude",
				filter_field: "company_name",
				filter_value: "Amazon",
			};
			mocks.mockApiPost.mockResolvedValue({ data: newFilter });

			const user = await renderAndWaitForLoad();
			await user.click(screen.getByText(/add filter/i));
			await fillFilterForm(user);
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}/custom-non-negotiables`,
					expect.objectContaining({
						filter_name: "No Amazon",
						filter_type: "Exclude",
						filter_field: "company_name",
						filter_value: "Amazon",
					}),
				);
			});

			// Returns to list and shows the new entry
			await waitFor(() => {
				expect(
					screen.queryByTestId("custom-filter-form"),
				).not.toBeInTheDocument();
			});
			expect(screen.getByText("No Amazon")).toBeInTheDocument();
		});

		it("submits custom field name when 'Other' is selected", async () => {
			const newFilter: CustomNonNegotiable = {
				id: "filter-new",
				persona_id: DEFAULT_PERSONA_ID,
				filter_name: "Benefits check",
				filter_type: "Require",
				filter_field: "benefits",
				filter_value: "401k",
			};
			mocks.mockApiPost.mockResolvedValue({ data: newFilter });

			const user = await renderAndWaitForLoad();
			await user.click(screen.getByText(/add filter/i));
			await fillFilterForm(user, {
				filterName: "Benefits check",
				filterType: "Require",
				filterField: "other",
				filterFieldCustom: "benefits",
				filterValue: "401k",
			});
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}/custom-non-negotiables`,
					expect.objectContaining({
						filter_field: "benefits",
					}),
				);
			});
		});

		it("returns to list on cancel without saving", async () => {
			const user = await renderAndWaitForLoad();
			await user.click(screen.getByText(/add filter/i));
			expect(screen.getByTestId("custom-filter-form")).toBeInTheDocument();

			await user.click(screen.getByRole("button", { name: /cancel/i }));
			expect(
				screen.queryByTestId("custom-filter-form"),
			).not.toBeInTheDocument();
			expect(mocks.mockApiPost).not.toHaveBeenCalled();
		});

		it("shows error message on API failure", async () => {
			mocks.mockApiPost.mockRejectedValue(new Error("Network error"));

			const user = await renderAndWaitForLoad();
			await user.click(screen.getByText(/add filter/i));
			await fillFilterForm(user);
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(screen.getByTestId("submit-error")).toBeInTheDocument();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Edit flow
	// -----------------------------------------------------------------------

	describe("edit flow", () => {
		beforeEach(() => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
		});

		it("opens pre-filled form on edit click", async () => {
			const user = await renderAndWaitForLoad();
			await user.click(screen.getByLabelText(/edit no defense contractors/i));

			expect(screen.getByTestId("custom-filter-form")).toBeInTheDocument();
			expect(screen.getByLabelText(/filter name/i)).toHaveValue(
				"No defense contractors",
			);
			expect(screen.getByRole("radio", { name: "Exclude" })).toBeChecked();
			expect(screen.getByLabelText(/field to check/i)).toHaveValue(
				"company_name",
			);
			expect(screen.getByLabelText(/value to match/i)).toHaveValue("Raytheon");
		});

		it("pre-fills custom field when filter_field is not predefined", async () => {
			const customFieldFilter: CustomNonNegotiable = {
				id: "filter-003",
				persona_id: DEFAULT_PERSONA_ID,
				filter_name: "Benefits filter",
				filter_type: "Require",
				filter_field: "benefits",
				filter_value: "401k",
			};
			mocks.mockApiGet.mockResolvedValue({
				data: [customFieldFilter],
				meta: { total: 1, page: 1, per_page: 20 },
			});

			const user = await renderAndWaitForLoad();
			await user.click(screen.getByLabelText(/edit benefits filter/i));

			expect(screen.getByLabelText(/field to check/i)).toHaveValue("other");
			expect(screen.getByLabelText(/custom field name/i)).toHaveValue(
				"benefits",
			);
		});

		it("submits update via PATCH", async () => {
			const updated = { ...MOCK_FILTER_1, filter_value: "Lockheed Martin" };
			mocks.mockApiPatch.mockResolvedValue({ data: updated });

			const user = await renderAndWaitForLoad();
			await user.click(screen.getByLabelText(/edit no defense contractors/i));

			// Change filter value
			const valueInput = screen.getByLabelText(/value to match/i);
			await user.clear(valueInput);
			await user.type(valueInput, "Lockheed Martin");
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}/custom-non-negotiables/${MOCK_FILTER_1.id}`,
					expect.objectContaining({
						filter_name: "No defense contractors",
						filter_value: "Lockheed Martin",
					}),
				);
			});
		});

		it("shows error on API failure during edit", async () => {
			mocks.mockApiPatch.mockRejectedValue(new Error("Server error"));

			const user = await renderAndWaitForLoad();
			await user.click(screen.getByLabelText(/edit no defense contractors/i));
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(screen.getByTestId("submit-error")).toBeInTheDocument();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Delete flow
	// -----------------------------------------------------------------------

	describe("delete flow", () => {
		beforeEach(() => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
		});

		it("opens confirmation dialog on delete click", async () => {
			const user = await renderAndWaitForLoad();
			await user.click(screen.getByLabelText(/delete no defense contractors/i));

			const dialog = screen.getByRole("alertdialog");
			expect(
				within(dialog).getByText(/are you sure you want to delete/i),
			).toBeInTheDocument();
		});

		it("deletes filter via DELETE on confirm", async () => {
			mocks.mockApiDelete.mockResolvedValue(undefined);

			const user = await renderAndWaitForLoad();
			await user.click(screen.getByLabelText(/delete no defense contractors/i));

			const dialog = screen.getByRole("alertdialog");
			await user.click(within(dialog).getByRole("button", { name: /delete/i }));

			await waitFor(() => {
				expect(mocks.mockApiDelete).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}/custom-non-negotiables/${MOCK_FILTER_1.id}`,
				);
			});

			// Card removed from list
			await waitFor(() => {
				expect(
					screen.queryByText("No defense contractors"),
				).not.toBeInTheDocument();
			});
		});

		it("closes dialog without deleting on cancel", async () => {
			const user = await renderAndWaitForLoad();
			await user.click(screen.getByLabelText(/delete no defense contractors/i));

			const dialog = screen.getByRole("alertdialog");
			await user.click(within(dialog).getByRole("button", { name: /cancel/i }));

			await waitFor(() => {
				expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
			});
			expect(screen.getByText("No defense contractors")).toBeInTheDocument();
			expect(mocks.mockApiDelete).not.toHaveBeenCalled();
		});
	});

	// -----------------------------------------------------------------------
	// Validation
	// -----------------------------------------------------------------------

	describe("validation", () => {
		beforeEach(() => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_LIST_RESPONSE);
		});

		it("shows validation errors for empty required fields", async () => {
			const user = await renderAndWaitForLoad();
			await user.click(screen.getByText(/add filter/i));

			// Submit empty form
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				const errors = screen.getAllByText(/filter name is required/i);
				expect(errors.length).toBeGreaterThanOrEqual(1);
			});
		});

		it("requires custom field name when Other is selected", async () => {
			const user = await renderAndWaitForLoad();
			await user.click(screen.getByText(/add filter/i));

			await user.type(screen.getByLabelText(/filter name/i), "Test");
			await user.click(screen.getByRole("radio", { name: "Exclude" }));
			await user.selectOptions(
				screen.getByLabelText(/field to check/i),
				"other",
			);
			await user.type(screen.getByLabelText(/value to match/i), "test");
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				const errors = screen.getAllByText(/custom field name is required/i);
				expect(errors.length).toBeGreaterThanOrEqual(1);
			});
		});
	});

	// -----------------------------------------------------------------------
	// Fetch failure
	// -----------------------------------------------------------------------

	describe("fetch failure", () => {
		it("shows empty state when fetch fails", async () => {
			mocks.mockApiGet.mockRejectedValue(new Error("Network error"));
			await renderAndWaitForLoad();

			expect(screen.getByText(/no custom filters yet/i)).toBeInTheDocument();
		});
	});
});
