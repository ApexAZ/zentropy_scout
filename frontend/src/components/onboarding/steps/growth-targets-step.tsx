"use client";

/**
 * Growth targets step for onboarding wizard (Step 9).
 *
 * REQ-012 §6.3.9: Form with tag inputs for target roles and skills,
 * and a stretch appetite radio group with descriptions
 * (Low / Medium / High, default Medium).
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Loader2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { FormErrorSummary } from "@/components/form/form-error-summary";
import { FormTagField } from "@/components/form/form-tag-field";
import { Button } from "@/components/ui/button";
import {
	Form,
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { apiGet, apiPatch } from "@/lib/api-client";
import { toFriendlyError } from "@/lib/form-errors";
import { useOnboarding } from "@/lib/onboarding-provider";
import type { ApiListResponse } from "@/types/api";
import type { Persona } from "@/types/persona";
import { STRETCH_APPETITES } from "@/types/persona";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Stretch appetite option descriptions shown below each radio. */
const STRETCH_DESCRIPTIONS: Readonly<Record<string, string>> = {
	Low: "Show me roles I'm already qualified for",
	Medium: "Mix of comfortable and stretch roles",
	High: "Challenge me — I want to grow into new areas",
};

// ---------------------------------------------------------------------------
// Validation schema
// ---------------------------------------------------------------------------

const growthTargetsSchema = z.object({
	target_roles: z.array(z.string().trim().min(1).max(100)).max(20),
	target_skills: z.array(z.string().trim().min(1).max(100)).max(20),
	stretch_appetite: z.enum(
		STRETCH_APPETITES as unknown as [string, ...string[]],
	),
});

type GrowthTargetsFormData = z.infer<typeof growthTargetsSchema>;

const DEFAULT_VALUES: GrowthTargetsFormData = {
	target_roles: [],
	target_skills: [],
	stretch_appetite: "Medium",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Onboarding Step 9: Growth Targets.
 *
 * Renders a form with tag inputs for target roles and skills, and a
 * stretch appetite radio group. On valid submission, PATCHes the
 * persona and advances to the next step.
 */
export function GrowthTargetsStep() {
	const { personaId, next, back } = useOnboarding();

	const [isLoadingPersona, setIsLoadingPersona] = useState(!!personaId);
	const [submitError, setSubmitError] = useState<string | null>(null);
	const [isSubmitting, setIsSubmitting] = useState(false);

	const form = useForm<GrowthTargetsFormData>({
		resolver: zodResolver(growthTargetsSchema),
		defaultValues: DEFAULT_VALUES,
		mode: "onTouched",
	});

	const { reset } = form;

	// -----------------------------------------------------------------------
	// Pre-fill from persona data
	// -----------------------------------------------------------------------

	useEffect(() => {
		if (!personaId) return;

		let cancelled = false;

		apiGet<ApiListResponse<Persona>>("/personas")
			.then((res) => {
				if (cancelled) return;
				const persona = res.data[0];
				if (persona) {
					reset({
						target_roles: persona.target_roles ?? [],
						target_skills: persona.target_skills ?? [],
						stretch_appetite: persona.stretch_appetite ?? "Medium",
					});
				}
			})
			.catch(() => {
				// Pre-fill failed — user can fill manually
			})
			.finally(() => {
				if (!cancelled) setIsLoadingPersona(false);
			});

		return () => {
			cancelled = true;
		};
	}, [personaId, reset]);

	// -----------------------------------------------------------------------
	// Submit handler
	// -----------------------------------------------------------------------

	const onSubmit = useCallback(
		async (data: GrowthTargetsFormData) => {
			if (!personaId) return;

			setSubmitError(null);
			setIsSubmitting(true);

			try {
				await apiPatch(`/personas/${personaId}`, {
					target_roles: data.target_roles,
					target_skills: data.target_skills,
					stretch_appetite: data.stretch_appetite,
				});
				next();
			} catch (err) {
				setIsSubmitting(false);
				setSubmitError(toFriendlyError(err));
			}
		},
		[personaId, next],
	);

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	if (isLoadingPersona) {
		return (
			<div
				className="flex flex-1 flex-col items-center justify-center"
				data-testid="loading-growth-targets"
			>
				<Loader2 className="text-primary h-8 w-8 animate-spin" />
				<p className="text-muted-foreground mt-3">
					Loading your growth targets...
				</p>
			</div>
		);
	}

	return (
		<div className="flex flex-1 flex-col gap-6">
			<div className="text-center">
				<h2 className="text-lg font-semibold">Growth Targets</h2>
				<p className="text-muted-foreground mt-1">
					Where are you headed? Define the roles and skills you want to grow
					into.
				</p>
			</div>

			<Form {...form}>
				<form
					id="growth-targets-form"
					onSubmit={form.handleSubmit(onSubmit)}
					className="space-y-6"
					data-testid="growth-targets-form"
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
								<FormLabel>Stretch Appetite</FormLabel>
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
				</form>
			</Form>

			{/* Navigation */}
			<div className="flex items-center justify-between pt-4">
				<Button
					type="button"
					variant="ghost"
					onClick={back}
					data-testid="back-button"
				>
					<ArrowLeft className="mr-2 h-4 w-4" />
					Back
				</Button>
				<Button
					type="submit"
					form="growth-targets-form"
					disabled={isSubmitting}
					data-testid="submit-button"
				>
					{isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
					{isSubmitting ? "Saving..." : "Next"}
				</Button>
			</div>
		</div>
	);
}
