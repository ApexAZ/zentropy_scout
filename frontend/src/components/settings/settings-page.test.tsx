/**
 * Tests for the SettingsPage component (§11.1).
 *
 * REQ-012 §12.1: Settings page layout with Job Sources,
 * Agent Configuration, and About sections.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("./job-sources-section", () => ({
	JobSourcesSection: ({ personaId }: { personaId: string }) => (
		<div data-testid="mock-job-sources-section" data-persona-id={personaId} />
	),
}));

import { SettingsPage } from "./settings-page";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PAGE_TESTID = "settings-page";
const JOB_SOURCES_TESTID = "settings-job-sources";
const AGENT_CONFIG_TESTID = "settings-agent-configuration";
const ABOUT_TESTID = "settings-about";
const PERSONA_ID = "p-1";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SettingsPage", () => {
	afterEach(() => {
		cleanup();
	});

	it("renders settings page container", () => {
		render(<SettingsPage personaId={PERSONA_ID} />);
		expect(screen.getByTestId(PAGE_TESTID)).toBeInTheDocument();
	});

	it("displays 'Settings' heading", () => {
		render(<SettingsPage personaId={PERSONA_ID} />);
		expect(
			screen.getByRole("heading", { name: "Settings", level: 1 }),
		).toBeInTheDocument();
	});

	it("renders Job Sources section with title", () => {
		render(<SettingsPage personaId={PERSONA_ID} />);
		const section = screen.getByTestId(JOB_SOURCES_TESTID);
		expect(section).toBeInTheDocument();
		expect(section).toHaveTextContent("Job Sources");
	});

	it("renders Agent Configuration section with title", () => {
		render(<SettingsPage personaId={PERSONA_ID} />);
		const section = screen.getByTestId(AGENT_CONFIG_TESTID);
		expect(section).toBeInTheDocument();
		expect(section).toHaveTextContent("Agent Configuration");
	});

	it("renders About section with title", () => {
		render(<SettingsPage personaId={PERSONA_ID} />);
		const section = screen.getByTestId(ABOUT_TESTID);
		expect(section).toBeInTheDocument();
		expect(section).toHaveTextContent("About");
	});

	it("renders JobSourcesSection in the Job Sources card", () => {
		render(<SettingsPage personaId={PERSONA_ID} />);
		const mockChild = screen.getByTestId("mock-job-sources-section");
		expect(mockChild).toBeInTheDocument();
		expect(mockChild).toHaveAttribute("data-persona-id", PERSONA_ID);
	});

	it("shows placeholder text in Agent Configuration section", () => {
		render(<SettingsPage personaId={PERSONA_ID} />);
		const section = screen.getByTestId(AGENT_CONFIG_TESTID);
		expect(section).toHaveTextContent("Model routing (read-only)");
	});

	it("shows version info in About section", () => {
		render(<SettingsPage personaId={PERSONA_ID} />);
		const section = screen.getByTestId(ABOUT_TESTID);
		expect(section).toHaveTextContent("Zentropy Scout");
		expect(section).toHaveTextContent("AGPL-3.0");
	});

	it("shows auth placeholder in About section", () => {
		render(<SettingsPage personaId={PERSONA_ID} />);
		const section = screen.getByTestId(ABOUT_TESTID);
		expect(section).toHaveTextContent(
			"Single-user mode \u2014 no configuration needed.",
		);
	});
});
