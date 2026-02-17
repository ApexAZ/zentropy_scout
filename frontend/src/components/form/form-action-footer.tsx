/**
 * Shared form footer with error summary, submit error, and action buttons.
 *
 * Used by onboarding step forms and persona editor forms to render
 * the consistent Cancel/Save button pair with loading state.
 */

import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { FormErrorSummary } from "@/components/form/form-error-summary";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface FormActionFooterProps {
	/** API-level submit error message (distinct from field validation). */
	submitError: string | null;
	/** Whether the form is currently submitting. */
	isSubmitting: boolean;
	/** Handler for the Cancel button. */
	onCancel: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

function FormActionFooter({
	submitError,
	isSubmitting,
	onCancel,
}: Readonly<FormActionFooterProps>) {
	return (
		<>
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

			<div className="flex items-center justify-end gap-3 pt-2">
				<Button
					type="button"
					variant="ghost"
					onClick={onCancel}
					disabled={isSubmitting}
				>
					Cancel
				</Button>
				<Button type="submit" disabled={isSubmitting}>
					{isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
					{isSubmitting ? "Saving..." : "Save"}
				</Button>
			</div>
		</>
	);
}

export { FormActionFooter };
export type { FormActionFooterProps };
