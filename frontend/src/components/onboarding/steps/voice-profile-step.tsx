"use client";

/**
 * Voice profile step for onboarding wizard (Step 10).
 *
 * REQ-012 §6.3.10: Agent-derived voice profile review card with
 * per-field inline editing. Two modes:
 * - Review: read-only card with "Looks good!" and "Let me edit"
 * - Edit: form with text inputs + tag inputs for all voice fields
 *
 * Falls back to edit mode when no profile exists (GUI-first path).
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Loader2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { FormErrorSummary } from "@/components/form/form-error-summary";
import { FormInputField } from "@/components/form/form-input-field";
import { FormTagField } from "@/components/form/form-tag-field";
import { Button } from "@/components/ui/button";
import {
	Form,
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Textarea } from "@/components/ui/textarea";
import { apiGet, apiPatch } from "@/lib/api-client";
import { toFriendlyError } from "@/lib/form-errors";
import { useOnboarding } from "@/lib/onboarding-provider";
import {
	VOICE_PROFILE_DEFAULT_VALUES,
	toFormValues,
	toRequestBody,
	voiceProfileSchema,
} from "@/lib/voice-profile-helpers";
import type { VoiceProfileFormData } from "@/lib/voice-profile-helpers";
import type { ApiResponse } from "@/types/api";
import type { VoiceProfile } from "@/types/persona";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ViewMode = "review" | "edit";

/** Subset of VoiceProfile fields used to determine if data exists. */
interface ProfileData {
	tone?: string;
	sentence_style?: string;
	vocabulary_level?: string;
	personality_markers?: string | null;
	sample_phrases?: string[];
	things_to_avoid?: string[];
	writing_sample_text?: string | null;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** CSS classes shared by all field labels in the review card. */
const FIELD_LABEL_CLASSES =
	"text-muted-foreground text-xs font-medium uppercase tracking-wider";

/** Display labels for voice profile fields in the review card. */
const FIELD_LABELS: readonly { key: keyof ProfileData; label: string }[] = [
	{ key: "tone", label: "Tone" },
	{ key: "sentence_style", label: "Style" },
	{ key: "vocabulary_level", label: "Vocabulary" },
	{ key: "personality_markers", label: "Personality" },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Check if the fetched profile has meaningful data. */
function hasProfileData(data: ProfileData): boolean {
	return Boolean(data.tone);
}

// ---------------------------------------------------------------------------
// Review card sub-component
// ---------------------------------------------------------------------------

function ReviewCard({
	profile,
	onAccept,
	onEdit,
}: {
	profile: ProfileData;
	onAccept: () => void;
	onEdit: () => void;
}) {
	return (
		<div data-testid="voice-profile-review" className="space-y-4">
			<p className="text-muted-foreground text-sm">
				Based on your conversation, here&apos;s how we&apos;d describe your
				writing voice:
			</p>

			<div className="bg-card space-y-3 rounded-lg border p-4">
				{FIELD_LABELS.map(({ key, label }) => {
					const value = profile[key] as string | null;
					if (!value) return null;
					return (
						<div key={key} data-field={key}>
							<dt className={FIELD_LABEL_CLASSES}>{label}</dt>
							<dd className="mt-0.5">{value}</dd>
						</div>
					);
				})}

				{profile.sample_phrases && profile.sample_phrases.length > 0 && (
					<div data-field="sample_phrases">
						<dt className={FIELD_LABEL_CLASSES}>Sample Phrases</dt>
						<dd className="mt-1 flex flex-wrap gap-1.5">
							{profile.sample_phrases.map((phrase) => (
								<span
									key={phrase}
									className="bg-secondary text-secondary-foreground rounded-md px-2 py-0.5 text-xs font-medium"
								>
									{phrase}
								</span>
							))}
						</dd>
					</div>
				)}

				{profile.things_to_avoid && profile.things_to_avoid.length > 0 && (
					<div data-field="things_to_avoid">
						<dt className={FIELD_LABEL_CLASSES}>Avoid</dt>
						<dd className="mt-1 flex flex-wrap gap-1.5">
							{profile.things_to_avoid.map((word) => (
								<span
									key={word}
									className="bg-destructive/10 text-destructive rounded-md px-2 py-0.5 text-xs font-medium"
								>
									{word}
								</span>
							))}
						</dd>
					</div>
				)}
			</div>

			<div className="flex items-center justify-center gap-3 pt-2">
				<Button type="button" variant="outline" onClick={onEdit}>
					Let me edit
				</Button>
				<Button type="button" onClick={onAccept}>
					Looks good!
				</Button>
			</div>
		</div>
	);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Onboarding Step 10: Voice Profile.
 *
 * If an agent-derived profile exists, shows a review card. Otherwise,
 * shows an editable form. User can toggle to edit mode from review.
 */
export function VoiceProfileStep() {
	const { personaId, next, back } = useOnboarding();

	const [isLoading, setIsLoading] = useState(!!personaId);
	const [viewMode, setViewMode] = useState<ViewMode>("edit");
	const [profileData, setProfileData] = useState<ProfileData | null>(null);
	const [submitError, setSubmitError] = useState<string | null>(null);
	const [isSubmitting, setIsSubmitting] = useState(false);

	const form = useForm<VoiceProfileFormData>({
		resolver: zodResolver(voiceProfileSchema),
		defaultValues: VOICE_PROFILE_DEFAULT_VALUES,
		mode: "onTouched",
	});

	const { reset } = form;

	// -----------------------------------------------------------------------
	// Fetch voice profile on mount
	// -----------------------------------------------------------------------

	useEffect(() => {
		if (!personaId) return;

		let cancelled = false;

		apiGet<ApiResponse<VoiceProfile>>(`/personas/${personaId}/voice-profile`)
			.then((res) => {
				if (cancelled) return;
				const profile = res.data;
				if (hasProfileData(profile)) {
					setProfileData(profile);
					setViewMode("review");
					reset({ ...VOICE_PROFILE_DEFAULT_VALUES, ...toFormValues(profile) });
				}
			})
			.catch(() => {
				// Fetch failed — start in edit mode
			})
			.finally(() => {
				if (!cancelled) setIsLoading(false);
			});

		return () => {
			cancelled = true;
		};
	}, [personaId, reset]);

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	const handleAccept = useCallback(() => {
		next();
	}, [next]);

	const handleSwitchToEdit = useCallback(() => {
		setViewMode("edit");
	}, []);

	const onSubmit = useCallback(
		async (data: VoiceProfileFormData) => {
			if (!personaId) return;

			setSubmitError(null);
			setIsSubmitting(true);

			try {
				await apiPatch(
					`/personas/${personaId}/voice-profile`,
					toRequestBody(data),
				);
				next();
			} catch (err) {
				setIsSubmitting(false);
				setSubmitError(toFriendlyError(err));
			}
		},
		[personaId, next],
	);

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	if (isLoading) {
		return (
			<div
				className="flex flex-1 flex-col items-center justify-center"
				data-testid="loading-voice-profile"
			>
				<Loader2 className="text-primary h-8 w-8 animate-spin" />
				<p className="text-muted-foreground mt-3">
					Loading your voice profile...
				</p>
			</div>
		);
	}

	return (
		<div className="flex flex-1 flex-col gap-6">
			<div className="text-center">
				<h2 className="text-lg font-semibold">Voice Profile</h2>
				<p className="text-muted-foreground mt-1">
					{viewMode === "review"
						? "Review your writing voice profile below."
						: "Describe your writing voice so generated content sounds like you."}
				</p>
			</div>

			{/* Review mode */}
			{viewMode === "review" && profileData && (
				<ReviewCard
					profile={profileData}
					onAccept={handleAccept}
					onEdit={handleSwitchToEdit}
				/>
			)}

			{/* Edit mode */}
			{viewMode === "edit" && (
				<Form {...form}>
					<form
						id="voice-profile-form"
						onSubmit={form.handleSubmit(onSubmit)}
						className="space-y-6"
						data-testid="voice-profile-form"
						noValidate
					>
						<FormInputField
							control={form.control}
							name="tone"
							label="Tone"
							placeholder='e.g., "Direct, confident, avoids buzzwords"'
						/>

						<FormInputField
							control={form.control}
							name="sentence_style"
							label="Style"
							placeholder='e.g., "Short sentences, active voice"'
						/>

						<FormInputField
							control={form.control}
							name="vocabulary_level"
							label="Vocabulary"
							placeholder='e.g., "Technical when relevant, plain otherwise"'
						/>

						<FormInputField
							control={form.control}
							name="personality_markers"
							label="Personality"
							placeholder='e.g., "Occasional dry humor" (optional)'
						/>

						<FormTagField
							control={form.control}
							name="sample_phrases"
							label="Sample Phrases"
							placeholder="e.g., I led..., The result was..."
							description="Phrases that sound like you"
							maxItems={20}
						/>

						<FormTagField
							control={form.control}
							name="things_to_avoid"
							label="Things to Avoid"
							placeholder="e.g., Passionate, Synergy"
							description="Words or phrases you never use"
							maxItems={20}
						/>

						<FormField
							control={form.control}
							name="writing_sample_text"
							render={({ field }) => (
								<FormItem>
									<FormLabel>Writing Sample (optional)</FormLabel>
									<FormControl>
										<Textarea
											placeholder="Paste a writing sample for better voice matching..."
											className="min-h-[100px] resize-y"
											{...field}
										/>
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>

						<FormErrorSummary className="mt-2" />

						{submitError && (
							<div
								role="alert"
								className="text-destructive text-sm font-medium"
								data-testid="submit-error"
							>
								{submitError}
							</div>
						)}
					</form>
				</Form>
			)}

			{/* Navigation */}
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
				{viewMode === "edit" && (
					<Button
						type="submit"
						form="voice-profile-form"
						disabled={isSubmitting}
						data-testid="submit-button"
					>
						{isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
						{isSubmitting ? "Saving..." : "Save & Continue"}
					</Button>
				)}
			</div>
		</div>
	);
}
