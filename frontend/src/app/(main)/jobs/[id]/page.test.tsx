/**
 * Tests for the JobDetailPage route component (§7.7).
 *
 * Verifies guard clause and prop passthrough to JobDetailHeader.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import JobDetailPage from "./page";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MOCK_JOB_ID = "test-job-id";
const HEADER_TESTID = "job-detail-header-stub";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
	mockUsePersonaStatus: vi.fn(),
	mockUseParams: vi.fn(),
}));

vi.mock("@/hooks/use-persona-status", () => ({
	usePersonaStatus: mocks.mockUsePersonaStatus,
}));

vi.mock("next/navigation", () => ({
	useParams: mocks.mockUseParams,
}));

function MockJobDetailHeader({ jobId }: { jobId: string }) {
	return <div data-testid={HEADER_TESTID}>{jobId}</div>;
}
MockJobDetailHeader.displayName = "MockJobDetailHeader";

vi.mock("@/components/jobs/job-detail-header", () => ({
	JobDetailHeader: MockJobDetailHeader,
}));

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("JobDetailPage", () => {
	beforeEach(() => {
		mocks.mockUseParams.mockReturnValue({ id: MOCK_JOB_ID });
		mocks.mockUsePersonaStatus.mockReset();
	});

	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	it("renders nothing when status is loading", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({ status: "loading" });
		const { container } = render(<JobDetailPage />);

		expect(container.innerHTML).toBe("");
	});

	it("renders nothing when status is needs-onboarding", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "needs-onboarding",
		});
		const { container } = render(<JobDetailPage />);

		expect(container.innerHTML).toBe("");
	});

	it("renders JobDetailHeader with jobId from route params", () => {
		mocks.mockUsePersonaStatus.mockReturnValue({
			status: "onboarded",
			persona: { id: "p-1" },
		});
		render(<JobDetailPage />);

		const header = screen.getByTestId(HEADER_TESTID);
		expect(header).toBeInTheDocument();
		expect(header).toHaveTextContent(MOCK_JOB_ID);
	});
});
