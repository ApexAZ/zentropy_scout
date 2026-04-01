/**
 * @fileoverview Form-level error summary component.
 *
 * Layer: component
 * Feature: shared
 *
 * REQ-012 §13.2: Form-level error summary on submit failure.
 * Must be rendered inside a FormProvider context.
 *
 * Coordinates with:
 * - lib/utils.ts: cn for conditional class merging
 *
 * Called by / Used by:
 * - components/form/form-action-footer.tsx: embedded error summary in form footer
 * - components/onboarding/steps/base-resume-setup-step.tsx: resume setup form validation
 * - components/onboarding/steps/bullet-form.tsx: bullet edit form validation
 * - components/onboarding/steps/basic-info-step.tsx: basic info step validation
 * - components/persona/growth-targets-form-fields.tsx: growth targets form validation
 * - components/persona/non-negotiables-form-fields.tsx: non-negotiables form validation
 * - components/persona/voice-profile-form-fields.tsx: voice profile form validation
 * - components/persona/discovery-preferences-editor.tsx: discovery preferences validation
 * - components/persona/basic-info-editor.tsx: basic info editor validation
 */

"use client";

import { useFormState } from "react-hook-form";

import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function FormErrorSummary({
	className,
}: Readonly<{ className?: string }>) {
	const { errors } = useFormState();

	const errorMessages = Object.entries(errors)
		.map(([field, error]) => ({
			field,
			message: (error?.message as string) ?? "",
		}))
		.filter((entry) => entry.message.length > 0);

	if (errorMessages.length === 0) {
		return null;
	}

	return (
		<div
			role="alert"
			className={cn(
				"border-destructive/50 bg-destructive/10 rounded border p-4",
				className,
			)}
		>
			<p className="text-destructive text-sm font-medium">
				Please fix the following errors:
			</p>
			<ul className="text-destructive mt-2 list-disc pl-4 text-sm">
				{errorMessages.map(({ field, message }) => (
					<li key={field}>{message}</li>
				))}
			</ul>
		</div>
	);
}
