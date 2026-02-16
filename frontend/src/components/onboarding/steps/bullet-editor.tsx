"use client";

/**
 * Bullet editor for managing accomplishment bullets within a work history entry.
 *
 * REQ-012 §6.3.3: Per-job bullet editing — expandable list within each
 * job card with add/edit/delete and drag-and-drop reordering.
 */

import { Plus } from "lucide-react";
import { useCallback, useState } from "react";

import { Button } from "@/components/ui/button";
import { ReorderableList } from "@/components/ui/reorderable-list";
import { apiDelete, apiPatch, apiPost } from "@/lib/api-client";
import { toFriendlyError } from "@/lib/form-errors";
import type { ApiResponse } from "@/types/api";
import type { Bullet } from "@/types/persona";

import { BulletForm } from "./bullet-form";
import type { BulletFormData } from "./bullet-form";
import { BulletItem } from "./bullet-item";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface BulletEditorProps {
	personaId: string;
	workHistoryId: string;
	initialBullets: Bullet[];
	onBulletsChange: (bullets: Bullet[]) => void;
}

type ViewMode = "list" | "add" | "edit";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Convert form data to API request body. */
function toRequestBody(
	data: BulletFormData,
	displayOrder: number,
): Record<string, unknown> {
	return {
		text: data.text,
		metrics: data.metrics || null,
		display_order: displayOrder,
	};
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function BulletEditor({
	personaId,
	workHistoryId,
	initialBullets,
	onBulletsChange,
}: Readonly<BulletEditorProps>) {
	const [bullets, setBullets] = useState<Bullet[]>(initialBullets);
	const [viewMode, setViewMode] = useState<ViewMode>("list");
	const [editingBullet, setEditingBullet] = useState<Bullet | null>(null);
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [submitError, setSubmitError] = useState<string | null>(null);

	const basePath = `/personas/${personaId}/work-history/${workHistoryId}/bullets`;

	// -----------------------------------------------------------------------
	// Add handler
	// -----------------------------------------------------------------------

	const handleAdd = useCallback(() => {
		setEditingBullet(null);
		setSubmitError(null);
		setViewMode("add");
	}, []);

	const handleSaveNew = useCallback(
		async (data: BulletFormData) => {
			setSubmitError(null);
			setIsSubmitting(true);

			try {
				const res = await apiPost<ApiResponse<Bullet>>(basePath, {
					...toRequestBody(data, bullets.length),
				});

				const newBullets = [...bullets, res.data];
				setBullets(newBullets);
				onBulletsChange(newBullets);
				setViewMode("list");
			} catch (err) {
				setSubmitError(toFriendlyError(err));
			} finally {
				setIsSubmitting(false);
			}
		},
		[basePath, bullets, onBulletsChange],
	);

	// -----------------------------------------------------------------------
	// Edit handler
	// -----------------------------------------------------------------------

	const handleEdit = useCallback((bullet: Bullet) => {
		setEditingBullet(bullet);
		setSubmitError(null);
		setViewMode("edit");
	}, []);

	const handleSaveEdit = useCallback(
		async (data: BulletFormData) => {
			if (!editingBullet) return;

			setSubmitError(null);
			setIsSubmitting(true);

			try {
				const res = await apiPatch<ApiResponse<Bullet>>(
					`${basePath}/${editingBullet.id}`,
					toRequestBody(data, editingBullet.display_order),
				);

				const newBullets = bullets.map((b) =>
					b.id === editingBullet.id ? res.data : b,
				);
				setBullets(newBullets);
				onBulletsChange(newBullets);
				setViewMode("list");
			} catch (err) {
				setSubmitError(toFriendlyError(err));
			} finally {
				setIsSubmitting(false);
			}
		},
		[basePath, bullets, editingBullet, onBulletsChange],
	);

	// -----------------------------------------------------------------------
	// Delete handler
	// -----------------------------------------------------------------------

	const handleDelete = useCallback(
		async (bullet: Bullet) => {
			try {
				await apiDelete(`${basePath}/${bullet.id}`);
				const newBullets = bullets.filter((b) => b.id !== bullet.id);
				setBullets(newBullets);
				onBulletsChange(newBullets);
			} catch (err) {
				setSubmitError(toFriendlyError(err));
			}
		},
		[basePath, bullets, onBulletsChange],
	);

	// -----------------------------------------------------------------------
	// Cancel form
	// -----------------------------------------------------------------------

	const handleCancel = useCallback(() => {
		setEditingBullet(null);
		setSubmitError(null);
		setViewMode("list");
	}, []);

	// -----------------------------------------------------------------------
	// Reorder handler
	// -----------------------------------------------------------------------

	const handleReorder = useCallback(
		(reordered: Bullet[]) => {
			const previousBullets = [...bullets];
			setBullets(reordered);
			onBulletsChange(reordered);

			const patches = reordered
				.map((bullet, newOrder) => ({ bullet, newOrder }))
				.filter(({ bullet, newOrder }) => bullet.display_order !== newOrder)
				.map(({ bullet, newOrder }) =>
					apiPatch(`${basePath}/${bullet.id}`, {
						display_order: newOrder,
					}),
				);

			if (patches.length > 0) {
				void Promise.all(patches).catch(() => {
					setBullets(previousBullets);
					onBulletsChange(previousBullets);
					setSubmitError("Failed to save new order. Please try again.");
				});
			}
		},
		[basePath, bullets, onBulletsChange],
	);

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	return (
		<div data-testid="bullet-editor" className="space-y-3">
			{/* Form view (add or edit) */}
			{viewMode !== "list" && (
				<BulletForm
					initialValues={
						viewMode === "edit" && editingBullet
							? {
									text: editingBullet.text,
									metrics: editingBullet.metrics ?? "",
								}
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
					{bullets.length === 0 ? (
						<p className="text-muted-foreground py-2 text-center text-sm">
							No bullets yet. Add your first accomplishment.
						</p>
					) : (
						<ReorderableList
							items={bullets}
							onReorder={handleReorder}
							label="Accomplishment bullets"
							renderItem={(bullet, dragHandle) => (
								<BulletItem
									bullet={bullet}
									onEdit={handleEdit}
									onDelete={handleDelete}
									dragHandle={dragHandle}
								/>
							)}
						/>
					)}

					{submitError && (
						<div
							role="alert"
							className="text-destructive text-sm font-medium"
							data-testid="bullet-submit-error"
						>
							{submitError}
						</div>
					)}

					<Button
						type="button"
						variant="outline"
						size="sm"
						onClick={handleAdd}
						className="w-full"
					>
						<Plus className="mr-2 h-4 w-4" />
						Add bullet
					</Button>
				</>
			)}
		</div>
	);
}
