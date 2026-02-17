"use client";

/**
 * Certification step for onboarding wizard (Step 6).
 *
 * REQ-012 §6.3.6: Skippable step. Certifications editor with
 * "Does not expire" toggle, CRUD, and reordering.
 * Skip button: "Skip — No certifications".
 */

import { useCrudStep } from "@/hooks/use-crud-step";
import { toFormValues, toRequestBody } from "@/lib/certification-helpers";
import { useOnboarding } from "@/lib/onboarding-provider";
import type { Certification } from "@/types/persona";

import { CertificationCard } from "./certification-card";
import { CertificationForm } from "./certification-form";
import type { CertificationFormData } from "./certification-form";
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
