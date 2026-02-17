"use client";

/**
 * Certification form for adding/editing a certification entry.
 *
 * REQ-012 §6.3.6: Fields — certification_name, issuing_organization,
 * date_obtained (required), expiration_date, credential_id,
 * verification_url (optional). "Does not expire" checkbox nulls
 * the expiration_date field.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { useCallback, useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { FormActionFooter } from "@/components/form/form-action-footer";
import { FormInputField } from "@/components/form/form-input-field";
import { Checkbox } from "@/components/ui/checkbox";
import {
	Form,
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MAX_CERT_NAME_LENGTH = 255;
const MAX_ISSUER_LENGTH = 255;
const MAX_CREDENTIAL_ID_LENGTH = 100;
const MAX_URL_LENGTH = 2083;

/** Shared two-column grid layout class. */
const GRID_TWO_COL = "grid gap-4 sm:grid-cols-2";

// ---------------------------------------------------------------------------
// Validation schema
// ---------------------------------------------------------------------------

const certificationFormSchema = z.object({
	certification_name: z
		.string()
		.min(1, { message: "Certification name is required" })
		.max(MAX_CERT_NAME_LENGTH, { message: "Certification name is too long" }),
	issuing_organization: z
		.string()
		.min(1, { message: "Issuing organization is required" })
		.max(MAX_ISSUER_LENGTH, { message: "Issuing organization is too long" }),
	date_obtained: z.string().min(1, { message: "Date obtained is required" }),
	does_not_expire: z.boolean(),
	expiration_date: z.string().optional().or(z.literal("")),
	credential_id: z
		.string()
		.max(MAX_CREDENTIAL_ID_LENGTH, { message: "Credential ID is too long" })
		.optional()
		.or(z.literal("")),
	verification_url: z
		.string()
		.max(MAX_URL_LENGTH, { message: "URL is too long" })
		.optional()
		.or(z.literal(""))
		.refine(
			(val) => {
				if (!val || val === "") return true;
				try {
					const url = new URL(val);
					return url.protocol === "https:" || url.protocol === "http:";
				} catch {
					return false;
				}
			},
			{ message: "Enter a valid URL (http:// or https://)" },
		),
});

export type CertificationFormData = z.infer<typeof certificationFormSchema>;

/** Default form values for a new entry. */
const DEFAULT_VALUES: CertificationFormData = {
	certification_name: "",
	issuing_organization: "",
	date_obtained: "",
	does_not_expire: false,
	expiration_date: "",
	credential_id: "",
	verification_url: "",
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface CertificationFormProps {
	/** Pre-fill values for editing. Omit for add mode. */
	initialValues?: Partial<CertificationFormData>;
	/** Called with validated form data on save. */
	onSave: (data: CertificationFormData) => Promise<void>;
	/** Called when user cancels. */
	onCancel: () => void;
	/** Whether the form is currently submitting. */
	isSubmitting: boolean;
	/** Error message to display below the form. */
	submitError: string | null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CertificationForm({
	initialValues,
	onSave,
	onCancel,
	isSubmitting,
	submitError,
}: Readonly<CertificationFormProps>) {
	const defaultVals: CertificationFormData = {
		...DEFAULT_VALUES,
		...initialValues,
	};

	const form = useForm<CertificationFormData>({
		resolver: zodResolver(certificationFormSchema),
		defaultValues: defaultVals,
		mode: "onTouched",
	});

	const watchedDoesNotExpire = form.watch("does_not_expire");

	// Clear expiration_date when "Does not expire" is checked
	useEffect(() => {
		if (watchedDoesNotExpire) {
			form.setValue("expiration_date", "", { shouldValidate: false });
		}
	}, [watchedDoesNotExpire, form]);

	const handleSubmit = useCallback(
		async (data: CertificationFormData) => {
			await onSave(data);
		},
		[onSave],
	);

	return (
		<div data-testid="certification-form">
			<Form {...form}>
				<form
					onSubmit={form.handleSubmit(handleSubmit)}
					className="space-y-4"
					noValidate
				>
					<FormInputField
						control={form.control}
						name="certification_name"
						label="Certification Name"
						placeholder="AWS Solutions Architect"
					/>

					<FormInputField
						control={form.control}
						name="issuing_organization"
						label="Issuing Organization"
						placeholder="Amazon Web Services"
					/>

					<div className={GRID_TWO_COL}>
						<FormField
							control={form.control}
							name="date_obtained"
							render={({ field }) => (
								<FormItem>
									<FormLabel>Date Obtained</FormLabel>
									<FormControl>
										<Input type="date" {...field} />
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>
						<FormField
							control={form.control}
							name="expiration_date"
							render={({ field }) => (
								<FormItem>
									<FormLabel>Expiration Date</FormLabel>
									<FormControl>
										<Input
											type="date"
											{...field}
											value={field.value ?? ""}
											disabled={watchedDoesNotExpire}
										/>
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>
					</div>

					{/* "Does not expire" checkbox */}
					<FormField
						control={form.control}
						name="does_not_expire"
						render={({ field }) => (
							<FormItem className="flex items-center gap-2">
								<FormControl>
									<Checkbox
										checked={field.value}
										onCheckedChange={field.onChange}
										id="does-not-expire"
									/>
								</FormControl>
								<FormLabel
									htmlFor="does-not-expire"
									className="!mt-0 cursor-pointer text-sm font-normal"
								>
									Does not expire
								</FormLabel>
							</FormItem>
						)}
					/>

					<div className={GRID_TWO_COL}>
						<FormInputField
							control={form.control}
							name="credential_id"
							label="Credential ID (optional)"
							placeholder="ABC-123"
						/>
						<FormInputField
							control={form.control}
							name="verification_url"
							label="Verification URL (optional)"
							placeholder="https://verify.example.com/..."
						/>
					</div>

					<FormActionFooter
						submitError={submitError}
						isSubmitting={isSubmitting}
						onCancel={onCancel}
					/>
				</form>
			</Form>
		</div>
	);
}
