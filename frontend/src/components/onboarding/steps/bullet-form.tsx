"use client";

/**
 * Bullet form for adding/editing an accomplishment bullet.
 *
 * REQ-012 §6.3.3: Per-job bullet editing with text and optional metrics.
 * REQ-001 §3.2: Bullet fields — text (required), metrics (optional).
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { useCallback } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { FormErrorSummary } from "@/components/form/form-error-summary";
import { FormInputField } from "@/components/form/form-input-field";
import { FormTextareaField } from "@/components/form/form-textarea-field";
import { Button } from "@/components/ui/button";
import { Form } from "@/components/ui/form";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Max length for bullet text. */
const MAX_TEXT_LENGTH = 2000;

/** Max length for metrics field (matches DB VARCHAR(255)). */
const MAX_METRICS_LENGTH = 255;

// ---------------------------------------------------------------------------
// Validation schema
// ---------------------------------------------------------------------------

const bulletFormSchema = z.object({
	text: z
		.string()
		.min(1, "Bullet text is required")
		.max(MAX_TEXT_LENGTH, "Bullet text is too long"),
	metrics: z
		.string()
		.max(MAX_METRICS_LENGTH, "Metrics is too long")
		.optional()
		.or(z.literal("")),
});

export type BulletFormData = z.infer<typeof bulletFormSchema>;

/** Default form values for a new bullet. */
const DEFAULT_VALUES: BulletFormData = {
	text: "",
	metrics: "",
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface BulletFormProps {
	/** Pre-fill values for editing. Omit for add mode. */
	initialValues?: Partial<BulletFormData>;
	/** Called with validated form data on save. */
	onSave: (data: BulletFormData) => Promise<void>;
	/** Called when user cancels. */
	onCancel: () => void;
	/** Whether the form is currently submitting. */
	isSubmitting: boolean;
	/** Error message to display below the form. */
	submitError: string | null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function BulletForm({
	initialValues,
	onSave,
	onCancel,
	isSubmitting,
	submitError,
}: BulletFormProps) {
	const form = useForm<BulletFormData>({
		resolver: zodResolver(bulletFormSchema),
		defaultValues: { ...DEFAULT_VALUES, ...initialValues },
		mode: "onTouched",
	});

	const handleSubmit = useCallback(
		async (data: BulletFormData) => {
			await onSave(data);
		},
		[onSave],
	);

	return (
		<div data-testid="bullet-form">
			<Form {...form}>
				<form
					onSubmit={form.handleSubmit(handleSubmit)}
					className="space-y-3"
					noValidate
				>
					<FormTextareaField
						control={form.control}
						name="text"
						label="Bullet Text"
						placeholder="Describe an accomplishment or responsibility"
						rows={2}
					/>

					<FormInputField
						control={form.control}
						name="metrics"
						label="Metrics"
						placeholder="e.g., Reduced costs by 30%"
					/>

					<FormErrorSummary className="mt-2" />

					{submitError && (
						<div
							role="alert"
							className="text-destructive text-sm font-medium"
							data-testid="bullet-submit-error"
						>
							{submitError}
						</div>
					)}

					<div className="flex items-center justify-end gap-3 pt-1">
						<Button
							type="button"
							variant="ghost"
							size="sm"
							onClick={onCancel}
							disabled={isSubmitting}
						>
							Cancel
						</Button>
						<Button type="submit" size="sm" disabled={isSubmitting}>
							{isSubmitting && (
								<Loader2 className="mr-2 h-4 w-4 animate-spin" />
							)}
							{isSubmitting ? "Saving..." : "Save"}
						</Button>
					</div>
				</form>
			</Form>
		</div>
	);
}
