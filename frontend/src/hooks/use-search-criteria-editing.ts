/**
 * @fileoverview Hook for SearchProfile bucket editing with save/refresh.
 *
 * Layer: hook
 * Feature: persona
 *
 * REQ-034 §9.1, §9.2: Encapsulates local state management, tag editing
 * callbacks, save, and refresh logic for editable SearchProfile
 * fit/stretch buckets.
 *
 * Coordinates with:
 * - components/onboarding/steps/search-criteria-bucket-card.tsx: updateBucket helper
 * - lib/api/search-profiles.ts: generateSearchProfile, updateSearchProfile
 * - lib/query-keys.ts: queryKeys.searchProfile for cache invalidation
 * - lib/toast.ts: showToast for user feedback
 * - types/search-profile.ts: SearchBucket, SearchProfile types
 * - types/api.ts: ApiResponse envelope type
 *
 * Called by / Used by:
 * - components/settings/job-search-section.tsx: Job Search settings card
 */

import { useCallback, useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { updateBucket } from "@/components/onboarding/steps/search-criteria-bucket-card";
import {
	generateSearchProfile,
	updateSearchProfile,
} from "@/lib/api/search-profiles";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import type { ApiResponse } from "@/types/api";
import type { SearchBucket, SearchProfile } from "@/types/search-profile";

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/** Manages editable SearchProfile state with save and refresh actions. */
export function useSearchCriteriaEditing(
	personaId: string,
	profileData: ApiResponse<SearchProfile> | undefined,
) {
	const queryClient = useQueryClient();

	const [fitSearches, setFitSearches] = useState<SearchBucket[]>([]);
	const [stretchSearches, setStretchSearches] = useState<SearchBucket[]>([]);
	const [isSaving, setIsSaving] = useState(false);
	const [isRefreshing, setIsRefreshing] = useState(false);

	// Sync query data → local state
	useEffect(() => {
		if (profileData) {
			setFitSearches(profileData.data.fit_searches);
			setStretchSearches(profileData.data.stretch_searches);
		}
	}, [profileData]);

	// Tag editing callbacks (generic — works for both fit and stretch)
	const handleAddTag = useCallback(
		(
			setter: React.Dispatch<React.SetStateAction<SearchBucket[]>>,
			bucketIndex: number,
			field: "keywords" | "titles",
			tag: string,
		) => {
			setter((prev) =>
				updateBucket(prev, bucketIndex, field, [
					...prev[bucketIndex][field],
					tag,
				]),
			);
		},
		[],
	);

	const handleRemoveTag = useCallback(
		(
			setter: React.Dispatch<React.SetStateAction<SearchBucket[]>>,
			bucketIndex: number,
			field: "keywords" | "titles",
			tagIndex: number,
		) => {
			setter((prev) =>
				updateBucket(
					prev,
					bucketIndex,
					field,
					prev[bucketIndex][field].filter((_, i) => i !== tagIndex),
				),
			);
		},
		[],
	);

	// Save current edits
	const handleSave = useCallback(async () => {
		setIsSaving(true);
		try {
			await updateSearchProfile(personaId, {
				fit_searches: fitSearches,
				stretch_searches: stretchSearches,
			});
			await queryClient.invalidateQueries({
				queryKey: queryKeys.searchProfile(personaId),
			});
			showToast.success("Search criteria saved.");
		} catch {
			showToast.error("Failed to save search criteria.");
		} finally {
			setIsSaving(false);
		}
	}, [personaId, fitSearches, stretchSearches, queryClient]);

	// Regenerate profile via AI
	const handleRefresh = useCallback(async () => {
		setIsRefreshing(true);
		try {
			const res = await generateSearchProfile(personaId);
			setFitSearches(res.data.fit_searches);
			setStretchSearches(res.data.stretch_searches);
			await queryClient.invalidateQueries({
				queryKey: queryKeys.searchProfile(personaId),
			});
			showToast.success("Search criteria regenerated.");
		} catch {
			showToast.error("Failed to regenerate search criteria.");
		} finally {
			setIsRefreshing(false);
		}
	}, [personaId, queryClient]);

	return {
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
	};
}
