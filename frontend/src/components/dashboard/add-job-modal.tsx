"use client";

/**
 * Two-step modal for manually ingesting a job posting.
 *
 * REQ-012 §8.7: "Add Job" modal in the Opportunities toolbar.
 * Step 1: Paste raw job text + select source → extract preview.
 * Step 2: Review extracted fields → confirm to create JobPosting.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { Loader2 } from "lucide-react";

import { ApiError, apiPost } from "@/lib/api-client";
import { toFriendlyError } from "@/lib/form-errors";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Form } from "@/components/ui/form";
import { FormInputField } from "@/components/form/form-input-field";
import { FormSelectField } from "@/components/form/form-select-field";
import { FormTextareaField } from "@/components/form/form-textarea-field";
import { SubmitButton } from "@/components/form/submit-button";
import type { ApiResponse } from "@/types/api";
import type {
	IngestConfirmResponse,
	IngestJobPostingResponse,
	IngestPreview,
} from "@/types/ingest";
import { INGEST_SOURCE_NAMES } from "@/types/ingest";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SOURCE_OPTIONS = INGEST_SOURCE_NAMES.map((name) => ({
	label: name,
	value: name,
}));

// ---------------------------------------------------------------------------
// Zod Schema
// ---------------------------------------------------------------------------

const ingestFormSchema = z.object({
	source_name: z.string().min(1, { message: "Source is required" }),
	source_url: z
		.url({ message: "Must be a valid URL" })
		.or(z.literal(""))
		.optional()
		.transform((v) => (v === "" ? undefined : v)),
	raw_text: z
		.string()
		.min(1, { message: "Job posting text is required" })
		.max(50000, { message: "Text must be under 50,000 characters" }),
});

type IngestFormValues = z.input<typeof ingestFormSchema>;

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface AddJobModalProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatCurrency(amount: number, currency: string | null): string {
	return new Intl.NumberFormat("en-US", {
		style: "currency",
		currency: currency ?? "USD",
		maximumFractionDigits: 0,
	}).format(amount);
}

function formatCountdown(seconds: number): string {
	const m = Math.floor(seconds / 60);
	const s = seconds % 60;
	return `${m}:${String(s).padStart(2, "0")}`;
}

// ---------------------------------------------------------------------------
// Sub-component: Preview display
// ---------------------------------------------------------------------------

function PreviewField({
	label,
	value,
}: Readonly<{
	label: string;
	value: string | null | undefined;
}>) {
	return (
		<div>
			<dt className="text-muted-foreground text-xs font-medium">{label}</dt>
			<dd className="text-sm">{value ?? "\u2014"}</dd>
		</div>
	);
}

function PreviewContent({ preview }: Readonly<{ preview: IngestPreview }>) {
	const salaryText =
		preview.salary_min !== null || preview.salary_max !== null
			? [
					preview.salary_min === null
						? null
						: formatCurrency(preview.salary_min, preview.salary_currency),
					preview.salary_max === null
						? null
						: formatCurrency(preview.salary_max, preview.salary_currency),
				]
					.filter(Boolean)
					.join(" \u2013 ")
			: null;

	return (
		<dl className="grid grid-cols-2 gap-3">
			<PreviewField label="Job Title" value={preview.job_title} />
			<PreviewField label="Company" value={preview.company_name} />
			<PreviewField label="Location" value={preview.location} />
			<PreviewField label="Employment Type" value={preview.employment_type} />
			<PreviewField label="Salary" value={salaryText} />
			<PreviewField label="Culture" value={preview.culture_text} />
			{preview.extracted_skills.length > 0 && (
				<div className="col-span-2">
					<dt className="text-muted-foreground text-xs font-medium">Skills</dt>
					<dd className="mt-1 flex flex-wrap gap-1">
						{preview.extracted_skills.map((skill) => (
							<span
								key={skill.skill_name}
								className="bg-muted rounded-md px-2 py-0.5 text-xs"
							>
								{skill.skill_name}
								{skill.years_requested !== null && (
									<span className="text-muted-foreground ml-1">
										({skill.years_requested}y)
									</span>
								)}
							</span>
						))}
					</dd>
				</div>
			)}
		</dl>
	);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function AddJobModal({
	open,
	onOpenChange,
}: Readonly<AddJobModalProps>) {
	const router = useRouter();
	const queryClient = useQueryClient();
	const [step, setStep] = useState<"submit" | "preview">("submit");
	const [ingestResponse, setIngestResponse] =
		useState<IngestJobPostingResponse | null>(null);
	const [isConfirming, setIsConfirming] = useState(false);
	const [secondsLeft, setSecondsLeft] = useState<number | null>(null);
	const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

	const form = useForm<IngestFormValues>({
		resolver: zodResolver(ingestFormSchema),
		defaultValues: {
			source_name: "",
			source_url: "",
			raw_text: "",
		},
	});

	// Reset when modal closes
	useEffect(() => {
		if (!open) {
			setStep("submit");
			setIngestResponse(null);
			setIsConfirming(false);
			setSecondsLeft(null);
			form.reset();
			if (timerRef.current) {
				clearInterval(timerRef.current);
				timerRef.current = null;
			}
		}
	}, [open, form]);

	// Countdown timer for step 2
	useEffect(() => {
		if (step !== "preview" || !ingestResponse) return;

		const expiresAt = new Date(ingestResponse.expires_at).getTime();

		function updateTimer() {
			const remaining = Math.max(
				0,
				Math.floor((expiresAt - Date.now()) / 1000),
			);
			setSecondsLeft(remaining);
			if (remaining <= 0 && timerRef.current) {
				clearInterval(timerRef.current);
				timerRef.current = null;
			}
		}

		updateTimer();
		timerRef.current = setInterval(updateTimer, 1000);

		return () => {
			if (timerRef.current) {
				clearInterval(timerRef.current);
				timerRef.current = null;
			}
		};
	}, [step, ingestResponse]);

	const handleExtract = useCallback(async (values: IngestFormValues) => {
		try {
			const body: Record<string, string> = {
				raw_text: values.raw_text,
				source_name: values.source_name,
			};
			if (values.source_url) {
				body.source_url = values.source_url;
			}

			const res = await apiPost<ApiResponse<IngestJobPostingResponse>>(
				"/job-postings/ingest",
				body,
			);
			setIngestResponse(res.data);
			setStep("preview");
		} catch (err) {
			showToast.error(toFriendlyError(err));
		}
	}, []);

	const handleConfirm = useCallback(async () => {
		if (!ingestResponse) return;

		setIsConfirming(true);
		try {
			const res = await apiPost<ApiResponse<IngestConfirmResponse>>(
				"/job-postings/ingest/confirm",
				{ confirmation_token: ingestResponse.confirmation_token },
			);
			await queryClient.invalidateQueries({ queryKey: queryKeys.jobs });
			showToast.success("Job saved successfully.");
			onOpenChange(false);
			router.push(`/jobs/${res.data.id}`);
		} catch (err) {
			if (err instanceof ApiError && err.code === "TOKEN_EXPIRED") {
				showToast.error(toFriendlyError(err));
				setStep("submit");
				setIngestResponse(null);
			} else {
				showToast.error(toFriendlyError(err));
			}
		} finally {
			setIsConfirming(false);
		}
	}, [ingestResponse, queryClient, onOpenChange, router]);

	const isExpired = secondsLeft !== null && secondsLeft <= 0;

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="sm:max-w-lg">
				{step === "submit" ? (
					<>
						<DialogHeader>
							<DialogTitle>Add Job</DialogTitle>
							<DialogDescription>
								Paste a job posting to extract and save it.
							</DialogDescription>
						</DialogHeader>

						<Form {...form}>
							<form
								onSubmit={form.handleSubmit(handleExtract)}
								className="space-y-4"
							>
								<FormSelectField
									control={form.control}
									name="source_name"
									label="Source"
									options={SOURCE_OPTIONS}
									placeholder="Select source..."
								/>

								<FormInputField
									control={form.control}
									name="source_url"
									label="Source URL"
									type="url"
									placeholder="https://..."
								/>

								<FormTextareaField
									control={form.control}
									name="raw_text"
									label="Job Posting Text"
									placeholder="Paste the full job posting text here..."
									rows={8}
								/>

								<DialogFooter>
									<Button
										type="button"
										variant="outline"
										onClick={() => onOpenChange(false)}
									>
										Cancel
									</Button>
									<SubmitButton
										label="Extract & Preview"
										isSubmitting={form.formState.isSubmitting}
										loadingLabel="Extracting..."
									/>
								</DialogFooter>
							</form>
						</Form>
					</>
				) : (
					<>
						<DialogHeader>
							<DialogTitle>Preview Extracted Data</DialogTitle>
							<DialogDescription>
								Review the extracted information before saving.
							</DialogDescription>
						</DialogHeader>

						{ingestResponse && (
							<PreviewContent preview={ingestResponse.preview} />
						)}

						<div
							data-testid="countdown-timer"
							className="text-muted-foreground text-center text-sm"
						>
							{isExpired ? (
								<span className="text-destructive">
									Preview expired. Go back and resubmit.
								</span>
							) : (
								<span>Expires in {formatCountdown(secondsLeft ?? 0)}</span>
							)}
						</div>

						<DialogFooter>
							<Button
								type="button"
								variant="outline"
								onClick={() => {
									setStep("submit");
									setIngestResponse(null);
								}}
							>
								Back
							</Button>
							<Button
								type="button"
								disabled={isConfirming || isExpired}
								onClick={handleConfirm}
								className="gap-2"
							>
								{isConfirming && (
									<Loader2
										data-testid="confirm-spinner"
										className="h-4 w-4 animate-spin"
										aria-hidden="true"
									/>
								)}
								{isConfirming ? "Saving..." : "Confirm & Save"}
							</Button>
						</DialogFooter>
					</>
				)}
			</DialogContent>
		</Dialog>
	);
}
