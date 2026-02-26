/**
 * Tests for the OnboardingShell layout component.
 *
 * REQ-012 §6.2: Full-screen layout with progress bar and navigation.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { OnboardingShell } from "./onboarding-shell";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const defaultProps = {
	currentStep: 3,
	totalSteps: 11,
	stepName: "Work History",
	onNext: vi.fn(),
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderShell(
	props: Partial<
		typeof defaultProps & {
			onBack: () => void;
			onSkip: () => void;
			isNextDisabled: boolean;
			isNextLoading: boolean;
		}
	> = {},
) {
	return render(
		<OnboardingShell {...defaultProps} {...props}>
			<div>Content</div>
		</OnboardingShell>,
	);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("OnboardingShell", () => {
	// -----------------------------------------------------------------------
	// Header
	// -----------------------------------------------------------------------

	describe("header", () => {
		it("renders the Zentropy Scout logo text", () => {
			renderShell();
			expect(screen.getByText("Zentropy Scout")).toBeInTheDocument();
		});

		it("shows step counter as 'Step N of M'", () => {
			renderShell();
			expect(screen.getByText("Step 3 of 11")).toBeInTheDocument();
		});

		it("renders a progress bar with correct value", () => {
			renderShell();
			const progressBar = screen.getByRole("progressbar");
			expect(progressBar).toBeInTheDocument();
			// Step 3 of 11 ≈ 27%
			expect(progressBar).toHaveAttribute("aria-valuenow", "27");
		});

		it("shows step name on hover via title attribute", () => {
			renderShell();
			const stepCounter = screen.getByText("Step 3 of 11");
			expect(stepCounter).toHaveAttribute("title", "Work History");
		});
	});

	// -----------------------------------------------------------------------
	// Content
	// -----------------------------------------------------------------------

	describe("content", () => {
		it("renders children in the content area", () => {
			render(
				<OnboardingShell {...defaultProps}>
					<div data-testid="child">Hello</div>
				</OnboardingShell>,
			);
			expect(screen.getByTestId("child")).toBeInTheDocument();
			expect(screen.getByText("Hello")).toBeInTheDocument();
		});

		it("wraps content in a main landmark", () => {
			renderShell();
			expect(screen.getByRole("main")).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Navigation buttons
	// -----------------------------------------------------------------------

	describe("navigation", () => {
		it("always renders the Next button", () => {
			renderShell();
			expect(screen.getByRole("button", { name: /next/i })).toBeInTheDocument();
		});

		it("calls onNext when Next is clicked", async () => {
			const onNext = vi.fn();
			const user = userEvent.setup();
			renderShell({ onNext });
			await user.click(screen.getByRole("button", { name: /next/i }));
			expect(onNext).toHaveBeenCalledOnce();
		});

		it("disables Next when isNextDisabled is true", () => {
			renderShell({ isNextDisabled: true });
			expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();
		});

		it("shows loading spinner on Next when isNextLoading is true", () => {
			renderShell({ isNextLoading: true });
			const nextBtn = screen.getByRole("button", { name: /next/i });
			expect(nextBtn).toBeDisabled();
			expect(nextBtn.querySelector("svg")).toBeInTheDocument();
		});

		it("renders Back button when onBack is provided", () => {
			renderShell({ onBack: vi.fn() });
			expect(screen.getByRole("button", { name: /back/i })).toBeInTheDocument();
		});

		it("does not render Back button when onBack is not provided", () => {
			renderShell();
			expect(
				screen.queryByRole("button", { name: /back/i }),
			).not.toBeInTheDocument();
		});

		it("calls onBack when Back is clicked", async () => {
			const onBack = vi.fn();
			const user = userEvent.setup();
			renderShell({ onBack });
			await user.click(screen.getByRole("button", { name: /back/i }));
			expect(onBack).toHaveBeenCalledOnce();
		});

		it("renders Skip button when onSkip is provided", () => {
			renderShell({ onSkip: vi.fn() });
			expect(screen.getByRole("button", { name: /skip/i })).toBeInTheDocument();
		});

		it("does not render Skip button when onSkip is not provided", () => {
			renderShell();
			expect(
				screen.queryByRole("button", { name: /skip/i }),
			).not.toBeInTheDocument();
		});

		it("calls onSkip when Skip is clicked", async () => {
			const onSkip = vi.fn();
			const user = userEvent.setup();
			renderShell({ onSkip });
			await user.click(screen.getByRole("button", { name: /skip/i }));
			expect(onSkip).toHaveBeenCalledOnce();
		});

		it("wraps navigation in a nav landmark", () => {
			renderShell({ onBack: vi.fn() });
			expect(
				screen.getByRole("navigation", { name: /onboarding/i }),
			).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Full-screen layout
	// -----------------------------------------------------------------------

	describe("layout", () => {
		it("uses full screen height", () => {
			renderShell();
			const shell = screen
				.getByRole("main")
				.closest('[data-slot="onboarding-shell"]');
			expect(shell).toBeInTheDocument();
			expect(shell).toHaveClass("min-h-screen");
		});

		it("renders the last step correctly", () => {
			renderShell({ currentStep: 11, stepName: "Review" });
			expect(screen.getByText("Step 11 of 11")).toBeInTheDocument();
			const progressBar = screen.getByRole("progressbar");
			expect(progressBar).toHaveAttribute("aria-valuenow", "100");
		});

		it("renders the first step correctly", () => {
			renderShell({ currentStep: 1, stepName: "Resume Upload" });
			expect(screen.getByText("Step 1 of 11")).toBeInTheDocument();
			const progressBar = screen.getByRole("progressbar");
			// Step 1 of 11 ≈ 9%
			expect(progressBar).toHaveAttribute("aria-valuenow", "9");
		});
	});
});
