/**
 * Shared CRUD state management hook for onboarding step components.
 *
 * Extracts the common pattern of fetch-on-mount, add/edit/delete/reorder
 * handlers, and associated loading/error/view state from the five CRUD
 * onboarding steps (certification, education, work-history, skills, story).
 *
 * REQ-012 §6.3.3–§6.3.7: CRUD steps share identical state management.
 */

import { useCallback, useEffect, useState } from "react";

import { apiDelete, apiGet, apiPatch, apiPost } from "@/lib/api-client";
import { toFriendlyError } from "@/lib/form-errors";
import type { ApiListResponse, ApiResponse } from "@/types/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ViewMode = "list" | "add" | "edit";

/** Minimum shape required of every CRUD entity. */
interface CrudEntity {
	id: string;
	display_order: number;
}

interface UseCrudStepConfig<TEntity extends CrudEntity, TFormData> {
	/** Active persona ID (null during loading). */
	personaId: string | null;
	/** API collection path segment (e.g. "certifications", "education"). */
	collection: string;
	/** Converts an entity to form default values. */
	toFormValues: (entity: TEntity) => Partial<TFormData> | TFormData;
	/** Converts form data to the API request body. */
	toRequestBody: (data: TFormData) => object;
	/** When true, delete errors are captured and exposed via `deleteError`. */
	hasDeleteError?: boolean;
	/** Optional secondary fetch run in parallel (e.g. stories fetches skills). */
	secondaryFetch?: {
		collection: string;
		onData: (data: unknown[]) => void;
	};
}

