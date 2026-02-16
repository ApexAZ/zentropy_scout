"use client";

/**
 * Post-onboarding discovery preferences editor (§6.11).
 *
 * REQ-012 §7.2.9: Two threshold sliders (0-100) with behavioral
 * explanations, polling frequency select, and cross-field validation
 * warning when auto-draft < minimum fit threshold.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";
import { useCallback, useState } from "react";
import { useForm } from "react-hook-form";

import { FormErrorSummary } from "@/components/form/form-error-summary";
import { Button } from "@/components/ui/button";
import {
	Form,
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { apiPatch } from "@/lib/api-client";
import {
	DISCOVERY_PREFERENCES_DEFAULT_VALUES,
	EXPLANATION_TEXT,
	THRESHOLD_WARNING,
	discoveryPreferencesSchema,
	toFormValues,
	toRequestBody,
} from "@/lib/discovery-preferences-helpers";
import type { DiscoveryPreferencesFormData } from "@/lib/discovery-preferences-helpers";
import { toFriendlyError } from "@/lib/form-errors";
import { queryKeys } from "@/lib/query-keys";
import type { Persona } from "@/types/persona";
import { POLLING_FREQUENCIES } from "@/types/persona";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Post-onboarding editor for discovery preference fields.
 *
 * Receives the current persona as a prop. Pre-fills sliders and select
 * from persona data. Shows behavioral explanations and a cross-field
 * validation warning.
 */
export function DiscoveryPreferencesEditor({
	persona,
}: Readonly<{ persona: Persona }>) {
	const personaId = persona.id;
	const queryClient = useQueryClient();

	// -----------------------------------------------------------------------
	// Form
	// -----------------------------------------------------------------------

	const form = useForm<DiscoveryPreferencesFormData>({
		resolver: zodResolver(discoveryPreferencesSchema),
		defaultValues: {
			...DISCOVERY_PREFERENCES_DEFAULT_VALUES,
			...toFormValues(persona),
		},
		mode: "onTouched",
	});

	const { watch } = form;

	const [submitError, setSubmitError] = useState<string | null>(null);
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [saveSuccess, setSaveSuccess] = useState(false);

	const watchedFitThreshold = watch("minimum_fit_threshold");
	const watchedDraftThreshold = watch("auto_draft_threshold");

	const showThresholdWarning = watchedDraftThreshold < watchedFitThreshold;

	// -----------------------------------------------------------------------
	// Submit handler
	// -----------------------------------------------------------------------

	const onSubmit = useCallback(
		async (data: DiscoveryPreferencesFormData) => {
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
				<h2 className="text-lg font-semibold">Discovery Preferences</h2>
				<p className="text-muted-foreground mt-1">
					Control how jobs are filtered and when drafts are generated.
				</p>
			</div>

			<Form {...form}>
				<form
					onSubmit={form.handleSubmit(onSubmit)}
					className="space-y-6"
					data-testid="discovery-preferences-editor-form"
					noValidate
				>
					{/* Minimum Fit Threshold */}
					<FormField
						control={form.control}
						name="minimum_fit_threshold"
						render={({ field }) => (
							<FormItem>
								<FormLabel htmlFor="minimum-fit-threshold">
									Minimum Fit Threshold
								</FormLabel>
								<FormControl>
									<div className="space-y-2">
										<div className="flex items-center gap-4">
											<input
												id="minimum-fit-threshold"
												type="range"
												min={0}
												max={100}
												step={1}
												value={field.value}
												onChange={(e) => field.onChange(Number(e.target.value))}
												onBlur={field.onBlur}
												className="accent-primary h-2 w-full cursor-pointer"
												aria-label="Minimum Fit Threshold"
											/>
											<span className="w-10 text-right text-sm font-medium tabular-nums">
												{field.value}
											</span>
										</div>
										<p className="text-muted-foreground text-sm">
											{EXPLANATION_TEXT.minimum_fit_threshold(field.value)}
										</p>
									</div>
								</FormControl>
								<FormMessage />
							</FormItem>
						)}
					/>

					{/* Auto-Draft Threshold */}
					<FormField
						control={form.control}
						name="auto_draft_threshold"
						render={({ field }) => (
							<FormItem>
								<FormLabel htmlFor="auto-draft-threshold">
									Auto-Draft Threshold
								</FormLabel>
								<FormControl>
									<div className="space-y-2">
										<div className="flex items-center gap-4">
											<input
												id="auto-draft-threshold"
												type="range"
												min={0}
												max={100}
												step={1}
												value={field.value}
												onChange={(e) => field.onChange(Number(e.target.value))}
												onBlur={field.onBlur}
												className="accent-primary h-2 w-full cursor-pointer"
												aria-label="Auto-Draft Threshold"
											/>
											<span className="w-10 text-right text-sm font-medium tabular-nums">
												{field.value}
											</span>
										</div>
										<p className="text-muted-foreground text-sm">
											{EXPLANATION_TEXT.auto_draft_threshold(field.value)}
										</p>
									</div>
								</FormControl>
								<FormMessage />
							</FormItem>
						)}
					/>

					{/* Cross-field validation warning */}
					{showThresholdWarning && (
						<div
							className="rounded-md border border-yellow-300 bg-yellow-50 p-3 text-sm text-yellow-800 dark:border-yellow-700 dark:bg-yellow-900/20 dark:text-yellow-300"
							role="alert"
							data-testid="threshold-warning"
						>
							{THRESHOLD_WARNING}
						</div>
					)}

					{/* Polling Frequency */}
					<FormField
						control={form.control}
						name="polling_frequency"
						render={({ field }) => (
							<FormItem>
								<FormLabel htmlFor="polling-frequency">
									Polling Frequency
								</FormLabel>
								<p className="text-muted-foreground text-sm">
									{EXPLANATION_TEXT.polling_frequency}
								</p>
								<FormControl>
									<select
										id="polling-frequency"
										aria-label="Polling Frequency"
										className="border-input bg-background ring-offset-background focus-visible:ring-ring flex h-10 w-full rounded-md border px-3 py-2 text-sm focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50"
										value={field.value}
										onChange={(e) => field.onChange(e.target.value)}
										onBlur={field.onBlur}
										ref={field.ref as React.Ref<HTMLSelectElement>}
										name={field.name}
									>
										{POLLING_FREQUENCIES.map((freq) => (
											<option key={freq} value={freq}>
												{freq}
											</option>
										))}
									</select>
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
							Discovery preferences saved.
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
