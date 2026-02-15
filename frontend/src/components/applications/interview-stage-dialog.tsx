"use client";

/**
 * Dialog for selecting interview stage during Interviewing status transition.
 *
 * REQ-012 §11.3: When transitioning to Interviewing, prompt for stage:
 * Phone Screen, Onsite, or Final Round.
 */

import { useState } from "react";
import { AlertDialog as AlertDialogPrimitive } from "radix-ui";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { INTERVIEW_STAGES } from "@/types/application";
import type { InterviewStage } from "@/types/application";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface InterviewStageDialogProps {
	open: boolean;
	onConfirm: (stage: InterviewStage) => void;
	onCancel: () => void;
	loading?: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function InterviewStageDialog({
	open,
	onConfirm,
	onCancel,
	loading = false,
}: InterviewStageDialogProps) {
	const [selectedStage, setSelectedStage] = useState<InterviewStage | "">("");

	const handleConfirm = () => {
		if (selectedStage) {
			onConfirm(selectedStage);
		}
	};

	const handleOpenChange = (isOpen: boolean) => {
		if (!isOpen) {
			onCancel();
			setSelectedStage("");
		}
	};

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
							Select Interview Stage
						</AlertDialogPrimitive.Title>
						<AlertDialogPrimitive.Description className="text-muted-foreground text-sm">
							Choose the interview stage for this application.
						</AlertDialogPrimitive.Description>
					</div>

					<RadioGroup
						value={selectedStage}
						onValueChange={(v) => {
							if (INTERVIEW_STAGES.includes(v as InterviewStage)) {
								setSelectedStage(v as InterviewStage);
							}
						}}
						className="gap-3"
					>
						{INTERVIEW_STAGES.map((stage) => (
							<div key={stage} className="flex items-center gap-2">
								<RadioGroupItem value={stage} id={`stage-${stage}`} />
								<Label htmlFor={`stage-${stage}`}>{stage}</Label>
							</div>
						))}
					</RadioGroup>

					<div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
						<AlertDialogPrimitive.Cancel asChild>
							<Button variant="outline" disabled={loading}>
								Cancel
							</Button>
						</AlertDialogPrimitive.Cancel>
						<Button
							disabled={loading || !selectedStage}
							onClick={handleConfirm}
						>
							Confirm
						</Button>
					</div>
				</AlertDialogPrimitive.Content>
			</AlertDialogPrimitive.Portal>
		</AlertDialogPrimitive.Root>
	);
}
