"use client";

/**
 * @fileoverview Skills step for onboarding wizard (Step 5).
 *
 * Layer: component
 * Feature: persona
 *
 * REQ-012 §6.3.5: Not skippable. Skills editor with proficiency
 * selector, conditional category dropdown, CRUD, and reordering.
 * All 6 fields required per skill entry.
 *
 * Coordinates with:
 * - hooks/use-crud-step.ts: useCrudStep for CRUD state management
 * - lib/onboarding-provider.tsx: useOnboarding for wizard navigation
 * - lib/skills-helpers.ts: toFormValues, toRequestBody, SkillFormData for form data conversion
 * - types/persona.ts: Skill type for entity data
 * - onboarding/steps/crud-step-layout.tsx: CrudStepLayout for shared CRUD layout
 * - onboarding/steps/skills-card.tsx: SkillCard for entry display
 * - onboarding/steps/skills-form.tsx: SkillForm for add/edit form
 *
 * Called by / Used by:
 * - app/onboarding/page.tsx: onboarding step 5 component
 */

import { useCrudStep } from "@/hooks/use-crud-step";
import { useOnboarding } from "@/lib/onboarding-provider";
import {
	toFormValues,
	toRequestBody,
	type SkillFormData,
} from "@/lib/skills-helpers";
import type { Skill } from "@/types/persona";

import { CrudStepLayout } from "./crud-step-layout";
import { SkillCard } from "./skills-card";
import { SkillForm } from "./skills-form";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Onboarding Step 5: Skills.
 *
 * Renders a list of skill cards with add/edit/delete and
 * drag-and-drop reordering. Not skippable — all 6 fields required.
 */
export function SkillsStep() {
	const { personaId, next, back } = useOnboarding();

	const crud = useCrudStep<Skill, SkillFormData>({
		personaId,
		collection: "skills",
		toFormValues,
		toRequestBody,
		hasDeleteError: true,
	});

	return (
		<CrudStepLayout
			crud={crud}
			title="Skills"
			emptySubtitle="Add your technical and professional skills."
			listSubtitle="Your skills. Add, edit, or reorder as needed."
			loadingTestId="loading-skills"
			loadingText="Loading your skills..."
			emptyMessage="No skills yet."
			listLabel="Skill entries"
			addLabel="Add skill"
			deleteTitle="Delete skill"
			getDeleteDescription={(target, error) =>
				error
					? `Failed to delete "${target?.skill_name ?? ""}". ${error}`
					: `Are you sure you want to delete "${target?.skill_name ?? ""}"? This cannot be undone.`
			}
			toFormValues={toFormValues}
			renderForm={(props) => <SkillForm {...props} />}
			renderCard={(entry, dragHandle) => (
				<SkillCard
					entry={entry}
					onEdit={crud.handleEdit}
					onDelete={crud.handleDeleteRequest}
					dragHandle={dragHandle}
				/>
			)}
			back={back}
			next={next}
		/>
	);
}
