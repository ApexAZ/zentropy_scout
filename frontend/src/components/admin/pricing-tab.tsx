"use client";

/**
 * @fileoverview Pricing config management tab for the admin page.
 *
 * Layer: component
 * Feature: admin
 *
 * REQ-022 §11.2, §11.5: Table of pricing entries with effective dates,
 * "Current" badge, add/edit form with live cost preview.
 *
 * Coordinates with:
 * - lib/api/admin.ts: createPricing, deletePricing, fetchPricing for API calls
 * - lib/query-keys.ts: queryKeys for cache key management
 * - lib/toast.ts: showToast for success/error feedback
 * - components/ui/button.tsx: Button for add and delete actions
 * - components/ui/confirmation-dialog.tsx: ConfirmationDialog for delete confirmation
 * - components/ui/table.tsx: Table, TableBody, TableCell, TableHead, TableHeader, TableRow for layout
 * - components/admin/add-pricing-dialog.tsx: AddPricingDialog for pricing creation form
 * - types/admin.ts: PricingConfigCreateRequest, PricingConfigItem types
 *
 * Called by / Used by:
 * - components/admin/admin-config-page.tsx: Pricing tab content
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus, Trash2 } from "lucide-react";

import { createPricing, deletePricing, fetchPricing } from "@/lib/api/admin";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import { Button } from "@/components/ui/button";
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import type {
	PricingConfigCreateRequest,
	PricingConfigItem,
} from "@/types/admin";

import { AddPricingDialog } from "./add-pricing-dialog";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Pricing config management — list, add, delete with live cost preview. */
export function PricingTab() {
	const queryClient = useQueryClient();
	const [addOpen, setAddOpen] = useState(false);
	const [deleteTarget, setDeleteTarget] = useState<PricingConfigItem | null>(
		null,
	);

	// -----------------------------------------------------------------------
	// Queries
	// -----------------------------------------------------------------------

	const { data, isLoading, error, refetch } = useQuery({
		queryKey: queryKeys.adminPricing,
		queryFn: () => fetchPricing(),
	});

	// -----------------------------------------------------------------------
	// Mutations
	// -----------------------------------------------------------------------

	const createMut = useMutation({
		mutationFn: (body: PricingConfigCreateRequest) => createPricing(body),
		onSuccess: () => {
			void queryClient.invalidateQueries({
				queryKey: queryKeys.adminPricing,
			});
			showToast.success("Pricing created");
			setAddOpen(false);
		},
		onError: () => {
			showToast.error("Failed to create pricing");
		},
	});

	const deleteMut = useMutation({
		mutationFn: (id: string) => deletePricing(id),
		onSuccess: () => {
			void queryClient.invalidateQueries({
				queryKey: queryKeys.adminPricing,
			});
			showToast.success("Pricing deleted");
			setDeleteTarget(null);
		},
		onError: () => {
			showToast.error("Failed to delete pricing");
		},
	});

	// -----------------------------------------------------------------------
	// Loading / Error
	// -----------------------------------------------------------------------

	if (isLoading) {
		return (
			<div data-testid="pricing-loading" className="flex justify-center py-12">
				<Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
			</div>
		);
	}

	if (error) {
		return (
			<div className="py-8 text-center">
				<p className="text-destructive mb-2">Failed to load pricing.</p>
				<Button variant="outline" size="sm" onClick={() => void refetch()}>
					Retry
				</Button>
			</div>
		);
	}

	const items = data?.data ?? [];
	const today = new Date().toISOString().slice(0, 10);

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	return (
		<div data-testid="pricing-tab" className="space-y-4 pt-4">
			<div className="flex items-center justify-between">
				<p className="text-muted-foreground text-sm">
					{items.length} pricing entr{items.length === 1 ? "y" : "ies"}
				</p>
				<Button variant="outline" size="sm" onClick={() => setAddOpen(true)}>
					<Plus className="mr-1 h-4 w-4" />
					Add Pricing
				</Button>
			</div>

			{items.length === 0 ? (
				<p className="text-muted-foreground py-8 text-center text-sm">
					No pricing entries yet.
				</p>
			) : (
				<Table>
					<TableHeader>
						<TableRow>
							<TableHead>Provider</TableHead>
							<TableHead>Model</TableHead>
							<TableHead>Input/1K</TableHead>
							<TableHead>Output/1K</TableHead>
							<TableHead>Margin</TableHead>
							<TableHead>Effective Date</TableHead>
							<TableHead>Status</TableHead>
							<TableHead className="text-right">Actions</TableHead>
						</TableRow>
					</TableHeader>
					<TableBody>
						{items.map((item) => (
							<TableRow key={item.id}>
								<TableCell>{item.provider}</TableCell>
								<TableCell className="font-mono text-xs">
									{item.model}
								</TableCell>
								<TableCell className="font-mono text-xs">
									{item.input_cost_per_1k}
								</TableCell>
								<TableCell className="font-mono text-xs">
									{item.output_cost_per_1k}
								</TableCell>
								<TableCell>{item.margin_multiplier}</TableCell>
								<TableCell>{item.effective_date}</TableCell>
								<TableCell>
									{item.is_current ? (
										<span className="bg-success/20 text-success rounded px-2 py-0.5 text-xs font-medium">
											Current
										</span>
									) : (
										<span className="text-muted-foreground text-xs">
											{item.effective_date > today ? "Future" : "Past"}
										</span>
									)}
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

			{/* Add Pricing Dialog */}
			<AddPricingDialog
				open={addOpen}
				onOpenChange={setAddOpen}
				isPending={createMut.isPending}
				onSubmit={(data) => createMut.mutate(data)}
			/>

			{/* Delete Confirmation */}
			<ConfirmationDialog
				open={deleteTarget !== null}
				onOpenChange={(open) => {
					if (!open) setDeleteTarget(null);
				}}
				title="Delete Pricing?"
				description={`Are you sure you want to delete pricing for ${deleteTarget?.provider}/${deleteTarget?.model} (${deleteTarget?.effective_date})?`}
				confirmLabel="Confirm"
				variant="destructive"
				loading={deleteMut.isPending}
				onConfirm={() => {
					if (deleteTarget) deleteMut.mutate(deleteTarget.id);
				}}
			/>
		</div>
	);
}
