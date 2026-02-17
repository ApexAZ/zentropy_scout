"use client";

/**
 * Form textarea field with React Hook Form integration.
 *
 * REQ-012 §13.2: Inline errors below each field on blur.
 * Wraps shadcn/ui Textarea with FormField, FormLabel, FormDescription, FormMessage.
 */

import type { Control, FieldPath, FieldValues } from "react-hook-form";

import { Textarea } from "@/components/ui/textarea";
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

interface FormTextareaFieldProps<TValues extends FieldValues> {
	control: Control<TValues>;
	name: FieldPath<TValues>;
	label: string;
	description?: string;
	placeholder?: string;
	disabled?: boolean;
	className?: string;
	rows?: number;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function FormTextareaField<TValues extends FieldValues>({
	control,
	name,
	label,
	description,
	placeholder,
	disabled,
	className,
	rows,
}: Readonly<FormTextareaFieldProps<TValues>>) {
	return (
		<FormField
			control={control}
			name={name}
			render={({ field }) => (
				<FormItem className={className}>
					<FormLabel>{label}</FormLabel>
					<FormControl>
						<Textarea
							placeholder={placeholder}
							disabled={disabled}
							rows={rows}
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
