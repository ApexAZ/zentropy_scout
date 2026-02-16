"use client";

/**
 * Post-onboarding growth targets editor (§6.11).
 *
 * REQ-012 §7.2.8: Simple form matching §6.3.9 — tag inputs for target
 * roles and skills, and a stretch appetite radio group with descriptions.
 * Pre-fills from persona prop, PATCHes on save, invalidates cache.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";
import { useCallback, useState } from "react";
import { useForm } from "react-hook-form";

import { FormErrorSummary } from "@/components/form/form-error-summary";
import { FormTagField } from "@/components/form/form-tag-field";
import { Button } from "@/components/ui/button";
import {
	Form,
	FormControl,
	FormField,
	FormItem,
	FormMessage,
} from "@/components/ui/form";
import { apiPatch } from "@/lib/api-client";
import { toFriendlyError } from "@/lib/form-errors";
import {
	GROWTH_TARGETS_DEFAULT_VALUES,
	STRETCH_DESCRIPTIONS,
	growthTargetsSchema,
	toFormValues,
	toRequestBody,
} from "@/lib/growth-targets-helpers";
import type { GrowthTargetsFormData } from "@/lib/growth-targets-helpers";
import { queryKeys } from "@/lib/query-keys";
import type { Persona } from "@/types/persona";
import { STRETCH_APPETITES } from "@/types/persona";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Post-onboarding editor for growth target fields.
 *
 * Receives the current persona as a prop. Pre-fills the form from persona
 * data and saves changes via PATCH.
 */
export function GrowthTargetsEditor({
	persona,
}: Readonly<{ persona: Persona }>) {
	const personaId = persona.id;
	const queryClient = useQueryClient();

	// -----------------------------------------------------------------------
	// Form
	// -----------------------------------------------------------------------

	const form = useForm<GrowthTargetsFormData>({
		resolver: zodResolver(growthTargetsSchema),
		defaultValues: {
			...GROWTH_TARGETS_DEFAULT_VALUES,
			...toFormValues(persona),
		},
		mode: "onTouched",
	});

	const [submitError, setSubmitError] = useState<string | null>(null);
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [saveSuccess, setSaveSuccess] = useState(false);

	// -----------------------------------------------------------------------
	// Submit handler
	// -----------------------------------------------------------------------

	const onSubmit = useCallback(
		async (data: GrowthTargetsFormData) => {
			setSubmitError(null);
			setSaveSuccess(false);
			setIsSubmitting(true);

			try {
				await apiPatch(`/personas/${personaId}`, toRequestBody(data));

				await queryClient.invalidateQueries({
					queryKey: queryKeys.personas,
				});
				setSaveSuccess(true);
			} catch (err) {
				setSubmitError(toFriendlyError(err));
			} finally {
				setIsSubmitting(false);
			}
		},
		[personaId, queryClient],
	);

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	return (
		<div className="flex flex-1 flex-col gap-6">
			<div>
				<h2 className="text-lg font-semibold">Growth Targets</h2>
				<p className="text-muted-foreground mt-1">
					Define the roles and skills you want to grow into.
				</p>
			</div>

			<Form {...form}>
				<form
					onSubmit={form.handleSubmit(onSubmit)}
					className="space-y-6"
					data-testid="growth-targets-editor-form"
					noValidate
				>
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

					{saveSuccess && (
						<div
							className="text-sm font-medium text-green-600"
							data-testid="save-success"
						>
							Growth targets saved.
						</div>
					)}

					<div className="flex items-center justify-between pt-4">
						<Link
							href="/persona"
							className="text-muted-foreground hover:text-foreground inline-flex items-center text-sm"
						>
							<ArrowLeft className="mr-2 h-4 w-4" />
							Back to Profile
						</Link>
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
