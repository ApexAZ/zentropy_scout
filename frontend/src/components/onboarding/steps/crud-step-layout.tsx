/**
 * Shared layout for CRUD onboarding steps.
 *
 * Renders the standard step structure: loading spinner, header,
 * form view toggle, empty/list state with ReorderableList,
 * add button, navigation footer, and delete confirmation dialog.
 *
 * Each step provides entity-specific text and render props.
 */

import type { ReactNode } from "react";
import { ArrowLeft, Loader2, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog";
import { ReorderableList } from "@/components/ui/reorderable-list";
import type { UseCrudStepReturn } from "@/hooks/use-crud-step";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CrudEntity {
	id: string;
	display_order: number;
}

interface CrudStepLayoutProps<TEntity extends CrudEntity, TFormData> {
	/** The CRUD state object from useCrudStep. */
	crud: UseCrudStepReturn<TEntity, TFormData>;

	// -- Text config --

	/** Step title displayed as h2. */
	title: string;
	/** Subtitle shown when the entry list is empty. */
	emptySubtitle: string;
	/** Subtitle shown when entries exist. String or function of entry count. */
	listSubtitle: string | ((count: number) => string);
	/** data-testid for the loading spinner wrapper. */
	loadingTestId: string;
	/** Text shown below the loading spinner. */
	loadingText: string;
	/** Message when the entry list is empty. */
	emptyMessage: string;
	/** aria-label for the ReorderableList. */
	listLabel: string;
	/** Label for the Add button (e.g. "Add education"). */
	addLabel: string;

	// -- Delete dialog --

	/** Title for the delete confirmation dialog. */
	deleteTitle: string;
	/** Generates the delete dialog description from the target entity and optional error. */
	getDeleteDescription: (
		target: TEntity | null,
		error: string | null,
	) => string;

	// -- Render props --

	/** Converts an entity to form values for the edit form. */
	toFormValues: (entity: TEntity) => TFormData | Partial<TFormData>;
	/** Renders the entity form (add or edit). */
	renderForm: (props: {
		initialValues: TFormData | Partial<TFormData> | undefined;
		onSave: (data: TFormData) => Promise<void>;
		onCancel: () => void;
		isSubmitting: boolean;
		submitError: string | null;
	}) => ReactNode;
	/** Renders a card for an entity in the list. */
	renderCard: (entry: TEntity, dragHandle: ReactNode) => ReactNode;

	// -- Navigation --

	/** Navigates to the previous step. */
	back: () => void;
	/** Navigates to the next step. */
	next: () => void;
	/** Optional skip handler (renders Skip button when provided). */
	skip?: () => void;
	/** Whether the Skip button should be visible (defaults to entries.length === 0). */
	showSkip?: boolean;
	/** Whether the Next button should be disabled. */
	nextDisabled?: boolean;

	// -- Optional extras --

	/** Extra content rendered between the list and navigation footer. */
	beforeNavigation?: ReactNode;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

function CrudStepLayout<TEntity extends CrudEntity, TFormData>({
	crud,
	title,
	emptySubtitle,
	listSubtitle,
	loadingTestId,
	loadingText,
	emptyMessage,
	listLabel,
	addLabel,
	deleteTitle,
	getDeleteDescription,
	toFormValues,
	renderForm,
	renderCard,
	back,
	next,
	skip,
	showSkip,
	nextDisabled = false,
	beforeNavigation,
}: Readonly<CrudStepLayoutProps<TEntity, TFormData>>) {
	if (crud.isLoading) {
		return (
			<div
				className="flex flex-1 flex-col items-center justify-center"
				data-testid={loadingTestId}
			>
				<Loader2 className="text-primary h-8 w-8 animate-spin" />
				<p className="text-muted-foreground mt-3">{loadingText}</p>
			</div>
		);
	}

	let subtitle = emptySubtitle;
	if (crud.entries.length > 0) {
		subtitle =
			typeof listSubtitle === "function"
				? listSubtitle(crud.entries.length)
				: listSubtitle;
	}

	const skipVisible =
		showSkip ?? (skip !== undefined && crud.entries.length === 0);

	return (
		<div className="flex flex-1 flex-col gap-6">
			<div className="text-center">
				<h2 className="text-lg font-semibold">{title}</h2>
				<p className="text-muted-foreground mt-1">{subtitle}</p>
			</div>

			{/* Form view (add or edit) */}
			{crud.viewMode !== "list" &&
				renderForm({
					initialValues:
						crud.viewMode === "edit" && crud.editingEntry
							? toFormValues(crud.editingEntry)
							: undefined,
					onSave:
						crud.viewMode === "add" ? crud.handleSaveNew : crud.handleSaveEdit,
					onCancel: crud.handleCancel,
					isSubmitting: crud.isSubmitting,
					submitError: crud.submitError,
				})}

			{/* List view */}
			{crud.viewMode === "list" && (
				<>
					{crud.entries.length === 0 ? (
						<div className="text-muted-foreground py-8 text-center">
							<p>{emptyMessage}</p>
						</div>
					) : (
						<ReorderableList
							items={crud.entries}
							onReorder={crud.handleReorder}
							label={listLabel}
							renderItem={renderCard}
						/>
					)}

					<Button
						type="button"
						variant="outline"
						onClick={crud.handleAdd}
						className="self-center"
					>
						<Plus className="mr-2 h-4 w-4" />
						{addLabel}
					</Button>
				</>
			)}

			{/* Extra content before navigation */}
			{crud.viewMode === "list" && beforeNavigation}

			{/* Navigation */}
			{crud.viewMode === "list" && (
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
					<div className="flex gap-2">
						{skipVisible && skip && (
							<Button type="button" variant="outline" onClick={skip}>
								Skip
							</Button>
						)}
						<Button
							type="button"
							onClick={next}
							disabled={nextDisabled}
							data-testid="next-button"
						>
							Next
						</Button>
					</div>
				</div>
			)}

			{/* Delete confirmation dialog */}
			<ConfirmationDialog
				open={crud.deleteTarget !== null}
				onOpenChange={(open) => {
					if (!open) crud.handleDeleteCancel();
				}}
				title={deleteTitle}
				description={getDeleteDescription(crud.deleteTarget, crud.deleteError)}
				confirmLabel="Delete"
				variant="destructive"
				onConfirm={crud.handleDeleteConfirm}
				loading={crud.isDeleting}
			/>
		</div>
	);
}

export { CrudStepLayout };
export type { CrudStepLayoutProps };
