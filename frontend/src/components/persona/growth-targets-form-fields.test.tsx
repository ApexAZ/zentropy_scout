/**
 * Tests for the GrowthTargetsFormFields shared component.
 *
 * REQ-012 §6.3.9 / §7.2.8: Verifies field rendering and error display
 * for the shared form fields used by both the onboarding step and
 * post-onboarding editor.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { useForm } from "react-hook-form";

import { Form } from "@/components/ui/form";
import {
	GROWTH_TARGETS_DEFAULT_VALUES,
	STRETCH_DESCRIPTIONS,
	growthTargetsSchema,
} from "@/lib/growth-targets-helpers";
import type { GrowthTargetsFormData } from "@/lib/growth-targets-helpers";

import {
	GrowthTargetsFormFields,
	type GrowthTargetsFormFieldsProps,
} from "./growth-targets-form-fields";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STRETCH_OPTIONS = ["Low", "Medium", "High"] as const;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function TestHarness({
	defaultValues = GROWTH_TARGETS_DEFAULT_VALUES,
	submitError = null,
}: {
	defaultValues?: GrowthTargetsFormData;
	submitError?: GrowthTargetsFormFieldsProps["submitError"];
}) {
	const form = useForm<GrowthTargetsFormData>({
		resolver: zodResolver(growthTargetsSchema),
		defaultValues,
		mode: "onTouched",
	});

	return (
		<Form {...form}>
			<form>
				<GrowthTargetsFormFields form={form} submitError={submitError} />
			</form>
		</Form>
	);
}

function renderFields(
	overrides: {
		defaultValues?: Partial<GrowthTargetsFormData>;
		submitError?: string | null;
	} = {},
) {
	const user = userEvent.setup();
	const { defaultValues: dv, ...rest } = overrides;
	render(
		<TestHarness
			defaultValues={{ ...GROWTH_TARGETS_DEFAULT_VALUES, ...dv }}
			{...rest}
		/>,
	);
	return user;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("GrowthTargetsFormFields", () => {
	afterEach(() => {
		cleanup();
	});

	// -----------------------------------------------------------------------
	// Field rendering
	// -----------------------------------------------------------------------

	describe("field rendering", () => {
		it("renders Target Roles tag field", () => {
			renderFields();

			expect(screen.getByLabelText(/target roles/i)).toBeInTheDocument();
		});

		it("renders Target Skills tag field", () => {
			renderFields();

			expect(screen.getByLabelText(/target skills/i)).toBeInTheDocument();
		});

		it("renders Stretch Appetite label", () => {
			renderFields();

			expect(screen.getByText("Stretch Appetite")).toBeInTheDocument();
		});

		it("renders all 3 stretch appetite radio options", () => {
			renderFields();

			const group = screen.getByRole("radiogroup", {
				name: /stretch appetite/i,
			});
			for (const option of STRETCH_OPTIONS) {
				expect(
					group.querySelector(`input[value="${option}"]`),
				).toBeInTheDocument();
			}
		});

		it("renders stretch appetite descriptions", () => {
			renderFields();

			for (const option of STRETCH_OPTIONS) {
				expect(
					screen.getByText(STRETCH_DESCRIPTIONS[option]),
				).toBeInTheDocument();
			}
		});

		it("defaults to Medium stretch appetite", () => {
			renderFields();

			expect(screen.getByRole("radio", { name: /medium/i })).toBeChecked();
		});
	});

	// -----------------------------------------------------------------------
	// Stretch appetite interaction
	// -----------------------------------------------------------------------

	describe("stretch appetite interaction", () => {
		it("changes selection when clicking a different option", async () => {
			const user = renderFields();

			expect(screen.getByRole("radio", { name: /medium/i })).toBeChecked();

			await user.click(screen.getByRole("radio", { name: /high/i }));

			expect(screen.getByRole("radio", { name: /high/i })).toBeChecked();
			expect(screen.getByRole("radio", { name: /medium/i })).not.toBeChecked();
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
