/**
 * @fileoverview Maps server-side validation errors to React Hook Form field errors.
 *
 * Layer: lib/utility
 * Feature: shared
 *
 * REQ-012 §13.2: Converts API field-level error arrays into React
 * Hook Form `setError` calls so validation messages appear inline.
 * Includes prototype-pollution guard for defence-in-depth.
 *
 * Coordinates with:
 * - lib/form-errors.ts: sibling error utility — friendly user-facing messages
 * - react-hook-form: setError integration point for all form components
 *
 * Called by / Used by:
 * - Currently no production consumers (available for form components needing
 *   server-error → field-error mapping)
 */

import type { FieldValues, Path, UseFormSetError } from "react-hook-form";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ServerFieldError {
	field: string;
	message: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/**
 * Field names that could cause prototype pollution if passed to Object
 * property assignment. Skipped silently to prevent attacks via crafted
 * server error responses.
 */
const DANGEROUS_FIELDS = new Set(["__proto__", "constructor", "prototype"]);

// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------

/**
 * Maps an array of server-side field errors to React Hook Form field errors.
 *
 * Each error's `field` is used as the form field path (supports dot notation
 * for nested fields, e.g., "address.city"). Use `field: "root"` for
 * form-level errors.
 *
 * Field names matching prototype pollution vectors (`__proto__`, `constructor`,
 * `prototype`) are silently skipped as a defense-in-depth measure.
 *
 * @remarks The `field as Path<TValues>` assertion is necessary because
 * server-supplied field names are dynamic strings. Invalid field names will
 * be set on the form errors object but won't match any rendered FormMessage.
 *
 * @example
 * ```ts
 * mapServerErrors(
 *   [{ field: "email", message: "Email already exists" }],
 *   form.setError,
 * );
 * ```
 */
export function mapServerErrors<TValues extends FieldValues>(
	fieldErrors: ServerFieldError[],
	setError: UseFormSetError<TValues>,
): void {
	for (const { field, message } of fieldErrors) {
		if (DANGEROUS_FIELDS.has(field.split(".")[0])) {
			continue;
		}
		setError(field as Path<TValues>, { type: "server", message });
	}
}
