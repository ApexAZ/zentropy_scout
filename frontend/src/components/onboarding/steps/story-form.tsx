"use client";

/**
 * Story form for adding/editing an achievement story entry.
 *
 * REQ-012 §6.3.7: Fields — title, context, action, outcome (required),
 * skills_demonstrated (optional checkboxes). Context/Action/Outcome
 * follows the CAO structured format.
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
import { Checkbox } from "@/components/ui/checkbox";
import {
	Form,
	FormControl,
	FormField,
	FormItem,
	FormLabel,
} from "@/components/ui/form";
import type { Skill } from "@/types/persona";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MAX_TITLE_LENGTH = 255;
const MAX_TEXT_LENGTH = 5000;

// ---------------------------------------------------------------------------
// Validation schema
// ---------------------------------------------------------------------------

const storyFormSchema = z.object({
	title: z
		.string()
		.min(1, "Title is required")
		.max(MAX_TITLE_LENGTH, "Title is too long"),
	context: z
		.string()
		.min(1, "Context is required")
		.max(MAX_TEXT_LENGTH, "Context is too long"),
	action: z
		.string()
		.min(1, "Action is required")
		.max(MAX_TEXT_LENGTH, "Action is too long"),
	outcome: z
		.string()
		.min(1, "Outcome is required")
		.max(MAX_TEXT_LENGTH, "Outcome is too long"),
	skills_demonstrated: z
		.array(z.string().uuid("Invalid skill ID"))
		.max(50, "Too many skills selected"),
});

export type StoryFormData = z.infer<typeof storyFormSchema>;

/** Default form values for a new entry. */
const DEFAULT_VALUES: StoryFormData = {
	title: "",
	context: "",
	action: "",
	outcome: "",
	skills_demonstrated: [],
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface StoryFormProps {
	/** Pre-fill values for editing. Omit for add mode. */
	initialValues?: Partial<StoryFormData>;
	/** Called with validated form data on save. */
	onSave: (data: StoryFormData) => Promise<void>;
	/** Called when user cancels. */
	onCancel: () => void;
	/** Whether the form is currently submitting. */
	isSubmitting: boolean;
	/** Error message to display below the form. */
	submitError: string | null;
	/** Available skills for the checkbox picker. */
	skills: Skill[];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function StoryForm({
	initialValues,
	onSave,
	onCancel,
	isSubmitting,
	submitError,
	skills,
}: StoryFormProps) {
	const defaultVals: StoryFormData = {
		...DEFAULT_VALUES,
		...initialValues,
	};

	const form = useForm<StoryFormData>({
		resolver: zodResolver(storyFormSchema),
		defaultValues: defaultVals,
		mode: "onTouched",
	});

	const handleSubmit = useCallback(
		async (data: StoryFormData) => {
			await onSave(data);
		},
		[onSave],
	);

	return (
		<div data-testid="story-form">
			<Form {...form}>
				<form
					onSubmit={form.handleSubmit(handleSubmit)}
					className="space-y-4"
					noValidate
				>
					<FormInputField
						control={form.control}
						name="title"
						label="Story Title"
						placeholder="e.g., Turned around failing project"
					/>

					<FormTextareaField
						control={form.control}
						name="context"
						label="Context"
						placeholder="What was the situation? (1-2 sentences)"
						rows={3}
					/>

					<FormTextareaField
						control={form.control}
						name="action"
						label="What did you do?"
						placeholder="Describe what actions you took."
						rows={3}
					/>

					<FormTextareaField
						control={form.control}
						name="outcome"
						label="Outcome"
						placeholder="What was the result? Quantify if possible."
						rows={3}
					/>

					{/* Skills demonstrated (optional) */}
					{skills.length > 0 && (
						<FormField
							control={form.control}
							name="skills_demonstrated"
							render={({ field }) => (
								<FormItem>
									<FormLabel>Skills Demonstrated (optional)</FormLabel>
									<div className="flex flex-wrap gap-3">
										{skills.map((skill) => (
											<div key={skill.id} className="flex items-center gap-2">
												<FormControl>
													<Checkbox
														checked={field.value.includes(skill.id)}
														onCheckedChange={(checked) => {
															if (checked) {
																field.onChange([...field.value, skill.id]);
															} else {
																field.onChange(
																	field.value.filter(
																		(id: string) => id !== skill.id,
																	),
																);
															}
														}}
														id={`skill-${skill.id}`}
													/>
												</FormControl>
												<label
													htmlFor={`skill-${skill.id}`}
													className="cursor-pointer text-sm"
												>
													{skill.skill_name}
												</label>
											</div>
										))}
									</div>
								</FormItem>
							)}
						/>
					)}

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
