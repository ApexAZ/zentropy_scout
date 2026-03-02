/**
 * Add Pricing dialog form with live cost preview.
 *
 * REQ-022 §11.2, §11.5: Form with provider, model, costs, margin,
 * effective date. Shows live cost preview for example token counts.
 */

import { useCallback, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import type { PricingConfigCreateRequest } from "@/types/admin";

import { PROVIDERS } from "./constants";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Example token counts for cost preview (REQ-022 §11.5). */
const PREVIEW_INPUT_TOKENS = 1000;
const PREVIEW_OUTPUT_TOKENS = 500;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Compute cost preview for a given pricing configuration.
 *
 * Returns null if any input is invalid or empty.
 */
function computeCostPreview(
	inputCost: string,
	outputCost: string,
	margin: string,
): { raw: string; billed: string; marginDisplay: string } | null {
	const inputNum = Number(inputCost);
	const outputNum = Number(outputCost);
	const marginNum = Number(margin);

	if (
		!inputCost ||
		!outputCost ||
		!margin ||
		Number.isNaN(inputNum) ||
		Number.isNaN(outputNum) ||
		Number.isNaN(marginNum) ||
		marginNum <= 0
	) {
		return null;
	}

	const rawCost =
		(inputNum * PREVIEW_INPUT_TOKENS) / 1000 +
		(outputNum * PREVIEW_OUTPUT_TOKENS) / 1000;
	const billedCost = rawCost * marginNum;

	return {
		raw: `$${rawCost.toFixed(6)}`,
		billed: `$${billedCost.toFixed(6)}`,
		marginDisplay: `x${marginNum.toFixed(2)}`,
	};
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface AddPricingDialogProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	isPending: boolean;
	onSubmit: (data: PricingConfigCreateRequest) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Dialog form for adding pricing with live cost preview. */
export function AddPricingDialog({
	open,
	onOpenChange,
	isPending,
	onSubmit,
}: Readonly<AddPricingDialogProps>) {
	const [provider, setProvider] = useState("");
	const [model, setModel] = useState("");
	const [inputCost, setInputCost] = useState("");
	const [outputCost, setOutputCost] = useState("");
	const [margin, setMargin] = useState("");
	const [effectiveDate, setEffectiveDate] = useState("");

	const costPreview = useMemo(
		() => computeCostPreview(inputCost, outputCost, margin),
		[inputCost, outputCost, margin],
	);

	function resetForm() {
		setProvider("");
		setModel("");
		setInputCost("");
		setOutputCost("");
		setMargin("");
		setEffectiveDate("");
	}

	const handleCreate = useCallback(() => {
		onSubmit({
			provider,
			model,
			input_cost_per_1k: inputCost,
			output_cost_per_1k: outputCost,
			margin_multiplier: margin,
			effective_date: effectiveDate,
		});
	}, [onSubmit, provider, model, inputCost, outputCost, margin, effectiveDate]);

	const handleOpenChange = useCallback(
		(nextOpen: boolean) => {
			if (!nextOpen) resetForm();
			onOpenChange(nextOpen);
		},
		[onOpenChange],
	);

	return (
		<Dialog open={open} onOpenChange={handleOpenChange}>
			<DialogContent>
				<DialogHeader>
					<DialogTitle>Add Pricing</DialogTitle>
				</DialogHeader>
				<div className="space-y-4">
					<div className="space-y-2">
						<Label htmlFor="price-provider">Provider</Label>
						<Select value={provider} onValueChange={setProvider}>
							<SelectTrigger id="price-provider">
								<SelectValue placeholder="Select provider" />
							</SelectTrigger>
							<SelectContent>
								{PROVIDERS.map((p) => (
									<SelectItem key={p} value={p}>
										{p}
									</SelectItem>
								))}
							</SelectContent>
						</Select>
					</div>
					<div className="space-y-2">
						<Label htmlFor="price-model">Model</Label>
						<Input
							id="price-model"
							value={model}
							onChange={(e) => setModel(e.target.value)}
							placeholder="e.g. claude-3-5-haiku-20241022"
							maxLength={100}
						/>
					</div>
					<div className="grid grid-cols-3 gap-4">
						<div className="space-y-2">
							<Label htmlFor="price-input-cost">Input Cost / 1K</Label>
							<Input
								id="price-input-cost"
								value={inputCost}
								onChange={(e) => setInputCost(e.target.value)}
								placeholder="0.001"
								inputMode="decimal"
								maxLength={20}
							/>
						</div>
						<div className="space-y-2">
							<Label htmlFor="price-output-cost">Output Cost / 1K</Label>
							<Input
								id="price-output-cost"
								value={outputCost}
								onChange={(e) => setOutputCost(e.target.value)}
								placeholder="0.005"
								inputMode="decimal"
								maxLength={20}
							/>
						</div>
						<div className="space-y-2">
							<Label htmlFor="price-margin">Margin</Label>
							<Input
								id="price-margin"
								value={margin}
								onChange={(e) => setMargin(e.target.value)}
								placeholder="3.0"
								inputMode="decimal"
								maxLength={10}
							/>
						</div>
					</div>
					<div className="space-y-2">
						<Label htmlFor="price-effective-date">Effective Date</Label>
						<Input
							id="price-effective-date"
							type="date"
							value={effectiveDate}
							onChange={(e) => setEffectiveDate(e.target.value)}
						/>
					</div>

					{/* Live cost preview (REQ-022 §11.5) */}
					{costPreview && (
						<div
							data-testid="cost-preview"
							className="bg-muted rounded-md p-3 font-mono text-xs"
						>
							<p className="text-muted-foreground mb-1">
								Example: {PREVIEW_INPUT_TOKENS.toLocaleString()} input +{" "}
								{PREVIEW_OUTPUT_TOKENS.toLocaleString()} output tokens
							</p>
							<p>
								Raw cost:{" "}
								<span className="font-semibold">{costPreview.raw}</span>
							</p>
							<p>
								Billed cost:{" "}
								<span className="font-semibold">{costPreview.billed}</span> (
								{costPreview.marginDisplay} margin)
							</p>
						</div>
					)}
				</div>
				<DialogFooter>
					<Button
						onClick={handleCreate}
						disabled={
							isPending ||
							!provider ||
							!model ||
							!inputCost ||
							!outputCost ||
							!margin ||
							!effectiveDate
						}
					>
						{isPending ? "Creating..." : "Create"}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
