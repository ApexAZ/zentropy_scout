/**
 * Tests for the UsageSummary component.
 *
 * REQ-020 §9.2: Period summary with total cost, call count,
 * token usage, and breakdowns by task type and provider.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { UsageSummaryResponse } from "@/types/usage";

import { UsageSummary } from "./usage-summary";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_SUMMARY: UsageSummaryResponse = {
	period_start: "2026-03-01",
	period_end: "2026-03-31",
	total_calls: 42,
	total_input_tokens: 10000,
	total_output_tokens: 5000,
	total_raw_cost_usd: "3.000000",
	total_billed_cost_usd: "3.900000",
	by_task_type: [
		{
			task_type: "extraction",
			call_count: 20,
			input_tokens: 5000,
			output_tokens: 2500,
			billed_cost_usd: "2.000000",
		},
		{
			task_type: "generation",
			call_count: 22,
			input_tokens: 5000,
			output_tokens: 2500,
			billed_cost_usd: "1.900000",
		},
	],
	by_provider: [
		{ provider: "claude", call_count: 30, billed_cost_usd: "2.500000" },
		{ provider: "openai", call_count: 12, billed_cost_usd: "1.400000" },
	],
};

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

afterEach(() => {
	cleanup();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("UsageSummary", () => {
	it("renders Period Summary heading", () => {
		render(<UsageSummary data={MOCK_SUMMARY} isLoading={false} />);
		expect(screen.getByText("Period Summary")).toBeInTheDocument();
	});

	it("shows total calls", () => {
		render(<UsageSummary data={MOCK_SUMMARY} isLoading={false} />);
		expect(screen.getByTestId("total-calls")).toHaveTextContent("42");
	});

	it("shows total billed cost formatted to 2 decimal places", () => {
		render(<UsageSummary data={MOCK_SUMMARY} isLoading={false} />);
		expect(screen.getByTestId("total-cost")).toHaveTextContent("$3.90");
	});

	it("shows total tokens", () => {
		render(<UsageSummary data={MOCK_SUMMARY} isLoading={false} />);
		expect(screen.getByTestId("total-tokens")).toHaveTextContent("15,000");
	});

	it("renders task type breakdown rows", () => {
		render(<UsageSummary data={MOCK_SUMMARY} isLoading={false} />);
		expect(screen.getByText("extraction")).toBeInTheDocument();
		expect(screen.getByText("generation")).toBeInTheDocument();
	});

	it("renders provider breakdown rows", () => {
		render(<UsageSummary data={MOCK_SUMMARY} isLoading={false} />);
		expect(screen.getByText("claude")).toBeInTheDocument();
		expect(screen.getByText("openai")).toBeInTheDocument();
	});

	it("shows loading state", () => {
		render(<UsageSummary data={undefined} isLoading={true} />);
		expect(screen.getByTestId("summary-loading")).toBeInTheDocument();
	});

	it("shows empty state when no data and not loading", () => {
		render(<UsageSummary data={undefined} isLoading={false} />);
		expect(screen.getByText(/no usage data/i)).toBeInTheDocument();
	});
});
