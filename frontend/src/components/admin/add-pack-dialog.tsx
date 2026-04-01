/**
 * @fileoverview Add Pack dialog form for the admin funding packs tab.
 *
 * Layer: component
 * Feature: admin
 *
 * REQ-022 §11.2, §10.4: Form with name, price (cents), grant amount,
 * and optional description. Validates numeric fields before submit.
 *
 * Coordinates with:
 * - components/ui/button.tsx: Button for create action
 * - components/ui/dialog.tsx: Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle for modal
 * - components/ui/input.tsx: Input for name, price, grant, and description fields
 * - components/ui/label.tsx: Label for form fields
 *
 * Called by / Used by:
 * - components/admin/packs-tab.tsx: add pack dialog in funding packs tab
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
		grant_cents: number;
		description?: string;
	}) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Dialog form for adding a new funding pack. */
export function AddPackDialog({
	open,
	onOpenChange,
	isPending,
	onSubmit,
}: Readonly<AddPackDialogProps>) {
	const [name, setName] = useState("");
	const [priceCents, setPriceCents] = useState("");
	const [grantCents, setGrantCents] = useState("");
	const [description, setDescription] = useState("");

	function resetForm() {
		setName("");
		setPriceCents("");
		setGrantCents("");
		setDescription("");
	}

	const handleCreate = useCallback(() => {
		const cents = Number.parseInt(priceCents, 10);
		const credits = Number.parseInt(grantCents, 10);
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
			grant_cents: credits,
			description: description || undefined,
		});
	}, [onSubmit, name, priceCents, grantCents, description]);

	const handleOpenChange = useCallback(
		(nextOpen: boolean) => {
			if (!nextOpen) resetForm();
			onOpenChange(nextOpen);
		},
		[onOpenChange],
	);

	const cents = Number.parseInt(priceCents, 10);
	const credits = Number.parseInt(grantCents, 10);
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
						<Label htmlFor="add-pack-grant-cents">Grant Amount (cents)</Label>
						<Input
							id="add-pack-grant-cents"
							value={grantCents}
							onChange={(e) => setGrantCents(e.target.value)}
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
