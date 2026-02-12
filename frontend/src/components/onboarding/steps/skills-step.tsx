"use client";

/**
 * Skills step for onboarding wizard (Step 5).
 *
 * REQ-012 §6.3.5: Not skippable. Skills editor with proficiency
 * selector, conditional category dropdown, CRUD, and reordering.
 * All 6 fields required per skill entry.
 */

import { ArrowLeft, Loader2, Plus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog";
import { ReorderableList } from "@/components/ui/reorderable-list";
import { apiDelete, apiGet, apiPatch, apiPost } from "@/lib/api-client";
import { toFriendlyError } from "@/lib/form-errors";
import { useOnboarding } from "@/lib/onboarding-provider";
import type { ApiListResponse, ApiResponse } from "@/types/api";
import type { Skill } from "@/types/persona";

import { SkillCard } from "./skills-card";
import { SkillForm } from "./skills-form";
import type { SkillFormData } from "./skills-form";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Convert form data to API request body. */
function toRequestBody(data: SkillFormData) {
	return {
		skill_name: data.skill_name,
		skill_type: data.skill_type,
		category: data.category,
		proficiency: data.proficiency,
		years_used: parseInt(data.years_used, 10),
		last_used: data.last_used,
	};
}

/** Convert a Skill entry to form initial values. */
function toFormValues(entry: Skill): Partial<SkillFormData> {
	return {
		skill_name: entry.skill_name,
		skill_type: entry.skill_type,
		category: entry.category,
		proficiency: entry.proficiency,
		years_used: String(entry.years_used),
		last_used: entry.last_used,
	};
}

type ViewMode = "list" | "add" | "edit";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Onboarding Step 5: Skills.
 *
 * Renders a list of skill cards with add/edit/delete and
 * drag-and-drop reordering. Not skippable — all 6 fields required.
 */
export function SkillsStep() {
	const { personaId, next, back } = useOnboarding();

	const [entries, setEntries] = useState<Skill[]>([]);
	const [isLoading, setIsLoading] = useState(true);
	const [viewMode, setViewMode] = useState<ViewMode>("list");
	const [editingEntry, setEditingEntry] = useState<Skill | null>(null);
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [submitError, setSubmitError] = useState<string | null>(null);
	const [deleteTarget, setDeleteTarget] = useState<Skill | null>(null);
	const [isDeleting, setIsDeleting] = useState(false);
	const [deleteError, setDeleteError] = useState<string | null>(null);

	// -----------------------------------------------------------------------
	// Fetch skills on mount
	// -----------------------------------------------------------------------

	useEffect(() => {
		if (!personaId) {
			setIsLoading(false);
			return;
		}

		let cancelled = false;

		apiGet<ApiListResponse<Skill>>(`/personas/${personaId}/skills`)
			.then((res) => {
				if (cancelled) return;
				setEntries(res.data);
			})
			.catch(() => {
				// Fetch failed — user can add entries manually
			})
			.finally(() => {
				if (!cancelled) setIsLoading(false);
			});

		return () => {
			cancelled = true;
		};
	}, [personaId]);

	// -----------------------------------------------------------------------
	// Add handler
	// -----------------------------------------------------------------------

	const handleAdd = useCallback(() => {
		setEditingEntry(null);
		setSubmitError(null);
		setViewMode("add");
	}, []);

	const handleSaveNew = useCallback(
		async (data: SkillFormData) => {
			if (!personaId) return;

			setSubmitError(null);
			setIsSubmitting(true);

			try {
				const res = await apiPost<ApiResponse<Skill>>(
					`/personas/${personaId}/skills`,
					{
						...toRequestBody(data),
						display_order: entries.length,
					},
				);

				setEntries((prev) => [...prev, res.data]);
				setViewMode("list");
			} catch (err) {
				setSubmitError(toFriendlyError(err));
			} finally {
				setIsSubmitting(false);
			}
		},
		[personaId, entries.length],
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
		async (data: SkillFormData) => {
			if (!personaId || !editingEntry) return;

			setSubmitError(null);
			setIsSubmitting(true);

			try {
				const res = await apiPatch<ApiResponse<Skill>>(
					`/personas/${personaId}/skills/${editingEntry.id}`,
					toRequestBody(data),
				);

				setEntries((prev) =>
					prev.map((e) => (e.id === editingEntry.id ? res.data : e)),
				);
				setViewMode("list");
			} catch (err) {
				setSubmitError(toFriendlyError(err));
			} finally {
				setIsSubmitting(false);
			}
		},
		[personaId, editingEntry],
	);

	// -----------------------------------------------------------------------
	// Delete handler
	// -----------------------------------------------------------------------

	const handleDeleteRequest = useCallback((entry: Skill) => {
		setDeleteError(null);
		setDeleteTarget(entry);
	}, []);

	const handleDeleteConfirm = useCallback(async () => {
		if (!personaId || !deleteTarget) return;

		setIsDeleting(true);

		try {
			await apiDelete(`/personas/${personaId}/skills/${deleteTarget.id}`);
			setEntries((prev) => prev.filter((e) => e.id !== deleteTarget.id));
			setDeleteTarget(null);
		} catch (err) {
			setDeleteError(toFriendlyError(err));
		} finally {
			setIsDeleting(false);
		}
	}, [personaId, deleteTarget]);

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
	// Reorder handler
	// -----------------------------------------------------------------------

	const handleReorder = useCallback(
		(reordered: Skill[]) => {
			if (!personaId) return;

			const previousEntries = [...entries];
			setEntries(reordered);

			const patches = reordered
				.map((entry, newOrder) => ({ entry, newOrder }))
				.filter(({ entry, newOrder }) => entry.display_order !== newOrder)
				.map(({ entry, newOrder }) =>
					apiPatch(`/personas/${personaId}/skills/${entry.id}`, {
						display_order: newOrder,
					}),
				);

			if (patches.length > 0) {
				void Promise.all(patches).catch(() => {
					setEntries(previousEntries);
				});
			}
		},
		[personaId, entries],
	);

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	if (isLoading) {
		return (
			<div
				className="flex flex-1 flex-col items-center justify-center"
				data-testid="loading-skills"
			>
				<Loader2 className="text-primary h-8 w-8 animate-spin" />
				<p className="text-muted-foreground mt-3">Loading your skills...</p>
			</div>
		);
	}

	return (
		<div className="flex flex-1 flex-col gap-6">
			<div className="text-center">
				<h2 className="text-lg font-semibold">Skills</h2>
				<p className="text-muted-foreground mt-1">
					{entries.length === 0
						? "Add your technical and professional skills."
						: "Your skills. Add, edit, or reorder as needed."}
				</p>
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

			{/* List view */}
			{viewMode === "list" && (
				<>
					{entries.length === 0 ? (
						<div className="text-muted-foreground py-8 text-center">
							<p>No skills yet.</p>
						</div>
					) : (
						<ReorderableList
							items={entries}
							onReorder={handleReorder}
							label="Skill entries"
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

			{/* Navigation — no skip button (skills is not skippable) */}
			{viewMode === "list" && (
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
					<Button type="button" onClick={next} data-testid="next-button">
						Next
					</Button>
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
