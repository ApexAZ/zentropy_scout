/**
 * Tests for SubmitButton component.
 *
 * REQ-012 §13.2: Spinner on buttons during async operations.
 * Disabled inputs during submission.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SubmitButton } from "./submit-button";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_LABEL = "Save";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SubmitButton", () => {
	it("shows label when not submitting", () => {
		render(<SubmitButton label={DEFAULT_LABEL} isSubmitting={false} />);
		expect(
			screen.getByRole("button", { name: DEFAULT_LABEL }),
		).toBeInTheDocument();
	});

	it("is not disabled when not submitting", () => {
		render(<SubmitButton label={DEFAULT_LABEL} isSubmitting={false} />);
		expect(screen.getByRole("button")).not.toBeDisabled();
	});

	it("shows spinner when submitting", () => {
		render(<SubmitButton label={DEFAULT_LABEL} isSubmitting />);
		expect(screen.getByTestId("submit-spinner")).toBeInTheDocument();
	});

	it("is disabled when submitting", () => {
		render(<SubmitButton label={DEFAULT_LABEL} isSubmitting />);
		expect(screen.getByRole("button")).toBeDisabled();
	});

	it("shows loading label when submitting and loadingLabel provided", () => {
		render(
			<SubmitButton
				label={DEFAULT_LABEL}
				loadingLabel="Saving..."
				isSubmitting
			/>,
		);
		expect(screen.getByText("Saving...")).toBeInTheDocument();
	});

	it("falls back to label when submitting and no loadingLabel", () => {
		render(<SubmitButton label={DEFAULT_LABEL} isSubmitting />);
		expect(screen.getByText(DEFAULT_LABEL)).toBeInTheDocument();
	});

	it("is disabled when disabled prop is true even when not submitting", () => {
		render(
			<SubmitButton label={DEFAULT_LABEL} isSubmitting={false} disabled />,
		);
		expect(screen.getByRole("button")).toBeDisabled();
	});
});
