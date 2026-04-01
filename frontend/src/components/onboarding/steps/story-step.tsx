"use client";

/**
 * @fileoverview Achievement Stories step for onboarding wizard (Step 7).
 *
 * Layer: component
 * Feature: persona
 *
 * REQ-012 §6.3.7: Conversational capture of Context/Action/Outcome
 * structured stories. Minimum 3 stories required before proceeding.
 * Review cards with edit/delete and reordering.
 *
 * Coordinates with:
 * - hooks/use-crud-step.ts: useCrudStep for CRUD state management
 * - lib/achievement-stories-helpers.ts: toFormValues, toRequestBody, StoryFormData for form data conversion
 * - lib/onboarding-provider.tsx: useOnboarding for wizard navigation
 * - types/persona.ts: AchievementStory, Skill types for entity data
 * - onboarding/steps/crud-step-layout.tsx: CrudStepLayout for shared CRUD layout
 * - onboarding/steps/story-card.tsx: StoryCard for entry display
 * - onboarding/steps/story-form.tsx: StoryForm for add/edit form
 *
 * Called by / Used by:
 * - app/onboarding/page.tsx: onboarding step 7 component
 */

import { useState } from "react";

import { useCrudStep } from "@/hooks/use-crud-step";
import {
	toFormValues,
	toRequestBody,
	type StoryFormData,
} from "@/lib/achievement-stories-helpers";
import { useOnboarding } from "@/lib/onboarding-provider";
import type { AchievementStory, Skill } from "@/types/persona";

import { CrudStepLayout } from "./crud-step-layout";
import { StoryCard } from "./story-card";
import { StoryForm } from "./story-form";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MIN_STORIES = 3;

function storyCounterText(count: number): string {
	if (count < MIN_STORIES) {
		return `${count} of 3\u20135 stories \u00B7 minimum ${MIN_STORIES} required`;
	}
	return `${count} of 3\u20135 stories`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Onboarding Step 7: Achievement Stories.
 *
 * Renders a list of story review cards with add/edit/delete and
 * drag-and-drop reordering. Minimum 3 stories required before the
 * user can proceed.
 */
export function StoryStep() {
	const { personaId, next, back } = useOnboarding();

	const [skills, setSkills] = useState<Skill[]>([]);

	const crud = useCrudStep<AchievementStory, StoryFormData>({
		personaId,
		collection: "achievement-stories",
		toFormValues,
		toRequestBody,
		hasDeleteError: true,
		secondaryFetch: {
			collection: "skills",
			onData: (data) => setSkills(data as Skill[]),
		},
	});

	return (
		<CrudStepLayout
			crud={crud}
			title="Achievement Stories"
			emptySubtitle="Share stories of times you made a real impact."
			listSubtitle={storyCounterText}
			loadingTestId="loading-stories"
			loadingText="Loading your achievement stories..."
			emptyMessage="No stories yet."
			listLabel="Achievement story entries"
			addLabel="Add story"
			deleteTitle="Delete story"
			getDeleteDescription={(target, error) =>
				error
					? `Failed to delete "${target?.title ?? ""}". ${error}`
					: `Are you sure you want to delete "${target?.title ?? ""}"? This cannot be undone.`
			}
			toFormValues={toFormValues}
			renderForm={(props) => <StoryForm {...props} skills={skills} />}
			renderCard={(entry, dragHandle) => (
				<StoryCard
					entry={entry}
					skills={skills}
					onEdit={crud.handleEdit}
					onDelete={crud.handleDeleteRequest}
					dragHandle={dragHandle}
				/>
			)}
			back={back}
			next={next}
			nextDisabled={crud.entries.length < MIN_STORIES}
		/>
	);
}
