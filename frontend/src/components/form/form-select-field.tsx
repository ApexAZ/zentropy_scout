"use client";

/**
 * Form select field with React Hook Form integration.
 *
 * REQ-012 §13.2: Inline errors below each field on blur.
 * Wraps shadcn/ui Select with FormField, FormLabel, FormDescription, FormMessage.
 */

import type { Control, FieldPath, FieldValues } from "react-hook-form";

import {
	FormControl,
	FormDescription,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SelectOption {
	label: string;
	value: string;
}

interface FormSelectFieldProps<TValues extends FieldValues> {
	control: Control<TValues>;
	name: FieldPath<TValues>;
	label: string;
	options: SelectOption[];
	description?: string;
	placeholder?: string;
	disabled?: boolean;
	className?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function FormSelectField<TValues extends FieldValues>({
	control,
	name,
	label,
	options,
	description,
	placeholder,
	disabled,
	className,
}: Readonly<FormSelectFieldProps<TValues>>) {
	return (
		<FormField
			control={control}
			name={name}
			render={({ field }) => (
				<FormItem className={className}>
					<FormLabel>{label}</FormLabel>
					{/* Select values are always strings; safe coercion with fallback */}
					<Select
						onValueChange={field.onChange}
						defaultValue={
							typeof field.value === "string" ? field.value : undefined
						}
						disabled={disabled}
					>
						<FormControl>
							<SelectTrigger>
								<SelectValue placeholder={placeholder} />
							</SelectTrigger>
						</FormControl>
						<SelectContent>
							{options.map((option) => (
								<SelectItem key={option.value} value={option.value}>
									{option.label}
								</SelectItem>
							))}
						</SelectContent>
					</Select>
					{description && <FormDescription>{description}</FormDescription>}
					<FormMessage />
				</FormItem>
			)}
		/>
	);
}
