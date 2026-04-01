"use client";

/**
 * @fileoverview Post-onboarding growth targets editor with tag inputs and stretch appetite.
 *
 * Layer: component
 * Feature: persona
 *
 * REQ-012 §7.2.8: Tag inputs for target roles and skills, and a stretch
 * appetite radio group with descriptions. Pre-fills from persona prop,
 * PATCHes on save, invalidates cache.
 *
 * Coordinates with:
 * - lib/api-client.ts: apiPatch for persona update
 * - lib/form-errors.ts: toFriendlyError for error display
 * - lib/growth-targets-helpers.ts: schema, defaults, toFormValues, toRequestBody
 * - lib/query-keys.ts: queryKeys.personas cache key
 * - components/persona/growth-targets-form-fields.tsx: growth targets form fields
 * - components/ui/button.tsx: submit button
 * - components/ui/form.tsx: Form context provider
 * - types/persona.ts: Persona type
 *
 * Called by / Used by:
 * - app/(main)/persona/growth/page.tsx: growth targets page route
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";
import { useCallback, useState } from "react";
import { useForm } from "react-hook-form";

import { GrowthTargetsFormFields } from "@/components/persona/growth-targets-form-fields";
import { Button } from "@/components/ui/button";
import { Form } from "@/components/ui/form";
import { apiPatch } from "@/lib/api-client";
import { toFriendlyError } from "@/lib/form-errors";
import {
	GROWTH_TARGETS_DEFAULT_VALUES,
	growthTargetsSchema,
	toFormValues,
	toRequestBody,
} from "@/lib/growth-targets-helpers";
import type { GrowthTargetsFormData } from "@/lib/growth-targets-helpers";
import { queryKeys } from "@/lib/query-keys";
import type { Persona } from "@/types/persona";

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
					<GrowthTargetsFormFields form={form} submitError={submitError} />

					{saveSuccess && (
						<div
							className="text-success text-sm font-medium"
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
