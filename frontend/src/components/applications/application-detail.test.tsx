/**
 * Tests for the ApplicationDetail component (§10.2, §10.5, §10.6).
 *
 * REQ-012 §11.2: Application detail page — header with back link,
 * job title/company, applied date, status badge, interview stage,
 * documents panel (resume, cover letter, job snapshot),
 * and editable notes section.
 * REQ-012 §11.5: Offer details card display with deadline countdown
 * and edit dialog integration.
 * REQ-012 §11.6: Rejection details card display with stage, reason,
 * feedback, and date.
 * REQ-012 §11.7: Add Event dialog integration for timeline.
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

const LOADING_TESTID = "loading-spinner";
const BACK_LINK_TESTID = "back-to-applications";
const HEADER_TESTID = "application-header";
const DOCUMENTS_TESTID = "documents-panel";
const NOTES_TESTID = "notes-section";
const OFFER_SECTION_TESTID = "offer-details-section";
const DETAIL_TESTID = "application-detail";
const REJECTION_SECTION_TESTID = "rejection-details-section";
const TIMELINE_PANEL_TESTID = "timeline-panel";

const MOCK_APP_ID = "app-1";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Returns an ISO 8601 datetime string for N days before now (UTC). */
function daysAgoIso(days: number): string {
	const d = new Date();
	d.setUTCDate(d.getUTCDate() - days);
	return d.toISOString();
}

function makeApplication(overrides?: Record<string, unknown>) {
	return {
		id: MOCK_APP_ID,
		persona_id: "p-1",
		job_posting_id: "jp-1",
		job_variant_id: "jv-1",
		cover_letter_id: "cl-1",
		submitted_resume_pdf_id: "srpdf-1",
		submitted_cover_letter_pdf_id: "sclpdf-1",
		job_snapshot: {
			title: "Scrum Master",
			company_name: "Acme Corp",
			company_url: null,
			description: "Lead agile teams.",
			requirements: null,
			salary_min: null,
			salary_max: null,
			salary_currency: null,
			location: "Austin, TX",
			work_model: "Remote",
			source_url: "https://example.com/job/123",
			captured_at: "2026-01-15T10:00:00Z",
		},
		status: "Applied",
		current_interview_stage: null,
		offer_details: null,
		rejection_details: null,
		notes: "Recruiter: Sarah (sarah@acme.com)",
		is_pinned: false,
		applied_at: daysAgoIso(3),
		status_updated_at: daysAgoIso(1),
		created_at: daysAgoIso(3),
		updated_at: daysAgoIso(1),
		archived_at: null,
		...overrides,
	};
}

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
		mockApiPost: vi.fn(),
		mockApiDelete: vi.fn(),
		mockBuildUrl: vi.fn(
			(path: string) => `http://localhost:8000/api/v1${path}`,
		),
		MockApiError,
		mockShowToast: {
			success: vi.fn(),
			error: vi.fn(),
			warning: vi.fn(),
			info: vi.fn(),
			dismiss: vi.fn(),
		},
		mockPush: vi.fn(),
		mockInvalidateQueries: vi.fn().mockResolvedValue(undefined),
	};
});

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
	apiPatch: mocks.mockApiPatch,
	apiPost: mocks.mockApiPost,
	apiDelete: mocks.mockApiDelete,
	buildUrl: mocks.mockBuildUrl,
	ApiError: mocks.MockApiError,
}));

vi.mock("@/lib/toast", () => ({
	showToast: mocks.mockShowToast,
}));

vi.mock("next/navigation", () => ({
	useRouter: () => ({ push: mocks.mockPush }),
}));

function MockLink({
	children,
	href,
	...rest
}: {
	children: ReactNode;
	href: string;
	[key: string]: unknown;
}) {
	return (
		<a href={href} {...rest}>
			{children}
		</a>
	);
}
MockLink.displayName = "MockLink";

vi.mock("next/link", () => ({
	default: MockLink,
}));

vi.mock("./application-timeline", () => ({
	ApplicationTimeline: ({
		applicationId,
		onAddEvent,
	}: {
		applicationId: string;
		onAddEvent?: () => void;
	}) => (
		<div data-testid="mock-application-timeline" data-app-id={applicationId}>
			{onAddEvent && (
				<button
					data-testid="mock-add-event-btn"
					onClick={onAddEvent}
					type="button"
				>
					Add Event
				</button>
			)}
		</div>
	),
}));