interface UseCrudStepReturn<TEntity extends CrudEntity, TFormData> {
	entries: TEntity[];
	isLoading: boolean;
	viewMode: ViewMode;
	editingEntry: TEntity | null;
	isSubmitting: boolean;
	submitError: string | null;
	deleteTarget: TEntity | null;
	isDeleting: boolean;
	deleteError: string | null;
	setEntries: React.Dispatch<React.SetStateAction<TEntity[]>>;
	handleAdd: () => void;
	handleSaveNew: (data: TFormData) => Promise<void>;
	handleEdit: (entry: TEntity) => void;
	handleSaveEdit: (data: TFormData) => Promise<void>;
	handleDeleteRequest: (entry: TEntity) => void;
	handleDeleteConfirm: () => Promise<void>;
	handleDeleteCancel: () => void;
	handleCancel: () => void;
	handleReorder: (reordered: TEntity[]) => void;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

function useCrudStep<TEntity extends CrudEntity, TFormData>(
	config: UseCrudStepConfig<TEntity, TFormData>,
): UseCrudStepReturn<TEntity, TFormData> {
	const {
		personaId,
		collection,
		toRequestBody,
		hasDeleteError = false,
		secondaryFetch,
	} = config;

	const [entries, setEntries] = useState<TEntity[]>([]);
	const [isLoading, setIsLoading] = useState(true);
	const [viewMode, setViewMode] = useState<ViewMode>("list");
	const [editingEntry, setEditingEntry] = useState<TEntity | null>(null);
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [submitError, setSubmitError] = useState<string | null>(null);
	const [deleteTarget, setDeleteTarget] = useState<TEntity | null>(null);
	const [isDeleting, setIsDeleting] = useState(false);
	const [deleteError, setDeleteError] = useState<string | null>(null);

	// -----------------------------------------------------------------------
	// Fetch on mount
	// -----------------------------------------------------------------------

	useEffect(() => {
		if (!personaId) {
			setIsLoading(false);
			return;
		}

		let cancelled = false;

		if (secondaryFetch) {
			Promise.all([
				apiGet<ApiListResponse<TEntity>>(
					`/personas/${personaId}/${collection}`,
				),
				apiGet<ApiListResponse<unknown>>(
					`/personas/${personaId}/${secondaryFetch.collection}`,
				),
			])
				.then(([primaryRes, secondaryRes]) => {
					if (cancelled) return;
					setEntries(primaryRes.data);
					secondaryFetch.onData(secondaryRes.data);
				})
				.catch(() => {
					// Fetch failed — user can add entries manually
				})
				.finally(() => {
					if (!cancelled) setIsLoading(false);
				});
		} else {
			apiGet<ApiListResponse<TEntity>>(`/personas/${personaId}/${collection}`)
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
		}

		return () => {
			cancelled = true;
		};
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [personaId]);

	// -----------------------------------------------------------------------
	// Add handlers
	// -----------------------------------------------------------------------

	const handleAdd = useCallback(() => {
		setEditingEntry(null);
		setSubmitError(null);
		setViewMode("add");
	}, []);

	const handleSaveNew = useCallback(
		async (data: TFormData) => {
			if (!personaId) return;

			setSubmitError(null);
			setIsSubmitting(true);

			try {
				const res = await apiPost<ApiResponse<TEntity>>(
					`/personas/${personaId}/${collection}`,
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
		[personaId, collection, toRequestBody, entries.length],
	);

	// -----------------------------------------------------------------------
	// Edit handlers
	// -----------------------------------------------------------------------

	const handleEdit = useCallback((entry: TEntity) => {
		setEditingEntry(entry);
		setSubmitError(null);
		setViewMode("edit");
	}, []);

	const handleSaveEdit = useCallback(
		async (data: TFormData) => {
			if (!personaId || !editingEntry) return;

			setSubmitError(null);
			setIsSubmitting(true);

			try {
				const res = await apiPatch<ApiResponse<TEntity>>(
					`/personas/${personaId}/${collection}/${editingEntry.id}`,
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
		[personaId, collection, editingEntry, toRequestBody],
	);

	// -----------------------------------------------------------------------
	// Delete handlers
	// -----------------------------------------------------------------------

	const handleDeleteRequest = useCallback(
		(entry: TEntity) => {
			if (hasDeleteError) setDeleteError(null);
			setDeleteTarget(entry);
		},
		[hasDeleteError],
	);

	const handleDeleteConfirm = useCallback(async () => {
		if (!personaId || !deleteTarget) return;

		setIsDeleting(true);

		try {
			await apiDelete(
				`/personas/${personaId}/${collection}/${deleteTarget.id}`,
			);
			setEntries((prev) => prev.filter((e) => e.id !== deleteTarget.id));
			setDeleteTarget(null);
		} catch (err) {
			if (hasDeleteError) {
				setDeleteError(toFriendlyError(err));
			}
			// When hasDeleteError is false, dialog stays open silently
		} finally {
			setIsDeleting(false);
		}
	}, [personaId, collection, deleteTarget, hasDeleteError]);

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
		(reordered: TEntity[]) => {
			if (!personaId) return;

			const previousEntries = [...entries];
			setEntries(reordered);

			const patches = reordered
				.map((entry, newOrder) => ({ entry, newOrder }))
				.filter(({ entry, newOrder }) => entry.display_order !== newOrder)
				.map(({ entry, newOrder }) =>
					apiPatch(`/personas/${personaId}/${collection}/${entry.id}`, {
						display_order: newOrder,
					}),
				);

			if (patches.length > 0) {
				void Promise.all(patches).catch(() => {
					setEntries(previousEntries);
				});
			}
		},
		[personaId, collection, entries],
	);

	return {
		entries,
		isLoading,
		viewMode,
		editingEntry,
		isSubmitting,
		submitError,
		deleteTarget,
		isDeleting,
		deleteError,
		setEntries,
		handleAdd,
		handleSaveNew,
		handleEdit,
		handleSaveEdit,
		handleDeleteRequest,
		handleDeleteConfirm,
		handleDeleteCancel,
		handleCancel,
		handleReorder,
	};
}

export { useCrudStep };
export type { CrudEntity, UseCrudStepConfig, UseCrudStepReturn };
