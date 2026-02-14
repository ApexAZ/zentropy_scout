"use client";

/**
 * Post-onboarding achievement stories editor (§6.8).
 *
 * REQ-012 §7.2.5: CRUD for achievement story entries with
 * C/A/O display, skill links, and drag-drop reordering.
 * Adapts onboarding StoryStep logic to the post-onboarding pattern.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2, Plus } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { StoryCard } from "@/components/onboarding/steps/story-card";
import { StoryForm } from "@/components/onboarding/steps/story-form";
import type { StoryFormData } from "@/components/onboarding/steps/story-form";
import { Button } from "@/components/ui/button";
import { DeleteReferenceDialog } from "@/components/ui/delete-reference-dialog";
import { ReorderableList } from "@/components/ui/reorderable-list";
import { useDeleteWithReferences } from "@/hooks/use-delete-with-references";
import { toFormValues, toRequestBody } from "@/lib/achievement-stories-helpers";
import { apiGet, apiPatch, apiPost } from "@/lib/api-client";
import { toFriendlyError } from "@/lib/form-errors";
import { queryKeys } from "@/lib/query-keys";
import type { ApiListResponse, ApiResponse } from "@/types/api";
import type { AchievementStory, Persona, Skill } from "@/types/persona";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ViewMode = "list" | "add" | "edit";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Post-onboarding editor for achievement story entries.
 *
 * Receives the current persona as a prop and fetches stories and skills
 * via useQuery. Provides add/edit/delete and drag-drop reordering with
 * skill link resolution on cards.
 */
