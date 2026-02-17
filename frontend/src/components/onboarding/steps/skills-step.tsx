"use client";

/**
 * Skills step for onboarding wizard (Step 5).
 *
 * REQ-012 §6.3.5: Not skippable. Skills editor with proficiency
 * selector, conditional category dropdown, CRUD, and reordering.
 * All 6 fields required per skill entry.
 */

import { useCrudStep } from "@/hooks/use-crud-step";
import { useOnboarding } from "@/lib/onboarding-provider";
import { toFormValues, toRequestBody } from "@/lib/skills-helpers";
import type { Skill } from "@/types/persona";

import { CrudStepLayout } from "./crud-step-layout";
import { SkillCard } from "./skills-card";
import { SkillForm } from "./skills-form";
import type { SkillFormData } from "./skills-form";

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
