/**
 * Hook for deleting persona items with reference checking.
 *
 * REQ-012 §7.5 / REQ-001 §7b: Before deleting, checks whether the
 * item is referenced by any BaseResumes or CoverLetters. Drives a
 * state machine that transitions through checking → mutable-refs /
 * immutable-block / immediate-delete depending on the API response.
 *
 * When the backend reference endpoint returns 404, the hook degrades
 * gracefully to the "no references" path (immediate delete + toast).
 */

import { useCallback, useRef, useState } from "react";

import type { QueryClient } from "@tanstack/react-query";

import { ApiError, apiDelete, apiGet } from "@/lib/api-client";
import { toFriendlyError } from "@/lib/form-errors";
import { showToast } from "@/lib/toast";
import type { ApiResponse } from "@/types/api";
import type {
	DeletableItemType,
	DeleteFlowState,
	ReferenceCheckResponse,
	ReferencingEntity,
} from "@/types/deletion";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface UseDeleteWithReferencesOptions<T extends { id: string }> {
	personaId: string;
	itemType: DeletableItemType;
	collection: string;
	getItemLabel: (item: T) => string;
	onDeleted: (deletedId: string) => void;
	queryClient?: QueryClient;
	queryKey?: readonly unknown[];
}

export interface UseDeleteWithReferencesReturn<T extends { id: string }> {
	deleteTarget: T | null;
	flowState: DeleteFlowState;
	deleteError: string | null;
	references: ReferencingEntity[];
	hasImmutableReferences: boolean;
	reviewSelections: Record<string, boolean>;
	requestDelete: (item: T) => void;
	cancel: () => void;
	removeAllAndDelete: () => Promise<void>;
	expandReviewEach: () => void;
	toggleReviewSelection: (refId: string) => void;
	confirmReviewAndDelete: () => Promise<void>;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useDeleteWithReferences<T extends { id: string }>(
	options: UseDeleteWithReferencesOptions<T>,
): UseDeleteWithReferencesReturn<T> {
	const {
		personaId,
		collection,
		getItemLabel,
		onDeleted,
		queryClient,
		queryKey,
	} = options;

	const [deleteTarget, setDeleteTarget] = useState<T | null>(null);
	const [flowState, setFlowState] = useState<DeleteFlowState>("idle");
	const [deleteError, setDeleteError] = useState<string | null>(null);
	const [references, setReferences] = useState<ReferencingEntity[]>([]);
	const [hasImmutableReferences, setHasImmutableReferences] = useState(false);
	const [reviewSelections, setReviewSelections] = useState<
		Record<string, boolean>
	>({});
	const preDeleteFlowStateRef = useRef<DeleteFlowState>("idle");

	// -----------------------------------------------------------------------
	// Internal helpers
	// -----------------------------------------------------------------------

	const resetState = useCallback(() => {
		setDeleteTarget(null);
		setFlowState("idle");
		setDeleteError(null);
		setReferences([]);
		setHasImmutableReferences(false);
		setReviewSelections({});
	}, []);

	const performDelete = useCallback(
		async (item: T) => {
			preDeleteFlowStateRef.current = flowState;
			setFlowState("deleting");
			try {
				await apiDelete(`/personas/${personaId}/${collection}/${item.id}`);
				const label = getItemLabel(item);
				showToast.success(`"${label}" deleted successfully.`);
				onDeleted(item.id);
				if (queryClient && queryKey) {
					await queryClient.invalidateQueries({ queryKey: [...queryKey] });
				}
				resetState();
			} catch (err) {
				setDeleteError(toFriendlyError(err));
				// Revert to the state before "deleting" was set
				setFlowState(preDeleteFlowStateRef.current);
			}
		},
		[
			personaId,
			collection,
			flowState,
			getItemLabel,
			onDeleted,
			queryClient,
			queryKey,
			resetState,
		],
	);

	// -----------------------------------------------------------------------
	// Public API
	// -----------------------------------------------------------------------

	const requestDelete = useCallback(
		(item: T) => {
			setDeleteTarget(item);
			setDeleteError(null);
			setFlowState("checking");

			apiGet<ApiResponse<ReferenceCheckResponse>>(
				`/personas/${personaId}/${collection}/${item.id}/references`,
			)
				.then((response) => {
					const refData = response.data;

					if (!refData.has_references) {
						// No references — delete immediately
						void performDelete(item);
						return;
					}

					if (refData.has_immutable_references) {
						setReferences(refData.references);
						setHasImmutableReferences(true);
						setFlowState("immutable-block");
					} else {
						setReferences(refData.references);
						setHasImmutableReferences(false);
						setFlowState("mutable-refs");
					}
				})
				.catch((err) => {
					if (err instanceof ApiError && err.status === 404) {
						// Backend not ready — graceful degradation
						void performDelete(item);
						return;
					}
					setDeleteError(toFriendlyError(err));
					setFlowState("idle");
					setDeleteTarget(null);
				});
		},
		[personaId, collection, performDelete],
	);

	const cancel = useCallback(() => {
		resetState();
	}, [resetState]);

	const removeAllAndDelete = useCallback(async () => {
		if (!deleteTarget) return;
		await performDelete(deleteTarget);
	}, [deleteTarget, performDelete]);

	const expandReviewEach = useCallback(() => {
		const selections: Record<string, boolean> = {};
		for (const ref of references) {
			selections[ref.id] = true;
		}
		setReviewSelections(selections);
		setFlowState("review-each");
	}, [references]);

	const toggleReviewSelection = useCallback((refId: string) => {
		setReviewSelections((prev) => ({
			...prev,
			[refId]: !prev[refId],
		}));
	}, []);

	const confirmReviewAndDelete = useCallback(async () => {
		if (!deleteTarget) return;
		await performDelete(deleteTarget);
	}, [deleteTarget, performDelete]);

	return {
		deleteTarget,
		flowState,
		deleteError,
		references,
		hasImmutableReferences,
		reviewSelections,
		requestDelete,
		cancel,
		removeAllAndDelete,
		expandReviewEach,
		toggleReviewSelection,
		confirmReviewAndDelete,
	};
}
