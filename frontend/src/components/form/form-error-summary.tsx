/**
 * Form-level error summary component.
 *
 * REQ-012 §13.2: Form-level error summary on submit failure.
 * Must be rendered inside a <Form> (FormProvider) context.
 */

"use client";

import { useFormState } from "react-hook-form";

import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function FormErrorSummary({ className }: { className?: string }) {
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
