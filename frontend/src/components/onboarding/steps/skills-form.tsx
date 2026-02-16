"use client";

/**
 * Skills form for adding/editing a skill entry.
 *
 * REQ-012 §6.3.5: All 6 fields required — skill_name, skill_type,
 * category, proficiency, years_used, last_used.
 * Category dropdown changes based on skill_type.
 * Proficiency uses radio buttons per wireframe.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { useCallback, useEffect, useMemo } from "react";
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

const MAX_SKILL_NAME_LENGTH = 100;
const MAX_CATEGORY_LENGTH = 100;
const MAX_LAST_USED_LENGTH = 20;
const MAX_YEARS_USED = 70;

/** Shared two-column grid layout class. */
const GRID_TWO_COL = "grid gap-4 sm:grid-cols-2";

/** Hard skill category defaults (REQ-001 §3.4). */
export const HARD_SKILL_CATEGORIES = [
	"Programming Language",
	"Framework / Library",
	"Tool / Software",
	"Platform / Infrastructure",
	"Methodology",
	"Domain Knowledge",
] as const;

/** Soft skill category defaults (REQ-001 §3.4). */
export const SOFT_SKILL_CATEGORIES = [
	"Leadership & Management",
	"Communication",
	"Collaboration",
	"Problem Solving",
	"Adaptability",
] as const;

/** Proficiency levels with tooltip descriptions (REQ-001 §3.4). */
const PROFICIENCY_OPTIONS = [
	{
		value: "Learning",
		tooltip: "Currently studying, no professional use yet",
	},
	{
		value: "Familiar",
		tooltip: "Have used professionally, would need ramp-up time",
	},
	{
		value: "Proficient",
		tooltip: "Can work independently, solid experience",
	},
	{
		value: "Expert",
		tooltip: "Deep expertise, could teach others, go-to person",
	},
] as const;

// ---------------------------------------------------------------------------
// Validation schema
// ---------------------------------------------------------------------------

const skillFormSchema = z.object({
	skill_name: z
		.string()
		.min(1, { message: "Skill name is required" })
		.max(MAX_SKILL_NAME_LENGTH, { message: "Skill name is too long" }),
	skill_type: z.enum(["Hard", "Soft"], {
		message: "Skill type is required",
	}),
	category: z
		.string()
		.min(1, { message: "Category is required" })
		.max(MAX_CATEGORY_LENGTH, { message: "Category is too long" }),
	proficiency: z.enum(["Learning", "Familiar", "Proficient", "Expert"], {
		message: "Proficiency is required",
	}),
	years_used: z
		.string()
		.min(1, { message: "Years used is required" })
		.refine((val) => /^\d+$/.test(val), {
			message: "Enter a valid number",
		})
		.refine((val) => parseInt(val, 10) >= 1, {
			message: "Must be at least 1",
		})
		.refine((val) => parseInt(val, 10) <= MAX_YEARS_USED, {
			message: `Must be at most ${MAX_YEARS_USED}`,
		}),
	last_used: z
		.string()
		.min(1, { message: "Last used is required" })
		.max(MAX_LAST_USED_LENGTH, { message: "Last used is too long" }),
});

export type SkillFormData = z.infer<typeof skillFormSchema>;

