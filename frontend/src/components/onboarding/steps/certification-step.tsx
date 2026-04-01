"use client";

/**
 * @fileoverview Certification step for onboarding wizard (Step 6).
 *
 * Layer: component
 * Feature: persona
 *
 * REQ-012 §6.3.6: Skippable step. Certifications editor with
 * "Does not expire" toggle, CRUD, and reordering.
 * Skip button: "Skip — No certifications".
 *
 * Coordinates with:
 * - hooks/use-crud-step.ts: useCrudStep for CRUD state management
 * - lib/certification-helpers.ts: toFormValues, toRequestBody, CertificationFormData for form data conversion
 * - lib/onboarding-provider.tsx: useOnboarding for wizard navigation
 * - types/persona.ts: Certification type for entity data
 * - onboarding/steps/certification-card.tsx: CertificationCard for entry display
 * - onboarding/steps/certification-form.tsx: CertificationForm for add/edit form
 * - onboarding/steps/crud-step-layout.tsx: CrudStepLayout for shared CRUD layout
 *
 * Called by / Used by:
 * - app/onboarding/page.tsx: onboarding step 6 component
 */

import { useCrudStep } from "@/hooks/use-crud-step";
import {
	toFormValues,
	toRequestBody,
	type CertificationFormData,
} from "@/lib/certification-helpers";
import { useOnboarding } from "@/lib/onboarding-provider";
import type { Certification } from "@/types/persona";

import { CertificationCard } from "./certification-card";
import { CertificationForm } from "./certification-form";
import { CrudStepLayout } from "./crud-step-layout";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Onboarding Step 6: Certifications.
 *
 * Renders a list of certification cards with add/edit/delete and
 * drag-and-drop reordering. 0 entries is valid (step is skippable).
 */
export function CertificationStep() {
	const { personaId, next, back, skip } = useOnboarding();

	const crud = useCrudStep<Certification, CertificationFormData>({
		personaId,
		collection: "certifications",
		toFormValues,
		toRequestBody,
		hasDeleteError: true,
	});

	return (
		<CrudStepLayout
			crud={crud}
			title="Certifications"
			emptySubtitle="Do you have any professional certifications?"
			listSubtitle="Your certifications. Add, edit, or reorder as needed."
			loadingTestId="loading-certifications"
			loadingText="Loading your certifications..."
			emptyMessage="No certifications yet."
			listLabel="Certification entries"
			addLabel="Add certification"
			deleteTitle="Delete certification"
			getDeleteDescription={(target, error) =>
				error
					? `Failed to delete "${target?.certification_name ?? ""}". ${error}`
					: `Are you sure you want to delete "${target?.certification_name ?? ""}"? This cannot be undone.`
			}
			toFormValues={toFormValues}
			renderForm={(props) => <CertificationForm {...props} />}
			renderCard={(entry, dragHandle) => (
				<CertificationCard
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
