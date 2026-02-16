"use client";

/**
 * Dialog for deletion with reference checking.
 *
 * REQ-012 §7.5 / REQ-001 §7b: Shows different dialog variants
 * depending on the deletion flow state:
 *   - checking: spinner while reference check runs
 *   - mutable-refs: three-option dialog (remove all, review each, cancel)
 *   - review-each: checkbox list of references to deselect
 *   - immutable-block: warning with link to application
 *   - deleting: spinner while delete runs
 *
 * Uses Dialog (not AlertDialog) because the "review-each" variant
 * needs interactive checkboxes. onInteractOutside is prevented to
 * keep the blocking UX.
 */

import { AlertTriangle, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import type { DeleteFlowState, ReferencingEntity } from "@/types/deletion";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface DeleteReferenceDialogProps {
	open: boolean;
	onCancel: () => void;
	flowState: DeleteFlowState;
	deleteError: string | null;
	itemLabel: string;
	references: ReferencingEntity[];
	hasImmutableReferences: boolean;
	reviewSelections: Record<string, boolean>;
	onRemoveAllAndDelete: () => void;
	onExpandReviewEach: () => void;
	onToggleReviewSelection: (refId: string) => void;
	onConfirmReviewAndDelete: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DeleteReferenceDialog({
	open,
	onCancel,
	flowState,
	deleteError,
	itemLabel,
	references,
	hasImmutableReferences: _hasImmutableReferences,
	reviewSelections,
	onRemoveAllAndDelete,
	onExpandReviewEach,
	onToggleReviewSelection,
	onConfirmReviewAndDelete,
}: Readonly<DeleteReferenceDialogProps>) {
	const isProcessing = flowState === "checking" || flowState === "deleting";

	return (
		<Dialog
			open={open}
			onOpenChange={(nextOpen) => {
				if (!nextOpen && !isProcessing) onCancel();
			}}
		>
			<DialogContent
				showCloseButton={false}
				onInteractOutside={(e) => e.preventDefault()}
				data-testid="delete-reference-dialog"
			>
				{/* ------ Checking state ------ */}
				{flowState === "checking" && (
					<>
						<DialogHeader>
							<DialogTitle>Checking references...</DialogTitle>
							<DialogDescription>
								Checking if &quot;{itemLabel}&quot; is used in any resumes or
								cover letters.
							</DialogDescription>
						</DialogHeader>
						<div className="flex justify-center py-4">
							<Loader2
								className="text-muted-foreground h-8 w-8 animate-spin"
								data-testid="checking-spinner"
							/>
						</div>
						<DialogFooter>
							<Button variant="outline" disabled>
								Cancel
							</Button>
						</DialogFooter>
					</>
				)}

				{/* ------ Mutable references ------ */}
				{flowState === "mutable-refs" && (
					<>
						<DialogHeader>
							<DialogTitle>
								Used in {references.length} document
								{references.length === 1 ? "" : "s"}
							</DialogTitle>
							<DialogDescription>
								&quot;{itemLabel}&quot; is referenced by:
							</DialogDescription>
						</DialogHeader>
						<ul
							className="list-disc space-y-1 pl-5 text-sm"
							data-testid="reference-list"
						>
							{references.map((ref) => (
								<li key={ref.id}>{ref.name}</li>
							))}
						</ul>
						{deleteError && (
							<p
								className="text-destructive text-sm"
								data-testid="delete-error"
							>
								{deleteError}
							</p>
						)}
						<DialogFooter className="sm:flex-col sm:gap-2">
							<Button
								variant="destructive"
								onClick={onRemoveAllAndDelete}
								data-testid="remove-all-delete-btn"
							>
								Remove from all &amp; delete
							</Button>
							<Button
								variant="outline"
								onClick={onExpandReviewEach}
								data-testid="review-each-btn"
							>
								Review each
							</Button>
							<Button variant="outline" onClick={onCancel}>
								Cancel
							</Button>
						</DialogFooter>
					</>
				)}

				{/* ------ Review each ------ */}
				{flowState === "review-each" && (
					<>
						<DialogHeader>
							<DialogTitle>Review references</DialogTitle>
							<DialogDescription>
								Select which references to remove before deleting &quot;
								{itemLabel}&quot;.
							</DialogDescription>
						</DialogHeader>
						<div className="space-y-3" data-testid="review-checkbox-list">
							{references.map((ref) => (
								<label key={ref.id} className="flex items-center gap-2 text-sm">
									<Checkbox
										checked={reviewSelections[ref.id] ?? false}
										onCheckedChange={() => onToggleReviewSelection(ref.id)}
										data-testid={`review-checkbox-${ref.id}`}
									/>
									{ref.name}
								</label>
							))}
						</div>
						{deleteError && (
							<p
								className="text-destructive text-sm"
								data-testid="delete-error"
							>
								{deleteError}
							</p>
						)}
						<DialogFooter>
							<Button
								variant="destructive"
								onClick={onConfirmReviewAndDelete}
								data-testid="confirm-review-delete-btn"
							>
								Confirm &amp; delete
							</Button>
							<Button variant="outline" onClick={onCancel}>
								Back
							</Button>
						</DialogFooter>
					</>
				)}

				{/* ------ Immutable block ------ */}
				{flowState === "immutable-block" &&
					(() => {
						const refWithCompany = references.find((r) => r.company_name);
						const refWithApp = references.find((r) => r.application_id);
						return (
							<>
								<DialogHeader>
									<DialogTitle className="flex items-center gap-2">
										<AlertTriangle className="text-destructive h-5 w-5" />
										Cannot delete
									</DialogTitle>
									<DialogDescription>
										&quot;{itemLabel}&quot; is part of a submitted application
										{refWithCompany ? ` to ${refWithCompany.company_name}` : ""}
										. Submitted application documents cannot be modified.
									</DialogDescription>
								</DialogHeader>
								<ul
									className="list-disc space-y-1 pl-5 text-sm"
									data-testid="immutable-reference-list"
								>
									{references.map((ref) => (
										<li key={ref.id}>{ref.name}</li>
									))}
								</ul>
								<DialogFooter>
									{refWithApp && (
										<Button variant="outline" asChild>
											<a
												href={`/applications/${refWithApp.application_id}`}
												data-testid="go-to-application-link"
											>
												Go to Application
											</a>
										</Button>
									)}
									<Button variant="outline" onClick={onCancel}>
										Cancel
									</Button>
								</DialogFooter>
							</>
						);
					})()}

				{/* ------ Deleting state ------ */}
				{flowState === "deleting" && (
					<>
						<DialogHeader>
							<DialogTitle>Deleting...</DialogTitle>
							<DialogDescription>
								Removing &quot;{itemLabel}&quot; and updating references.
							</DialogDescription>
						</DialogHeader>
						<div className="flex justify-center py-4">
							<Loader2
								className="text-muted-foreground h-8 w-8 animate-spin"
								data-testid="deleting-spinner"
							/>
						</div>
						<DialogFooter>
							<Button variant="outline" disabled>
								Cancel
							</Button>
						</DialogFooter>
					</>
				)}
			</DialogContent>
		</Dialog>
	);
}
