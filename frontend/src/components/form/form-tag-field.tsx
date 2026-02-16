"use client";

/**
 * Tag/chip input for JSONB string arrays with React Hook Form integration.
 *
 * REQ-012 §13.2: Used for skills, cities, exclusions, target roles,
 * sample phrases, and things-to-avoid fields across onboarding and
 * persona management.
 *
 * Wraps a composite input (tag chips + text input) with FormField,
 * FormLabel, FormDescription, FormMessage.
 */

import { useRef } from "react";
import type { Control, FieldPath, FieldValues } from "react-hook-form";
import { X } from "lucide-react";

import { cn } from "@/lib/utils";
import {
	FormDescription,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
	useFormField,
} from "@/components/ui/form";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface FormTagFieldProps<TValues extends FieldValues> {
	control: Control<TValues>;
	name: FieldPath<TValues>;
	label: string;
	description?: string;
	placeholder?: string;
	disabled?: boolean;
	className?: string;
	maxItems?: number;
}

// ---------------------------------------------------------------------------
// Internal: Tag input area (needs FormField context for ARIA)
//
// FormControl (Radix Slot) cannot wrap a composite container with multiple
// children (tags + input). ARIA attributes are wired manually via
// useFormField() instead.
// ---------------------------------------------------------------------------

function TagInputArea({
	value,
	onChange,
	onBlur,
	disabled,
	placeholder,
	maxItems,
}: Readonly<{
	value: string[];
	onChange: (tags: string[]) => void;
	onBlur: () => void;
	disabled?: boolean;
	placeholder?: string;
	maxItems?: number;
}>) {
	const inputRef = useRef<HTMLInputElement>(null);
	const { formItemId, formDescriptionId, formMessageId, error } =
		useFormField();

	const atLimit = maxItems !== undefined && value.length >= maxItems;

	function addTag(raw: string) {
		const tag = raw.trim();
		if (!tag) return;
		if (atLimit) return;
		const isDuplicate = value.some(
			(existing) => existing.toLowerCase() === tag.toLowerCase(),
		);
		if (isDuplicate) return;
		onChange([...value, tag]);
	}

	function removeTag(index: number) {
		onChange(value.filter((_, i) => i !== index));
	}

	function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
		const input = e.currentTarget;

		if (e.key === "Enter") {
			e.preventDefault();
			addTag(input.value);
			input.value = "";
			return;
		}

		if (e.key === "Backspace" && input.value === "" && value.length > 0) {
			removeTag(value.length - 1);
		}
	}

	function handleInput(e: React.InputEvent<HTMLInputElement>) {
		const input = e.currentTarget;
		if (input.value.includes(",")) {
			const parts = input.value.split(",");
			for (const part of parts.slice(0, -1)) {
				addTag(part);
			}
			input.value = parts[parts.length - 1];
		}
	}

	function handleContainerClick() {
		inputRef.current?.focus();
	}

	return (
		/* eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions -- Wrapper click delegates focus to the inner <input>; keyboard users reach it via Tab. */
		<div
			data-slot="tag-input-area"
			className={cn(
				"border-input flex min-h-9 flex-wrap items-center gap-1.5 rounded-md border bg-transparent px-3 py-1.5 text-sm shadow-xs transition-colors",
				"focus-within:ring-ring/50 focus-within:ring-[3px]",
				"focus-within:border-ring",
				error && "border-destructive focus-within:ring-destructive/50",
				disabled && "cursor-not-allowed opacity-50",
			)}
			onClick={handleContainerClick}
		>
			{/* key={tag} is safe: addTag enforces case-insensitive uniqueness */}
			{value.map((tag, index) => (
				<span
					key={tag}
					data-slot="tag"
					className={cn(
						"bg-secondary text-secondary-foreground inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium",
					)}
				>
					{tag}
					{!disabled && (
						<button
							type="button"
							aria-label={`Remove ${tag}`}
							className="focus-visible:ring-ring rounded-sm opacity-70 hover:opacity-100 focus-visible:ring-1 focus-visible:outline-none"
							onClick={(e) => {
								e.stopPropagation();
								removeTag(index);
							}}
						>
							<X className="h-3 w-3" />
						</button>
					)}
				</span>
			))}
			{/* Uncontrolled: draft text is ephemeral; only committed tags enter RHF state */}
			{!atLimit && (
				<input
					ref={inputRef}
					id={formItemId}
					type="text"
					placeholder={value.length === 0 ? placeholder : undefined}
					disabled={disabled}
					aria-describedby={
						error ? `${formDescriptionId} ${formMessageId}` : formDescriptionId
					}
					aria-invalid={!!error}
					className="placeholder:text-muted-foreground min-w-[120px] flex-1 bg-transparent outline-none disabled:cursor-not-allowed"
					onKeyDown={handleKeyDown}
					onInput={handleInput}
					onBlur={onBlur}
				/>
			)}
		</div>
	);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function FormTagField<TValues extends FieldValues>({
	control,
	name,
	label,
	description,
	placeholder,
	disabled,
	className,
	maxItems,
}: FormTagFieldProps<TValues>) {
	return (
		<FormField
			control={control}
			name={name}
			render={({ field }) => (
				<FormItem className={className}>
					<FormLabel>{label}</FormLabel>
					<TagInputArea
						value={(field.value as string[]) ?? []}
						onChange={field.onChange}
						onBlur={field.onBlur}
						disabled={disabled}
						placeholder={placeholder}
						maxItems={maxItems}
					/>
					{description && <FormDescription>{description}</FormDescription>}
					<FormMessage />
				</FormItem>
			)}
		/>
	);
}
