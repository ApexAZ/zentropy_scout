/**
 * Tests for the certification step component.
 *
 * REQ-012 §6.3.6: Certifications form with skip option. Skippable step —
 * 0 entries is valid. Fields: certification_name, issuing_organization,
 * date_obtained (required), expiration_date, credential_id, verification_url
 * (optional). "Does not expire" checkbox nulls expiration_date.
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

import type { Certification } from "@/types/persona";

import { CertificationStep } from "./certification-step";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_PERSONA_ID = "00000000-0000-4000-a000-000000000001";
const GENERIC_ERROR_TEXT = "Failed to save. Please try again.";

const MOCK_CERT_1: Certification = {
	id: "cert-001",
	persona_id: DEFAULT_PERSONA_ID,
	certification_name: "AWS Solutions Architect",
	issuing_organization: "Amazon Web Services",
	date_obtained: "2023-06-15",
	expiration_date: "2026-06-15",
	credential_id: "ABC-123",
	verification_url: "https://aws.amazon.com/verify/ABC-123",
	display_order: 0,
};

const MOCK_CERT_2: Certification = {
	id: "cert-002",
	persona_id: DEFAULT_PERSONA_ID,
	certification_name: "PMP",
	issuing_organization: "PMI",
	date_obtained: "2021-03-01",
	expiration_date: null,
	credential_id: null,
	verification_url: null,
	display_order: 1,
};

const MOCK_LIST_RESPONSE = {
	data: [MOCK_CERT_1, MOCK_CERT_2],
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
		mockNext: vi.fn(),
		mockBack: vi.fn(),
		mockSkip: vi.fn(),
	};
});

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
	apiPost: mocks.mockApiPost,
	apiPatch: mocks.mockApiPatch,
	apiDelete: mocks.mockApiDelete,
	ApiError: mocks.MockApiError,
}));

vi.mock("@/lib/onboarding-provider", () => ({
	useOnboarding: () => ({
		personaId: DEFAULT_PERSONA_ID,
		next: mocks.mockNext,
		back: mocks.mockBack,
		skip: mocks.mockSkip,
	}),
}));

// Mock ReorderableList to avoid DnD complexity in jsdom
let capturedOnReorder: ((items: Certification[]) => void) | null = null;

vi.mock("@/components/ui/reorderable-list", () => ({
	ReorderableList: ({
		items,
		renderItem,
		onReorder,
		label,
	}: {
		items: Certification[];
		renderItem: (
			item: Certification,
			dragHandle: React.ReactNode | null,
		) => React.ReactNode;
		onReorder: (items: Certification[]) => void;
		label: string;
	}) => {
		capturedOnReorder = onReorder;
		return (
			<div aria-label={label} data-testid="reorderable-list">
				{items.map((item) => (
					<div key={item.id} data-testid={`entry-${item.id}`}>
						{renderItem(item, null)}
					</div>
				))}
			</div>
		);
	},
}));

// Mock Radix Checkbox since jsdom doesn't support data-state reliably
vi.mock("@/components/ui/checkbox", () => ({
	Checkbox: ({
		checked,
		onCheckedChange,
		id,
		...props
	}: {
		checked?: boolean;
		onCheckedChange?: (checked: boolean) => void;
		id?: string;
		"aria-label"?: string;
		disabled?: boolean;
	}) => (
		<input
			type="checkbox"
			checked={checked ?? false}
			onChange={(e) => onCheckedChange?.(e.target.checked)}
			id={id}
			role="checkbox"
			{...props}
		/>
	),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function renderAndWaitForLoad() {
	const user = userEvent.setup();
	render(<CertificationStep />);
	await waitFor(() => {
		expect(
			screen.queryByTestId("loading-certifications"),
		).not.toBeInTheDocument();
	});
	return user;
}

async function fillCertificationForm(
	user: ReturnType<typeof userEvent.setup>,
	overrides?: Partial<{
		certificationName: string;
		issuingOrganization: string;
		dateObtained: string;
		expirationDate: string;
		credentialId: string;
		verificationUrl: string;
		doesNotExpire: boolean;
	}>,
) {
	const values = {
		certificationName: "AWS Solutions Architect",
		issuingOrganization: "Amazon Web Services",
		dateObtained: "2023-06-15",
		...overrides,
	};

	await user.type(
		screen.getByLabelText(/certification name/i),
		values.certificationName,
	);
	await user.type(
		screen.getByLabelText(/issuing organization/i),
		values.issuingOrganization,
	);
	// Date input — use fireEvent for type="date" since userEvent.type
	// doesn't reliably fill date inputs in jsdom
	const dateInput = screen.getByLabelText(/date obtained/i);
	await user.clear(dateInput);
	await user.type(dateInput, values.dateObtained);

	if (values.doesNotExpire) {
		await user.click(screen.getByRole("checkbox"));
	}

	if (values.expirationDate && !values.doesNotExpire) {
		const expInput = screen.getByLabelText(/expiration date/i);
		await user.clear(expInput);
		await user.type(expInput, values.expirationDate);
	}

	if (values.credentialId) {
		await user.type(
			screen.getByLabelText(/credential id/i),
			values.credentialId,
		);
	}

	if (values.verificationUrl) {
		await user.type(
			screen.getByLabelText(/verification url/i),
			values.verificationUrl,
		);
	}
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

describe("CertificationStep", () => {
	beforeEach(() => {
		mocks.mockApiGet.mockReset();
		mocks.mockApiPost.mockReset();
		mocks.mockApiPatch.mockReset();
		mocks.mockApiDelete.mockReset();
		mocks.mockNext.mockReset();
		mocks.mockBack.mockReset();
		mocks.mockSkip.mockReset();
		capturedOnReorder = null;
	});

	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	// -----------------------------------------------------------------------
	// Rendering & loading
	// -----------------------------------------------------------------------

	describe("rendering", () => {
		it("shows loading spinner while fetching certifications", () => {
			mocks.mockApiGet.mockReturnValue(new Promise(() => {}));
			render(<CertificationStep />);

			expect(screen.getByTestId("loading-certifications")).toBeInTheDocument();
		});

		it("renders title and description after loading", async () => {
			mocks.mockApiGet.mockResolvedValueOnce(MOCK_EMPTY_LIST_RESPONSE);
			await renderAndWaitForLoad();

			expect(screen.getByText("Certifications")).toBeInTheDocument();
		});

		it("fetches certifications from correct endpoint", async () => {
			mocks.mockApiGet.mockResolvedValueOnce(MOCK_EMPTY_LIST_RESPONSE);
			await renderAndWaitForLoad();

			expect(mocks.mockApiGet).toHaveBeenCalledWith(
				`/personas/${DEFAULT_PERSONA_ID}/certifications`,
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

		it("shows skip prompt when no entries exist", async () => {
			await renderAndWaitForLoad();

			expect(
				screen.getByText(/professional certifications/i),
			).toBeInTheDocument();
		});

		it("shows Add certification button", async () => {
			await renderAndWaitForLoad();

			expect(
				screen.getByRole("button", { name: /add certification/i }),
			).toBeInTheDocument();
		});

		it("shows Skip button", async () => {
			await renderAndWaitForLoad();

			expect(screen.getByRole("button", { name: /skip/i })).toBeInTheDocument();
		});

		it("enables Next button when no entries exist (skippable)", async () => {
			await renderAndWaitForLoad();

			expect(screen.getByTestId("next-button")).toBeEnabled();
		});
	});

	// -----------------------------------------------------------------------
	// Card display
	// -----------------------------------------------------------------------

	describe("card display", () => {
		beforeEach(() => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
		});

		it("renders certification cards for each entry", async () => {
			await renderAndWaitForLoad();

			expect(screen.getByText("AWS Solutions Architect")).toBeInTheDocument();
			expect(screen.getByText("PMP")).toBeInTheDocument();
		});

		it("shows issuing organization on cards", async () => {
			await renderAndWaitForLoad();

			expect(screen.getByText("Amazon Web Services")).toBeInTheDocument();
			expect(screen.getByText("PMI")).toBeInTheDocument();
		});

		it("shows expiration date when present", async () => {
			await renderAndWaitForLoad();

			expect(screen.getByText(/2026-06-15/)).toBeInTheDocument();
		});

		it("shows 'Does not expire' when expiration_date is null", async () => {
			await renderAndWaitForLoad();

			expect(screen.getByText(/does not expire/i)).toBeInTheDocument();
		});

		it("shows edit and delete buttons on each card", async () => {
			await renderAndWaitForLoad();

			const editButtons = screen.getAllByRole("button", { name: /edit/i });
			const deleteButtons = screen.getAllByRole("button", {
				name: /delete/i,
			});

			expect(editButtons.length).toBeGreaterThanOrEqual(2);
			expect(deleteButtons.length).toBeGreaterThanOrEqual(2);
		});

		it("hides skip button when entries exist", async () => {
			await renderAndWaitForLoad();

			expect(
				screen.queryByRole("button", { name: /skip/i }),
			).not.toBeInTheDocument();
		});

		it("renders verification URL as an external link", async () => {
			await renderAndWaitForLoad();

			const verifyLink = screen.getByRole("link", { name: /verify/i });
			expect(verifyLink).toHaveAttribute(
				"href",
				"https://aws.amazon.com/verify/ABC-123",
			);
			expect(verifyLink).toHaveAttribute("target", "_blank");
			expect(verifyLink).toHaveAttribute("rel", "noopener noreferrer");
		});
	});

	// -----------------------------------------------------------------------
	// Add certification flow
	// -----------------------------------------------------------------------

	describe("add certification flow", () => {
		beforeEach(() => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_LIST_RESPONSE);
		});

		it("shows form when Add certification is clicked", async () => {
			const user = await renderAndWaitForLoad();

			await user.click(
				screen.getByRole("button", { name: /add certification/i }),
			);

			expect(screen.getByTestId("certification-form")).toBeInTheDocument();
		});

		it("submits new certification via POST and shows card", async () => {
			const newEntry: Certification = {
				id: "cert-new",
				persona_id: DEFAULT_PERSONA_ID,
				certification_name: "AWS Solutions Architect",
				issuing_organization: "Amazon Web Services",
				date_obtained: "2023-06-15",
				expiration_date: null,
				credential_id: null,
				verification_url: null,
				display_order: 0,
			};
			mocks.mockApiPost.mockResolvedValueOnce({ data: newEntry });

			const user = await renderAndWaitForLoad();
			await user.click(
				screen.getByRole("button", { name: /add certification/i }),
			);
			await fillCertificationForm(user, { doesNotExpire: true });
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}/certifications`,
					expect.objectContaining({
						certification_name: "AWS Solutions Architect",
						issuing_organization: "Amazon Web Services",
						expiration_date: null,
					}),
				);
			});
		});

		it("cancels add form and returns to list", async () => {
			const user = await renderAndWaitForLoad();

			await user.click(
				screen.getByRole("button", { name: /add certification/i }),
			);
			expect(screen.getByTestId("certification-form")).toBeInTheDocument();

			await user.click(screen.getByRole("button", { name: /cancel/i }));
			expect(
				screen.queryByTestId("certification-form"),
			).not.toBeInTheDocument();
		});

		it("shows error on failed POST", async () => {
			mocks.mockApiPost.mockRejectedValueOnce(new Error("Network error"));

			const user = await renderAndWaitForLoad();
			await user.click(
				screen.getByRole("button", { name: /add certification/i }),
			);
			await fillCertificationForm(user, { doesNotExpire: true });
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(screen.getByText(GENERIC_ERROR_TEXT)).toBeInTheDocument();
			});
		});
	});

	// -----------------------------------------------------------------------
	// "Does not expire" toggle
	// -----------------------------------------------------------------------

	describe("does not expire toggle", () => {
		beforeEach(() => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_LIST_RESPONSE);
		});

		it("disables expiration date field when checkbox is checked", async () => {
			const user = await renderAndWaitForLoad();

			await user.click(
				screen.getByRole("button", { name: /add certification/i }),
			);

			const expirationInput = screen.getByLabelText(/expiration date/i);
			expect(expirationInput).toBeEnabled();

			await user.click(screen.getByRole("checkbox"));

			expect(expirationInput).toBeDisabled();
		});

		it("sends null expiration_date when checkbox is checked", async () => {
			const newEntry: Certification = {
				id: "cert-new",
				persona_id: DEFAULT_PERSONA_ID,
				certification_name: "PMP",
				issuing_organization: "PMI",
				date_obtained: "2023-01-01",
				expiration_date: null,
				credential_id: null,
				verification_url: null,
				display_order: 0,
			};
			mocks.mockApiPost.mockResolvedValueOnce({ data: newEntry });

			const user = await renderAndWaitForLoad();
			await user.click(
				screen.getByRole("button", { name: /add certification/i }),
			);
			await fillCertificationForm(user, {
				certificationName: "PMP",
				issuingOrganization: "PMI",
				dateObtained: "2023-01-01",
				doesNotExpire: true,
			});
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith(
					expect.any(String),
					expect.objectContaining({
						expiration_date: null,
					}),
				);
			});
		});

		it("pre-checks checkbox when editing cert with null expiration_date", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);

			const user = await renderAndWaitForLoad();

			// MOCK_CERT_2 has null expiration_date
			const entry2 = screen.getByTestId("entry-cert-002");
			await user.click(within(entry2).getByRole("button", { name: /edit/i }));

			expect(screen.getByRole("checkbox")).toBeChecked();
		});
	});

	// -----------------------------------------------------------------------
	// Edit certification flow
	// -----------------------------------------------------------------------

	describe("edit certification flow", () => {
		beforeEach(() => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
		});

		it("opens form with pre-filled data when edit is clicked", async () => {
			const user = await renderAndWaitForLoad();

			const entry1 = screen.getByTestId("entry-cert-001");
			await user.click(within(entry1).getByRole("button", { name: /edit/i }));

			const form = screen.getByTestId("certification-form");
			expect(
				within(form).getByDisplayValue("AWS Solutions Architect"),
			).toBeInTheDocument();
			expect(
				within(form).getByDisplayValue("Amazon Web Services"),
			).toBeInTheDocument();
		});

		it("submits updated certification via PATCH", async () => {
			mocks.mockApiPatch.mockResolvedValueOnce({
				data: {
					...MOCK_CERT_1,
					certification_name: "AWS Architect Professional",
				},
			});

			const user = await renderAndWaitForLoad();
			const entry1 = screen.getByTestId("entry-cert-001");
			await user.click(within(entry1).getByRole("button", { name: /edit/i }));

			const nameInput = screen.getByDisplayValue("AWS Solutions Architect");
			await user.clear(nameInput);
			await user.type(nameInput, "AWS Architect Professional");
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}/certifications/cert-001`,
					expect.objectContaining({
						certification_name: "AWS Architect Professional",
					}),
				);
			});
		});

		it("cancels edit without saving changes", async () => {
			const user = await renderAndWaitForLoad();
			const entry1 = screen.getByTestId("entry-cert-001");
			await user.click(within(entry1).getByRole("button", { name: /edit/i }));

			await user.click(screen.getByRole("button", { name: /cancel/i }));

			expect(mocks.mockApiPatch).not.toHaveBeenCalled();
			expect(screen.getByText("AWS Solutions Architect")).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Delete flow
	// -----------------------------------------------------------------------

	describe("delete flow", () => {
		beforeEach(() => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
		});

		it("shows confirmation dialog when delete is clicked", async () => {
			const user = await renderAndWaitForLoad();

			const entry1 = screen.getByTestId("entry-cert-001");
			await user.click(within(entry1).getByRole("button", { name: /delete/i }));

			expect(screen.getByText(/are you sure/i)).toBeInTheDocument();
		});

		it("deletes certification on confirm and removes card", async () => {
			mocks.mockApiDelete.mockResolvedValueOnce(undefined);

			const user = await renderAndWaitForLoad();
			const entry1 = screen.getByTestId("entry-cert-001");
			await user.click(within(entry1).getByRole("button", { name: /delete/i }));

			const dialog = screen.getByRole("alertdialog");
			const confirmButton = within(dialog).getByRole("button", {
				name: /^delete$/i,
			});
			await user.click(confirmButton);

			await waitFor(() => {
				expect(mocks.mockApiDelete).toHaveBeenCalledWith(
					`/personas/${DEFAULT_PERSONA_ID}/certifications/cert-001`,
				);
			});
			expect(
				screen.queryByText("AWS Solutions Architect"),
			).not.toBeInTheDocument();
		});

		it("keeps card when delete API call fails", async () => {
			mocks.mockApiDelete.mockRejectedValueOnce(new Error("Network error"));

			const user = await renderAndWaitForLoad();
			const entry1 = screen.getByTestId("entry-cert-001");
			await user.click(within(entry1).getByRole("button", { name: /delete/i }));

			const dialog = screen.getByRole("alertdialog");
			const confirmButton = within(dialog).getByRole("button", {
				name: /^delete$/i,
			});
			await user.click(confirmButton);

			await waitFor(() => {
				expect(mocks.mockApiDelete).toHaveBeenCalledTimes(1);
			});
			// Card should still be visible after failed delete
			expect(screen.getByTestId("entry-cert-001")).toBeInTheDocument();
		});

		it("shows error message in dialog when delete fails", async () => {
			mocks.mockApiDelete.mockRejectedValueOnce(new Error("Network error"));

			const user = await renderAndWaitForLoad();
			const entry1 = screen.getByTestId("entry-cert-001");
			await user.click(within(entry1).getByRole("button", { name: /delete/i }));

			const dialog = screen.getByRole("alertdialog");
			await user.click(
				within(dialog).getByRole("button", { name: /^delete$/i }),
			);

			await waitFor(() => {
				expect(screen.getByText(/failed to delete/i)).toBeInTheDocument();
			});
		});

		it("cancels delete without removing card", async () => {
			const user = await renderAndWaitForLoad();
			const entry1 = screen.getByTestId("entry-cert-001");
			await user.click(within(entry1).getByRole("button", { name: /delete/i }));

			await user.click(screen.getByRole("button", { name: /cancel/i }));

			expect(mocks.mockApiDelete).not.toHaveBeenCalled();
			expect(screen.getByText("AWS Solutions Architect")).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Reordering
	// -----------------------------------------------------------------------

	describe("reordering", () => {
		it("calls PATCH to update display_order after reorder", async () => {
			mocks.mockApiGet.mockResolvedValue(MOCK_LIST_RESPONSE);
			mocks.mockApiPatch.mockResolvedValue({ data: {} });

			await renderAndWaitForLoad();

			expect(capturedOnReorder).not.toBeNull();

			// Simulate reorder: swap entries
			capturedOnReorder!([MOCK_CERT_2, MOCK_CERT_1]);

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalled();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Navigation
	// -----------------------------------------------------------------------

	describe("navigation", () => {
		it("calls next() when Next is clicked", async () => {
			mocks.mockApiGet.mockResolvedValueOnce(MOCK_LIST_RESPONSE);
			const user = await renderAndWaitForLoad();

			await user.click(screen.getByTestId("next-button"));

			expect(mocks.mockNext).toHaveBeenCalledTimes(1);
		});

		it("calls back() when Back is clicked", async () => {
			mocks.mockApiGet.mockResolvedValueOnce(MOCK_LIST_RESPONSE);
			const user = await renderAndWaitForLoad();

			await user.click(screen.getByTestId("back-button"));

			expect(mocks.mockBack).toHaveBeenCalledTimes(1);
		});

		it("calls skip() when Skip is clicked", async () => {
			mocks.mockApiGet.mockResolvedValueOnce(MOCK_EMPTY_LIST_RESPONSE);
			const user = await renderAndWaitForLoad();

			await user.click(screen.getByRole("button", { name: /skip/i }));

			expect(mocks.mockSkip).toHaveBeenCalledTimes(1);
		});

		it("allows Next with zero entries (skippable step)", async () => {
			mocks.mockApiGet.mockResolvedValueOnce(MOCK_EMPTY_LIST_RESPONSE);
			const user = await renderAndWaitForLoad();

			await user.click(screen.getByTestId("next-button"));

			expect(mocks.mockNext).toHaveBeenCalledTimes(1);
		});
	});

	// -----------------------------------------------------------------------
	// Form validation
	// -----------------------------------------------------------------------

	describe("form validation", () => {
		beforeEach(() => {
			mocks.mockApiGet.mockResolvedValue(MOCK_EMPTY_LIST_RESPONSE);
		});

		it("shows validation errors for empty required fields", async () => {
			const user = await renderAndWaitForLoad();

			await user.click(
				screen.getByRole("button", { name: /add certification/i }),
			);
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(
					screen.getAllByText(/is required/i).length,
				).toBeGreaterThanOrEqual(1);
			});
			expect(mocks.mockApiPost).not.toHaveBeenCalled();
		});

		it("validates verification URL format", async () => {
			const user = await renderAndWaitForLoad();

			await user.click(
				screen.getByRole("button", { name: /add certification/i }),
			);

			await fillCertificationForm(user, {
				doesNotExpire: true,
				verificationUrl: "not-a-url",
			});
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(
					screen.getAllByText(/valid url.*https?/i).length,
				).toBeGreaterThanOrEqual(1);
			});
			expect(mocks.mockApiPost).not.toHaveBeenCalled();
		});
	});
});
