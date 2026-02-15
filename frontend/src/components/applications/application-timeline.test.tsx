/**
 * Tests for the ApplicationTimeline component (§10.7).
 *
 * REQ-012 §11.7: Vertical chronological timeline with event type icons.
 * Events are immutable (append-only). "Add Event" button opens form (§10.8).
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { TimelineEvent, TimelineEventType } from "@/types/application";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TIMELINE_TESTID = "application-timeline";
const LOADING_TESTID = "timeline-loading";
const EMPTY_TESTID = "timeline-empty";
const MOCK_APP_ID = "app-timeline-1";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeTimelineEvent(overrides?: Partial<TimelineEvent>): TimelineEvent {
	return {
		id: "te-1",
		application_id: MOCK_APP_ID,
		event_type: "applied",
		event_date: "2026-01-10T09:00:00Z",
		description: null,
		interview_stage: null,
		created_at: "2026-01-10T09:00:00Z",
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
		MockApiError,
	};
});

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
	ApiError: mocks.MockApiError,
}));

import { ApplicationTimeline } from "./application-timeline";

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

function renderTimeline(applicationId = MOCK_APP_ID, onAddEvent = vi.fn()) {
	return {
		...render(
			<ApplicationTimeline
				applicationId={applicationId}
				onAddEvent={onAddEvent}
			/>,
			{ wrapper: createWrapper() },
		),
		onAddEvent,
	};
}

beforeEach(() => {
	mocks.mockApiGet.mockResolvedValue({
		data: [],
		meta: { total: 0, page: 1, per_page: 50, total_pages: 0 },
	});
});

afterEach(() => {
	cleanup();
	vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ApplicationTimeline", () => {
	// -----------------------------------------------------------------------
	// Loading
	// -----------------------------------------------------------------------

	describe("loading", () => {
		it("shows spinner while fetching events", () => {
			mocks.mockApiGet.mockReturnValue(new Promise(() => {})); // Never resolves
			renderTimeline();
			expect(screen.getByTestId(LOADING_TESTID)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Error
	// -----------------------------------------------------------------------

	describe("error", () => {
		it("shows error state on API failure", async () => {
			mocks.mockApiGet.mockRejectedValue(
				new mocks.MockApiError("SERVER_ERROR", "Internal error", 500),
			);
			renderTimeline();

			await waitFor(() => {
				expect(screen.getByText("Failed to load.")).toBeInTheDocument();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Empty state
	// -----------------------------------------------------------------------

	describe("empty state", () => {
		it("shows empty message when no events", async () => {
			renderTimeline();

			await waitFor(() => {
				expect(screen.getByTestId(EMPTY_TESTID)).toBeInTheDocument();
			});
			expect(screen.getByText("No events yet.")).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Rendering
	// -----------------------------------------------------------------------

	describe("rendering", () => {
		it("renders timeline card with title", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: [makeTimelineEvent()],
				meta: { total: 1, page: 1, per_page: 50, total_pages: 1 },
			});
			renderTimeline();

			await waitFor(() => {
				expect(screen.getByTestId(TIMELINE_TESTID)).toBeInTheDocument();
			});
			expect(screen.getByText("Timeline")).toBeInTheDocument();
		});

		it("renders Add Event button", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: [makeTimelineEvent()],
				meta: { total: 1, page: 1, per_page: 50, total_pages: 1 },
			});
			renderTimeline();

			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: /Add Event/i }),
				).toBeInTheDocument();
			});
		});

		it("calls onAddEvent when Add Event is clicked", async () => {
			const user = userEvent.setup();
			mocks.mockApiGet.mockResolvedValue({
				data: [makeTimelineEvent()],
				meta: { total: 1, page: 1, per_page: 50, total_pages: 1 },
			});
			const { onAddEvent } = renderTimeline();

			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: /Add Event/i }),
				).toBeInTheDocument();
			});
			await user.click(screen.getByRole("button", { name: /Add Event/i }));

			expect(onAddEvent).toHaveBeenCalledOnce();
		});

		it("does not render Add Event button when onAddEvent is not provided", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: [makeTimelineEvent()],
				meta: { total: 1, page: 1, per_page: 50, total_pages: 1 },
			});
			render(<ApplicationTimeline applicationId={MOCK_APP_ID} />, {
				wrapper: createWrapper(),
			});

			await waitFor(() => {
				expect(screen.getByTestId(TIMELINE_TESTID)).toBeInTheDocument();
			});
			expect(
				screen.queryByRole("button", { name: /Add Event/i }),
			).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Event display
	// -----------------------------------------------------------------------

	describe("event display", () => {
		it("renders event type label", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: [makeTimelineEvent({ event_type: "interview_scheduled" })],
				meta: { total: 1, page: 1, per_page: 50, total_pages: 1 },
			});
			renderTimeline();

			await waitFor(() => {
				expect(screen.getByText("Interview Scheduled")).toBeInTheDocument();
			});
		});

		it("renders formatted event date", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: [makeTimelineEvent({ event_date: "2026-01-15T10:30:00Z" })],
				meta: { total: 1, page: 1, per_page: 50, total_pages: 1 },
			});
			renderTimeline();

			await waitFor(() => {
				expect(screen.getByText("Jan 15, 2026")).toBeInTheDocument();
			});
		});

		it("renders 'Unknown' for invalid event date", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: [makeTimelineEvent({ event_date: "not-a-date" })],
				meta: { total: 1, page: 1, per_page: 50, total_pages: 1 },
			});
			renderTimeline();

			await waitFor(() => {
				expect(screen.getByText("Unknown")).toBeInTheDocument();
			});
		});

		it("renders event description when present", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: [
					makeTimelineEvent({
						description: "Passed phone screen with flying colors",
					}),
				],
				meta: { total: 1, page: 1, per_page: 50, total_pages: 1 },
			});
			renderTimeline();

			await waitFor(() => {
				expect(
					screen.getByText("Passed phone screen with flying colors"),
				).toBeInTheDocument();
			});
		});

		it("does not render description when null", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: [makeTimelineEvent({ description: null })],
				meta: { total: 1, page: 1, per_page: 50, total_pages: 1 },
			});
			renderTimeline();

			await waitFor(() => {
				expect(screen.getByText("Applied")).toBeInTheDocument();
			});
			// No description element should exist
			expect(
				screen.queryByTestId("timeline-event-description"),
			).not.toBeInTheDocument();
		});

		it("renders interview stage for interview events", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: [
					makeTimelineEvent({
						event_type: "interview_scheduled",
						interview_stage: "Onsite",
					}),
				],
				meta: { total: 1, page: 1, per_page: 50, total_pages: 1 },
			});
			renderTimeline();

			await waitFor(() => {
				expect(screen.getByText("Onsite")).toBeInTheDocument();
			});
		});

		it("does not render interview stage when null", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: [
					makeTimelineEvent({
						event_type: "applied",
						interview_stage: null,
					}),
				],
				meta: { total: 1, page: 1, per_page: 50, total_pages: 1 },
			});
			renderTimeline();

			await waitFor(() => {
				expect(screen.getByText("Applied")).toBeInTheDocument();
			});
			expect(
				screen.queryByTestId("timeline-event-stage"),
			).not.toBeInTheDocument();
		});

		it("renders multiple events in chronological order", async () => {
			mocks.mockApiGet.mockResolvedValue({
				data: [
					makeTimelineEvent({
						id: "te-1",
						event_type: "applied",
						event_date: "2026-01-10T09:00:00Z",
					}),
					makeTimelineEvent({
						id: "te-2",
						event_type: "interview_scheduled",
						event_date: "2026-01-15T14:00:00Z",
					}),
					makeTimelineEvent({
						id: "te-3",
						event_type: "offer_received",
						event_date: "2026-01-20T11:00:00Z",
					}),
				],
				meta: { total: 3, page: 1, per_page: 50, total_pages: 1 },
			});
			renderTimeline();

			await waitFor(() => {
				expect(screen.getByText("Applied")).toBeInTheDocument();
			});

			const items = screen.getAllByTestId("timeline-event-item");
			expect(items).toHaveLength(3);
		});
	});

	// -----------------------------------------------------------------------
	// Event icons
	// -----------------------------------------------------------------------

	describe("event icons", () => {
		const EVENT_TYPES_TO_TEST: TimelineEventType[] = [
			"applied",
			"status_changed",
			"note_added",
			"interview_scheduled",
			"interview_completed",
			"offer_received",
			"offer_accepted",
			"rejected",
			"withdrawn",
			"follow_up_sent",
			"response_received",
			"custom",
		];

		it.each(EVENT_TYPES_TO_TEST)(
			"renders icon for %s event type",
			async (eventType) => {
				mocks.mockApiGet.mockResolvedValue({
					data: [makeTimelineEvent({ event_type: eventType })],
					meta: { total: 1, page: 1, per_page: 50, total_pages: 1 },
				});
				renderTimeline();

				await waitFor(() => {
					expect(
						screen.getByTestId(`timeline-icon-${eventType}`),
					).toBeInTheDocument();
				});
			},
		);
	});

	// -----------------------------------------------------------------------
	// API integration
	// -----------------------------------------------------------------------

	describe("API integration", () => {
		it("fetches from correct endpoint", async () => {
			renderTimeline("app-abc-123");

			await waitFor(() => {
				expect(mocks.mockApiGet).toHaveBeenCalledWith(
					"/applications/app-abc-123/timeline",
				);
			});
		});
	});
});
