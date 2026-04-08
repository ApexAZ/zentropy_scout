"use client";

/**
 * @fileoverview Search criteria step for onboarding wizard (Step 10).
 *
 * Layer: component
 * Feature: persona
 *
 * REQ-034 §9.1: Displays the AI-generated SearchProfile with
 * fit and stretch buckets as editable tag lists. Auto-triggers
 * generation if no profile exists. "Looks Good" button approves
 * and sets approved_at.
 *
 * Coordinates with:
 * - components/onboarding/steps/search-criteria-bucket-card.tsx: BucketCard, updateBucket
 * - lib/api/search-profiles.ts: getSearchProfile, generateSearchProfile, updateSearchProfile
 * - lib/api-client.ts: ApiError for 404 detection
 * - lib/onboarding-provider.tsx: useOnboarding for wizard navigation and personaId
 * - types/search-profile.ts: SearchBucket type for bucket state
 * - components/ui/button.tsx: Button for navigation and approval
 *
 * Called by / Used by:
 * - app/onboarding/page.tsx: onboarding step 10 component
 */

import { ArrowLeft, Loader2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api-client";
import {
	generateSearchProfile,
	getSearchProfile,
	updateSearchProfile,
} from "@/lib/api/search-profiles";
import { useOnboarding } from "@/lib/onboarding-provider";
import type { SearchBucket } from "@/types/search-profile";

import { BucketCard, updateBucket } from "./search-criteria-bucket-card";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Onboarding Step 10: Your Job Search Criteria.
 *
 * Fetches the AI-generated SearchProfile on mount. If none exists,
 * auto-triggers generation. Displays fit and stretch buckets as
 * editable tag lists. "Looks Good" button approves the profile.
 */
export function SearchCriteriaStep() {
	const { personaId, next, back } = useOnboarding();

	const [isLoading, setIsLoading] = useState(true);
	const [isGenerating, setIsGenerating] = useState(false);
	const [isApproving, setIsApproving] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [approveError, setApproveError] = useState<string | null>(null);
	const [fitSearches, setFitSearches] = useState<SearchBucket[]>([]);
	const [stretchSearches, setStretchSearches] = useState<SearchBucket[]>([]);

	// -----------------------------------------------------------------------
	// Fetch profile on mount (auto-generate if 404)
	// -----------------------------------------------------------------------

	useEffect(() => {
		if (!personaId) return;

		let cancelled = false;

		async function loadProfile() {
			try {
				const res = await getSearchProfile(personaId!);
				if (cancelled) return;
				setFitSearches(res.data.fit_searches);
				setStretchSearches(res.data.stretch_searches);
				setIsLoading(false);
			} catch (err) {
				if (cancelled) return;

				if (err instanceof ApiError && err.status === 404) {
					setIsGenerating(true);
					setIsLoading(false);
					try {
						const res = await generateSearchProfile(personaId!);
						if (cancelled) return;
						setFitSearches(res.data.fit_searches);
						setStretchSearches(res.data.stretch_searches);
						setIsGenerating(false);
					} catch {
						if (cancelled) return;
						setError("Failed to generate search criteria. Please try again.");
						setIsGenerating(false);
					}
				} else {
					setError("Failed to load search criteria. Please try again.");
					setIsLoading(false);
				}
			}
		}

		void loadProfile();

		return () => {
			cancelled = true;
		};
	}, [personaId]);

	// -----------------------------------------------------------------------
	// Tag editing callbacks (generic — works for both fit and stretch)
	// -----------------------------------------------------------------------

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

	// -----------------------------------------------------------------------
	// Approve handler
	// -----------------------------------------------------------------------

	const handleApprove = useCallback(async () => {
		if (!personaId) return;
		setApproveError(null);
		setIsApproving(true);

		try {
			await updateSearchProfile(personaId, {
				fit_searches: fitSearches,
				stretch_searches: stretchSearches,
				approved_at: new Date().toISOString(),
			});
			next();
		} catch {
			setApproveError("Failed to save. Please try again.");
			setIsApproving(false);
		}
	}, [personaId, fitSearches, stretchSearches, next]);

	// -----------------------------------------------------------------------
	// Render: loading / generating
	// -----------------------------------------------------------------------

	if (isLoading || isGenerating) {
		return (
			<div
				className="flex flex-1 flex-col items-center justify-center"
				data-testid="loading-search-criteria"
			>
				<Loader2 className="text-primary h-8 w-8 animate-spin" />
				<p className="text-muted-foreground mt-3">
					{isGenerating
						? "Generating your search criteria..."
						: "Loading your search criteria..."}
				</p>
			</div>
		);
	}

	// -----------------------------------------------------------------------
	// Render: error
	// -----------------------------------------------------------------------

	if (error) {
		return (
			<div className="flex flex-1 flex-col items-center justify-center gap-4">
				<p className="text-destructive text-sm">{error}</p>
				<div className="flex gap-2">
					<Button variant="ghost" onClick={back} data-testid="back-button">
						<ArrowLeft className="mr-2 h-4 w-4" />
						Back
					</Button>
				</div>
			</div>
		);
	}

	// -----------------------------------------------------------------------
	// Render: profile
	// -----------------------------------------------------------------------

	return (
		<div className="flex flex-1 flex-col gap-6">
			<div className="text-center">
				<h2 className="text-lg font-semibold">Your Job Search Criteria</h2>
				<p className="text-muted-foreground mt-1">
					AI has analyzed your profile and created search criteria. Review and
					edit the keywords and titles below.
				</p>
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
						<h3 className="text-base font-semibold">{title}</h3>
						<p className="text-muted-foreground text-sm">{desc}</p>
						{buckets.map((bucket, i) => (
							<BucketCard
								key={bucket.label}
								bucket={bucket}
								testId={`${prefix}-bucket-${i}`}
								onKeywordAdd={(tag) => handleAddTag(setter, i, "keywords", tag)}
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

			{/* Approval error */}
			{approveError && (
				<p className="text-destructive text-center text-sm">{approveError}</p>
			)}

			{/* Navigation */}
			<div className="flex items-center justify-between pt-4">
				<Button
					type="button"
					variant="ghost"
					onClick={back}
					data-testid="back-button"
				>
					<ArrowLeft className="mr-2 h-4 w-4" />
					Back
				</Button>
				<Button
					type="button"
					disabled={isApproving}
					onClick={handleApprove}
					data-testid="approve-button"
				>
					{isApproving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
					{isApproving ? "Saving..." : "Looks Good"}
				</Button>
			</div>
		</div>
	);
}
