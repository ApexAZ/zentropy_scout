"use client";

/**
 * @fileoverview Post-onboarding non-negotiables editor with sectioned form and custom filters.
 *
 * Layer: component
 * Feature: persona
 *
 * REQ-012 §7.2.7: Sectioned form for location preferences, compensation,
 * other filters, and embedded custom filters CRUD.
 *
 * Coordinates with:
 * - lib/api-client.ts: apiPatch for persona update
 * - lib/embedding-staleness.ts: notifyEmbeddingUpdate after non-negotiable changes
 * - lib/form-errors.ts: toFriendlyError for error display
 * - lib/non-negotiables-helpers.ts: schema, defaults, toFormValues, toRequestBody
 * - lib/query-keys.ts: queryKeys.personas cache key
 * - components/onboarding/steps/custom-filters-section.tsx: custom filters CRUD section
 * - components/persona/non-negotiables-form-fields.tsx: non-negotiables form fields
 * - components/ui/button.tsx: submit button
 * - components/ui/form.tsx: Form context provider
 * - types/persona.ts: Persona type
 *
 * Called by / Used by:
 * - app/(main)/persona/non-negotiables/page.tsx: non-negotiables page route
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";
import { useCallback, useState } from "react";
import { useForm } from "react-hook-form";

import { CustomFiltersSection } from "@/components/onboarding/steps/custom-filters-section";
import { NonNegotiablesFormFields } from "@/components/persona/non-negotiables-form-fields";
import { Button } from "@/components/ui/button";
import { Form } from "@/components/ui/form";
import { apiPatch } from "@/lib/api-client";
import { notifyEmbeddingUpdate } from "@/lib/embedding-staleness";
import { toFriendlyError } from "@/lib/form-errors";
import {
	NON_NEGOTIABLES_DEFAULT_VALUES,
	nonNegotiablesSchema,
	toFormValues,
	toRequestBody,
} from "@/lib/non-negotiables-helpers";
import type { NonNegotiablesFormData } from "@/lib/non-negotiables-helpers";
import { queryKeys } from "@/lib/query-keys";
import type { Persona } from "@/types/persona";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Post-onboarding editor for non-negotiable fields.
 *
 * Receives the current persona as a prop. Pre-fills the form from persona
 * data and saves changes via PATCH. Includes embedded CustomFiltersSection.
 */
export function NonNegotiablesEditor({
	persona,
}: Readonly<{ persona: Persona }>) {
	const personaId = persona.id;
	const queryClient = useQueryClient();

	// -----------------------------------------------------------------------
	// Form
	// -----------------------------------------------------------------------

	const form = useForm<NonNegotiablesFormData>({
		resolver: zodResolver(nonNegotiablesSchema),
		defaultValues: {
			...NON_NEGOTIABLES_DEFAULT_VALUES,
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
		async (data: NonNegotiablesFormData) => {
			setSubmitError(null);
			setSaveSuccess(false);
			setIsSubmitting(true);

			try {
				await apiPatch(`/personas/${personaId}`, toRequestBody(data));

				await queryClient.invalidateQueries({
					queryKey: queryKeys.personas,
				});
				notifyEmbeddingUpdate();
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
				<h2 className="text-lg font-semibold">Non-Negotiables</h2>
				<p className="text-muted-foreground mt-1">
					Set your location preferences, compensation, and other filters.
				</p>
			</div>

			<Form {...form}>
				<form
					onSubmit={form.handleSubmit(onSubmit)}
					className="space-y-6"
					data-testid="non-negotiables-editor-form"
					noValidate
				>
					<NonNegotiablesFormFields form={form} submitError={submitError} />

					{saveSuccess && (
						<div
							className="text-success text-sm font-medium"
							data-testid="save-success"
						>
							Non-negotiables saved.
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

			{/* Custom filters — separate CRUD section with own state/API calls */}
			<CustomFiltersSection personaId={personaId} />
		</div>
	);
}
