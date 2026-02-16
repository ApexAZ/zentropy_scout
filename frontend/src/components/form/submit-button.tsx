"use client";

/**
 * Submit button with loading spinner.
 *
 * REQ-012 §13.2: Spinner on buttons during async operations.
 * Disabled inputs during submission.
 */

import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SubmitButtonProps {
	label: string;
	isSubmitting: boolean;
	loadingLabel?: string;
	disabled?: boolean;
	className?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SubmitButton({
	label,
	isSubmitting,
	loadingLabel,
	disabled,
	className,
}: Readonly<SubmitButtonProps>) {
	return (
		<Button
			type="submit"
			disabled={isSubmitting || disabled}
			className={cn("gap-2", className)}
		>
			{isSubmitting && (
				<Loader2
					data-testid="submit-spinner"
					className="h-4 w-4 animate-spin"
					aria-hidden="true"
				/>
			)}
			{isSubmitting ? (loadingLabel ?? label) : label}
		</Button>
	);
}
