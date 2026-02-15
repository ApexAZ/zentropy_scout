/**
 * Tests for the AddTimelineEventDialog component (§10.8).
 *
 * REQ-012 §11.7: "Add Event" form for timeline with event type selector
 * (manual types only), description, conditional interview stage, and date/time.
 * Timeline events are immutable — no edit, only append.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AddTimelineEventDialog } from "./add-timeline-event-dialog";
import type { CreateTimelineEventPayload } from "./add-timeline-event-dialog";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DIALOG_TITLE = "Add Timeline Event";
const EVENT_TYPE_SELECT_TESTID = "event-type-select";
const INTERVIEW_STAGE_SELECT_TESTID = "interview-stage-select";
const CHAR_COUNT_TESTID = "description-char-count";
const EVENT_TYPE_LABEL = "Event Type";
const EVENT_DATE_LABEL = "Event Date";
const DESCRIPTION_LABEL = "Description";
const INTERVIEW_STAGE_LABEL = "Interview Stage";
const INTERVIEW_SCHEDULED_LABEL = "Interview Scheduled";
const INTERVIEW_COMPLETED_LABEL = "Interview Completed";
const FOLLOW_UP_SENT_LABEL = "Follow-up Sent";
const RESPONSE_RECEIVED_LABEL = "Response Received";
const CUSTOM_EVENT_LABEL = "Custom Event";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderDialog(
	props?: Partial<{
		open: boolean;
		onConfirm: (data: CreateTimelineEventPayload) => void;
		onCancel: () => void;
		loading: boolean;
	}>,
) {
	const defaultProps = {
		open: true,
		onConfirm: vi.fn(),
		onCancel: vi.fn(),
		loading: false,
		...props,
	};
	return {
		...render(<AddTimelineEventDialog {...defaultProps} />),
		onConfirm: defaultProps.onConfirm,
		onCancel: defaultProps.onCancel,
	};
}

// ---------------------------------------------------------------------------
// Setup / Teardown
// ---------------------------------------------------------------------------

afterEach(() => {
	cleanup();
	vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AddTimelineEventDialog", () => {
	// -----------------------------------------------------------------------
	// Rendering
	// -----------------------------------------------------------------------

	describe("rendering", () => {
		it("renders dialog title", () => {
			renderDialog();
			expect(screen.getByText(DIALOG_TITLE)).toBeInTheDocument();
		});

		it("renders event type select", () => {
			renderDialog();
			expect(screen.getByLabelText(EVENT_TYPE_LABEL)).toBeInTheDocument();
		});

		it("renders event date input", () => {
			renderDialog();
			expect(screen.getByLabelText(EVENT_DATE_LABEL)).toBeInTheDocument();
		});

		it("renders description textarea", () => {
			renderDialog();
			expect(screen.getByLabelText(DESCRIPTION_LABEL)).toBeInTheDocument();
		});

		it("renders character counter for description", () => {
			renderDialog();
			expect(screen.getByTestId(CHAR_COUNT_TESTID)).toHaveTextContent("0/2000");
		});

		it("does not render dialog content when open is false", () => {
			renderDialog({ open: false });
			expect(screen.queryByText(DIALOG_TITLE)).not.toBeInTheDocument();
		});

		it("renders Save and Cancel buttons", () => {
			renderDialog();
			expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
			expect(
				screen.getByRole("button", { name: "Cancel" }),
			).toBeInTheDocument();
		});

		it("disables Save button when form is empty (no event type or date)", () => {
			renderDialog();
			expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
		});
	});

	// -----------------------------------------------------------------------
	// Event type options
	// -----------------------------------------------------------------------

	describe("event type options", () => {
		it("shows only manual event types in dropdown", async () => {
			const user = userEvent.setup();
			renderDialog();

			const trigger = screen.getByTestId(EVENT_TYPE_SELECT_TESTID);
			await user.click(trigger);

			await waitFor(() => {
				expect(
					screen.getByRole("option", { name: INTERVIEW_SCHEDULED_LABEL }),
				).toBeInTheDocument();
				expect(
					screen.getByRole("option", { name: INTERVIEW_COMPLETED_LABEL }),
				).toBeInTheDocument();
				expect(
					screen.getByRole("option", { name: FOLLOW_UP_SENT_LABEL }),
				).toBeInTheDocument();
				expect(
					screen.getByRole("option", { name: RESPONSE_RECEIVED_LABEL }),
				).toBeInTheDocument();
				expect(
					screen.getByRole("option", { name: CUSTOM_EVENT_LABEL }),
				).toBeInTheDocument();
			});
		});

		it("does not show auto event types in dropdown", async () => {
			const user = userEvent.setup();
			renderDialog();

			const trigger = screen.getByTestId(EVENT_TYPE_SELECT_TESTID);
			await user.click(trigger);

			await waitFor(() => {
				expect(
					screen.getByRole("option", { name: INTERVIEW_SCHEDULED_LABEL }),
				).toBeInTheDocument();
			});

			// Auto types should NOT be selectable
			const autoTypes = [
				"Applied",
				"Status Changed",
				"Note Added",
				"Offer Received",
				"Offer Accepted",
				"Rejected",
				"Withdrawn",
			];
			for (const label of autoTypes) {
				expect(
					screen.queryByRole("option", { name: label }),
				).not.toBeInTheDocument();
			}
		});
	});

	// -----------------------------------------------------------------------
	// Conditional interview stage
	// -----------------------------------------------------------------------

	describe("conditional interview stage", () => {
		it("does not show interview stage by default", () => {
			renderDialog();
			expect(
				screen.queryByLabelText(INTERVIEW_STAGE_LABEL),
			).not.toBeInTheDocument();
		});

		it("shows interview stage when interview_scheduled is selected", async () => {
			const user = userEvent.setup();
			renderDialog();

			// Select interview_scheduled
			await user.click(screen.getByTestId(EVENT_TYPE_SELECT_TESTID));
			await waitFor(() => {
				expect(
					screen.getByRole("option", { name: INTERVIEW_SCHEDULED_LABEL }),
				).toBeInTheDocument();
			});
			await user.click(
				screen.getByRole("option", { name: INTERVIEW_SCHEDULED_LABEL }),
			);

			expect(screen.getByLabelText(INTERVIEW_STAGE_LABEL)).toBeInTheDocument();
		});

		it("shows interview stage when interview_completed is selected", async () => {
			const user = userEvent.setup();
			renderDialog();

			// Select interview_completed
			await user.click(screen.getByTestId(EVENT_TYPE_SELECT_TESTID));
			await waitFor(() => {
				expect(
					screen.getByRole("option", { name: INTERVIEW_COMPLETED_LABEL }),
				).toBeInTheDocument();
			});
			await user.click(
				screen.getByRole("option", { name: INTERVIEW_COMPLETED_LABEL }),
			);

			expect(screen.getByLabelText(INTERVIEW_STAGE_LABEL)).toBeInTheDocument();
		});

		it("hides interview stage when switching from interview to non-interview type", async () => {
			const user = userEvent.setup();
			renderDialog();

			// Select interview_scheduled first
			await user.click(screen.getByTestId(EVENT_TYPE_SELECT_TESTID));
			await waitFor(() => {
				expect(
					screen.getByRole("option", { name: INTERVIEW_SCHEDULED_LABEL }),
				).toBeInTheDocument();
			});
			await user.click(
				screen.getByRole("option", { name: INTERVIEW_SCHEDULED_LABEL }),
			);
			expect(screen.getByLabelText(INTERVIEW_STAGE_LABEL)).toBeInTheDocument();

			// Switch to custom
			await user.click(screen.getByTestId(EVENT_TYPE_SELECT_TESTID));
			await waitFor(() => {
				expect(
					screen.getByRole("option", { name: CUSTOM_EVENT_LABEL }),
				).toBeInTheDocument();
			});
			await user.click(
				screen.getByRole("option", { name: CUSTOM_EVENT_LABEL }),
			);

			expect(
				screen.queryByLabelText(INTERVIEW_STAGE_LABEL),
			).not.toBeInTheDocument();
		});

		it("shows interview stage options (Phone Screen, Onsite, Final Round)", async () => {
			const user = userEvent.setup();
			renderDialog();

			// Select interview_scheduled
			await user.click(screen.getByTestId(EVENT_TYPE_SELECT_TESTID));
			await waitFor(() => {
				expect(
					screen.getByRole("option", { name: INTERVIEW_SCHEDULED_LABEL }),
				).toBeInTheDocument();
			});
			await user.click(
				screen.getByRole("option", { name: INTERVIEW_SCHEDULED_LABEL }),
			);

			// Open interview stage dropdown
			await user.click(screen.getByTestId(INTERVIEW_STAGE_SELECT_TESTID));
			await waitFor(() => {
				expect(
					screen.getByRole("option", { name: "Phone Screen" }),
				).toBeInTheDocument();
				expect(
					screen.getByRole("option", { name: "Onsite" }),
				).toBeInTheDocument();
				expect(
					screen.getByRole("option", { name: "Final Round" }),
				).toBeInTheDocument();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Interaction
	// -----------------------------------------------------------------------

	describe("interaction", () => {
		it("calls onConfirm with event type and date", async () => {
			const user = userEvent.setup();
			const { onConfirm } = renderDialog();

			// Select event type
			await user.click(screen.getByTestId(EVENT_TYPE_SELECT_TESTID));
			await waitFor(() => {
				expect(
					screen.getByRole("option", { name: FOLLOW_UP_SENT_LABEL }),
				).toBeInTheDocument();
			});
			await user.click(
				screen.getByRole("option", { name: FOLLOW_UP_SENT_LABEL }),
			);

			// Set date
			const dateInput = screen.getByLabelText(EVENT_DATE_LABEL);
			await user.clear(dateInput);
			await user.type(dateInput, "2026-02-15T10:30");

			await user.click(screen.getByRole("button", { name: "Save" }));

			expect(onConfirm).toHaveBeenCalledWith(
				expect.objectContaining({
					event_type: "follow_up_sent",
					event_date: "2026-02-15T10:30",
				}),
			);
		});

		it("calls onConfirm with all fields including description", async () => {
			const user = userEvent.setup();
			const { onConfirm } = renderDialog();

			// Select event type
			await user.click(screen.getByTestId(EVENT_TYPE_SELECT_TESTID));
			await waitFor(() => {
				expect(
					screen.getByRole("option", { name: CUSTOM_EVENT_LABEL }),
				).toBeInTheDocument();
			});
			await user.click(
				screen.getByRole("option", { name: CUSTOM_EVENT_LABEL }),
			);

			// Set date
			const dateInput = screen.getByLabelText(EVENT_DATE_LABEL);
			await user.clear(dateInput);
			await user.type(dateInput, "2026-02-10T14:00");

			// Set description
			await user.type(
				screen.getByLabelText(DESCRIPTION_LABEL),
				"Attended networking event",
			);

			await user.click(screen.getByRole("button", { name: "Save" }));

			expect(onConfirm).toHaveBeenCalledWith(
				expect.objectContaining({
					event_type: "custom",
					event_date: "2026-02-10T14:00",
					description: "Attended networking event",
				}),
			);
		});

		it("calls onConfirm with interview stage for interview event", async () => {
			const user = userEvent.setup();
			const { onConfirm } = renderDialog();

			// Select interview_scheduled
			await user.click(screen.getByTestId(EVENT_TYPE_SELECT_TESTID));
			await waitFor(() => {
				expect(
					screen.getByRole("option", { name: INTERVIEW_SCHEDULED_LABEL }),
				).toBeInTheDocument();
			});
			await user.click(
				screen.getByRole("option", { name: INTERVIEW_SCHEDULED_LABEL }),
			);

			// Set date
			const dateInput = screen.getByLabelText(EVENT_DATE_LABEL);
			await user.clear(dateInput);
			await user.type(dateInput, "2026-02-20T09:00");

			// Select interview stage
			await user.click(screen.getByTestId(INTERVIEW_STAGE_SELECT_TESTID));
			await waitFor(() => {
				expect(
					screen.getByRole("option", { name: "Onsite" }),
				).toBeInTheDocument();
			});
			await user.click(screen.getByRole("option", { name: "Onsite" }));

			await user.click(screen.getByRole("button", { name: "Save" }));

			expect(onConfirm).toHaveBeenCalledWith(
				expect.objectContaining({
					event_type: "interview_scheduled",
					event_date: "2026-02-20T09:00",
					interview_stage: "Onsite",
				}),
			);
		});

		it("does not include interview_stage for non-interview event", async () => {
			const user = userEvent.setup();
			const onConfirm = vi.fn();
			renderDialog({ onConfirm });

			// Select follow_up_sent
			await user.click(screen.getByTestId(EVENT_TYPE_SELECT_TESTID));
			await waitFor(() => {
				expect(
					screen.getByRole("option", { name: FOLLOW_UP_SENT_LABEL }),
				).toBeInTheDocument();
			});
			await user.click(
				screen.getByRole("option", { name: FOLLOW_UP_SENT_LABEL }),
			);

			// Set date
			const dateInput = screen.getByLabelText(EVENT_DATE_LABEL);
			await user.clear(dateInput);
			await user.type(dateInput, "2026-02-15T10:30");

			await user.click(screen.getByRole("button", { name: "Save" }));

			const payload = onConfirm.mock.calls[0][0] as CreateTimelineEventPayload;
			expect(payload.interview_stage).toBeUndefined();
		});

		it("calls onCancel when Cancel is clicked", async () => {
			const user = userEvent.setup();
			const { onCancel } = renderDialog();

			await user.click(screen.getByRole("button", { name: "Cancel" }));

			expect(onCancel).toHaveBeenCalled();
		});

		it("disables Save button while loading", () => {
			renderDialog({ loading: true });
			expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
		});

		it("disables Cancel button while loading", () => {
			renderDialog({ loading: true });
			expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
		});

		it("does not call onConfirm when event type is not selected", async () => {
			const user = userEvent.setup();
			const onConfirm = vi.fn();
			renderDialog({ onConfirm });

			// Set date but no event type
			const dateInput = screen.getByLabelText(EVENT_DATE_LABEL);
			await user.clear(dateInput);
			await user.type(dateInput, "2026-02-15T10:30");

			// Save button should be disabled, but verify onConfirm is not called
			expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
			expect(onConfirm).not.toHaveBeenCalled();
		});

		it("does not call onConfirm when event date is empty", async () => {
			const user = userEvent.setup();
			const onConfirm = vi.fn();
			renderDialog({ onConfirm });

			// Select event type but no date
			await user.click(screen.getByTestId(EVENT_TYPE_SELECT_TESTID));
			await waitFor(() => {
				expect(
					screen.getByRole("option", { name: CUSTOM_EVENT_LABEL }),
				).toBeInTheDocument();
			});
			await user.click(
				screen.getByRole("option", { name: CUSTOM_EVENT_LABEL }),
			);

			// Save button should be disabled
			expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
			expect(onConfirm).not.toHaveBeenCalled();
		});

		it("resets form when dialog reopens", async () => {
			const user = userEvent.setup();
			const { rerender, onConfirm } = renderDialog();

			// Fill description
			await user.type(screen.getByLabelText(DESCRIPTION_LABEL), "Some text");

			// Close and reopen dialog
			rerender(
				<AddTimelineEventDialog
					open={false}
					onConfirm={onConfirm}
					onCancel={vi.fn()}
				/>,
			);
			rerender(
				<AddTimelineEventDialog
					open={true}
					onConfirm={onConfirm}
					onCancel={vi.fn()}
				/>,
			);

			// Description should be empty
			expect(screen.getByLabelText(DESCRIPTION_LABEL)).toHaveValue("");
		});
	});
});
