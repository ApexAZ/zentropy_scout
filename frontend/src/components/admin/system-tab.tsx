"use client";

/**
 * System config management tab.
 *
 * REQ-022 §11.2, §10.5: Key-value config entries with add form
 * and delete confirmation. Uses PUT upsert for create/update.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus, Trash2 } from "lucide-react";

import { deleteConfig, fetchConfig, upsertConfig } from "@/lib/api/admin";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import { Button } from "@/components/ui/button";
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog";
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
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import type { SystemConfigItem } from "@/types/admin";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** System config management — list, add (upsert), delete. */
export function SystemTab() {
	const queryClient = useQueryClient();
	const [addOpen, setAddOpen] = useState(false);
	const [deleteTarget, setDeleteTarget] = useState<SystemConfigItem | null>(
		null,
	);

	// Form state
	const [key, setKey] = useState("");
	const [value, setValue] = useState("");
	const [description, setDescription] = useState("");

	// -----------------------------------------------------------------------
	// Queries
	// -----------------------------------------------------------------------

	const { data, isLoading, error, refetch } = useQuery({
		queryKey: queryKeys.adminConfig,
		queryFn: () => fetchConfig(),
	});

	// -----------------------------------------------------------------------
	// Mutations
	// -----------------------------------------------------------------------

	const upsertMut = useMutation({
		mutationFn: ({
			key: configKey,
			value: configValue,
			description: configDesc,
		}: {
			key: string;
			value: string;
			description: string;
		}) =>
			upsertConfig(configKey, {
				value: configValue,
				description: configDesc,
			}),
		onSuccess: () => {
			void queryClient.invalidateQueries({
				queryKey: queryKeys.adminConfig,
			});
			showToast.success("Config saved");
			setAddOpen(false);
			resetForm();
		},
		onError: () => {
			showToast.error("Failed to save config");
		},
	});

	const deleteMut = useMutation({
		mutationFn: (configKey: string) => deleteConfig(configKey),
		onSuccess: () => {
			void queryClient.invalidateQueries({
				queryKey: queryKeys.adminConfig,
			});
			showToast.success("Config deleted");
			setDeleteTarget(null);
		},
		onError: () => {
			showToast.error("Failed to delete config");
		},
	});

	// -----------------------------------------------------------------------
	// Form helpers
	// -----------------------------------------------------------------------

	function resetForm() {
		setKey("");
		setValue("");
		setDescription("");
	}

	function handleSave() {
		upsertMut.mutate({ key, value, description });
	}

	// -----------------------------------------------------------------------
	// Loading / Error
	// -----------------------------------------------------------------------

	if (isLoading) {
		return (
			<div data-testid="system-loading" className="flex justify-center py-12">
				<Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
			</div>
		);
	}

	if (error) {
		return (
			<div className="py-8 text-center">
				<p className="text-destructive mb-2">Failed to load config.</p>
				<Button variant="outline" size="sm" onClick={() => void refetch()}>
					Retry
				</Button>
			</div>
		);
	}

	const items = data?.data ?? [];

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	return (
		<div data-testid="system-tab" className="space-y-4 pt-4">
			<div className="flex items-center justify-between">
				<p className="text-muted-foreground text-sm">
					{items.length} config entr{items.length !== 1 ? "ies" : "y"}
				</p>
				<Button variant="outline" size="sm" onClick={() => setAddOpen(true)}>
					<Plus className="mr-1 h-4 w-4" />
					Add Config
				</Button>
			</div>

			{items.length === 0 ? (
				<p className="text-muted-foreground py-8 text-center text-sm">
					No config entries yet.
				</p>
			) : (
				<Table>
					<TableHeader>
						<TableRow>
							<TableHead>Key</TableHead>
							<TableHead>Value</TableHead>
							<TableHead>Description</TableHead>
							<TableHead className="text-right">Actions</TableHead>
						</TableRow>
					</TableHeader>
					<TableBody>
						{items.map((item) => (
							<TableRow key={item.key}>
								<TableCell className="font-mono text-xs">{item.key}</TableCell>
								<TableCell className="font-mono text-xs">
									{item.value}
								</TableCell>
								<TableCell className="text-muted-foreground text-sm">
									{item.description ?? "—"}
								</TableCell>
								<TableCell className="text-right">
									<Button
										variant="ghost"
										size="sm"
										aria-label="Delete"
										onClick={() => setDeleteTarget(item)}
									>
										<Trash2 className="h-4 w-4" />
									</Button>
								</TableCell>
							</TableRow>
						))}
					</TableBody>
				</Table>
			)}

			{/* Add Config Dialog */}
			<Dialog
				open={addOpen}
				onOpenChange={(open) => {
					if (!open) resetForm();
					setAddOpen(open);
				}}
			>
				<DialogContent>
					<DialogHeader>
						<DialogTitle>Add Config</DialogTitle>
					</DialogHeader>
					<div className="space-y-4">
						<div className="space-y-2">
							<Label htmlFor="add-config-key">Key</Label>
							<Input
								id="add-config-key"
								value={key}
								onChange={(e) => setKey(e.target.value)}
								placeholder="e.g. signup_grant_credits"
								maxLength={100}
							/>
						</div>
						<div className="space-y-2">
							<Label htmlFor="add-config-value">Value</Label>
							<Input
								id="add-config-value"
								value={value}
								onChange={(e) => setValue(e.target.value)}
								placeholder="e.g. 1000"
								maxLength={1000}
							/>
						</div>
						<div className="space-y-2">
							<Label htmlFor="add-config-description">Description</Label>
							<Input
								id="add-config-description"
								value={description}
								onChange={(e) => setDescription(e.target.value)}
								placeholder="Optional description"
								maxLength={255}
							/>
						</div>
					</div>
					<DialogFooter>
						<Button
							onClick={handleSave}
							disabled={upsertMut.isPending || !key || !value}
						>
							{upsertMut.isPending ? "Saving..." : "Save"}
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>

			{/* Delete Confirmation */}
			<ConfirmationDialog
				open={deleteTarget !== null}
				onOpenChange={(open) => {
					if (!open) setDeleteTarget(null);
				}}
				title="Delete Config?"
				description={`Are you sure you want to delete config key "${deleteTarget?.key}"?`}
				confirmLabel="Confirm"
				variant="destructive"
				loading={deleteMut.isPending}
				onConfirm={() => {
					if (deleteTarget) deleteMut.mutate(deleteTarget.key);
				}}
			/>
		</div>
	);
}
