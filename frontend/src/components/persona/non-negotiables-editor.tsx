"use client";

/**
 * Post-onboarding non-negotiables editor (§6.10).
 *
 * REQ-012 §7.2.7: Sectioned form for location preferences, compensation,
 * other filters, and embedded custom filters CRUD. Pre-fills from persona
 * prop, PATCHes on save, invalidates cache, shows success message.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";
import { useCallback, useState } from "react";
import { useForm } from "react-hook-form";

import { FormErrorSummary } from "@/components/form/form-error-summary";
import { FormTagField } from "@/components/form/form-tag-field";
import { CustomFiltersSection } from "@/components/onboarding/steps/custom-filters-section";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
	Form,
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { apiPatch } from "@/lib/api-client";
import { toFriendlyError } from "@/lib/form-errors";
import {
	CURRENCIES,
	NON_NEGOTIABLES_DEFAULT_VALUES,
	nonNegotiablesSchema,
	toFormValues,
	toRequestBody,
} from "@/lib/non-negotiables-helpers";
import type { NonNegotiablesFormData } from "@/lib/non-negotiables-helpers";
import { queryKeys } from "@/lib/query-keys";
import type { Persona, RemotePreference } from "@/types/persona";
import {
	COMPANY_SIZE_PREFERENCES,
	MAX_TRAVEL_PERCENTS,
	REMOTE_PREFERENCES,
} from "@/types/persona";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Post-onboarding editor for non-negotiable fields.
 *
 * Receives the current persona as a prop. Pre-fills the form from persona
 * data and saves changes via PATCH. Includes embedded CustomFiltersSection.
 */
