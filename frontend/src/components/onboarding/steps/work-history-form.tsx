"use client";

/**
 * Work history form for adding/editing a job entry.
 *
 * REQ-012 §6.3.3: Fields — title, company, dates, location, work model.
 * Conditional end_date validation when is_current is false.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { useCallback, useEffect } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { FormActionFooter } from "@/components/form/form-action-footer";
import { FormInputField } from "@/components/form/form-input-field";
import { FormTextareaField } from "@/components/form/form-textarea-field";
import { Checkbox } from "@/components/ui/checkbox";
import {
	Form,
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { WORK_MODELS } from "@/types/persona";
import type { WorkModel } from "@/types/persona";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Max length for text fields. */
const MAX_TEXT_LENGTH = 255;

/** Max length for industry field. */
const MAX_INDUSTRY_LENGTH = 100;

/** Max length for description. */
const MAX_DESCRIPTION_LENGTH = 5000;

/** Shared two-column grid layout class. */
const GRID_TWO_COL = "grid gap-4 sm:grid-cols-2";

/** Expected format for month input values. */
const MONTH_PATTERN = /^\d{4}-(0[1-9]|1[0-2])$/;

// ---------------------------------------------------------------------------
// Validation schema
// ---------------------------------------------------------------------------

const workHistoryFormSchema = z
	.object({
		job_title: z
			.string()
			.min(1, { message: "Job title is required" })
			.max(MAX_TEXT_LENGTH, { message: "Job title is too long" }),
		company_name: z
			.string()
			.min(1, { message: "Company name is required" })
			.max(MAX_TEXT_LENGTH, { message: "Company name is too long" }),
		company_industry: z
			.string()
			.max(MAX_INDUSTRY_LENGTH, { message: "Industry is too long" })
			.optional()
			.or(z.literal("")),
		location: z
			.string()
			.min(1, { message: "Location is required" })
			.max(MAX_TEXT_LENGTH, { message: "Location is too long" }),
		work_model: z.enum(["Remote", "Hybrid", "Onsite"] as const, {
			message: "Work model is required",
		}),
		start_date: z
			.string()
			.min(1, { message: "Start date is required" })
			.regex(MONTH_PATTERN, { message: "Invalid date format" }),
		end_date: z
			.string()
			.regex(MONTH_PATTERN, { message: "Invalid date format" })
			.optional()
			.or(z.literal("")),
		is_current: z.boolean(),
		description: z
			.string()
			.max(MAX_DESCRIPTION_LENGTH, { message: "Description is too long" })
			.optional()
			.or(z.literal("")),
	})
	.refine(
		(data) => data.is_current || (data.end_date && data.end_date.length > 0),
		{ message: "End date is required when not current", path: ["end_date"] },
	);

export type WorkHistoryFormData = z.infer<typeof workHistoryFormSchema>;

/** Default form values for a new entry. */
const DEFAULT_VALUES: WorkHistoryFormData = {
	job_title: "",
	company_name: "",
	company_industry: "",
	location: "",
	work_model: "Remote",
	start_date: "",
	end_date: "",
	is_current: false,
	description: "",
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface WorkHistoryFormProps {
	/** Pre-fill values for editing. Omit for add mode. */
	initialValues?: Partial<WorkHistoryFormData>;
	/** Called with validated form data on save. */
	onSave: (data: WorkHistoryFormData) => Promise<void>;
	/** Called when user cancels. */
	onCancel: () => void;
	/** Whether the form is currently submitting. */
	isSubmitting: boolean;
	/** Error message to display below the form. */
	submitError: string | null;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Convert YYYY-MM-DD to YYYY-MM for the month input. */
export function toMonthValue(isoDate: string | null | undefined): string {
	if (!isoDate) return "";
	return isoDate.slice(0, 7); // "2020-01-01" → "2020-01"
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function WorkHistoryForm({
	initialValues,
	onSave,
	onCancel,
	isSubmitting,
	submitError,
}: Readonly<WorkHistoryFormProps>) {
	const defaultVals: WorkHistoryFormData = {
		...DEFAULT_VALUES,
		...initialValues,
	};

	const form = useForm<WorkHistoryFormData>({
		resolver: zodResolver(workHistoryFormSchema),
		defaultValues: defaultVals,
		mode: "onTouched",
	});

	const isCurrent = useWatch({ control: form.control, name: "is_current" });

	// Clear end_date when is_current is toggled on
	useEffect(() => {
		if (isCurrent) {
			form.setValue("end_date", "", { shouldValidate: true });
		}
	}, [isCurrent, form]);

	const handleSubmit = useCallback(
		async (data: WorkHistoryFormData) => {
			await onSave(data);
		},
		[onSave],
	);

	return (
		<div data-testid="work-history-form">
			<Form {...form}>
				<form
					onSubmit={form.handleSubmit(handleSubmit)}
					className="space-y-4"
					noValidate
				>
					<FormInputField
						control={form.control}
						name="job_title"
						label="Job Title"
						placeholder="Software Engineer"
					/>

					<div className={GRID_TWO_COL}>
						<FormInputField
							control={form.control}
							name="company_name"
							label="Company Name"
							placeholder="Acme Corp"
						/>
						<FormInputField
							control={form.control}
							name="company_industry"
							label="Industry"
							placeholder="Technology"
						/>
					</div>

					<div className={GRID_TWO_COL}>
						<FormInputField
							control={form.control}
							name="location"
							label="Location"
							placeholder="San Francisco, CA"
						/>
						<FormField
							control={form.control}
							name="work_model"
							render={({ field }) => (
								<FormItem>
									<FormLabel>Work Model</FormLabel>
									<FormControl>
										<select
											className="border-input bg-background ring-offset-background placeholder:text-muted-foreground focus-visible:ring-ring flex h-9 w-full rounded-md border px-3 py-1 text-base shadow-sm transition-colors focus-visible:ring-1 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50 md:text-sm"
											{...field}
										>
											<option value="">Select work model</option>
											{WORK_MODELS.map((model: WorkModel) => (
												<option key={model} value={model}>
													{model}
												</option>
											))}
										</select>
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>
					</div>

					<div className={GRID_TWO_COL}>
						<FormField
							control={form.control}
							name="start_date"
							render={({ field }) => (
								<FormItem>
									<FormLabel>Start Date</FormLabel>
									<FormControl>
										<Input type="month" {...field} />
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>
						<FormField
							control={form.control}
							name="end_date"
							render={({ field }) => (
								<FormItem>
									<FormLabel>End Date</FormLabel>
									<FormControl>
										<Input type="month" disabled={isCurrent} {...field} />
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>
					</div>

					<FormField
						control={form.control}
						name="is_current"
						render={({ field }) => (
							<FormItem className="flex items-center gap-2">
								<FormControl>
									<Checkbox
										checked={field.value}
										onCheckedChange={field.onChange}
									/>
								</FormControl>
								<FormLabel className="!mt-0">This is my current role</FormLabel>
							</FormItem>
						)}
					/>

					<FormTextareaField
						control={form.control}
						name="description"
						label="Description"
						placeholder="Brief summary of your role and responsibilities"
						rows={3}
					/>

					<FormActionFooter
						submitError={submitError}
						isSubmitting={isSubmitting}
						onCancel={onCancel}
					/>
				</form>
			</Form>
		</div>
	);
}
