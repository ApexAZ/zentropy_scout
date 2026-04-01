"use client";

/**
 * @fileoverview Form input field with React Hook Form integration.
 *
 * Layer: component
 * Feature: shared
 *
 * REQ-012 §13.2: Inline errors below each field on blur.
 * Wraps shadcn/ui Input with FormField, FormLabel, FormDescription, FormMessage.
 *
 * Coordinates with:
 * - components/ui/input.tsx: Input for the text input control
 * - components/ui/form.tsx: FormControl, FormDescription, FormField, FormItem, FormLabel, FormMessage for RHF integration
 *
 * Called by / Used by:
 * - components/onboarding/steps/base-resume-setup-step.tsx: resume title field
 * - components/onboarding/steps/skills-form.tsx: skill name field
 * - components/onboarding/steps/education-form.tsx: school/degree fields
 * - components/onboarding/steps/certification-form.tsx: certification name/issuer fields
 * - components/onboarding/steps/bullet-form.tsx: bullet title field
 * - components/onboarding/steps/custom-filter-form.tsx: filter name field
 * - components/onboarding/steps/basic-info-step.tsx: name/title fields
 * - components/onboarding/steps/work-history-form.tsx: company/title fields
 * - components/onboarding/steps/story-form.tsx: story title field
 * - components/persona/voice-profile-form-fields.tsx: voice profile fields
 * - components/persona/basic-info-editor.tsx: name/title fields
 * - components/dashboard/add-job-modal.tsx: job posting fields
 */

import type { Control, FieldPath, FieldValues } from "react-hook-form";

import { Input } from "@/components/ui/input";
import {
	FormControl,
	FormDescription,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface FormInputFieldProps<TValues extends FieldValues> {
	control: Control<TValues>;
	name: FieldPath<TValues>;
	label: string;
	description?: string;
	placeholder?: string;
	type?: "text" | "email" | "url" | "tel" | "password" | "number";
	disabled?: boolean;
	className?: string;
	min?: number;
	max?: number;
	step?: number;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function FormInputField<TValues extends FieldValues>({
	control,
	name,
	label,
	description,
	placeholder,
	type = "text",
	disabled,
	className,
	min,
	max,
	step,
}: Readonly<FormInputFieldProps<TValues>>) {
	return (
		<FormField
			control={control}
			name={name}
			render={({ field }) => (
				<FormItem className={className}>
					<FormLabel>{label}</FormLabel>
					<FormControl>
						<Input
							placeholder={placeholder}
							type={type}
							disabled={disabled}
							min={min}
							max={max}
							step={step}
							{...field}
						/>
					</FormControl>
					{description && <FormDescription>{description}</FormDescription>}
					<FormMessage />
				</FormItem>
			)}
		/>
	);
}
