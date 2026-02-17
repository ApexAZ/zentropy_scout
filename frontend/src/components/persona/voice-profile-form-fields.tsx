/**
 * Shared form fields for the voice profile editor and onboarding step.
 *
 * REQ-012 §6.3.10 / §7.2.6: Text inputs (tone, style, vocabulary,
 * personality), tag inputs (sample phrases, things to avoid), and
 * optional textarea (writing sample) — identical fields used by both
 * the onboarding wizard step and the post-onboarding editor.
 */

import type { UseFormReturn } from "react-hook-form";

import { FormErrorSummary } from "@/components/form/form-error-summary";
import { FormInputField } from "@/components/form/form-input-field";
import { FormTagField } from "@/components/form/form-tag-field";
import {
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Textarea } from "@/components/ui/textarea";
import type { VoiceProfileFormData } from "@/lib/voice-profile-helpers";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface VoiceProfileFormFieldsProps {
	/** React Hook Form instance for the voice profile form. */
	form: UseFormReturn<VoiceProfileFormData>;
	/** API submission error message, if any. */
	submitError: string | null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Renders all voice profile form fields (4 text inputs, 2 tag inputs,
 * 1 textarea) plus the error summary and submit error alert. Consumers
 * provide their own `<form>` wrapper, submit button, and navigation.
 */
function VoiceProfileFormFields({
	form,
	submitError,
}: Readonly<VoiceProfileFormFieldsProps>) {
	return (
		<>
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
		</>
	);
}

export { VoiceProfileFormFields };
export type { VoiceProfileFormFieldsProps };
