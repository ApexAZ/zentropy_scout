/**
 * Tests for the OnboardingGate component.
 *
 * REQ-012 §3.3: Entry gate that redirects to /onboarding when
 * persona does not exist or onboarding is incomplete.
 */

import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { OnboardingGate } from "./onboarding-gate";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => {
	const mockUsePersonaStatus = vi.fn();
	const mockReplace = vi.fn();
	return { mockUsePersonaStatus, mockReplace };
});

vi.mock("@/hooks/use-persona-status", () => ({
	usePersonaStatus: mocks.mockUsePersonaStatus,
}));

vi.mock("next/navigation", () => ({
	useRouter: () => ({
		replace: mocks.mockReplace,
	}),
}));

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CHILD_TEXT = "Protected content";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderGate() {
	return render(
		<OnboardingGate>
			<div>{CHILD_TEXT}</div>
		</OnboardingGate>,
	);
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
	vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("OnboardingGate", () => {
	it("shows loading indicator while persona status is loading", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({ status: "loading" });
		renderGate();
		expect(screen.queryByText(CHILD_TEXT)).not.toBeInTheDocument();
		expect(screen.getByRole("status")).toBeInTheDocument();
	});

	it("does not render children during loading", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({ status: "loading" });
		renderGate();
		expect(screen.queryByText(CHILD_TEXT)).not.toBeInTheDocument();
	});

	it("redirects to /onboarding when needs-onboarding", async () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "needs-onboarding",
		});
		renderGate();
		await waitFor(() => {
			expect(mocks.mockReplace).toHaveBeenCalledWith("/onboarding");
		});
		expect(screen.queryByText(CHILD_TEXT)).not.toBeInTheDocument();
	});

	it("renders children when persona is onboarded", () => {
		const persona = { id: "test-id", onboarding_complete: true };
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "onboarded",
			persona,
		});
		renderGate();
		expect(screen.getByText(CHILD_TEXT)).toBeInTheDocument();
	});

	it("does not redirect when onboarded", () => {
		const persona = { id: "test-id", onboarding_complete: true };
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "onboarded",
			persona,
		});
		renderGate();
		expect(mocks.mockReplace).not.toHaveBeenCalled();
	});

	it("shows error state when API fails", () => {
		const error = new Error("Network error");
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "error",
			error,
		});
		renderGate();
		expect(screen.queryByText(CHILD_TEXT)).not.toBeInTheDocument();
		expect(screen.getByRole("alert")).toBeInTheDocument();
	});
});
