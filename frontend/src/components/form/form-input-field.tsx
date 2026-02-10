"use client";

/**
 * Form input field with React Hook Form integration.
 *
 * REQ-012 §13.2: Inline errors below each field on blur.
 * Wraps shadcn/ui Input with FormField, FormLabel, FormDescription, FormMessage.
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
}: FormInputFieldProps<TValues>) {
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
