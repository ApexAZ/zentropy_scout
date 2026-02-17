"use client";

/**
 * Work history step for onboarding wizard (Step 3).
 *
 * REQ-012 §6.3.3: Display jobs in editable cards with add/edit/delete
 * and ordering. Minimum 1 job required to proceed. Each card expands
 * to show accomplishment bullets with min 1 bullet per job.
 */

import { useCallback, useState } from "react";

import { useCrudStep } from "@/hooks/use-crud-step";
import { useOnboarding } from "@/lib/onboarding-provider";
import { toFormValues, toRequestBody } from "@/lib/work-history-helpers";
import type { Bullet, WorkHistory } from "@/types/persona";

import { BulletEditor } from "./bullet-editor";
import { CrudStepLayout } from "./crud-step-layout";
import { WorkHistoryCard } from "./work-history-card";
import { WorkHistoryForm } from "./work-history-form";
import type { WorkHistoryFormData } from "./work-history-form";

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

	const crud = useCrudStep<WorkHistory, WorkHistoryFormData>({
		personaId,
		collection: "work-history",
		toFormValues,
		toRequestBody,
	});

	const [expandedEntryId, setExpandedEntryId] = useState<string | null>(null);

	// -----------------------------------------------------------------------
	// Bullet expand/collapse and change handlers
	// -----------------------------------------------------------------------

	const handleToggleExpand = useCallback((entryId: string) => {
		setExpandedEntryId((prev) => (prev === entryId ? null : entryId));
	}, []);

	const handleBulletsChange = useCallback(
		(entryId: string, bullets: Bullet[]) => {
			crud.setEntries((prev) =>
				prev.map((e) => (e.id === entryId ? { ...e, bullets } : e)),
			);
		},
		[crud],
	);

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	const bulletHint = crud.entries.some((e) => e.bullets.length === 0) ? (
		<p
			className="text-muted-foreground text-center text-sm"
			data-testid="bullet-hint"
		>
			Each job needs at least one accomplishment bullet to continue.
		</p>
	) : null;

	return (
		<CrudStepLayout
			crud={crud}
			title="Work History"
			emptySubtitle="Add your work experience. We'll use this to build your resume."
			listSubtitle="Add your work experience. We'll use this to build your resume."
			loadingTestId="loading-work-history"
			loadingText="Loading your work history..."
			emptyMessage="Add your first job to get started."
			listLabel="Work history entries"
			addLabel="Add a job"
			deleteTitle="Delete job entry"
			getDeleteDescription={(target) =>
				`Are you sure you want to delete "${target?.job_title ?? ""}" at ${target?.company_name ?? ""}? This cannot be undone.`
			}
			toFormValues={toFormValues}
			renderForm={(props) => <WorkHistoryForm {...props} />}
			renderCard={(entry, dragHandle) => (
				<div>
					<WorkHistoryCard
						entry={entry}
						onEdit={crud.handleEdit}
						onDelete={crud.handleDeleteRequest}
						dragHandle={dragHandle}
						expanded={expandedEntryId === entry.id}
						onToggleExpand={() => handleToggleExpand(entry.id)}
					/>
					{expandedEntryId === entry.id && personaId && (
						<div className="border-border ml-6 border-l-2 pt-3 pl-4">
							<BulletEditor
								personaId={personaId}
								workHistoryId={entry.id}
								initialBullets={entry.bullets}
								onBulletsChange={(bullets) =>
									handleBulletsChange(entry.id, bullets)
								}
							/>
						</div>
					)}
				</div>
			)}
			back={back}
			next={next}
			nextDisabled={
				crud.entries.length === 0 ||
				crud.entries.some((e) => e.bullets.length === 0)
			}
			beforeNavigation={bulletHint}
		/>
	);
}
