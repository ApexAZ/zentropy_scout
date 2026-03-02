/**
 * Add Model dialog form.
 *
 * REQ-022 §11.2: Form with provider, model ID, display name, and model type.
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
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";

import { MODEL_TYPES, PROVIDERS } from "./constants";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface AddModelDialogProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	isPending: boolean;
	onSubmit: (data: {
		provider: string;
		model: string;
		display_name: string;
		model_type: string;
	}) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Dialog form for adding a new model to the registry. */
export function AddModelDialog({
	open,
	onOpenChange,
	isPending,
	onSubmit,
}: Readonly<AddModelDialogProps>) {
	const [provider, setProvider] = useState("");
	const [model, setModel] = useState("");
	const [displayName, setDisplayName] = useState("");
	const [modelType, setModelType] = useState("");

	function resetForm() {
		setProvider("");
		setModel("");
		setDisplayName("");
		setModelType("");
	}

	const handleCreate = useCallback(() => {
		onSubmit({
			provider,
			model,
			display_name: displayName,
			model_type: modelType,
		});
	}, [onSubmit, provider, model, displayName, modelType]);

	// Reset form when dialog closes
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
					<DialogTitle>Add Model</DialogTitle>
				</DialogHeader>
				<div className="space-y-4">
					<div className="space-y-2">
						<Label htmlFor="add-provider">Provider</Label>
						<Select value={provider} onValueChange={setProvider}>
							<SelectTrigger id="add-provider">
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
						<Label htmlFor="add-model">Model</Label>
						<Input
							id="add-model"
							value={model}
							onChange={(e) => setModel(e.target.value)}
							placeholder="e.g. claude-3-5-haiku-20241022"
							maxLength={100}
						/>
					</div>
					<div className="space-y-2">
						<Label htmlFor="add-display-name">Display Name</Label>
						<Input
							id="add-display-name"
							value={displayName}
							onChange={(e) => setDisplayName(e.target.value)}
							placeholder="e.g. Claude 3.5 Haiku"
							maxLength={100}
						/>
					</div>
					<div className="space-y-2">
						<Label htmlFor="add-model-type">Model Type</Label>
						<Select value={modelType} onValueChange={setModelType}>
							<SelectTrigger id="add-model-type">
								<SelectValue placeholder="Select type" />
							</SelectTrigger>
							<SelectContent>
								{MODEL_TYPES.map((t) => (
									<SelectItem key={t} value={t}>
										{t}
									</SelectItem>
								))}
							</SelectContent>
						</Select>
					</div>
				</div>
				<DialogFooter>
					<Button
						onClick={handleCreate}
						disabled={
							isPending || !provider || !model || !displayName || !modelType
						}
					>
						{isPending ? "Creating..." : "Create"}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
