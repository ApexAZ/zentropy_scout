/**
 * Tests for the JobSnapshotSection component (§10.9).
 *
 * REQ-012 §11.10: Expandable section on application detail page showing
 * frozen job data at application time. Shows all captured fields.
 * Includes captured_at timestamp and "View live posting" link.
 */

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { JobSnapshot } from "@/types/application";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SECTION_TESTID = "job-snapshot-section";
const TOGGLE_TESTID = "snapshot-toggle";
const DETAILS_TESTID = "snapshot-details";
const LIVE_POSTING_TESTID = "view-live-posting";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeSnapshot(overrides?: Partial<JobSnapshot>): JobSnapshot {
	return {
		title: "Senior Engineer",
		company_name: "Acme Corp",
		company_url: null,
		description: "Build scalable systems.",
		requirements: "5+ years TypeScript",
		salary_min: 120000,
		salary_max: 150000,
		salary_currency: "USD",
		location: "Austin, TX",
		work_model: "Remote",
		source_url: "https://example.com/job/42",
		captured_at: "2026-01-15T10:00:00Z",
		...overrides,
	};
}

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@/lib/job-formatters", () => ({
	formatDateTimeAgo: (iso: string) => `mocked-${iso}`,
	formatSnapshotSalary: (
		min: number | null,
		max: number | null,
		currency: string | null,
	) => `salary(${min},${max},${currency})`,
}));

vi.mock("@/lib/url-utils", () => ({
	isSafeUrl: (url: string) => url.startsWith("https://"),
}));

import { JobSnapshotSection } from "./job-snapshot-section";

// ---------------------------------------------------------------------------
// Teardown
// ---------------------------------------------------------------------------

afterEach(() => {
	cleanup();
	vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("JobSnapshotSection", () => {
	it("renders card with data-testid", () => {
		render(<JobSnapshotSection snapshot={makeSnapshot()} />);
		expect(screen.getByTestId(SECTION_TESTID)).toBeInTheDocument();
	});

	it("shows captured_at timestamp", () => {
		render(<JobSnapshotSection snapshot={makeSnapshot()} />);
		expect(screen.getByText(/mocked-2026-01-15T10:00:00Z/)).toBeInTheDocument();
	});

	it("shows 'View live posting' link when source_url is safe", () => {
		render(<JobSnapshotSection snapshot={makeSnapshot()} />);
		const link = screen.getByTestId(LIVE_POSTING_TESTID);
		expect(link).toHaveAttribute("href", "https://example.com/job/42");
	});

	it("hides 'View live posting' when source_url is null", () => {
		render(
			<JobSnapshotSection snapshot={makeSnapshot({ source_url: null })} />,
		);
		expect(screen.queryByTestId(LIVE_POSTING_TESTID)).not.toBeInTheDocument();
	});

	it("hides 'View live posting' when source_url is unsafe", () => {
		render(
			<JobSnapshotSection
				snapshot={makeSnapshot({ source_url: "javascript:alert(1)" })}
			/>,
		);
		expect(screen.queryByTestId(LIVE_POSTING_TESTID)).not.toBeInTheDocument();
	});

	it("starts collapsed (no snapshot-details visible)", () => {
		render(<JobSnapshotSection snapshot={makeSnapshot()} />);
		expect(screen.queryByTestId(DETAILS_TESTID)).not.toBeInTheDocument();
	});

	it("expand toggle reveals snapshot-details", async () => {
		const user = userEvent.setup();
		render(<JobSnapshotSection snapshot={makeSnapshot()} />);
		await user.click(screen.getByTestId(TOGGLE_TESTID));
		expect(screen.getByTestId(DETAILS_TESTID)).toBeInTheDocument();
	});

	it("second click collapses snapshot-details", async () => {
		const user = userEvent.setup();
		render(<JobSnapshotSection snapshot={makeSnapshot()} />);
		await user.click(screen.getByTestId(TOGGLE_TESTID));
		expect(screen.getByTestId(DETAILS_TESTID)).toBeInTheDocument();
		await user.click(screen.getByTestId(TOGGLE_TESTID));
		expect(screen.queryByTestId(DETAILS_TESTID)).not.toBeInTheDocument();
	});

	it("expanded shows description", async () => {
		const user = userEvent.setup();
		render(<JobSnapshotSection snapshot={makeSnapshot()} />);
		await user.click(screen.getByTestId(TOGGLE_TESTID));
		expect(screen.getByText("Build scalable systems.")).toBeInTheDocument();
	});

	it("expanded shows requirements", async () => {
		const user = userEvent.setup();
		render(<JobSnapshotSection snapshot={makeSnapshot()} />);
		await user.click(screen.getByTestId(TOGGLE_TESTID));
		expect(screen.getByText("5+ years TypeScript")).toBeInTheDocument();
	});

	it("expanded shows salary via formatSnapshotSalary", async () => {
		const user = userEvent.setup();
		render(<JobSnapshotSection snapshot={makeSnapshot()} />);
		await user.click(screen.getByTestId(TOGGLE_TESTID));
		expect(screen.getByText("salary(120000,150000,USD)")).toBeInTheDocument();
	});

	it("expanded shows location", async () => {
		const user = userEvent.setup();
		render(<JobSnapshotSection snapshot={makeSnapshot()} />);
		await user.click(screen.getByTestId(TOGGLE_TESTID));
		expect(screen.getByText("Austin, TX")).toBeInTheDocument();
	});

	it("expanded shows work_model", async () => {
		const user = userEvent.setup();
		render(<JobSnapshotSection snapshot={makeSnapshot()} />);
		await user.click(screen.getByTestId(TOGGLE_TESTID));
		expect(screen.getByText("Remote")).toBeInTheDocument();
	});

	it("shows 'Not specified' for null requirements", async () => {
		const user = userEvent.setup();
		render(
			<JobSnapshotSection snapshot={makeSnapshot({ requirements: null })} />,
		);
		await user.click(screen.getByTestId(TOGGLE_TESTID));
		expect(screen.getByTestId("snapshot-requirements")).toHaveTextContent(
			"Not specified",
		);
	});

	it("shows 'Not specified' for null location", async () => {
		const user = userEvent.setup();
		render(<JobSnapshotSection snapshot={makeSnapshot({ location: null })} />);
		await user.click(screen.getByTestId(TOGGLE_TESTID));
		expect(screen.getByTestId("snapshot-location")).toHaveTextContent(
			"Not specified",
		);
	});

	it("shows 'Not specified' for null work_model", async () => {
		const user = userEvent.setup();
		render(
			<JobSnapshotSection snapshot={makeSnapshot({ work_model: null })} />,
		);
		await user.click(screen.getByTestId(TOGGLE_TESTID));
		expect(screen.getByTestId("snapshot-work-model")).toHaveTextContent(
			"Not specified",
		);
	});
});
