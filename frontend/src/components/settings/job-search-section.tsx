"use client";

/**
 * @fileoverview Job Search settings section with editable search criteria,
 * poll schedule, job sources, refresh, and staleness banner.
 *
 * Layer: component
 * Feature: persona
 *
 * REQ-034 §9.2: Job Search settings tab. Contains editable SearchProfile
 * fit/stretch buckets, polling frequency display, embedded job source
 * toggles, "Refresh Criteria" button, and staleness banner when
 * is_stale=true.
 *
 * Coordinates with:
 * - hooks/use-search-criteria-editing.ts: state management, save, refresh, tag editing
 * - components/onboarding/steps/search-criteria-bucket-card.tsx: BucketCard for bucket display
 * - components/settings/job-sources-section.tsx: JobSourcesSection for source toggles
 * - lib/api/search-profiles.ts: getSearchProfile for initial fetch
 * - lib/api-client.ts: apiGet for persona polling frequency
 * - lib/query-keys.ts: queryKeys for cache management
 * - types/persona.ts: Persona type for polling_frequency
 * - types/api.ts: ApiResponse envelope type
 *
 * Called by / Used by:
 * - components/settings/settings-page.tsx: Job Search card in settings layout
 */

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Loader2, RefreshCw, Save } from "lucide-react";

import { BucketCard } from "@/components/onboarding/steps/search-criteria-bucket-card";
import { Button } from "@/components/ui/button";
import { FailedState } from "@/components/ui/error-states";
import { useSearchCriteriaEditing } from "@/hooks/use-search-criteria-editing";
import { apiGet } from "@/lib/api-client";
import { getSearchProfile } from "@/lib/api/search-profiles";
import { queryKeys } from "@/lib/query-keys";
import type { ApiResponse } from "@/types/api";
import type { Persona } from "@/types/persona";

import { JobSourcesSection } from "./job-sources-section";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface JobSearchSectionProps {
	personaId: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Job Search settings section — editable criteria, poll schedule, sources. */
export function JobSearchSection({
	personaId,
}: Readonly<JobSearchSectionProps>) {
	// Data fetching
	const {
		data: profileData,
		isLoading: profileLoading,
		error: profileError,
		refetch: refetchProfile,
	} = useQuery({
		queryKey: queryKeys.searchProfile(personaId),
		queryFn: () => getSearchProfile(personaId),
	});

	const { data: personaData } = useQuery({
		queryKey: queryKeys.persona(personaId),
		queryFn: () =>
			apiGet<ApiResponse<Persona>>(
				`/personas/${encodeURIComponent(personaId)}`,
			),
	});

	// Editing state + handlers
	const {
		fitSearches,
		setFitSearches,
		stretchSearches,
		setStretchSearches,
		isSaving,
		isRefreshing,
		handleAddTag,
		handleRemoveTag,
		handleSave,
		handleRefresh,
	} = useSearchCriteriaEditing(personaId, profileData);

	// Loading / Error
	if (profileLoading) {
		return (
			<div data-testid="loading-spinner" className="flex justify-center py-12">
				<Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
			</div>
		);
	}

	if (profileError) {
		return <FailedState onRetry={() => refetchProfile()} />;
	}

	const isStale = profileData?.data.is_stale ?? false;
	const pollingFrequency = personaData?.data.polling_frequency ?? "—";

	// Render
	return (
		<div data-testid="job-search-section" className="space-y-6">
			{/* Staleness banner */}
			{isStale && (
				<output
					data-testid="staleness-banner"
					className="border-warning/50 bg-warning/10 flex items-start gap-3 rounded-md border p-3"
				>
					<AlertTriangle className="text-warning mt-0.5 h-4 w-4 shrink-0" />
					<div className="flex-1">
						<p className="text-sm">
							Your persona has changed since your search criteria were last
							generated.
						</p>
						<Button
							variant="link"
							size="sm"
							className="h-auto p-0"
							disabled={isRefreshing}
							onClick={() => void handleRefresh()}
						>
							Refresh criteria
						</Button>
					</div>
				</output>
			)}

			{/* Search Criteria */}
			<div className="space-y-4">
				<div className="flex items-center justify-between">
					<h3 className="text-base font-semibold">Search Criteria</h3>
					<div className="flex gap-2">
						<Button
							size="sm"
							variant="outline"
							disabled={isRefreshing}
							onClick={() => void handleRefresh()}
							data-testid="refresh-criteria-button"
						>
							{isRefreshing ? (
								<Loader2 className="mr-2 h-4 w-4 animate-spin" />
							) : (
								<RefreshCw className="mr-2 h-4 w-4" />
							)}
							{isRefreshing ? "Refreshing..." : "Refresh"}
						</Button>
						<Button
							size="sm"
							disabled={isSaving}
							onClick={() => void handleSave()}
							data-testid="save-criteria-button"
						>
							{isSaving ? (
								<Loader2 className="mr-2 h-4 w-4 animate-spin" />
							) : (
								<Save className="mr-2 h-4 w-4" />
							)}
							{isSaving ? "Saving..." : "Save"}
						</Button>
					</div>
				</div>

				{/* Bucket sections: fit + stretch */}
				{[
					{
						title: "Best Fit",
						desc: "Roles matching your current experience",
						buckets: fitSearches,
						setter: setFitSearches,
						prefix: "fit",
					},
					{
						title: "Growth Opportunities",
						desc: "Stretch roles to grow into",
						buckets: stretchSearches,
						setter: setStretchSearches,
						prefix: "stretch",
					},
				].map(({ title, desc, buckets, setter, prefix }) =>
					buckets.length > 0 ? (
						<div key={prefix} className="space-y-3">
							<h4 className="text-sm font-medium">{title}</h4>
							<p className="text-muted-foreground text-xs">{desc}</p>
							{buckets.map((bucket, i) => (
								<BucketCard
									key={bucket.label}
									bucket={bucket}
									testId={`${prefix}-bucket-${i}`}
									onKeywordAdd={(tag) =>
										handleAddTag(setter, i, "keywords", tag)
									}
									onKeywordRemove={(idx) =>
										handleRemoveTag(setter, i, "keywords", idx)
									}
									onTitleAdd={(tag) => handleAddTag(setter, i, "titles", tag)}
									onTitleRemove={(idx) =>
										handleRemoveTag(setter, i, "titles", idx)
									}
								/>
							))}
						</div>
					) : null,
				)}
			</div>

			{/* Poll Schedule */}
			<div className="space-y-2">
				<h3 className="text-base font-semibold">Poll Schedule</h3>
				<p className="text-muted-foreground text-sm">
					Polling frequency:{" "}
					<span className="text-foreground font-medium">
						{pollingFrequency}
					</span>
				</p>
			</div>

			{/* Job Sources */}
			<div className="space-y-2">
				<h3 className="text-base font-semibold">Job Sources</h3>
				<JobSourcesSection personaId={personaId} />
			</div>
		</div>
	);
}
