"use client";

/**
 * Post-onboarding skills editor (§6.7).
 *
 * REQ-012 §7.2.4: CRUD for skill entries with Hard/Soft tabs and
 * per-type drag-drop reordering. Adapts onboarding SkillsStep logic
 * to the post-onboarding pattern.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2, Plus } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { SkillCard } from "@/components/onboarding/steps/skills-card";
import { SkillForm } from "@/components/onboarding/steps/skills-form";
import type { SkillFormData } from "@/components/onboarding/steps/skills-form";
import { Button } from "@/components/ui/button";
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog";
import { ReorderableList } from "@/components/ui/reorderable-list";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { apiDelete, apiGet, apiPatch, apiPost } from "@/lib/api-client";
import { toFriendlyError } from "@/lib/form-errors";
import { queryKeys } from "@/lib/query-keys";
import { toFormValues, toRequestBody } from "@/lib/skills-helpers";
import type { ApiListResponse, ApiResponse } from "@/types/api";
import type { Persona, Skill, SkillType } from "@/types/persona";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ViewMode = "list" | "add" | "edit";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Post-onboarding editor for skill entries.
 *
 * Receives the current persona as a prop and fetches skills via
 * useQuery. Provides add/edit/delete and per-type drag-drop reordering
 * with Hard/Soft skill tabs.
 */
