/**
 * Add Routing dialog form.
 *
 * REQ-022 §11.2, §10.3: Form with provider select, task type, and model.
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

import { PROVIDERS } from "./constants";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface AddRoutingDialogProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	isPending: boolean;
	onSubmit: (data: {
		provider: string;
		task_type: string;
		model: string;
	}) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Dialog form for adding a new task routing entry. */
export function AddRoutingDialog({
	open,
	onOpenChange,
	isPending,
	onSubmit,
}: Readonly<AddRoutingDialogProps>) {
	const [provider, setProvider] = useState("");
	const [taskType, setTaskType] = useState("");
	const [model, setModel] = useState("");

	function resetForm() {
		setProvider("");
		setTaskType("");
		setModel("");
	}

	const handleCreate = useCallback(() => {
		onSubmit({ provider, task_type: taskType, model });
	}, [onSubmit, provider, taskType, model]);

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
					<DialogTitle>Add Routing</DialogTitle>
				</DialogHeader>
				<div className="space-y-4">
					<div className="space-y-2">
						<Label htmlFor="add-routing-provider">Provider</Label>
						<Select value={provider} onValueChange={setProvider}>
							<SelectTrigger id="add-routing-provider">
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
						<Label htmlFor="add-routing-task-type">Task Type</Label>
						<Input
							id="add-routing-task-type"
							value={taskType}
							onChange={(e) => setTaskType(e.target.value)}
							placeholder="e.g. extraction, _default"
							maxLength={50}
						/>
					</div>
					<div className="space-y-2">
						<Label htmlFor="add-routing-model">Model</Label>
						<Input
							id="add-routing-model"
							value={model}
							onChange={(e) => setModel(e.target.value)}
							placeholder="e.g. claude-3-5-haiku-20241022"
							maxLength={100}
						/>
					</div>
				</div>
				<DialogFooter>
					<Button
						onClick={handleCreate}
						disabled={isPending || !provider || !taskType || !model}
					>
						{isPending ? "Creating..." : "Create"}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
