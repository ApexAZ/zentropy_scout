/**
 * Shared form fields for the growth targets editor and onboarding step.
 *
 * REQ-012 §6.3.9 / §7.2.8: Tag inputs for target roles and skills,
 * and a stretch appetite radio group with descriptions — identical
 * fields used by both the onboarding wizard step and the post-onboarding
 * editor.
 */

import type { UseFormReturn } from "react-hook-form";

import { FormErrorSummary } from "@/components/form/form-error-summary";
import { FormTagField } from "@/components/form/form-tag-field";
import {
	FormControl,
	FormField,
	FormItem,
	FormMessage,
} from "@/components/ui/form";
import { STRETCH_DESCRIPTIONS } from "@/lib/growth-targets-helpers";
import type { GrowthTargetsFormData } from "@/lib/growth-targets-helpers";
import { STRETCH_APPETITES } from "@/types/persona";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface GrowthTargetsFormFieldsProps {
	/** React Hook Form instance for the growth targets form. */
	form: UseFormReturn<GrowthTargetsFormData>;
	/** API submission error message, if any. */
	submitError: string | null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Renders growth targets form fields (2 tag inputs + stretch appetite
 * radio group) plus the error summary and submit error alert. Consumers
 * provide their own `<form>` wrapper, submit button, and navigation.
 */
function GrowthTargetsFormFields({
	form,
	submitError,
}: Readonly<GrowthTargetsFormFieldsProps>) {
	return (
		<>
			{/* Target Roles */}
			<FormTagField
				control={form.control}
				name="target_roles"
				label="Target Roles"
				placeholder="e.g., Engineering Manager, Staff Engineer"
				description="Roles you aspire to grow into"
				maxItems={20}
			/>

			{/* Target Skills */}
			<FormTagField
				control={form.control}
				name="target_skills"
				label="Target Skills"
				placeholder="e.g., Kubernetes, People Management"
				description="Skills you want to develop"
				maxItems={20}
			/>

			{/* Stretch Appetite */}
			<FormField
				control={form.control}
				name="stretch_appetite"
				render={({ field }) => (
					<FormItem>
						<span className="text-sm leading-none font-medium">
							Stretch Appetite
						</span>
						<FormControl>
							<div
								className="space-y-3"
								role="radiogroup"
								aria-label="Stretch Appetite"
							>
								{STRETCH_APPETITES.map((level) => (
									<label
										key={level}
										aria-label={level}
										className="hover:bg-accent flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors"
									>
										<input
											type="radio"
											name={field.name}
											value={level}
											checked={field.value === level}
											onChange={() => field.onChange(level)}
											className="text-primary mt-0.5 h-4 w-4"
										/>
										<div>
											<span className="font-medium">{level}</span>
											<p className="text-muted-foreground text-sm">
												{STRETCH_DESCRIPTIONS[level]}
											</p>
										</div>
									</label>
								))}
							</div>
						</FormControl>
						<FormMessage />
					</FormItem>
				)}
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
		</>
	);
}

export { GrowthTargetsFormFields };
export type { GrowthTargetsFormFieldsProps };
