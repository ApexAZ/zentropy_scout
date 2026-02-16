"use client";

/**
 * Dialog for adding a manual timeline event to an application.
 *
 * REQ-012 §11.7: "Add Event" button opens a form with event type selector
 * (manual types only), description, conditional interview stage, and date/time.
 * Timeline events are immutable — no edit, only append.
 */

import { useCallback, useState } from "react";
import { AlertDialog as AlertDialogPrimitive } from "radix-ui";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { INTERVIEW_STAGES } from "@/types/application";
import type { InterviewStage, TimelineEventType } from "@/types/application";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const FIELD_WRAPPER_CLASS = "space-y-1";
const DESCRIPTION_MAX_LENGTH = 2_000;

interface ManualEventOption {
	value: TimelineEventType;
	label: string;
}

const MANUAL_EVENT_TYPES: readonly ManualEventOption[] = [
	{ value: "interview_scheduled", label: "Interview Scheduled" },
	{ value: "interview_completed", label: "Interview Completed" },
	{ value: "follow_up_sent", label: "Follow-up Sent" },
	{ value: "response_received", label: "Response Received" },
	{ value: "custom", label: "Custom Event" },
] as const;

const MANUAL_EVENT_TYPE_VALUES: ReadonlySet<string> = new Set(
	MANUAL_EVENT_TYPES.map((t) => t.value),
);

const INTERVIEW_EVENT_TYPES: ReadonlySet<TimelineEventType> = new Set([
	"interview_scheduled",
	"interview_completed",
]);

// ---------------------------------------------------------------------------
// Type guards
// ---------------------------------------------------------------------------

function isValidManualEventType(value: string): value is TimelineEventType {
	return MANUAL_EVENT_TYPE_VALUES.has(value);
}

