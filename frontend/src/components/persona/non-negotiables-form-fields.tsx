/**
 * Shared form fields for the non-negotiables editor and onboarding step.
 *
 * REQ-012 §6.3.8 / §7.2.7: Location preferences, compensation,
 * and other filters — identical fields used by both the onboarding
 * wizard step and the post-onboarding editor.
 */

import type { UseFormReturn } from "react-hook-form";

import { FormErrorSummary } from "@/components/form/form-error-summary";
import { FormTagField } from "@/components/form/form-tag-field";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { CURRENCIES } from "@/lib/non-negotiables-helpers";
import type { NonNegotiablesFormData } from "@/lib/non-negotiables-helpers";
import type { RemotePreference } from "@/types/persona";
import {
	COMPANY_SIZE_PREFERENCES,
	MAX_TRAVEL_PERCENTS,
	REMOTE_PREFERENCES,
} from "@/types/persona";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface NonNegotiablesFormFieldsProps {
	/** React Hook Form instance for the non-negotiables form. */
	form: UseFormReturn<NonNegotiablesFormData>;
	/** API submission error message, if any. */
	submitError: string | null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Renders all non-negotiables form fields (4 fieldsets) plus the error
 * summary and submit error alert. Consumers provide their own `<form>`
 * wrapper, submit button, and navigation.
 */
function NonNegotiablesFormFields({
	form,
	submitError,
}: Readonly<NonNegotiablesFormFieldsProps>) {
	const watchedRemotePreference = form.watch(
		"remote_preference",
	) as RemotePreference;
	const watchedRelocationOpen = form.watch("relocation_open");
	const watchedPreferNoSalary = form.watch("prefer_no_salary");

	const isRemoteOnly = watchedRemotePreference === "Remote Only";

	return (
		<>
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
		</>
	);
}

export { NonNegotiablesFormFields };
export type { NonNegotiablesFormFieldsProps };
