/**
 * Tests for the VoiceProfileFormFields shared component.
 *
 * REQ-012 §6.3.10 / §7.2.6: Verifies field rendering and error display
 * for the shared form fields used by both the onboarding step and
 * post-onboarding editor.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { useForm } from "react-hook-form";

import { Form } from "@/components/ui/form";
import {
	VOICE_PROFILE_DEFAULT_VALUES,
	voiceProfileSchema,
} from "@/lib/voice-profile-helpers";
import type { VoiceProfileFormData } from "@/lib/voice-profile-helpers";

import {
	VoiceProfileFormFields,
	type VoiceProfileFormFieldsProps,
} from "./voice-profile-form-fields";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function TestHarness({
	defaultValues = VOICE_PROFILE_DEFAULT_VALUES,
	submitError = null,
}: {
	defaultValues?: VoiceProfileFormData;
	submitError?: VoiceProfileFormFieldsProps["submitError"];
}) {
	const form = useForm<VoiceProfileFormData>({
		resolver: zodResolver(voiceProfileSchema),
		defaultValues,
		mode: "onTouched",
	});

	return (
		<Form {...form}>
			<form>
				<VoiceProfileFormFields form={form} submitError={submitError} />
			</form>
		</Form>
	);
}

function renderFields(
	overrides: {
		defaultValues?: Partial<VoiceProfileFormData>;
		submitError?: string | null;
	} = {},
) {
	const { defaultValues: dv, ...rest } = overrides;
	render(
		<TestHarness
			defaultValues={{ ...VOICE_PROFILE_DEFAULT_VALUES, ...dv }}
			{...rest}
		/>,
	);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("VoiceProfileFormFields", () => {
	afterEach(() => {
		cleanup();
	});

	// -----------------------------------------------------------------------
	// Field rendering
	// -----------------------------------------------------------------------

	describe("field rendering", () => {
		it("renders Tone input", () => {
			renderFields();

			expect(screen.getByLabelText(/tone/i)).toBeInTheDocument();
		});

		it("renders Style input", () => {
			renderFields();

			expect(screen.getByLabelText(/style/i)).toBeInTheDocument();
		});

		it("renders Vocabulary input", () => {
			renderFields();

			expect(screen.getByLabelText(/vocabulary/i)).toBeInTheDocument();
		});

		it("renders Personality input", () => {
			renderFields();

			expect(screen.getByLabelText(/personality/i)).toBeInTheDocument();
		});

		it("renders Sample Phrases tag field", () => {
			renderFields();

			expect(screen.getByLabelText(/sample phrases/i)).toBeInTheDocument();
		});

		it("renders Things to Avoid tag field", () => {
			renderFields();

			expect(screen.getByLabelText(/things to avoid/i)).toBeInTheDocument();
		});

		it("renders Writing Sample textarea", () => {
			renderFields();

			expect(screen.getByLabelText(/writing sample/i)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Submit error display
	// -----------------------------------------------------------------------

	describe("submit error", () => {
		it("shows submit error when provided", () => {
			renderFields({ submitError: "Something went wrong." });

			const alert = screen.getByTestId("submit-error");
			expect(alert).toBeInTheDocument();
			expect(alert).toHaveTextContent("Something went wrong.");
		});

		it("hides submit error when null", () => {
			renderFields({ submitError: null });

			expect(screen.queryByTestId("submit-error")).not.toBeInTheDocument();
		});
	});
});
