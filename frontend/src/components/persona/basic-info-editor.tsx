"use client";

/**
 * Basic info and professional overview editor (§6.3).
 *
 * REQ-012 §7.2.1: Two-column form (desktop) / stacked (mobile) for all
 * 12 basic info and professional overview fields. Pre-filled from persona
 * prop, validates with Zod, PATCHes /personas/{id}, invalidates cache,
 * and navigates back to /persona.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { FormErrorSummary } from "@/components/form/form-error-summary";
import { FormInputField } from "@/components/form/form-input-field";
import { FormTextareaField } from "@/components/form/form-textarea-field";
import { Button } from "@/components/ui/button";
import { Form } from "@/components/ui/form";
import { apiPatch } from "@/lib/api-client";
import { BASIC_INFO_FIELDS } from "@/lib/basic-info-schema";
import { toFriendlyError } from "@/lib/form-errors";
import { queryKeys } from "@/lib/query-keys";
import type { Persona } from "@/types/persona";

// ---------------------------------------------------------------------------
// Validation schema
// ---------------------------------------------------------------------------

const MAX_SUMMARY_LENGTH = 2000;
const MAX_FIELD_LENGTH = 255;

const basicInfoEditorSchema = z.object({
	...BASIC_INFO_FIELDS,
	professional_summary: z
		.string()
		.max(MAX_SUMMARY_LENGTH, { message: "Summary is too long" })
		.optional()
		.or(z.literal("")),
	years_experience: z.string().refine((val) => {
		if (val === "") return true;
		const num = Number(val);
		return Number.isInteger(num) && num >= 0 && num <= 99;
	}, "Must be between 0 and 99"),
	current_role: z
		.string()
		.max(MAX_FIELD_LENGTH, "Current role is too long")
		.optional()
		.or(z.literal("")),
	current_company: z
		.string()
		.max(MAX_FIELD_LENGTH, "Current company is too long")
		.optional()
		.or(z.literal("")),
});

type BasicInfoEditorFormData = z.infer<typeof basicInfoEditorSchema>;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Post-onboarding editor for basic info and professional overview fields.
 *
 * Receives the current persona as a prop, pre-fills all 12 fields,
 * and saves changes via PATCH /personas/{id}. On success, invalidates
 * the personas query cache and navigates back to /persona.
 */
export function BasicInfoEditor({ persona }: Readonly<{ persona: Persona }>) {
	const router = useRouter();
	const queryClient = useQueryClient();

	const [submitError, setSubmitError] = useState<string | null>(null);
	const [isSubmitting, setIsSubmitting] = useState(false);

	const form = useForm<BasicInfoEditorFormData>({
		resolver: zodResolver(basicInfoEditorSchema),
		defaultValues: {
			full_name: persona.full_name ?? "",
			email: persona.email ?? "",
			phone: persona.phone ?? "",
			linkedin_url: persona.linkedin_url ?? "",
			portfolio_url: persona.portfolio_url ?? "",
			home_city: persona.home_city ?? "",
			home_state: persona.home_state ?? "",
			home_country: persona.home_country ?? "",
			professional_summary: persona.professional_summary ?? "",
			years_experience:
				persona.years_experience == null
					? ""
					: String(persona.years_experience),
			current_role: persona.current_role ?? "",
			current_company: persona.current_company ?? "",
		},
		mode: "onTouched",
	});

	// -----------------------------------------------------------------------
	// Submit handler
	// -----------------------------------------------------------------------

	const onSubmit = useCallback(
		async (data: BasicInfoEditorFormData) => {
			setSubmitError(null);
			setIsSubmitting(true);

			try {
				await apiPatch(`/personas/${persona.id}`, {
					full_name: data.full_name,
					email: data.email,
					phone: data.phone,
					linkedin_url: data.linkedin_url || null,
					portfolio_url: data.portfolio_url || null,
					home_city: data.home_city,
					home_state: data.home_state,
					home_country: data.home_country,
					professional_summary: data.professional_summary || null,
					years_experience: data.years_experience
						? Number(data.years_experience)
						: null,
					current_role: data.current_role || null,
					current_company: data.current_company || null,
				});

				await queryClient.invalidateQueries({
					queryKey: queryKeys.personas,
				});
				router.push("/persona");
			} catch (err) {
				setIsSubmitting(false);
				setSubmitError(toFriendlyError(err));
			}
		},
		[persona.id, router, queryClient],
	);

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	return (
		<div className="flex flex-1 flex-col gap-6">
			<div>
				<h2 className="text-lg font-semibold">Edit Basic Info</h2>
				<p className="text-muted-foreground mt-1">
					Update your personal and professional details.
				</p>
			</div>

			<Form {...form}>
				<form
					onSubmit={form.handleSubmit(onSubmit)}
					className="space-y-6"
					data-testid="basic-info-editor-form"
					noValidate
				>
					<div className="grid gap-6 md:grid-cols-2">
						{/* Left column: basic info */}
						<div className="space-y-4">
							<FormInputField
								control={form.control}
								name="full_name"
								label="Full Name"
								placeholder="Jane Doe"
							/>

							<FormInputField
								control={form.control}
								name="email"
								label="Email"
								type="email"
								placeholder="jane@example.com"
							/>

							<FormInputField
								control={form.control}
								name="phone"
								label="Phone"
								type="tel"
								placeholder="+1 555-123-4567"
							/>

							<FormInputField
								control={form.control}
								name="linkedin_url"
								label="LinkedIn URL"
								type="url"
								placeholder="https://linkedin.com/in/janedoe"
							/>

							<FormInputField
								control={form.control}
								name="portfolio_url"
								label="Portfolio URL"
								type="url"
								placeholder="https://janedoe.com"
							/>

							<div className="grid gap-4 sm:grid-cols-3">
								<FormInputField
									control={form.control}
									name="home_city"
									label="City"
									placeholder="San Francisco"
								/>
								<FormInputField
									control={form.control}
									name="home_state"
									label="State"
									placeholder="CA"
								/>
								<FormInputField
									control={form.control}
									name="home_country"
									label="Country"
									placeholder="USA"
								/>
							</div>
						</div>

						{/* Right column: professional overview */}
						<div className="space-y-4">
							<FormTextareaField
								control={form.control}
								name="professional_summary"
								label="Professional Summary"
								placeholder="Brief overview of your professional background..."
								rows={5}
							/>

							<FormInputField
								control={form.control}
								name="years_experience"
								label="Years of Experience"
								type="number"
								placeholder="0"
								min={0}
								max={99}
								step={1}
							/>

							<FormInputField
								control={form.control}
								name="current_role"
								label="Current Role"
								placeholder="Software Engineer"
							/>

							<FormInputField
								control={form.control}
								name="current_company"
								label="Current Company"
								placeholder="TechCorp"
							/>
						</div>
					</div>

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
