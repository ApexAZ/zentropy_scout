"use client";

/**
 * Work history step for onboarding wizard (Step 3a).
 *
 * REQ-012 §6.3.3: Display jobs in editable cards with add/edit/delete
 * and ordering. Minimum 1 job required to proceed.
 */

import { ArrowLeft, Loader2, Plus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog";
import { ReorderableList } from "@/components/ui/reorderable-list";
import {
	ApiError,
	apiDelete,
	apiGet,
	apiPatch,
	apiPost,
} from "@/lib/api-client";
import { useOnboarding } from "@/lib/onboarding-provider";
import type { ApiListResponse, ApiResponse } from "@/types/api";
import type { WorkHistory } from "@/types/persona";

import { WorkHistoryCard } from "./work-history-card";
import { WorkHistoryForm, toMonthValue } from "./work-history-form";
import type { WorkHistoryFormData } from "./work-history-form";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Friendly error messages keyed by API error code. */
const FRIENDLY_ERROR_MESSAGES: Readonly<Record<string, string>> = {
	VALIDATION_ERROR: "Please check your input and try again.",
};

/** Fallback error message for unexpected errors. */
const GENERIC_ERROR_MESSAGE = "Failed to save. Please try again.";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Map an ApiError to a user-friendly message. */
function toFriendlyError(err: unknown): string {
	if (err instanceof ApiError) {
		return FRIENDLY_ERROR_MESSAGES[err.code] ?? GENERIC_ERROR_MESSAGE;
	}
	return GENERIC_ERROR_MESSAGE;
}

/** Convert month input value (YYYY-MM) to ISO date (YYYY-MM-01). */
function toIsoDate(monthValue: string): string {
	return monthValue ? `${monthValue}-01` : "";
}

/** Convert a WorkHistory entry to form initial values. */
function toFormValues(entry: WorkHistory): Partial<WorkHistoryFormData> {
	return {
		job_title: entry.job_title,
		company_name: entry.company_name,
		company_industry: entry.company_industry ?? "",
		location: entry.location,
		work_model: entry.work_model,
		start_date: toMonthValue(entry.start_date),
		end_date: toMonthValue(entry.end_date),
		is_current: entry.is_current,
		description: entry.description ?? "",
	};
}

/** Convert form data to API request body. */
function toRequestBody(data: WorkHistoryFormData) {
	return {
		job_title: data.job_title,
		company_name: data.company_name,
		company_industry: data.company_industry || null,
		location: data.location,
		work_model: data.work_model,
		start_date: toIsoDate(data.start_date),
		end_date: data.is_current ? null : toIsoDate(data.end_date ?? ""),
		is_current: data.is_current,
		description: data.description || null,
	};
}

type ViewMode = "list" | "add" | "edit";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Onboarding Step 3a: Work History.
 *
 * Renders a list of work history cards with add/edit/delete and
 * drag-and-drop reordering. Minimum 1 job is required to proceed.
 */
export function WorkHistoryStep() {
	const { personaId, next, back } = useOnboarding();

	const [entries, setEntries] = useState<WorkHistory[]>([]);
	const [isLoading, setIsLoading] = useState(true);
	const [viewMode, setViewMode] = useState<ViewMode>("list");
	const [editingEntry, setEditingEntry] = useState<WorkHistory | null>(null);
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [submitError, setSubmitError] = useState<string | null>(null);
	const [deleteTarget, setDeleteTarget] = useState<WorkHistory | null>(null);
	const [isDeleting, setIsDeleting] = useState(false);

	// -----------------------------------------------------------------------
	// Fetch work history on mount
	// -----------------------------------------------------------------------

	useEffect(() => {
		if (!personaId) {
			setIsLoading(false);
			return;
		}

		let cancelled = false;

		apiGet<ApiListResponse<WorkHistory>>(`/personas/${personaId}/work-history`)
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
		async (data: WorkHistoryFormData) => {
			if (!personaId) return;

			setSubmitError(null);
			setIsSubmitting(true);

			try {
				const res = await apiPost<ApiResponse<WorkHistory>>(
					`/personas/${personaId}/work-history`,
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

	const handleEdit = useCallback((entry: WorkHistory) => {
		setEditingEntry(entry);
		setSubmitError(null);
		setViewMode("edit");
	}, []);

	const handleSaveEdit = useCallback(
		async (data: WorkHistoryFormData) => {
			if (!personaId || !editingEntry) return;

			setSubmitError(null);
			setIsSubmitting(true);

			try {
				const res = await apiPatch<ApiResponse<WorkHistory>>(
					`/personas/${personaId}/work-history/${editingEntry.id}`,
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

	const handleDeleteRequest = useCallback((entry: WorkHistory) => {
		setDeleteTarget(entry);
	}, []);

	const handleDeleteConfirm = useCallback(async () => {
		if (!personaId || !deleteTarget) return;

		setIsDeleting(true);

		try {
			await apiDelete(`/personas/${personaId}/work-history/${deleteTarget.id}`);
			setEntries((prev) => prev.filter((e) => e.id !== deleteTarget.id));
			setDeleteTarget(null);
		} catch {
			// Delete failed — dialog stays open
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
		(reordered: WorkHistory[]) => {
			if (!personaId) return;

			const previousEntries = [...entries];
			setEntries(reordered);

			// PATCH display_order for each changed entry
			const patches = reordered
				.map((entry, newOrder) => ({ entry, newOrder }))
				.filter(({ entry, newOrder }) => entry.display_order !== newOrder)
				.map(({ entry, newOrder }) =>
					apiPatch(`/personas/${personaId}/work-history/${entry.id}`, {
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
				data-testid="loading-work-history"
			>
				<Loader2 className="text-primary h-8 w-8 animate-spin" />
				<p className="text-muted-foreground mt-3">
					Loading your work history...
				</p>
			</div>
		);
	}

	return (
		<div className="flex flex-1 flex-col gap-6">
			<div className="text-center">
				<h2 className="text-lg font-semibold">Work History</h2>
				<p className="text-muted-foreground mt-1">
					Add your work experience. We&apos;ll use this to build your resume.
				</p>
			</div>

			{/* Form view (add or edit) */}
			{viewMode !== "list" && (
				<WorkHistoryForm
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
							<p>Add your first job to get started.</p>
						</div>
					) : (
						<ReorderableList
							items={entries}
							onReorder={handleReorder}
							label="Work history entries"
							renderItem={(entry, dragHandle) => (
								<WorkHistoryCard
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
						Add a job
					</Button>
				</>
			)}

			{/* Navigation */}
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
					<Button
						type="button"
						disabled={entries.length === 0}
						onClick={next}
						data-testid="next-button"
					>
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
				title="Delete job entry"
				description={`Are you sure you want to delete "${deleteTarget?.job_title ?? ""}" at ${deleteTarget?.company_name ?? ""}? This cannot be undone.`}
				confirmLabel="Delete"
				variant="destructive"
				onConfirm={handleDeleteConfirm}
				loading={isDeleting}
			/>
		</div>
	);
}
