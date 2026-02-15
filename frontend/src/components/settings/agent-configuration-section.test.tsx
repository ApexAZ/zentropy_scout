/**
 * Tests for the AgentConfigurationSection component (§11.3).
 *
 * REQ-012 §12.1: Read-only card displaying model routing categories
 * and provider info. Static data — no API calls needed.
 */

import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { AgentConfigurationSection } from "./agent-configuration-section";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SECTION_TESTID = "agent-configuration-section";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AgentConfigurationSection", () => {
	afterEach(() => {
		cleanup();
	});

	it("renders section container", () => {
		render(<AgentConfigurationSection />);
		expect(screen.getByTestId(SECTION_TESTID)).toBeInTheDocument();
	});

	it("displays 'Model Routing' label", () => {
		render(<AgentConfigurationSection />);
		expect(screen.getByText("Model Routing")).toBeInTheDocument();
	});

	it("shows 'read-only' indicator", () => {
		render(<AgentConfigurationSection />);
		expect(screen.getByText(/read-only/i)).toBeInTheDocument();
	});

	it("renders Chat / Onboarding category", () => {
		render(<AgentConfigurationSection />);
		expect(screen.getByText("Chat / Onboarding")).toBeInTheDocument();
	});

	it("renders Scouter / Ghost Detection category", () => {
		render(<AgentConfigurationSection />);
		expect(screen.getByText("Scouter / Ghost Detection")).toBeInTheDocument();
	});

	it("renders Scoring / Generation category", () => {
		render(<AgentConfigurationSection />);
		expect(screen.getByText("Scoring / Generation")).toBeInTheDocument();
	});

	it("shows Sonnet model for Chat / Onboarding category", () => {
		render(<AgentConfigurationSection />);
		const row = screen.getByTestId("routing-row-chat-onboarding");
		expect(within(row).getByText("Claude 3.5 Sonnet")).toBeInTheDocument();
	});

	it("shows Haiku model for Scouter / Ghost Detection category", () => {
		render(<AgentConfigurationSection />);
		const row = screen.getByTestId("routing-row-scouter-ghost-detection");
		expect(within(row).getByText("Claude 3.5 Haiku")).toBeInTheDocument();
	});

	it("shows Sonnet model for Scoring / Generation category", () => {
		render(<AgentConfigurationSection />);
		const row = screen.getByTestId("routing-row-scoring-generation");
		expect(within(row).getByText("Claude 3.5 Sonnet")).toBeInTheDocument();
	});

	it("renders provider info", () => {
		render(<AgentConfigurationSection />);
		expect(screen.getByText(/Local \(Claude SDK\)/)).toBeInTheDocument();
	});

	it("renders correct number of routing rows", () => {
		render(<AgentConfigurationSection />);
		const rows = screen.getAllByTestId(/^routing-row-/);
		expect(rows).toHaveLength(3);
	});
});
