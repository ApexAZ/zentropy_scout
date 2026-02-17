"use client";

/**
 * Education step for onboarding wizard (Step 4).
 *
 * REQ-012 §6.3.4: Skippable step. Display education entries in editable
 * cards with add/edit/delete and ordering. 0 entries is valid (skip).
 */

import { useCrudStep } from "@/hooks/use-crud-step";
import { toFormValues, toRequestBody } from "@/lib/education-helpers";
import { useOnboarding } from "@/lib/onboarding-provider";
import type { Education } from "@/types/persona";

import { CrudStepLayout } from "./crud-step-layout";
import { EducationCard } from "./education-card";
import { EducationForm } from "./education-form";
import type { EducationFormData } from "./education-form";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Onboarding Step 4: Education.
 *
 * Renders a list of education cards with add/edit/delete and
 * drag-and-drop reordering. 0 entries is valid (step is skippable).
 */
export function EducationStep() {
	const { personaId, next, back, skip } = useOnboarding();

	const crud = useCrudStep<Education, EducationFormData>({
		personaId,
		collection: "education",
		toFormValues,
		toRequestBody,
	});

	return (
		<CrudStepLayout
			crud={crud}
			title="Education"
			emptySubtitle="Do you have any formal education to include? (This is optional)"
			listSubtitle="Your education entries. Add, edit, or reorder as needed."
			loadingTestId="loading-education"
			loadingText="Loading your education..."
			emptyMessage="No education entries yet."
			listLabel="Education entries"
			addLabel="Add education"
			deleteTitle="Delete education entry"
			getDeleteDescription={(target) =>
				`Are you sure you want to delete "${target?.degree ?? ""} in ${target?.field_of_study ?? ""}" at ${target?.institution ?? ""}? This cannot be undone.`
			}
			toFormValues={toFormValues}
			renderForm={(props) => <EducationForm {...props} />}
			renderCard={(entry, dragHandle) => (
				<EducationCard
					entry={entry}
					onEdit={crud.handleEdit}
					onDelete={crud.handleDeleteRequest}
					dragHandle={dragHandle}
				/>
			)}
			back={back}
			next={next}
			skip={skip}
		/>
	);
}
