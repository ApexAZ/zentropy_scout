"use client";

/**
 * Dialog for capturing rejection details during Rejected status transition.
 *
 * REQ-012 §11.6: Rejection details form with pre-populated stage.
 * Triggered from StatusTransitionDropdown when user selects Rejected,
 * or from the RejectionDetailsCard Edit button.
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
}: RejectionDetailsDialogProps) {
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
							Rejection Details
						</AlertDialogPrimitive.Title>
						<AlertDialogPrimitive.Description className="text-muted-foreground text-sm">
							Capture rejection details. All fields are optional.
						</AlertDialogPrimitive.Description>
					</div>

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

					{/* Buttons */}
					<div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
						<AlertDialogPrimitive.Cancel asChild>
							<Button variant="outline" disabled={loading}>
								Cancel
							</Button>
						</AlertDialogPrimitive.Cancel>
						<Button disabled={loading} onClick={handleConfirm}>
							Save
						</Button>
					</div>
				</AlertDialogPrimitive.Content>
			</AlertDialogPrimitive.Portal>
		</AlertDialogPrimitive.Root>
	);
}
