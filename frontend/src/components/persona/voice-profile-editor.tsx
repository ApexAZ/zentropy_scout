"use client";

/**
 * Post-onboarding voice profile editor (§6.9).
 *
 * REQ-012 §7.2.6: Single form with text inputs, tag inputs
 * (sample_phrases, things_to_avoid), and optional textarea.
 * Fetches via useQuery, PATCHes on save, invalidates cache.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";
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
import { queryKeys } from "@/lib/query-keys";
import {
	VOICE_PROFILE_DEFAULT_VALUES,
	toFormValues,
	toRequestBody,
	voiceProfileSchema,
} from "@/lib/voice-profile-helpers";
import type { VoiceProfileFormData } from "@/lib/voice-profile-helpers";
import type { ApiResponse } from "@/types/api";
import type { Persona, VoiceProfile } from "@/types/persona";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Post-onboarding editor for voice profile fields.
 *
 * Receives the current persona as a prop and fetches the voice profile
 * via useQuery. Pre-fills the form and saves changes via PATCH.
 */
export function VoiceProfileEditor({
	persona,
}: Readonly<{ persona: Persona }>) {
	const personaId = persona.id;
	const queryClient = useQueryClient();
	const voiceProfileQueryKey = queryKeys.voiceProfile(personaId);

	// -----------------------------------------------------------------------
	// Data fetching
	// -----------------------------------------------------------------------

	const { data: profileData, isLoading } = useQuery({
		queryKey: voiceProfileQueryKey,
		queryFn: () =>
			apiGet<ApiResponse<VoiceProfile>>(`/personas/${personaId}/voice-profile`),
	});

	// -----------------------------------------------------------------------
	// Form
	// -----------------------------------------------------------------------

	const form = useForm<VoiceProfileFormData>({
		resolver: zodResolver(voiceProfileSchema),
		defaultValues: VOICE_PROFILE_DEFAULT_VALUES,
		mode: "onTouched",
	});

	const { reset } = form;

	const [submitError, setSubmitError] = useState<string | null>(null);
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [saveSuccess, setSaveSuccess] = useState(false);

	// Pre-fill form when data arrives
	useEffect(() => {
		if (profileData?.data) {
			reset({
				...VOICE_PROFILE_DEFAULT_VALUES,
				...toFormValues(profileData.data),
			});
		}
	}, [profileData, reset]);

	// -----------------------------------------------------------------------
	// Submit handler
	// -----------------------------------------------------------------------

	const onSubmit = useCallback(
		async (data: VoiceProfileFormData) => {
			setSubmitError(null);
			setSaveSuccess(false);
			setIsSubmitting(true);

			try {
				await apiPatch(
					`/personas/${personaId}/voice-profile`,
					toRequestBody(data),
				);

				await queryClient.invalidateQueries({
					queryKey: voiceProfileQueryKey,
				});
				setSaveSuccess(true);
			} catch (err) {
				setSubmitError(toFriendlyError(err));
			} finally {
				setIsSubmitting(false);
			}
		},
		[personaId, queryClient, voiceProfileQueryKey],
	);

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	if (isLoading) {
		return (
			<div
				className="flex flex-1 flex-col items-center justify-center"
				data-testid="loading-voice-profile-editor"
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
			<div>
				<h2 className="text-lg font-semibold">Voice Profile</h2>
				<p className="text-muted-foreground mt-1">
					Describe your writing voice so generated content sounds like you.
				</p>
			</div>

			<Form {...form}>
				<form
					onSubmit={form.handleSubmit(onSubmit)}
					className="space-y-6"
					data-testid="voice-profile-editor-form"
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

					{saveSuccess && (
						<div
							className="text-sm font-medium text-green-600"
							data-testid="save-success"
						>
							Voice profile saved.
						</div>
					)}

					<div className="flex items-center justify-between pt-4">
						<Link
							href="/persona"
							className="text-muted-foreground hover:text-foreground inline-flex items-center text-sm"
						>
							<ArrowLeft className="mr-2 h-4 w-4" />
							Back to Profile
						</Link>
						<Button type="submit" disabled={isSubmitting}>
							{isSubmitting && (
								<Loader2 className="mr-2 h-4 w-4 animate-spin" />
							)}
							{isSubmitting ? "Saving..." : "Save"}
						</Button>
					</div>
				</form>
			</Form>
		</div>
	);
}
