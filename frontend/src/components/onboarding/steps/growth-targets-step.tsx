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

import { GrowthTargetsFormFields } from "@/components/persona/growth-targets-form-fields";
import { Button } from "@/components/ui/button";
import { Form } from "@/components/ui/form";
import { apiGet, apiPatch } from "@/lib/api-client";
import { toFriendlyError } from "@/lib/form-errors";
import {
	GROWTH_TARGETS_DEFAULT_VALUES,
	growthTargetsSchema,
	toFormValues,
	toRequestBody,
} from "@/lib/growth-targets-helpers";
import type { GrowthTargetsFormData } from "@/lib/growth-targets-helpers";
import { useOnboarding } from "@/lib/onboarding-provider";
import type { ApiListResponse } from "@/types/api";
import type { Persona } from "@/types/persona";

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
		defaultValues: GROWTH_TARGETS_DEFAULT_VALUES,
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
						...GROWTH_TARGETS_DEFAULT_VALUES,
						...toFormValues(persona),
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
				await apiPatch(`/personas/${personaId}`, toRequestBody(data));
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
					<GrowthTargetsFormFields form={form} submitError={submitError} />
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
