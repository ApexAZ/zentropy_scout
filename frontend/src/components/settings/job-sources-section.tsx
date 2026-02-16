"use client";

/**
 * Job source preferences section for the settings page.
 *
 * REQ-012 §12.2: Toggle switches to enable/disable job sources,
 * drag-and-drop reorder, source description tooltips, and
 * grayed-out styling for system-inactive sources.
 */

import { useCallback, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import { apiGet, apiPatch } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import { cn } from "@/lib/utils";
import { Switch } from "@/components/ui/switch";
import { EmptyState, FailedState } from "@/components/ui/error-states";
import {
	ReorderableList,
	type ReorderableItem,
} from "@/components/ui/reorderable-list";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import type { ApiListResponse } from "@/types/api";
import type { JobSource, UserSourcePreference } from "@/types/source";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PREFERENCES_PATH = "/user-source-preferences";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SourceItem extends ReorderableItem {
	sourceId: string;
	sourceName: string;
	description: string;
	isActive: boolean;
	isEnabled: boolean;
	displayOrder: number;
	preferenceId: string | null;
}

export interface JobSourcesSectionProps {
	personaId: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Job source preferences with toggle, reorder, and tooltip. */
export function JobSourcesSection({
	personaId,
}: Readonly<JobSourcesSectionProps>) {
	const queryClient = useQueryClient();

	// -----------------------------------------------------------------------
	// Data fetching
	// -----------------------------------------------------------------------

	const {
		data: sourcesData,
		isLoading: sourcesLoading,
		error: sourcesError,
		refetch: refetchSources,
	} = useQuery({
		queryKey: queryKeys.jobSources,
		queryFn: () => apiGet<ApiListResponse<JobSource>>("/job-sources"),
	});

	const {
		data: preferencesData,
		isLoading: preferencesLoading,
		error: preferencesError,
	} = useQuery({
		queryKey: queryKeys.sourcePreferences(personaId),
		queryFn: () =>
			apiGet<ApiListResponse<UserSourcePreference>>(PREFERENCES_PATH),
	});

	// -----------------------------------------------------------------------
	// Merged view model
	// -----------------------------------------------------------------------

	const mergedItems: SourceItem[] = useMemo(() => {
		const sources = sourcesData?.data ?? [];
		const preferences = preferencesData?.data ?? [];

		const prefBySourceId = new Map<string, UserSourcePreference>();
		for (const pref of preferences) {
			prefBySourceId.set(pref.source_id, pref);
		}

		return sources
			.map((source): SourceItem => {
				const pref = prefBySourceId.get(source.id);
				return {
					id: pref?.id ?? source.id,
					sourceId: source.id,
					sourceName: source.source_name,
					description: source.description,
					isActive: source.is_active,
					isEnabled: pref ? pref.is_enabled : true,
					displayOrder: pref?.display_order ?? source.display_order,
					preferenceId: pref?.id ?? null,
				};
			})
			.sort((a, b) => a.displayOrder - b.displayOrder);
	}, [sourcesData, preferencesData]);

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	const handleToggle = useCallback(
		async (item: SourceItem) => {
			if (!item.preferenceId) return;
			try {
				await apiPatch(`${PREFERENCES_PATH}/${item.preferenceId}`, {
					is_enabled: !item.isEnabled,
				});
				await queryClient.invalidateQueries({
					queryKey: queryKeys.sourcePreferences(personaId),
				});
				showToast.success(
					`${item.sourceName} ${item.isEnabled ? "disabled" : "enabled"}.`,
				);
			} catch {
				showToast.error("Failed to update source preference.");
			}
		},
		[personaId, queryClient],
	);

	const handleReorder = useCallback(
		async (reorderedItems: SourceItem[]) => {
			const updates = reorderedItems
				.map((item, index) => ({
					preferenceId: item.preferenceId,
					displayOrder: index,
				}))
				.filter((u) => u.preferenceId !== null);

			try {
				await Promise.all(
					updates.map((u) =>
						apiPatch(`${PREFERENCES_PATH}/${u.preferenceId}`, {
							display_order: u.displayOrder,
						}),
					),
				);
				await queryClient.invalidateQueries({
					queryKey: queryKeys.sourcePreferences(personaId),
				});
			} catch {
				showToast.error("Failed to update source order.");
			}
		},
		[personaId, queryClient],
	);

	// -----------------------------------------------------------------------
	// Loading / Error / Empty states
	// -----------------------------------------------------------------------

	const isLoading = sourcesLoading || preferencesLoading;
	const error = sourcesError ?? preferencesError;

	if (isLoading) {
		return (
			<div data-testid="loading-spinner" className="flex justify-center py-12">
				<Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
			</div>
		);
	}

	if (error) {
		return <FailedState onRetry={() => refetchSources()} />;
	}

	if (mergedItems.length === 0) {
		return (
			<EmptyState
				title="No job sources"
				description="No job sources have been configured yet."
			/>
		);
	}

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	return (
		<div data-testid="job-sources-section">
			<TooltipProvider>
				<ReorderableList
					items={mergedItems}
					onReorder={(items) => void handleReorder(items)}
					renderItem={(item, dragHandle) => (
						<div
							data-testid={`source-item-${item.sourceId}`}
							className={cn(
								"flex items-center gap-3 rounded-md border p-3",
								!item.isActive && "opacity-50",
							)}
						>
							{dragHandle}
							<Switch
								checked={item.isEnabled}
								disabled={!item.isActive}
								onCheckedChange={() => void handleToggle(item)}
								aria-label={`Toggle ${item.sourceName}`}
							/>
							<Tooltip>
								<TooltipTrigger asChild>
									<span className="text-sm font-medium">{item.sourceName}</span>
								</TooltipTrigger>
								<TooltipContent>{item.description}</TooltipContent>
							</Tooltip>
						</div>
					)}
					label="job sources"
				/>
			</TooltipProvider>
		</div>
	);
}
