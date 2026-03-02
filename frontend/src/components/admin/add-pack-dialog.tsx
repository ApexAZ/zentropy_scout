/**
 * Add Pack dialog form.
 *
 * REQ-022 §11.2, §10.4: Form with name, price (cents), credit amount,
 * and optional description. Validates numeric fields before submit.
 */

import { useCallback, useState } from "react";

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

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface AddPackDialogProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	isPending: boolean;
	onSubmit: (data: {
		name: string;
		price_cents: number;
		credit_amount: number;
		description?: string;
	}) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Dialog form for adding a new credit pack. */
export function AddPackDialog({
	open,
	onOpenChange,
	isPending,
	onSubmit,
}: Readonly<AddPackDialogProps>) {
	const [name, setName] = useState("");
	const [priceCents, setPriceCents] = useState("");
	const [creditAmount, setCreditAmount] = useState("");
	const [description, setDescription] = useState("");

	function resetForm() {
		setName("");
		setPriceCents("");
		setCreditAmount("");
		setDescription("");
	}

	const handleCreate = useCallback(() => {
		const cents = Number.parseInt(priceCents, 10);
		const credits = Number.parseInt(creditAmount, 10);
		if (
			Number.isNaN(cents) ||
			cents <= 0 ||
			Number.isNaN(credits) ||
			credits <= 0
		)
			return;
		onSubmit({
			name,
			price_cents: cents,
			credit_amount: credits,
			description: description || undefined,
		});
	}, [onSubmit, name, priceCents, creditAmount, description]);

	const handleOpenChange = useCallback(
		(nextOpen: boolean) => {
			if (!nextOpen) resetForm();
			onOpenChange(nextOpen);
		},
		[onOpenChange],
	);

	const cents = Number.parseInt(priceCents, 10);
	const credits = Number.parseInt(creditAmount, 10);
	const numericValid =
		!Number.isNaN(cents) && cents > 0 && !Number.isNaN(credits) && credits > 0;

	return (
		<Dialog open={open} onOpenChange={handleOpenChange}>
			<DialogContent>
				<DialogHeader>
					<DialogTitle>Add Pack</DialogTitle>
				</DialogHeader>
				<div className="space-y-4">
					<div className="space-y-2">
						<Label htmlFor="add-pack-name">Name</Label>
						<Input
							id="add-pack-name"
							value={name}
							onChange={(e) => setName(e.target.value)}
							placeholder="e.g. Starter Pack"
							maxLength={50}
						/>
					</div>
					<div className="space-y-2">
						<Label htmlFor="add-pack-price">Price (cents)</Label>
						<Input
							id="add-pack-price"
							value={priceCents}
							onChange={(e) => setPriceCents(e.target.value)}
							placeholder="e.g. 500"
							inputMode="numeric"
							maxLength={10}
						/>
					</div>
					<div className="space-y-2">
						<Label htmlFor="add-pack-credits">Credit Amount</Label>
						<Input
							id="add-pack-credits"
							value={creditAmount}
							onChange={(e) => setCreditAmount(e.target.value)}
							placeholder="e.g. 10000"
							inputMode="numeric"
							maxLength={15}
						/>
					</div>
					<div className="space-y-2">
						<Label htmlFor="add-pack-description">Description</Label>
						<Input
							id="add-pack-description"
							value={description}
							onChange={(e) => setDescription(e.target.value)}
							placeholder="Optional description"
							maxLength={255}
						/>
					</div>
				</div>
				<DialogFooter>
					<Button
						onClick={handleCreate}
						disabled={isPending || !name || !numericValid}
					>
						{isPending ? "Creating..." : "Create"}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
