"use client";

/**
 * Education form for adding/editing an education entry.
 *
 * REQ-012 §6.3.4: Fields — degree, field_of_study, institution,
 * graduation_year (required), gpa, honors (optional).
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { useCallback } from "react";
import { useForm } from "react-hook-form";

import { FormActionFooter } from "@/components/form/form-action-footer";
import { FormInputField } from "@/components/form/form-input-field";
import {
	Form,
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
	educationFormSchema,
	type EducationFormData,
} from "@/lib/education-helpers";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Shared two-column grid layout class. */
const GRID_TWO_COL = "grid gap-4 sm:grid-cols-2";

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