function isValidInterviewStage(value: string): value is InterviewStage {
	return (INTERVIEW_STAGES as readonly string[]).includes(value);
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface CreateTimelineEventPayload {
	event_type: TimelineEventType;
	event_date: string;
	description?: string;
	interview_stage?: InterviewStage;
}

export interface AddTimelineEventDialogProps {
	open: boolean;
	onConfirm: (data: CreateTimelineEventPayload) => void;
	onCancel: () => void;
	loading?: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function AddTimelineEventDialog({
	open,
	onConfirm,
	onCancel,
	loading = false,
}: Readonly<AddTimelineEventDialogProps>) {
	const [eventType, setEventType] = useState<TimelineEventType | "">("");
	const [eventDate, setEventDate] = useState("");
	const [description, setDescription] = useState("");
	const [interviewStage, setInterviewStage] = useState<InterviewStage | "">("");

	// Adjust state when dialog opens (React "deriving state from props" pattern)
	const [prevOpen, setPrevOpen] = useState(false);
	if (open !== prevOpen) {
		setPrevOpen(open);
		if (open) {
			setEventType("");
			setEventDate("");
			setDescription("");
			setInterviewStage("");
		}
	}

	const isInterviewEvent =
		eventType !== "" && INTERVIEW_EVENT_TYPES.has(eventType);
	const isFormValid = eventType !== "" && eventDate !== "";

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	const handleEventTypeChange = useCallback((value: string) => {
		if (!isValidManualEventType(value)) return;
		setEventType(value);
		// Clear interview stage when switching away from interview type
		if (!INTERVIEW_EVENT_TYPES.has(value)) {
			setInterviewStage("");
		}
	}, []);

	const handleConfirm = useCallback(() => {
		if (!eventType || !eventDate) return;

		// Validate date is parseable
		const parsed = new Date(eventDate);
		if (Number.isNaN(parsed.getTime())) return;

		const payload: CreateTimelineEventPayload = {
			event_type: eventType,
			event_date: eventDate,
		};
		if (description) {
			payload.description = description;
		}
		if (
			isInterviewEvent &&
			interviewStage &&
			isValidInterviewStage(interviewStage)
		) {
			payload.interview_stage = interviewStage;
		}
		onConfirm(payload);
	}, [
		eventType,
		eventDate,
		description,
		isInterviewEvent,
		interviewStage,
		onConfirm,
	]);

	const handleOpenChange = useCallback(
		(isOpen: boolean) => {
			if (!isOpen) {
				onCancel();
			}
		},
		[onCancel],
	);

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	return (
		<AlertDialogPrimitive.Root open={open} onOpenChange={handleOpenChange}>
			<AlertDialogPrimitive.Portal>
				<AlertDialogPrimitive.Overlay className="data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 fixed inset-0 z-50 bg-black/50" />
				<AlertDialogPrimitive.Content
					className={cn(
						"bg-background data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 fixed top-[50%] left-[50%] z-50 grid w-full max-w-[calc(100%-2rem)] translate-x-[-50%] translate-y-[-50%] gap-4 rounded-lg border p-6 shadow-lg duration-200 outline-none sm:max-w-lg",
					)}
				>
					<div className="flex flex-col gap-2 text-center sm:text-left">
						<AlertDialogPrimitive.Title className="text-lg leading-none font-semibold">
							Add Timeline Event
						</AlertDialogPrimitive.Title>
						<AlertDialogPrimitive.Description className="text-muted-foreground text-sm">
							Add a manual event to the application timeline.
						</AlertDialogPrimitive.Description>
					</div>

					{/* Form fields */}
					<div className="grid grid-cols-2 gap-4">
						{/* Event Type */}
						<div className={FIELD_WRAPPER_CLASS}>
							<Label htmlFor="event-type">Event Type</Label>
							<Select value={eventType} onValueChange={handleEventTypeChange}>
								<SelectTrigger id="event-type" data-testid="event-type-select">
									<SelectValue placeholder="Select type" />
								</SelectTrigger>
								<SelectContent>
									{MANUAL_EVENT_TYPES.map((t) => (
										<SelectItem key={t.value} value={t.value}>
											{t.label}
										</SelectItem>
									))}
								</SelectContent>
							</Select>
						</div>

						{/* Event Date */}
						<div className={FIELD_WRAPPER_CLASS}>
							<Label htmlFor="event-date">Event Date</Label>
							<Input
								id="event-date"
								type="datetime-local"
								value={eventDate}
								onChange={(e) => setEventDate(e.target.value)}
							/>
						</div>
					</div>

					{/* Interview Stage (conditional) */}
					{isInterviewEvent && (
						<div className={FIELD_WRAPPER_CLASS}>
							<Label htmlFor="interview-stage">Interview Stage</Label>
							<Select
								value={interviewStage}
								onValueChange={(v) => {
									if (isValidInterviewStage(v)) setInterviewStage(v);
								}}
							>
								<SelectTrigger
									id="interview-stage"
									data-testid="interview-stage-select"
								>
									<SelectValue placeholder="Select stage" />
								</SelectTrigger>
								<SelectContent>
									{INTERVIEW_STAGES.map((s) => (
										<SelectItem key={s} value={s}>
											{s}
										</SelectItem>
									))}
								</SelectContent>
							</Select>
						</div>
					)}

					{/* Description */}
					<div className={FIELD_WRAPPER_CLASS}>
						<Label htmlFor="event-description">Description</Label>
						<Textarea
							id="event-description"
							rows={3}
							maxLength={DESCRIPTION_MAX_LENGTH}
							value={description}
							onChange={(e) => setDescription(e.target.value)}
							placeholder="Optional event details"
						/>
						<span
							data-testid="description-char-count"
							className="text-muted-foreground text-xs"
						>
							{description.length}/{DESCRIPTION_MAX_LENGTH}
						</span>
					</div>

					{/* Buttons */}
					<div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
						<AlertDialogPrimitive.Cancel asChild>
							<Button variant="outline" disabled={loading}>
								Cancel
							</Button>
						</AlertDialogPrimitive.Cancel>
						<Button disabled={loading || !isFormValid} onClick={handleConfirm}>
							Save
						</Button>
					</div>
				</AlertDialogPrimitive.Content>
			</AlertDialogPrimitive.Portal>
		</AlertDialogPrimitive.Root>
	);
}
