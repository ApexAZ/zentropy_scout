/**
 * Tests for the NonNegotiablesFormFields shared component.
 *
 * REQ-012 §6.3.8 / §7.2.7: Verifies field rendering, conditional
 * visibility, and error display for the shared form fields used by
 * both the onboarding step and post-onboarding editor.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { useForm } from "react-hook-form";

import { Form } from "@/components/ui/form";
import {
	NON_NEGOTIABLES_DEFAULT_VALUES,
	nonNegotiablesSchema,
} from "@/lib/non-negotiables-helpers";
import type { NonNegotiablesFormData } from "@/lib/non-negotiables-helpers";

import {
	NonNegotiablesFormFields,
	type NonNegotiablesFormFieldsProps,
} from "./non-negotiables-form-fields";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const REMOTE_OPTIONS = [
	"Remote Only",
	"Hybrid OK",
	"Onsite OK",
	"No Preference",
] as const;

const COMPANY_SIZE_OPTIONS = [
	"Startup",
	"Mid-size",
	"Enterprise",
	"No Preference",
] as const;

const MAX_TRAVEL_OPTIONS = ["None", "<25%", "<50%", "Any"] as const;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Wrapper that provides the React Hook Form context required by FormField. */
function TestHarness({
	defaultValues = NON_NEGOTIABLES_DEFAULT_VALUES,
	submitError = null,
}: {
	defaultValues?: NonNegotiablesFormData;
	submitError?: NonNegotiablesFormFieldsProps["submitError"];
}) {
	const form = useForm<NonNegotiablesFormData>({
		resolver: zodResolver(nonNegotiablesSchema),
		defaultValues,
		mode: "onTouched",
	});

	return (
		<Form {...form}>
			<form>
				<NonNegotiablesFormFields form={form} submitError={submitError} />
			</form>
		</Form>
	);
}

function renderFields(
	overrides: {
		defaultValues?: Partial<NonNegotiablesFormData>;
		submitError?: string | null;
	} = {},
) {
	const user = userEvent.setup();
	const { defaultValues: dv, ...rest } = overrides;
	render(
		<TestHarness
			defaultValues={{ ...NON_NEGOTIABLES_DEFAULT_VALUES, ...dv }}
			{...rest}
		/>,
	);
	return user;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("NonNegotiablesFormFields", () => {
	afterEach(() => {
		cleanup();
	});

	// -----------------------------------------------------------------------
	// Fieldset rendering
	// -----------------------------------------------------------------------

	describe("fieldset rendering", () => {
		it("renders Location Preferences section", () => {
			renderFields();

			expect(screen.getByText("Location Preferences")).toBeInTheDocument();
		});

		it("renders Relocation section", () => {
			renderFields();

			expect(screen.getByText("Relocation")).toBeInTheDocument();
		});

		it("renders Compensation section", () => {
			renderFields();

			expect(screen.getByText("Compensation")).toBeInTheDocument();
		});

		it("renders Other Filters section", () => {
			renderFields();

			expect(screen.getByText("Other Filters")).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Radio groups
	// -----------------------------------------------------------------------

	describe("radio groups", () => {
		it("renders all 4 remote preference options", () => {
			renderFields();

			const group = screen.getByRole("radiogroup", {
				name: /remote preference/i,
			});
			for (const option of REMOTE_OPTIONS) {
				expect(
					group.querySelector(`input[value="${option}"]`),
				).toBeInTheDocument();
			}
		});

		it("renders all 4 company size options", () => {
			renderFields();

			const group = screen.getByRole("radiogroup", {
				name: /company size/i,
			});
			for (const option of COMPANY_SIZE_OPTIONS) {
				expect(
					group.querySelector(`input[value="${option}"]`),
				).toBeInTheDocument();
			}
		});

		it("renders all 4 max travel options", () => {
			renderFields();

			const group = screen.getByRole("radiogroup", {
				name: /max travel/i,
			});
			for (const option of MAX_TRAVEL_OPTIONS) {
				expect(
					group.querySelector(`input[value="${option}"]`),
				).toBeInTheDocument();
			}
		});
	});

	// -----------------------------------------------------------------------
	// Conditional visibility — commute fields
	// -----------------------------------------------------------------------

	describe("commute field visibility", () => {
		it("shows commute fields when remote preference is not Remote Only", () => {
			renderFields({ defaultValues: { remote_preference: "Hybrid OK" } });

			expect(screen.getByLabelText(/commutable cities/i)).toBeInTheDocument();
			expect(screen.getByLabelText(/max commute/i)).toBeInTheDocument();
		});

		it("hides commute fields when remote preference is Remote Only", () => {
			renderFields({ defaultValues: { remote_preference: "Remote Only" } });

			expect(
				screen.queryByLabelText(/commutable cities/i),
			).not.toBeInTheDocument();
			expect(screen.queryByLabelText(/max commute/i)).not.toBeInTheDocument();
		});

		it("toggles commute fields when switching remote preference", async () => {
			const user = renderFields({
				defaultValues: { remote_preference: "Hybrid OK" },
			});

			expect(screen.getByLabelText(/commutable cities/i)).toBeInTheDocument();

			await user.click(screen.getByLabelText("Remote Only"));

			expect(
				screen.queryByLabelText(/commutable cities/i),
			).not.toBeInTheDocument();

			await user.click(screen.getByLabelText("Onsite OK"));

			expect(screen.getByLabelText(/commutable cities/i)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Conditional visibility — relocation cities
	// -----------------------------------------------------------------------

	describe("relocation field visibility", () => {
		it("hides relocation cities when relocation is off", () => {
			renderFields({ defaultValues: { relocation_open: false } });

			expect(
				screen.queryByLabelText(/relocation cities/i),
			).not.toBeInTheDocument();
		});

		it("shows relocation cities when relocation is on", () => {
			renderFields({ defaultValues: { relocation_open: true } });

			expect(screen.getByLabelText(/relocation cities/i)).toBeInTheDocument();
		});

		it("toggles relocation cities when checkbox changes", async () => {
			const user = renderFields({
				defaultValues: { relocation_open: false },
			});

			expect(
				screen.queryByLabelText(/relocation cities/i),
			).not.toBeInTheDocument();

			await user.click(screen.getByLabelText(/open to relocation/i));

			expect(screen.getByLabelText(/relocation cities/i)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Conditional visibility — salary fields
	// -----------------------------------------------------------------------

	describe("salary field visibility", () => {
		it("hides salary fields when prefer_no_salary is true", () => {
			renderFields({ defaultValues: { prefer_no_salary: true } });

			expect(
				screen.queryByLabelText(/minimum base salary/i),
			).not.toBeInTheDocument();
			expect(screen.queryByLabelText(/currency/i)).not.toBeInTheDocument();
		});

		it("shows salary fields when prefer_no_salary is false", () => {
			renderFields({ defaultValues: { prefer_no_salary: false } });

			expect(screen.getByLabelText(/minimum base salary/i)).toBeInTheDocument();
			expect(screen.getByLabelText(/currency/i)).toBeInTheDocument();
		});

		it("toggles salary fields when checkbox changes", async () => {
			const user = renderFields({
				defaultValues: { prefer_no_salary: false },
			});

			expect(screen.getByLabelText(/minimum base salary/i)).toBeInTheDocument();

			await user.click(screen.getByLabelText(/prefer not to set/i));

			expect(
				screen.queryByLabelText(/minimum base salary/i),
			).not.toBeInTheDocument();
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