/** Default form values for a new entry. */
const DEFAULT_VALUES: SkillFormData = {
	skill_name: "",
	skill_type: "" as SkillFormData["skill_type"],
	category: "",
	proficiency: "" as SkillFormData["proficiency"],
	years_used: "",
	last_used: "",
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SkillFormProps {
	/** Pre-fill values for editing. Omit for add mode. */
	initialValues?: Partial<SkillFormData>;
	/** Called with validated form data on save. */
	onSave: (data: SkillFormData) => Promise<void>;
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

export function SkillForm({
	initialValues,
	onSave,
	onCancel,
	isSubmitting,
	submitError,
}: Readonly<SkillFormProps>) {
	const defaultVals: SkillFormData = {
		...DEFAULT_VALUES,
		...initialValues,
	};

	const form = useForm<SkillFormData>({
		resolver: zodResolver(skillFormSchema),
		defaultValues: defaultVals,
		mode: "onTouched",
	});

	const watchedType = form.watch("skill_type");

	const categoryOptions = useMemo(
		() =>
			watchedType === "Hard"
				? HARD_SKILL_CATEGORIES
				: watchedType === "Soft"
					? SOFT_SKILL_CATEGORIES
					: [],
		[watchedType],
	);

	// Clear category when skill_type changes and current category is invalid
	useEffect(() => {
		const currentCategory = form.getValues("category");
		if (
			currentCategory &&
			categoryOptions.length > 0 &&
			!(categoryOptions as readonly string[]).includes(currentCategory)
		) {
			form.setValue("category", "", { shouldValidate: false });
		}
	}, [watchedType, categoryOptions, form]);

	const handleSubmit = useCallback(
		async (data: SkillFormData) => {
			await onSave(data);
		},
		[onSave],
	);

	return (
		<div data-testid="skills-form">
			<Form {...form}>
				<form
					onSubmit={form.handleSubmit(handleSubmit)}
					className="space-y-4"
					noValidate
				>
					<FormInputField
						control={form.control}
						name="skill_name"
						label="Skill Name"
						placeholder="Python"
					/>

					{/* Skill type radio buttons */}
					<FormField
						control={form.control}
						name="skill_type"
						render={({ field }) => (
							<FormItem>
								<FormLabel>Skill Type</FormLabel>
								<FormControl>
									<div
										className="flex gap-4"
										role="radiogroup"
										aria-label="Skill Type"
									>
										{(["Hard", "Soft"] as const).map((type) => (
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

					{/* Category select — options depend on skill_type */}
					<FormField
						control={form.control}
						name="category"
						render={({ field }) => (
							<FormItem>
								<FormLabel>Category</FormLabel>
								<FormControl>
									<select
										aria-label="Category"
										className="border-input bg-background ring-offset-background focus-visible:ring-ring flex h-10 w-full rounded-md border px-3 py-2 text-sm focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50"
										value={field.value}
										onChange={(e) => field.onChange(e.target.value)}
										onBlur={field.onBlur}
										ref={field.ref as React.Ref<HTMLSelectElement>}
										name={field.name}
										disabled={categoryOptions.length === 0}
									>
										<option value="">
											{categoryOptions.length === 0
												? "Select skill type first..."
												: "Select category..."}
										</option>
										{categoryOptions.map((cat) => (
											<option key={cat} value={cat}>
												{cat}
											</option>
										))}
									</select>
								</FormControl>
								<FormMessage />
							</FormItem>
						)}
					/>

					{/* Proficiency radio buttons */}
					<FormField
						control={form.control}
						name="proficiency"
						render={({ field }) => (
							<FormItem>
								<FormLabel>Proficiency</FormLabel>
								<FormControl>
									<div
										className="grid grid-cols-2 gap-2"
										role="radiogroup"
										aria-label="Proficiency"
									>
										{PROFICIENCY_OPTIONS.map((opt) => (
											<label
												key={opt.value}
												className="flex cursor-pointer items-center gap-2 rounded-md border p-2 text-sm"
												title={opt.tooltip}
											>
												<input
													type="radio"
													name={field.name}
													value={opt.value}
													checked={field.value === opt.value}
													onChange={() => field.onChange(opt.value)}
													className="text-primary h-4 w-4"
												/>
												{opt.value}
											</label>
										))}
									</div>
								</FormControl>
								<FormMessage />
							</FormItem>
						)}
					/>

					<div className={GRID_TWO_COL}>
						<FormField
							control={form.control}
							name="years_used"
							render={({ field }) => (
								<FormItem>
									<FormLabel>Years Used</FormLabel>
									<FormControl>
										<Input
											type="number"
											min="1"
											max={MAX_YEARS_USED}
											placeholder="5"
											{...field}
										/>
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>
						<FormInputField
							control={form.control}
							name="last_used"
							label="Last Used"
							placeholder="Current or 2024"
						/>
					</div>

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
