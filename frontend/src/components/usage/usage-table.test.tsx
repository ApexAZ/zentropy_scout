/**
 * Tests for the UsageTable component.
 *
 * REQ-020 §9.2: Recent activity — paginated table of
 * individual usage records.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { UsageRecordResponse } from "@/types/usage";

import { UsageTable } from "./usage-table";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_RECORDS: UsageRecordResponse[] = [
	{
		id: "u-1",
		provider: "claude",
		model: "claude-3-5-haiku-20241022",
		task_type: "extraction",
		input_tokens: 500,
		output_tokens: 200,
		billed_cost_usd: "0.001300",
		created_at: "2026-03-01T10:00:00Z",
	},
	{
		id: "u-2",
		provider: "openai",
		model: "gpt-4o-mini",
		task_type: "generation",
		input_tokens: 1000,
		output_tokens: 500,
		billed_cost_usd: "0.005200",
		created_at: "2026-03-01T11:00:00Z",
	},
];

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

afterEach(() => {
	cleanup();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("UsageTable", () => {
	const defaultProps = {
		records: MOCK_RECORDS,
		isLoading: false,
		page: 1,
		totalPages: 1,
		onPageChange: vi.fn(),
	};

	it("renders Recent Activity heading", () => {
		render(<UsageTable {...defaultProps} />);
		expect(screen.getByText("Recent Activity")).toBeInTheDocument();
	});

	it("renders usage records with provider and model", () => {
		render(<UsageTable {...defaultProps} />);
		expect(screen.getByText("claude")).toBeInTheDocument();
		expect(screen.getByText("openai")).toBeInTheDocument();
		expect(screen.getByText("claude-3-5-haiku-20241022")).toBeInTheDocument();
	});

	it("renders task type column", () => {
		render(<UsageTable {...defaultProps} />);
		expect(screen.getByText("extraction")).toBeInTheDocument();
		expect(screen.getByText("generation")).toBeInTheDocument();
	});

	it("shows empty state when no records", () => {
		render(<UsageTable {...defaultProps} records={[]} />);
		expect(screen.getByText(/no usage records/i)).toBeInTheDocument();
	});

	it("shows loading state", () => {
		render(<UsageTable {...defaultProps} records={[]} isLoading={true} />);
		expect(screen.getByTestId("usage-table-loading")).toBeInTheDocument();
	});

	it("disables Previous button on first page", () => {
		render(<UsageTable {...defaultProps} page={1} totalPages={3} />);
		expect(screen.getByRole("button", { name: /previous/i })).toBeDisabled();
	});

	it("disables Next button on last page", () => {
		render(<UsageTable {...defaultProps} page={3} totalPages={3} />);
		expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();
	});

	it("calls onPageChange with next page when Next is clicked", () => {
		const onPageChange = vi.fn();
		render(
			<UsageTable
				{...defaultProps}
				page={1}
				totalPages={3}
				onPageChange={onPageChange}
			/>,
		);
		screen.getByRole("button", { name: /next/i }).click();
		expect(onPageChange).toHaveBeenCalledWith(2);
	});

	it("calls onPageChange with previous page when Previous is clicked", () => {
		const onPageChange = vi.fn();
		render(
			<UsageTable
				{...defaultProps}
				page={2}
				totalPages={3}
				onPageChange={onPageChange}
			/>,
		);
		screen.getByRole("button", { name: /previous/i }).click();
		expect(onPageChange).toHaveBeenCalledWith(1);
	});

	it("shows < $0.01 for sub-cent costs", () => {
		render(<UsageTable {...defaultProps} records={[MOCK_RECORDS[0]]} />);
		expect(screen.getByText("< $0.01")).toBeInTheDocument();
	});
});