vi.mock("./add-timeline-event-dialog", () => ({
	AddTimelineEventDialog: ({
		open,
		onConfirm,
		onCancel,
	}: {
		open: boolean;
		onConfirm: (data: unknown) => void;
		onCancel: () => void;
		loading?: boolean;
	}) =>
		open ? (
			<div data-testid="mock-add-event-dialog">
				<button
					data-testid="mock-add-event-save"
					onClick={() =>
						onConfirm({
							event_type: "custom",
							event_date: "2026-02-15T10:00",
						})
					}
					type="button"
				>
					Save
				</button>
				<button
					data-testid="mock-add-event-cancel"
					onClick={onCancel}
					type="button"
				>
					Cancel
				</button>
			</div>
		) : null,
}));

vi.mock("./job-snapshot-section", () => ({
	JobSnapshotSection: ({ snapshot }: { snapshot: unknown }) => (
		<div
			data-testid="mock-job-snapshot-section"
			data-snapshot={JSON.stringify(snapshot)}
		/>
	),
}));

import { ApplicationDetail } from "./application-detail";

// ---------------------------------------------------------------------------
// Setup / Teardown
// ---------------------------------------------------------------------------

function createWrapper() {
	const queryClient = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
	queryClient.invalidateQueries = mocks.mockInvalidateQueries;
	return function Wrapper({ children }: { children: ReactNode }) {
		return (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);
	};
}

function renderDetail(applicationId = MOCK_APP_ID) {
	const Wrapper = createWrapper();
	return render(
		<Wrapper>
			<ApplicationDetail applicationId={applicationId} />
		</Wrapper>,
	);
}

beforeEach(() => {
	mocks.mockApiGet.mockReset();
	mocks.mockApiPatch.mockReset();
	mocks.mockApiPost.mockReset();
	mocks.mockApiDelete.mockReset();
	mocks.mockBuildUrl.mockReset();
	mocks.mockBuildUrl.mockImplementation(
		(path: string) => `http://localhost:8000/api/v1${path}`,
	);
	mocks.mockPush.mockReset();
	mocks.mockInvalidateQueries.mockReset().mockResolvedValue(undefined);
	Object.values(mocks.mockShowToast).forEach((fn) => fn.mockReset());
});