export function NonNegotiablesEditor({ persona }: { persona: Persona }) {
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

	const { watch } = form;

	const [submitError, setSubmitError] = useState<string | null>(null);
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [saveSuccess, setSaveSuccess] = useState(false);

	const watchedRemotePreference = watch(
		"remote_preference",
	) as RemotePreference;
	const watchedRelocationOpen = watch("relocation_open");
	const watchedPreferNoSalary = watch("prefer_no_salary");

	const isRemoteOnly = watchedRemotePreference === "Remote Only";

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
					{/* ---- Location Preferences ---- */}
					<fieldset className="space-y-4">
						<legend className="text-base font-semibold">
							Location Preferences
						</legend>

						{/* Remote preference radio group */}
						<FormField
							control={form.control}
							name="remote_preference"
							render={({ field }) => (
								<FormItem>
									<FormLabel>Remote Preference</FormLabel>
									<FormControl>
										<div
											className="flex flex-wrap gap-4"
											role="radiogroup"
											aria-label="Remote Preference"
										>
											{REMOTE_PREFERENCES.map((option) => (
												<label
													key={option}
													className="flex cursor-pointer items-center gap-2"
												>
													<input
														type="radio"
														name={field.name}
														value={option}
														checked={field.value === option}
														onChange={() => field.onChange(option)}
														className="text-primary h-4 w-4"
													/>
													{option}
												</label>
											))}
										</div>
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>

						{/* Conditional: commutable cities + max commute */}
						{!isRemoteOnly && (
							<>
								<FormTagField
									control={form.control}
									name="commutable_cities"
									label="Commutable Cities"
									placeholder="Type a city and press Enter"
									description="Cities you can commute to for work"
									maxItems={20}
								/>

								<FormField
									control={form.control}
									name="max_commute_minutes"
									render={({ field }) => (
										<FormItem>
											<FormLabel>Max Commute (minutes)</FormLabel>
											<FormControl>
												<Input
													type="number"
													placeholder="e.g. 45"
													{...field}
													value={field.value ?? ""}
												/>
											</FormControl>
											<FormMessage />
										</FormItem>
									)}
								/>
							</>
						)}
					</fieldset>

					{/* ---- Relocation ---- */}
					<fieldset className="space-y-4">
						<legend className="text-base font-semibold">Relocation</legend>

						<FormField
							control={form.control}
							name="relocation_open"
							render={({ field }) => (
								<FormItem className="flex items-center gap-2">
									<FormControl>
										<Checkbox
											checked={field.value}
											onCheckedChange={field.onChange}
											id="relocation-toggle"
										/>
									</FormControl>
									<FormLabel
										htmlFor="relocation-toggle"
										className="!mt-0 cursor-pointer"
									>
										Open to relocation
									</FormLabel>
								</FormItem>
							)}
						/>

						{watchedRelocationOpen && (
							<FormTagField
								control={form.control}
								name="relocation_cities"
								label="Relocation Cities"
								placeholder="Type a city and press Enter"
								description="Cities you would consider relocating to"
								maxItems={20}
							/>
						)}
					</fieldset>

					{/* ---- Compensation ---- */}
					<fieldset className="space-y-4">
						<legend className="text-base font-semibold">Compensation</legend>

						<FormField
							control={form.control}
							name="prefer_no_salary"
							render={({ field }) => (
								<FormItem className="flex items-center gap-2">
									<FormControl>
										<Checkbox
											checked={field.value}
											onCheckedChange={field.onChange}
											id="prefer-no-salary"
										/>
									</FormControl>
									<FormLabel
										htmlFor="prefer-no-salary"
										className="!mt-0 cursor-pointer"
									>
										Prefer not to set
									</FormLabel>
								</FormItem>
							)}
						/>

						{!watchedPreferNoSalary && (
							<div className="grid gap-4 sm:grid-cols-2">
								<FormField
									control={form.control}
									name="minimum_base_salary"
									render={({ field }) => (
										<FormItem>
											<FormLabel>Minimum Base Salary</FormLabel>
											<FormControl>
												<Input
													type="number"
													placeholder="e.g. 100000"
													{...field}
													value={field.value ?? ""}
												/>
											</FormControl>
											<FormMessage />
										</FormItem>
									)}
								/>

								<FormField
									control={form.control}
									name="salary_currency"
									render={({ field }) => (
										<FormItem>
											<FormLabel>Currency</FormLabel>
											<FormControl>
												<select
													aria-label="Currency"
													className="border-input bg-background ring-offset-background focus-visible:ring-ring flex h-10 w-full rounded-md border px-3 py-2 text-sm focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50"
													value={field.value}
													onChange={(e) => field.onChange(e.target.value)}
													onBlur={field.onBlur}
													ref={field.ref as React.Ref<HTMLSelectElement>}
													name={field.name}
												>
													{CURRENCIES.map((code) => (
														<option key={code} value={code}>
															{code}
														</option>
													))}
												</select>
											</FormControl>
											<FormMessage />
										</FormItem>
									)}
								/>
							</div>
						)}
					</fieldset>

					{/* ---- Other Filters ---- */}
					<fieldset className="space-y-4">
						<legend className="text-base font-semibold">Other Filters</legend>

						<FormField
							control={form.control}
							name="visa_sponsorship_required"
							render={({ field }) => (
								<FormItem className="flex items-center gap-2">
									<FormControl>
										<Checkbox
											checked={field.value}
											onCheckedChange={field.onChange}
											id="visa-sponsorship"
										/>
									</FormControl>
									<FormLabel
										htmlFor="visa-sponsorship"
										className="!mt-0 cursor-pointer"
									>
										Visa sponsorship required
									</FormLabel>
								</FormItem>
							)}
						/>

						<FormTagField
							control={form.control}
							name="industry_exclusions"
							label="Industry Exclusions"
							placeholder="Type an industry and press Enter"
							description="Industries you want to exclude from job matches"
							maxItems={20}
						/>

						{/* Company size preference radio group */}
						<FormField
							control={form.control}
							name="company_size_preference"
							render={({ field }) => (
								<FormItem>
									<FormLabel>Company Size Preference</FormLabel>
									<FormControl>
										<div
											className="flex flex-wrap gap-4"
											role="radiogroup"
											aria-label="Company Size Preference"
										>
											{COMPANY_SIZE_PREFERENCES.map((option) => (
												<label
													key={option}
													className="flex cursor-pointer items-center gap-2"
												>
													<input
														type="radio"
														name={field.name}
														value={option}
														checked={field.value === option}
														onChange={() => field.onChange(option)}
														className="text-primary h-4 w-4"
													/>
													{option}
												</label>
											))}
										</div>
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>

						{/* Max travel radio group */}
						<FormField
							control={form.control}
							name="max_travel_percent"
							render={({ field }) => (
								<FormItem>
									<FormLabel>Max Travel</FormLabel>
									<FormControl>
										<div
											className="flex flex-wrap gap-4"
											role="radiogroup"
											aria-label="Max Travel"
										>
											{MAX_TRAVEL_PERCENTS.map((option) => (
												<label
													key={option}
													className="flex cursor-pointer items-center gap-2"
												>
													<input
														type="radio"
														name={field.name}
														value={option}
														checked={field.value === option}
														onChange={() => field.onChange(option)}
														className="text-primary h-4 w-4"
													/>
													{option}
												</label>
											))}
										</div>
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>
					</fieldset>

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