export function SkillsEditor({ persona }: { persona: Persona }) {
	const personaId = persona.id;
	const queryClient = useQueryClient();
	const skillsQueryKey = queryKeys.skills(personaId);

	// -----------------------------------------------------------------------
	// Data fetching
	// -----------------------------------------------------------------------

	const { data, isLoading } = useQuery({
		queryKey: skillsQueryKey,
		queryFn: () =>
			apiGet<ApiListResponse<Skill>>(`/personas/${personaId}/skills`),
	});

	const [entries, setEntries] = useState<Skill[]>([]);
	const [activeTab, setActiveTab] = useState<SkillType>("Hard");
	const [viewMode, setViewMode] = useState<ViewMode>("list");
	const [editingEntry, setEditingEntry] = useState<Skill | null>(null);
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [submitError, setSubmitError] = useState<string | null>(null);
	const [deleteTarget, setDeleteTarget] = useState<Skill | null>(null);
	const [isDeleting, setIsDeleting] = useState(false);
	const [deleteError, setDeleteError] = useState<string | null>(null);

	// Sync query data to local state for optimistic updates
	useEffect(() => {
		if (data?.data) {
			setEntries(data.data);
		}
	}, [data]);

	// Filter entries by active tab
	const hardSkills = useMemo(
		() => entries.filter((e) => e.skill_type === "Hard"),
		[entries],
	);
	const softSkills = useMemo(
		() => entries.filter((e) => e.skill_type === "Soft"),
		[entries],
	);
	// -----------------------------------------------------------------------
	// Add handler
	// -----------------------------------------------------------------------

	const handleAdd = useCallback(() => {
		setEditingEntry(null);
		setSubmitError(null);
		setViewMode("add");
	}, []);

	const handleSaveNew = useCallback(
		async (formData: SkillFormData) => {
			setSubmitError(null);
			setIsSubmitting(true);

			try {
				const body = toRequestBody(formData);
				const sameTypeCount = entries.filter(
					(e) => e.skill_type === body.skill_type,
				).length;

				const res = await apiPost<ApiResponse<Skill>>(
					`/personas/${personaId}/skills`,
					{
						...body,
						display_order: sameTypeCount,
					},
				);

				setEntries((prev) => [...prev, res.data]);
				setActiveTab(res.data.skill_type);
				setViewMode("list");
				await queryClient.invalidateQueries({
					queryKey: skillsQueryKey,
				});
			} catch (err) {
				setSubmitError(toFriendlyError(err));
			} finally {
				setIsSubmitting(false);
			}
		},
		[personaId, entries, queryClient, skillsQueryKey],
	);

	// -----------------------------------------------------------------------
	// Edit handler
	// -----------------------------------------------------------------------

	const handleEdit = useCallback((entry: Skill) => {
		setEditingEntry(entry);
		setSubmitError(null);
		setViewMode("edit");
	}, []);

	const handleSaveEdit = useCallback(
		async (formData: SkillFormData) => {
			if (!editingEntry) return;

			setSubmitError(null);
			setIsSubmitting(true);

			try {
				const res = await apiPatch<ApiResponse<Skill>>(
					`/personas/${personaId}/skills/${editingEntry.id}`,
					toRequestBody(formData),
				);

				setEntries((prev) =>
					prev.map((e) => (e.id === editingEntry.id ? res.data : e)),
				);
				setViewMode("list");
				await queryClient.invalidateQueries({
					queryKey: skillsQueryKey,
				});
			} catch (err) {
				setSubmitError(toFriendlyError(err));
			} finally {
				setIsSubmitting(false);
			}
		},
		[personaId, editingEntry, queryClient, skillsQueryKey],
	);

	// -----------------------------------------------------------------------
	// Delete handler
	// -----------------------------------------------------------------------

	const handleDeleteRequest = useCallback((entry: Skill) => {
		setDeleteError(null);
		setDeleteTarget(entry);
	}, []);

	const handleDeleteConfirm = useCallback(async () => {
		if (!deleteTarget) return;

		setIsDeleting(true);

		try {
			await apiDelete(`/personas/${personaId}/skills/${deleteTarget.id}`);
			setEntries((prev) => prev.filter((e) => e.id !== deleteTarget.id));
			setDeleteTarget(null);
			await queryClient.invalidateQueries({
				queryKey: skillsQueryKey,
			});
		} catch (err) {
			setDeleteError(toFriendlyError(err));
		} finally {
			setIsDeleting(false);
		}
	}, [personaId, deleteTarget, queryClient, skillsQueryKey]);

	const handleDeleteCancel = useCallback(() => {
		setDeleteTarget(null);
	}, []);

	// -----------------------------------------------------------------------
	// Cancel form
	// -----------------------------------------------------------------------

	const handleCancel = useCallback(() => {
		setEditingEntry(null);
		setSubmitError(null);
		setViewMode("list");
	}, []);

	// -----------------------------------------------------------------------
	// Reorder handler (per-type)
	// -----------------------------------------------------------------------

	const handleReorder = useCallback(
		(reordered: Skill[]) => {
			// Merge reordered subset back into full entries list
			const reorderedIds = new Set(reordered.map((e) => e.id));
			const otherEntries = entries.filter((e) => !reorderedIds.has(e.id));
			const previousEntries = [...entries];

			setEntries([...otherEntries, ...reordered]);

			const patches = reordered
				.map((entry, newOrder) => ({ entry, newOrder }))
				.filter(({ entry, newOrder }) => entry.display_order !== newOrder)
				.map(({ entry, newOrder }) =>
					apiPatch(`/personas/${personaId}/skills/${entry.id}`, {
						display_order: newOrder,
					}),
				);

			if (patches.length > 0) {
				void Promise.all(patches)
					.then(() =>
						queryClient.invalidateQueries({
							queryKey: skillsQueryKey,
						}),
					)
					.catch(() => {
						setEntries(previousEntries);
					});
			}
		},
		[personaId, entries, queryClient, skillsQueryKey],
	);

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	if (isLoading) {
		return (
			<div
				className="flex flex-1 flex-col items-center justify-center"
				data-testid="loading-skills-editor"
			>
				<Loader2 className="text-primary h-8 w-8 animate-spin" />
				<p className="text-muted-foreground mt-3">Loading your skills...</p>
			</div>
		);
	}

	return (
		<div className="flex flex-1 flex-col gap-6">
			<div>
				<h2 className="text-lg font-semibold">Skills</h2>
				<p className="text-muted-foreground mt-1">Manage your skills.</p>
			</div>

			{/* Form view (add or edit) */}
			{viewMode !== "list" && (
				<SkillForm
					initialValues={
						viewMode === "edit" && editingEntry
							? toFormValues(editingEntry)
							: undefined
					}
					onSave={viewMode === "add" ? handleSaveNew : handleSaveEdit}
					onCancel={handleCancel}
					isSubmitting={isSubmitting}
					submitError={submitError}
				/>
			)}

			{/* List view with tabs */}
			{viewMode === "list" && (
				<>
					<Tabs
						value={activeTab}
						onValueChange={(val) => {
							if (val === "Hard" || val === "Soft") setActiveTab(val);
						}}
					>
						<TabsList>
							<TabsTrigger value="Hard">
								Hard Skills ({hardSkills.length})
							</TabsTrigger>
							<TabsTrigger value="Soft">
								Soft Skills ({softSkills.length})
							</TabsTrigger>
						</TabsList>

						<TabsContent value="Hard">
							{hardSkills.length === 0 ? (
								<div className="text-muted-foreground py-8 text-center">
									<p>No hard skills yet.</p>
								</div>
							) : (
								<ReorderableList
									items={hardSkills}
									onReorder={handleReorder}
									label="Hard skill entries"
									renderItem={(entry, dragHandle) => (
										<SkillCard
											entry={entry}
											onEdit={handleEdit}
											onDelete={handleDeleteRequest}
											dragHandle={dragHandle}
										/>
									)}
								/>
							)}
						</TabsContent>

						<TabsContent value="Soft">
							{softSkills.length === 0 ? (
								<div className="text-muted-foreground py-8 text-center">
									<p>No soft skills yet.</p>
								</div>
							) : (
								<ReorderableList
									items={softSkills}
									onReorder={handleReorder}
									label="Soft skill entries"
									renderItem={(entry, dragHandle) => (
										<SkillCard
											entry={entry}
											onEdit={handleEdit}
											onDelete={handleDeleteRequest}
											dragHandle={dragHandle}
										/>
									)}
								/>
							)}
						</TabsContent>
					</Tabs>

					<Button
						type="button"
						variant="outline"
						onClick={handleAdd}
						className="self-center"
					>
						<Plus className="mr-2 h-4 w-4" />
						Add skill
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

			{/* Delete confirmation dialog */}
			<ConfirmationDialog
				open={deleteTarget !== null}
				onOpenChange={(open) => {
					if (!open) handleDeleteCancel();
				}}
				title="Delete skill"
				description={
					deleteError
						? `Failed to delete "${deleteTarget?.skill_name ?? ""}". ${deleteError}`
						: `Are you sure you want to delete "${deleteTarget?.skill_name ?? ""}"? This cannot be undone.`
				}
				confirmLabel="Delete"
				variant="destructive"
				onConfirm={handleDeleteConfirm}
				loading={isDeleting}
			/>
		</div>
	);
}
