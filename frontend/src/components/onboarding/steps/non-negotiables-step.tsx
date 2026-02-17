"use client";

/**
 * Non-negotiables step for onboarding wizard (Step 8).
 *
 * REQ-012 §6.3.8: Form with sections for location preferences,
 * compensation, and other filters. Uses shared NonNegotiablesFormFields
 * component for the form body.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Loader2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useForm } from "react-hook-form";

import { NonNegotiablesFormFields } from "@/components/persona/non-negotiables-form-fields";
import { Button } from "@/components/ui/button";
import { Form } from "@/components/ui/form";
import { ApiError, apiGet, apiPatch } from "@/lib/api-client";
import {
	NON_NEGOTIABLES_DEFAULT_VALUES,
	nonNegotiablesSchema,
	toFormValues,
	toRequestBody,
} from "@/lib/non-negotiables-helpers";
import type { NonNegotiablesFormData } from "@/lib/non-negotiables-helpers";
import { useOnboarding } from "@/lib/onboarding-provider";
import type { ApiListResponse } from "@/types/api";
import type { Persona } from "@/types/persona";

import { CustomFiltersSection } from "./custom-filters-section";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Friendly error messages keyed by API error code. */
const FRIENDLY_ERROR_MESSAGES: Readonly<Record<string, string>> = {
	VALIDATION_ERROR: "Please check your input and try again.",
};

/** Fallback error message for unexpected errors. */
const GENERIC_ERROR_MESSAGE = "Failed to save. Please try again.";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Map an ApiError to a user-friendly message. */
function toFriendlyError(err: unknown): string {
	if (err instanceof ApiError) {
		return FRIENDLY_ERROR_MESSAGES[err.code] ?? GENERIC_ERROR_MESSAGE;
	}
	return GENERIC_ERROR_MESSAGE;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Onboarding Step 8: Non-Negotiables.
 *
 * Renders a multi-section form covering location preferences, compensation,
 * and other job filters. On valid submission, PATCHes the persona and
 * advances to the next step.
 */
export function NonNegotiablesStep() {
	const { personaId, next, back } = useOnboarding();

	const [isLoadingPersona, setIsLoadingPersona] = useState(!!personaId);
	const [submitError, setSubmitError] = useState<string | null>(null);
	const [isSubmitting, setIsSubmitting] = useState(false);

	const form = useForm<NonNegotiablesFormData>({
		resolver: zodResolver(nonNegotiablesSchema),
		defaultValues: NON_NEGOTIABLES_DEFAULT_VALUES,
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
						...NON_NEGOTIABLES_DEFAULT_VALUES,
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
		async (data: NonNegotiablesFormData) => {
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
				data-testid="loading-non-negotiables"
			>
				<Loader2 className="text-primary h-8 w-8 animate-spin" />
				<p className="text-muted-foreground mt-3">
					Loading your preferences...
				</p>
			</div>
		);
	}

	return (
		<div className="flex flex-1 flex-col gap-6">
			<div className="text-center">
				<h2 className="text-lg font-semibold">Non-Negotiables</h2>
				<p className="text-muted-foreground mt-1">
					Set your location preferences so we only surface jobs that fit.
				</p>
			</div>

			<Form {...form}>
				<form
					id="non-negotiables-form"
					onSubmit={form.handleSubmit(onSubmit)}
					className="space-y-6"
					data-testid="non-negotiables-form"
					noValidate
				>
					<NonNegotiablesFormFields form={form} submitError={submitError} />
				</form>

				{/* Custom filters — separate CRUD section with own <form> */}
				{personaId && <CustomFiltersSection personaId={personaId} />}

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
						form="non-negotiables-form"
						disabled={isSubmitting}
						data-testid="submit-button"
					>
						{isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
						{isSubmitting ? "Saving..." : "Next"}
					</Button>
				</div>
			</Form>
		</div>
	);
}
