"use client";

/**
 * Education form for adding/editing an education entry.
 *
 * REQ-012 §6.3.4: Fields — degree, field_of_study, institution,
 * graduation_year (required), gpa, honors (optional).
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { useCallback } from "react";
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

const MAX_INSTITUTION_LENGTH = 255;
const MAX_DEGREE_LENGTH = 100;
const MAX_FIELD_LENGTH = 255;
const MAX_HONORS_LENGTH = 255;
const MIN_GRADUATION_YEAR = 1950;
const MAX_GRADUATION_YEAR = 2100;
const MAX_GPA = 4.0;

/** Shared two-column grid layout class. */
const GRID_TWO_COL = "grid gap-4 sm:grid-cols-2";

// ---------------------------------------------------------------------------
// Validation schema
// ---------------------------------------------------------------------------

/**
 * Numeric fields stored as strings in the form (HTML inputs return strings).
 * Conversion to numbers happens in toRequestBody() at the step level.
 */
const educationFormSchema = z.object({
	institution: z
		.string()
		.min(1, { message: "Institution is required" })
		.max(MAX_INSTITUTION_LENGTH, { message: "Institution name is too long" }),
	degree: z
		.string()
		.min(1, { message: "Degree is required" })
		.max(MAX_DEGREE_LENGTH, { message: "Degree is too long" }),
	field_of_study: z
		.string()
		.min(1, { message: "Field of study is required" })
		.max(MAX_FIELD_LENGTH, { message: "Field of study is too long" }),
	graduation_year: z
		.string()
		.min(1, { message: "Graduation year is required" })
		.refine((val) => /^\d{4}$/.test(val), {
			message: "Enter a valid 4-digit year",
		})
		.refine(
			(val) => {
				const year = Number.parseInt(val, 10);
				return year >= MIN_GRADUATION_YEAR;
			},
			{ message: `Year must be ${MIN_GRADUATION_YEAR} or later` },
		)
		.refine(
			(val) => {
				const year = Number.parseInt(val, 10);
				return year <= MAX_GRADUATION_YEAR;
			},
			{ message: `Year must be ${MAX_GRADUATION_YEAR} or earlier` },
		),
	gpa: z
		.string()
		.optional()
		.or(z.literal(""))
		.refine(
			(val) => {
				if (!val || val === "") return true;
				const num = Number.parseFloat(val);
				return !Number.isNaN(num) && num >= 0 && num <= MAX_GPA;
			},
			{ message: `GPA must be between 0 and ${MAX_GPA}` },
		),
	honors: z
		.string()
		.max(MAX_HONORS_LENGTH, "Honors is too long")
		.optional()
		.or(z.literal("")),
});

export type EducationFormData = z.infer<typeof educationFormSchema>;

/** Default form values for a new entry. */
const DEFAULT_VALUES: EducationFormData = {
	institution: "",
	degree: "",
	field_of_study: "",
	graduation_year: "",
	gpa: "",
	honors: "",
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface EducationFormProps {
	/** Pre-fill values for editing. Omit for add mode. */
	initialValues?: Partial<EducationFormData>;
	/** Called with validated form data on save. */
	onSave: (data: EducationFormData) => Promise<void>;
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

export function EducationForm({
	initialValues,
	onSave,
	onCancel,
	isSubmitting,
	submitError,
}: Readonly<EducationFormProps>) {
	const defaultVals: EducationFormData = {
		...DEFAULT_VALUES,
		...initialValues,
	};

	const form = useForm<EducationFormData>({
		resolver: zodResolver(educationFormSchema),
		defaultValues: defaultVals,
		mode: "onTouched",
	});

	const handleSubmit = useCallback(
		async (data: EducationFormData) => {
			await onSave(data);
		},
		[onSave],
	);

	return (
		<div data-testid="education-form">
			<Form {...form}>
				<form
					onSubmit={form.handleSubmit(handleSubmit)}
					className="space-y-4"
					noValidate
				>
					<FormInputField
						control={form.control}
						name="institution"
						label="Institution"
						placeholder="MIT"
					/>

					<div className={GRID_TWO_COL}>
						<FormInputField
							control={form.control}
							name="degree"
							label="Degree"
							placeholder="Bachelor of Science"
						/>
						<FormInputField
							control={form.control}
							name="field_of_study"
							label="Field of Study"
							placeholder="Computer Science"
						/>
					</div>

					<div className={GRID_TWO_COL}>
						<FormField
							control={form.control}
							name="graduation_year"
							render={({ field }) => (
								<FormItem>
									<FormLabel>Graduation Year</FormLabel>
									<FormControl>
										<Input type="number" placeholder="2020" {...field} />
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>
						<FormField
							control={form.control}
							name="gpa"
							render={({ field }) => (
								<FormItem>
									<FormLabel>GPA (optional)</FormLabel>
									<FormControl>
										<Input
											type="number"
											step="0.01"
											placeholder="3.80"
											{...field}
											value={field.value ?? ""}
										/>
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>
					</div>

					<FormInputField
						control={form.control}
						name="honors"
						label="Honors (optional)"
						placeholder="Magna Cum Laude"
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
