"use client";

/**
 * Dialog for capturing rejection details during Rejected status transition.
 *
 * REQ-012 §11.6: Rejection details form with pre-populated stage.
 * Triggered from StatusTransitionDropdown when user selects Rejected,
 * or from the RejectionDetailsCard Edit button.
 */

import { useCallback, useState } from "react";

import { FormAlertDialog } from "@/components/ui/form-alert-dialog";
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
import type { RejectionDetails } from "@/types/application";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const FIELD_WRAPPER_CLASS = "space-y-1";
const REJECTION_REASON_MAX_LENGTH = 500;
const REJECTION_FEEDBACK_MAX_LENGTH = 2_000;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface RejectionDetailsDialogProps {
	open: boolean;
	onConfirm: (details: RejectionDetails) => void;
	onCancel: () => void;
	loading?: boolean;
	initialData?: RejectionDetails | null;
	initialStage?: string | null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function RejectionDetailsDialog({
	open,
	onConfirm,
	onCancel,
	loading = false,
	initialData,
	initialStage,
}: Readonly<RejectionDetailsDialogProps>) {
	const [form, setForm] = useState<RejectionDetails>({});

	// Adjust state when dialog opens (React "deriving state from props" pattern)
	const [prevOpen, setPrevOpen] = useState(false);
	if (open !== prevOpen) {
		setPrevOpen(open);
		if (open) {
			if (initialData) {
				setForm({ ...initialData });
			} else if (initialStage) {
				setForm({ stage: initialStage });
			} else {
				setForm({});
			}
		}
	}

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	const updateString = useCallback(
		(key: keyof RejectionDetails, value: string) => {
			setForm((prev) => ({
				...prev,
				[key]: value === "" ? undefined : value,
			}));
		},
		[],
	);

	const handleConfirm = useCallback(() => {
		onConfirm(form);
	}, [form, onConfirm]);

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
		<FormAlertDialog
			open={open}
			onOpenChange={handleOpenChange}
			title="Rejection Details"
			description="Capture rejection details. All fields are optional."
			loading={loading}
			onConfirm={handleConfirm}
		>
			{/* Form fields */}
			<div className="grid grid-cols-2 gap-4">
				{/* Stage */}
				<div className={FIELD_WRAPPER_CLASS}>
					<Label htmlFor="rejection-stage">Stage</Label>
					<Select
						value={form.stage ?? ""}
						onValueChange={(v) => updateString("stage", v)}
					>
						<SelectTrigger
							id="rejection-stage"
							data-testid="rejection-stage-select"
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

				{/* When */}
				<div className={FIELD_WRAPPER_CLASS}>
					<Label htmlFor="rejection-when">When</Label>
					<Input
						id="rejection-when"
						type="datetime-local"
						value={form.rejected_at ?? ""}
						onChange={(e) => updateString("rejected_at", e.target.value)}
					/>
				</div>
			</div>

			{/* Reason */}
			<div className={FIELD_WRAPPER_CLASS}>
				<Label htmlFor="rejection-reason">Reason</Label>
				<Input
					id="rejection-reason"
					maxLength={REJECTION_REASON_MAX_LENGTH}
					value={form.reason ?? ""}
					onChange={(e) => updateString("reason", e.target.value)}
					placeholder="e.g., Culture fit concerns"
				/>
			</div>

			{/* Feedback */}
			<div className={FIELD_WRAPPER_CLASS}>
				<Label htmlFor="rejection-feedback">Feedback</Label>
				<Textarea
					id="rejection-feedback"
					rows={3}
					maxLength={REJECTION_FEEDBACK_MAX_LENGTH}
					value={form.feedback ?? ""}
					onChange={(e) => updateString("feedback", e.target.value)}
					placeholder="e.g., Looking for more senior candidate"
				/>
			</div>
		</FormAlertDialog>
	);
}
