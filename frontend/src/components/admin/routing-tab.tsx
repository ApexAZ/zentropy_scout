"use client";

/**
 * Task routing management tab — fixed editable table.
 *
 * REQ-028 §6.1: Fixed 10-row table (one per TaskType), inline provider/model
 * dropdowns, no add/delete. Provider changes use delete+create; model changes
 * use PATCH.
 */

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import {
	createRouting,
	deleteRouting,
	fetchModels,
	fetchRouting,
	updateRouting,
} from "@/lib/api/admin";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import { Button } from "@/components/ui/button";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import type {
	ModelRegistryItem,
	TaskRoutingCreateRequest,
	TaskRoutingItem,
	TaskRoutingUpdateRequest,
} from "@/types/admin";

import { PROVIDERS, TASK_TYPES } from "./constants";

// ---------------------------------------------------------------------------
// Mutation action types
// ---------------------------------------------------------------------------

type SaveAction =
	| { type: "create"; body: TaskRoutingCreateRequest }
	| { type: "update"; id: string; body: TaskRoutingUpdateRequest }
	| { type: "replace"; deleteId: string; body: TaskRoutingCreateRequest };

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Task routing management — fixed 10-row editable table. */
export function RoutingTab() {
	const queryClient = useQueryClient();

	/** Pending provider overrides (provider changed but model not yet selected). */
	const [pendingProviders, setPendingProviders] = useState<
		Record<string, string>
	>({});

	// -----------------------------------------------------------------------
	// Queries
	// -----------------------------------------------------------------------

	const routingQuery = useQuery({
		queryKey: queryKeys.adminRouting,
		queryFn: () => fetchRouting(),
	});

	const modelsQuery = useQuery({
		queryKey: queryKeys.adminModels,
		queryFn: () => fetchModels({ model_type: "llm", is_active: true }),
	});

	// -----------------------------------------------------------------------
	// Derived data
	// -----------------------------------------------------------------------

	const routingMap = useMemo(() => {
		const map = new Map<string, TaskRoutingItem>();
		for (const item of routingQuery.data?.data ?? []) {
			map.set(item.task_type, item);
		}
		return map;
	}, [routingQuery.data]);

	const modelsByProvider = useMemo(() => {
		const map = new Map<string, ModelRegistryItem[]>();
		for (const model of modelsQuery.data?.data ?? []) {
			if (model.model_type === "llm" && model.is_active) {
				const list = map.get(model.provider) ?? [];
				list.push(model);
				map.set(model.provider, list);
			}
		}
		return map;
	}, [modelsQuery.data]);

	// -----------------------------------------------------------------------
	// Mutations
	// -----------------------------------------------------------------------

	const saveMut = useMutation({
		mutationFn: async (action: SaveAction) => {
			switch (action.type) {
				case "create":
					return createRouting(action.body);
				case "update":
					return updateRouting(action.id, action.body);
				case "replace":
					await deleteRouting(action.deleteId);
					return createRouting(action.body);
			}
		},
		onSuccess: () => {
			void queryClient.invalidateQueries({
				queryKey: queryKeys.adminRouting,
			});
			showToast.success("Routing updated");
		},
		onError: () => {
			showToast.error("Failed to update routing");
			void queryClient.invalidateQueries({
				queryKey: queryKeys.adminRouting,
			});
		},
	});

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	function handleProviderChange(taskType: string, newProvider: string) {
		setPendingProviders((prev) => ({ ...prev, [taskType]: newProvider }));
	}

	function handleModelSelect(taskType: string, newModel: string) {
		const existing = routingMap.get(taskType);
		const pendingProvider = pendingProviders[taskType];
		const provider = pendingProvider ?? existing?.provider;

		if (!provider) return;

		// Clear pending state
		setPendingProviders((prev) => {
			const next = { ...prev };
			delete next[taskType];
			return next;
		});

		if (existing && !pendingProvider) {
			// Same provider — PATCH model
			saveMut.mutate({
				type: "update",
				id: existing.id,
				body: { model: newModel },
			});
		} else if (existing && pendingProvider) {
			// Provider changed — delete old + create new
			saveMut.mutate({
				type: "replace",
				deleteId: existing.id,
				body: { provider, task_type: taskType, model: newModel },
			});
		} else {
			// New routing entry
			saveMut.mutate({
				type: "create",
				body: { provider, task_type: taskType, model: newModel },
			});
		}
	}

	// -----------------------------------------------------------------------
	// Loading / Error
	// -----------------------------------------------------------------------

	if (routingQuery.isLoading || modelsQuery.isLoading) {
		return (
			<div data-testid="routing-loading" className="flex justify-center py-12">
				<Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
			</div>
		);
	}

	if (routingQuery.error || modelsQuery.error) {
		return (
			<div className="py-8 text-center">
				<p className="text-destructive mb-2">Failed to load routing.</p>
				<Button
					variant="outline"
					size="sm"
					onClick={() => {
						void routingQuery.refetch();
						void modelsQuery.refetch();
					}}
				>
					Retry
				</Button>
			</div>
		);
	}

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	return (
		<div data-testid="routing-tab" className="space-y-4 pt-4">
			<p className="text-muted-foreground text-sm">
				Configure which provider and model handles each task type.
			</p>

			<Table>
				<TableHeader>
					<TableRow>
						<TableHead>Task Type</TableHead>
						<TableHead>Provider</TableHead>
						<TableHead>Model</TableHead>
					</TableRow>
				</TableHeader>
				<TableBody>
					{TASK_TYPES.map(({ value, label }) => {
						const routing = routingMap.get(value);
						const currentProvider =
							pendingProviders[value] ?? routing?.provider ?? "";
						const currentModel = pendingProviders[value]
							? ""
							: (routing?.model ?? "");
						const availableModels = modelsByProvider.get(currentProvider) ?? [];

						return (
							<TableRow key={value}>
								<TableCell className="font-medium">{label}</TableCell>
								<TableCell>
									<Select
										value={currentProvider}
										onValueChange={(p) => handleProviderChange(value, p)}
									>
										<SelectTrigger
											data-testid={`provider-select-${value}`}
											aria-label={`Provider for ${label}`}
											className="w-[140px]"
										>
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
								</TableCell>
								<TableCell>
									<Select
										value={currentModel}
										onValueChange={(m) => handleModelSelect(value, m)}
										disabled={!currentProvider}
									>
										<SelectTrigger
											data-testid={`model-select-${value}`}
											aria-label={`Model for ${label}`}
											className="w-[260px]"
										>
											<SelectValue placeholder="Select model" />
										</SelectTrigger>
										<SelectContent>
											{availableModels.map((m) => (
												<SelectItem key={m.id} value={m.model}>
													{m.display_name}
												</SelectItem>
											))}
										</SelectContent>
									</Select>
								</TableCell>
							</TableRow>
						);
					})}
				</TableBody>
			</Table>
		</div>
	);
}
