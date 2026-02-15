"use client";

/**
 * Dialog for capturing offer details during Offer status transition.
 *
 * REQ-012 §11.5: Offer details form with all-optional fields.
 * Triggered from StatusTransitionDropdown when user selects Offer,
 * or from the OfferDetailsCard Edit button.
 */

import { useCallback, useState } from "react";
import { AlertDialog as AlertDialogPrimitive } from "radix-ui";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type { OfferDetails } from "@/types/application";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CURRENCIES = ["USD", "EUR", "GBP", "CAD", "AUD", "CHF", "JPY"] as const;
const DEFAULT_CURRENCY = "USD";
const EQUITY_TYPES = ["RSU", "Options"] as const;
const FIELD_WRAPPER_CLASS = "space-y-1";
const OFFER_TEXT_MAX_LENGTH = 2_000;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface OfferDetailsDialogProps {
	open: boolean;
	onConfirm: (details: OfferDetails) => void;
	onCancel: () => void;
	loading?: boolean;
	initialData?: OfferDetails | null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function OfferDetailsDialog({
	open,
	onConfirm,
	onCancel,
	loading = false,
	initialData,
}: OfferDetailsDialogProps) {
	const [form, setForm] = useState<OfferDetails>({
		salary_currency: DEFAULT_CURRENCY,
	});

	// Adjust state when dialog opens (React "deriving state from props" pattern)
	const [prevOpen, setPrevOpen] = useState(false);
	if (open !== prevOpen) {
		setPrevOpen(open);
		if (open) {
			setForm(
				initialData
					? { ...initialData }
					: { salary_currency: DEFAULT_CURRENCY },
			);
		}
	}

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	const updateNumber = useCallback((key: keyof OfferDetails, value: string) => {
		if (value === "") {
			setForm((prev) => ({ ...prev, [key]: undefined }));
			return;
		}
		const num = Number(value);
		if (!Number.isFinite(num) || num < 0) return;
		setForm((prev) => ({ ...prev, [key]: num }));
	}, []);

	const updateString = useCallback((key: keyof OfferDetails, value: string) => {
		setForm((prev) => ({
			...prev,
			[key]: value === "" ? undefined : value,
		}));
	}, []);

	const handleConfirm = useCallback(() => {
		onConfirm(form);
	}, [form, onConfirm]);

	const handleOpenChange = useCallback(
		(isOpen: boolean) => {
			if (!isOpen) {
				onCancel();
			}
		},
		[onCancel],
	);

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	return (
		<AlertDialogPrimitive.Root open={open} onOpenChange={handleOpenChange}>
			<AlertDialogPrimitive.Portal>
				<AlertDialogPrimitive.Overlay className="data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 fixed inset-0 z-50 bg-black/50" />
				<AlertDialogPrimitive.Content
					className={cn(
						"bg-background data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 fixed top-[50%] left-[50%] z-50 grid w-full max-w-[calc(100%-2rem)] translate-x-[-50%] translate-y-[-50%] gap-4 rounded-lg border p-6 shadow-lg duration-200 outline-none sm:max-w-lg",
					)}
				>
					<div className="flex flex-col gap-2 text-center sm:text-left">
						<AlertDialogPrimitive.Title className="text-lg leading-none font-semibold">
							Offer Details
						</AlertDialogPrimitive.Title>
						<AlertDialogPrimitive.Description className="text-muted-foreground text-sm">
							Capture offer details. All fields are optional.
						</AlertDialogPrimitive.Description>
					</div>

					{/* Form fields */}
					<div className="grid grid-cols-2 gap-4">
						{/* Base Salary */}
						<div className={FIELD_WRAPPER_CLASS}>
							<Label htmlFor="offer-base-salary">Base Salary</Label>
							<Input
								id="offer-base-salary"
								type="number"
								min={0}
								max={99_999_999}
								value={form.base_salary ?? ""}
								onChange={(e) => updateNumber("base_salary", e.target.value)}
							/>
						</div>

						{/* Currency */}
						<div className={FIELD_WRAPPER_CLASS}>
							<Label htmlFor="offer-currency">Currency</Label>
							<Select
								value={form.salary_currency ?? DEFAULT_CURRENCY}
								onValueChange={(v) => updateString("salary_currency", v)}
							>
								<SelectTrigger
									id="offer-currency"
									data-testid="currency-select"
								>
									<SelectValue />
								</SelectTrigger>
								<SelectContent>
									{CURRENCIES.map((c) => (
										<SelectItem key={c} value={c}>
											{c}
										</SelectItem>
									))}
								</SelectContent>
							</Select>
						</div>

						{/* Bonus */}
						<div className={FIELD_WRAPPER_CLASS}>
							<Label htmlFor="offer-bonus">Bonus (%)</Label>
							<Input
								id="offer-bonus"
								type="number"
								min={0}
								max={100}
								value={form.bonus_percent ?? ""}
								onChange={(e) => updateNumber("bonus_percent", e.target.value)}
							/>
						</div>

						{/* Equity Value */}
						<div className={FIELD_WRAPPER_CLASS}>
							<Label htmlFor="offer-equity-value">Equity Value</Label>
							<Input
								id="offer-equity-value"
								type="number"
								min={0}
								max={99_999_999}
								value={form.equity_value ?? ""}
								onChange={(e) => updateNumber("equity_value", e.target.value)}
							/>
						</div>

						{/* Equity Type */}
						<div className={FIELD_WRAPPER_CLASS}>
							<Label htmlFor="offer-equity-type">Equity Type</Label>
							<Select
								value={form.equity_type ?? ""}
								onValueChange={(v) =>
									updateString("equity_type", v as "RSU" | "Options")
								}
							>
								<SelectTrigger
									id="offer-equity-type"
									data-testid="equity-type-select"
								>
									<SelectValue placeholder="Select type" />
								</SelectTrigger>
								<SelectContent>
									{EQUITY_TYPES.map((t) => (
										<SelectItem key={t} value={t}>
											{t}
										</SelectItem>
									))}
								</SelectContent>
							</Select>
						</div>

						{/* Vesting Years */}
						<div className={FIELD_WRAPPER_CLASS}>
							<Label htmlFor="offer-vesting-years">Vesting Years</Label>
							<Input
								id="offer-vesting-years"
								type="number"
								min={0}
								max={10}
								step={1}
								value={form.equity_vesting_years ?? ""}
								onChange={(e) =>
									updateNumber("equity_vesting_years", e.target.value)
								}
							/>
						</div>

						{/* Start Date */}
						<div className={FIELD_WRAPPER_CLASS}>
							<Label htmlFor="offer-start-date">Start Date</Label>
							<Input
								id="offer-start-date"
								type="date"
								value={form.start_date ?? ""}
								onChange={(e) => updateString("start_date", e.target.value)}
							/>
						</div>

						{/* Response Deadline */}
						<div className={FIELD_WRAPPER_CLASS}>
							<Label htmlFor="offer-deadline">Response Deadline</Label>
							<Input
								id="offer-deadline"
								type="date"
								value={form.response_deadline ?? ""}
								onChange={(e) =>
									updateString("response_deadline", e.target.value)
								}
							/>
						</div>
					</div>

					{/* Full-width textareas */}
					<div className={FIELD_WRAPPER_CLASS}>
						<Label htmlFor="offer-benefits">Benefits</Label>
						<Textarea
							id="offer-benefits"
							rows={3}
							maxLength={OFFER_TEXT_MAX_LENGTH}
							value={form.other_benefits ?? ""}
							onChange={(e) => updateString("other_benefits", e.target.value)}
							placeholder="e.g., 401k 6% match, unlimited PTO"
						/>
					</div>

					<div className={FIELD_WRAPPER_CLASS}>
						<Label htmlFor="offer-notes">Notes</Label>
						<Textarea
							id="offer-notes"
							rows={3}
							maxLength={OFFER_TEXT_MAX_LENGTH}
							value={form.notes ?? ""}
							onChange={(e) => updateString("notes", e.target.value)}
							placeholder="e.g., Negotiated from 140k"
						/>
					</div>

					{/* Buttons */}
					<div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
						<AlertDialogPrimitive.Cancel asChild>
							<Button variant="outline" disabled={loading}>
								Cancel
							</Button>
						</AlertDialogPrimitive.Cancel>
						<Button disabled={loading} onClick={handleConfirm}>
							Save
						</Button>
					</div>
				</AlertDialogPrimitive.Content>
			</AlertDialogPrimitive.Portal>
		</AlertDialogPrimitive.Root>
	);
}
