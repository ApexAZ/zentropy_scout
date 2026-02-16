"use client";

/**
 * Form for adding/editing a custom non-negotiable filter.
 *
 * REQ-012 §6.3.8: Filter name, type (Exclude/Require), field to
 * check (dropdown with suggestions + custom), and value to match.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { useCallback, useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { FormErrorSummary } from "@/components/form/form-error-summary";
import { FormInputField } from "@/components/form/form-input-field";
import { Button } from "@/components/ui/button";
import {
	Form,
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Suggested job fields for the filter_field dropdown. */
const FIELD_SUGGESTIONS = [
	{ value: "company_name", label: "Company Name" },
	{ value: "description", label: "Job Description" },
	{ value: "job_title", label: "Job Title" },
] as const;

const FILTER_TYPES = ["Exclude", "Require"] as const;

/** Sentinel value for the "Other (custom)" option in the field select. */
const OTHER_FIELD_VALUE = "other";

// ---------------------------------------------------------------------------
// Validation schema
// ---------------------------------------------------------------------------

const customFilterSchema = z.object({
	filter_name: z
		.string()
		.min(1, { message: "Filter name is required" })
		.max(255, { message: "Filter name is too long" }),
	filter_type: z.enum(FILTER_TYPES, {
		message: "Filter type is required",
	}),
	filter_field_select: z.string().min(1, { message: "Field is required" }),
	filter_field_custom: z
		.string()
		.max(100, { message: "Field name is too long" })
		.regex(/^[a-z_]*$/, {
			message: "Only lowercase letters and underscores allowed",
		}),
	filter_value: z
		.string()
		.min(1, { message: "Value is required" })
		.max(500, { message: "Value is too long" }),
});

export type CustomFilterFormData = z.infer<typeof customFilterSchema>;

const DEFAULT_VALUES: CustomFilterFormData = {
	filter_name: "",
	filter_type: "" as CustomFilterFormData["filter_type"],
	filter_field_select: "",
	filter_field_custom: "",
	filter_value: "",
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface CustomFilterFormProps {
	initialValues?: Partial<CustomFilterFormData>;
	onSave: (data: CustomFilterFormData) => Promise<void>;
	onCancel: () => void;
	isSubmitting: boolean;
	submitError: string | null;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Resolve the effective filter_field from form data.
 * If "other" is selected, use the custom text; otherwise use the select value.
 */
export function resolveFilterField(data: CustomFilterFormData): string {
	return data.filter_field_select === OTHER_FIELD_VALUE
		? data.filter_field_custom
		: data.filter_field_select;
}

/**
 * Convert an existing filter's field value into form initial values.
 * Maps the field string back to select + custom.
 */
export function fieldToFormValues(filterField: string): {
	filter_field_select: string;
	filter_field_custom: string;
} {
	const isPredefined = FIELD_SUGGESTIONS.some((s) => s.value === filterField);
	return isPredefined
		? { filter_field_select: filterField, filter_field_custom: "" }
		: {
				filter_field_select: OTHER_FIELD_VALUE,
				filter_field_custom: filterField,
			};
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CustomFilterForm({
	initialValues,
	onSave,
	onCancel,
	isSubmitting,
	submitError,
}: Readonly<CustomFilterFormProps>) {
	const form = useForm<CustomFilterFormData>({
		resolver: zodResolver(customFilterSchema),
		defaultValues: { ...DEFAULT_VALUES, ...initialValues },
		mode: "onTouched",
	});

	const watchedFieldSelect = form.watch("filter_field_select");
	const isOtherField = watchedFieldSelect === OTHER_FIELD_VALUE;

	// Clear custom field when switching away from "other"
	useEffect(() => {
		if (!isOtherField) {
			form.setValue("filter_field_custom", "", { shouldValidate: false });
		}
	}, [isOtherField, form]);

	const handleSubmit = useCallback(
		async (data: CustomFilterFormData) => {
			// Validate custom field when "other" is selected
			if (
				data.filter_field_select === OTHER_FIELD_VALUE &&
				!data.filter_field_custom.trim()
			) {
				form.setError("filter_field_custom", {
					message: "Custom field name is required",
				});
				return;
			}
			await onSave(data);
		},
		[onSave, form],
	);

	return (
		<div data-testid="custom-filter-form">
			<Form {...form}>
				<form
					onSubmit={form.handleSubmit(handleSubmit)}
					className="space-y-4"
					noValidate
				>
					<FormInputField
						control={form.control}
						name="filter_name"
						label="Filter Name"
						placeholder="e.g. No defense contractors"
					/>

					{/* Filter type radio buttons */}
					<FormField
						control={form.control}
						name="filter_type"
						render={({ field }) => (
							<FormItem>
								<FormLabel>Filter Type</FormLabel>
								<FormControl>
									<div
										className="flex gap-4"
										role="radiogroup"
										aria-label="Filter Type"
									>
										{FILTER_TYPES.map((type) => (
											<label
												key={type}
												className="flex cursor-pointer items-center gap-2"
											>
												<input
													type="radio"
													name={field.name}
													value={type}
													checked={field.value === type}
													onChange={() => field.onChange(type)}
													className="text-primary h-4 w-4"
												/>
												{type}
											</label>
										))}
									</div>
								</FormControl>
								<FormMessage />
							</FormItem>
						)}
					/>

					{/* Field to check — select with suggestions + "Other" */}
					<FormField
						control={form.control}
						name="filter_field_select"
						render={({ field }) => (
							<FormItem>
								<FormLabel>Field to Check</FormLabel>
								<FormControl>
									<select
										aria-label="Field to Check"
										className="border-input bg-background ring-offset-background focus-visible:ring-ring flex h-10 w-full rounded-md border px-3 py-2 text-sm focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50"
										value={field.value}
										onChange={(e) => field.onChange(e.target.value)}
										onBlur={field.onBlur}
										ref={field.ref as React.Ref<HTMLSelectElement>}
										name={field.name}
									>
										<option value="">Select field...</option>
										{FIELD_SUGGESTIONS.map((opt) => (
											<option key={opt.value} value={opt.value}>
												{opt.label}
											</option>
										))}
										<option value={OTHER_FIELD_VALUE}>Other (custom)</option>
									</select>
								</FormControl>
								<FormMessage />
							</FormItem>
						)}
					/>

					{/* Custom field name — shown when "Other" is selected */}
					{isOtherField && (
						<FormField
							control={form.control}
							name="filter_field_custom"
							render={({ field }) => (
								<FormItem>
									<FormLabel>Custom Field Name</FormLabel>
									<FormControl>
										<Input placeholder="e.g. benefits" {...field} />
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>
					)}

					<FormInputField
						control={form.control}
						name="filter_value"
						label="Value to Match"
						placeholder="e.g. Raytheon"
					/>

					<FormErrorSummary className="mt-2" />

					{submitError && (
						<div
							role="alert"
							className="text-destructive text-sm font-medium"
							data-testid="submit-error"
						>
							{submitError}
						</div>
					)}

					<div className="flex items-center justify-end gap-3 pt-2">
						<Button
							type="button"
							variant="ghost"
							onClick={onCancel}
							disabled={isSubmitting}
						>
							Cancel
						</Button>
						<Button type="submit" disabled={isSubmitting}>
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