afterEach(() => {
	cleanup();
	vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests — Loading / Error / 404
// ---------------------------------------------------------------------------

describe("ApplicationDetail", () => {
	describe("loading and error states", () => {
		it("shows a loading spinner while fetching", () => {
			mocks.mockApiGet.mockReturnValue(new Promise(() => {}));
			renderDetail();
			expect(screen.getByTestId(LOADING_TESTID)).toBeInTheDocument();
		});

		it("shows FailedState when the API returns an error", async () => {
			mocks.mockApiGet.mockRejectedValue(new Error("Network error"));
			renderDetail();
			await waitFor(() => {
				expect(screen.getByText("Failed to load.")).toBeInTheDocument();
			});
		});

		it("shows NotFoundState for a 404 error", async () => {
			mocks.mockApiGet.mockRejectedValue(
				new mocks.MockApiError("NOT_FOUND", "Not found", 404),
			);
			renderDetail();
			await waitFor(() => {
				expect(screen.getByText(/doesn\u2019t exist/)).toBeInTheDocument();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Header
	// -----------------------------------------------------------------------

	describe("header", () => {
		it("renders a back link to /applications", async () => {
			mocks.mockApiGet.mockResolvedValue({ data: makeApplication() });
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(BACK_LINK_TESTID)).toBeInTheDocument();
			});
			const backLink = screen.getByTestId(BACK_LINK_TESTID);
			expect(backLink).toHaveAttribute("href", "/applications");
		});

		it("displays job title and company name", async () => {
			mocks.mockApiGet.mockResolvedValue({ data: makeApplication() });
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(HEADER_TESTID)).toBeInTheDocument();
			});
			expect(screen.getByText("Scrum Master")).toBeInTheDocument();
			expect(screen.getByText("Acme Corp")).toBeInTheDocument();
		});

		it("displays the applied date", async () => {
			mocks.mockApiGet.mockResolvedValue({ data: makeApplication() });
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(HEADER_TESTID)).toBeInTheDocument();
			});
			expect(screen.getByText(/3 days ago/)).toBeInTheDocument();
		});

		it("displays the status badge", async () => {
			mocks.mockApiGet.mockResolvedValue({ data: makeApplication() });
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(HEADER_TESTID)).toBeInTheDocument();
			});
			expect(screen.getByText("Applied")).toBeInTheDocument();
		});

		it("shows interview stage when status is Interviewing", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({
					status: "Interviewing",
					current_interview_stage: "Onsite",
				}),
			});
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(HEADER_TESTID)).toBeInTheDocument();
			});
			expect(screen.getByText("Onsite")).toBeInTheDocument();
		});

		it("does not show interview stage when status is not Interviewing", async () => {
			mocks.mockApiGet.mockResolvedValue({ data: makeApplication() });
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(HEADER_TESTID)).toBeInTheDocument();
			});
			expect(screen.queryByText("Phone Screen")).not.toBeInTheDocument();
			expect(screen.queryByText("Onsite")).not.toBeInTheDocument();
			expect(screen.queryByText("Final Round")).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Documents Panel
	// -----------------------------------------------------------------------

	describe("documents panel", () => {
		it("renders the documents panel", async () => {
			mocks.mockApiGet.mockResolvedValue({ data: makeApplication() });
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(DOCUMENTS_TESTID)).toBeInTheDocument();
			});
		});

		it("shows resume View and Download links when pdf exists", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({ submitted_resume_pdf_id: "srpdf-1" }),
			});
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(DOCUMENTS_TESTID)).toBeInTheDocument();
			});
			const panel = screen.getByTestId(DOCUMENTS_TESTID);
			expect(within(panel).getByTestId("resume-download")).toBeInTheDocument();
		});

		it("hides resume Download when no submitted_resume_pdf_id", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({ submitted_resume_pdf_id: null }),
			});
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(DOCUMENTS_TESTID)).toBeInTheDocument();
			});
			const panel = screen.getByTestId(DOCUMENTS_TESTID);
			expect(
				within(panel).queryByTestId("resume-download"),
			).not.toBeInTheDocument();
		});

		it("shows cover letter section when cover_letter_id exists", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({ cover_letter_id: "cl-1" }),
			});
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(DOCUMENTS_TESTID)).toBeInTheDocument();
			});
			const panel = screen.getByTestId(DOCUMENTS_TESTID);
			expect(
				within(panel).getByTestId("cover-letter-section"),
			).toBeInTheDocument();
		});

		it("hides cover letter section when no cover_letter_id", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({ cover_letter_id: null }),
			});
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(DOCUMENTS_TESTID)).toBeInTheDocument();
			});
			const panel = screen.getByTestId(DOCUMENTS_TESTID);
			expect(
				within(panel).queryByTestId("cover-letter-section"),
			).not.toBeInTheDocument();
		});

		it("shows cover letter Download when submitted_cover_letter_pdf_id exists", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({
					cover_letter_id: "cl-1",
					submitted_cover_letter_pdf_id: "sclpdf-1",
				}),
			});
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(DOCUMENTS_TESTID)).toBeInTheDocument();
			});
			const panel = screen.getByTestId(DOCUMENTS_TESTID);
			expect(
				within(panel).getByTestId("cover-letter-download"),
			).toBeInTheDocument();
		});

		it("hides cover letter Download when no submitted_cover_letter_pdf_id", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({
					cover_letter_id: "cl-1",
					submitted_cover_letter_pdf_id: null,
				}),
			});
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(DOCUMENTS_TESTID)).toBeInTheDocument();
			});
			const panel = screen.getByTestId(DOCUMENTS_TESTID);
			expect(
				within(panel).queryByTestId("cover-letter-download"),
			).not.toBeInTheDocument();
		});

		it("shows job snapshot section (delegated to JobSnapshotSection)", async () => {
			mocks.mockApiGet.mockResolvedValue({ data: makeApplication() });
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(DOCUMENTS_TESTID)).toBeInTheDocument();
			});
			const panel = screen.getByTestId(DOCUMENTS_TESTID);
			expect(
				within(panel).getByTestId("mock-job-snapshot-section"),
			).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Timeline Panel
	// -----------------------------------------------------------------------

	describe("timeline panel", () => {
		it("renders the timeline panel with ApplicationTimeline", async () => {
			mocks.mockApiGet.mockResolvedValue({ data: makeApplication() });
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(TIMELINE_PANEL_TESTID)).toBeInTheDocument();
			});
			const timeline = screen.getByTestId("mock-application-timeline");
			expect(timeline).toBeInTheDocument();
			expect(timeline).toHaveAttribute("data-app-id", MOCK_APP_ID);
		});

		it("passes onAddEvent to ApplicationTimeline", async () => {
			mocks.mockApiGet.mockResolvedValue({ data: makeApplication() });
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(TIMELINE_PANEL_TESTID)).toBeInTheDocument();
			});
			expect(screen.getByTestId("mock-add-event-btn")).toBeInTheDocument();
		});

		it("opens Add Event dialog when Add Event button is clicked", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue({ data: makeApplication() });
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(TIMELINE_PANEL_TESTID)).toBeInTheDocument();
			});
			await user.click(screen.getByTestId("mock-add-event-btn"));
			expect(screen.getByTestId("mock-add-event-dialog")).toBeInTheDocument();
		});

		it("closes Add Event dialog when Cancel is clicked", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue({ data: makeApplication() });
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(TIMELINE_PANEL_TESTID)).toBeInTheDocument();
			});
			await user.click(screen.getByTestId("mock-add-event-btn"));
			expect(screen.getByTestId("mock-add-event-dialog")).toBeInTheDocument();
			await user.click(screen.getByTestId("mock-add-event-cancel"));
			expect(
				screen.queryByTestId("mock-add-event-dialog"),
			).not.toBeInTheDocument();
		});

		it("saves event via POST and shows success toast", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue({ data: makeApplication() });
			mocks.mockApiPost.mockResolvedValue({ data: {} });
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(TIMELINE_PANEL_TESTID)).toBeInTheDocument();
			});
			await user.click(screen.getByTestId("mock-add-event-btn"));
			await user.click(screen.getByTestId("mock-add-event-save"));
			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith(
					`/applications/${MOCK_APP_ID}/timeline`,
					{
						event_type: "custom",
						event_date: "2026-02-15T10:00",
					},
				);
			});
			expect(mocks.mockShowToast.success).toHaveBeenCalledWith("Event added.");
		});

		it("shows error toast when event save fails", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue({ data: makeApplication() });
			mocks.mockApiPost.mockRejectedValue(new Error("Network error"));
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(TIMELINE_PANEL_TESTID)).toBeInTheDocument();
			});
			await user.click(screen.getByTestId("mock-add-event-btn"));
			await user.click(screen.getByTestId("mock-add-event-save"));
			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalledWith(
					"Failed to add event.",
				);
			});
		});

		it("invalidates timeline query on successful event save", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue({ data: makeApplication() });
			mocks.mockApiPost.mockResolvedValue({ data: {} });
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(TIMELINE_PANEL_TESTID)).toBeInTheDocument();
			});
			await user.click(screen.getByTestId("mock-add-event-btn"));
			await user.click(screen.getByTestId("mock-add-event-save"));
			await waitFor(() => {
				expect(mocks.mockInvalidateQueries).toHaveBeenCalled();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Notes Section
	// -----------------------------------------------------------------------

	describe("notes section", () => {
		it("displays existing notes", async () => {
			mocks.mockApiGet.mockResolvedValue({ data: makeApplication() });
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(NOTES_TESTID)).toBeInTheDocument();
			});
			expect(
				screen.getByText("Recruiter: Sarah (sarah@acme.com)"),
			).toBeInTheDocument();
		});

		it("shows placeholder when notes are empty", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({ notes: null }),
			});
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(NOTES_TESTID)).toBeInTheDocument();
			});
			expect(screen.getByText("No notes yet.")).toBeInTheDocument();
		});

		it("opens edit mode when Edit button is clicked", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue({ data: makeApplication() });
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(NOTES_TESTID)).toBeInTheDocument();
			});
			await user.click(screen.getByTestId("notes-edit-button"));
			expect(screen.getByTestId("notes-textarea")).toBeInTheDocument();
		});

		it("pre-populates textarea with existing notes", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue({ data: makeApplication() });
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(NOTES_TESTID)).toBeInTheDocument();
			});
			await user.click(screen.getByTestId("notes-edit-button"));
			const textarea = screen.getByTestId("notes-textarea");
			expect(textarea).toHaveValue("Recruiter: Sarah (sarah@acme.com)");
		});

		it("saves notes via PATCH and shows success toast", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue({ data: makeApplication() });
			mocks.mockApiPatch.mockResolvedValue({
				data: makeApplication({ notes: "Updated notes" }),
			});
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(NOTES_TESTID)).toBeInTheDocument();
			});
			await user.click(screen.getByTestId("notes-edit-button"));
			const textarea = screen.getByTestId("notes-textarea");
			await user.clear(textarea);
			await user.type(textarea, "Updated notes");
			await user.click(screen.getByTestId("notes-save-button"));
			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/applications/${MOCK_APP_ID}`,
					{ notes: "Updated notes" },
				);
			});
			expect(mocks.mockShowToast.success).toHaveBeenCalledWith(
				"Notes updated.",
			);
		});

		it("shows error toast when save fails", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue({ data: makeApplication() });
			mocks.mockApiPatch.mockRejectedValue(new Error("Network error"));
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(NOTES_TESTID)).toBeInTheDocument();
			});
			await user.click(screen.getByTestId("notes-edit-button"));
			await user.click(screen.getByTestId("notes-save-button"));
			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalledWith(
					"Failed to save notes.",
				);
			});
		});

		it("cancels edit and reverts to display mode", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue({ data: makeApplication() });
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(NOTES_TESTID)).toBeInTheDocument();
			});
			await user.click(screen.getByTestId("notes-edit-button"));
			expect(screen.getByTestId("notes-textarea")).toBeInTheDocument();
			await user.click(screen.getByTestId("notes-cancel-button"));
			expect(screen.queryByTestId("notes-textarea")).not.toBeInTheDocument();
			expect(
				screen.getByText("Recruiter: Sarah (sarah@acme.com)"),
			).toBeInTheDocument();
		});

		it("shows character count with correct value in edit mode", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue({ data: makeApplication() });
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(NOTES_TESTID)).toBeInTheDocument();
			});
			await user.click(screen.getByTestId("notes-edit-button"));
			const charCount = screen.getByTestId("notes-char-count");
			expect(charCount).toBeInTheDocument();
			// "Recruiter: Sarah (sarah@acme.com)" is 33 characters
			expect(charCount).toHaveTextContent("33/10000");
		});

		it("invalidates query cache on successful save", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue({ data: makeApplication() });
			mocks.mockApiPatch.mockResolvedValue({
				data: makeApplication({ notes: "New note" }),
			});
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(NOTES_TESTID)).toBeInTheDocument();
			});
			await user.click(screen.getByTestId("notes-edit-button"));
			await user.click(screen.getByTestId("notes-save-button"));
			await waitFor(() => {
				expect(mocks.mockInvalidateQueries).toHaveBeenCalled();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Offer Details Section (§10.5)
	// -----------------------------------------------------------------------

	describe("offer details section", () => {
		it("renders offer details card when status is Offer and offer_details exists", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({
					status: "Offer",
					offer_details: {
						base_salary: 155000,
						salary_currency: "USD",
					},
				}),
			});
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(OFFER_SECTION_TESTID)).toBeInTheDocument();
			});
		});

		it("renders offer details card when status is Accepted and offer_details exists", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({
					status: "Accepted",
					offer_details: {
						base_salary: 155000,
						salary_currency: "USD",
					},
				}),
			});
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(OFFER_SECTION_TESTID)).toBeInTheDocument();
			});
		});

		it("does not render offer section when status is Applied", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({ status: "Applied" }),
			});
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(DETAIL_TESTID)).toBeInTheDocument();
			});
			expect(
				screen.queryByTestId(OFFER_SECTION_TESTID),
			).not.toBeInTheDocument();
		});

		it("does not render offer section when offer_details is null", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({
					status: "Offer",
					offer_details: null,
				}),
			});
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(DETAIL_TESTID)).toBeInTheDocument();
			});
			expect(
				screen.queryByTestId(OFFER_SECTION_TESTID),
			).not.toBeInTheDocument();
		});

		it("displays salary in the offer card", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({
					status: "Offer",
					offer_details: {
						base_salary: 155000,
						salary_currency: "USD",
					},
				}),
			});
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(OFFER_SECTION_TESTID)).toBeInTheDocument();
			});
			expect(screen.getByText(/\$155,000/)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Rejection Details Section (§10.6)
	// -----------------------------------------------------------------------

	describe("rejection details section", () => {
		it("renders rejection details card when status is Rejected and rejection_details exists", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({
					status: "Rejected",
					rejection_details: {
						stage: "Onsite",
						reason: "Culture fit concerns",
					},
				}),
			});
			renderDetail();
			await waitFor(() => {
				expect(
					screen.getByTestId(REJECTION_SECTION_TESTID),
				).toBeInTheDocument();
			});
		});

		it("does not render rejection section when status is Applied", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({ status: "Applied" }),
			});
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(DETAIL_TESTID)).toBeInTheDocument();
			});
			expect(
				screen.queryByTestId(REJECTION_SECTION_TESTID),
			).not.toBeInTheDocument();
		});

		it("does not render rejection section when rejection_details is null", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({
					status: "Rejected",
					rejection_details: null,
				}),
			});
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(DETAIL_TESTID)).toBeInTheDocument();
			});
			expect(
				screen.queryByTestId(REJECTION_SECTION_TESTID),
			).not.toBeInTheDocument();
		});

		it("displays stage in the rejection card", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({
					status: "Rejected",
					rejection_details: {
						stage: "Onsite",
						reason: "Culture fit concerns",
					},
				}),
			});
			renderDetail();
			await waitFor(() => {
				expect(
					screen.getByTestId(REJECTION_SECTION_TESTID),
				).toBeInTheDocument();
			});
			expect(screen.getByText("Onsite")).toBeInTheDocument();
		});

		it("displays reason in the rejection card", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({
					status: "Rejected",
					rejection_details: {
						stage: "Phone Screen",
						reason: "Culture fit concerns",
					},
				}),
			});
			renderDetail();
			await waitFor(() => {
				expect(
					screen.getByTestId(REJECTION_SECTION_TESTID),
				).toBeInTheDocument();
			});
			expect(screen.getByText("Culture fit concerns")).toBeInTheDocument();
		});

		it("renders rejection card for empty rejection_details object", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({
					status: "Rejected",
					rejection_details: {},
				}),
			});
			renderDetail();
			await waitFor(() => {
				expect(
					screen.getByTestId(REJECTION_SECTION_TESTID),
				).toBeInTheDocument();
			});
		});

		it("saves rejection details via PATCH and shows success toast", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({
					status: "Rejected",
					rejection_details: { stage: "Onsite", reason: "Culture fit" },
				}),
			});
			mocks.mockApiPatch.mockResolvedValue({
				data: makeApplication({
					status: "Rejected",
					rejection_details: { stage: "Onsite", reason: "Updated reason" },
				}),
			});
			renderDetail();
			await waitFor(() => {
				expect(
					screen.getByTestId(REJECTION_SECTION_TESTID),
				).toBeInTheDocument();
			});
			// Click Edit on the rejection card
			const section = screen.getByTestId(REJECTION_SECTION_TESTID);
			await user.click(within(section).getByRole("button", { name: "Edit" }));
			// The rejection dialog should open — verify via dialog-only field
			await waitFor(() => {
				expect(screen.getByLabelText("Reason")).toBeInTheDocument();
			});
			await user.click(screen.getByRole("button", { name: "Save" }));
			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/applications/${MOCK_APP_ID}`,
					expect.objectContaining({ rejection_details: expect.any(Object) }),
				);
			});
			expect(mocks.mockShowToast.success).toHaveBeenCalledWith(
				"Rejection details updated.",
			);
		});

		it("shows error toast when rejection save fails", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({
					status: "Rejected",
					rejection_details: { stage: "Onsite" },
				}),
			});
			mocks.mockApiPatch.mockRejectedValue(new Error("Network error"));
			renderDetail();
			await waitFor(() => {
				expect(
					screen.getByTestId(REJECTION_SECTION_TESTID),
				).toBeInTheDocument();
			});
			const section = screen.getByTestId(REJECTION_SECTION_TESTID);
			await user.click(within(section).getByRole("button", { name: "Edit" }));
			// The rejection dialog should open — verify via dialog-only field
			await waitFor(() => {
				expect(screen.getByLabelText("Reason")).toBeInTheDocument();
			});
			await user.click(screen.getByRole("button", { name: "Save" }));
			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalledWith(
					"Failed to update rejection details.",
				);
			});
		});
	});

	// -----------------------------------------------------------------------
	// Pin toggle (§10.9)
	// -----------------------------------------------------------------------

	describe("pin toggle", () => {
		it("renders pin toggle button in header", async () => {
			mocks.mockApiGet.mockResolvedValue({ data: makeApplication() });
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId("pin-toggle")).toBeInTheDocument();
			});
		});

		it("has aria-label 'Pin application' when unpinned", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({ is_pinned: false }),
			});
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId("pin-toggle")).toBeInTheDocument();
			});
			expect(screen.getByTestId("pin-toggle")).toHaveAttribute(
				"aria-label",
				"Pin application",
			);
		});

		it("has aria-label 'Unpin application' when pinned", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({ is_pinned: true }),
			});
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId("pin-toggle")).toBeInTheDocument();
			});
			expect(screen.getByTestId("pin-toggle")).toHaveAttribute(
				"aria-label",
				"Unpin application",
			);
		});

		it("sends PATCH with is_pinned: true when pinning", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({ is_pinned: false }),
			});
			mocks.mockApiPatch.mockResolvedValue({
				data: makeApplication({ is_pinned: true }),
			});
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId("pin-toggle")).toBeInTheDocument();
			});
			await user.click(screen.getByTestId("pin-toggle"));
			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/applications/${MOCK_APP_ID}`,
					{ is_pinned: true },
				);
			});
		});

		it("sends PATCH with is_pinned: false when unpinning", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({ is_pinned: true }),
			});
			mocks.mockApiPatch.mockResolvedValue({
				data: makeApplication({ is_pinned: false }),
			});
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId("pin-toggle")).toBeInTheDocument();
			});
			await user.click(screen.getByTestId("pin-toggle"));
			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith(
					`/applications/${MOCK_APP_ID}`,
					{ is_pinned: false },
				);
			});
		});

		it("shows success toast when pinning", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({ is_pinned: false }),
			});
			mocks.mockApiPatch.mockResolvedValue({
				data: makeApplication({ is_pinned: true }),
			});
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId("pin-toggle")).toBeInTheDocument();
			});
			await user.click(screen.getByTestId("pin-toggle"));
			await waitFor(() => {
				expect(mocks.mockShowToast.success).toHaveBeenCalledWith(
					"Application pinned.",
				);
			});
		});

		it("shows error toast when pin toggle fails", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({ is_pinned: false }),
			});
			mocks.mockApiPatch.mockRejectedValue(new Error("Network error"));
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId("pin-toggle")).toBeInTheDocument();
			});
			await user.click(screen.getByTestId("pin-toggle"));
			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalledWith(
					"Failed to update pin status.",
				);
			});
		});
	});

	// -----------------------------------------------------------------------
	// Archive (§10.9)
	// -----------------------------------------------------------------------

	describe("archive", () => {
		it("shows archive button when not archived", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({ archived_at: null }),
			});
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId("archive-button")).toBeInTheDocument();
			});
		});

		it("hides archive button when archived", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({ archived_at: "2026-02-10T00:00:00Z" }),
			});
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(DETAIL_TESTID)).toBeInTheDocument();
			});
			expect(screen.queryByTestId("archive-button")).not.toBeInTheDocument();
		});

		it("calls apiDelete and shows success toast", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({ archived_at: null }),
			});
			mocks.mockApiDelete.mockResolvedValue(undefined);
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId("archive-button")).toBeInTheDocument();
			});
			await user.click(screen.getByTestId("archive-button"));
			await waitFor(() => {
				expect(mocks.mockApiDelete).toHaveBeenCalledWith(
					`/applications/${MOCK_APP_ID}`,
				);
			});
			expect(mocks.mockShowToast.success).toHaveBeenCalledWith(
				"Application archived.",
			);
		});

		it("navigates to /applications after archiving", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({ archived_at: null }),
			});
			mocks.mockApiDelete.mockResolvedValue(undefined);
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId("archive-button")).toBeInTheDocument();
			});
			await user.click(screen.getByTestId("archive-button"));
			await waitFor(() => {
				expect(mocks.mockPush).toHaveBeenCalledWith("/applications");
			});
		});

		it("shows error toast when archive fails", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({ archived_at: null }),
			});
			mocks.mockApiDelete.mockRejectedValue(new Error("Network error"));
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId("archive-button")).toBeInTheDocument();
			});
			await user.click(screen.getByTestId("archive-button"));
			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalledWith(
					"Failed to archive application.",
				);
			});
		});
	});

	// -----------------------------------------------------------------------
	// Restore (§10.9)
	// -----------------------------------------------------------------------

	describe("restore", () => {
		it("shows restore button when archived", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({ archived_at: "2026-02-10T00:00:00Z" }),
			});
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId("restore-button")).toBeInTheDocument();
			});
		});

		it("hides restore button when not archived", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({ archived_at: null }),
			});
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId(DETAIL_TESTID)).toBeInTheDocument();
			});
			expect(screen.queryByTestId("restore-button")).not.toBeInTheDocument();
		});

		it("calls apiPost restore and shows success toast", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({ archived_at: "2026-02-10T00:00:00Z" }),
			});
			mocks.mockApiPost.mockResolvedValue({
				data: makeApplication({ archived_at: null }),
			});
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId("restore-button")).toBeInTheDocument();
			});
			await user.click(screen.getByTestId("restore-button"));
			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith(
					`/applications/${MOCK_APP_ID}/restore`,
				);
			});
			expect(mocks.mockShowToast.success).toHaveBeenCalledWith(
				"Application restored.",
			);
		});

		it("shows error toast when restore fails", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({ archived_at: "2026-02-10T00:00:00Z" }),
			});
			mocks.mockApiPost.mockRejectedValue(new Error("Network error"));
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId("restore-button")).toBeInTheDocument();
			});
			await user.click(screen.getByTestId("restore-button"));
			await waitFor(() => {
				expect(mocks.mockShowToast.error).toHaveBeenCalledWith(
					"Failed to restore application.",
				);
			});
		});

		it("invalidates query cache on successful restore", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue({
				data: makeApplication({ archived_at: "2026-02-10T00:00:00Z" }),
			});
			mocks.mockApiPost.mockResolvedValue({
				data: makeApplication({ archived_at: null }),
			});
			renderDetail();
			await waitFor(() => {
				expect(screen.getByTestId("restore-button")).toBeInTheDocument();
			});
			await user.click(screen.getByTestId("restore-button"));
			await waitFor(() => {
				expect(mocks.mockInvalidateQueries).toHaveBeenCalled();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Job Snapshot Section integration (§10.9)
	// -----------------------------------------------------------------------

	describe("job snapshot section integration", () => {
		it("renders JobSnapshotSection with snapshot data", async () => {
			mocks.mockApiGet.mockResolvedValue({ data: makeApplication() });
			renderDetail();
			await waitFor(() => {
				expect(
					screen.getByTestId("mock-job-snapshot-section"),
				).toBeInTheDocument();
			});
		});
	});

	// -----------------------------------------------------------------------
	// API call verification
	// -----------------------------------------------------------------------

	describe("API integration", () => {
		it("fetches the application by ID", async () => {
			mocks.mockApiGet.mockResolvedValue({ data: makeApplication() });
			renderDetail();
			await waitFor(() => {
				expect(mocks.mockApiGet).toHaveBeenCalledWith(
					`/applications/${MOCK_APP_ID}`,
				);
			});
		});
	});
});
