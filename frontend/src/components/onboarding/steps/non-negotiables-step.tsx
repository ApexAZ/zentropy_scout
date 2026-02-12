"use client";

/**
 * Non-negotiables step for onboarding wizard (Step 8).
 *
 * REQ-012 §6.3.8: Form with sections.
 * - Location preferences: remote preference radio group, commutable cities
 *   tag input, max commute number input, relocation toggle/cities.
 * - Compensation: minimum base salary with currency selector, "prefer not
 *   to set" checkbox.
 * - Other filters: visa sponsorship toggle, industry exclusions tag input,
 *   company size preference radio group, max travel radio group.
 *
 * Conditional visibility:
 * - Remote Only hides commutable_cities and max_commute_minutes.
 * - relocation_open = false hides relocation_cities.
 * - prefer_no_salary = true hides minimum_base_salary input.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Loader2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { FormErrorSummary } from "@/components/form/form-error-summary";
import { FormTagField } from "@/components/form/form-tag-field";
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
import { ApiError, apiGet, apiPatch } from "@/lib/api-client";
import { useOnboarding } from "@/lib/onboarding-provider";
import type { ApiListResponse } from "@/types/api";
import type { Persona, RemotePreference } from "@/types/persona";
import {
	COMPANY_SIZE_PREFERENCES,
	MAX_TRAVEL_PERCENTS,
	REMOTE_PREFERENCES,
} from "@/types/persona";

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

/** Max commute in minutes (8 hours). */
const MAX_COMMUTE_MINUTES = 480;

/** Max salary value (prevents integer overflow in DB/downstream). */
const MAX_SALARY = 999_999_999;

/** Common currency codes for the salary currency selector. */
const CURRENCIES = [
	"USD",
	"EUR",
	"GBP",
	"CAD",
	"AUD",
	"CHF",
	"JPY",
	"CNY",
	"INR",
] as const;

// ---------------------------------------------------------------------------
// Validation schema
// ---------------------------------------------------------------------------

/**
 * Positive-number string validator. Stored as string from the HTML number
 * input. Validates that the value is a positive number. Conversion to
 * number happens in toRequestBody().
 */
const positiveNumberField = z.string().refine(
	(val) => {
		if (val === "") return true;
		const num = Number(val);
		return !Number.isNaN(num) && num > 0;
	},
	{ message: "Must be a positive number" },
);

/**
 * Commute field: positive number with upper bound.
 */
const commuteField = positiveNumberField.refine(
	(val) => {
		if (val === "") return true;
		return Number(val) <= MAX_COMMUTE_MINUTES;
	},
	{ message: `Cannot exceed ${MAX_COMMUTE_MINUTES} minutes` },
);

/**
 * Salary field: positive number with upper bound.
 */
const salaryField = positiveNumberField.refine(
	(val) => {
		if (val === "") return true;
		return Number(val) <= MAX_SALARY;
	},
	{ message: `Cannot exceed ${MAX_SALARY.toLocaleString()}` },
);

const nonNegotiablesSchema = z.object({
	// Location
	// REMOTE_PREFERENCES is readonly string[] — double assertion needed
	// because z.enum() requires a mutable [string, ...string[]] tuple.
	remote_preference: z.enum(
		REMOTE_PREFERENCES as unknown as [string, ...string[]],
	),
	commutable_cities: z.array(z.string().trim().max(100)).max(20),
	max_commute_minutes: commuteField,
	relocation_open: z.boolean(),
	relocation_cities: z.array(z.string().trim().max(100)).max(20),

	// Compensation
	prefer_no_salary: z.boolean(),
	minimum_base_salary: salaryField,
	// CURRENCIES is readonly string[] — double assertion needed for z.enum().
	salary_currency: z.enum(CURRENCIES as unknown as [string, ...string[]]),

	// Other filters
	visa_sponsorship_required: z.boolean(),
	industry_exclusions: z.array(z.string().trim().max(100)).max(20),
	company_size_preference: z.enum(
		COMPANY_SIZE_PREFERENCES as unknown as [string, ...string[]],
	),
	max_travel_percent: z.enum(
		MAX_TRAVEL_PERCENTS as unknown as [string, ...string[]],
	),
});

type NonNegotiablesFormData = z.infer<typeof nonNegotiablesSchema>;

const DEFAULT_VALUES: NonNegotiablesFormData = {
	remote_preference: "No Preference",
	commutable_cities: [],
	max_commute_minutes: "",
	relocation_open: false,
	relocation_cities: [],
	prefer_no_salary: true,
	minimum_base_salary: "",
	salary_currency: "USD",
	visa_sponsorship_required: false,
	industry_exclusions: [],
	company_size_preference: "No Preference",
	max_travel_percent: "None",
};

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

/** Build API request body. Clears conditional fields and converts types. */
function toRequestBody(data: NonNegotiablesFormData) {
	const isRemoteOnly = data.remote_preference === "Remote Only";
	const commute = data.max_commute_minutes;
	const salary = data.minimum_base_salary;
	return {
		// Location
		remote_preference: data.remote_preference,
		commutable_cities: isRemoteOnly ? [] : data.commutable_cities,
		max_commute_minutes:
			isRemoteOnly || commute === "" ? null : Number(commute),
		relocation_open: data.relocation_open,
		relocation_cities: data.relocation_open ? data.relocation_cities : [],

		// Compensation
		minimum_base_salary:
			data.prefer_no_salary || salary === "" ? null : Number(salary),
		salary_currency: data.salary_currency,

		// Other filters
		visa_sponsorship_required: data.visa_sponsorship_required,
		industry_exclusions: data.industry_exclusions,
		company_size_preference: data.company_size_preference,
		max_travel_percent: data.max_travel_percent,
	};
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
		defaultValues: DEFAULT_VALUES,
		mode: "onTouched",
	});

	const { reset, watch } = form;

	const watchedRemotePreference = watch(
		"remote_preference",
	) as RemotePreference;
	const watchedRelocationOpen = watch("relocation_open");
	const watchedPreferNoSalary = watch("prefer_no_salary");

	const isRemoteOnly = watchedRemotePreference === "Remote Only";

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
						// Location
						remote_preference: persona.remote_preference ?? "No Preference",
						commutable_cities: persona.commutable_cities ?? [],
						max_commute_minutes:
							persona.max_commute_minutes != null
								? String(persona.max_commute_minutes)
								: "",
						relocation_open: persona.relocation_open ?? false,
						relocation_cities: persona.relocation_cities ?? [],

						// Compensation
						prefer_no_salary: persona.minimum_base_salary == null,
						minimum_base_salary:
							persona.minimum_base_salary != null
								? String(persona.minimum_base_salary)
								: "",
						salary_currency: persona.salary_currency ?? "USD",

						// Other filters
						visa_sponsorship_required:
							persona.visa_sponsorship_required ?? false,
						industry_exclusions: persona.industry_exclusions ?? [],
						company_size_preference:
							persona.company_size_preference ?? "No Preference",
						max_travel_percent: persona.max_travel_percent ?? "None",
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
