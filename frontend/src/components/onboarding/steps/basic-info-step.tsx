"use client";

/**
 * Basic info step for onboarding wizard (Step 2).
 *
 * REQ-012 §6.3.2: 8-field form (full name, email, phone, LinkedIn URL,
 * portfolio URL, city, state, country) with pre-fill from resume
 * extraction, client-side Zod validation, and PATCH /personas/{id}
 * submission.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Loader2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { FormInputField } from "@/components/form/form-input-field";
import { FormErrorSummary } from "@/components/form/form-error-summary";
import { Button } from "@/components/ui/button";
import { Form } from "@/components/ui/form";
import { apiGet, apiPatch } from "@/lib/api-client";
import { BASIC_INFO_FIELDS } from "@/lib/basic-info-schema";
import { toFriendlyError } from "@/lib/form-errors";
import { useOnboarding } from "@/lib/onboarding-provider";
import type { ApiListResponse } from "@/types/api";
import type { Persona } from "@/types/persona";

// ---------------------------------------------------------------------------
// Validation schema
// ---------------------------------------------------------------------------

const basicInfoSchema = z.object(BASIC_INFO_FIELDS);

type BasicInfoFormData = z.infer<typeof basicInfoSchema>;

const DEFAULT_VALUES: BasicInfoFormData = {
	full_name: "",
	email: "",
	phone: "",
	linkedin_url: "",
	portfolio_url: "",
	home_city: "",
	home_state: "",
	home_country: "",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Onboarding Step 2: Basic Information.
 *
 * Renders a form with 8 fields for personal details. If the user
 * uploaded a resume in Step 1, fields are pre-filled from the
 * extracted data. On valid submission, PATCHes the persona and
 * advances to the next step.
 */
export function BasicInfoStep() {
	const { personaId, next, back } = useOnboarding();

	const [isLoadingPersona, setIsLoadingPersona] = useState(!!personaId);
	const [submitError, setSubmitError] = useState<string | null>(null);
	const [isSubmitting, setIsSubmitting] = useState(false);

	const form = useForm<BasicInfoFormData>({
		resolver: zodResolver(basicInfoSchema),
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
						full_name: persona.full_name ?? "",
						email: persona.email ?? "",
						phone: persona.phone ?? "",
						linkedin_url: persona.linkedin_url ?? "",
						portfolio_url: persona.portfolio_url ?? "",
						home_city: persona.home_city ?? "",
						home_state: persona.home_state ?? "",
						home_country: persona.home_country ?? "",
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
		async (data: BasicInfoFormData) => {
			if (!personaId) return;

			setSubmitError(null);
			setIsSubmitting(true);

			try {
				await apiPatch(`/personas/${personaId}`, {
					full_name: data.full_name,
					email: data.email,
					phone: data.phone,
					linkedin_url: data.linkedin_url || null,
					portfolio_url: data.portfolio_url || null,
					home_city: data.home_city,
					home_state: data.home_state,
					home_country: data.home_country,
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
				data-testid="loading-persona"
			>
				<Loader2 className="text-primary h-8 w-8 animate-spin" />
				<p className="text-muted-foreground mt-3">
					Loading your information...
				</p>
			</div>
		);
	}

	return (
		<div className="flex flex-1 flex-col gap-6">
			<div className="text-center">
				<h2 className="text-lg font-semibold">Basic Information</h2>
				<p className="text-muted-foreground mt-1">
					Tell us a bit about yourself. We&apos;ll use this as the foundation
					for your resume.
				</p>
			</div>

			<Form {...form}>
				<form
					onSubmit={form.handleSubmit(onSubmit)}
					className="space-y-4"
					data-testid="basic-info-form"
					noValidate
				>
					<FormInputField
						control={form.control}
						name="full_name"
						label="Full Name"
						placeholder="Jane Doe"
					/>

					<div className="grid gap-4 sm:grid-cols-2">
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
					</div>

					<div className="grid gap-4 sm:grid-cols-2">
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
					</div>

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
							disabled={isSubmitting}
							data-testid="submit-button"
						>
							{isSubmitting && (
								<Loader2 className="mr-2 h-4 w-4 animate-spin" />
							)}
							{isSubmitting ? "Saving..." : "Next"}
						</Button>
					</div>
				</form>
			</Form>
		</div>
	);
}