export function AchievementStoriesEditor({ persona }: { persona: Persona }) {
	const personaId = persona.id;
	const queryClient = useQueryClient();
	const storiesQueryKey = queryKeys.achievementStories(personaId);

	// -----------------------------------------------------------------------
	// Data fetching
	// -----------------------------------------------------------------------

	const { data: storiesData, isLoading: isLoadingStories } = useQuery({
		queryKey: storiesQueryKey,
		queryFn: () =>
			apiGet<ApiListResponse<AchievementStory>>(
				`/personas/${personaId}/achievement-stories`,
			),
	});

	const { data: skillsData, isLoading: isLoadingSkills } = useQuery({
		queryKey: queryKeys.skills(personaId),
		queryFn: () =>
			apiGet<ApiListResponse<Skill>>(`/personas/${personaId}/skills`),
	});

	const [entries, setEntries] = useState<AchievementStory[]>([]);
	const [skills, setSkills] = useState<Skill[]>([]);
	const [viewMode, setViewMode] = useState<ViewMode>("list");
	const [editingEntry, setEditingEntry] = useState<AchievementStory | null>(
		null,
	);
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [submitError, setSubmitError] = useState<string | null>(null);
	const deleteHandler = useDeleteWithReferences<AchievementStory>({
		personaId,
		itemType: "achievement-story",
		collection: "achievement-stories",
		getItemLabel: (s) => s.title,
		onDeleted: (id) => setEntries((prev) => prev.filter((e) => e.id !== id)),
		queryClient,
		queryKey: storiesQueryKey,
	});

	// Sync query data to local state for optimistic updates
	useEffect(() => {
		if (storiesData?.data) {
			setEntries(storiesData.data);
		}
	}, [storiesData]);

	useEffect(() => {
		if (skillsData?.data) {
			setSkills(skillsData.data);
		}
	}, [skillsData]);

	const isLoading = isLoadingStories || isLoadingSkills;

	// -----------------------------------------------------------------------
	// Add handler
	// -----------------------------------------------------------------------

	const handleAdd = useCallback(() => {
		setEditingEntry(null);
		setSubmitError(null);
		setViewMode("add");
	}, []);

	const handleSaveNew = useCallback(
		async (formData: StoryFormData) => {
			setSubmitError(null);
			setIsSubmitting(true);

			try {
				const res = await apiPost<ApiResponse<AchievementStory>>(
					`/personas/${personaId}/achievement-stories`,
					{
						...toRequestBody(formData),
						display_order: entries.length,
					},
				);

				setEntries((prev) => [...prev, res.data]);
				setViewMode("list");
				await queryClient.invalidateQueries({
					queryKey: storiesQueryKey,
				});
			} catch (err) {
				setSubmitError(toFriendlyError(err));
			} finally {
				setIsSubmitting(false);
			}
		},
		[personaId, entries.length, queryClient, storiesQueryKey],
	);

	// -----------------------------------------------------------------------
	// Edit handler
	// -----------------------------------------------------------------------

	const handleEdit = useCallback((entry: AchievementStory) => {
		setEditingEntry(entry);
		setSubmitError(null);
		setViewMode("edit");
	}, []);

	const handleSaveEdit = useCallback(
		async (formData: StoryFormData) => {
			if (!editingEntry) return;

			setSubmitError(null);
			setIsSubmitting(true);

			try {
				const res = await apiPatch<ApiResponse<AchievementStory>>(
					`/personas/${personaId}/achievement-stories/${editingEntry.id}`,
					toRequestBody(formData),
				);

				setEntries((prev) =>
					prev.map((e) => (e.id === editingEntry.id ? res.data : e)),
				);
				setViewMode("list");
				await queryClient.invalidateQueries({
					queryKey: storiesQueryKey,
				});
			} catch (err) {
				setSubmitError(toFriendlyError(err));
			} finally {
				setIsSubmitting(false);
			}
		},
		[personaId, editingEntry, queryClient, storiesQueryKey],
	);

	// -----------------------------------------------------------------------
	// Cancel form
	// -----------------------------------------------------------------------

	const handleCancel = useCallback(() => {
		setEditingEntry(null);
		setSubmitError(null);
		setViewMode("list");
	}, []);

	// -----------------------------------------------------------------------
	// Reorder handler
	// -----------------------------------------------------------------------

	const handleReorder = useCallback(
		(reordered: AchievementStory[]) => {
			const previousEntries = [...entries];
			setEntries(reordered);

			const patches = reordered
				.map((entry, newOrder) => ({ entry, newOrder }))
				.filter(({ entry, newOrder }) => entry.display_order !== newOrder)
				.map(({ entry, newOrder }) =>
					apiPatch(`/personas/${personaId}/achievement-stories/${entry.id}`, {
						display_order: newOrder,
					}),
				);

			if (patches.length > 0) {
				void Promise.all(patches)
					.then(() =>
						queryClient.invalidateQueries({
							queryKey: storiesQueryKey,
						}),
					)
					.catch(() => {
						setEntries(previousEntries);
					});
			}
		},
		[personaId, entries, queryClient, storiesQueryKey],
	);

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	if (isLoading) {
		return (
			<div
				className="flex flex-1 flex-col items-center justify-center"
				data-testid="loading-stories-editor"
			>
				<Loader2 className="text-primary h-8 w-8 animate-spin" />
				<p className="text-muted-foreground mt-3">
					Loading your achievement stories...
				</p>
			</div>
		);
	}

	return (
		<div className="flex flex-1 flex-col gap-6">
			<div>
				<h2 className="text-lg font-semibold">Achievement Stories</h2>
				<p className="text-muted-foreground mt-1">
					Manage your achievement stories.
				</p>
			</div>

			{/* Form view (add or edit) */}
			{viewMode !== "list" && (
				<StoryForm
					initialValues={
						viewMode === "edit" && editingEntry
							? toFormValues(editingEntry)
							: undefined
					}
					onSave={viewMode === "add" ? handleSaveNew : handleSaveEdit}
					onCancel={handleCancel}
					isSubmitting={isSubmitting}
					submitError={submitError}
					skills={skills}
				/>
			)}

			{/* List view */}
			{viewMode === "list" && (
				<>
					{entries.length === 0 ? (
						<div className="text-muted-foreground py-8 text-center">
							<p>No stories yet.</p>
						</div>
					) : (
						<ReorderableList
							items={entries}
							onReorder={handleReorder}
							label="Achievement story entries"
							renderItem={(entry, dragHandle) => (
								<StoryCard
									entry={entry}
									skills={skills}
									onEdit={handleEdit}
									onDelete={deleteHandler.requestDelete}
									dragHandle={dragHandle}
								/>
							)}
						/>
					)}

					<Button
						type="button"
						variant="outline"
						onClick={handleAdd}
						className="self-center"
					>
						<Plus className="mr-2 h-4 w-4" />
						Add story
					</Button>
				</>
			)}

			{/* Navigation */}
			{viewMode === "list" && (
				<div className="flex items-center justify-between pt-4">
					<Link
						href="/persona"
						className="text-muted-foreground hover:text-foreground inline-flex items-center text-sm"
					>
						<ArrowLeft className="mr-2 h-4 w-4" />
						Back to Profile
					</Link>
				</div>
			)}

			{/* Delete reference dialog */}
			<DeleteReferenceDialog
				open={deleteHandler.flowState !== "idle"}
				onCancel={deleteHandler.cancel}
				flowState={deleteHandler.flowState}
				deleteError={deleteHandler.deleteError}
				itemLabel={deleteHandler.deleteTarget?.title ?? ""}
				references={deleteHandler.references}
				hasImmutableReferences={deleteHandler.hasImmutableReferences}
				reviewSelections={deleteHandler.reviewSelections}
				onRemoveAllAndDelete={deleteHandler.removeAllAndDelete}
				onExpandReviewEach={deleteHandler.expandReviewEach}
				onToggleReviewSelection={deleteHandler.toggleReviewSelection}
				onConfirmReviewAndDelete={deleteHandler.confirmReviewAndDelete}
			/>
		</div>
	);
}
